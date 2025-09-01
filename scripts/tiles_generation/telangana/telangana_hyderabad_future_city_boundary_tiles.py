#!/usr/bin/env python3
"""
Enhanced script to generate high-quality PNG tiles from Future City Hyderabad GeoJSON boundary
Creates tiles with specified colors: Border #C3C3C3, Background #7D7D7D (50% opacity)
Features: Perfect edge handling, data validation, efficient rendering, anti-aliasing
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
from shapely.geometry import shape, Polygon, MultiPolygon, Point, LineString
from shapely.ops import transform, unary_union
import pyproj
from functools import partial
import time

# Configure enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class EnhancedFutureCityHyderabadBoundaryTileGenerator:
    """
    Generate high-quality PNG tiles from Future City Hyderabad GeoJSON boundary
    with perfect edge handling and data validation
    """
    
    def __init__(self, data_dir: str = "data/Telangana/Hyderabad/future-city",
                 output_dir: str = "hyderabad_future_city_boundary_tiles"):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Color specifications
        self.border_color = (195, 195, 195)  # #C3C3C3
        self.background_color = (125, 125, 125, 128)  # #7D7D7D with 50% opacity
        
        # Performance settings
        self.sample_density = 4  # Higher density for better quality
        self.buffer_distance = 0.001  # Buffer for edge handling
        
        logger.info("🚀 Enhanced Future City Hyderabad Boundary Tile Generator initialized")
        logger.info(f"📂 Data directory: {self.data_dir}")
        logger.info(f"📁 Output directory: {self.output_dir}")
    
    def load_geojson_boundary(self):
        """Load and parse the GeoJSON boundary with validation"""
        geojson_path = self.data_dir / "FCDA Boundary.geojson"
        
        if not geojson_path.exists():
            logger.error(f"❌ GeoJSON file not found: {geojson_path}")
            return None, None
        
        try:
            with open(geojson_path, 'r') as f:
                geojson_data = json.load(f)
            
            # Extract and validate features
            features = geojson_data.get('features', [])
            if not features:
                logger.error("❌ No features found in GeoJSON")
                return None, None
            
            # Process all features and union them
            geometries = []
            for i, feature in enumerate(features):
                try:
                    geometry = shape(feature['geometry'])
                    if geometry.is_valid:
                        geometries.append(geometry)
                    else:
                        logger.warning(f"⚠️  Invalid geometry in feature {i}, attempting to fix...")
                        geometry = geometry.buffer(0)  # Try to fix self-intersections
                        if geometry.is_valid:
                            geometries.append(geometry)
                        else:
                            logger.error(f"❌ Could not fix invalid geometry in feature {i}")
                except Exception as e:
                    logger.error(f"❌ Error processing feature {i}: {e}")
            
            if not geometries:
                logger.error("❌ No valid geometries found")
                return None, None
            
            # Union all geometries
            if len(geometries) == 1:
                boundary_shape = geometries[0]
            else:
                boundary_shape = unary_union(geometries)
            
            # Ensure the shape is valid
            if not boundary_shape.is_valid:
                logger.warning("⚠️  Union result is invalid, attempting to fix...")
                boundary_shape = boundary_shape.buffer(0)
            
            # Get bounds with buffer for edge handling
            bounds = boundary_shape.bounds
            buffered_bounds = (
                bounds[0] - self.buffer_distance,
                bounds[1] - self.buffer_distance,
                bounds[2] + self.buffer_distance,
                bounds[3] + self.buffer_distance
            )
            
            logger.info(f"✅ Loaded GeoJSON boundary with {len(features)} features")
            logger.info(f"📊 Boundary type: {type(boundary_shape)}")
            logger.info(f"📍 Original bounds: {bounds}")
            logger.info(f"📍 Buffered bounds: {buffered_bounds}")
            logger.info(f"🔍 Shape is valid: {boundary_shape.is_valid}")
            logger.info(f"📏 Shape area: {boundary_shape.area:.6f}")
            
            return boundary_shape, buffered_bounds
            
        except Exception as e:
            logger.error(f"❌ Error loading GeoJSON: {e}")
            return None, None
    
    def generate_tiles(self, min_zoom=8, max_zoom=16):
        """Generate PNG tiles for Future City Hyderabad boundary with validation"""
        # Load GeoJSON boundary
        boundary_shape, bounds = self.load_geojson_boundary()
        if boundary_shape is None:
            logger.error("❌ Failed to load GeoJSON boundary")
            return 0
        
        total_tiles = 0
        tiles_with_data = 0
        start_time = time.time()
        
        for zoom in range(min_zoom, max_zoom + 1):
            logger.info(f"🔄 Processing zoom level {zoom}")
            zoom_start_time = time.time()
            
            # Calculate tile bounds for this zoom level
            min_tile = mercantile.tile(bounds[0], bounds[1], zoom)
            max_tile = mercantile.tile(bounds[2], bounds[3], zoom)
            
            zoom_dir = self.output_dir / str(zoom)
            zoom_dir.mkdir(exist_ok=True)
            
            zoom_tiles = 0
            zoom_tiles_with_data = 0
            
            for x in range(min_tile.x, max_tile.x + 1):
                x_dir = zoom_dir / str(x)
                x_dir.mkdir(exist_ok=True)
                
                for y in range(max_tile.y, min_tile.y + 1):
                    tile_path = x_dir / f"{y}.png"
                    
                    # Generate tile with validation
                    tile_has_data = self.generate_single_tile_enhanced(
                        boundary_shape, zoom, x, y, tile_path
                    )
                    
                    if tile_has_data:
                        tiles_with_data += 1
                        zoom_tiles_with_data += 1
                    
                    total_tiles += 1
                    zoom_tiles += 1
                    
                    # Log progress every 1000 tiles
                    if total_tiles % 1000 == 0:
                        elapsed = time.time() - start_time
                        rate = total_tiles / elapsed if elapsed > 0 else 0
                        logger.info(f"📊 Progress: {total_tiles:,} tiles, {tiles_with_data:,} with data, {rate:.1f} tiles/sec")
            
            zoom_elapsed = time.time() - zoom_start_time
            logger.info(f"✅ Zoom {zoom}: {zoom_tiles:,} tiles, {zoom_tiles_with_data:,} with data, {zoom_elapsed:.1f}s")
        
        total_elapsed = time.time() - start_time
        logger.info(f"🎉 Generated {total_tiles:,} total tiles, {tiles_with_data:,} with data")
        logger.info(f"⏱️  Total time: {total_elapsed:.1f}s, Average rate: {total_tiles/total_elapsed:.1f} tiles/sec")
        
        # Create supporting files
        self.create_supporting_files(bounds, min_zoom, max_zoom)
        
        return tiles_with_data
    
    def generate_single_tile_enhanced(self, boundary_shape, zoom, x, y, tile_path):
        """Generate a single PNG tile with enhanced validation and rendering"""
        try:
            # Get tile bounds
            tile_bounds = mercantile.bounds(x, y, zoom)
            
            # Check if tile intersects with boundary
            tile_polygon = Polygon([
                (tile_bounds.west, tile_bounds.south),
                (tile_bounds.east, tile_bounds.south),
                (tile_bounds.east, tile_bounds.north),
                (tile_bounds.west, tile_bounds.north),
                (tile_bounds.west, tile_bounds.south)
            ])
            
            if not boundary_shape.intersects(tile_polygon):
                # Tile has no data, don't create it
                return False
            
            # Create a blank tile with transparency
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Render the boundary to this tile
            tile_has_data = self.render_boundary_to_tile_enhanced(
                boundary_shape, tile_bounds, draw
            )
            
            if tile_has_data:
                # Apply anti-aliasing for smoother edges
                img = img.filter(ImageFilter.SMOOTH_MORE)
                
                # Save the tile
                img.save(tile_path, 'PNG', optimize=True)
                return True
            else:
                # Tile has no visible data, don't save it
                return False
            
        except Exception as e:
            logger.error(f"❌ Error generating tile {zoom}/{x}/{y}: {e}")
            return False
    
    def render_boundary_to_tile_enhanced(self, boundary_shape, tile_bounds, draw):
        """Enhanced rendering with proper clipping and efficient sampling"""
        try:
            # Create tile polygon for clipping
            tile_polygon = Polygon([
                (tile_bounds.west, tile_bounds.south),
                (tile_bounds.east, tile_bounds.south),
                (tile_bounds.east, tile_bounds.north),
                (tile_bounds.west, tile_bounds.north),
                (tile_bounds.west, tile_bounds.south)
            ])
            
            # Clip boundary to tile bounds
            clipped_boundary = boundary_shape.intersection(tile_polygon)
            
            if clipped_boundary.is_empty:
                return False
            
            # Efficient sampling with higher density
            tile_width = tile_bounds.east - tile_bounds.west
            tile_height = tile_bounds.north - tile_bounds.south
            
            # Sample points efficiently
            for tile_y in range(0, 256, self.sample_density):
                for tile_x in range(0, 256, self.sample_density):
                    # Convert tile pixel to WGS84 coordinates
                    lon = tile_bounds.west + (tile_width * tile_x / 256)
                    lat = tile_bounds.north - (tile_height * tile_y / 256)
                    
                    # Check if point is within clipped boundary
                    point = Point(lon, lat)
                    if clipped_boundary.contains(point):
                        # Fill a block of pixels for efficiency
                        for dy in range(self.sample_density):
                            for dx in range(self.sample_density):
                                px, py = tile_x + dx, tile_y + dy
                                if 0 <= px < 256 and 0 <= py < 256:
                                    draw.point((px, py), fill=self.background_color)
            
            # Draw boundary outline with anti-aliasing
            self.draw_boundary_outline_enhanced(clipped_boundary, tile_bounds, draw)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error rendering boundary to tile: {e}")
            return False
    
    def draw_boundary_outline_enhanced(self, clipped_boundary, tile_bounds, draw):
        """Enhanced boundary outline drawing with proper coordinate transformation"""
        try:
            tile_width = tile_bounds.east - tile_bounds.west
            tile_height = tile_bounds.north - tile_bounds.south
            
            def coord_to_pixel(lon, lat):
                """Convert WGS84 coordinates to tile pixel coordinates"""
                if (tile_bounds.west <= lon <= tile_bounds.east and 
                    tile_bounds.south <= lat <= tile_bounds.north):
                    tile_x = int((lon - tile_bounds.west) / tile_width * 256)
                    tile_y = int((tile_bounds.north - lat) / tile_height * 256)
                    return (tile_x, tile_y)
                return None
            
            # Handle different geometry types
            if hasattr(clipped_boundary, 'exterior'):
                # Single polygon
                coords = list(clipped_boundary.exterior.coords)
                tile_coords = []
                for lon, lat in coords:
                    pixel = coord_to_pixel(lon, lat)
                    if pixel:
                        tile_coords.append(pixel)
                
                if len(tile_coords) > 2:
                    # Draw with anti-aliasing
                    draw.line(tile_coords, fill=self.border_color, width=3)
                    
                    # Draw inner lines for better visibility
                    if len(tile_coords) > 4:
                        draw.line(tile_coords, fill=self.border_color, width=1)
            
            elif hasattr(clipped_boundary, 'geoms'):
                # MultiPolygon
                for geom in clipped_boundary.geoms:
                    if hasattr(geom, 'exterior'):
                        coords = list(geom.exterior.coords)
                        tile_coords = []
                        for lon, lat in coords:
                            pixel = coord_to_pixel(lon, lat)
                            if pixel:
                                tile_coords.append(pixel)
                        
                        if len(tile_coords) > 2:
                            draw.line(tile_coords, fill=self.border_color, width=3)
                            if len(tile_coords) > 4:
                                draw.line(tile_coords, fill=self.border_color, width=1)
            
            elif hasattr(clipped_boundary, 'coords'):
                # LineString or other linear geometry
                coords = list(clipped_boundary.coords)
                tile_coords = []
                for lon, lat in coords:
                    pixel = coord_to_pixel(lon, lat)
                    if pixel:
                        tile_coords.append(pixel)
                
                if len(tile_coords) > 1:
                    draw.line(tile_coords, fill=self.border_color, width=3)
        
        except Exception as e:
            logger.error(f"❌ Error drawing boundary outline: {e}")
    
    def create_supporting_files(self, bounds, min_zoom, max_zoom):
        """Create supporting files for the tile set"""
        logger.info("📝 Creating supporting files...")
        
        # Create Mapbox style JSON
        style_json = {
            "version": 8,
            "name": "Telangana - Future City Hyderabad (Boundary)",
            "sources": {
                "future-city-hyderabad-boundary": {
                    "type": "raster",
                    "tiles": [
                        "https://d17yosovmfjm4.cloudfront.net/telangana/hyderabad/hyderabad_future_city/{z}/{x}/{y}.png"
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
                "https://d17yosovmfjm4.cloudfront.net/telangana/hyderabad/hyderabad_future_city/{z}/{x}/{y}.png"
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
                            "https://d17yosovmfjm4.cloudfront.net/telangana/hyderabad/hyderabad_future_city/{{z}}/{{x}}/{{y}}.png"
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
        
        logger.info("✅ Created supporting files: style.json, tilejson.json, viewer.html")

def main():
    """Main function"""
    logger.info("🚀 Starting Enhanced Future City Hyderabad boundary tile generation")
    
    # Initialize generator
    generator = EnhancedFutureCityHyderabadBoundaryTileGenerator()
    
    # Generate tiles with proper zoom levels
    total_tiles = generator.generate_tiles(min_zoom=17, max_zoom=18)
    
    logger.info(f"🎉 Enhanced Future City Hyderabad boundary tile generation completed!")
    logger.info(f"📊 Total tiles with data: {total_tiles:,}")

if __name__ == "__main__":
    main()
