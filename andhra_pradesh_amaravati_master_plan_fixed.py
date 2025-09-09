import os
import json
import glob
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import math

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import box, shape, mapping, Point
from shapely.ops import transform
import mercantile
from PIL import Image, ImageDraw, ImageFont
import pyproj
from functools import partial
import warnings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

class AmaravatiTileGenerator:
    """Generate PNG tiles for Amaravati Master Plan with perfect rendering."""
    
    def __init__(self, data_dir: str, output_dir: str = "tiles"):
        """
        Initialize the tile generator.
        
        Args:
            data_dir: Directory containing GeoJSON files
            output_dir: Directory for output tiles
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Zoom level configuration - FIXED for multiple zoom levels
        self.min_zoom = 4
        self.max_zoom = 9
        
        # Tile size
        self.tile_size = 256
        
        # No buffer needed for vector data - exact tile boundaries ensure seamless rendering
        
        # Coordinate transformers
        self.transformer_to_3857 = pyproj.Transformer.from_crs(
            "EPSG:4326", "EPSG:3857", always_xy=True
        )
        self.transformer_to_4326 = pyproj.Transformer.from_crs(
            "EPSG:3857", "EPSG:4326", always_xy=True
        )
        
        # Complete styling configuration - all 41 zones
        self.zoning_styles = {
            "Burial Ground": {"fill_color": "#E39E00"},
            "C1 -Mixed use zone": {"fill_color": "#73B2FF"},
            "C2- General commercial zone": {"fill_color": "#00C5FF"},
            "C3-Neighbourhood centre zone": {"fill_color": "#00C5FF"},
            "C4-Town centre zone": {"fill_color": "#00A9E6"},
            "C5-Regional centre zone": {"fill_color": "#0070FF"},
            "C6-Central business district zone": {"fill_color": "#005CE6"},
            "Commercial Vacant": {"fill_color": "#C5E2FF"},
            "I1-Business park zone": {"fill_color": "#FFBEE8"},
            "I2-Logistics zone": {"fill_color": "#FF73DF"},
            "I3-Non polluting industry zone": {"fill_color": "#A900E6"},
            "P1-Passive zone": {"fill_color": "#267300"},
            "P2-Active zone": {"fill_color": "#38A800"},
            "P3-Protected zone": {"fill_color": "#BEE8FF"},
            "P3-Protected zone Hills": {"fill_color": "#4C7300"},
            "PGN-G": {"fill_color": "#4C7300"},
            "PGN-V": {"fill_color": "#897044"},
            "R1-Village planning zone": {"fill_color": "#F0F0F0"},
            "R3-Medium to high density zone": {"fill_color": "#F5CA7A"},
            "R4-High density zone": {"fill_color": "#E69800"},
            "RAA": {"fill_color": "#FFAA00"},
            "Residential Vacant": {"fill_color": "#FFD37F"},
            "S2-Education zone": {"fill_color": "#FF7F7F"},
            "S3-Special zone": {"fill_color": "#D7B09E"},
            "SC1a-Mixed Use": {"fill_color": "#0070FF"},
            "SC1b - Mixed Use": {"fill_color": "#73B2FF"},
            "SP1- Passive Zone": {"fill_color": "#267300"},
            "SP2- Active Zone": {"fill_color": "#38A800"},
            "SP3-Protected Zone": {"fill_color": "#00C5FF"},
            "SR2 Low Density Housing": {"fill_color": "#FFFFBE"},
            "SR4 - High Density Private": {"fill_color": "#FFAA00"},
            "SS1 - Government Zone": {"fill_color": "#E60000"},
            "SS2a- Education Zone": {"fill_color": "#FF7F7F"},
            "SS2b Cultural Zone": {"fill_color": "#C500FF"},
            "SS2c Health Zone": {"fill_color": "#D3FFBE"},
            "SS3 - Special Zone": {"fill_color": "#A83B00"},
            "SU1-Reserve Zone": {"fill_color": "#E1E1E1"},
            "SU2 - Road Network": {"fill_color": "#F8F8F8"},
            "U1-Reserve zone": {"fill_color": "#CCCCCC"},
            "U2- Road Reserve Zone": {"fill_color": "#404040"},
            "Not Available": {"fill_color": "#B6B6B6"}
        }
        
        # Statistics tracking
        self.stats = {
            "total_features": 0,
            "zones_found": set(),
            "tiles_generated": 0,
            "empty_tiles_skipped": 0,
            "features_per_zoom": defaultdict(int)
        }
        
    def load_all_geojson_files(self) -> gpd.GeoDataFrame:
        """Load and merge all GeoJSON files."""
        logger.info(f"Loading GeoJSON files from {self.data_dir}")
        
        all_gdfs = []
        geojson_files = list(self.data_dir.glob("*.geojson"))
        
        if not geojson_files:
            raise ValueError(f"No GeoJSON files found in {self.data_dir}")
        
        logger.info(f"Found {len(geojson_files)} GeoJSON files")
        
        for file_path in geojson_files:
            try:
                # Extract zone name from filename
                zone_name = file_path.stem
                logger.info(f"Loading {zone_name}...")
                
                # Load GeoJSON
                gdf = gpd.read_file(file_path)
                
                # Ensure CRS is set to WGS84
                if gdf.crs is None:
                    gdf.set_crs("EPSG:4326", inplace=True)
                elif gdf.crs.to_epsg() != 4326:
                    gdf = gdf.to_crs("EPSG:4326")
                
                # Add zone information based on filename
                gdf['zone_type'] = zone_name
                
                # Also check for symbology attribute in the data
                if 'symbology' in gdf.columns:
                    # Use symbology as primary zone identifier if available
                    gdf['zone_type'] = gdf['symbology'].fillna(zone_name)
                
                # Fix invalid geometries
                gdf['geometry'] = gdf['geometry'].buffer(0)
                
                # Remove empty geometries
                gdf = gdf[~gdf.geometry.is_empty]
                
                if len(gdf) > 0:
                    all_gdfs.append(gdf)
                    # Track unique zone values
                    unique_zones = gdf['zone_type'].unique()
                    for zone in unique_zones:
                        self.stats["zones_found"].add(zone)
                    logger.info(f"  Loaded {len(gdf)} features from {zone_name}")
                
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
                continue
        
        if not all_gdfs:
            raise ValueError("No valid GeoJSON data could be loaded")
        
        # Combine all GeoDataFrames
        combined_gdf = gpd.GeoDataFrame(
            pd.concat(all_gdfs, ignore_index=True),
            crs="EPSG:4326"
        )
        
        # Keep in WGS84 for now - we'll project to Web Mercator only when needed
        # combined_gdf = combined_gdf.to_crs("EPSG:3857")
        
        self.stats["total_features"] = len(combined_gdf)
        logger.info(f"Loaded {self.stats['total_features']} total features from {len(self.stats['zones_found'])} zones")
        
        # Log zones found
        logger.info("Zones found in data:")
        for zone in sorted(self.stats["zones_found"]):
            count = len(combined_gdf[combined_gdf['zone_type'] == zone])
            logger.info(f"  - {zone}: {count} features")
        
        return combined_gdf
    
    def get_tiles_for_bounds(self, gdf: gpd.GeoDataFrame, zoom: int) -> List[mercantile.Tile]:
        """Get all tiles that intersect with the data bounds at given zoom level."""
        # Get bounds in WGS84 (data is already in WGS84)
        bounds_4326 = gdf.total_bounds
        min_x, min_y, max_x, max_y = bounds_4326
        
        # Add a buffer to ensure we capture tiles at low zoom levels
        # For low zoom levels, we need a larger buffer to ensure we get tiles
        if zoom <= 8:
            buffer = 0.1  # Larger buffer for low zoom levels
        else:
            buffer = 0.01  # Smaller buffer for higher zoom levels
        
        # Apply buffer to bounds
        buffered_min_x = max(-180, min_x - buffer)
        buffered_min_y = max(-85, min_y - buffer)
        buffered_max_x = min(180, max_x + buffer)
        buffered_max_y = min(85, max_y + buffer)
        
        # Get tiles for buffered bounds
        tiles = list(mercantile.tiles(buffered_min_x, buffered_min_y, buffered_max_x, buffered_max_y, [zoom]))
        
        # If no tiles found (shouldn't happen with buffer), try without buffer
        if not tiles:
            logger.warning(f"No tiles found with buffer for zoom {zoom}, trying without buffer")
            tiles = list(mercantile.tiles(min_x, min_y, max_x, max_y, [zoom]))
        
        logger.info(f"  Found {len(tiles)} tiles for zoom {zoom} (bounds: {buffered_min_x:.6f}, {buffered_min_y:.6f}, {buffered_max_x:.6f}, {buffered_max_y:.6f})")
        
        return tiles
    
    def world_to_pixel(self, x: float, y: float, tile_bounds: Tuple[float, float, float, float], 
                      tile_size: int = 256, buffer_pixels: int = 0) -> Tuple[float, float]:
        """
        Convert world coordinates to pixel coordinates within a tile.
        
        Args:
            x: X coordinate in Web Mercator
            y: Y coordinate in Web Mercator
            tile_bounds: Tuple of (west, south, east, north) in Web Mercator
            tile_size: Size of the tile in pixels
            buffer_pixels: Additional buffer in pixels
        """
        west, south, east, north = tile_bounds
        
        # Calculate scale factors
        x_scale = (tile_size + 2 * buffer_pixels) / (east - west)
        y_scale = (tile_size + 2 * buffer_pixels) / (north - south)
        
        # Convert to pixel coordinates
        px = (x - west) * x_scale
        py = (north - y) * y_scale  # Y is inverted
        
        return px, py
    
    def render_tile(self, tile: mercantile.Tile, gdf: gpd.GeoDataFrame) -> Optional[Image.Image]:
        """
        Render a single tile with exact boundary clipping for seamless vector rendering.
        
        Key improvements for continuous vector data:
        - No buffers to prevent overlapping renders
        - Exact geometry clipping to tile boundaries
        - Prevents stitching artifacts between adjacent tiles
        """
        # Get tile bounds in WGS84
        tile_bounds = mercantile.bounds(tile)
        
        # Create image with light gray background (makes light colors more visible)
        img = Image.new('RGB', (self.tile_size, self.tile_size), (240, 240, 240))
        draw = ImageDraw.Draw(img)
        
        # Convert to pixel coordinates function (from reference)
        def coord_to_pixel(lon, lat):
            # Simple linear interpolation within tile bounds
            tile_x = (lon - tile_bounds.west) / (tile_bounds.east - tile_bounds.west) * self.tile_size
            tile_y = (tile_bounds.north - lat) / (tile_bounds.north - tile_bounds.south) * self.tile_size
            return tile_x, tile_y
        
        # Create EXACT tile geometry - NO BUFFER for continuous vector rendering
        # This prevents overlapping renders and stitching artifacts
        exact_tile_geom = box(
            tile_bounds.west,
            tile_bounds.south, 
            tile_bounds.east,
            tile_bounds.north
        )
        
        # Get features that intersect with the exact tile boundary
        # This ensures seamless tile-to-tile rendering
        intersecting_features = gdf[gdf.geometry.intersects(exact_tile_geom)]
        
        # For vector data, we want to clip geometries to exact tile boundaries
        # This prevents features from being rendered multiple times across adjacent tiles
        clipped_features = []
        for idx, feature in intersecting_features.iterrows():
            try:
                # Clip geometry to exact tile boundary
                clipped_geom = feature.geometry.intersection(exact_tile_geom)
                
                # Only keep non-empty geometries - NO area threshold
                # This ensures ALL features are rendered, no matter how small
                if not clipped_geom.is_empty:
                    feature_copy = feature.copy()
                    feature_copy.geometry = clipped_geom
                    clipped_features.append(feature_copy)
            except Exception as e:
                # If clipping fails, include the original geometry
                # This handles edge cases with invalid geometries
                clipped_features.append(feature)
        
        # Convert back to GeoDataFrame
        if clipped_features:
            all_features = gpd.GeoDataFrame(clipped_features, crs=gdf.crs)
        else:
            all_features = gpd.GeoDataFrame(columns=gdf.columns, crs=gdf.crs)
        
        rendered_count = 0
        
        # Define rendering order (background to foreground)
        # Roads and infrastructure should render first, then buildings/zones
        rendering_priority = {
            "U2- Road Reserve Zone": 1,  # Roads first (background)
            "SU2 - Road Network": 1,
            "U1-Reserve zone": 2,
            "SU1-Reserve Zone": 2,
            "P1-Passive zone": 3,
            "P2-Active zone": 3,
            "P3-Protected zone": 3,
            "P3-Protected zone Hills": 3,
            "Commercial Vacant": 4,
            "Residential Vacant": 4,
            "C2- General commercial zone": 5,  # Main zones
            "R3-Medium to high density zone": 5,
            "C1 -Mixed use zone": 6,
            "C3-Neighbourhood centre zone": 6,
            "C4-Town centre zone": 6,
            "C5-Regional centre zone": 6,
            "C6-Central business district zone": 6,
            "S2-Education zone": 7,  # Special zones on top
            "S3-Special zone": 7,
            "SS1 - Government Zone": 8,  # Important zones last
            "SS2a- Education Zone": 8,
            "SS2b Cultural Zone": 8,
            "SS2c Health Zone": 8,
        }
        
        # Sort features by rendering priority (lower numbers render first)
        all_features['render_priority'] = all_features['zone_type'].map(
            lambda x: rendering_priority.get(x, 5)  # Default priority 5
        )
        all_features = all_features.sort_values('render_priority')
        
        # Render each feature in priority order
        for idx, feature in all_features.iterrows():
            zone_type = feature.get('zone_type', 'Not Available')
            geom = feature.geometry
            
            # Get style for zone type
            style = self.zoning_styles.get(zone_type)
            if not style:
                # Try to find a partial match
                for key in self.zoning_styles:
                    if key in str(zone_type) or str(zone_type) in key:
                        style = self.zoning_styles[key]
                        break
                
                if not style:
                    style = self.zoning_styles['Not Available']
            
            # Get fill color 
            fill_color = self.hex_to_rgb(style['fill_color'])
            
            # For road zones, use a lighter shade to reduce dominance
            if zone_type == "U2- Road Reserve Zone":
                # Make road reserves lighter so they don't dominate
                r, g, b = fill_color
                # Lighten the color by 40%
                fill_color = (
                    min(255, int(r + (255 - r) * 0.4)),
                    min(255, int(g + (255 - g) * 0.4)),
                    min(255, int(b + (255 - b) * 0.4))
                )
            
            # Convert geometry to pixel coordinates and draw
            if geom.geom_type == 'Polygon':
                coords = []
                for coord in geom.exterior.coords:
                    if len(coord) >= 2:
                        lon, lat = coord[0], coord[1]
                        px, py = coord_to_pixel(lon, lat)
                        coords.append((px, py))
                
                if len(coords) > 2:
                    # Check if polygon is too small (single point or very small area)
                    min_x = min(coord[0] for coord in coords)
                    max_x = max(coord[0] for coord in coords)
                    min_y = min(coord[1] for coord in coords)
                    max_y = max(coord[1] for coord in coords)
                    
                    width = max_x - min_x
                    height = max_y - min_y
                    
                    # If polygon is too small, draw as a rectangle with minimum size
                    if width < 1 and height < 1:
                        # Draw a small rectangle at the center
                        center_x = (min_x + max_x) / 2
                        center_y = (min_y + max_y) / 2
                        size = max(2, min(8, 256 // (2 ** (tile.z - 4))))  # Scale with zoom
                        draw.rectangle([center_x - size/2, center_y - size/2, 
                                       center_x + size/2, center_y + size/2], 
                                      fill=fill_color)
                    else:
                        # Fill only - no borders between features
                        draw.polygon(coords, fill=fill_color)
                    rendered_count += 1
            
            elif geom.geom_type == 'MultiPolygon':
                for poly in geom.geoms:
                    coords = []
                    for coord in poly.exterior.coords:
                        if len(coord) >= 2:
                            lon, lat = coord[0], coord[1]
                            px, py = coord_to_pixel(lon, lat)
                            coords.append((px, py))
                    
                    if len(coords) > 2:
                        # Check if polygon is too small (single point or very small area)
                        min_x = min(coord[0] for coord in coords)
                        max_x = max(coord[0] for coord in coords)
                        min_y = min(coord[1] for coord in coords)
                        max_y = max(coord[1] for coord in coords)
                        
                        width = max_x - min_x
                        height = max_y - min_y
                        
                        # If polygon is too small, draw as a rectangle with minimum size
                        if width < 1 and height < 1:
                            # Draw a small rectangle at the center
                            center_x = (min_x + max_x) / 2
                            center_y = (min_y + max_y) / 2
                            size = max(2, min(8, 256 // (2 ** (tile.z - 4))))  # Scale with zoom
                            draw.rectangle([center_x - size/2, center_y - size/2, 
                                           center_x + size/2, center_y + size/2], 
                                          fill=fill_color)
                        else:
                            # Fill only - no borders between features
                            draw.polygon(coords, fill=fill_color)
                        rendered_count += 1
            
            elif geom.geom_type == 'Point':
                # Handle point features with zoom-dependent sizing
                lon, lat = geom.x, geom.y
                px, py = coord_to_pixel(lon, lat)
                # Scale radius based on zoom level - larger at higher zoom
                if tile.z >= 16:
                    radius = 8
                elif tile.z >= 12:
                    radius = 6
                elif tile.z >= 10:
                    radius = 4
                else:
                    radius = 2
                draw.ellipse([px-radius, py-radius, px+radius, py+radius], fill=fill_color)
                rendered_count += 1
        
        if rendered_count > 0:
            self.stats["features_per_zoom"][tile.z] += rendered_count
            return img
        
        return None
    
    def draw_polygon(self, draw: ImageDraw.Draw, polygon, tile_bounds: Tuple[float, float, float, float],
                    fill_color: Tuple[int, int, int, int], outline_color: Tuple[int, int, int, int]) -> bool:
        """
        Draw a polygon on the image.
        
        Returns:
            bool: True if polygon was drawn, False if skipped
        """
        try:
            # Convert exterior ring to pixel coordinates
            exterior_coords = []
            for x, y in polygon.exterior.coords:
                px, py = self.world_to_pixel(x, y, tile_bounds, self.tile_size)
                exterior_coords.append((px, py))
            
            # Check if polygon is visible in tile
            if not exterior_coords:
                return False
            
            # Check if any point is within the tile bounds (with margin)
            margin = 50  # pixels
            has_visible_point = any(
                -margin <= px <= self.tile_size + margin and 
                -margin <= py <= self.tile_size + margin 
                for px, py in exterior_coords
            )
            
            if not has_visible_point and len(exterior_coords) < 100:
                # Skip if polygon is completely outside and not very complex
                return False
            
            if len(exterior_coords) >= 3:
                # Draw filled polygon
                draw.polygon(exterior_coords, fill=fill_color, outline=outline_color, width=1)
                
                # Handle holes if present
                for interior in polygon.interiors:
                    hole_coords = []
                    for x, y in interior.coords:
                        px, py = self.world_to_pixel(x, y, tile_bounds, self.tile_size)
                        hole_coords.append((px, py))
                    
                    if len(hole_coords) >= 3:
                        # Draw hole with transparent fill
                        draw.polygon(hole_coords, fill=(0, 0, 0, 0), outline=outline_color, width=1)
                
                return True
        except Exception as e:
            logger.debug(f"Error drawing polygon: {e}")
            return False
        
        return False
    
    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def generate_tiles_for_zoom(self, gdf: gpd.GeoDataFrame, zoom: int):
        """Generate all tiles for a specific zoom level."""
        logger.info(f"Generating tiles for zoom level {zoom}")
        
        # Log bounds for debugging
        bounds = gdf.total_bounds
        logger.info(f"  Data bounds: {bounds}")
        
        # Get all tiles that intersect with data
        tiles = self.get_tiles_for_bounds(gdf, zoom)
        logger.info(f"Processing {len(tiles)} tiles at zoom {zoom}")
        
        if len(tiles) == 0:
            logger.warning(f"No tiles found for zoom {zoom} - this might indicate an issue with bounds calculation")
        
        tiles_generated = 0
        empty_skipped = 0
        
        for i, tile in enumerate(tiles):
            if i % 100 == 0 and i > 0:
                logger.info(f"  Processed {i}/{len(tiles)} tiles at zoom {zoom}")
            
            # Render tile
            img = self.render_tile(tile, gdf)
            
            if img is not None:
                # Check if image has content (not mostly background color)
                img_array = np.array(img)
                # For RGB mode, check if less than 95% of pixels are background color (240, 240, 240)
                background_pixels = np.sum((img_array[:, :, 0] == 240) & 
                                          (img_array[:, :, 1] == 240) & 
                                          (img_array[:, :, 2] == 240))
                total_pixels = img_array.shape[0] * img_array.shape[1]
                background_percentage = (background_pixels / total_pixels) * 100
                # More lenient content detection for low zoom levels
                # At low zoom levels, features are small relative to tile size
                if tile.z <= 6:
                    has_content = background_percentage < 99.9  # Very lenient for very low zoom
                elif tile.z <= 8:
                    has_content = background_percentage < 99.5  # More lenient for low zoom
                else:
                    has_content = background_percentage < 95.0  # Standard threshold for higher zoom
                if has_content:
                    # Save tile
                    tile_dir = self.output_dir / str(zoom) / str(tile.x)
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    
                    tile_path = tile_dir / f"{tile.y}.png"
                    img.save(tile_path, 'PNG', optimize=True, compress_level=9)
                    tiles_generated += 1
                else:
                    empty_skipped += 1
            else:
                empty_skipped += 1
        
        logger.info(f"Zoom {zoom}: Generated {tiles_generated} tiles, skipped {empty_skipped} empty tiles")
        self.stats["tiles_generated"] += tiles_generated
        self.stats["empty_tiles_skipped"] += empty_skipped
    
    def generate_all_tiles(self):
        """Generate tiles for all zoom levels."""
        logger.info("Starting tile generation process")
        
        # Load all GeoJSON data
        gdf = self.load_all_geojson_files()
        
        # Create spatial index for faster queries
        logger.info("Creating spatial index...")
        gdf.sindex
        
        # Generate tiles for each zoom level
        for zoom in range(self.min_zoom, self.max_zoom + 1):
            self.generate_tiles_for_zoom(gdf, zoom)
        
        # Print statistics
        self.print_statistics()
    
    def generate_tiles_parallel(self, max_workers: int = 4):
        """Generate tiles using parallel processing."""
        logger.info(f"Starting parallel tile generation with {max_workers} workers")
        
        # Load all GeoJSON data
        gdf = self.load_all_geojson_files()
        
        # Create spatial index for faster queries
        logger.info("Creating spatial index...")
        gdf.sindex
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for zoom in range(self.min_zoom, self.max_zoom + 1):
                future = executor.submit(self.generate_tiles_for_zoom, gdf, zoom)
                futures.append((zoom, future))
            
            # Wait for all tasks to complete
            for zoom, future in futures:
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error generating tiles for zoom {zoom}: {e}")
        
        # Print statistics
        self.print_statistics()
    
    def generate_tiles_for_zoom_range(self, min_zoom: int, max_zoom: int, max_workers: int = 4):
        """Generate tiles for a specific zoom range - useful for Mapbox/CloudFront deployment."""
        logger.info(f"Generating tiles for zoom range {min_zoom}-{max_zoom}")
        
        # Temporarily override zoom settings
        original_min = self.min_zoom
        original_max = self.max_zoom
        
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        
        try:
            self.generate_tiles_parallel(max_workers)
        finally:
            # Restore original settings
            self.min_zoom = original_min
            self.max_zoom = original_max
    
    def validate_output(self):
        """Validate the generated tiles."""
        logger.info("Validating generated tiles...")
        
        validation_results = {
            "zoom_levels": {},
            "total_tiles": 0,
            "total_size_mb": 0,
            "zones_rendered": set(),
            "non_empty_tiles": 0
        }
        
        for zoom in range(self.min_zoom, self.max_zoom + 1):
            zoom_dir = self.output_dir / str(zoom)
            if zoom_dir.exists():
                tile_count = 0
                total_size = 0
                non_empty = 0
                
                for tile_path in zoom_dir.glob("*/*.png"):
                    tile_count += 1
                    file_size = tile_path.stat().st_size
                    total_size += file_size
                    
                    # Check if tile has content
                    if file_size > 1000:  # More than 1KB suggests content
                        non_empty += 1
                    
                    # Sample check for truly empty tiles
                    if tile_count <= 5:  # Check first few tiles
                        img = Image.open(tile_path)
                        img_array = np.array(img)
                        # For RGB mode, check if all pixels are white
                        if np.all(img_array == 255):
                            logger.warning(f"Empty tile found: {tile_path}")
                
                validation_results["zoom_levels"][zoom] = {
                    "tiles": tile_count,
                    "non_empty": non_empty,
                    "size_mb": total_size / (1024 * 1024)
                }
                validation_results["total_tiles"] += tile_count
                validation_results["non_empty_tiles"] += non_empty
                validation_results["total_size_mb"] += total_size / (1024 * 1024)
        
        logger.info("\nValidation Results:")
        logger.info(f"Total tiles generated: {validation_results['total_tiles']}")
        logger.info(f"Non-empty tiles: {validation_results['non_empty_tiles']}")
        logger.info(f"Total size: {validation_results['total_size_mb']:.2f} MB")
        
        for zoom, info in validation_results["zoom_levels"].items():
            logger.info(f"  Zoom {zoom}: {info['tiles']} tiles ({info['non_empty']} non-empty), {info['size_mb']:.2f} MB")
        
        return validation_results
    
    def print_statistics(self):
        """Print generation statistics."""
        logger.info("\n" + "=" * 60)
        logger.info("TILE GENERATION STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total features processed: {self.stats['total_features']}")
        logger.info(f"Zones found: {len(self.stats['zones_found'])}")
        logger.info(f"Total tiles generated: {self.stats['tiles_generated']}")
        logger.info(f"Empty tiles skipped: {self.stats['empty_tiles_skipped']}")
        
        if self.stats["features_per_zoom"]:
            logger.info("\nFeatures rendered per zoom level:")
            for zoom in sorted(self.stats["features_per_zoom"].keys()):
                logger.info(f"  Zoom {zoom}: {self.stats['features_per_zoom'][zoom]} features")
        
        logger.info(f"\nZones processed ({len(self.stats['zones_found'])} total):")
        for zone in sorted(self.stats['zones_found']):
            logger.info(f"  - {zone}")
        logger.info("=" * 60)


def main():
    """Main execution function."""
    # Configuration - Updated to match your actual data location
    DATA_DIR = "data/andhra_pradesh/amaravati/master_plan"  # Fixed path for your data structure
    OUTPUT_DIR = "amaravati_tiles"  # Separate output directory
    MAX_WORKERS = 4  # Number of parallel workers
    
    # Create tile generator
    generator = AmaravatiTileGenerator(
        data_dir=DATA_DIR,
        output_dir=OUTPUT_DIR
    )
    
    try:
        # Generate tiles (use parallel processing for better performance)
        generator.generate_tiles_parallel(max_workers=MAX_WORKERS)
        
        # Validate output
        generator.validate_output()
        
        logger.info("\nTile generation completed successfully!")
        logger.info(f"Tiles saved to: {OUTPUT_DIR}")
        logger.info("\nTo view the tiles:")
        logger.info("1. Run: python tile_viewer_utility.py --view")
        logger.info("2. Open: http://localhost:8000/tile_viewer.html")
        
    except Exception as e:
        logger.error(f"Error during tile generation: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()