#!/usr/bin/env python3
"""
Hyderabad Metro Tile Generator - Enhanced with Empty Border Tiles
Generates Mapbox-compatible PNG tiles for Hyderabad Metro lines with color coding
Includes empty border tiles to prevent edge bleeding
"""

import os
import sys
import math
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import mercantile
from PIL import Image, ImageDraw
import geopandas as gpd
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
import webbrowser
from shapely.geometry import box, LineString, MultiLineString

# Add the project root to the Python path
# Script is at: scripts/tiles_generation/telangana/hyderabad_metro.py
# Project root is 3 levels up from script
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent.parent
sys.path.insert(0, str(project_root))

# Default settings for tile generation and viewer
DEFAULT_VIEW_SETTINGS = {
    "min_zoom": 8,
    "max_zoom": 18,
    "view": True,
    "port": 8001,
    "token": "pk.eyJ1IjoiYXYxYWNyZSIsImEiOiJjbTJtZmdxN3owa2FzMmpyMjJ4OHV5MHhzIn0.FXpMd91JSER-r7LVpSZN-A"
}

class HyderabadMetroTileGenerator:
    def __init__(self):
        # Paths to the analyzed metro data
        self.metro_lines_path = project_root / "data" / "Telangana" / "Hyderabad" / "metro-lines" / "Hyd_metro_lines_ph_1&2_Final.geojson"
        self.output_dir = project_root / "hyderabad_metro_tiles"
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Color mapping for Hyderabad Metro lines
        self.color_mapping = {
            'Green Line Phase 1': '#00933D',
            'Blue Line Phase 1': '#2D6BA1',
            'Red Line Phase 1': '#E40D17',
            'Green Line Phase 2A': '#00933D',
            'Purple Line Phase 2A': '#8C06ED',
            'Future City Line': '#EF6908',
            'Blue Line Phase 2B': '#2D6BA1',
            'Green Line Phase 2B': '#00933D',
            'Metro Phase 1': '#00933D',
            'Metro Phase 2A': '#8C06ED',
            'Metro Phase 2B': '#EF6908'
        }
        
        # Line widths (thicker for better visibility)
        self.line_widths = {
            8: 2, 9: 2, 10: 3, 11: 3, 12: 4, 13: 4,
            14: 5, 15: 5, 16: 6, 17: 7, 18: 8
        }
        
        # Load the GeoJSON data
        self.load_metro_data()
        
        # Calculate data bounds once
        self.data_bounds = self.calculate_data_bounds()
        
    def calculate_data_bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """Calculate the actual bounds of the metro data (without buffer)"""
        all_bounds = []
        if not self.lines_gdf.empty:
            all_bounds.append(self.lines_gdf.total_bounds)
        if hasattr(self, 'stations_gdf') and not self.stations_gdf.empty:
            all_bounds.append(self.stations_gdf.total_bounds)
        
        if not all_bounds:
            return None
            
        min_lon = min(bounds[0] for bounds in all_bounds)
        min_lat = min(bounds[1] for bounds in all_bounds)
        max_lon = max(bounds[2] for bounds in all_bounds)
        max_lat = max(bounds[3] for bounds in all_bounds)
        
        return (min_lon, min_lat, max_lon, max_lat)
    
    def load_metro_data(self):
        """Load metro lines and stations data"""
        try:
            # Load metro lines
            if self.metro_lines_path.exists():
                self.lines_gdf = gpd.read_file(self.metro_lines_path)
                print(f"Loaded {len(self.lines_gdf)} metro lines")
                if self.lines_gdf.crs is None:
                    self.lines_gdf.set_crs('EPSG:4326', inplace=True)
                elif self.lines_gdf.crs.to_string() != 'EPSG:4326':
                    self.lines_gdf = self.lines_gdf.to_crs('EPSG:4326')
            else:
                print(f"Warning: Metro lines file not found at {self.metro_lines_path}")
                self.lines_gdf = gpd.GeoDataFrame()
            
            # No stations are rendered in this configuration
            self.stations_gdf = gpd.GeoDataFrame()
                
        except Exception as e:
            print(f"Error loading metro data: {e}")
            self.lines_gdf = gpd.GeoDataFrame()
            self.stations_gdf = gpd.GeoDataFrame()
    
    def get_line_color(self, line_name: str, line_colour: str = None) -> str:
        """Get color for a metro line based on its linecolour field"""
        color_field = line_colour if line_colour else line_name
        
        if not color_field:
            return '#800080'
            
        color_field_lower = color_field.lower()
        
        if 'blue line' in color_field_lower:
            return self.color_mapping['Blue Line Phase 1']
        elif 'green line' in color_field_lower:
            return self.color_mapping['Green Line Phase 1']
        elif 'red line' in color_field_lower:
            return self.color_mapping['Red Line Phase 1']
        elif 'purple line' in color_field_lower:
            return self.color_mapping['Purple Line Phase 2A']
        elif 'future' in color_field_lower:
            return self.color_mapping['Future City Line']
        
        line_name_lower = line_name.lower() if line_name else ''
        
        if 'phase 1' in line_name_lower:
            return self.color_mapping['Metro Phase 1']
        elif 'phase 2a' in line_name_lower:
            return self.color_mapping['Metro Phase 2A']
        elif 'phase 2b' in line_name_lower:
            return self.color_mapping['Metro Phase 2B']
        
        return self.color_mapping.get(color_field, '#800080')
    
    def wgs84_to_tile_pixel(self, lon: float, lat: float, tile_x: int, tile_y: int, zoom: int) -> Tuple[float, float]:
        """Convert WGS84 coordinates to pixel coordinates within a tile"""
        lat = max(-85.051129, min(85.051129, lat))
        
        n = 2.0 ** zoom
        tile_lon = (lon + 180.0) / 360.0 * n
        lat_rad = math.radians(lat)
        tile_lat = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
        
        pixel_x = (tile_lon - tile_x) * 256.0
        pixel_y = (tile_lat - tile_y) * 256.0
        
        return pixel_x, pixel_y
    
    def draw_line_antialiased(self, draw: ImageDraw, coordinates: List[Tuple[float, float]], 
                             color: str, width: int, tile_x: int, tile_y: int, zoom: int):
        """Draw a line on the tile with improved antialiasing (thicker with better rendering)"""
        if len(coordinates) < 2:
            return
        
        pixel_coords = []
        for lon, lat in coordinates:
            px, py = self.wgs84_to_tile_pixel(lon, lat, tile_x, tile_y, zoom)
            pixel_coords.append((px, py))
        
        # Increased padding for thicker lines
        padding = width + 15
        visible_segments = []
        
        for i in range(len(pixel_coords) - 1):
            x1, y1 = pixel_coords[i]
            x2, y2 = pixel_coords[i + 1]
            
            if not ((max(x1, x2) < -padding or min(x1, x2) > 256 + padding) or
                    (max(y1, y2) < -padding or min(y1, y2) > 256 + padding)):
                visible_segments.append([(x1, y1), (x2, y2)])
        
        for segment in visible_segments:
            try:
                rounded_segment = [(round(x), round(y)) for x, y in segment]
                draw.line(rounded_segment, fill=color, width=width, joint="curve")
            except Exception:
                pass
    
    def tile_has_data(self, tile_x: int, tile_y: int, zoom: int) -> bool:
        """Check if a tile contains any metro data"""
        tile_bounds = mercantile.bounds(tile_x, tile_y, zoom)
        
        # Create a slightly larger box for intersection testing
        buffer_deg = 0.001
        tile_box = box(
            tile_bounds.west - buffer_deg,
            tile_bounds.south - buffer_deg,
            tile_bounds.east + buffer_deg,
            tile_bounds.north + buffer_deg
        )
        
        # Check lines
        if not self.lines_gdf.empty:
            for _, row in self.lines_gdf.iterrows():
                if row.geometry and row.geometry.intersects(tile_box):
                    return True
        
        return False
    
    def generate_tile(self, x: int, y: int, zoom: int, force_empty: bool = False) -> Image.Image:
        """Generate a single tile"""
        # Create transparent tile
        img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        
        # If forced empty, return the transparent tile
        if force_empty:
            return img
        
        draw = ImageDraw.Draw(img, 'RGBA')
        tile_bounds = mercantile.bounds(x, y, zoom)
        
        line_width = self.line_widths.get(zoom, 3)
        buffer_deg = 0.001
        tile_box = box(
            tile_bounds.west - buffer_deg,
            tile_bounds.south - buffer_deg,
            tile_bounds.east + buffer_deg,
            tile_bounds.north + buffer_deg
        )
        
        # Draw metro lines
        if not self.lines_gdf.empty:
            for idx, row in self.lines_gdf.iterrows():
                geometry = row.geometry
                
                if geometry is None:
                    continue
                
                try:
                    if geometry.intersects(tile_box):
                        line_name = row.get('name', '')
                        line_colour = row.get('linecolour', '')
                        color = self.get_line_color(line_name, line_colour)
                        
                        if geometry.geom_type == 'MultiLineString':
                            for line in geometry.geoms:
                                coords = list(line.coords)
                                if len(coords) >= 2:
                                    self.draw_line_antialiased(draw, coords, color, line_width, x, y, zoom)
                        elif geometry.geom_type == 'LineString':
                            coords = list(geometry.coords)
                            if len(coords) >= 2:
                                self.draw_line_antialiased(draw, coords, color, line_width, x, y, zoom)
                except Exception as e:
                    continue
        
        return img
    
    def generate_png_tiles(self, min_zoom: int = 8, max_zoom: int = 18) -> int:
        """Generate PNG tiles with empty border tiles to prevent bleeding
        
        Returns:
            int: Total number of tiles generated
        """
        print(f"Generating tiles for zoom levels {min_zoom} to {max_zoom}")
        
        if self.data_bounds is None:
            print("No data to generate tiles from")
            return 0
        
        min_lon, min_lat, max_lon, max_lat = self.data_bounds
        print(f"Data bounds: [{min_lon:.4f}, {min_lat:.4f}] to [{max_lon:.4f}, {max_lat:.4f}]")
        
        total_tiles = 0
        total_empty_tiles = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            print(f"Processing zoom level {zoom}...")
            
            # Calculate tile range for actual data (no buffer)
            data_min_tile = mercantile.tile(min_lon, max_lat, zoom)
            data_max_tile = mercantile.tile(max_lon, min_lat, zoom)
            
            # Add buffer of empty tiles around the data
            # The buffer size increases at lower zoom levels
            if zoom <= 10:
                tile_buffer = 3  # More buffer at low zoom
            elif zoom <= 14:
                tile_buffer = 2  # Medium buffer at mid zoom
            else:
                tile_buffer = 1  # Less buffer at high zoom
            
            # Extended tile range with buffer
            buffered_min_x = data_min_tile.x - tile_buffer
            buffered_max_x = data_max_tile.x + tile_buffer
            buffered_min_y = data_min_tile.y - tile_buffer
            buffered_max_y = data_max_tile.y + tile_buffer
            
            zoom_tiles = 0
            empty_tiles = 0
            
            # Create zoom directory
            zoom_dir = self.output_dir / str(zoom)
            zoom_dir.mkdir(exist_ok=True)
            
            # Generate tiles for this zoom level
            for tile_x in range(buffered_min_x, buffered_max_x + 1):
                # Create x directory
                x_dir = zoom_dir / str(tile_x)
                x_dir.mkdir(exist_ok=True)
                
                for tile_y in range(buffered_min_y, buffered_max_y + 1):
                    tile_path = x_dir / f"{tile_y}.png"
                    
                    # Determine if this tile is in the buffer zone (should be empty)
                    is_buffer_tile = (
                        tile_x < data_min_tile.x or tile_x > data_max_tile.x or
                        tile_y < data_min_tile.y or tile_y > data_max_tile.y
                    )
                    
                    try:
                        if is_buffer_tile:
                            # Generate empty tile for buffer zone
                            tile_img = self.generate_tile(tile_x, tile_y, zoom, force_empty=True)
                            empty_tiles += 1
                        else:
                            # Check if tile actually contains data
                            if self.tile_has_data(tile_x, tile_y, zoom):
                                # Generate normal tile with data
                                tile_img = self.generate_tile(tile_x, tile_y, zoom, force_empty=False)
                            else:
                                # Generate empty tile for areas without data
                                tile_img = self.generate_tile(tile_x, tile_y, zoom, force_empty=True)
                                empty_tiles += 1
                        
                        # Save all tiles (including empty ones)
                        tile_img.save(tile_path, 'PNG', optimize=True)
                        zoom_tiles += 1
                        
                    except Exception as e:
                        print(f"Error generating tile {zoom}/{tile_x}/{tile_y}: {e}")
            
            print(f"  Generated {zoom_tiles} tiles ({empty_tiles} empty border/buffer tiles)")
            total_tiles += zoom_tiles
            total_empty_tiles += empty_tiles
        
        print(f"\nTotal tiles generated: {total_tiles}")
        print(f"  - Data tiles: {total_tiles - total_empty_tiles}")
        print(f"  - Empty border tiles: {total_empty_tiles}")
        print(f"Output directory: {self.output_dir}")
        
        return total_tiles

    def write_mapbox_viewer_html(self, access_token: str, port: int) -> Path:
        """Create an index.html in the tiles output dir that overlays the raster tiles on a Mapbox basemap."""
        if self.data_bounds is None:
            # Default Hyderabad bounds
            min_lon, min_lat, max_lon, max_lat = 78.2, 17.2, 78.7, 17.6
        else:
            min_lon, min_lat, max_lon, max_lat = self.data_bounds
        
        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
  <title>Hyderabad Metro Tiles Viewer</title>
  <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet" />
  <style>
    body, html, #map {{ margin: 0; padding: 0; height: 100%; width: 100%; }}
    .mapboxgl-ctrl-logo {{ display: none !important; }}
    .legend {{ 
      position: absolute; 
      bottom: 20px; 
      left: 20px; 
      background: white; 
      padding: 15px; 
      border-radius: 5px; 
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      font-family: Arial, sans-serif;
      font-size: 12px;
    }}
    .legend h3 {{ margin: 0 0 10px 0; font-size: 14px; }}
    .legend-item {{ margin: 5px 0; display: flex; align-items: center; }}
    .legend-color {{ width: 20px; height: 3px; margin-right: 8px; }}
    .info-box {{
      position: absolute;
      top: 10px;
      right: 50px;
      background: white;
      padding: 10px;
      border-radius: 5px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      font-family: Arial, sans-serif;
      font-size: 11px;
    }}
  </style>
