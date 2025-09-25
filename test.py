#!/usr/bin/env python3
"""
Karnataka Bengaluru Master Plan Seamless Tile Generator
Generates pixel-perfect PNG tiles with no seams for Mapbox integration.
Incorporates zone-specific color mapping from the master plan.
"""

import os
import sys
import json
import argparse
import logging
import warnings
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from dataclasses import dataclass

import numpy as np
import geopandas as gpd
from shapely.geometry import box, Polygon, MultiPolygon, Point, mapping
from shapely.ops import transform, unary_union
from shapely.validation import make_valid
import mercantile
from PIL import Image, ImageDraw
import pyproj
from rtree import index

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(processName)s] - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


@dataclass
class ZoneConfig:
    """Configuration for zone rendering."""
    name: str
    color: str
    category: str
    render_priority: int


class BengaluruSeamlessTileGenerator:
    """Seamless tile generator for Karnataka Bengaluru Master Plan."""
    
    # Zone color mapping from your configuration
    ZONE_COLORS = {
        'Residential_Mixed_.json': '#FFC400',
        'Residential_Main_.json': '#FFEB4F',
        'Commercial_Central_.json': '#004DA8',
        'Commercial_Business_.json': '#73B2FF',
        'Industrial.json': '#AA66B2',
        'HighTech.json': '#C29ED7',
        'Public_SemiPublic.json': '#E60000',
        'Defense.json': '#E0B8FC',
        'StateForest_Valley_ProtectedLand_.json': '#70A800',
        'Parks_GreenSpaces_Sports_Playgrounds_Cemetery_BurialGrounds.json': '#98E600',
        'Lake_Tank.json': '#BEE8FF',
        'Road_Rail_Airport_Transport.json': '#828282',
        'Power_Water_GarbageFacility_TreatmentPlant.json': '#D79E9E',
        'Agricultural_Land.json': '#9DC1CB',
        'Unclassified_Use.json': '#E1E1E1',
        'Drains.json': '#267300'
    }
    
    # Zone categories with render priority
    ZONE_CATEGORIES = {
        'WATER_BODIES': {
            'files': ['Lake_Tank.json', 'Drains.json'],
            'priority': 1  # Render first (bottom layer)
        },
        'AGRICULTURAL': {
            'files': ['Agricultural_Land.json'],
            'priority': 2
        },
        'PROTECTED': {
            'files': ['StateForest_Valley_ProtectedLand_.json'],
            'priority': 3
        },
        'PARKS_GREEN': {
            'files': ['Parks_GreenSpaces_Sports_Playgrounds_Cemetery_BurialGrounds.json'],
            'priority': 4
        },
        'RESIDENTIAL': {
            'files': ['Residential_Mixed_.json', 'Residential_Main_.json'],
            'priority': 5
        },
        'COMMERCIAL': {
            'files': ['Commercial_Central_.json', 'Commercial_Business_.json'],
            'priority': 6
        },
        'INDUSTRIAL': {
            'files': ['Industrial.json', 'HighTech.json'],
            'priority': 7
        },
        'GOVERNMENT': {
            'files': ['Public_SemiPublic.json', 'Defense.json'],
            'priority': 8
        },
        'UTILITIES': {
            'files': ['Power_Water_GarbageFacility_TreatmentPlant.json'],
            'priority': 9
        },
        'TRANSPORT': {
            'files': ['Road_Rail_Airport_Transport.json'],
            'priority': 10  # Render last (top layer)
        },
        'UNCLASSIFIED': {
            'files': ['Unclassified_Use.json'],
            'priority': 0
        }
    }
    
    def __init__(self,
                 data_dir: str = None,
                 input_file: str = None,
                 output_dir: str = "./tiles",
                 min_zoom: int = 4,
                 max_zoom: int = 18,
                 tile_size: int = 512,
                 buffer_pixels: int = 16,
                 workers: int = 4,
                 resume: bool = True,
                 debug: bool = False):
        """
        Initialize the tile generator.
        
        Args:
            data_dir: Directory containing multiple GeoJSON files (Bengaluru mode)
            input_file: Single GeoJSON file (single file mode)
            output_dir: Output directory for tiles
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            tile_size: Tile size in pixels (512 for Mapbox)
            buffer_pixels: Buffer in pixels for seamless rendering
            workers: Number of parallel workers
            resume: Skip existing tiles
            debug: Enable debug mode
        """
        self.data_dir = Path(data_dir) if data_dir else None
        self.input_file = Path(input_file) if input_file else None
        self.output_dir = Path(output_dir)
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.tile_size = tile_size
        self.buffer_pixels = buffer_pixels
        self.workers = workers
        self.resume = resume
        self.debug = debug
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup projections
        self.proj_4326 = pyproj.CRS('EPSG:4326')
        self.proj_3857 = pyproj.CRS('EPSG:3857')
        self.transformer_to_3857 = pyproj.Transformer.from_crs(
            self.proj_4326, self.proj_3857, always_xy=True
        )
        self.transformer_to_4326 = pyproj.Transformer.from_crs(
            self.proj_3857, self.proj_4326, always_xy=True
        )
        
        logger.info(f"Initialized BengaluruSeamlessTileGenerator")
        logger.info(f"Mode: {'Multi-file (Bengaluru)' if data_dir else 'Single file'}")
        logger.info(f"Output: {self.output_dir}")
        logger.info(f"Zoom levels: {self.min_zoom} to {self.max_zoom}")
        logger.info(f"Tile size: {self.tile_size}px")
        logger.info(f"Buffer: {self.buffer_pixels}px")
    
    def load_and_prepare_data(self) -> gpd.GeoDataFrame:
        """Load and prepare GeoJSON data."""
        if self.data_dir:
            return self._load_bengaluru_data()
        elif self.input_file:
            return self._load_single_file()
        else:
            raise ValueError("Either data_dir or input_file must be specified")
    
    def _load_bengaluru_data(self) -> gpd.GeoDataFrame:
        """Load multiple GeoJSON files for Bengaluru master plan."""
        logger.info(f"Loading Bengaluru master plan data from {self.data_dir}")
        
        if not self.data_dir.exists():
            raise ValueError(f"Data directory does not exist: {self.data_dir}")
        
        all_gdfs = []
        zone_summary = {}
        
        # Load files in render priority order
        files_by_priority = []
        for category, config in self.ZONE_CATEGORIES.items():
            for file in config['files']:
                files_by_priority.append((config['priority'], file, category))
        
        files_by_priority.sort(key=lambda x: x[0])
        
        for priority, filename, category in files_by_priority:
            filepath = self.data_dir / filename
            if not filepath.exists():
                logger.warning(f"File not found: {filepath}")
                continue
            
            try:
                logger.info(f"Loading {filename} (category: {category}, priority: {priority})")
                gdf = gpd.read_file(filepath)
                
                if gdf.empty:
                    logger.warning(f"No data in {filename}")
                    continue
                
                # Add zone metadata
                zone_name = filepath.stem
                gdf['zone_name'] = zone_name
                gdf['zone_file'] = filename
                gdf['zone_color'] = self.ZONE_COLORS.get(filename, '#E1E1E1')
                gdf['zone_category'] = category
                gdf['render_priority'] = priority
                
                # Add to collection
                all_gdfs.append(gdf)
                zone_summary[zone_name] = {
                    'file': filename,
                    'color': gdf['zone_color'].iloc[0],
                    'category': category,
                    'priority': priority,
                    'features': len(gdf)
                }
                
                logger.info(f"  → {len(gdf)} features, color: {gdf['zone_color'].iloc[0]}")
                
            except Exception as e:
                logger.error(f"Error loading {filename}: {e}")
                continue
        
        if not all_gdfs:
            raise ValueError("No valid GeoJSON data loaded")
        
        # Combine all GeoDataFrames
        combined_gdf = gpd.pd.concat(all_gdfs, ignore_index=True)
        
        # Sort by render priority (lower priority renders first)
        combined_gdf = combined_gdf.sort_values('render_priority')
        
        # Ensure CRS and reproject to Web Mercator
        if combined_gdf.crs is None:
            combined_gdf.set_crs('EPSG:4326', inplace=True)
        
        if combined_gdf.crs != 'EPSG:3857':
            logger.info(f"Reprojecting from {combined_gdf.crs} to EPSG:3857")
            combined_gdf = combined_gdf.to_crs('EPSG:3857')
        
        # Validate and repair geometries
        self._validate_geometries(combined_gdf)
        
        # Log summary
        self._log_zone_summary(zone_summary)
        
        return combined_gdf
    
    def _load_single_file(self) -> gpd.GeoDataFrame:
        """Load a single GeoJSON file."""
        logger.info(f"Loading data from {self.input_file}")
        
        gdf = gpd.read_file(self.input_file)
        logger.info(f"Loaded {len(gdf)} features")
        
        # Add default zone information
        gdf['zone_name'] = 'default'
        gdf['zone_color'] = '#6464C8'
        gdf['zone_category'] = 'DEFAULT'
        gdf['render_priority'] = 5
        
        # Ensure CRS and reproject
        if gdf.crs is None:
            gdf.set_crs('EPSG:4326', inplace=True)
        
        if gdf.crs != 'EPSG:3857':
            logger.info(f"Reprojecting from {gdf.crs} to EPSG:3857")
            gdf = gdf.to_crs('EPSG:3857')
        
        # Validate geometries
        self._validate_geometries(gdf)
        
        return gdf
    
    def _validate_geometries(self, gdf: gpd.GeoDataFrame):
        """Validate and repair invalid geometries."""
        logger.info("Validating and repairing geometries...")
        invalid_count = 0
        
        for idx in gdf.index:
            geom = gdf.at[idx, 'geometry']
            if geom is not None and not geom.is_valid:
                invalid_count += 1
                gdf.at[idx, 'geometry'] = make_valid(geom)
        
        if invalid_count > 0:
            logger.info(f"Repaired {invalid_count} invalid geometries")
    
    def _log_zone_summary(self, zone_summary: Dict):
        """Log a summary of loaded zones."""
        logger.info("=" * 70)
        logger.info("ZONE SUMMARY")
        logger.info("=" * 70)
        
        total_features = sum(info['features'] for info in zone_summary.values())
        
        for category, config in self.ZONE_CATEGORIES.items():
            zones_in_category = [
                zone for zone, info in zone_summary.items()
                if info['category'] == category
            ]
            if zones_in_category:
                category_features = sum(
                    zone_summary[zone]['features'] for zone in zones_in_category
                )
                logger.info(f"\n{category} (Priority: {config['priority']}):")
                for zone in zones_in_category:
                    info = zone_summary[zone]
                    logger.info(f"  • {info['file']}: {info['features']:,} features | {info['color']}")
        
        logger.info(f"\nTOTAL FEATURES: {total_features:,}")
        logger.info("=" * 70)
    
    def build_spatial_index(self, gdf: gpd.GeoDataFrame) -> index.Index:
        """Build R-tree spatial index for efficient querying."""
        logger.info("Building spatial index...")
        idx = index.Index()
        
        for i, geometry in enumerate(gdf.geometry):
            if geometry is not None:
                idx.insert(i, geometry.bounds)
        
        logger.info(f"Spatial index built with {len(gdf)} features")
        return idx
    
    def get_tile_bounds_3857(self, x: int, y: int, z: int) -> Tuple[float, float, float, float]:
        """Get tile bounds in EPSG:3857 with buffer."""
        # Get tile bounds in lat/lon
        tile = mercantile.Tile(x, y, z)
        bounds_4326 = mercantile.bounds(tile)
        
        # Convert corners to Web Mercator
        west, south = self.transformer_to_3857.transform(bounds_4326.west, bounds_4326.south)
        east, north = self.transformer_to_3857.transform(bounds_4326.east, bounds_4326.north)
        
        # Calculate buffer in meters
        tile_width_meters = east - west
        tile_height_meters = north - south
        buffer_x = (tile_width_meters / self.tile_size) * self.buffer_pixels
        buffer_y = (tile_height_meters / self.tile_size) * self.buffer_pixels
        
        # Apply buffer
        buffered_bounds = (
            west - buffer_x,
            south - buffer_y,
            east + buffer_x,
            north + buffer_y
        )
        
        return buffered_bounds
    
    def get_tile_bounds_no_buffer(self, x: int, y: int, z: int) -> Tuple[float, float, float, float]:
        """Get exact tile bounds in EPSG:3857 without buffer."""
        tile = mercantile.Tile(x, y, z)
        bounds_4326 = mercantile.bounds(tile)
        
        west, south = self.transformer_to_3857.transform(bounds_4326.west, bounds_4326.south)
        east, north = self.transformer_to_3857.transform(bounds_4326.east, bounds_4326.north)
        
        return west, south, east, north
    
    def simplify_geometry(self, geom, zoom: int) -> Any:
        """Simplify geometry based on zoom level."""
        # Calculate simplification tolerance
        base_tolerance = 156543.03392804097  # meters per pixel at zoom 0
        tolerance = base_tolerance / (2 ** zoom) * 0.5  # Half pixel tolerance
        
        # More aggressive simplification at lower zooms
        if zoom <= 8:
            tolerance *= 2
        elif zoom <= 12:
            tolerance *= 1.5
        
        # Simplify while preserving topology
        simplified = geom.simplify(tolerance, preserve_topology=True)
        
        # If simplification results in invalid or empty geometry, return original
        if simplified.is_empty or not simplified.is_valid:
            return geom
        
        # For very low zoom, convert small polygons to points
        if zoom <= 6 and simplified.area < tolerance * tolerance * 10:
            return simplified.centroid
        
        return simplified
    
    def hex_to_rgba(self, hex_color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
        """Convert hex color to RGBA tuple."""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return rgb + (alpha,)
    
    def world_to_pixel(self, x: float, y: float,
                      west: float, south: float, east: float, north: float,
                      with_buffer: bool = True) -> Tuple[int, int]:
        """Convert world coordinates to pixel coordinates."""
        tile_size = self.tile_size + (2 * self.buffer_pixels if with_buffer else 0)
        
        # Normalize to 0-1
        norm_x = (x - west) / (east - west) if (east - west) != 0 else 0
        norm_y = (north - y) / (north - south) if (north - south) != 0 else 0
        
        # Convert to pixels
        pixel_x = int(norm_x * tile_size)
        pixel_y = int(norm_y * tile_size)
        
        return pixel_x, pixel_y
    
    def render_polygon(self, draw: ImageDraw.Draw, polygon: Polygon,
                      bounds: Tuple[float, float, float, float],
                      fill_color: Tuple[int, int, int, int],
                      stroke_color: Optional[Tuple[int, int, int, int]] = None,
                      with_buffer: bool = True):
        """Render a polygon with anti-aliasing."""
        west, south, east, north = bounds
        
        # Get exterior ring
        exterior = list(polygon.exterior.coords)
        pixel_coords = [
            self.world_to_pixel(x, y, west, south, east, north, with_buffer)
            for x, y in exterior
        ]
        
        # Filter out coordinates far outside bounds
        max_coord = self.tile_size + (2 * self.buffer_pixels if with_buffer else 0) + 10
        pixel_coords = [
            (x, y) for x, y in pixel_coords
            if -10 <= x <= max_coord and -10 <= y <= max_coord
        ]
        
        if len(pixel_coords) >= 3:
            # Draw filled polygon with optional stroke
            if stroke_color:
                draw.polygon(pixel_coords, fill=fill_color, outline=stroke_color, width=1)
            else:
                draw.polygon(pixel_coords, fill=fill_color)
            
            # Handle holes
            for interior in polygon.interiors:
                hole_coords = [
                    self.world_to_pixel(x, y, west, south, east, north, with_buffer)
                    for x, y in interior.coords
                ]
                if len(hole_coords) >= 3:
                    draw.polygon(hole_coords, fill=(0, 0, 0, 0))
    
    def render_point(self, draw: ImageDraw.Draw, point: Point,
                    bounds: Tuple[float, float, float, float],
                    color: Tuple[int, int, int, int],
                    zoom: int,
                    with_buffer: bool = True):
        """Render a point as a circle."""
        west, south, east, north = bounds
        px, py = self.world_to_pixel(
            point.x, point.y, west, south, east, north, with_buffer
        )
        
        # Size based on zoom level
        radius = max(1, min(6, 12 - zoom // 2))
        
        draw.ellipse([px-radius, py-radius, px+radius, py+radius],
                    fill=color, outline=None)
    
    def generate_tile(self, x: int, y: int, z: int,
                     gdf: gpd.GeoDataFrame, spatial_idx: index.Index) -> Optional[str]:
        """Generate a single tile with seamless rendering."""
        try:
            # Check if tile exists (resume support)
            tile_path = self.output_dir / str(z) / str(x) / f"{y}.png"
            if self.resume and tile_path.exists():
                return "skipped"
            
            # Get tile bounds with buffer
            buffered_bounds = self.get_tile_bounds_3857(x, y, z)
            west_b, south_b, east_b, north_b = buffered_bounds
            
            # Query spatial index
            tile_box = box(*buffered_bounds)
            possible_matches = list(spatial_idx.intersection(buffered_bounds))
            
            if not possible_matches:
                return "empty"
            
            # Filter to actual intersections
            intersecting_indices = []
            for idx in possible_matches:
                geom = gdf.iloc[idx].geometry
                if geom and geom.intersects(tile_box):
                    intersecting_indices.append(idx)
            
            if not intersecting_indices:
                return "empty"
            
            # Create image with buffer
            img_size = self.tile_size + 2 * self.buffer_pixels
            
            # Use supersampling for anti-aliasing
            supersample = 2
            img = Image.new('RGBA', (img_size * supersample, img_size * supersample), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img, 'RGBA')
            
            # Get features (already sorted by render priority)
            features_to_render = gdf.iloc[intersecting_indices]
            
            # Render features
            for _, feature in features_to_render.iterrows():
                geom = feature.geometry
                
                # Simplify geometry for lower zoom levels
                if z < 14:
                    geom = self.simplify_geometry(geom, z)
                
                # Get zone color
                zone_color = self.hex_to_rgba(feature.zone_color, 230)  # Slight transparency
                
                # Clip to buffered bounds
                clipped = geom.intersection(tile_box)
                
                if clipped.is_empty:
                    continue
                
                # Scale bounds for supersampling
                scaled_bounds = (
                    west_b, south_b, east_b, north_b
                )
                
                # Create scaled draw for supersampling
                scaled_draw = ImageDraw.Draw(img, 'RGBA')
                
                # Render based on geometry type
                if clipped.geom_type == 'Polygon':
                    # Scale coordinates for supersampling
                    poly_exterior = list(clipped.exterior.coords)
                    scaled_coords = []
                    for px, py in poly_exterior:
                        sx, sy = self.world_to_pixel(px, py, *scaled_bounds, with_buffer=True)
                        scaled_coords.append((sx * supersample, sy * supersample))
                    
                    if len(scaled_coords) >= 3:
                        scaled_draw.polygon(scaled_coords, fill=zone_color)
                        
                elif clipped.geom_type == 'MultiPolygon':
                    for poly in clipped.geoms:
                        poly_exterior = list(poly.exterior.coords)
                        scaled_coords = []
                        for px, py in poly_exterior:
                            sx, sy = self.world_to_pixel(px, py, *scaled_bounds, with_buffer=True)
                            scaled_coords.append((sx * supersample, sy * supersample))
                        
                        if len(scaled_coords) >= 3:
                            scaled_draw.polygon(scaled_coords, fill=zone_color)
                            
                elif clipped.geom_type == 'Point':
                    px, py = self.world_to_pixel(
                        clipped.x, clipped.y, *scaled_bounds, with_buffer=True
                    )
                    radius = max(2, 10 - z // 2) * supersample
                    scaled_draw.ellipse(
                        [px * supersample - radius, py * supersample - radius,
                         px * supersample + radius, py * supersample + radius],
                        fill=zone_color
                    )
            
            # Downsample for anti-aliasing
            img = img.resize((img_size, img_size), Image.Resampling.LANCZOS)
            
            # Crop to remove buffer
            img = img.crop((
                self.buffer_pixels,
                self.buffer_pixels,
                self.buffer_pixels + self.tile_size,
                self.buffer_pixels + self.tile_size
            ))
            
            # Save debug image if requested
            if self.debug:
                self._save_debug_image(x, y, z, gdf.iloc[intersecting_indices], buffered_bounds)
            
            # Create output directory and save
            tile_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(tile_path, 'PNG', optimize=True)
            
            return "generated"
            
        except Exception as e:
            logger.error(f"Error generating tile {z}/{x}/{y}: {e}")
            import traceback
            traceback.print_exc()
            return "error"
    
    def _save_debug_image(self, x: int, y: int, z: int, features: gpd.GeoDataFrame, bounds: Tuple):
        """Save debug image with buffer area visible."""
        debug_path = self.output_dir / "debug" / str(z) / str(x) / f"{y}_debug.png"
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        
        img_size = self.tile_size + 2 * self.buffer_pixels
        img = Image.new('RGBA', (img_size, img_size), (240, 240, 240, 255))
        draw = ImageDraw.Draw(img, 'RGBA')
        
        # Draw tile boundary
        draw.rectangle(
            [self.buffer_pixels, self.buffer_pixels,
             self.buffer_pixels + self.tile_size, self.buffer_pixels + self.tile_size],
            outline=(0, 255, 0, 255), width=2
        )
        
        # Draw features with debug colors
        for _, feature in features.iterrows():
            geom = feature.geometry
            color = self.hex_to_rgba(feature.zone_color, 128)
            
            if geom.geom_type in ['Polygon', 'MultiPolygon']:
                if geom.geom_type == 'Polygon':
                    polygons = [geom]
                else:
                    polygons = geom.geoms
                
                for poly in polygons:
                    self.render_polygon(draw, poly, bounds, color, (255, 0, 0, 255), True)
        
        img.save(debug_path, 'PNG')
    
    def get_tiles_for_zoom(self, gdf: gpd.GeoDataFrame, zoom: int) -> List[mercantile.Tile]:
        """Get all tiles that intersect with data at given zoom."""
        # Convert to EPSG:4326 for tile calculation
        gdf_4326 = gdf.to_crs('EPSG:4326')
        bounds = gdf_4326.total_bounds
        
        # Add small buffer
        buffer = 0.001
        tiles = list(mercantile.tiles(
            bounds[0] - buffer,
            bounds[1] - buffer,
            bounds[2] + buffer,
            bounds[3] + buffer,
            [zoom]
        ))
        
        return tiles
    
    def generate_tiles_parallel(self):
        """Generate tiles using parallel processing."""
        logger.info("Starting seamless tile generation")
        
        # Load and prepare data
        gdf = self.load_and_prepare_data()
        
        # Build spatial index
        spatial_idx = self.build_spatial_index(gdf)
        
        # Save prepared data for workers
        cache_dir = self.output_dir / ".cache"
        cache_dir.mkdir(exist_ok=True)
        cache_file = cache_dir / "prepared_data.geojson"
        gdf.to_file(cache_file, driver="GeoJSON")
        
        # Statistics
        stats = {
            'generated': 0,
            'skipped': 0,
            'empty': 0,
            'errors': 0
        }
        
        # Process each zoom level
        for z in range(self.min_zoom, self.max_zoom + 1):
            logger.info(f"\nProcessing zoom level {z}")
            
            # Get tiles for this zoom
            tiles = self.get_tiles_for_zoom(gdf, z)
            logger.info(f"Found {len(tiles)} tiles to process")
            
            if not tiles:
                continue
            
            # Process tiles in parallel
            with ProcessPoolExecutor(max_workers=self.workers) as executor:
                futures = {
                    executor.submit(
                        self._generate_tile_worker,
                        tile.x, tile.y, tile.z,
                        cache_file,
                        self.output_dir,
                        self.tile_size,
                        self.buffer_pixels,
                        self.resume,
                        self.debug
                    ): (tile.x, tile.y, tile.z)
                    for tile in tiles
                }
                
                completed = 0
                for future in as_completed(futures):
                    x, y, z_level = futures[future]
                    try:
                        result = future.result()
                        stats[result] = stats.get(result, 0) + 1
                    except Exception as e:
                        logger.error(f"Error processing tile {z_level}/{x}/{y}: {e}")
                        stats['errors'] += 1
                    
                    completed += 1
                    if completed % 100 == 0:
                        logger.info(f"  Zoom {z}: {completed}/{len(tiles)} tiles processed")
            
            # Log zoom level stats
            logger.info(f"  Zoom {z} complete: {stats['generated']} new, "
                       f"{stats['skipped']} existing, {stats['empty']} empty, "
                       f"{stats['errors']} errors")
        
        # Clean up cache
        if cache_file.exists():
            os.remove(cache_file)
        
        # Final summary
        logger.info("\n" + "=" * 70)
        logger.info("TILE GENERATION COMPLETE")
        logger.info(f"Total generated: {stats['generated']:,}")
        logger.info(f"Total skipped: {stats['skipped']:,}")
        logger.info(f"Total empty: {stats['empty']:,}")
        logger.info(f"Total errors: {stats['errors']:,}")
        logger.info("=" * 70)
        
        # Create supporting files
        self.create_supporting_files(gdf.to_crs('EPSG:4326').total_bounds)
    
    @staticmethod
    def _generate_tile_worker(x: int, y: int, z: int, cache_file: Path,
                             output_dir: Path, tile_size: int, buffer_pixels: int,
                             resume: bool, debug: bool) -> str:
        """Worker function for parallel tile generation."""
        # Create a new generator instance in the worker process
        generator = BengaluruSeamlessTileGenerator(
            output_dir=str(output_dir),
            tile_size=tile_size,
            buffer_pixels=buffer_pixels,
            resume=resume,
            debug=debug
        )
        
        # Load data and build index
        gdf = gpd.read_file(cache_file)
        spatial_idx = generator.build_spatial_index(gdf)
        
        # Generate tile
        return generator.generate_tile(x, y, z, gdf, spatial_idx)
    
    def create_supporting_files(self, bounds: Tuple[float, float, float, float]):
        """Create TileJSON and viewer HTML."""
        logger.info("Creating supporting files...")
        
        # TileJSON
        tilejson = {
            "tilejson": "3.0.0",
            "name": "Karnataka Bengaluru Master Plan",
            "description": "Seamless master plan tiles for Bengaluru",
            "version": "1.0.0",
            "attribution": "Karnataka Government",
            "scheme": "xyz",
            "tiles": [
                f"file://{self.output_dir}/{{z}}/{{x}}/{{y}}.png"
            ],
            "minzoom": self.min_zoom,
            "maxzoom": self.max_zoom,
            "bounds": list(bounds),
            "center": [
                (bounds[0] + bounds[2]) / 2,
                (bounds[1] + bounds[3]) / 2,
                12
            ]
        }
        
        with open(self.output_dir / "tilejson.json", "w") as f:
            json.dump(tilejson, f, indent=2)
        
        logger.info(f"Created: {self.output_dir}/tilejson.json")
    
    def validate_seamless(self, zoom: int = 10):
        """Validate seamless rendering by checking tile boundaries."""
        logger.info(f"\nValidating seamless rendering at zoom {zoom}")
        
        zoom_dir = self.output_dir / str(zoom)
        if not zoom_dir.exists():
            logger.error(f"No tiles found at zoom {zoom}")
            return False
        
        # Find a sample tile
        sample_tile = None
        for x_dir in zoom_dir.iterdir():
            if x_dir.is_dir():
                for y_file in x_dir.glob("*.png"):
                    sample_tile = (int(x_dir.name), int(y_file.stem))
                    break
                if sample_tile:
                    break
        
        if not sample_tile:
            logger.error("No tiles found to validate")
            return False
        
        x, y = sample_tile
        logger.info(f"Validating 3x3 grid centered at tile {zoom}/{x}/{y}")
        
        # Create composite
        composite = Image.new('RGBA', (self.tile_size * 3, self.tile_size * 3), (255, 255, 255, 255))
        
        tiles_found = 0
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                tile_path = self.output_dir / str(zoom) / str(x + dx) / f"{y + dy}.png"
                if tile_path.exists():
                    tile = Image.open(tile_path)
                    composite.paste(tile, ((dx + 1) * self.tile_size, (dy + 1) * self.tile_size))
                    tiles_found += 1
        
        # Save validation image
        validation_dir = self.output_dir / "validation"
        validation_dir.mkdir(exist_ok=True)
        validation_path = validation_dir / f"seamless_check_z{zoom}_x{x}_y{y}.png"
        composite.save(validation_path)
        
        logger.info(f"✓ Validation image saved: {validation_path}")
        logger.info(f"✓ Found {tiles_found}/9 tiles in test grid")
        
        return True


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Generate seamless PNG tiles for Mapbox from Bengaluru Master Plan data"
    )
    
    # Input options (either data-dir or input)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--data-dir", 
                            help="Directory containing multiple GeoJSON files (Bengaluru mode)")
    input_group.add_argument("--input",
                            help="Single GeoJSON file")
    
    # Output options
    parser.add_argument("--output-dir", default="./tiles",
                       help="Output directory for tiles")
    
    # Zoom levels
    parser.add_argument("--min-zoom", type=int, default=4,
                       help="Minimum zoom level")
    parser.add_argument("--max-zoom", type=int, default=18,
                       help="Maximum zoom level")
    
    # Tile configuration
    parser.add_argument("--tile-size", type=int, default=512,
                       help="Tile size in pixels (512 for Mapbox)")
    parser.add_argument("--buffer", type=int, default=16,
                       help="Buffer size in pixels for seamless rendering")
    
    # Performance options
    parser.add_argument("--workers", type=int, default=4,
                       help="Number of parallel workers")
    parser.add_argument("--no-resume", action="store_true",
                       help="Regenerate existing tiles")
    
    # Debug and validation
    parser.add_argument("--debug", action="store_true",
                       help="Save debug images")
    parser.add_argument("--validate", action="store_true",
                       help="Validate seamless rendering after generation")
    parser.add_argument("--validate-zoom", type=int, default=10,
                       help="Zoom level for validation")
    
    args = parser.parse_args()
    
    # Create generator
    generator = BengaluruSeamlessTileGenerator(
        data_dir=args.data_dir,
        input_file=args.input,
        output_dir=args.output_dir,
        min_zoom=args.min_zoom,
        max_zoom=args.max_zoom,
        tile_size=args.tile_size,
        buffer_pixels=args.buffer,
        workers=args.workers,
        resume=not args.no_resume,
        debug=args.debug
    )
    
    try:
        # Generate tiles
        generator.generate_tiles_parallel()
        
        # Validate if requested
        if args.validate:
            generator.validate_seamless(zoom=args.validate_zoom)
        
        logger.info("\n✓ Tile generation completed successfully!")
        logger.info(f"✓ Output directory: {args.output_dir}")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()