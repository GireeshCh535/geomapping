#!/usr/bin/env python3
"""
Bangalore Metro Tile Generator - Clean Version
Generates Mapbox-compatible PNG tiles for Bangalore Metro lines with color coding
"""

import os
import sys
import math
from pathlib import Path
from typing import List, Tuple, Dict
import mercantile
from PIL import Image, ImageDraw
import geopandas as gpd
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
import webbrowser

# Add the project root to the Python path
script_dir = Path(__file__).parent
project_root = script_dir
sys.path.insert(0, str(project_root))

# Default settings for tile generation and viewer
DEFAULT_VIEW_SETTINGS = {
    "min_zoom": 8,
    "max_zoom": 18,
    "view": True,
    "port": 8000,
    "token": "pk.eyJ1IjoiYXYxYWNyZSIsImEiOiJjbTJtZmdxN3owa2FzMmpyMjJ4OHV5MHhzIn0.FXpMd91JSER-r7LVpSZN-A"  # Set your Mapbox access token here
}

class BangaloreMetroTileGenerator:
    def __init__(self):
        self.geojson_path = project_root / "Bangalore Metro Phases 1,2,2A&2B (2).geojson"
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
            8: 1, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 
            14: 6, 15: 8, 16: 10, 17: 12, 18: 15
        }
        
        # Station marker sizes for different zoom levels
        self.station_sizes = {
            8: 2, 9: 2, 10: 3, 11: 4, 12: 5, 13: 6,
            14: 8, 15: 10, 16: 12, 17: 15, 18: 18
        }
        
        # Station marker color
        self.station_color = '#FF0000'
        
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
        
        # Convert to pixel coordinates within the tile (top-left origin)
        pixel_x = int((tile_lon - tile_x) * 256)
        pixel_y = int((tile_lat - tile_y) * 256)
        
        return pixel_x, pixel_y
    
    def draw_line(self, draw: ImageDraw, coordinates: List[Tuple[float, float]], 
                  color: str, width: int, tile_x: int, tile_y: int, zoom: int,
                  offset_x: int = 0, offset_y: int = 0):
        """Draw a line on the tile"""
        if len(coordinates) < 2:
            return
            
        # Convert coordinates to pixel positions
        pixel_coords = []
        for lon, lat in coordinates:
            pixel_x, pixel_y = self.wgs84_to_tile_pixel(lon, lat, tile_x, tile_y, zoom)
            pixel_coords.append((pixel_x + offset_x, pixel_y + offset_y))
        
        # Draw the line segments
        if len(pixel_coords) >= 2:
            try:
                draw.line(pixel_coords, fill=color, width=width)
            except Exception as e:
                # If line drawing fails, draw individual segments
                for i in range(len(pixel_coords) - 1):
                    start = pixel_coords[i]
                    end = pixel_coords[i + 1]
                    try:
                        draw.line([start, end], fill=color, width=width)
                    except:
                        continue
    
    def draw_station_marker(self, draw: ImageDraw, lon: float, lat: float, 
                           color: str, size: int, tile_x: int, tile_y: int, zoom: int,
                           offset_x: int = 0, offset_y: int = 0):
        """Draw a station marker on the tile"""
        pixel_x, pixel_y = self.wgs84_to_tile_pixel(lon, lat, tile_x, tile_y, zoom)
        pixel_x += offset_x
        pixel_y += offset_y
        
        # Check if marker is within tile bounds with some padding
        if -size <= pixel_x <= 256 + size and -size <= pixel_y <= 256 + size:
            # Draw a filled circle for the station
            bbox = [pixel_x - size, pixel_y - size, pixel_x + size, pixel_y + size]
            draw.ellipse(bbox, fill=color, outline='white', width=1)
    
    def generate_tile(self, x: int, y: int, zoom: int) -> Image.Image:
        """Generate a single tile"""
        # Determine styles for this zoom level
        line_width = self.line_widths.get(zoom, 3)
        station_size = self.station_sizes.get(zoom, 5)

        # Add bleed to avoid seams across adjacent tiles
        bleed_px = max(2, line_width * 2)

        # Create a transparent image larger than a tile to draw with bleed
        canvas_size = 256 + 2 * bleed_px
        img = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Get tile bounds
        tile_bounds = mercantile.bounds(x, y, zoom)
        
        # Create a shapely box for the tile bounds with slight buffer for intersection
        from shapely.geometry import box
        tile_width_deg = tile_bounds.east - tile_bounds.west
        tile_height_deg = tile_bounds.north - tile_bounds.south
        buffer_px = bleed_px + max(line_width, station_size)
        buffer_lon = tile_width_deg * (buffer_px / 256.0)
        buffer_lat = tile_height_deg * (buffer_px / 256.0)
        tile_box = box(
            tile_bounds.west - buffer_lon,
            tile_bounds.south - buffer_lat,
            tile_bounds.east + buffer_lon,
            tile_bounds.north + buffer_lat
        )
        
        # Collect station coordinates (only for significant endpoints)
        station_coords = set()
        
        # Draw metro lines
        for idx, row in self.gdf.iterrows():
            geometry = row.geometry
            
            # Check if geometry intersects with tile bounds
            if geometry.intersects(tile_box):
                # Get color for this line
                line_color = row.get('linecolour', 'Purple')
                color = self.color_mapping.get(line_color, '#800080')
                
                # Draw the line
                if geometry.geom_type == 'MultiLineString':
                    for line in geometry.geoms:
                        coords = list(line.coords)
                        if len(coords) >= 2:
                            self.draw_line(draw, coords, color, line_width, x, y, zoom, bleed_px, bleed_px)
                            # Only add stations for longer line segments (reduces clutter)
                            if len(coords) > 5:  # Only for significant line segments
                                station_coords.add((coords[0][0], coords[0][1]))  # Start
                                station_coords.add((coords[-1][0], coords[-1][1]))  # End
                elif geometry.geom_type == 'LineString':
                    coords = list(geometry.coords)
                    if len(coords) >= 2:
                        self.draw_line(draw, coords, color, line_width, x, y, zoom, bleed_px, bleed_px)
                        # Only add stations for longer line segments
                        if len(coords) > 5:
                            station_coords.add((coords[0][0], coords[0][1]))  # Start
                            station_coords.add((coords[-1][0], coords[-1][1]))  # End
        
        # Draw station markers (only at higher zoom levels to avoid clutter)
        if zoom >= 12:  # Only show stations at zoom 12 and above
            for lon, lat in station_coords:
                self.draw_station_marker(draw, lon, lat, self.station_color, station_size, x, y, zoom, bleed_px, bleed_px)
        
        # Crop to the central 256x256 tile area to remove the bleed
        cropped = img.crop((bleed_px, bleed_px, bleed_px + 256, bleed_px + 256))
        return cropped
    
    def generate_png_tiles(self, min_zoom: int = 8, max_zoom: int = 18):
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
                            
                            # Always save the tile image. If there's no content, this will be a fully transparent PNG.
                            tile_img.save(tile_path, 'PNG')
                            zoom_tiles += 1
                        except Exception as e:
                            print(f"Error generating tile {zoom}/{x}/{y}: {e}")
            
            print(f"Generated {zoom_tiles} tiles for zoom level {zoom}")
            total_tiles += zoom_tiles
        
        print(f"Total tiles generated: {total_tiles}")
        print(f"Output directory: {self.output_dir}")

    def write_mapbox_viewer_html(self, access_token: str, port: int) -> Path:
        """Create an index.html in the tiles output dir that overlays the raster tiles on a Mapbox basemap."""
        bounds = self.gdf.total_bounds
        min_lon, min_lat, max_lon, max_lat = bounds
        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2
        
        html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"initial-scale=1,maximum-scale=1,user-scalable=no\" />
  <title>Bengaluru Metro Tiles Viewer</title>
  <link href=\"https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css\" rel=\"stylesheet\" />
  <style>
    body, html, #map {{ margin: 0; padding: 0; height: 100%; width: 100%; }}
    .mapboxgl-ctrl-logo {{ display: none !important; }}
  </style>