</head>
<body>
  <div id="map"></div>
  <div class="info-box">
    <strong>Hyderabad Metro</strong><br>
    Zoom: <span id="zoom-level">11</span>
  </div>
  <div class="legend">
    <h3>Metro Lines</h3>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #00933D;"></div>
      <span>Green Line</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #2D6BA1;"></div>
      <span>Blue Line</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #E40D17;"></div>
      <span>Red Line</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #8C06ED;"></div>
      <span>Purple Line</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #EF6908;"></div>
      <span>Future City Line</span>
    </div>
  </div>
  <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
  <script>
    mapboxgl.accessToken = '{access_token}';
    const map = new mapboxgl.Map({{
      container: 'map',
      style: 'mapbox://styles/mapbox/satellite-streets-v12',
      center: [{center_lon}, {center_lat}],
      zoom: 11,
      maxBounds: [[{min_lon - 0.5}, {min_lat - 0.5}], [{max_lon + 0.5}, {max_lat + 0.5}]]
    }});

    map.addControl(new mapboxgl.NavigationControl(), 'top-right');

    map.on('load', () => {{
      map.fitBounds([[{min_lon}, {min_lat}], [{max_lon}, {max_lat}]], {{ padding: 50 }});
      
      map.addSource('metro-tiles', {{
        type: 'raster',
        tiles: ['http://localhost:{port}/{{z}}/{{x}}/{{y}}.png'],
        tileSize: 256,
        minzoom: 8,
        maxzoom: 18,
        bounds: [{min_lon - 0.1}, {min_lat - 0.1}, {max_lon + 0.1}, {max_lat + 0.1}]
      }});
      
      map.addLayer({{ 
        id: 'metro-tiles', 
        type: 'raster', 
        source: 'metro-tiles', 
        paint: {{ 
          'raster-opacity': 1,
          'raster-fade-duration': 0
        }} 
      }});
    }});
    
    map.on('zoom', () => {{
      document.getElementById('zoom-level').textContent = map.getZoom().toFixed(1);
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
    print("=== Hyderabad Metro Tile Generator (Enhanced) ===")
    print("Generating tiles with empty border tiles to prevent edge bleeding\n")
    
    settings = DEFAULT_VIEW_SETTINGS

    generator = HyderabadMetroTileGenerator()
    
    # Generate tiles with empty borders
    print("Step 1: Generating tiles...")
    tiles_generated = generator.generate_png_tiles(min_zoom=settings["min_zoom"], max_zoom=settings["max_zoom"])
    
    if tiles_generated == 0:
        print("\nError: No tiles were generated. Please check that the data files exist:")
        print(f"  - {generator.metro_lines_path}")
        sys.exit(1)
    
    print(f"\nStep 2: Tiles generated successfully ({tiles_generated} tiles)")
    
    # Optionally view
    if settings["view"]:
        print("\nStep 3: Starting tile server and viewer...")
        token = settings["token"]
        port = settings["port"]
        if not token:
            print("Error: Set DEFAULT_VIEW_SETTINGS['token'] to a valid Mapbox access token to use the viewer.")
            sys.exit(1)
        index_path = generator.write_mapbox_viewer_html(token, port)
        generator.serve_tiles_and_open_browser(port, index_path)
    
    print("\nTile generation completed!")

if __name__ == "__main__":
    main()