#!/usr/bin/env python3
"""
Karnataka Bengaluru Metro Tile Generator - Fixed Version with Blank Tiles
Generates high-quality PNG tiles from metro GeoJSON data with perfect alignment
Includes empty border tiles to prevent edge bleeding
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
import argparse
from shapely.geometry import shape, LineString, MultiLineString, Point, box
from shapely.ops import transform, unary_union
from shapely.validation import make_valid
import pyproj
from functools import partial
import geopandas as gpd
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import webbrowser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KarnatakaBengaluruMetroTileGenerator:
    def __init__(self, data_dir, output_dir, force_overwrite=True):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.force_overwrite = force_overwrite
        
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
        
        # Station marker color
        self.station_color = '#FF0000'
        
        # Data storage
        self.gdf = None
        self.spatial_index = None
        
        # Load and process data
        self.load_and_process_data()
        
        # Calculate data bounds once
        self.data_bounds = self.calculate_data_bounds()
    
    def calculate_data_bounds(self):
        """Calculate the actual bounds of the metro data (without buffer)"""
        if self.gdf is None or self.gdf.empty:
            return None
        
        bounds = self.gdf.total_bounds
        return tuple(bounds)  # (min_lon, min_lat, max_lon, max_lat)
    
    def clean_geometry(self, geom):
        """Clean and validate geometry"""
        try:
            if geom is None or geom.is_empty:
                return None
            
            # Make valid if needed
            if not geom.is_valid:
                geom = make_valid(geom)
                if geom is None or geom.is_empty:
                    return None
            
            # Handle different geometry types
            if geom.geom_type == 'LineString':
                coords = list(geom.coords)
                if len(coords) < 2:
                    return None
                # Remove duplicate consecutive points
                clean_coords = [coords[0]]
                for coord in coords[1:]:
                    if coord != clean_coords[-1]:
                        clean_coords.append(coord)
                if len(clean_coords) >= 2:
                    return LineString(clean_coords)
                return None
                
            elif geom.geom_type == 'MultiLineString':
                clean_lines = []
                for line in geom.geoms:
                    cleaned = self.clean_geometry(line)
                    if cleaned is not None:
                        clean_lines.append(cleaned)
                if clean_lines:
                    return MultiLineString(clean_lines) if len(clean_lines) > 1 else clean_lines[0]
                return None
            
            return geom
        except Exception as e:
            logger.warning(f"Error cleaning geometry: {e}")
            return None
    
    def load_and_process_data(self):
        """Load and process the metro GeoJSON data"""
        logger.info("Loading metro data...")
        
        # Load the GeoJSON file
        geojson_path = self.data_dir / "Bangalore Metro Phases 1,2,2A&2B.geojson"
        if not geojson_path.exists():
            raise FileNotFoundError(f"Metro data file not found: {geojson_path}")
        
        self.gdf = gpd.read_file(geojson_path)
        logger.info(f"Loaded {len(self.gdf)} metro features")
        
        # Ensure CRS is WGS84
        if self.gdf.crs is None:
            self.gdf.crs = 'EPSG:4326'
        elif self.gdf.crs != 'EPSG:4326':
            self.gdf = self.gdf.to_crs('EPSG:4326')
        
        # Clean geometries
        logger.info("Cleaning geometries...")
        cleaned_geometries = []
        for idx, row in self.gdf.iterrows():
            cleaned_geom = self.clean_geometry(row.geometry)
            cleaned_geometries.append(cleaned_geom)
        
        # Update geometries and remove invalid ones
        self.gdf.geometry = cleaned_geometries
        valid_mask = self.gdf.geometry.notna() & ~self.gdf.geometry.is_empty
        self.gdf = self.gdf[valid_mask].copy()
        
        logger.info(f"Processed {len(self.gdf)} valid metro features")
        
        # Build spatial index
        logger.info("Building spatial index...")
        self.spatial_index = self.gdf.sindex
        
        # Extract station/junction points from line endpoints
        logger.info("Extracting station/junction coordinates...")
        self.extract_stations_from_lines()
        
        logger.info("Data processing completed")
    
    def extract_stations_from_lines(self):
        """Extract station/junction coordinates from line endpoints"""
        self.stations = {}  # Dictionary: station_name -> (lon, lat)
        
        for idx, row in self.gdf.iterrows():
            geometry = row.geometry
            
            if geometry is None or geometry.is_empty:
                continue
            
            try:
                # Get junction names
                from_junction = row.get('fromjunction', '')
                to_junction = row.get('tojunction', '')
                
                # Extract coordinates from geometry
                if geometry.geom_type == 'LineString':
                    coords = list(geometry.coords)
                    if len(coords) >= 2:
                        # First point is from_junction
                        if from_junction and from_junction.strip():
                            self.stations[from_junction.strip()] = coords[0]
                        # Last point is to_junction
                        if to_junction and to_junction.strip():
                            self.stations[to_junction.strip()] = coords[-1]
                
                elif geometry.geom_type == 'MultiLineString':
                    # For MultiLineString, use first line's start and last line's end
                    if len(geometry.geoms) > 0:
                        first_line = geometry.geoms[0]
                        last_line = geometry.geoms[-1]
                        
                        first_coords = list(first_line.coords)
                        last_coords = list(last_line.coords)
                        
                        if len(first_coords) >= 2 and from_junction and from_junction.strip():
                            self.stations[from_junction.strip()] = first_coords[0]
                        
                        if len(last_coords) >= 2 and to_junction and to_junction.strip():
                            self.stations[to_junction.strip()] = last_coords[-1]
            
            except Exception as e:
                logger.warning(f"Error extracting stations from feature {idx}: {e}")
                continue
        
        logger.info(f"Extracted {len(self.stations)} unique station/junction points")
        
        # Log some station names for verification
        if self.stations:
            sample_stations = list(self.stations.keys())[:5]
            logger.info(f"Sample stations: {', '.join(sample_stations)}")
    
    def get_line_width(self, zoom):
        """Get line width based on zoom level (thicker lines)"""
        line_widths = {
            4: 2, 5: 2, 6: 2, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3, 
            12: 4, 13: 4, 14: 5, 15: 5, 16: 6, 17: 7, 18: 8
        }
        return line_widths.get(zoom, 4)
    
    def get_station_size(self, zoom):
        """Get station marker size based on zoom level (larger dots)"""
        station_sizes = {
            4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 2, 11: 3, 
            12: 4, 13: 5, 14: 6, 15: 7, 16: 8, 17: 9, 18: 10
        }
        return station_sizes.get(zoom, 0)
    
    def get_features_for_tile(self, tile_bounds):
        """Get features that intersect with the tile bounds"""
        try:
            # Create tile polygon with buffer for intersection
            buffer = 0.001  # ~100m buffer
            tile_polygon = box(
                tile_bounds.west - buffer,
                tile_bounds.south - buffer,
                tile_bounds.east + buffer,
                tile_bounds.north + buffer
            )
            
            # Use spatial index for efficient intersection
            possible_matches_index = list(self.spatial_index.intersection(tile_polygon.bounds))
            if not possible_matches_index:
                return self.gdf.iloc[0:0]  # Return empty DataFrame
            
            possible_matches = self.gdf.iloc[possible_matches_index]
            
            # Refine with actual intersection
            intersecting_features = possible_matches[possible_matches.intersects(tile_polygon)]
            
            return intersecting_features
        except Exception as e:
            logger.warning(f"Error getting features for tile: {e}")
            return self.gdf.iloc[0:0]  # Return empty DataFrame
    
    def tile_has_data(self, tile_x, tile_y, zoom):
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
        
        # Check if any features intersect with this tile
        if not self.gdf.empty:
            for _, row in self.gdf.iterrows():
                if row.geometry and row.geometry.intersects(tile_box):
                    return True
        
        return False
    
    def clip_geometry_to_tile(self, geom, tile_bounds):
        """Clip geometry to tile bounds with proper handling"""
        try:
            # Create tile polygon with small buffer to ensure lines aren't cut off
            buffer = 0.0001  # ~10m buffer
            tile_polygon = box(
                tile_bounds.west - buffer,
                tile_bounds.south - buffer,
                tile_bounds.east + buffer,
                tile_bounds.north + buffer
            )
            
            # Clip geometry
            clipped = geom.intersection(tile_polygon)
            
            if clipped.is_empty:
                return None
            
            # Handle different geometry types
            if clipped.geom_type == 'LineString':
                return clipped
            elif clipped.geom_type == 'MultiLineString':
                return clipped
            elif clipped.geom_type == 'GeometryCollection':
                # Extract LineString and MultiLineString from collection
                lines = []
                for g in clipped.geoms:
                    if g.geom_type == 'LineString':
                        lines.append(g)
                    elif g.geom_type == 'MultiLineString':
                        lines.extend(g.geoms)
                if lines:
                    return MultiLineString(lines) if len(lines) > 1 else lines[0]
                return None
            
            return None
        except Exception as e:
            logger.warning(f"Error clipping geometry: {e}")
            return None
    
    def coords_to_pixels(self, coords, tile_bounds, tile_x, tile_y, zoom):
        """Convert geographic coordinates to pixel coordinates with proper tile alignment"""
        pixels = []
        for lon, lat in coords:
            # Clamp latitude to avoid math domain error
            lat = max(-85.051129, min(85.051129, lat))
            
            # Convert to tile coordinates using Web Mercator projection
            # This ensures perfect alignment with standard web map tiles
            tile_lon = (lon + 180) / 360 * (2 ** zoom)
            tile_lat = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * (2 ** zoom)
            
            # Convert to pixel coordinates within the tile
            pixel_x = (tile_lon - tile_x) * 256
            pixel_y = (tile_lat - tile_y) * 256
            
            pixels.append((pixel_x, pixel_y))
        
        return pixels
    
    def draw_line_antialiased(self, draw, coordinates, color, width, tile_x, tile_y, zoom):
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
    
    def draw_station_marker(self, draw, lon: float, lat: float, size: int, tile_x: int, tile_y: int, zoom: int):
        """Draw a station marker on the tile (larger with better border)"""
        if size <= 0:
            return
            
        pixel_x, pixel_y = self.wgs84_to_tile_pixel(lon, lat, tile_x, tile_y, zoom)
        
        padding = size + 10
        if -padding <= pixel_x <= 256 + padding and -padding <= pixel_y <= 256 + padding:
            px, py = round(pixel_x), round(pixel_y)
            
            # White background (thicker border)
            white_size = size + 2
            white_bbox = [px - white_size, py - white_size, px + white_size, py + white_size]
            draw.ellipse(white_bbox, fill='white', outline=None)
            
            # Red station marker
            bbox = [px - size, py - size, px + size, py + size]
            draw.ellipse(bbox, fill=self.station_color, outline=None)
    
    def generate_tile(self, x, y, zoom, force_empty=False):
        """Generate a single tile (identical to Hyderabad Metro)"""
        # Create transparent tile
        img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        
        # If forced empty, return the transparent tile
        if force_empty:
            return img
        
        draw = ImageDraw.Draw(img, 'RGBA')
        tile_bounds = mercantile.bounds(x, y, zoom)
        
        line_width = self.get_line_width(zoom)
        station_size = self.get_station_size(zoom)
        
        buffer_deg = 0.001
        tile_box = box(
            tile_bounds.west - buffer_deg,
            tile_bounds.south - buffer_deg,
            tile_bounds.east + buffer_deg,
            tile_bounds.north + buffer_deg
        )
        
        # Draw metro lines
        if not self.gdf.empty:
            for idx, row in self.gdf.iterrows():
                geometry = row.geometry
                
                if geometry is None:
                    continue
                
                try:
                    if geometry.intersects(tile_box):
                        line_color = row.get('linecolour', 'Blue')
                        color = self.color_mapping.get(line_color, '#0066CC')
                        
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
        
        # Draw station markers (junctions)
        if station_size > 0 and hasattr(self, 'stations') and self.stations:
            for station_name, (lon, lat) in self.stations.items():
                try:
                    # Create point for intersection check
                    station_point = Point(lon, lat)
                    
                    if station_point.intersects(tile_box):
                        self.draw_station_marker(draw, lon, lat, station_size, x, y, zoom)
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
        """Create index.html with Mapbox GL JS viewer (identical to Hyderabad Metro)"""
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
  <title>Bengaluru Metro Tiles Viewer</title>
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
    <strong>Bengaluru Metro</strong><br>
    Zoom: <span id="zoom-level">11</span>
  </div>
  <div class="legend">
    <h3>Metro Lines</h3>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #0066CC;"></div>
      <span>Blue Line</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #800080;"></div>
      <span>Purple Line</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #00AA00;"></div>
      <span>Green Line</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #FFD700;"></div>
      <span>Yellow Line</span>
    </div>
    <div class="legend-item">
      <div class="legend-color" style="background-color: #FF69B4;"></div>
      <span>Pink Line</span>
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
        minzoom: 4,
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
    
    def create_tilejson(self):
        """Create TileJSON file"""
        logger.info("Creating tilejson.json...")
        
        # Get bounds
        bounds = self.gdf.total_bounds
        min_lon, min_lat, max_lon, max_lat = bounds
        
        tilejson = {
            "tilejson": "3.0.0",
            "name": "Karnataka Bengaluru Metro",
            "description": "High-quality metro tiles with empty border tiles",
            "version": "1.0.0",
            "attribution": "Karnataka Bengaluru Metro",
            "template": "./{z}/{x}/{y}.png",
            "tiles": ["./{z}/{x}/{y}.png"],
            "minzoom": 4,
            "maxzoom": 18,
            "bounds": [min_lon, min_lat, max_lon, max_lat],
            "center": [(min_lon + max_lon) / 2, (min_lat + max_lat) / 2, 11]
        }
        
        with open(self.output_dir / "tilejson.json", "w") as f:
            json.dump(tilejson, f, indent=2)
        
        logger.info("Created tilejson.json")
    
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
    """Main function - Identical behavior to Hyderabad Metro script"""
    # Default settings (same structure as Hyderabad)
    DEFAULT_VIEW_SETTINGS = {
        "min_zoom": 4,
        "max_zoom": 18,
        "view": True,  # Auto-start server by default
        "port": 8002,  # Different port than Hyderabad (8001) to avoid conflicts
        "token": "pk.eyJ1IjoiYXYxYWNyZSIsImEiOiJjbTJtZmdxN3owa2FzMmpyMjJ4OHV5MHhzIn0.FXpMd91JSER-r7LVpSZN-A"
    }
    
    print("=== Bengaluru Metro Tile Generator (Enhanced) ===")
    print("Generating tiles with empty border tiles to prevent edge bleeding\n")
    
    settings = DEFAULT_VIEW_SETTINGS
    
    try:
        # Set up paths - get project root directory
        # Script is at: scripts/tiles_generation/karnataka_bengaluru_metro_tiles.py
        # Project root is 3 levels up from script
        script_path = Path(__file__).resolve()
        project_root = script_path.parent.parent.parent
        
        data_dir = project_root / "data" / "karnataka" / "bengaluru" / "metro"
        output_dir = project_root / "karnataka_bengaluru_metro_tiles"
        
        # Initialize generator
        generator = KarnatakaBengaluruMetroTileGenerator(
            data_dir=data_dir,
            output_dir=output_dir,
            force_overwrite=True
        )
        
        print(f"Generating tiles for zoom levels {settings['min_zoom']} to {settings['max_zoom']}\n")
        
        # Generate tiles
        tiles_generated = generator.generate_tiles(min_zoom=settings["min_zoom"], max_zoom=settings["max_zoom"])
        
        if tiles_generated == 0:
            print("\nError: No tiles were generated. Please check that the data files exist:")
            print(f"  - {data_dir / 'Bangalore Metro Phases 1,2,2A&2B.geojson'}")
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