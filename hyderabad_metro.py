#!/usr/bin/env python3
"""
Hyderabad Metro Tile Generator
Generates Mapbox-compatible PNG tiles for Hyderabad Metro lines with color coding
Based on complete analysis of metro data from data/Telangana/Hyderabad/metro-lines/
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
    "port": 8001,  # Different port from Bangalore
    "token": "pk.eyJ1IjoiYXYxYWNyZSIsImEiOiJjbTJtZmdxN3owa2FzMmpyMjJ4OHV5MHhzIn0.FXpMd91JSER-r7LVpSZN-A"  # Set your Mapbox access token here
}

class HyderabadMetroTileGenerator:
    def __init__(self):
        # Paths to the analyzed metro data
        self.metro_lines_path = project_root / "data" / "Telangana" / "Hyderabad" / "metro-lines" / "Hyd_metro_lines_ph_1&2_Final.geojson"
        self.metro_stations_path = project_root / "data" / "Telangana" / "Hyderabad" / "metro-lines" / "Hyd_metro_stations_ph1&2.geojson"
        self.output_dir = project_root / "hyderabad_metro_tiles"
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Color mapping for Hyderabad Metro lines based on provided scheme
        self.color_mapping = {
            # Metro Phase 1 (Existing)
            'Green Line Phase 1': '#00933D',      # JBS Parade Ground → MG Bus Station
            'Blue Line Phase 1': '#2D6BA1',       # Nagole → Raidurg  
            'Red Line Phase 1': '#E40D17',        # Miyapur → L.B. Nagar
            
            # Metro Phase 2A (Upcoming)
            'Green Line Phase 2A': '#00933D',     # MG Bus Station → Chandrayangutta
            'Purple Line Phase 2A': '#8C06ED',    # Nagole → RGIA Shamshabad
            
            # Metro Phase 2B (Upcoming)
            'Future City Line': '#EF6908',        # RGIA Shamshabad → Future City
            'Blue Line Phase 2B': '#2D6BA1',      # JBS Parade Ground → Shamirpet
            'Green Line Phase 2B': '#00933D',     # Paradise → Medchal
            
            # Default colors for any unmapped lines
            'Metro Phase 1': '#00933D',
            'Metro Phase 2A': '#8C06ED', 
            'Metro Phase 2B': '#EF6908'
        }
        
        # Line width for different zoom levels (reduced)
        self.line_widths = {
            8: 1, 9: 1, 10: 1, 11: 2, 12: 2, 13: 3, 
            14: 4, 15: 5, 16: 6, 17: 8, 18: 10
        }
        
        # Station marker sizes for different zoom levels (reduced but visible)
        self.station_sizes = {
            8: 2, 9: 2, 10: 3, 11: 3, 12: 4, 13: 4,
            14: 5, 15: 6, 16: 7, 17: 8, 18: 9
        }
        
        # Station marker colors - all stations are red
        self.station_colors = {
            'Terminus': '#FF0000',                    # Red for terminus stations
            'Interchange': '#FF0000',                 # Red for interchange stations
            'General Station': '#FF0000',             # Red for general stations
            'Railway & MMTS': '#FF0000',              # Red for railway connections
            'Airport Shuttle Service': '#FF0000',     # Red for airport connections
            'Bus Station': '#FF0000',                 # Red for bus stations
            'default': '#FF0000'                      # Default red
        }
        
        # Load the GeoJSON data
        self.load_metro_data()
        
    def load_metro_data(self):
        """Load metro lines and stations data"""
        try:
            # Load metro lines
            if self.metro_lines_path.exists():
                self.lines_gdf = gpd.read_file(self.metro_lines_path)
                print(f"Loaded {len(self.lines_gdf)} metro lines")
            else:
                print(f"Warning: Metro lines file not found at {self.metro_lines_path}")
                self.lines_gdf = gpd.GeoDataFrame()
            
            # Load metro stations
            if self.metro_stations_path.exists():
                self.stations_gdf = gpd.read_file(self.metro_stations_path)
                print(f"Loaded {len(self.stations_gdf)} metro stations")
            else:
                print(f"Warning: Metro stations file not found at {self.metro_stations_path}")
                self.stations_gdf = gpd.GeoDataFrame()
                
        except Exception as e:
            print(f"Error loading metro data: {e}")
            self.lines_gdf = gpd.GeoDataFrame()
            self.stations_gdf = gpd.GeoDataFrame()
    
    def get_line_color(self, line_name: str, line_colour: str = None) -> str:
        """Get color for a metro line based on its linecolour field"""
        # Use linecolour field if available, otherwise fall back to line_name
        color_field = line_colour if line_colour else line_name
        
        if not color_field:
            return '#800080'  # Default purple
            
        color_field_lower = color_field.lower()
        
        # Direct mapping based on linecolour field
        if 'blue line' in color_field_lower:
            return self.color_mapping['Blue Line Phase 1']  # #2D6BA1
        elif 'green line' in color_field_lower:
            return self.color_mapping['Green Line Phase 1']  # #00933D
        elif 'red line' in color_field_lower:
            return self.color_mapping['Red Line Phase 1']  # #E40D17
        elif 'purple line' in color_field_lower:
            return self.color_mapping['Purple Line Phase 2A']  # #8C06ED
        elif 'future' in color_field_lower:
            return self.color_mapping['Future City Line']  # #EF6908
        
        # Fallback to line_name analysis
        line_name_lower = line_name.lower() if line_name else ''
        
        # Check for specific line patterns in name
        if 'phase 1' in line_name_lower:
            return self.color_mapping['Metro Phase 1']
        elif 'phase 2a' in line_name_lower:
            return self.color_mapping['Metro Phase 2A']
        elif 'phase 2b' in line_name_lower:
            return self.color_mapping['Metro Phase 2B']
        
        # Default mapping
        return self.color_mapping.get(color_field, '#800080')
    
    def get_station_color(self, station_type: str) -> str:
        """Get color for a station based on its type"""
        if not station_type:
            return self.station_colors['default']
            
        # Check for multiple types (e.g., "Terminus, Airport Shuttle Service")
        station_type_lower = station_type.lower()
        
        if 'terminus' in station_type_lower:
            return self.station_colors['Terminus']
        elif 'interchange' in station_type_lower:
            return self.station_colors['Interchange']
        elif 'railway' in station_type_lower or 'mmts' in station_type_lower:
            return self.station_colors['Railway & MMTS']
        elif 'airport' in station_type_lower:
            return self.station_colors['Airport Shuttle Service']
        elif 'bus' in station_type_lower:
            return self.station_colors['Bus Station']
        else:
            return self.station_colors['General Station']
    
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
            # Draw a filled circle for the station with white outline for better visibility
            bbox = [pixel_x - size, pixel_y - size, pixel_x + size, pixel_y + size]
            draw.ellipse(bbox, fill=color, outline='white', width=2)
    
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
        
        # Draw metro lines
        if not self.lines_gdf.empty:
            for idx, row in self.lines_gdf.iterrows():
                geometry = row.geometry
                
                # Check if geometry intersects with tile bounds
                if geometry.intersects(tile_box):
                    # Get color for this line
                    line_name = row.get('name', '')
                    line_colour = row.get('linecolour', '')
                    color = self.get_line_color(line_name, line_colour)
                    
                    # Draw the line
                    if geometry.geom_type == 'MultiLineString':
                        for line in geometry.geoms:
                            coords = list(line.coords)
                            if len(coords) >= 2:
                                self.draw_line(draw, coords, color, line_width, x, y, zoom, bleed_px, bleed_px)
                    elif geometry.geom_type == 'LineString':
                        coords = list(geometry.coords)
                        if len(coords) >= 2:
                            self.draw_line(draw, coords, color, line_width, x, y, zoom, bleed_px, bleed_px)
        
        # Draw station markers (only at higher zoom levels to avoid clutter)
        if zoom >= 10 and not self.stations_gdf.empty:
            for idx, row in self.stations_gdf.iterrows():
                geometry = row.geometry
                
                # Check if station is within tile bounds
                if geometry.intersects(tile_box):
                    if geometry.geom_type == 'Point':
                        lon, lat = geometry.coords[0]
                        station_name = row.get('name', '')
                        station_type = row.get('stationtype', '')
                        station_color = self.get_station_color(station_type)
                        
                        # Debug output for Paradise station
                        if 'Paradise' in station_name:
                            print(f"Drawing Paradise station at {lon}, {lat} for tile {zoom}/{x}/{y}")
                        
                        self.draw_station_marker(draw, lon, lat, station_color, station_size, x, y, zoom, bleed_px, bleed_px)
        
        # Crop to the central 256x256 tile area to remove the bleed
        cropped = img.crop((bleed_px, bleed_px, bleed_px + 256, bleed_px + 256))
        return cropped
    
    def generate_png_tiles(self, min_zoom: int = 8, max_zoom: int = 18):
        """Generate PNG tiles for all zoom levels"""
        print(f"Generating tiles for zoom levels {min_zoom} to {max_zoom}")
        
        # Get the bounds of all features
        all_bounds = []
        if not self.lines_gdf.empty:
            all_bounds.append(self.lines_gdf.total_bounds)
        if not self.stations_gdf.empty:
            all_bounds.append(self.stations_gdf.total_bounds)
        
        if not all_bounds:
            print("No data to generate tiles from")
            return
            
        # Calculate combined bounds
        min_lon = min(bounds[0] for bounds in all_bounds)
        min_lat = min(bounds[1] for bounds in all_bounds)
        max_lon = max(bounds[2] for bounds in all_bounds)
        max_lat = max(bounds[3] for bounds in all_bounds)
        
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
        # Get combined bounds
        all_bounds = []
        if not self.lines_gdf.empty:
            all_bounds.append(self.lines_gdf.total_bounds)
        if not self.stations_gdf.empty:
            all_bounds.append(self.stations_gdf.total_bounds)
        
        if not all_bounds:
            # Default Hyderabad bounds
            min_lon, min_lat, max_lon, max_lat = 78.2, 17.2, 78.7, 17.6
        else:
            min_lon = min(bounds[0] for bounds in all_bounds)
            min_lat = min(bounds[1] for bounds in all_bounds)
            max_lon = max(bounds[2] for bounds in all_bounds)
            max_lat = max(bounds[3] for bounds in all_bounds)
        
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
  </style>
</head>
<body>
  <div id="map"></div>
  <div class="legend">
    <h3>Hyderabad Metro Lines</h3>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #00933D;"></div>
      <span>Green Line (Phase 1 & 2)</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #2D6BA1;"></div>
      <span>Blue Line (Phase 1 & 2B)</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #E40D17;"></div>
      <span>Red Line (Phase 1)</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #8C06ED;"></div>
      <span>Purple Line (Phase 2A)</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #EF6908;"></div>
      <span>Future City Line (Phase 2B)</span>
    </div>
  </div>
  <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
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
    print("=== Hyderabad Metro Tile Generator ===")
    print("Based on complete analysis of metro data from data/Telangana/Hyderabad/metro-lines/")
    
    settings = DEFAULT_VIEW_SETTINGS

    generator = HyderabadMetroTileGenerator()
    
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
