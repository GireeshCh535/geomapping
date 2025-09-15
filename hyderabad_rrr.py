#!/usr/bin/env python3
"""
Production-grade Seamless PNG Tile Generator for Mapbox
Specialized for line geometries (roads, railways, boundaries)
Prevents bleeding and ensures pixel-perfect tile boundaries
"""

import os
import sys
import json
import argparse
import logging
import warnings
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Union
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
import hashlib
import time

import numpy as np
import geopandas as gpd
from shapely.geometry import (
    box, LineString, MultiLineString, Point, MultiPoint,
    Polygon, MultiPolygon, GeometryCollection, mapping
)
from shapely.ops import transform, unary_union, linemerge, split
from shapely.validation import make_valid, explain_validity
import mercantile
from PIL import Image, ImageDraw, ImageFilter
import pyproj
from rtree import index
import cairo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(processName)s] - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


class SeamlessLineGenerator:
    """
    Specialized tile generator for line geometries with zero bleeding.
    Uses Cairo for subpixel-accurate rendering.
    """
    
    def __init__(self,
                 input_file: str,
                 output_dir: str = "./tiles",
                 min_zoom: int = 4,
                 max_zoom: int = 18,
                 tile_size: int = 512,
                 buffer_pixels: int = 16,
                 workers: int = 4,
                 resume: bool = True,
                 debug: bool = False,
                 line_color: str = "#14E098",
                 force_lines: bool = True):
        """
        Initialize the seamless tile generator for line features.
        
        Args:
            input_file: Path to input GeoJSON file
            output_dir: Output directory for tiles
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            tile_size: Tile size in pixels (512 for Mapbox)
            buffer_pixels: Buffer in pixels for seamless rendering
            workers: Number of parallel workers
            resume: Skip existing tiles
            debug: Enable debug mode
            line_color: Default line color
            force_lines: Force all geometries to be treated as lines
        """
        self.input_file = Path(input_file)
        self.output_dir = Path(output_dir)
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.tile_size = tile_size
        self.buffer_pixels = buffer_pixels
        self.workers = workers
        self.resume = resume
        self.debug = debug
        self.line_color = line_color
        self.force_lines = force_lines
        
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
        
        # Precision settings
        self.coord_precision = 6  # decimal places
        self.simplification_base = 0.00001
        
        logger.info(f"Initialized SeamlessLineGenerator")
        logger.info(f"Input: {self.input_file}")
        logger.info(f"Output: {self.output_dir}")
        logger.info(f"Zoom levels: {self.min_zoom} to {self.max_zoom}")
        logger.info(f"Tile size: {self.tile_size}px")
        logger.info(f"Buffer: {self.buffer_pixels}px")
    
    def fix_geometry(self, geom):
        """Fix common geometry issues."""
        if geom is None or geom.is_empty:
            return None
        
        # Make valid
        if not geom.is_valid:
            logger.debug(f"Fixing invalid geometry: {explain_validity(geom)}")
            geom = make_valid(geom)
        
        # Handle self-intersections for lines
        if geom.geom_type in ['LineString', 'MultiLineString']:
            if not geom.is_simple:
                # Buffer by 0 to fix self-intersections
                buffered = geom.buffer(0)
                if buffered.geom_type == 'Polygon':
                    # Extract boundary as line
                    geom = buffered.boundary
                elif buffered.geom_type == 'MultiPolygon':
                    # Extract all boundaries
                    lines = [poly.boundary for poly in buffered.geoms]
                    geom = unary_union(lines)
        
        # Merge connected lines
        if geom.geom_type == 'MultiLineString':
            merged = linemerge(geom)
            if merged.geom_type == 'LineString':
                geom = merged
        
        return geom
    
    def simplify_for_zoom(self, geom, zoom: int):
        """Simplify geometry appropriately for zoom level."""
        # Calculate tolerance based on zoom
        # At zoom 0, 1 pixel = ~156km
        # Each zoom level doubles the resolution
        meters_per_pixel = 156543.03392804097 / (2 ** zoom)
        
        # Use half-pixel tolerance for simplification
        tolerance = meters_per_pixel * 0.5
        
        # More aggressive simplification at lower zooms
        if zoom <= 6:
            tolerance *= 3
        elif zoom <= 10:
            tolerance *= 2
        elif zoom <= 14:
            tolerance *= 1.5
        
        # Simplify
        simplified = geom.simplify(tolerance, preserve_topology=True)
        
        # Don't lose the geometry entirely
        if simplified.is_empty and not geom.is_empty:
            # Fall back to centroid for very small features
            if geom.geom_type in ['Polygon', 'MultiPolygon']:
                return geom.centroid
            return geom
        
        return simplified
    
    def round_coordinates(self, geom):
        """Round coordinates to reasonable precision."""
        def round_coord(x, y):
            return (
                round(float(x), self.coord_precision),
                round(float(y), self.coord_precision)
            )
        
        if geom.geom_type == 'LineString':
            coords = [round_coord(x, y) for x, y in geom.coords]
            # Remove consecutive duplicates
            cleaned = [coords[0]]
            for coord in coords[1:]:
                if coord != cleaned[-1]:
                    cleaned.append(coord)
            if len(cleaned) >= 2:
                return LineString(cleaned)
                
        elif geom.geom_type == 'MultiLineString':
            lines = []
            for line in geom.geoms:
                coords = [round_coord(x, y) for x, y in line.coords]
                # Remove consecutive duplicates
                cleaned = [coords[0]]
                for coord in coords[1:]:
                    if coord != cleaned[-1]:
                        cleaned.append(coord)
                if len(cleaned) >= 2:
                    lines.append(LineString(cleaned))
            if lines:
                return MultiLineString(lines)
        
        return geom
    
    def load_and_prepare_data(self) -> gpd.GeoDataFrame:
        """Load and prepare GeoJSON data."""
        logger.info(f"Loading data from {self.input_file}")
        
        # Load GeoJSON
        gdf = gpd.read_file(self.input_file)
        logger.info(f"Loaded {len(gdf)} features")
        
        # Ensure CRS
        if gdf.crs is None:
            gdf.set_crs('EPSG:4326', inplace=True)
            logger.info("Set CRS to EPSG:4326")
        
        # Fix geometries
        logger.info("Fixing and validating geometries...")
        fixed_geoms = []
        for idx, row in gdf.iterrows():
            geom = row.geometry
            
            # Fix geometry issues
            fixed = self.fix_geometry(geom)
            
            # Round coordinates
            if fixed:
                fixed = self.round_coordinates(fixed)
            
            fixed_geoms.append(fixed)
            
            if idx % 100 == 0 and idx > 0:
                logger.debug(f"Processed {idx}/{len(gdf)} geometries")
        
        gdf['geometry'] = fixed_geoms
        
        # Remove null geometries
        gdf = gdf[gdf.geometry.notna()]
        gdf = gdf[~gdf.geometry.is_empty]
        
        # Reproject to Web Mercator
        if gdf.crs != 'EPSG:3857':
            logger.info(f"Reprojecting from {gdf.crs} to EPSG:3857")
            gdf = gdf.to_crs('EPSG:3857')
        
        # Add color if not present
        if 'color' not in gdf.columns:
            gdf['color'] = self.line_color
        
        # Calculate line widths if not present
        if 'width' not in gdf.columns:
            gdf['width'] = 1.0
        
        logger.info(f"Prepared {len(gdf)} valid features")
        return gdf
    
    def build_spatial_index(self, gdf: gpd.GeoDataFrame) -> index.Index:
        """Build R-tree spatial index."""
        logger.info("Building spatial index...")
        idx = index.Index()
        
        for i, geometry in enumerate(gdf.geometry):
            if geometry is not None and not geometry.is_empty:
                idx.insert(i, geometry.bounds)
        
        logger.info(f"Spatial index built with {len(gdf)} features")
        return idx
    
    def get_tile_bounds_3857(self, x: int, y: int, z: int, 
                            with_buffer: bool = True) -> Tuple[float, float, float, float]:
        """Get tile bounds in EPSG:3857."""
        # Get tile bounds in lat/lon
        tile = mercantile.Tile(x, y, z)
        bounds_4326 = mercantile.bounds(tile)
        
        # Convert to Web Mercator
        west, south = self.transformer_to_3857.transform(bounds_4326.west, bounds_4326.south)
        east, north = self.transformer_to_3857.transform(bounds_4326.east, bounds_4326.north)
        
        if with_buffer:
            # Calculate buffer in meters
            tile_width = east - west
            tile_height = north - south
            buffer_x = (tile_width / self.tile_size) * self.buffer_pixels
            buffer_y = (tile_height / self.tile_size) * self.buffer_pixels
            
            return (
                west - buffer_x,
                south - buffer_y,
                east + buffer_x,
                north + buffer_y
            )
        
        return west, south, east, north
    
    def clip_to_tile_bounds(self, geom, bounds: Tuple[float, float, float, float]):
        """Clip geometry to tile bounds precisely."""
        west, south, east, north = bounds
        clip_box = box(west, south, east, north)
        
        try:
            # Perform intersection
            clipped = geom.intersection(clip_box)
            
            if clipped.is_empty:
                return None
            
            # Handle GeometryCollection results
            if clipped.geom_type == 'GeometryCollection':
                # Extract relevant geometries
                lines = []
                for g in clipped.geoms:
                    if g.geom_type in ['LineString', 'MultiLineString']:
                        lines.append(g)
                
                if lines:
                    return unary_union(lines) if len(lines) > 1 else lines[0]
                return None
            
            return clipped
            
        except Exception as e:
            logger.debug(f"Clipping error: {e}")
            return None
    
    def get_line_width_for_zoom(self, base_width: float, zoom: int) -> float:
        """Calculate appropriate line width for zoom level."""
        # Scale line width with zoom
        if zoom <= 6:
            return base_width * 0.5
        elif zoom <= 10:
            return base_width * 1.0
        elif zoom <= 14:
            return base_width * 1.5
        elif zoom <= 16:
            return base_width * 2.0
        else:
            return base_width * 2.5
    
    def render_with_cairo(self, features: gpd.GeoDataFrame, 
                         bounds: Tuple[float, float, float, float],
                         zoom: int) -> Image.Image:
        """Render features using Cairo for precise anti-aliasing."""
        west, south, east, north = bounds
        width = self.tile_size + 2 * self.buffer_pixels
        height = self.tile_size + 2 * self.buffer_pixels
        
        # Create Cairo surface
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        ctx = cairo.Context(surface)
        
        # Clear background (transparent)
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.paint()
        
        # Set up transformation matrix
        scale_x = width / (east - west)
        scale_y = height / (north - south)
        
        def transform_point(x, y):
            px = (x - west) * scale_x
            py = height - ((y - south) * scale_y)  # Flip Y axis
            return px, py
        
        # Enable anti-aliasing
        ctx.set_antialias(cairo.ANTIALIAS_BEST)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        
        # Render each feature
        for _, feature in features.iterrows():
            geom = feature.geometry
            
            # Get color
            color = feature.get('color', self.line_color)
            if isinstance(color, str) and color.startswith('#'):
                r = int(color[1:3], 16) / 255
                g = int(color[3:5], 16) / 255
                b = int(color[5:7], 16) / 255
            else:
                r, g, b = 0.08, 0.88, 0.60  # Default color
            
            # Get line width
            base_width = float(feature.get('width', 1.0))
            line_width = self.get_line_width_for_zoom(base_width, zoom)
            
            # Set stroke properties
            ctx.set_source_rgba(r, g, b, 0.9)  # Slight transparency
            ctx.set_line_width(line_width)
            
            # Draw geometry
            if geom.geom_type == 'LineString':
                coords = list(geom.coords)
                if len(coords) >= 2:
                    # Start path
                    x, y = transform_point(coords[0][0], coords[0][1])
                    ctx.move_to(x, y)
                    
                    # Draw line segments
                    for coord in coords[1:]:
                        x, y = transform_point(coord[0], coord[1])
                        ctx.line_to(x, y)
                    
                    ctx.stroke()
                    
            elif geom.geom_type == 'MultiLineString':
                for line in geom.geoms:
                    coords = list(line.coords)
                    if len(coords) >= 2:
                        x, y = transform_point(coords[0][0], coords[0][1])
                        ctx.move_to(x, y)
                        
                        for coord in coords[1:]:
                            x, y = transform_point(coord[0], coord[1])
                            ctx.line_to(x, y)
                        
                        ctx.stroke()
            
            elif geom.geom_type == 'Point':
                # Render as circle
                x, y = transform_point(geom.x, geom.y)
                radius = max(2, line_width * 2)
                ctx.arc(x, y, radius, 0, 2 * np.pi)
                ctx.fill()
        
        # Convert to PIL Image
        buf = surface.get_data()
        img = Image.frombuffer("RGBA", (width, height), buf, "raw", "BGRA", 0, 1)
        
        return img
    
    def generate_tile(self, x: int, y: int, z: int,
                     gdf: gpd.GeoDataFrame, spatial_idx: index.Index) -> Optional[str]:
        """Generate a single tile with seamless rendering."""
        try:
            # Check if tile exists
            tile_path = self.output_dir / str(z) / str(x) / f"{y}.png"
            if self.resume and tile_path.exists():
                return "skipped"
            
            # Get tile bounds with buffer
            buffered_bounds = self.get_tile_bounds_3857(x, y, z, with_buffer=True)
            
            # Query spatial index
            possible_matches = list(spatial_idx.intersection(buffered_bounds))
            
            if not possible_matches:
                return "empty"
            
            # Get intersecting features
            tile_box = box(*buffered_bounds)
            intersecting_features = []
            
            for idx in possible_matches:
                geom = gdf.iloc[idx].geometry
                if geom and geom.intersects(tile_box):
                    # Simplify for zoom
                    simplified = self.simplify_for_zoom(geom, z)
                    
                    # Clip to buffered bounds
                    clipped = self.clip_to_tile_bounds(simplified, buffered_bounds)
                    
                    if clipped and not clipped.is_empty:
                        # Create a copy of the feature with clipped geometry
                        feature = gdf.iloc[idx].copy()
                        feature['geometry'] = clipped
                        intersecting_features.append(feature)
            
            if not intersecting_features:
                return "empty"
            
            # Create GeoDataFrame from features
            features_gdf = gpd.GeoDataFrame(intersecting_features)
            
            # Render with Cairo
            img = self.render_with_cairo(features_gdf, buffered_bounds, z)
            
            # Crop to remove buffer
            img = img.crop((
                self.buffer_pixels,
                self.buffer_pixels,
                self.buffer_pixels + self.tile_size,
                self.buffer_pixels + self.tile_size
            ))
            
            # Apply final smoothing for better appearance
            if z >= 14:
                img = img.filter(ImageFilter.SMOOTH)
            
            # Save debug image if requested
            if self.debug:
                self._save_debug_image(x, y, z, features_gdf, buffered_bounds)
            
            # Create output directory and save
            tile_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(tile_path, 'PNG', optimize=True)
            
            return "generated"
            
        except Exception as e:
            logger.error(f"Error generating tile {z}/{x}/{y}: {e}")
            import traceback
            traceback.print_exc()
            return "error"
    
    def _save_debug_image(self, x: int, y: int, z: int, 
                         features: gpd.GeoDataFrame, bounds: Tuple):
        """Save debug image showing buffer area and clipping."""
        debug_dir = self.output_dir / "debug" / str(z) / str(x)
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        # Render with visible buffer boundary
        img = self.render_with_cairo(features, bounds, z)
        
        # Draw tile boundary
        draw = ImageDraw.Draw(img)
        tile_rect = [
            self.buffer_pixels,
            self.buffer_pixels,
            self.buffer_pixels + self.tile_size - 1,
            self.buffer_pixels + self.tile_size - 1
        ]
        draw.rectangle(tile_rect, outline=(0, 255, 0, 255), width=2)
        
        # Save
        debug_path = debug_dir / f"{y}_debug.png"
        img.save(debug_path, 'PNG')
    
    def get_tiles_for_zoom(self, gdf: gpd.GeoDataFrame, zoom: int) -> List[mercantile.Tile]:
        """Get all tiles that intersect with data at given zoom."""
        # Convert to EPSG:4326 for tile calculation
        gdf_4326 = gdf.to_crs('EPSG:4326')
        bounds = gdf_4326.total_bounds
        
        # Add small buffer to ensure edge tiles are included
        buffer = 0.01  # degrees
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
        start_time = time.time()
        
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
            zoom_start = time.time()
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
                        self.debug,
                        self.line_color
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
                        elapsed = time.time() - zoom_start
                        rate = completed / elapsed if elapsed > 0 else 0
                        logger.info(f"  Zoom {z}: {completed}/{len(tiles)} tiles "
                                  f"({rate:.1f} tiles/sec)")
            
            zoom_elapsed = time.time() - zoom_start
            logger.info(f"  Zoom {z} complete in {zoom_elapsed:.1f}s")
        
        # Clean up cache
        if cache_file.exists():
            os.remove(cache_file)
        
        # Total time
        total_elapsed = time.time() - start_time
        
        # Final summary
        logger.info("\n" + "=" * 70)
        logger.info("TILE GENERATION COMPLETE")
        logger.info(f"Total time: {total_elapsed:.1f} seconds")
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
                             resume: bool, debug: bool, line_color: str) -> str:
        """Worker function for parallel tile generation."""
        # Create generator instance in worker
        generator = SeamlessLineGenerator(
            input_file=str(cache_file),
            output_dir=str(output_dir),
            tile_size=tile_size,
            buffer_pixels=buffer_pixels,
            resume=resume,
            debug=debug,
            line_color=line_color
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
            "name": "Seamless Line Tiles",
            "description": "Pixel-perfect seamless tiles with no bleeding",
            "version": "1.0.0",
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
        
        # HTML Viewer
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Seamless Tiles Viewer</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
        .info {{
            position: fixed;
            top: 10px;
            right: 10px;
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            z-index: 1000;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info">
        <h4>Seamless Tiles</h4>
        <p>Zoom: <span id="zoom">12</span></p>
        <p>No bleeding • No seams • Pixel-perfect</p>
    </div>
    <script>
        var map = L.map('map').setView([{(bounds[1] + bounds[3]) / 2}, {(bounds[0] + bounds[2]) / 2}], 12);
        
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors',
            opacity: 0.5
        }}).addTo(map);
        
        L.tileLayer('{{z}}/{{x}}/{{y}}.png', {{
            minZoom: {self.min_zoom},
            maxZoom: {self.max_zoom},
            attribution: 'Seamless Tiles'
        }}).addTo(map);
        
        map.on('zoomend', function() {{
            document.getElementById('zoom').textContent = map.getZoom();
        }});
    </script>
