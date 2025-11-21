#!/usr/bin/env python3
"""
Generic Master Plan Tile Generator
==================================

A data-driven tile generator that works for any city based on a configuration file.
Usage: python generic_tile_generator.py --config path/to/config.json
"""

import os
import sys
import logging
import time
import json
import argparse
import csv
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional

import geopandas as gpd
import numpy as np
import mercantile
from PIL import Image, ImageDraw
from shapely.geometry import box, Polygon

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MasterPlanTileGenerator:
    """
    Generic Tile generator for Master Plans.
    """
    
    def __init__(self, config_path: str):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)
            
        self.city_name = self.config.get('city_name', 'Unknown City')
        self.data_dir = Path(self.config['data_dir'])
        self.output_dir = Path(self.config['output_dir'])
        
        # Zoom configuration
        self.min_zoom = self.config['zoom_range'][0]
        self.max_zoom = self.config['zoom_range'][1]
        
        # Tile configuration
        self.tile_size = self.config.get('tile_size', 256)
        self.supersample_factor = self.config.get('supersample_factor', 4)
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load Legend/Styles
        self.zoning_styles = self._load_styles()
        
        # Mappings and Priorities
        self.filename_mapping = self.config.get('filename_mapping', {})
        self.rendering_priority = self.config.get('rendering_priority', {})
        
        logger.info(f"Initialized Generator for: {self.city_name}")
        logger.info(f"Data directory: {self.data_dir}")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Zoom range: {self.min_zoom}-{self.max_zoom}")

    def _load_styles(self) -> Dict:
        """Load styles from the CSV file specified in config."""
        styles = {}
        legend_path = self.config.get('legend_path')
        
        if legend_path and os.path.exists(legend_path):
            with open(legend_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    zone = row['Zone']
                    color = row['Color']
                    styles[zone] = {
                        "fill_color": color,
                        "hatch": row.get('Hatch', '').strip(),
                        "hatch_color": row.get('HatchColor', '').strip()
                    }
        else:
            # Fallback or inline styles if provided
            styles = self.config.get('styles', {})
            
        return styles

    def load_all_geojson_files(self) -> gpd.GeoDataFrame:
        """Load all GeoJSON files from the data directory."""
        logger.info(f"Loading GeoJSON files from {self.data_dir}")
        
        all_gdfs = []
        geojson_files = list(self.data_dir.glob("*.geojson"))
        logger.info(f"Found {len(geojson_files)} GeoJSON files")
        
        for file_path in geojson_files:
            filename_stem = file_path.stem
            
            # Determine zone type from filename
            zone_type = self.filename_mapping.get(filename_stem, filename_stem)
            
            logger.info(f"Loading {filename_stem} as {zone_type}...")
            
            try:
                gdf = gpd.read_file(file_path)
                if not gdf.empty:
                    # Add zone type column
                    gdf['zone_type'] = zone_type
                    
                    # Ensure CRS is WGS84
                    if gdf.crs is not None and gdf.crs.to_string() != "EPSG:4326":
                        gdf = gdf.to_crs("EPSG:4326")
                    
                    all_gdfs.append(gdf)
                else:
                    logger.warning(f"  No features found in {filename_stem}")
            except Exception as e:
                logger.error(f"  Error loading {filename_stem}: {e}")
        
        if not all_gdfs:
            raise ValueError("No valid GeoJSON files found")
        
        # Combine all GeoDataFrames
        combined_gdf = gpd.pd.concat(all_gdfs, ignore_index=True)
        logger.info(f"Loaded {len(combined_gdf)} total features")
        
        # Create spatial index
        logger.info("Creating spatial index...")
        combined_gdf.sindex
        
        return combined_gdf

    def get_tiles_for_bounds(self, gdf: gpd.GeoDataFrame, zoom: int) -> List[mercantile.Tile]:
        """Get all tiles that intersect with the data bounds for a given zoom level."""
        bounds = gdf.total_bounds
        # Add small buffer to ensure edge tiles are caught
        buffer = 0.00001
        buffered_bounds = [
            bounds[0] - buffer,
            bounds[1] - buffer,
            bounds[2] + buffer,
            bounds[3] + buffer
        ]
        return list(mercantile.tiles(*buffered_bounds, zooms=zoom))

    def render_tile(self, tile: mercantile.Tile, gdf: gpd.GeoDataFrame) -> Optional[Image.Image]:
        """Render a single tile."""
        tile_bounds = mercantile.bounds(tile)
        
        # Create high-res image for supersampling
        render_size = self.tile_size * self.supersample_factor
        # Initialize with transparent WHITE to avoid black halos during interpolation
        img = Image.new('RGBA', (render_size, render_size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        
        def coord_to_pixel(lon, lat):
            tile_x = (lon - tile_bounds.west) / (tile_bounds.east - tile_bounds.west) * render_size
            tile_y = (tile_bounds.north - lat) / (tile_bounds.north - tile_bounds.south) * render_size
            return tile_x, tile_y
        
        # Create BUFFERED tile geometry to prevent edge artifacts
        width = tile_bounds.east - tile_bounds.west
        height = tile_bounds.north - tile_bounds.south
        buffer_x = width * 0.1
        buffer_y = height * 0.1
        
        buffered_tile_geom = box(
            tile_bounds.west - buffer_x, tile_bounds.south - buffer_y,
            tile_bounds.east + buffer_x, tile_bounds.north + buffer_y
        )
        
        # Find intersecting features using spatial index
        possible_matches_index = list(gdf.sindex.intersection(buffered_tile_geom.bounds))
        possible_matches = gdf.iloc[possible_matches_index]
        
        # Filter features that actually intersect the buffered tile
        intersecting_features = possible_matches[possible_matches.geometry.intersects(buffered_tile_geom)]
        
        if intersecting_features.empty:
            return None
        
        all_features = []
        for _, feature in intersecting_features.iterrows():
            zone_type = feature['zone_type']
            
            # Clip geometry to BUFFERED tile bounds
            clipped_geom = feature.geometry.intersection(buffered_tile_geom)
            
            if not clipped_geom.is_empty:
                all_features.append({
                    'geometry': clipped_geom,
                    'zone_type': zone_type,
                    'render_priority': self.rendering_priority.get(zone_type, 5)
                })
        
        if not all_features:
            return None
        
        # Sort by priority
        all_features.sort(key=lambda x: x['render_priority'])
        
        for feature in all_features:
            zone_type = feature['zone_type']
            geometry = feature['geometry']
            
            style = self.zoning_styles.get(zone_type, {"fill_color": "#CCCCCC"})
            fill_color = style.get("fill_color", "#CCCCCC")
            hatch_pattern = style.get("hatch", "")
            hatch_color_hex = style.get("hatch_color", "#000000")
            
            if fill_color.startswith('#'):
                rgb = tuple(int(fill_color[i:i+2], 16) for i in (1, 3, 5))
            else:
                rgb = (204, 204, 204)

            if hatch_color_hex and hatch_color_hex.startswith('#'):
                 hatch_rgb = tuple(int(hatch_color_hex[i:i+2], 16) for i in (1, 3, 5))
            else:
                 hatch_rgb = (0, 0, 0)
            
            # Only draw outlines for zoom levels >= 15
            draw_outlines = tile.z >= 15
            
            if geometry.geom_type == 'Polygon':
                self._draw_polygon(img, draw, geometry, rgb, hatch_pattern, hatch_rgb, coord_to_pixel, render_size, draw_outlines)
            elif geometry.geom_type == 'MultiPolygon':
                for poly in geometry.geoms:
                    self._draw_polygon(img, draw, poly, rgb, hatch_pattern, hatch_rgb, coord_to_pixel, render_size, draw_outlines)
        
        # Downsample to final size
        if self.supersample_factor > 1:
            # Use BILINEAR instead of LANCZOS to avoid ringing artifacts (extra mask pixels)
            img = img.resize((self.tile_size, self.tile_size), resample=Image.Resampling.BILINEAR)
            
        return img

    def _draw_polygon(self, img: Image.Image, draw: ImageDraw.Draw, polygon: Polygon, color: Tuple[int, int, int], hatch_pattern: str, hatch_color: Tuple[int, int, int], coord_to_pixel, render_size, draw_outline: bool):
        try:
            exterior_coords = list(polygon.exterior.coords)
            pixel_coords = []
            
            for lon, lat in exterior_coords:
                x, y = coord_to_pixel(lon, lat)
                pixel_coords.append((x, y))
            
            if len(pixel_coords) >= 3:
                # 1. Draw Solid Fill
                draw.polygon(pixel_coords, fill=color)

                # 2. Draw Hatch Pattern (if any)
                if hatch_pattern:
                    self._draw_hatch(img, pixel_coords, hatch_pattern, hatch_color, render_size)

                # 3. Draw Outline (if enabled)
                if draw_outline:
                    outline_color = (0, 0, 0)
                    # Scale outline width
                    outline_width = max(1, int(1 * (render_size / self.tile_size)))
                    draw.polygon(pixel_coords, fill=None, outline=outline_color, width=outline_width)
                
                # 4. Handle Holes
                for hole in polygon.interiors:
                    hole_coords = []
                    for lon, lat in hole.coords:
                        x, y = coord_to_pixel(lon, lat)
                        hole_coords.append((x, y))
                    
                    if len(hole_coords) >= 3:
                        # Clear the hole (transparent)
                        draw.polygon(hole_coords, fill=(0, 0, 0, 0))
                        # Re-draw outline for hole if needed
                        if draw_outline:
                             draw.polygon(hole_coords, fill=None, outline=outline_color, width=outline_width)

        except Exception as e:
            logger.warning(f"Error drawing polygon: {e}")

    def _draw_hatch(self, img: Image.Image, pixel_coords: List[Tuple[float, float]], pattern: str, color: Tuple[int, int, int], render_size: int):
        """
        Draws a simple hatch pattern over the polygon.
        Supported patterns:
        - '//////': Diagonal lines (top-left to bottom-right)
        - '......': Dots
        """
        # Create a mask for the polygon to clip the hatch
        mask = Image.new('L', (render_size, render_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.polygon(pixel_coords, fill=255)
        
        # Create a hatch layer
        hatch_layer = Image.new('RGBA', (render_size, render_size), (0, 0, 0, 0))
        hatch_draw = ImageDraw.Draw(hatch_layer)
        
        if pattern == '//////':
            spacing = int(render_size / 40) # Adjust density based on tile size
            width = max(1, int(render_size / 200))
            
            # Draw diagonal lines
            # We draw lines covering the whole tile, then mask them
            # Range needs to cover enough to handle diagonals
            for i in range(-render_size, render_size * 2, spacing):
                hatch_draw.line([(i, 0), (i + render_size, render_size)], fill=color + (255,), width=width)
                
        elif pattern == '......':
            spacing = int(render_size / 30)
            radius = max(1, int(render_size / 300))
            
            for x in range(0, render_size, spacing):
                for y in range(0, render_size, spacing):
                    # Offset every other row for a better dot pattern
                    offset_x = (spacing // 2) if (y // spacing) % 2 == 1 else 0
                    
                    hatch_draw.ellipse(
                        (x + offset_x - radius, y - radius, x + offset_x + radius, y + radius),
                        fill=color + (255,)
                    )

        # Composite the hatch layer onto the main image using the mask
        img.paste(hatch_layer, (0, 0), mask)


    def generate_tiles_for_zoom(self, zoom: int, gdf: gpd.GeoDataFrame) -> int:
        logger.info(f"Generating tiles for zoom level {zoom}")
        tiles = self.get_tiles_for_bounds(gdf, zoom)
        
        tiles_generated = 0
        for i, tile in enumerate(tiles):
            try:
                img = self.render_tile(tile, gdf)
                if img is not None:
                    # Check if tile has content (not just transparent)
                    if np.array(img).shape[2] == 4:
                        # If not completely transparent
                        if np.sum(np.array(img)[:, :, 3] == 0) / (256*256) < 0.99:
                            tile_dir = self.output_dir / str(zoom) / str(tile.x)
                            tile_dir.mkdir(parents=True, exist_ok=True)
                            tile_path = tile_dir / f"{tile.y}.png"
                            img.save(tile_path, 'PNG')
                            tiles_generated += 1
            except Exception as e:
                logger.error(f"Error processing tile {tile}: {e}")
        
        logger.info(f"Zoom {zoom}: Generated {tiles_generated} tiles")
        return tiles_generated

    def generate_tiles_parallel(self, max_workers: int = 4) -> None:
        gdf = self.load_all_geojson_files()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.generate_tiles_for_zoom, zoom, gdf) 
                      for zoom in range(self.min_zoom, self.max_zoom + 1)]
            for future in as_completed(futures):
                future.result()

def main():
    parser = argparse.ArgumentParser(description='Generate map tiles from GeoJSON data.')
    parser.add_argument('--config', type=str, required=True, help='Path to the configuration JSON file')
    parser.add_argument('--workers', type=int, default=4, help='Number of worker threads')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.config):
        logger.error(f"Config file not found: {args.config}")
        sys.exit(1)
        
    generator = MasterPlanTileGenerator(args.config)
    generator.generate_tiles_parallel(max_workers=args.workers)

if __name__ == "__main__":
    main()
