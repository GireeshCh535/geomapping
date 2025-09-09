#!/usr/bin/env python3
"""
Fixed script to generate high-quality PNG tiles from Karnataka Bengaluru STRR GeoJSON
Creates tiles with specified color: #14e098
Includes robust geometry processing, spatial indexing, and anti-aliasing
"""

import os
import sys
import math
import numpy as np
from pathlib import Path
import mercantile
from PIL import Image, ImageDraw, ImageFilter
import json
import logging
import argparse
from shapely.geometry import shape, LineString, MultiLineString, Point, box
from shapely.ops import transform, unary_union
from shapely.validation import make_valid
import pyproj
from functools import partial
import geopandas as gpd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KarnatakaBengaluruSTRRTileGenerator:
    """
    Generate high-quality PNG tiles from Karnataka Bengaluru STRR GeoJSON
    with robust geometry processing and anti-aliasing
    """

    def __init__(self, data_dir: str = "data/karnataka/bengaluru/strr",
                 output_dir: str = "karnataka_bengaluru_strr_tiles",
                 skip_existing: bool = True):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.skip_existing = skip_existing

        # Color specification
        self.strr_color = (20, 224, 152)  # #14e098

        # Geometry processing parameters
        self.buffer_factor = 0.00001  # Small buffer for intersection testing
        self.precision_threshold = 1e-8  # Coordinate precision
        self.simplification_tolerance = 1e-6  # Geometry simplification

        # Data storage
        self.gdf = None
        self.spatial_index = None
        self.unary_union_geom = None

        logger.info("Karnataka Bengaluru STRR Tile Generator initialized")

    def fix_self_intersections(self, geom):
        """Fix self-intersecting geometries"""
        try:
            if not geom.is_valid:
                # Try to make valid using shapely's make_valid
                geom = make_valid(geom)
                
                # If still invalid, try buffer(0) trick
                if not geom.is_valid:
                    geom = geom.buffer(0)
                    
            return geom
        except Exception as e:
            logger.warning(f"Could not fix self-intersections: {e}")
            return geom

    def simplify_dense_geometry(self, geom, max_points=1000):
        """Simplify geometries with too many points"""
        try:
            if hasattr(geom, 'geoms'):  # MultiLineString
                simplified_geoms = []
                for g in geom.geoms:
                    if hasattr(g, 'coords') and len(g.coords) > max_points:
                        simplified_geoms.append(g.simplify(self.simplification_tolerance))
                    else:
                        simplified_geoms.append(g)
                return type(geom)(simplified_geoms)
            elif hasattr(geom, 'coords') and len(geom.coords) > max_points:
                return geom.simplify(self.simplification_tolerance)
            return geom
        except Exception as e:
            logger.warning(f"Could not simplify geometry: {e}")
            return geom

    def round_coordinates(self, geom):
        """Round coordinates to specified precision and remove duplicates"""
        try:
            def round_coords(coords):
                rounded = []
                prev_coord = None
                for coord in coords:
                    rounded_coord = (round(coord[0], 8), round(coord[1], 8))
                    if prev_coord is None or rounded_coord != prev_coord:
                        rounded.append(rounded_coord)
                        prev_coord = rounded_coord
                return rounded

            if hasattr(geom, 'geoms'):  # MultiLineString
                new_geoms = []
                for g in geom.geoms:
                    if hasattr(g, 'coords'):
                        new_coords = round_coords(g.coords)
                        if len(new_coords) >= 2:
                            new_geoms.append(LineString(new_coords))
                return MultiLineString(new_geoms) if len(new_geoms) > 1 else (new_geoms[0] if new_geoms else geom)
            elif hasattr(geom, 'coords'):
                new_coords = round_coords(geom.coords)
                if len(new_coords) >= 2:
                    return LineString(new_coords)
                return geom
            return geom
        except Exception as e:
            logger.warning(f"Could not round coordinates: {e}")
            return geom

    def handle_closed_loop(self, geom):
        """Ensure closed LineString geometries are properly closed"""
        try:
            if hasattr(geom, 'geoms'):  # MultiLineString
                new_geoms = []
                for g in geom.geoms:
                    if hasattr(g, 'coords') and len(g.coords) >= 2:
                        coords = list(g.coords)
                        # Check if first and last coordinates are the same
                        if coords[0] != coords[-1]:
                            coords.append(coords[0])  # Close the loop
                        new_geoms.append(LineString(coords))
                return MultiLineString(new_geoms) if len(new_geoms) > 1 else (new_geoms[0] if new_geoms else geom)
            elif hasattr(geom, 'coords') and len(geom.coords) >= 2:
                coords = list(geom.coords)
                if coords[0] != coords[-1]:
                    coords.append(coords[0])  # Close the loop
                return LineString(coords)
            return geom
        except Exception as e:
            logger.warning(f"Could not handle closed loop: {e}")
            return geom

    def load_and_process_data(self):
        """Load and process GeoJSON data with robust geometry handling"""
        logger.info("Loading and processing STRR data...")
        
        try:
            # Load GeoJSON files
            geojson_files = list(self.data_dir.glob("*.geojson"))
            if not geojson_files:
                logger.error(f"No GeoJSON files found in {self.data_dir}")
                return False

            # Load all GeoJSON files into a single GeoDataFrame
            gdfs = []
            for geojson_path in geojson_files:
                logger.info(f"Loading {geojson_path}")
                gdf = gpd.read_file(geojson_path)
                gdfs.append(gdf)

            # Combine all GeoDataFrames
            self.gdf = gpd.pd.concat(gdfs, ignore_index=True)
            
            # Ensure CRS is WGS84
            if self.gdf.crs is None:
                self.gdf.crs = 'EPSG:4326'
            elif self.gdf.crs != 'EPSG:4326':
                self.gdf = self.gdf.to_crs('EPSG:4326')

            logger.info(f"Loaded {len(self.gdf)} features")

            # Process geometries
            logger.info("Processing geometries...")
            processed_geometries = []
            
            for idx, row in self.gdf.iterrows():
                geom = row.geometry
                
                # Apply geometry fixes
                geom = self.fix_self_intersections(geom)
                geom = self.handle_closed_loop(geom)
                geom = self.simplify_dense_geometry(geom)
                geom = self.round_coordinates(geom)
                
                processed_geometries.append(geom)

            # Update the GeoDataFrame with processed geometries
            self.gdf.geometry = processed_geometries

            # Build spatial index
            logger.info("Building spatial index...")
            self.spatial_index = self.gdf.sindex

            # Create unary union for overall bounds and intersection testing
            logger.info("Creating unary union...")
            self.unary_union_geom = unary_union(self.gdf.geometry)

            logger.info("Data processing completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error loading and processing data: {e}")
            return False

    def get_strr_line_width(self, zoom):
        """Get appropriate line width for STRR based on zoom level"""
        width_map = {
            4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1, 10: 2, 11: 2, 12: 3, 13: 4, 14: 5, 15: 6, 16: 8, 17: 10, 18: 12
        }
        return width_map.get(zoom, 3)

    def get_features_for_tile(self, tile_bounds):
        """Get features that intersect with the tile bounds using spatial index"""
        try:
            # Create a buffered tile polygon for intersection testing
            tile_polygon = box(
                tile_bounds.west - self.buffer_factor,
                tile_bounds.south - self.buffer_factor,
                tile_bounds.east + self.buffer_factor,
                tile_bounds.north + self.buffer_factor
            )

            # Use spatial index to find potential intersections
            possible_matches_index = list(self.spatial_index.intersection(tile_polygon.bounds))
            possible_matches = self.gdf.iloc[possible_matches_index]

            # Refine with actual intersection test
            intersecting_features = possible_matches[possible_matches.intersects(tile_polygon)]
            
            return intersecting_features

        except Exception as e:
            logger.error(f"Error getting features for tile: {e}")
            return self.gdf.iloc[0:0]  # Return empty GeoDataFrame

    def clip_geometry_to_tile(self, geom, tile_bounds):
        """Clip geometry to tile bounds with proper handling"""
        try:
            # Create tile polygon with small buffer to avoid precision issues
            tile_polygon = box(
                tile_bounds.west - 0.0001,
                tile_bounds.south - 0.0001,
                tile_bounds.east + 0.0001,
                tile_bounds.north + 0.0001
            )

            # Clip the geometry
            clipped = geom.intersection(tile_polygon)
            
            if clipped.is_empty:
                return None

            # Handle different geometry types
            if hasattr(clipped, 'geoms'):  # MultiLineString or GeometryCollection
                valid_geoms = []
                for g in clipped.geoms:
                    if hasattr(g, 'coords') and len(g.coords) >= 2:
                        valid_geoms.append(g)
                if valid_geoms:
                    return MultiLineString(valid_geoms) if len(valid_geoms) > 1 else valid_geoms[0]
                return None
            elif hasattr(clipped, 'coords') and len(clipped.coords) >= 2:
                return clipped
            return None

        except Exception as e:
            logger.warning(f"Error clipping geometry: {e}")
            return None

    def coords_to_pixels(self, coords, tile_bounds):
        """Convert geographic coordinates to pixel coordinates with subpixel precision"""
        pixels = []
        for lon, lat in coords:
            # Convert to tile-relative coordinates (0-1)
            x = (lon - tile_bounds.west) / (tile_bounds.east - tile_bounds.west)
            y = (tile_bounds.north - lat) / (tile_bounds.north - tile_bounds.south)
            
            # Convert to pixel coordinates
            pixel_x = x * 256
            pixel_y = y * 256
            
            pixels.append((pixel_x, pixel_y))
        return pixels

    def draw_strr_line(self, draw, pixels, color_rgb, width):
        """Draw STRR line with anti-aliasing"""
        if len(pixels) < 2:
            return

        # Draw the main line
        draw.line(pixels, fill=color_rgb, width=width)

        # For wider lines, add a subtle center line for better visibility
        if width > 4:
            center_color = tuple(min(255, c + 30) for c in color_rgb)
            draw.line(pixels, fill=center_color, width=max(1, width // 3))

    def generate_tile(self, x, y, zoom):
        """Generate a single tile with anti-aliasing"""
        try:
            # Get tile bounds
            tile_bounds = mercantile.bounds(x, y, zoom)
            
            # Get features that intersect with this tile
            intersecting_features = self.get_features_for_tile(tile_bounds)
            
            if intersecting_features.empty:
                return None

            # Determine scale factor for anti-aliasing
            scale = 2 if zoom >= 12 else 1
            tile_size = 256 * scale

            # Create higher resolution image for anti-aliasing
            img = Image.new('RGBA', (tile_size, tile_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Get line width for this zoom level
            line_width = self.get_strr_line_width(zoom) * scale

            # Process each feature
            for idx, feature in intersecting_features.iterrows():
                geom = feature.geometry
                
                # Clip geometry to tile bounds
                clipped_geom = self.clip_geometry_to_tile(geom, tile_bounds)
                if clipped_geom is None:
                    continue

                # Convert to pixel coordinates
                if hasattr(clipped_geom, 'geoms'):  # MultiLineString
                    for g in clipped_geom.geoms:
                        if hasattr(g, 'coords'):
                            pixels = self.coords_to_pixels(g.coords, tile_bounds)
                            self.draw_strr_line(draw, pixels, self.strr_color, line_width)
                elif hasattr(clipped_geom, 'coords'):
                    pixels = self.coords_to_pixels(clipped_geom.coords, tile_bounds)
                    self.draw_strr_line(draw, pixels, self.strr_color, line_width)

            # Downscale for anti-aliasing effect
            if scale > 1:
                img = img.resize((256, 256), Image.Resampling.LANCZOS)
                
                # Apply smoothing filter for higher zoom levels
                if zoom >= 14:
                    img = img.filter(ImageFilter.SMOOTH_MORE)

            return img

        except Exception as e:
            logger.error(f"Error generating tile {zoom}/{x}/{y}: {e}")
            return None

    def generate_tiles(self, min_zoom=4, max_zoom=18):
        """Generate PNG tiles for Karnataka Bengaluru STRR"""
        logger.info(f"Generating tiles from zoom {min_zoom} to {max_zoom}")
        
        # Load and process data
        if not self.load_and_process_data():
            logger.error("Failed to load and process data")
            return 0

        # Get overall bounds
        bounds = self.unary_union_geom.bounds
        logger.info(f"Overall bounds: {bounds}")

        total_tiles = 0
        generated_tiles = 0
        skipped_tiles = 0

        for zoom in range(min_zoom, max_zoom + 1):
            logger.info(f"Processing zoom level {zoom}")

            # Calculate tile bounds for this zoom level
            min_tile = mercantile.tile(bounds[0], bounds[1], zoom)
            max_tile = mercantile.tile(bounds[2], bounds[3], zoom)

            zoom_dir = self.output_dir / str(zoom)
            zoom_dir.mkdir(exist_ok=True)

            for x in range(min_tile.x, max_tile.x + 1):
                x_dir = zoom_dir / str(x)
                x_dir.mkdir(exist_ok=True)

                for y in range(max_tile.y, min_tile.y + 1):
                    tile_path = x_dir / f"{y}.png"
                    total_tiles += 1

                    # Skip if tile exists and skip_existing is True
                    if tile_path.exists() and self.skip_existing:
                        skipped_tiles += 1
                        continue

                    # Generate the tile
                    img = self.generate_tile(x, y, zoom)
                    
                    if img is not None:
                        img.save(tile_path, 'PNG')
                        generated_tiles += 1
                    else:
                        # Create empty tile if no content
                        empty_img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
                        empty_img.save(tile_path, 'PNG')

                    # Log progress
                    if total_tiles % 1000 == 0:
                        logger.info(f"Processed {total_tiles} tiles, generated {generated_tiles}, skipped {skipped_tiles}")

        logger.info(f"Tile generation completed!")
        logger.info(f"Total tiles processed: {total_tiles}")
        logger.info(f"Tiles generated: {generated_tiles}")
        logger.info(f"Tiles skipped: {skipped_tiles}")

        # Create supporting files
        self.create_viewer_html(bounds, min_zoom, max_zoom)
        self.create_tilejson(bounds, min_zoom, max_zoom)

        return generated_tiles

    def create_viewer_html(self, bounds, min_zoom, max_zoom):
        """Create HTML viewer for the tiles"""
        logger.info("Creating viewer.html...")
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Karnataka Bengaluru STRR - Fixed PNG Tiles</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ height: 100vh; width: 100%; }}
        .info {{
            position: fixed;
            top: 10px;
            right: 10px;
            background: white;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            z-index: 1000;
            font-family: Arial, sans-serif;
        }}
        .info h3 {{ margin-top: 0; color: #333; }}
        .info p {{ margin: 5px 0; color: #666; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info">
        <h3>Karnataka Bengaluru STRR</h3>
        <p><strong>Satellite Town Ring Road</strong></p>
        <p>Color: #14e098</p>
        <p>Zoom: {min_zoom} - {max_zoom}</p>
        <p>Bounds: {bounds[0]:.4f}, {bounds[1]:.4f}, {bounds[2]:.4f}, {bounds[3]:.4f}</p>
    </div>

    <script>
        // Initialize map
        var map = L.map('map').setView([{(bounds[1] + bounds[3]) / 2}, {(bounds[0] + bounds[2]) / 2}], 10);

        // Add base layer
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors'
        }}).addTo(map);

        // Add STRR layer
        const strrLayer = L.tileLayer('http://localhost:3000/{{z}}/{{x}}/{{y}}.png', {{
            attribution: 'Karnataka Government',
            opacity: 0.8
        }}).addTo(map);

        // Add layer control
        var baseMaps = {{
            "OpenStreetMap": L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '© OpenStreetMap contributors'
            }})
        }};

        var overlayMaps = {{
            "STRR": strrLayer
        }};

        L.control.layers(baseMaps, overlayMaps).addTo(map);
    </script>
