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
        
        # Zoom level configuration
        self.min_zoom = 18
        self.max_zoom = 18
        
        # Tile size
        self.tile_size = 256
        
        # Buffer for preventing edge clipping (in pixels)
        self.tile_buffer = 16
        
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
            "R1-Village planning zone": {"fill_color": "#FFFFFF"},
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
            "SU2 - Road Network": {"fill_color": "#FFFFFF"},
            "U1-Reserve zone": {"fill_color": "#CCCCCC"},
            "U2- Road Reserve Zone": {"fill_color": "#000000"},
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
        
        # Add small buffer to ensure complete coverage
        buffer = 0.001
        min_x -= buffer
        min_y -= buffer
        max_x += buffer
        max_y += buffer
        
        # Get tiles for bounds
        tiles = list(mercantile.tiles(min_x, min_y, max_x, max_y, [zoom]))
        
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
        """Render a single tile with all features using the reference approach."""
        # Get tile bounds in WGS84
        tile_bounds = mercantile.bounds(tile)
        
        # Create image with transparency
        img = Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img, 'RGBA')
        
        # Convert to pixel coordinates function (from reference)
        def coord_to_pixel(lon, lat):
            # Simple linear interpolation within tile bounds
            tile_x = (lon - tile_bounds.west) / (tile_bounds.east - tile_bounds.west) * self.tile_size
            tile_y = (tile_bounds.north - lat) / (tile_bounds.north - tile_bounds.south) * self.tile_size
            return tile_x, tile_y
        
        # Create tile geometry for intersection with larger buffer to ensure complete coverage
        # Use a larger buffer to capture all features that should appear in this tile
        buffer_factor = 0.2  # 20% buffer for better coverage
        lon_range = tile_bounds.east - tile_bounds.west
        lat_range = tile_bounds.north - tile_bounds.south
        
        buffered_tile_geom = box(
            tile_bounds.west - (lon_range * buffer_factor),
            tile_bounds.south - (lat_range * buffer_factor),
            tile_bounds.east + (lon_range * buffer_factor),
            tile_bounds.north + (lat_range * buffer_factor)
        )
        
        # Filter geometries that intersect with buffered tile
        intersecting = gdf[gdf.geometry.intersects(buffered_tile_geom)]
        
        # Additional check: also include features that are completely contained within the tile
        # This ensures we don't miss any features due to precision issues
        contained_features = gdf[gdf.geometry.within(buffered_tile_geom)]
        
        # Combine both sets to ensure complete coverage
        all_features = gpd.GeoDataFrame(pd.concat([intersecting, contained_features], ignore_index=True))
        all_features = all_features.drop_duplicates()  # Remove any duplicates
        
        rendered_count = 0
        
        # Render each feature
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
            
            # Convert geometry to pixel coordinates and draw
            if geom.geom_type == 'Polygon':
                coords = []
                for coord in geom.exterior.coords:
                    if len(coord) >= 2:
                        lon, lat = coord[0], coord[1]
                        px, py = coord_to_pixel(lon, lat)
                        coords.append((px, py))
                
                if len(coords) > 2:
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
                        # Fill only - no borders between features
                        draw.polygon(coords, fill=fill_color)
                        rendered_count += 1
            
            elif geom.geom_type == 'Point':
                # Handle point features
                lon, lat = geom.x, geom.y
                px, py = coord_to_pixel(lon, lat)
                # Draw a small circle for points
                radius = max(2, min(8, 256 // (2 ** (18 - tile.z))))  # Scale radius with zoom
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
        
        # Get all tiles that intersect with data
        tiles = self.get_tiles_for_bounds(gdf, zoom)
        logger.info(f"Processing {len(tiles)} tiles at zoom {zoom}")
        
        tiles_generated = 0
        empty_skipped = 0
        
        for i, tile in enumerate(tiles):
            if i % 100 == 0 and i > 0:
                logger.info(f"  Processed {i}/{len(tiles)} tiles at zoom {zoom}")
            
            # Render tile
            img = self.render_tile(tile, gdf)
            
            if img is not None:
                # Check if image has content (not fully transparent)
                img_array = np.array(img)
                if img_array[:, :, 3].max() > 0:  # Check alpha channel
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
                        if img_array[:, :, 3].max() == 0:
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
    # Configuration - Update this path to match your actual data location
    DATA_DIR = "data/andhra_pradesh/amaravati/master_plan"  # Fixed path
    OUTPUT_DIR = "tiles"
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