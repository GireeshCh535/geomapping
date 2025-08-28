#!/usr/bin/env python3
"""
Dedicated script to generate high-quality PNG tiles from Karnataka Bengaluru highways GeoJSON
Creates tiles with specified color: #14e098
"""

import os
import sys
import math
import numpy as np
from pathlib import Path
import mercantile
from PIL import Image, ImageDraw
import json
import logging
from shapely.geometry import shape, LineString, MultiLineString, Point
from shapely.ops import transform
import pyproj
from functools import partial

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KarnatakaBengaluruHighwaysTileGenerator:
    """
    Generate high-quality PNG tiles from Karnataka Bengaluru highways GeoJSON
    """

    def __init__(self, data_dir: str = "data/karnataka/bengaluru/highways",
                 output_dir: str = "karnataka_bengaluru_highways_tiles"):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Color specification
        self.highway_color = (20, 224, 152)  # #14e098

        logger.info("Karnataka Bengaluru Highways Tile Generator initialized")

    def load_geojson_highways(self):
        """Load and parse the GeoJSON highways"""
        geojson_files = list(self.data_dir.glob("*.geojson"))
        if not geojson_files:
            logger.error(f"No GeoJSON files found in {self.data_dir}")
            return None

        all_features = []
        bounds = None

        for geojson_path in geojson_files:
            logger.info(f"Loading {geojson_path}")
            
            with open(geojson_path, 'r') as f:
                geojson_data = json.load(f)

            # Extract features
            features = geojson_data.get('features', [])
            if not features:
                logger.warning(f"No features found in {geojson_path}")
                continue

            all_features.extend(features)
            logger.info(f"Loaded {len(features)} features from {geojson_path}")

        if not all_features:
            logger.error("No features found in any GeoJSON files")
            return None

        # Calculate overall bounds
        min_lon, min_lat, max_lon, max_lat = float('inf'), float('inf'), float('-inf'), float('-inf')
        
        for feature in all_features:
            geometry = feature['geometry']
            if geometry['type'] in ['LineString', 'MultiLineString']:
                shape_obj = shape(geometry)
                feature_bounds = shape_obj.bounds
                min_lon = min(min_lon, feature_bounds[0])
                min_lat = min(min_lat, feature_bounds[1])
                max_lon = max(max_lon, feature_bounds[2])
                max_lat = max(max_lat, feature_bounds[3])

        bounds = (min_lon, min_lat, max_lon, max_lat)
        logger.info(f"Overall bounds: {bounds}")
        logger.info(f"Total features loaded: {len(all_features)}")

        return all_features, bounds

    def generate_tiles(self, min_zoom=8, max_zoom=16):
        """Generate PNG tiles for Karnataka Bengaluru highways"""
        # Load GeoJSON highways
        features_data = self.load_geojson_highways()
        if features_data is None:
            logger.error("Failed to load GeoJSON highways")
            return

        all_features, bounds = features_data

        # Calculate tile bounds
        min_tile = mercantile.tile(bounds[0], bounds[1], min_zoom)
        max_tile = mercantile.tile(bounds[2], bounds[3], max_zoom)

        total_tiles = 0

        for zoom in range(min_zoom, max_zoom + 1):
            logger.info(f"Processing zoom level {zoom}")

            # Recalculate tile bounds for this zoom level
            min_tile = mercantile.tile(bounds[0], bounds[1], zoom)
            max_tile = mercantile.tile(bounds[2], bounds[3], zoom)

            zoom_dir = self.output_dir / str(zoom)
            zoom_dir.mkdir(exist_ok=True)

            for x in range(min_tile.x, max_tile.x + 1):
                x_dir = zoom_dir / str(x)
                x_dir.mkdir(exist_ok=True)

                for y in range(max_tile.y, min_tile.y + 1):
                    tile_path = x_dir / f"{y}.png"

                    if self.generate_single_tile(all_features, zoom, x, y, tile_path):
                        total_tiles += 1

                    # Log progress every 100 tiles
                    if total_tiles % 100 == 0:
                        logger.info(f"Generated {total_tiles} tiles so far...")

        logger.info(f"Generated {total_tiles} PNG tiles for Karnataka Bengaluru highways")

        # Create supporting files
        self.create_supporting_files(bounds, min_zoom, max_zoom)

        return total_tiles

    def generate_single_tile(self, all_features, zoom, x, y, tile_path):
        """Generate a single PNG tile"""
        try:
            # Get tile bounds
            tile_bounds = mercantile.bounds(x, y, zoom)

            # Create a blank tile
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Render the highways to this tile
            self.render_highways_to_tile(all_features, tile_bounds, draw)

            # Save the tile
            img.save(tile_path, 'PNG')
            return True

        except Exception as e:
            logger.error(f"Error generating tile {zoom}/{x}/{y}: {e}")
            return False

    def render_highways_to_tile(self, all_features, tile_bounds, draw):
        """Render highways to a tile"""
        try:
            # Convert tile coordinates to WGS84
            tile_width = tile_bounds.east - tile_bounds.west
            tile_height = tile_bounds.north - tile_bounds.south

            for feature in all_features:
                geometry = feature['geometry']
                
                if geometry['type'] == 'LineString':
                    self.draw_line_string(geometry['coordinates'], tile_bounds, tile_width, tile_height, draw)
                elif geometry['type'] == 'MultiLineString':
                    for line_string in geometry['coordinates']:
                        self.draw_line_string(line_string, tile_bounds, tile_width, tile_height, draw)

        except Exception as e:
            logger.error(f"Error rendering highways to tile: {e}")

    def draw_line_string(self, coordinates, tile_bounds, tile_width, tile_height, draw):
        """Draw a LineString on the tile"""
        try:
            tile_coords = []
            
            for lon, lat in coordinates:
                # Check if point is within tile bounds
                if (tile_bounds.west <= lon <= tile_bounds.east and
                    tile_bounds.south <= lat <= tile_bounds.north):
                    
                    # Convert WGS84 coordinates to tile pixel coordinates
                    tile_x = int((lon - tile_bounds.west) / tile_width * 256)
                    tile_y = int((tile_bounds.north - lat) / tile_height * 256)
                    tile_coords.append((tile_x, tile_y))

            # Draw the line if we have at least 2 points
            if len(tile_coords) >= 2:
                draw.line(tile_coords, fill=self.highway_color, width=3)

        except Exception as e:
            logger.error(f"Error drawing LineString: {e}")

    def create_supporting_files(self, bounds, min_zoom, max_zoom):
        """Create supporting files for the tile set"""
        logger.info("Creating supporting files...")

        # Create Mapbox style JSON
        style_json = {
            "version": 8,
            "name": "Karnataka - Bengaluru Highways",
            "sources": {
                "karnataka-bengaluru-highways": {
                    "type": "raster",
                    "tiles": [
                        "https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/highways/{z}/{x}/{y}.png"
                    ],
                    "tileSize": 256
                }
            },
            "layers": [
                {
                    "id": "karnataka-bengaluru-highways-layer",
                    "type": "raster",
                    "source": "karnataka-bengaluru-highways",
                    "paint": {
                        "raster-opacity": 0.8
                    }
                }
            ]
        }

        with open(self.output_dir / "style.json", "w") as f:
            json.dump(style_json, f, indent=2)

        # Create TileJSON
        tilejson = {
            "tilejson": "2.2.0",
            "name": "Karnataka - Bengaluru Highways",
            "description": "Highways and major roads in Bengaluru, Karnataka",
            "version": "1.0.0",
            "attribution": "Karnataka Government",
            "template": "",
            "legend": "",
            "scheme": "xyz",
            "tiles": [
                "https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/highways/{z}/{x}/{y}.png"
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

        # Create HTML viewer
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Karnataka - Bengaluru Highways</title>
    <script src='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js'></script>
    <link href='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css' rel='stylesheet' />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
    </style>
</head>
<body>
    <div id='map'></div>
    <script>
        mapboxgl.accessToken = 'pk.eyJ1IjoiZXhhbXBsZSIsImEiOiJjbGV4YW1wbGUifQ.example';
        var map = new mapboxgl.Map({{
            container: 'map',
            style: {{
                "version": 8,
                "sources": {{
                    "karnataka-bengaluru-highways": {{
                        "type": "raster",
                        "tiles": [
                            "https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/highways/{{z}}/{{x}}/{{y}}.png"
                        ],
                        "tileSize": 256
                    }}
                }},
                "layers": [
                    {{
                        "id": "karnataka-bengaluru-highways-layer",
                        "type": "raster",
                        "source": "karnataka-bengaluru-highways",
                        "paint": {{
                            "raster-opacity": 0.8
                        }}
                    }}
                ]
            }},
            center: [{(bounds[0] + bounds[2]) / 2}, {(bounds[1] + bounds[3]) / 2}],
            zoom: 10
        }});
    </script>
</body>
</html>
"""

        with open(self.output_dir / "viewer.html", "w") as f:
            f.write(html_content)

        logger.info("Created supporting files: style.json, tilejson.json, viewer.html")

def main():
    """Main function"""
    logger.info("Starting Karnataka Bengaluru highways tile generation")

    # Initialize generator
    generator = KarnatakaBengaluruHighwaysTileGenerator()

    # Generate tiles with higher zoom levels for better quality
    generator.generate_tiles(min_zoom=8, max_zoom=16)

    logger.info("Karnataka Bengaluru highways tile generation completed!")

if __name__ == "__main__":
    main()
