#!/usr/bin/env python3
"""
Dedicated script to generate high-quality PNG tiles from Future City Hyderabad GeoJSON boundary
Creates tiles with specified colors: Border #C3C3C3, Background #7D7D7D (50% opacity)
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
from shapely.geometry import shape, Polygon, MultiPolygon, Point
from shapely.ops import transform
import pyproj
from functools import partial

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FutureCityHyderabadBoundaryTileGenerator:
    """
    Generate high-quality PNG tiles from Future City Hyderabad GeoJSON boundary
    """
    
    def __init__(self, data_dir: str = "data/Telangana/Hyderabad/future-city",
                 output_dir: str = "hyderabad_future_city_boundary_tiles"):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Color specifications
        self.border_color = (195, 195, 195)  # #C3C3C3
        self.background_color = (125, 125, 125, 128)  # #7D7D7D with 50% opacity (128/255)
        
        logger.info("Future City Hyderabad Boundary Tile Generator initialized")
    
    def load_geojson_boundary(self):
        """Load and parse the GeoJSON boundary"""
        geojson_path = self.data_dir / "FCDA Boundary.geojson"
        
        with open(geojson_path, 'r') as f:
            geojson_data = json.load(f)
        
        # Extract the boundary geometry
        features = geojson_data.get('features', [])
        if not features:
            logger.error("No features found in GeoJSON")
            return None
        
        # Get the first feature's geometry
        geometry = features[0]['geometry']
        boundary_shape = shape(geometry)
        
        logger.info(f"Loaded GeoJSON boundary with {len(features)} features")
        logger.info(f"Boundary type: {type(boundary_shape)}")
        
        # Get bounds
        bounds = boundary_shape.bounds
        logger.info(f"Boundary bounds: {bounds}")
        
        return boundary_shape, bounds
    
    def generate_tiles(self, min_zoom=8, max_zoom=16):
        """Generate PNG tiles for Future City Hyderabad boundary"""
        # Load GeoJSON boundary
        boundary_shape, bounds = self.load_geojson_boundary()
        if boundary_shape is None:
            logger.error("Failed to load GeoJSON boundary")
            return
        
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
                    
                    if self.generate_single_tile(boundary_shape, zoom, x, y, tile_path):
                        total_tiles += 1
                    
                    # Log progress every 100 tiles
                    if total_tiles % 100 == 0:
                        logger.info(f"Generated {total_tiles} tiles so far...")
        
        logger.info(f"Generated {total_tiles} PNG tiles for Future City Hyderabad boundary")
        
        # Create supporting files
        self.create_supporting_files(bounds, min_zoom, max_zoom)
        
        return total_tiles
    
    def generate_single_tile(self, boundary_shape, zoom, x, y, tile_path):
        """Generate a single PNG tile"""
        try:
            # Get tile bounds
            tile_bounds = mercantile.bounds(x, y, zoom)
            
            # Create a blank tile
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Render the boundary to this tile
            self.render_boundary_to_tile(boundary_shape, tile_bounds, draw)
            
            # Save the tile
            img.save(tile_path, 'PNG')
            return True
            
        except Exception as e:
            logger.error(f"Error generating tile {zoom}/{x}/{y}: {e}")
            return False
    
    def render_boundary_to_tile(self, boundary_shape, tile_bounds, draw):
        """Render boundary to a tile"""
        try:
            # Convert boundary coordinates to tile coordinates
            tile_width = tile_bounds.east - tile_bounds.west
            tile_height = tile_bounds.north - tile_bounds.south
            
            # Sample points in the tile to fill the boundary
            for tile_y in range(0, 256, 1):
                for tile_x in range(0, 256, 1):
                    # Convert tile pixel to WGS84 coordinates
                    lon = tile_bounds.west + (tile_bounds.east - tile_bounds.west) * tile_x / 256
                    lat = tile_bounds.north - (tile_bounds.north - tile_bounds.south) * tile_y / 256
                    
                    # Check if point is within boundary
                    point = Point(lon, lat)
                    is_within_boundary = boundary_shape.contains(point)
                    
                    if is_within_boundary:
                        # Draw background color with 50% opacity
                        draw.point((tile_x, tile_y), fill=self.background_color)
            
            # Draw boundary outline
            self.draw_boundary_outline(boundary_shape, tile_bounds, draw)
        
        except Exception as e:
            logger.error(f"Error rendering boundary to tile: {e}")
    
    def draw_boundary_outline(self, boundary_shape, tile_bounds, draw):
        """Draw the boundary outline on the tile"""
        try:
            # Convert boundary coordinates to tile coordinates
            tile_width = tile_bounds.east - tile_bounds.west
            tile_height = tile_bounds.north - tile_bounds.south
            
            if hasattr(boundary_shape, 'exterior'):
                # Single polygon
                coords = list(boundary_shape.exterior.coords)
                tile_coords = []
                for lon, lat in coords:
                    if (tile_bounds.west <= lon <= tile_bounds.east and 
                        tile_bounds.south <= lat <= tile_bounds.north):
                        tile_x = int((lon - tile_bounds.west) / tile_width * 256)
                        tile_y = int((tile_bounds.north - lat) / tile_height * 256)
                        tile_coords.append((tile_x, tile_y))
                
                if len(tile_coords) > 2:
                    draw.line(tile_coords, fill=self.border_color, width=2)
            
            elif hasattr(boundary_shape, 'geoms'):
                # MultiPolygon
                for geom in boundary_shape.geoms:
                    if hasattr(geom, 'exterior'):
                        coords = list(geom.exterior.coords)
                        tile_coords = []
                        for lon, lat in coords:
                            if (tile_bounds.west <= lon <= tile_bounds.east and 
                                tile_bounds.south <= lat <= tile_bounds.north):
                                tile_x = int((lon - tile_bounds.west) / tile_width * 256)
                                tile_y = int((tile_bounds.north - lat) / tile_height * 256)
                                tile_coords.append((tile_x, tile_y))
                        
                        if len(tile_coords) > 2:
                            draw.line(tile_coords, fill=self.border_color, width=2)
        
        except Exception as e:
            logger.error(f"Error drawing boundary outline: {e}")
    
    def create_supporting_files(self, bounds, min_zoom, max_zoom):
        """Create supporting files for the tile set"""
        logger.info("Creating supporting files...")
        
        # Create Mapbox style JSON
        style_json = {
            "version": 8,
            "name": "Telangana - Future City Hyderabad (Boundary)",
            "sources": {
                "future-city-hyderabad-boundary": {
                    "type": "raster",
                    "tiles": [
                        "https://d17yosovmfjm4.cloudfront.net/telangana/hyderabad/future_city_boundary/{z}/{x}/{y}.png"
                    ],
                    "tileSize": 256
                }
            },
            "layers": [
                {
                    "id": "future-city-hyderabad-boundary-layer",
                    "type": "raster",
                    "source": "future-city-hyderabad-boundary",
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
            "name": "Telangana - Future City Hyderabad (Boundary)",
            "description": "Future City Development Authority (FCDA) boundary tiles for Hyderabad",
            "version": "1.0.0",
            "attribution": "FCDA",
            "template": "",
            "legend": "",
            "scheme": "xyz",
            "tiles": [
                "https://d17yosovmfjm4.cloudfront.net/telangana/hyderabad/future_city_boundary/{z}/{x}/{y}.png"
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
    <title>Telangana - Future City Hyderabad (Boundary)</title>
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
                    "future-city-hyderabad-boundary": {{
                        "type": "raster",
                        "tiles": [
                            "https://d17yosovmfjm4.cloudfront.net/telangana/hyderabad/future_city_boundary/{{z}}/{{x}}/{{y}}.png"
                        ],
                        "tileSize": 256
                    }}
                }},
                "layers": [
                    {{
                        "id": "future-city-hyderabad-boundary-layer",
                        "type": "raster",
                        "source": "future-city-hyderabad-boundary",
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
    logger.info("Starting Future City Hyderabad boundary tile generation")
    
    # Initialize generator
    generator = FutureCityHyderabadBoundaryTileGenerator()
    
    # Generate tiles with higher zoom levels for better quality
    generator.generate_tiles(min_zoom=8, max_zoom=16)
    
    logger.info("Future City Hyderabad boundary tile generation completed!")

if __name__ == "__main__":
    main()
