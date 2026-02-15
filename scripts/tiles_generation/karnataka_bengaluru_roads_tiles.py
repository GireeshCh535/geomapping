#!/usr/bin/env python3
"""
Karnataka Bengaluru Roads Tile Generator - Enhanced Version
Generates high-quality PNG tiles from Bengaluru Masterplan Roads data
Uses same rendering approach as metro tiles for consistency
"""

import os
import sys
import math
from pathlib import Path
import mercantile
from PIL import Image, ImageDraw
import json
import logging
import geopandas as gpd
from shapely.geometry import box, Point, LineString, MultiLineString
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
import webbrowser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KarnatakaBengaluruRoadsTileGenerator:
    def __init__(self, data_dir, output_dir, force_overwrite=True):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.force_overwrite = force_overwrite
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Single color for all roads
        self.road_color = '#14e098'  # Teal/cyan color
        
        # Load and process data
        self.load_and_process_data()
        
        # Calculate data bounds
        self.data_bounds = self.calculate_data_bounds()
    
    def calculate_data_bounds(self):
        """Calculate the bounds of the road data"""
        if self.gdf.empty:
            return None
        bounds = self.gdf.total_bounds
        return tuple(bounds)  # (min_lon, min_lat, max_lon, max_lat)
    
    def load_and_process_data(self):
        """Load and process the roads GeoJSON data"""
        logger.info("Loading roads data...")
        
        # Load the GeoJSON file
        geojson_path = self.data_dir / "Bangalore Masterplan Roads.geojson"
        if not geojson_path.exists():
            raise FileNotFoundError(f"Roads data file not found: {geojson_path}")
        
        self.gdf = gpd.read_file(geojson_path)
        logger.info(f"Loaded {len(self.gdf)} road features")
        
        # Ensure CRS is WGS84
        if self.gdf.crs is None:
            self.gdf.crs = 'EPSG:4326'
        elif self.gdf.crs != 'EPSG:4326':
            self.gdf = self.gdf.to_crs('EPSG:4326')
        
        # Remove invalid geometries
        valid_mask = self.gdf.geometry.notna() & ~self.gdf.geometry.is_empty
        self.gdf = self.gdf[valid_mask].copy()
        
        logger.info(f"Processed {len(self.gdf)} valid road features")
        
        # Build spatial index
        logger.info("Building spatial index...")
        self.spatial_index = self.gdf.sindex
        
        logger.info("Data processing completed")
    
    def get_line_width(self, zoom, road_width_feet=None):
        """Get line width based on zoom level and road width
        
        Args:
            zoom: Zoom level
            road_width_feet: Road width in feet from data
        """
        # Base widths by zoom
        base_widths = {
            4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1, 10: 2, 11: 2, 
            12: 2, 13: 3, 14: 3, 15: 4, 16: 4, 17: 5, 18: 6
        }
        
        base_width = base_widths.get(zoom, 2)
        
        # Scale by road width if provided
        if road_width_feet:
            if road_width_feet >= 36:
                return base_width + 2  # Major roads
            elif road_width_feet >= 24:
                return base_width + 1  # Medium roads
        
        return base_width
    
    def get_road_color(self, road_width_feet=None):
        """Get color for a road (single color for all roads)"""
        return self.road_color
    
    def wgs84_to_tile_pixel(self, lon: float, lat: float, tile_x: int, tile_y: int, zoom: int):
        """Convert WGS84 coordinates to pixel coordinates within a tile"""
        lat = max(-85.051129, min(85.051129, lat))
        
        n = 2.0 ** zoom
        tile_lon = (lon + 180.0) / 360.0 * n
        lat_rad = math.radians(lat)
        tile_lat = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
        
        pixel_x = (tile_lon - tile_x) * 256.0
        pixel_y = (tile_lat - tile_y) * 256.0
        
        return pixel_x, pixel_y
    
    def draw_line_antialiased(self, draw, coordinates, color, width, tile_x, tile_y, zoom):
        """Draw a line on the tile with improved antialiasing"""
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
    
    def tile_has_data(self, tile_x, tile_y, zoom):
        """Check if a tile contains any road data"""
        tile_bounds = mercantile.bounds(tile_x, tile_y, zoom)
        
        # Create a slightly larger box for intersection testing
        buffer_deg = 0.001
        tile_box = box(
            tile_bounds.west - buffer_deg,
            tile_bounds.south - buffer_deg,
            tile_bounds.east + buffer_deg,
            tile_bounds.north + buffer_deg
        )
        
        # Check if any roads intersect
        if not self.gdf.empty:
            for _, row in self.gdf.iterrows():
                if row.geometry and row.geometry.intersects(tile_box):
                    return True
        
        return False
    
    def generate_tile(self, x, y, zoom, force_empty=False):
        """Generate a single tile"""
        # Create transparent tile
        img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        
        # If forced empty, return the transparent tile
        if force_empty:
            return img
        
        draw = ImageDraw.Draw(img, 'RGBA')
        tile_bounds = mercantile.bounds(x, y, zoom)
        
        buffer_deg = 0.001
        tile_box = box(
            tile_bounds.west - buffer_deg,
            tile_bounds.south - buffer_deg,
            tile_bounds.east + buffer_deg,
            tile_bounds.north + buffer_deg
        )
        
        # Draw roads
        if not self.gdf.empty:
            for idx, row in self.gdf.iterrows():
                geometry = row.geometry
                
                if geometry is None:
                    continue
                
                try:
                    if geometry.intersects(tile_box):
                        # Get road width and determine color/width
                        road_width_feet = row.get('Road Width (in feet)', None)
                        color = self.get_road_color(road_width_feet)
                        line_width = self.get_line_width(zoom, road_width_feet)
                        
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
    
    def generate_tiles(self, min_zoom, max_zoom):
        """Generate tiles for specified zoom levels with empty border tiles
        
        Returns:
            int: Total number of tiles generated (0 if no data)
        """
        logger.info(f"Generating tiles for zoom levels {min_zoom} to {max_zoom}")
        logger.info("Blank tiles will be created for all tile positions")
        
        if self.data_bounds is None:
            logger.error("No data to generate tiles from")
            return 0
        
        min_lon, min_lat, max_lon, max_lat = self.data_bounds
        logger.info(f"Data bounds: [{min_lon:.4f}, {min_lat:.4f}] to [{max_lon:.4f}, {max_lat:.4f}]")
        
        total_tiles = 0
        total_empty_tiles = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            logger.info(f"Processing zoom level {zoom}...")
            
            # Calculate tile range for actual data (no buffer)
            data_min_tile = mercantile.tile(min_lon, max_lat, zoom)
            data_max_tile = mercantile.tile(max_lon, min_lat, zoom)
            
            # Add buffer of empty tiles around the data
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
                        logger.error(f"Error generating tile {zoom}/{tile_x}/{tile_y}: {e}")
            
            logger.info(f"  Generated {zoom_tiles} tiles ({empty_tiles} empty border/buffer tiles)")
            total_tiles += zoom_tiles
            total_empty_tiles += empty_tiles
        
        logger.info(f"\nTotal tiles generated: {total_tiles}")
        logger.info(f"  - Data tiles: {total_tiles - total_empty_tiles}")
        logger.info(f"  - Empty border tiles: {total_empty_tiles}")
        logger.info(f"Output directory: {self.output_dir}")
        
        return total_tiles
    
    def create_viewer_html(self, access_token: str, port: int):
        """Create index.html with Mapbox GL JS viewer"""
        # Get bounds
        if self.data_bounds is None:
            # Default Bangalore bounds
            bounds = self.gdf.total_bounds
            min_lon, min_lat, max_lon, max_lat = bounds
        else:
            min_lon, min_lat, max_lon, max_lat = self.data_bounds
        
        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
  <title>Bengaluru Roads Tiles Viewer</title>
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
    <strong>Bengaluru Roads</strong><br>
    Masterplan 2015<br>
    Zoom: <span id="zoom-level">11</span>
  </div>
  <div class="legend">
    <h3>Bengaluru Roads</h3>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #14e098;"></div>
      <span>Masterplan 2015 Roads</span>
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
      
      map.addSource('roads-tiles', {{
        type: 'raster',
        tiles: ['http://localhost:{port}/{{z}}/{{x}}/{{y}}.png'],
        tileSize: 256,
        minzoom: 4,
        maxzoom: 18,
        bounds: [{min_lon - 0.1}, {min_lat - 0.1}, {max_lon + 0.1}, {max_lat + 0.1}]
      }});
      
      map.addLayer({{ 
        id: 'roads-tiles', 
        type: 'raster', 
        source: 'roads-tiles', 
        paint: {{ 
          'raster-opacity': 0.8,
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
    
    def serve_tiles_and_open_browser(self, port: int, index_path: Path):
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
    """Main function - Identical behavior to Metro script"""
    # Default settings
    DEFAULT_VIEW_SETTINGS = {
        "min_zoom": 4,
        "max_zoom": 18,
        "view": True,  # Auto-start server by default
        "port": 8003,  # Different port than metro
        "token": "pk.eyJ1IjoiYXYxYWNyZSIsImEiOiJjbTJtZmdxN3owa2FzMmpyMjJ4OHV5MHhzIn0.FXpMd91JSER-r7LVpSZN-A"
    }
    
    print("=== Bengaluru Roads Tile Generator (Enhanced) ===")
    print("Generating tiles with empty border tiles to prevent edge bleeding\n")
    
    settings = DEFAULT_VIEW_SETTINGS
    
    try:
        # Set up paths - get project root directory
        # Script is at: scripts/tiles_generation/karnataka_bengaluru_roads_tiles.py
        # Project root is 2 levels up from script
        script_path = Path(__file__).resolve()
        project_root = script_path.parent.parent.parent
        
        data_dir = project_root / "data" / "karnataka" / "bengaluru" / "master_plan" / "roads"
        output_dir = project_root / "karnataka_bengaluru_roads_tiles"
        
        # Initialize generator
        generator = KarnatakaBengaluruRoadsTileGenerator(
            data_dir=data_dir,
            output_dir=output_dir,
            force_overwrite=True
        )
        
        print(f"Generating tiles for zoom levels {settings['min_zoom']} to {settings['max_zoom']}\n")
        
        # Generate tiles
        tiles_generated = generator.generate_tiles(min_zoom=settings["min_zoom"], max_zoom=settings["max_zoom"])
        
        if tiles_generated == 0:
            print("\nError: No tiles were generated. Please check that the data files exist:")
            print(f"  - {data_dir / 'Bangalore Masterplan Roads.geojson'}")
            sys.exit(1)
        
        # Create viewer and start server
        if settings["view"]:
            token = settings["token"]
            port = settings["port"]
            if not token:
                print("Error: Set DEFAULT_VIEW_SETTINGS['token'] to a valid Mapbox access token to use the viewer.")
                sys.exit(1)
            
            print()  # Blank line before viewer messages
            index_path = generator.create_viewer_html(token, port)
            generator.serve_tiles_and_open_browser(port, index_path)
        
    except Exception as e:
        print(f"Error in main: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