</head>
<body>
  <div id=\"map\"></div>
  <script src=\"https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js\"></script>
  <script>
    mapboxgl.accessToken = '{access_token}';
    const map = new mapboxgl.Map({{
      container: 'map',
      style: 'mapbox://styles/mapbox/satellite-streets-v12',
      center: [{center_lon}, {center_lat}],
      zoom: 11
    }});

    map.addControl(new mapboxgl.NavigationControl(), 'top-right');

    map.on('load', () => {{
      map.fitBounds([[{min_lon}, {min_lat}], [{max_lon}, {max_lat}]], {{ padding: 40 }});
      map.addSource('metro-tiles', {{
        type: 'raster',
        tiles: ['http://localhost:{port}/{{z}}/{{x}}/{{y}}.png'],
        tileSize: 256,
        minzoom: 8,
        maxzoom: 18
      }});
      map.addLayer({{ id: 'metro-tiles', type: 'raster', source: 'metro-tiles', paint: {{ 'raster-opacity': 1 }} }});
    }});
  </script>
</body>
</html>
"""
        index_path = self.output_dir / "index.html"
        index_path.write_text(html, encoding='utf-8')
        print(f"Viewer written to: {index_path}")
        return index_path

    def serve_tiles_and_open_browser(self, port: int, index_path: Path) -> None:
        """Serve the tiles output directory over HTTP and open the viewer in a browser."""
        handler_cls = partial(SimpleHTTPRequestHandler, directory=str(self.output_dir))
        server = ThreadingHTTPServer(("0.0.0.0", port), handler_cls)
        url = f"http://localhost:{port}/{index_path.name}"
        print(f"Serving {self.output_dir} at http://0.0.0.0:{port} (Ctrl+C to stop)")
        print(f"Opening {url} ...")
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"Could not open browser automatically: {e}\nYou can open {url} manually.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped by user.")
        finally:
            server.server_close()


def main():
    """Main function"""
    print("=== Bangalore Metro Tile Generator (Clean Version) ===")
    
    settings = DEFAULT_VIEW_SETTINGS

    generator = BangaloreMetroTileGenerator()
    
    # Generate tiles
    generator.generate_png_tiles(min_zoom=settings["min_zoom"], max_zoom=settings["max_zoom"])
    
    # Optionally view
    if settings["view"]:
        token = settings["token"]
        port = settings["port"]
        if not token:
            print("Error: Set DEFAULT_VIEW_SETTINGS['token'] to a valid Mapbox access token to use the viewer.")
            sys.exit(1)
        index_path = generator.write_mapbox_viewer_html(token, port)
        generator.serve_tiles_and_open_browser(port, index_path)
    
    print("Tile generation completed!")

if __name__ == "__main__":
    main()