</body>
</html>"""

        with open(self.output_dir / "viewer.html", "w") as f:
            f.write(html_content)

    def create_tilejson(self, bounds, min_zoom, max_zoom):
        """Create TileJSON file"""
        logger.info("Creating tilejson.json...")
        
        tilejson = {
            "tilejson": "2.2.0",
            "name": "Karnataka Bengaluru STRR",
            "description": "Satellite Town Ring Road (STRR) in Bengaluru, Karnataka - Fixed Version",
            "version": "1.0.0",
            "attribution": "Karnataka Government",
            "template": "",
            "legend": "",
            "scheme": "xyz",
            "tiles": [
                "http://localhost:3000/{z}/{x}/{y}.png"
            ],
            "grids": [],
            "data": [],
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "bounds": [
                bounds[0],  # west
                bounds[1],  # south
                bounds[2],  # east
                bounds[3]   # north
            ],
            "center": [
                (bounds[0] + bounds[2]) / 2,
                (bounds[1] + bounds[3]) / 2,
                10
            ]
        }

        with open(self.output_dir / "tilejson.json", "w") as f:
            json.dump(tilejson, f, indent=2)

    def print_help(self):
        """Print help information"""
        print("""
Karnataka Bengaluru STRR Tile Generator - Fixed Version

This script generates high-quality PNG tiles from Karnataka Bengaluru STRR GeoJSON data.
It includes robust geometry processing, spatial indexing, and anti-aliasing.

