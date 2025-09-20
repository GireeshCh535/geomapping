#!/usr/bin/env python3
"""
Hyderabad Ratan Tata Road Tile Generator
Generates Mapbox-compatible PNG tiles for Hyderabad Ratan Tata Road with proper styling
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
    "port": 8001,  # Different port to avoid conflicts
    "token": "pk.eyJ1IjoiYXYxYWNyZSIsImEiOiJjbTJtZmdxN3owa2FzMmpyMjJ4OHV5MHhzIn0.FXpMd91JSER-r7LVpSZN-A"  # Set your Mapbox access token here
}

class HyderabadRatanTataRoadTileGenerator:
    def __init__(self):
        self.geojson_path = project_root / "data/Telangana/Hyderabad/ratan-tata-road/RatanTataRoad.geojson"
        self.output_dir = project_root / "hyderabad_ratan_tata_road_tiles"
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Ratan Tata Road styling
        self.road_color = '#14e098'  # Custom green color for the road
        self.road_stroke_color = '#0fb876'  # Darker green for stroke
        
        # Line width for different zoom levels (thicker than metro for road visibility)
        self.line_widths = {
            8: 2, 9: 2, 10: 3, 11: 4, 12: 5, 13: 6, 
            14: 8, 15: 10, 16: 12, 17: 15, 18: 18
        }
        
        # Load the GeoJSON data
        self.gdf = gpd.read_file(self.geojson_path)
        print(f"Loaded {len(self.gdf)} road features")
        
        # Transform to WGS84 if needed
        if self.gdf.crs != 'EPSG:4326':
            print(f"Transforming from {self.gdf.crs} to EPSG:4326")
            self.gdf = self.gdf.to_crs('EPSG:4326')
            print("Transformation completed")
        
        # Print road information
        for idx, row in self.gdf.iterrows():
            print(f"Road: {row.get('Name', 'Unknown')}")
            print(f"  Route: {row.get('End_to_End', 'Unknown')}")
            print(f"  Width: {row.get('Width', 'Unknown')}")
        
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
        for coord in coordinates:
            # Handle 2D or 3D coordinates
            if len(coord) >= 2:
                lon, lat = coord[0], coord[1]
                pixel_x, pixel_y = self.wgs84_to_tile_pixel(lon, lat, tile_x, tile_y, zoom)
                pixel_coords.append((pixel_x + offset_x, pixel_y + offset_y))
        
        # Draw the line segments
        if len(pixel_coords) >= 2:
            try:
                # Draw a thicker stroke first for better visibility
                stroke_width = max(1, width + 2)
                draw.line(pixel_coords, fill=self.road_stroke_color, width=stroke_width)
                # Then draw the main line
                draw.line(pixel_coords, fill=color, width=width)
            except Exception as e:
                # If line drawing fails, draw individual segments
                for i in range(len(pixel_coords) - 1):
                    start = pixel_coords[i]
                    end = pixel_coords[i + 1]
                    try:
                        # Draw stroke
                        stroke_width = max(1, width + 2)
                        draw.line([start, end], fill=self.road_stroke_color, width=stroke_width)
                        # Draw main line
                        draw.line([start, end], fill=color, width=width)
                    except:
                        continue
    
    def generate_tile(self, x: int, y: int, zoom: int) -> Image.Image:
        """Generate a single tile"""
        # Determine styles for this zoom level
        line_width = self.line_widths.get(zoom, 4)

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
        buffer_px = bleed_px + line_width
        buffer_lon = tile_width_deg * (buffer_px / 256.0)
        buffer_lat = tile_height_deg * (buffer_px / 256.0)
        
        tile_box = box(
            tile_bounds.west - buffer_lon,
            tile_bounds.south - buffer_lat,
            tile_bounds.east + buffer_lon,
            tile_bounds.north + buffer_lat
        )
        
        # Draw road lines
        for idx, row in self.gdf.iterrows():
            geometry = row.geometry
            
            # Check if geometry intersects with tile bounds
            if geometry.intersects(tile_box):
                # Draw the road line
                if geometry.geom_type == 'MultiLineString':
                    for line in geometry.geoms:
                        coords = list(line.coords)
                        if len(coords) >= 2:
                            self.draw_line(draw, coords, self.road_color, line_width, x, y, zoom, bleed_px, bleed_px)
                elif geometry.geom_type == 'LineString':
                    coords = list(geometry.coords)
                    if len(coords) >= 2:
                        self.draw_line(draw, coords, self.road_color, line_width, x, y, zoom, bleed_px, bleed_px)
        
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
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        # Calculate appropriate zoom level to show the full road
        import math
        lat_diff = bounds[3] - bounds[1]
        lon_diff = bounds[2] - bounds[0]
        max_diff = max(lat_diff, lon_diff)
        
        if max_diff > 0.1:
            zoom = 10
        elif max_diff > 0.05:
            zoom = 11
        elif max_diff > 0.02:
            zoom = 12
        else:
            zoom = 13
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
    <title>Hyderabad Ratan Tata Road - Mapbox GL</title>
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet" />
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
        .info {{
            position: fixed;
            top: 10px;
            right: 10px;
            background: white;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            z-index: 1;
            font-family: Arial, sans-serif;
        }}
        .info h3 {{ margin-top: 0; }}
        .zoom-info {{
            position: fixed;
            bottom: 10px;
            left: 10px;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            z-index: 1;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info">
        <h3>🛣️ Hyderabad Ratan Tata Road (Mapbox)</h3>
        <p><strong>Color:</strong> {self.road_color} (Custom Green)</p>
        <p><strong>Tiles:</strong> Zoom {DEFAULT_VIEW_SETTINGS['min_zoom']}-{DEFAULT_VIEW_SETTINGS['max_zoom']}</p>
        <p><strong>Format:</strong> PNG (256x256)</p>
        <p><strong>Route:</strong> Raviryal (ORR Exit 13) to Meerkhanpet (Skill University)</p>
        <p><strong>Width:</strong> 6 Lanes</p>
        <small>Serve this folder via a local web server</small>
    </div>
    <div class="zoom-info" id="zoom-display">Zoom: {zoom}</div>
    <script>
        mapboxgl.accessToken = '{access_token}';
        const map = new mapboxgl.Map({{
            container: 'map',
            style: 'mapbox://styles/mapbox/satellite-streets-v12',
            center: [{center_lon}, {center_lat}],
            zoom: {zoom}
        }});

        map.addControl(new mapboxgl.NavigationControl(), 'top-right');

        map.on('load', () => {{
            map.fitBounds([[{bounds[0]}, {bounds[1]}], [{bounds[2]}, {bounds[3]}]], {{ padding: 40 }});
            map.addSource('ratan-tata-road-tiles', {{
                type: 'raster',
                tiles: ['http://localhost:{port}/{{z}}/{{x}}/{{y}}.png'],
                tileSize: 256,
                minzoom: {DEFAULT_VIEW_SETTINGS['min_zoom']},
                maxzoom: {DEFAULT_VIEW_SETTINGS['max_zoom']}
            }});
            map.addLayer({{ 
                id: 'ratan-tata-road-tiles', 
                type: 'raster', 
                source: 'ratan-tata-road-tiles', 
                paint: {{ 'raster-opacity': 1 }} 
            }});
        }});

        // Update zoom display
        map.on('zoom', () => {{
            document.getElementById('zoom-display').textContent = 'Zoom: ' + Math.round(map.getZoom());
        }});
    </script>
</body>
</html>"""
        
        index_path = self.output_dir / "index.html"
        with open(index_path, 'w') as f:
            f.write(html_content)
        
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
    print("=== Hyderabad Ratan Tata Road Tile Generator ===")
    
    settings = DEFAULT_VIEW_SETTINGS

    generator = HyderabadRatanTataRoadTileGenerator()
    
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