</body>
</html>"""
        
        with open(self.output_dir / "viewer.html", "w") as f:
            f.write(html_content)
        
        logger.info(f"Created: tilejson.json, viewer.html")
    
    def validate_seamless(self, zoom: int = 10):
        """Validate seamless rendering by checking adjacent tiles."""
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
        logger.info(f"Checking 3x3 grid centered at tile {zoom}/{x}/{y}")
        
        # Load tiles and check edges
        tiles = {}
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                tile_path = self.output_dir / str(zoom) / str(x + dx) / f"{y + dy}.png"
                if tile_path.exists():
                    tiles[(dx, dy)] = np.array(Image.open(tile_path))
        
        if len(tiles) < 2:
            logger.warning("Not enough tiles for validation")
            return False
        
        # Check horizontal seams
        seams_ok = True
        for dy in range(-1, 2):
            if (0, dy) in tiles and (1, dy) in tiles:
                left_edge = tiles[(0, dy)][:, -1, :]
                right_edge = tiles[(1, dy)][:, 0, :]
                diff = np.mean(np.abs(left_edge.astype(float) - right_edge.astype(float)))
                if diff > 1.0:  # Allow 1 pixel difference for anti-aliasing
                    logger.warning(f"Seam detected between tiles at y={dy}: diff={diff:.2f}")
                    seams_ok = False
        
        # Check vertical seams
        for dx in range(-1, 2):
            if (dx, 0) in tiles and (dx, 1) in tiles:
                top_edge = tiles[(dx, 0)][-1, :, :]
                bottom_edge = tiles[(dx, 1)][0, :, :]
                diff = np.mean(np.abs(top_edge.astype(float) - bottom_edge.astype(float)))
                if diff > 1.0:
                    logger.warning(f"Seam detected between tiles at x={dx}: diff={diff:.2f}")
                    seams_ok = False
        
        if seams_ok:
            logger.info("✓ Validation passed: No visible seams detected")
        else:
            logger.warning("⚠ Validation found potential seams (may be due to anti-aliasing)")
        
        # Create composite for visual inspection
        validation_dir = self.output_dir / "validation"
        validation_dir.mkdir(exist_ok=True)
        
        composite = Image.new('RGBA', (self.tile_size * 3, self.tile_size * 3), (255, 255, 255, 255))
        for (dx, dy), tile_array in tiles.items():
            tile_img = Image.fromarray(tile_array)
            composite.paste(tile_img, ((dx + 1) * self.tile_size, (dy + 1) * self.tile_size))
        
        composite_path = validation_dir / f"seamless_check_z{zoom}_x{x}_y{y}.png"
        composite.save(composite_path)
        logger.info(f"✓ Validation composite saved: {composite_path}")
        
        return seams_ok


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Generate seamless PNG tiles for Mapbox (optimized for lines)"
    )
    
    parser.add_argument("--input", required=True, help="Input GeoJSON file")
    parser.add_argument("--output-dir", default="./tiles", help="Output directory")
    parser.add_argument("--min-zoom", type=int, default=4, help="Minimum zoom level")
    parser.add_argument("--max-zoom", type=int, default=18, help="Maximum zoom level")
    parser.add_argument("--tile-size", type=int, default=512, help="Tile size in pixels")
    parser.add_argument("--buffer", type=int, default=16, help="Buffer size in pixels")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--line-color", default="#14E098", help="Default line color")
    parser.add_argument("--no-resume", action="store_true", help="Regenerate existing tiles")
    parser.add_argument("--debug", action="store_true", help="Save debug images")
    parser.add_argument("--validate", action="store_true", help="Validate after generation")
    parser.add_argument("--validate-only", action="store_true", help="Only run validation")
    parser.add_argument("--validate-zoom", type=int, default=10, help="Zoom for validation")
    
    args = parser.parse_args()
    
    # Create generator
    generator = SeamlessLineGenerator(
        input_file=args.input,
        output_dir=args.output_dir,
        min_zoom=args.min_zoom,
        max_zoom=args.max_zoom,
        tile_size=args.tile_size,
        buffer_pixels=args.buffer,
        workers=args.workers,
        resume=not args.no_resume,
        debug=args.debug,
        line_color=args.line_color
    )
    
    try:
        if args.validate_only:
            # Only run validation
            generator.validate_seamless(zoom=args.validate_zoom)
        else:
            # Generate tiles
            generator.generate_tiles_parallel()
            
            # Run validation if requested
            if args.validate:
                generator.validate_seamless(zoom=args.validate_zoom)
        
        logger.info("\n✓ Process completed successfully!")
        logger.info(f"✓ Output directory: {args.output_dir}")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()