Usage:
    python karnataka_bengaluru_strr_tiles_fixed.py [options]

Options:
    --force              Force regeneration of all tiles (ignore existing)
    --min-zoom ZOOM      Minimum zoom level (default: 4)
    --max-zoom ZOOM      Maximum zoom level (default: 18)

Features:
    - Robust geometry processing (self-intersection fixing, simplification)
    - Spatial indexing for efficient tile generation
    - Anti-aliasing for smooth line rendering
    - Automatic coordinate precision handling
    - Support for skipping existing tiles

Output:
    - PNG tiles in z/x/y format
    - viewer.html for local testing
    - tilejson.json for tile metadata

Example:
    python karnataka_bengaluru_strr_tiles_fixed.py --force --min-zoom 10 --max-zoom 16
        """)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Generate Karnataka Bengaluru STRR tiles')
    parser.add_argument('--force', action='store_true', 
                       help='Force regeneration of all tiles (ignore existing)')
    parser.add_argument('--min-zoom', type=int, default=4,
                       help='Minimum zoom level (default: 4)')
    parser.add_argument('--max-zoom', type=int, default=18,
                       help='Maximum zoom level (default: 18)')
    parser.add_argument('--help-detailed', action='store_true',
                       help='Show detailed help information')

    args = parser.parse_args()

    if args.help_detailed:
        generator = KarnatakaBengaluruSTRRTileGenerator()
        generator.print_help()
        return

    logger.info("Starting Karnataka Bengaluru STRR tile generation (Fixed Version)")

    # Initialize generator
    generator = KarnatakaBengaluruSTRRTileGenerator(skip_existing=not args.force)

    try:
        # Generate tiles
        total_generated = generator.generate_tiles(
            min_zoom=args.min_zoom,
            max_zoom=args.max_zoom
        )

        logger.info(f"Karnataka Bengaluru STRR tile generation completed!")
        logger.info(f"Total tiles generated: {total_generated}")

    except Exception as e:
        logger.error(f"Error during tile generation: {e}")
        raise

if __name__ == "__main__":
    main()
