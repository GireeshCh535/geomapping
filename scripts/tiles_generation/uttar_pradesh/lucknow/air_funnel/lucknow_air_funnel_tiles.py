#!/usr/bin/env python3
"""
Lucknow Air Funnel Zones Tile Generator
Generates PNG tiles for Airport Height Restriction Zones
Based on previous air funnel rendering approach
"""

import os
import sys
import json
import time
from pathlib import Path
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import shape, box, Polygon, MultiPolygon
from rtree import index
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
import webbrowser

# Add the project root to the Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Default settings for tile generation and viewer
DEFAULT_VIEW_SETTINGS = {
    "min_zoom": 8,
    "max_zoom": 18,
    "view": True,
    "port": 8017,
    "token": "pk.eyJ1IjoiYXYxYWNyZSIsImEiOiJjbTJtZmdxN3owa2FzMmpyMjJ4OHV5MHhzIn0.FXpMd91JSER-r7LVpSZN-A"
}

class LucknowAirFunnelTileGenerator:
    def __init__(self, data_path, output_dir):
        self.data_path = Path(data_path)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.spatial_index = index.Index()
        self.feature_id_counter = 0
        self.feature_lookup = {}
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
    def get_color_map(self):
        """Color mapping for height restriction zones (Lucknow)"""
        return {
            'For construction mandatory NOC from AAI is required': {'fill': '#91302D', 'outline': '#6B2421'},
            '140 Meters Above Mean Sea Level': {'fill': '#559B33', 'outline': '#3F7326'},
            '160 Meters Above Mean Sea Level': {'fill': '#8B36A4', 'outline': '#682881'},
            '180 Meters Above Mean Sea Level': {'fill': '#CF9D2C', 'outline': '#A37D23'},
            '200 Meters Above Mean Sea Level': {'fill': '#3A6A99', 'outline': '#2C5073'},
            '220 Meters Above Mean Sea Level': {'fill': '#A0A0A0', 'outline': '#787878'},
        }
    
    def hex_to_rgb(self, hex_color):
        """Convert hex to RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def get_zoom_scale(self, zoom):
        """Get rendering scale based on zoom level"""
        if zoom <= 10:
            return 4
        elif zoom <= 13:
            return 3
        elif zoom <= 15:
            return 2
        else:
            return 1
    
    def load_data(self):
        """Load air funnel zones data"""
        print(f"Loading data from {self.data_path.name}...")
        
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_path}")
        
        with open(self.data_path, 'r') as f:
            data = json.load(f)
        
        features = data.get('features', [])
        print(f"Found {len(features)} features")
        
        # Build spatial index
        print("Building spatial index...")
        loaded = 0
        
        for feature in features:
            try:
                geom = shape(feature['geometry'])
                
                if geom is None or geom.is_empty:
                    continue
                
                props = feature.get('properties', {})
                # Try multiple possible property names
                height_zone = props.get('Pemissible Height', 
                                       props.get('Permissible Height',
                                               props.get('Height',
                                                        props.get('Zone', 'Unknown'))))
                
                feature_data = {
                    'geometry': geom,
                    'zone': height_zone,
                    'properties': props,
                    'area': geom.area
                }
                
                bounds = geom.bounds
                self.spatial_index.insert(self.feature_id_counter, bounds)
                self.feature_lookup[self.feature_id_counter] = feature_data
                self.feature_id_counter += 1
                loaded += 1
                
            except Exception as e:
                print(f"Error loading feature: {e}")
                continue
        
        print(f"✓ Loaded {loaded} features successfully\n")
    
    def get_bounds(self):
        """Get geographic bounds"""
        min_lon, min_lat = float('inf'), float('inf')
        max_lon, max_lat = float('-inf'), float('-inf')
        
        for feature_data in self.feature_lookup.values():
            bounds = feature_data['geometry'].bounds
            min_lon = min(min_lon, bounds[0])
            min_lat = min(min_lat, bounds[1])
            max_lon = max(max_lon, bounds[2])
            max_lat = max(max_lat, bounds[3])
        
        return (min_lon, min_lat, max_lon, max_lat)
    
    def render_polygon_with_holes(self, draw, polygon, tile_bounds, lon_buffer, lat_buffer, 
                                  buffered_size, fill_rgb):
        """Render polygon with interior rings (holes) properly"""
        # Create a temporary image for this polygon with alpha channel
        poly_img = Image.new('RGBA', (buffered_size, buffered_size), (0, 0, 0, 0))
        poly_draw = ImageDraw.Draw(poly_img)
        
        # Convert exterior ring to pixel coordinates
        exterior_pixels = []
        for coord in polygon.exterior.coords:
            lon, lat = coord[0], coord[1]
            px = ((lon - (tile_bounds.west - lon_buffer)) / 
                  ((tile_bounds.east + lon_buffer) - (tile_bounds.west - lon_buffer)) * buffered_size)
            py = (((tile_bounds.north + lat_buffer) - lat) / 
                  ((tile_bounds.north + lat_buffer) - (tile_bounds.south - lat_buffer)) * buffered_size)
            exterior_pixels.append((int(px), int(py)))
        
        if len(exterior_pixels) < 3:
            return
        
        # Draw exterior ring with 100% opacity (fully opaque)
        fill_rgba = fill_rgb + (255,)  # 100% opacity
        poly_draw.polygon(exterior_pixels, fill=fill_rgba, outline=fill_rgba)
        
        # Draw interior rings (holes) as transparent
        for interior in polygon.interiors:
            interior_pixels = []
            for coord in interior.coords:
                lon, lat = coord[0], coord[1]
                px = ((lon - (tile_bounds.west - lon_buffer)) / 
                      ((tile_bounds.east + lon_buffer) - (tile_bounds.west - lon_buffer)) * buffered_size)
                py = (((tile_bounds.north + lat_buffer) - lat) / 
                      ((tile_bounds.north + lat_buffer) - (tile_bounds.south - lat_buffer)) * buffered_size)
                interior_pixels.append((int(px), int(py)))
            
            if len(interior_pixels) >= 3:
                # Draw hole as fully transparent
                poly_draw.polygon(interior_pixels, fill=(0, 0, 0, 0), outline=(0, 0, 0, 0))
        
        # Composite the polygon with holes onto the main image
        draw._image.paste(poly_img, (0, 0), poly_img)
    
    def render_tile(self, tile):
        """Render a single tile with air funnel zones"""
        z, x, y = tile.z, tile.x, tile.y
        
        scale = self.get_zoom_scale(z)
        img_size = self.tile_size * scale
        
        # Buffer zone to prevent seams
        buffer_pixels = 4 * scale
        buffered_size = img_size + (buffer_pixels * 2)
        
        img_buffered = Image.new('RGBA', (buffered_size, buffered_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img_buffered)
        
        tile_bounds = mercantile.bounds(tile)
        
        # 2% buffer for seamless tiles
        lon_buffer = (tile_bounds.east - tile_bounds.west) * 0.02
        lat_buffer = (tile_bounds.north - tile_bounds.south) * 0.02
        
        tile_bbox_buffered = box(
            tile_bounds.west - lon_buffer, 
            tile_bounds.south - lat_buffer,
            tile_bounds.east + lon_buffer, 
            tile_bounds.north + lat_buffer
        )
        
        intersecting_ids = list(self.spatial_index.intersection(tile_bbox_buffered.bounds))
        
        if not intersecting_ids:
            return None
        
        color_map = self.get_color_map()
        
        # Sort by area (largest first) - so smaller zones render on top
        features_to_render = []
        for feature_id in intersecting_ids:
            feature_data = self.feature_lookup[feature_id]
            if feature_data['geometry'].intersects(tile_bbox_buffered):
                features_to_render.append((feature_data['area'], feature_id, feature_data))
        
        features_to_render.sort(key=lambda x: x[0], reverse=True)
        
        # Render all features
        for area, feature_id, feature_data in features_to_render:
            geom = feature_data['geometry']
            zone = feature_data['zone']
            
            # Get color for this zone
            color_info = color_map.get(zone, {'fill': '#A0A0A0', 'outline': '#787878'})
            
            fill_rgb = self.hex_to_rgb(color_info['fill'])
            outline_rgb = self.hex_to_rgb(color_info.get('outline', color_info['fill']))
            
            # Handle geometry types
            if geom.geom_type == 'Polygon':
                polygons = [geom]
            elif geom.geom_type == 'MultiPolygon':
                polygons = list(geom.geoms)
            else:
                continue
            
            # Render each polygon
            for polygon in polygons:
                try:
                    # Convert exterior ring to pixel coordinates
                    pixel_coords = []
                    for coord in polygon.exterior.coords:
                        lon, lat = coord[0], coord[1]
                        px = ((lon - (tile_bounds.west - lon_buffer)) / 
                              ((tile_bounds.east + lon_buffer) - (tile_bounds.west - lon_buffer)) * buffered_size)
                        py = (((tile_bounds.north + lat_buffer) - lat) / 
                              ((tile_bounds.north + lat_buffer) - (tile_bounds.south - lat_buffer)) * buffered_size)
                        pixel_coords.append((px, py))
                    
                    if len(pixel_coords) < 3:
                        continue
                    
                    # Check if polygon has interior rings (holes)
                    has_holes = len(polygon.interiors) > 0
                    
                    int_pixels = [(int(x), int(y)) for x, y in pixel_coords]
                    
                    if has_holes:
                        # Render polygon with holes using mask
                        self.render_polygon_with_holes(draw, polygon, tile_bounds, lon_buffer, lat_buffer, 
                                                      buffered_size, fill_rgb)
                    else:
                        # Simple polygon without holes - 100% opacity (fully opaque)
                        fill_rgba = fill_rgb + (255,)
                        draw.polygon(int_pixels, fill=fill_rgba, outline=outline_rgb)
                
                except Exception as e:
                    continue
        
        # Crop to final tile size
        crop_box = (buffer_pixels, buffer_pixels, 
                   buffer_pixels + img_size, buffer_pixels + img_size)
        img_cropped = img_buffered.crop(crop_box)
        
        # Resize to standard tile size
        if scale > 1:
            img_final = img_cropped.resize((self.tile_size, self.tile_size), Image.Resampling.LANCZOS)
        else:
            img_final = img_cropped
        
        return img_final
    
    def generate_tiles(self, min_zoom, max_zoom):
        """Generate tiles for all zoom levels"""
        print(f"Generating tiles for zoom levels {min_zoom} to {max_zoom}\n")
        
        bounds = self.get_bounds()
        min_lon, min_lat, max_lon, max_lat = bounds
        print(f"Data bounds: [{min_lon:.4f}, {min_lat:.4f}] to [{max_lon:.4f}, {max_lat:.4f}]\n")
        
        total_tiles = 0
        total_empty_tiles = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            print(f"Processing zoom level {zoom}...")
            
            # Calculate tile range
            min_tile = mercantile.tile(min_lon, max_lat, zoom)
            max_tile = mercantile.tile(max_lon, min_lat, zoom)
            
            # Add buffer
            if zoom <= 10:
                tile_buffer = 2
            elif zoom <= 14:
                tile_buffer = 1
            else:
                tile_buffer = 1
            
            buffered_min_x = min_tile.x - tile_buffer
            buffered_max_x = max_tile.x + tile_buffer
            buffered_min_y = min_tile.y - tile_buffer
            buffered_max_y = max_tile.y + tile_buffer
            
            zoom_tiles = 0
            empty_tiles = 0
            
            # Create zoom directory
            zoom_dir = self.output_dir / str(zoom)
            zoom_dir.mkdir(exist_ok=True)
            
            # Generate tiles
            for tile_x in range(buffered_min_x, buffered_max_x + 1):
                x_dir = zoom_dir / str(tile_x)
                x_dir.mkdir(exist_ok=True)
                
                for tile_y in range(buffered_min_y, buffered_max_y + 1):
                    tile_path = x_dir / f"{tile_y}.png"
                    
                    try:
                        tile = mercantile.Tile(tile_x, tile_y, zoom)
                        tile_img = self.render_tile(tile)
                        
                        if tile_img is None:
                            # Empty tile
                            tile_img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
                            empty_tiles += 1
                        
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
    
    def write_mapbox_viewer_html(self, access_token: str, port: int):
        """Create an index.html viewer"""
        bounds = self.get_bounds()
        min_lon, min_lat, max_lon, max_lat = bounds
        
        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
  <title>Lucknow Air Funnel Zones Viewer</title>
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
      font-size: 11px;
      max-height: 70vh;
      overflow-y: auto;
    }}
    .legend h3 {{ margin: 0 0 10px 0; font-size: 14px; }}
    .legend-item {{ margin: 4px 0; display: flex; align-items: center; }}
    .legend-color {{ width: 18px; height: 18px; margin-right: 8px; border: 1px solid #666; }}
    
    .info-box {{
      position: absolute;
      top: 10px;
      right: 10px;
      background: white;
      padding: 12px;
      border-radius: 5px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      font-family: Arial, sans-serif;
      font-size: 11px;
    }}
    
    .controls {{
      position: absolute;
      top: 120px;
      right: 10px;
      background: white;
      padding: 12px;
      border-radius: 5px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      font-family: Arial, sans-serif;
      font-size: 11px;
      width: 200px;
    }}
    
    .controls h4 {{ margin: 0 0 8px 0; font-size: 12px; }}
    
    .control-item {{ margin: 8px 0; }}
    .control-item label {{ display: block; margin-bottom: 4px; font-weight: bold; }}
    
    input[type="range"] {{
      width: 100%;
      margin: 5px 0;
    }}
    
    .toggle-btn {{
      background: #0066CC;
      color: white;
      border: none;
      padding: 8px 12px;
      border-radius: 3px;
      cursor: pointer;
      width: 100%;
      font-size: 11px;
      margin-top: 5px;
    }}
    
    .toggle-btn:hover {{
      background: #0052A3;
    }}
    
    .toggle-btn.off {{
      background: #666;
    }}
  </style>
</head>
<body>
  <div id="map"></div>
  
  <div class="info-box">
    <strong>Lucknow Air Funnel Zones</strong><br>
    Airport Height Restrictions<br>
    Zoom: <span id="zoom-level">10</span>
  </div>
  
  <div class="controls">
    <h4>Layer Controls</h4>
    
    <div class="control-item">
      <label>Opacity: <span id="opacity-value">50</span>%</label>
      <input type="range" id="opacity-slider" min="0" max="100" value="50">
    </div>
    
    <div class="control-item">
      <button id="toggle-layer" class="toggle-btn">Hide Zones</button>
    </div>
    
    <div class="control-item">
      <button id="reset-view" class="toggle-btn">Reset View</button>
    </div>
  </div>
  
  <div class="legend">
    <h3>Height Restrictions (AMSL)</h3>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #91302D;"></div>
      <span style="font-size: 10px;">NOC Required</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #559B33;"></div>
      <span style="font-size: 10px;">140m</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #8B36A4;"></div>
      <span style="font-size: 10px;">160m</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #CF9D2C;"></div>
      <span style="font-size: 10px;">180m</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #3A6A99;"></div>
      <span style="font-size: 10px;">200m</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #A0A0A0;"></div>
      <span style="font-size: 10px;">220m</span>
    </div>
  </div>
  <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
  <script>
    mapboxgl.accessToken = '{access_token}';
    
    // Initial bounds for data
    const dataBounds = [[{min_lon}, {min_lat}], [{max_lon}, {max_lat}]];
    const dataCenter = [{center_lon}, {center_lat}];
    
    const map = new mapboxgl.Map({{
      container: 'map',
      style: 'mapbox://styles/mapbox/satellite-streets-v12',
      center: dataCenter,
      zoom: 9.5,
      minZoom: 6,    // Allow zooming out further
      maxZoom: 18    // No maxBounds - free navigation
    }});

    map.addControl(new mapboxgl.NavigationControl(), 'top-right');
    map.addControl(new mapboxgl.FullscreenControl(), 'top-right');

    let layerVisible = true;
    
    map.on('load', () => {{
      // Fit to data bounds initially
      map.fitBounds(dataBounds, {{ padding: 80, maxZoom: 11 }});
      
      map.addSource('air-funnel-tiles', {{
        type: 'raster',
        tiles: ['http://localhost:{port}/{{z}}/{{x}}/{{y}}.png'],
        tileSize: 256,
        minzoom: 8,
        maxzoom: 18,
        bounds: [{min_lon - 0.1}, {min_lat - 0.1}, {max_lon + 0.1}, {max_lat + 0.1}]
      }});
      
      map.addLayer({{ 
        id: 'air-funnel-tiles', 
        type: 'raster', 
        source: 'air-funnel-tiles', 
        paint: {{ 
          'raster-opacity': 0.5,  // Start at 50% opacity
          'raster-fade-duration': 0
        }} 
      }});
    }});
    
    // Update zoom level display
    map.on('zoom', () => {{
      document.getElementById('zoom-level').textContent = map.getZoom().toFixed(1);
    }});
    
    // Opacity slider control
    document.getElementById('opacity-slider').addEventListener('input', (e) => {{
      const opacity = e.target.value / 100;
      map.setPaintProperty('air-funnel-tiles', 'raster-opacity', opacity);
      document.getElementById('opacity-value').textContent = e.target.value;
    }});
    
    // Toggle layer visibility
    document.getElementById('toggle-layer').addEventListener('click', () => {{
      const btn = document.getElementById('toggle-layer');
      
      if (layerVisible) {{
        map.setLayoutProperty('air-funnel-tiles', 'visibility', 'none');
        btn.textContent = 'Show Zones';
        btn.classList.add('off');
      }} else {{
        map.setLayoutProperty('air-funnel-tiles', 'visibility', 'visible');
        btn.textContent = 'Hide Zones';
        btn.classList.remove('off');
      }}
      
      layerVisible = !layerVisible;
    }});
    
    // Reset view button
    document.getElementById('reset-view').addEventListener('click', () => {{
      map.fitBounds(dataBounds, {{ padding: 80, maxZoom: 11, duration: 1000 }});
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
        """Serve the tiles output directory over HTTP and open the viewer in a browser"""
        handler_cls = partial(SimpleHTTPRequestHandler, directory=str(self.output_dir))
        server = ThreadingHTTPServer(("0.0.0.0", port), handler_cls)
        url = f"http://localhost:{port}/{index_path.name}"
        
        print(f"\nServing {self.output_dir} at http://0.0.0.0:{port} (Ctrl+C to stop)")
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
    print("=== Lucknow Air Funnel Zones Tile Generator ===")
    print("Generating tiles for airport height restriction zones\n")
    
    settings = DEFAULT_VIEW_SETTINGS
    
    try:
        # Paths
        data_path = project_root / "data" / "uttar-pradesh" / "lucknow" / "air_funnel_zones" / "Lucknow.geojson"
        output_dir = project_root / "lucknow_air_funnel_tiles"
        
        # Initialize generator
        generator = LucknowAirFunnelTileGenerator(
            data_path=data_path,
            output_dir=output_dir
        )
        
        # Load data
        generator.load_data()
        
        # Generate tiles
        print(f"Generating tiles for zoom levels {settings['min_zoom']} to {settings['max_zoom']}\n")
        tiles_generated = generator.generate_tiles(min_zoom=settings["min_zoom"], max_zoom=settings["max_zoom"])
        
        if tiles_generated == 0:
            print("\nError: No tiles were generated. Please check that the data file exists:")
            print(f"  - {data_path}")
            sys.exit(1)
        
        # Create viewer and start server
        if settings["view"]:
            token = settings["token"]
            port = settings["port"]
            if not token:
                print("Error: Set DEFAULT_VIEW_SETTINGS['token'] to a valid Mapbox access token to use the viewer.")
                sys.exit(1)
            
            print()
            index_path = generator.write_mapbox_viewer_html(token, port)
            generator.serve_tiles_and_open_browser(port, index_path)
    
    except Exception as e:
        print(f"Error in main: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

