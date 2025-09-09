#!/usr/bin/env python3
"""
Bangalore Metro Tile Generator
Generates Mapbox-compatible PNG tiles for Bangalore Metro lines with color coding
"""

import os
import sys
import json
import math
from pathlib import Path
from typing import List, Tuple, Dict, Any
import mercantile
from PIL import Image, ImageDraw
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString
from shapely.ops import unary_union

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

class BangaloreMetroTileGenerator:
    def __init__(self):
        self.geojson_path = project_root / "data/karnataka/bengaluru/metro/Bangalore Metro Phases 1,2,2A&2B.geojson"
        self.output_dir = project_root / "karnataka_bengaluru_metro_tiles"
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Color mapping for metro lines
        self.color_mapping = {
            'Blue': '#0066CC',      # Phase 2B and Phase 2A
            'Purple': '#800080',    # Phase 2 and Phase 1 (Corridor 1)
            'Green': '#00AA00',     # Phase 1 and Phase 2 (Corridor 2)
            'Yellow': '#FFD700',    # Phase 2 (Corridor 3)
            'Pink': '#FF69B4'       # Phase 2 (Under Construction)
        }
        
        # Line width for different zoom levels
        self.line_widths = {
            10: 2,
            11: 3,
            12: 4,
            13: 5,
            14: 6,
            15: 8,
            16: 10
        }
        
        # Station marker sizes for different zoom levels
        self.station_sizes = {
            10: 3,
            11: 4,
            12: 5,
            13: 6,
            14: 8,
            15: 10,
            16: 12
        }
        
        # Load the GeoJSON data
        self.gdf = gpd.read_file(self.geojson_path)
        print(f"Loaded {len(self.gdf)} metro lines")
        
    def wgs84_to_tile_pixel(self, lon: float, lat: float, tile_x: int, tile_y: int, zoom: int) -> Tuple[int, int]:
        """Convert WGS84 coordinates to pixel coordinates within a tile"""
        # Clamp latitude to avoid math domain error
        lat = max(-85.051129, min(85.051129, lat))
        
        # Convert to tile coordinates
        tile_lon = (lon + 180) / 360 * (2 ** zoom)
        tile_lat = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * (2 ** zoom)
        
        # Convert to pixel coordinates within the tile
        pixel_x = int((tile_lon - tile_x) * 256)
        pixel_y = int((tile_lat - tile_y) * 256)
        
        return pixel_x, pixel_y
    
    def draw_line(self, draw: ImageDraw, coordinates: List[Tuple[float, float]], 
                  color: str, width: int, tile_x: int, tile_y: int, zoom: int):
        """Draw a line on the tile with proper clipping"""
        if len(coordinates) < 2:
            return
            
        # Convert coordinates to pixel positions
        pixel_coords = []
        for lon, lat in coordinates:
            pixel_x, pixel_y = self.wgs84_to_tile_pixel(lon, lat, tile_x, tile_y, zoom)
            pixel_coords.append((pixel_x, pixel_y))
        
        # Draw the line segments with proper clipping
        for i in range(len(pixel_coords) - 1):
            start = pixel_coords[i]
            end = pixel_coords[i + 1]
            
            # Clip line segment to tile bounds
            clipped_start, clipped_end = self.clip_line_to_tile(start, end)
            
            if clipped_start and clipped_end:
                draw.line([clipped_start, clipped_end], fill=color, width=width)
    
    def clip_line_to_tile(self, start: Tuple[int, int], end: Tuple[int, int]) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """Clip a line segment to tile bounds (0-256) using Cohen-Sutherland algorithm"""
        x1, y1 = start
        x2, y2 = end
        
        # Define region codes
        INSIDE = 0
        LEFT = 1
        RIGHT = 2
        BOTTOM = 4
        TOP = 8
        
        def compute_code(x, y):
            code = INSIDE
            if x < 0:
                code |= LEFT
            elif x > 256:
                code |= RIGHT
            if y < 0:
                code |= BOTTOM
            elif y > 256:
                code |= TOP
            return code
        
        code1 = compute_code(x1, y1)
        code2 = compute_code(x2, y2)
        
        while True:
            # If both endpoints are inside the tile
            if code1 == 0 and code2 == 0:
                return (x1, y1), (x2, y2)
            
            # If both endpoints are outside the same region
            if code1 & code2 != 0:
                return None, None
            
            # At least one endpoint is outside the tile
            code_out = code1 if code1 != 0 else code2
            
            # Find intersection point
            if code_out & TOP:
                x = x1 + (x2 - x1) * (256 - y1) / (y2 - y1)
                y = 256
            elif code_out & BOTTOM:
                x = x1 + (x2 - x1) * (0 - y1) / (y2 - y1)
                y = 0
            elif code_out & RIGHT:
                y = y1 + (y2 - y1) * (256 - x1) / (x2 - x1)
                x = 256
            elif code_out & LEFT:
                y = y1 + (y2 - y1) * (0 - x1) / (x2 - x1)
                x = 0
            
            # Replace point outside tile with intersection point
            if code_out == code1:
                x1, y1 = int(x), int(y)
                code1 = compute_code(x1, y1)
            else:
                x2, y2 = int(x), int(y)
                code2 = compute_code(x2, y2)
    
    def draw_station_marker(self, draw: ImageDraw, lon: float, lat: float, 
                           color: str, size: int, tile_x: int, tile_y: int, zoom: int):
        """Draw a station marker on the tile"""
        pixel_x, pixel_y = self.wgs84_to_tile_pixel(lon, lat, tile_x, tile_y, zoom)
        
        # Check if marker is within tile bounds
        if 0 <= pixel_x <= 256 and 0 <= pixel_y <= 256:
            # Draw a filled circle for the station
            bbox = [pixel_x - size, pixel_y - size, pixel_x + size, pixel_y + size]
            draw.ellipse(bbox, fill=color, outline='white', width=1)
    
    def generate_tile(self, x: int, y: int, zoom: int) -> Image.Image:
        """Generate a single tile"""
        # Create a transparent image
        img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Get tile bounds
        tile_bounds = mercantile.bounds(x, y, zoom)
        
        # Get line width and station size for this zoom level
        line_width = self.line_widths.get(zoom, 3)
        station_size = self.station_sizes.get(zoom, 5)
        
        # Create a shapely box for the tile bounds with slight buffer for better intersection
        from shapely.geometry import box
        buffer = 0.001  # Small buffer to ensure we catch lines that just touch the tile
        tile_box = box(
            tile_bounds.west - buffer, 
            tile_bounds.south - buffer, 
            tile_bounds.east + buffer, 
            tile_bounds.north + buffer
        )
        
        # Collect junction coordinates for station markers
        junction_coords = set()
        features_drawn = 0
        
        for idx, row in self.gdf.iterrows():
            geometry = row.geometry
            
            # Check if geometry intersects with tile bounds
            if geometry.intersects(tile_box):
                # Get color for this line
                line_color = row.get('linecolour', 'Blue')
                color = self.color_mapping.get(line_color, '#0066CC')
                
                # Draw the line
                if geometry.geom_type == 'MultiLineString':
                    for line in geometry.geoms:
                        coords = list(line.coords)
                        if len(coords) >= 2:
                            self.draw_line(draw, coords, color, line_width, x, y, zoom)
                            features_drawn += 1
                            # Add start and end points as potential stations
                            junction_coords.add((coords[0][0], coords[0][1]))  # Start
                            junction_coords.add((coords[-1][0], coords[-1][1]))  # End
                elif geometry.geom_type == 'LineString':
                    coords = list(geometry.coords)
                    if len(coords) >= 2:
                        self.draw_line(draw, coords, color, line_width, x, y, zoom)
                        features_drawn += 1
                        # Add start and end points as potential stations
                        junction_coords.add((coords[0][0], coords[0][1]))  # Start
                        junction_coords.add((coords[-1][0], coords[-1][1]))  # End
        
        # Draw station markers at junction points
        for lon, lat in junction_coords:
            self.draw_station_marker(draw, lon, lat, '#FF0000', station_size, x, y, zoom)
        
        return img
    
    def generate_png_tiles(self, min_zoom: int = 10, max_zoom: int = 16):
        """Generate PNG tiles for all zoom levels"""
        print(f"Generating tiles for zoom levels {min_zoom} to {max_zoom}")
        
        # Get the bounds of all features
        bounds = self.gdf.total_bounds
        min_lon, min_lat, max_lon, max_lat = bounds
        
        total_tiles = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            print(f"Processing zoom level {zoom}...")
            
            # Calculate tile range
            min_tile = mercantile.tile(min_lon, min_lat, zoom)
            max_tile = mercantile.tile(max_lon, max_lat, zoom)
            
            zoom_tiles = 0
            
            # Create zoom directory
            zoom_dir = self.output_dir / str(zoom)
            zoom_dir.mkdir(exist_ok=True)
            
            # Generate tiles for this zoom level
            for x in range(min_tile.x, max_tile.x + 1):
                # Create x directory
                x_dir = zoom_dir / str(x)
                x_dir.mkdir(exist_ok=True)
                
                for y in range(max_tile.y, min_tile.y + 1):
                    tile_path = x_dir / f"{y}.png"
                    
                    # Skip if tile already exists
                    if not tile_path.exists():
                        try:
                            tile_img = self.generate_tile(x, y, zoom)
                            
                            # Check if tile has any content before saving
                            has_content = False
                            for pixel in tile_img.getdata():
                                if len(pixel) == 4 and pixel[3] > 0:  # RGBA with alpha > 0
                                    has_content = True
                                    break
                                elif len(pixel) == 3:  # RGB
                                    has_content = True
                                    break
                            
                            # Only save tiles with content
                            if has_content:
                                tile_img.save(tile_path, 'PNG')
                                zoom_tiles += 1
                        except Exception as e:
                            print(f"Error generating tile {zoom}/{x}/{y}: {e}")
            
            print(f"Generated {zoom_tiles} tiles for zoom level {zoom}")
            total_tiles += zoom_tiles
        
        print(f"Total tiles generated: {total_tiles}")
        print(f"Output directory: {self.output_dir}")

def main():
    """Main function"""
    print("=== Bangalore Metro Tile Generator ===")
    
    generator = BangaloreMetroTileGenerator()
    
    # Generate tiles for zoom levels 10-16
    generator.generate_png_tiles(min_zoom=4, max_zoom=7)
    
    print("Tile generation completed!")

if __name__ == "__main__":
    main()
