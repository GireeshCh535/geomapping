#!/usr/bin/env python3
"""
Dedicated script to generate high-quality PNG tiles from Karnataka Bengaluru STRR GeoJSON
Creates tiles with specified color: #14e098
- Mapbox-safe blank/transparent tiles (prevents overzoom artifacts)
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

class KarnatakaBengaluruSTRRTileGenerator:
    """
    Generate high-quality PNG tiles from Karnataka Bengaluru STRR GeoJSON
    """

    def __init__(self, data_dir: str = "data/karnataka/bengaluru/strr",
                 output_dir: str = "karnataka_bengaluru_strr_tiles"):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Color specification
        self.strr_color = (20, 224, 152)  # #14e098

        logger.info("Karnataka Bengaluru STRR Tile Generator initialized")
        logger.info("Mapbox-safe blank/transparent tiles enabled")

    def load_geojson_strr(self):
        """Load and parse the GeoJSON STRR"""
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
    
    def create_blank_tile(self) -> Image.Image:
        """Create a fully transparent PNG tile (Mapbox-safe empty tile)"""
        return Image.new('RGBA', (256, 256), (0, 0, 0, 0))

    def generate_tiles(self, min_zoom=8, max_zoom=16):
        """Generate PNG tiles for Karnataka Bengaluru STRR"""
        # Load GeoJSON STRR
        features_data = self.load_geojson_strr()
        if features_data is None:
            logger.error("Failed to load GeoJSON STRR")
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

        logger.info(f"Generated {total_tiles} PNG tiles for Karnataka Bengaluru STRR")

        # Create supporting files
        self.create_supporting_files(bounds, min_zoom, max_zoom)

        return total_tiles

    def generate_single_tile(self, all_features, zoom, x, y, tile_path):
        """Generate a single PNG tile - simple and reliable approach"""
        try:
            # Get tile bounds
            tile_bounds = mercantile.bounds(x, y, zoom)
            
            # Create a shapely box for the tile bounds
            from shapely.geometry import box
            tile_box = box(tile_bounds.west, tile_bounds.south, tile_bounds.east, tile_bounds.north)
            
            # Check if any features intersect with this tile
            has_content = False
            intersecting_features = []
            
            for feature in all_features:
                geometry = feature['geometry']
                if geometry['type'] in ['LineString', 'MultiLineString']:
                    shape_obj = shape(geometry)
                    # Use a small buffer to catch nearby lines
                    buffered_shape = shape_obj.buffer(0.002)  # ~200m buffer - much smaller
                    if tile_box.intersects(buffered_shape):
                        has_content = True
                        intersecting_features.append(feature)
            
            # Create a blank tile (always create, even if empty)
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            
            if has_content:
                draw = ImageDraw.Draw(img)
                # Use simple rendering approach with all features for continuity
                self.render_strr_to_tile_simple(all_features, tile_bounds, draw)

            # Always save the tile image. If there's no content, this will be a fully transparent PNG.
            img.save(tile_path, 'PNG')
            return True

        except Exception as e:
            logger.error(f"Error generating tile {zoom}/{x}/{y}: {e}")
            
            # Create and save blank tile on error
            try:
                blank_img = self.create_blank_tile()
                blank_img.save(tile_path, 'PNG')
                return True
            except:
                return False

    def render_strr_to_tile_enhanced(self, features, tile_bounds, draw):
        """Render STRR to a tile with enhanced continuous line rendering and gap filling"""
        try:
            # Convert tile coordinates to WGS84
            tile_width = tile_bounds.east - tile_bounds.west
            tile_height = tile_bounds.north - tile_bounds.south

            # Collect all coordinate points from all features
            all_coordinates = []
            
            for feature in features:
                geometry = feature['geometry']
                
                if geometry['type'] == 'LineString':
                    all_coordinates.extend(geometry['coordinates'])
                elif geometry['type'] == 'MultiLineString':
                    for line_string in geometry['coordinates']:
                        all_coordinates.extend(line_string)

            if not all_coordinates:
                return

            # Convert all coordinates to pixel positions
            pixel_points = []
            for coord in all_coordinates:
                # Handle both 2D and 3D coordinates
                lon, lat = coord[0], coord[1]
                tile_x = int((lon - tile_bounds.west) / tile_width * 256)
                tile_y = int((tile_bounds.north - lat) / tile_height * 256)
                
                # Extend bounds slightly to ensure continuity
                tile_x = max(-20, min(276, tile_x))
                tile_y = max(-20, min(276, tile_y))
                
                pixel_points.append((tile_x, tile_y))

            # Remove duplicate points and sort by proximity to create continuous segments
            unique_points = list(set(pixel_points))
            
            if len(unique_points) < 2:
                return

            # Create continuous path by connecting nearby points
            connected_segments = self.create_continuous_path(unique_points)

            # Draw the connected segments with thick lines
            for segment in connected_segments:
                if len(segment) >= 2:
                    # Draw multiple passes for thickness
                    for thickness in range(6):  # Even thicker for better visibility
                        for i in range(len(segment) - 1):
                            start = (segment[i][0] + thickness - 3, segment[i][1])
                            end = (segment[i + 1][0] + thickness - 3, segment[i + 1][1])
                            
                            # Draw the line segment
                            draw.line([start, end], fill=self.strr_color, width=2)
                            
                            # Also draw vertical thickness
                            start_v = (segment[i][0], segment[i][1] + thickness - 3)
                            end_v = (segment[i + 1][0], segment[i + 1][1] + thickness - 3)
                            draw.line([start_v, end_v], fill=self.strr_color, width=2)

        except Exception as e:
            logger.error(f"Error rendering STRR to tile: {e}")

    def create_continuous_path(self, points):
        """Create continuous path segments from disconnected points"""
        if len(points) < 2:
            return []
        
        # Sort points to create a more logical connection order
        # Start from leftmost point and connect to nearest unvisited points
        remaining_points = points.copy()
        segments = []
        
        while len(remaining_points) > 1:
            # Start a new segment
            current_segment = [remaining_points.pop(0)]
            
            # Connect to nearest points within reasonable distance
            while remaining_points:
                current_point = current_segment[-1]
                nearest_point = None
                nearest_distance = float('inf')
                
                for point in remaining_points:
                    distance = ((point[0] - current_point[0]) ** 2 + (point[1] - current_point[1]) ** 2) ** 0.5
                    if distance < nearest_distance and distance < 100:  # Max connection distance
                        nearest_distance = distance
                        nearest_point = point
                
                if nearest_point:
                    current_segment.append(nearest_point)
                    remaining_points.remove(nearest_point)
                else:
                    break
            
            if len(current_segment) >= 2:
                segments.append(current_segment)
        
        return segments

    def render_strr_to_tile_simple(self, all_features, tile_bounds, draw):
        """Simple and reliable STRR rendering with segment connection"""
        try:
            # Convert tile coordinates to WGS84
            tile_width = tile_bounds.east - tile_bounds.west
            tile_height = tile_bounds.north - tile_bounds.south

            # First, collect all line segments and try to connect them
            all_segments = []
            for feature in all_features:
                geometry = feature['geometry']
                
                if geometry['type'] == 'LineString':
                    all_segments.append(geometry['coordinates'])
                elif geometry['type'] == 'MultiLineString':
                    for line_string in geometry['coordinates']:
                        if len(line_string) >= 2:  # Only process valid segments
                            all_segments.append(line_string)

            # Draw all segments with connection attempts
            for segment in all_segments:
                self.draw_line_string_simple(segment, tile_bounds, tile_width, tile_height, draw)
                
            # Draw connection lines between nearby segment endpoints
            self.draw_segment_connections(all_segments, tile_bounds, tile_width, tile_height, draw)

        except Exception as e:
            logger.error(f"Error rendering STRR to tile: {e}")
            
    def draw_segment_connections(self, all_segments, tile_bounds, tile_width, tile_height, draw):
        """Draw connecting lines between nearby segment endpoints to fill gaps"""
        try:
            # Collect all endpoints
            endpoints = []
            for segment in all_segments:
                if len(segment) >= 2:
                    endpoints.append(('start', segment[0]))
                    endpoints.append(('end', segment[-1]))
            
            # Find and connect nearby endpoints (within 0.01 degrees ~ 1.1km)
            connection_threshold = 0.01
            connected_pairs = set()
            
            for i, (type1, point1) in enumerate(endpoints):
                for j, (type2, point2) in enumerate(endpoints[i+1:], i+1):
                    # Calculate distance
                    dx = point2[0] - point1[0]
                    dy = point2[1] - point1[1]
                    distance = (dx*dx + dy*dy)**0.5
                    
                    # If points are close enough and not already connected
                    if distance < connection_threshold and (i,j) not in connected_pairs:
                        # Draw connecting line
                        self.draw_line_string_simple([point1, point2], tile_bounds, tile_width, tile_height, draw)
                        connected_pairs.add((i,j))
                        
        except Exception as e:
            logger.error(f"Error drawing segment connections: {e}")

    def draw_line_string_simple(self, coordinates, tile_bounds, tile_width, tile_height, draw):
        """Draw a line string with thick, continuous lines"""
        try:
            # Convert coordinates to pixel positions
            pixel_coords = []
            for coord in coordinates:
                # Handle both 2D and 3D coordinates
                lon, lat = coord[0], coord[1]
                # Convert WGS84 coordinates to tile pixel coordinates
                tile_x = int((lon - tile_bounds.west) / tile_width * 256)
                tile_y = int((tile_bounds.north - lat) / tile_height * 256)
                pixel_coords.append((tile_x, tile_y))
            
            if len(pixel_coords) < 2:
                return

            # Draw thick lines with multiple passes
            for thickness in range(8):  # 8-pixel thick lines
                offset_x = thickness - 4
                offset_y = thickness - 4
                
                adjusted_coords = [(x + offset_x, y + offset_y) for x, y in pixel_coords]
                
                # Draw the line segments
                for i in range(len(adjusted_coords) - 1):
                    start = adjusted_coords[i]
                    end = adjusted_coords[i + 1]
                    draw.line([start, end], fill=self.strr_color, width=3)

        except Exception as e:
            logger.error(f"Error drawing line string: {e}")

    def process_line_string(self, coordinates, tile_bounds, tile_width, tile_height):
        """Process a line string and return pixel coordinates"""
        try:
            # Convert coordinates to pixel positions
            pixel_coords = []
            for coord in coordinates:
                # Handle both 2D and 3D coordinates
                lon, lat = coord[0], coord[1]
                # Convert WGS84 coordinates to tile pixel coordinates
                tile_x = int((lon - tile_bounds.west) / tile_width * 256)
                tile_y = int((tile_bounds.north - lat) / tile_height * 256)
                
                # Clamp coordinates to tile bounds with some buffer
                tile_x = max(-10, min(266, tile_x))
                tile_y = max(-10, min(266, tile_y))
                
                pixel_coords.append((tile_x, tile_y))
            
            return [pixel_coords] if len(pixel_coords) >= 2 else []

        except Exception as e:
            logger.error(f"Error processing line string: {e}")
            return []

    def wgs84_to_tile_pixel(self, lon, lat, tile_x, tile_y, zoom):
        """Convert WGS84 coordinates to tile pixel coordinates"""
        # Clamp latitude to valid range
        lat = max(-85.051129, min(85.051129, lat))
        
        # Convert to tile coordinates
        tile_lon = (lon + 180) / 360 * (2 ** zoom)
        tile_lat = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * (2 ** zoom)
        
        # Convert to pixel coordinates within the tile
        pixel_x = int((tile_lon - tile_x) * 256)
        pixel_y = int((tile_lat - tile_y) * 256)
        
        return pixel_x, pixel_y

    def clip_line_to_tile(self, coordinates, tile_bounds):
        """Clip a line to tile bounds using Cohen-Sutherland algorithm"""
        if len(coordinates) < 2:
            return []
        
        clipped_coords = []
        
        for i in range(len(coordinates) - 1):
            start = coordinates[i]
            end = coordinates[i + 1]
            
            # Clip the line segment to tile bounds
            clipped_segment = self.clip_line_segment(start, end, tile_bounds)
            if clipped_segment:
                clipped_coords.extend(clipped_segment)
        
        return clipped_coords

    def clip_line_segment(self, start, end, tile_bounds):
        """Clip a line segment to tile bounds"""
        x1, y1 = start
        x2, y2 = end
        
        # Check if both points are outside the same side of the tile
        if ((x1 < tile_bounds.west and x2 < tile_bounds.west) or
            (x1 > tile_bounds.east and x2 > tile_bounds.east) or
            (y1 < tile_bounds.south and y2 < tile_bounds.south) or
            (y1 > tile_bounds.north and y2 > tile_bounds.north)):
            return []
        
        # Simple clipping: if both points are within bounds, return both
        if (tile_bounds.west <= x1 <= tile_bounds.east and
            tile_bounds.south <= y1 <= tile_bounds.north and
            tile_bounds.west <= x2 <= tile_bounds.east and
            tile_bounds.south <= y2 <= tile_bounds.north):
            return [start, end]
        
        # If one point is outside, clip to tile boundary
        clipped_start = start
        clipped_end = end
        
        # Clip to west boundary
        if x1 < tile_bounds.west or x2 < tile_bounds.west:
            if x1 < tile_bounds.west:
                clipped_start = (tile_bounds.west, y1 + (y2 - y1) * (tile_bounds.west - x1) / (x2 - x1))
            if x2 < tile_bounds.west:
                clipped_end = (tile_bounds.west, y2 + (y1 - y2) * (tile_bounds.west - x2) / (x1 - x2))
        
        # Clip to east boundary
        if x1 > tile_bounds.east or x2 > tile_bounds.east:
            if x1 > tile_bounds.east:
                clipped_start = (tile_bounds.east, y1 + (y2 - y1) * (tile_bounds.east - x1) / (x2 - x1))
            if x2 > tile_bounds.east:
                clipped_end = (tile_bounds.east, y2 + (y1 - y2) * (tile_bounds.east - x2) / (x1 - x2))
        
        # Clip to south boundary
        if y1 < tile_bounds.south or y2 < tile_bounds.south:
            if y1 < tile_bounds.south:
                clipped_start = (x1 + (x2 - x1) * (tile_bounds.south - y1) / (y2 - y1), tile_bounds.south)
            if y2 < tile_bounds.south:
                clipped_end = (x2 + (x1 - x2) * (tile_bounds.south - y2) / (y1 - y2), tile_bounds.south)
        
        # Clip to north boundary
        if y1 > tile_bounds.north or y2 > tile_bounds.north:
            if y1 > tile_bounds.north:
                clipped_start = (x1 + (x2 - x1) * (tile_bounds.north - y1) / (y2 - y1), tile_bounds.north)
            if y2 > tile_bounds.north:
                clipped_end = (x2 + (x1 - x2) * (tile_bounds.north - y2) / (y1 - y2), tile_bounds.north)
        
        return [clipped_start, clipped_end]

    def draw_line_string(self, coordinates, tile_bounds, tile_width, tile_height, draw):
        """Draw a LineString on the tile with proper clipping"""
        try:
            # Clip the line to tile bounds
            clipped_coords = self.clip_line_to_tile(coordinates, tile_bounds)
            
            if len(clipped_coords) < 2:
                return
            
            # Convert coordinates to pixel positions
            pixel_coords = []
            for lon, lat in clipped_coords:
                # Convert WGS84 coordinates to tile pixel coordinates
                tile_x = int((lon - tile_bounds.west) / tile_width * 256)
                tile_y = int((tile_bounds.north - lat) / tile_height * 256)
                pixel_coords.append((tile_x, tile_y))
            
            # Draw the line segments
            for i in range(len(pixel_coords) - 1):
                start = pixel_coords[i]
                end = pixel_coords[i + 1]
                
                # Check if line segment is within tile bounds
                if (0 <= start[0] <= 256 and 0 <= start[1] <= 256 and
                    0 <= end[0] <= 256 and 0 <= end[1] <= 256):
                    draw.line([start, end], fill=self.strr_color, width=3)

        except Exception as e:
            logger.error(f"Error drawing LineString: {e}")

    def create_supporting_files(self, bounds, min_zoom, max_zoom):
        """Create supporting files for the tile set"""
        logger.info("Creating supporting files...")

        # Create Mapbox style JSON
        style_json = {
            "version": 8,
            "name": "Karnataka - Bengaluru STRR",
            "sources": {
                "karnataka-bengaluru-strr": {
                    "type": "raster",
                    "tiles": [
                        "https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/strr/{z}/{x}/{y}.png"
                    ],
                    "tileSize": 256
                }
            },
            "layers": [
                {
                    "id": "karnataka-bengaluru-strr-layer",
                    "type": "raster",
                    "source": "karnataka-bengaluru-strr",
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
            "name": "Karnataka - Bengaluru STRR",
            "description": "Satellite Town Ring Road (STRR) in Bengaluru, Karnataka",
            "version": "1.0.0",
            "attribution": "Karnataka Government",
            "template": "",
            "legend": "",
            "scheme": "xyz",
            "tiles": [
                "https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/strr/{z}/{x}/{y}.png"
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
    <title>Karnataka - Bengaluru STRR</title>
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
                    "karnataka-bengaluru-strr": {{
                        "type": "raster",
                        "tiles": [
                            "https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/strr/{{z}}/{{x}}/{{y}}.png"
                        ],
                        "tileSize": 256
                    }}
                }},
                "layers": [
                    {{
                        "id": "karnataka-bengaluru-strr-layer",
                        "type": "raster",
                        "source": "karnataka-bengaluru-strr",
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
    logger.info("Starting Karnataka Bengaluru STRR tile generation")

    # Initialize generator
    generator = KarnatakaBengaluruSTRRTileGenerator()

    # Generate tiles with appropriate zoom levels
    generator.generate_tiles(min_zoom=4, max_zoom=18)

    logger.info("Karnataka Bengaluru STRR tile generation completed!")

if __name__ == "__main__":
    main()