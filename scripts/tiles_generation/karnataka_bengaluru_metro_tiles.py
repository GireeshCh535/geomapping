#!/usr/bin/env python3
"""
Fixed script to generate high-quality PNG tiles from Karnataka Bengaluru Metro GeoJSON
Creates tiles with color-coded metro lines and station markers
Includes robust geometry processing, spatial indexing, and anti-aliasing
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KarnatakaBengaluruMetroTileGenerator:
    def __init__(self, data_dir, output_dir, skip_existing=True):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.skip_existing = skip_existing
        
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
        
        # Geometry processing parameters
        self.buffer_factor = 0.0001
        self.precision_threshold = 1e-6
        self.simplification_tolerance = 0.00001
        
        # Data storage
        self.gdf = None
        self.spatial_index = None
        self.unary_union = None
        
        # Load and process data
        self.load_and_process_data()
    
    def fix_self_intersections(self, geom):
        """Fix self-intersecting geometries"""
        try:
            if not geom.is_valid:
                geom = make_valid(geom)
                if geom.is_empty:
                    return None
            return geom
        except Exception as e:
            logger.warning(f"Error fixing self-intersections: {e}")
            try:
                # Try buffer(0) method
                geom = geom.buffer(0)
                if geom.is_empty:
                    return None
                return geom
            except Exception as e2:
                logger.warning(f"Buffer method also failed: {e2}")
                return None
    
    def simplify_dense_geometry(self, geom, max_points=1000):
        """Simplify geometries with too many points"""
        try:
            if geom.geom_type == 'LineString':
                if len(geom.coords) > max_points:
                    # Simplify the geometry
                    simplified = geom.simplify(self.simplification_tolerance)
                    if simplified.is_empty:
                        return geom
                    return simplified
            elif geom.geom_type == 'MultiLineString':
                simplified_geoms = []
                for g in geom.geoms:
                    if len(g.coords) > max_points:
                        simplified = g.simplify(self.simplification_tolerance)
                        if not simplified.is_empty:
                            simplified_geoms.append(simplified)
                    else:
                        simplified_geoms.append(g)
                if simplified_geoms:
                    return MultiLineString(simplified_geoms)
                else:
                    return geom
            return geom
        except Exception as e:
            logger.warning(f"Error simplifying geometry: {e}")
            return geom
    
    def round_coordinates(self, geom):
        """Round coordinates to specified precision and remove duplicates"""
        try:
            if geom.geom_type == 'LineString':
                coords = list(geom.coords)
                # Round coordinates
                rounded_coords = [(round(x, 6), round(y, 6)) for x, y in coords]
                # Remove consecutive duplicates
                filtered_coords = [rounded_coords[0]]
                for coord in rounded_coords[1:]:
                    if coord != filtered_coords[-1]:
                        filtered_coords.append(coord)
                if len(filtered_coords) >= 2:
                    return LineString(filtered_coords)
                else:
                    return None
            elif geom.geom_type == 'MultiLineString':
                filtered_geoms = []
                for g in geom.geoms:
                    rounded = self.round_coordinates(g)
                    if rounded is not None:
                        filtered_geoms.append(rounded)
                if filtered_geoms:
                    return MultiLineString(filtered_geoms)
                else:
                    return None
            return geom
        except Exception as e:
            logger.warning(f"Error rounding coordinates: {e}")
            return geom
    
    def handle_closed_loop(self, geom):
        """Ensure closed LineString geometries are properly closed"""
        try:
            if geom.geom_type == 'LineString':
                coords = list(geom.coords)
                if len(coords) >= 3:
                    # Check if first and last coordinates are the same
                    if coords[0] != coords[-1]:
                        # Close the loop
                        coords.append(coords[0])
                    return LineString(coords)
            return geom
        except Exception as e:
            logger.warning(f"Error handling closed loop: {e}")
            return geom
    
    def load_and_process_data(self):
        """Load and process the metro GeoJSON data"""
        logger.info("Loading metro data...")
        
        # Load the GeoJSON file
        geojson_path = self.data_dir / "Bangalore Metro Phases 1,2,2A&2B.geojson"
        if not geojson_path.exists():
            raise FileNotFoundError(f"Metro data file not found: {geojson_path}")
        
        self.gdf = gpd.read_file(geojson_path)
        logger.info(f"Loaded {len(self.gdf)} metro lines")
        
        # Ensure CRS is WGS84
        if self.gdf.crs is None:
            self.gdf.crs = 'EPSG:4326'
        elif self.gdf.crs != 'EPSG:4326':
            self.gdf = self.gdf.to_crs('EPSG:4326')
        
        # Process geometries
        logger.info("Processing geometries...")
        processed_geometries = []
        
        for idx, row in self.gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            
            # Apply geometry fixes
            geom = self.fix_self_intersections(geom)
            if geom is None or geom.is_empty:
                continue
            
            geom = self.handle_closed_loop(geom)
            geom = self.simplify_dense_geometry(geom)
            geom = self.round_coordinates(geom)
            
            if geom is not None and not geom.is_empty:
                processed_geometries.append(geom)
            else:
                processed_geometries.append(row.geometry)  # Keep original if processing failed
        
        # Update geometries
        self.gdf.geometry = processed_geometries
        
        # Remove invalid geometries
        valid_mask = self.gdf.geometry.notna() & ~self.gdf.geometry.is_empty
        self.gdf = self.gdf[valid_mask].copy()
        
        logger.info(f"Processed {len(self.gdf)} valid metro lines")
        
        # Build spatial index
        logger.info("Building spatial index...")
        self.spatial_index = self.gdf.sindex
        
        # Create unary union for overall bounds
        self.unary_union = unary_union(self.gdf.geometry.values)
        
        logger.info("Data processing completed")
    
    def get_metro_line_width(self, zoom):
        """Get line width for metro lines based on zoom level"""
        if zoom <= 8:
            return 2
        elif zoom <= 10:
            return 3
        elif zoom <= 12:
            return 4
        elif zoom <= 14:
            return 6
        elif zoom <= 16:
            return 8
        else:
            return 10
    
    def get_station_size(self, zoom):
        """Get station marker size based on zoom level"""
        if zoom <= 8:
            return 2
        elif zoom <= 10:
            return 3
        elif zoom <= 12:
            return 4
        elif zoom <= 14:
            return 6
        elif zoom <= 16:
            return 8
        else:
            return 10
    
    def get_features_for_tile(self, tile_bounds):
        """Get features that intersect with the tile bounds using spatial index"""
        try:
            # Create a buffered tile polygon for intersection
            buffer = 0.001
            tile_polygon = box(
                tile_bounds.west - buffer,
                tile_bounds.south - buffer,
                tile_bounds.east + buffer,
                tile_bounds.north + buffer
            )
            
            # Use spatial index for efficient intersection
            possible_matches_index = list(self.spatial_index.intersection(tile_polygon.bounds))
            possible_matches = self.gdf.iloc[possible_matches_index]
            
            # Refine with actual intersection
            intersecting_features = possible_matches[possible_matches.intersects(tile_polygon)]
            
            return intersecting_features
        except Exception as e:
            logger.warning(f"Error getting features for tile: {e}")
            return self.gdf.iloc[0:0]  # Return empty DataFrame
    
    def clip_geometry_to_tile(self, geom, tile_bounds):
        """Clip geometry to tile bounds"""
        try:
            # Create tile polygon with small buffer
            buffer = 0.0001
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
                    if g.geom_type in ['LineString', 'MultiLineString']:
                        if g.geom_type == 'LineString':
                            lines.append(g)
                        else:
                            lines.extend(g.geoms)
                if lines:
                    return MultiLineString(lines) if len(lines) > 1 else lines[0]
                return None
            
            return None
        except Exception as e:
            logger.warning(f"Error clipping geometry: {e}")
            return None
    
    def coords_to_pixels(self, coords, tile_bounds, tile_x, tile_y, zoom):
        """Convert geographic coordinates to pixel coordinates with subpixel precision"""
        pixels = []
        for lon, lat in coords:
            # Clamp latitude to avoid math domain error
            lat = max(-85.051129, min(85.051129, lat))
            
            # Convert to tile coordinates
            tile_lon = (lon + 180) / 360 * (2 ** zoom)
            tile_lat = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * (2 ** zoom)
            
            # Convert to pixel coordinates within the tile
            pixel_x = (tile_lon - tile_x) * 256
            pixel_y = (tile_lat - tile_y) * 256
            
            pixels.append((pixel_x, pixel_y))
        
        return pixels
    
    def draw_metro_line(self, draw, pixels, color_rgb, width):
        """Draw metro line with anti-aliasing"""
        if len(pixels) < 2:
            return
        
        # Draw line segments
        for i in range(len(pixels) - 1):
            start = pixels[i]
            end = pixels[i + 1]
            
            # Clip to tile bounds
            if (0 <= start[0] <= 256 and 0 <= start[1] <= 256) or \
               (0 <= end[0] <= 256 and 0 <= end[1] <= 256):
                draw.line([start, end], fill=color_rgb, width=width)
    
    def draw_station_marker(self, draw, pixel, color_rgb, size):
        """Draw station marker"""
        x, y = pixel
        if 0 <= x <= 256 and 0 <= y <= 256:
            # Draw a filled circle for the station
            bbox = [x - size, y - size, x + size, y + size]
            draw.ellipse(bbox, fill=color_rgb, outline='white', width=1)
    
    def generate_tile(self, x, y, zoom):
        """Generate a single tile"""
        try:
            # Get tile bounds
            tile_bounds = mercantile.bounds(x, y, zoom)
            
            # Get features for this tile
            features = self.get_features_for_tile(tile_bounds)
            
            if features.empty:
                return None
            
            # Determine scale for anti-aliasing
            scale = 2 if zoom >= 12 else 1
            tile_size = 256 * scale
            
            # Create high-resolution image
            img = Image.new('RGBA', (tile_size, tile_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Get line width and station size
            line_width = self.get_metro_line_width(zoom) * scale
            station_size = self.get_station_size(zoom) * scale
            
            # Collect station coordinates
            station_coords = set()
            
            # Draw metro lines
            for idx, feature in features.iterrows():
                geom = feature.geometry
                line_color = feature.get('linecolour', 'Blue')
                color = self.color_mapping.get(line_color, '#0066CC')
                color_rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
                
                # Clip geometry to tile
                clipped_geom = self.clip_geometry_to_tile(geom, tile_bounds)
                if clipped_geom is None:
                    continue
                
                # Convert to pixels
                if clipped_geom.geom_type == 'LineString':
                    pixels = self.coords_to_pixels(list(clipped_geom.coords), tile_bounds, x, y, zoom)
                    if len(pixels) >= 2:
                        self.draw_metro_line(draw, pixels, color_rgb, line_width)
                        # Add start and end points as stations
                        station_coords.add(pixels[0])
                        station_coords.add(pixels[-1])
                elif clipped_geom.geom_type == 'MultiLineString':
                    for line in clipped_geom.geoms:
                        pixels = self.coords_to_pixels(list(line.coords), tile_bounds, x, y, zoom)
                        if len(pixels) >= 2:
                            self.draw_metro_line(draw, pixels, color_rgb, line_width)
                            # Add start and end points as stations
                            station_coords.add(pixels[0])
                            station_coords.add(pixels[-1])
            
            # Draw station markers
            station_color_rgb = tuple(int(self.station_color[i:i+2], 16) for i in (1, 3, 5))
            for pixel in station_coords:
                self.draw_station_marker(draw, pixel, station_color_rgb, station_size)
            
            # Downscale if needed
            if scale > 1:
                img = img.resize((256, 256), Image.Resampling.LANCZOS)
                # Apply smoothing filter for higher zooms
                if zoom >= 14:
                    img = img.filter(ImageFilter.SMOOTH_MORE)
            
            return img
            
        except Exception as e:
            logger.error(f"Error generating tile {zoom}/{x}/{y}: {e}")
            return None
    
    def generate_tiles(self, min_zoom, max_zoom):
        """Generate tiles for specified zoom levels"""
        logger.info(f"Generating tiles for zoom levels {min_zoom} to {max_zoom}")
        
        # Get bounds of all features
        bounds = self.gdf.total_bounds
        min_lon, min_lat, max_lon, max_lat = bounds
        
        total_tiles = 0
        generated_tiles = 0
        skipped_tiles = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            logger.info(f"Processing zoom level {zoom}...")
            
            # Calculate tile range
            min_tile = mercantile.tile(min_lon, min_lat, zoom)
            max_tile = mercantile.tile(max_lon, max_lat, zoom)
            
            zoom_tiles = 0
            zoom_generated = 0
            zoom_skipped = 0
            
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
                    total_tiles += 1
                    
                    # Check if tile already exists
                    if tile_path.exists() and not self.skip_existing:
                        zoom_skipped += 1
                        skipped_tiles += 1
                        continue
                    
                    try:
                        tile_img = self.generate_tile(x, y, zoom)
                        
                        if tile_img is not None:
                            # Check if tile has content
                            has_content = False
                            for pixel in tile_img.getdata():
                                if len(pixel) == 4 and pixel[3] > 0:  # RGBA with alpha > 0
                                    has_content = True
                                    break
                                elif len(pixel) == 3:  # RGB
                                    has_content = True
                                    break
                            
                            if has_content:
                                tile_img.save(tile_path, 'PNG')
                                zoom_generated += 1
                                generated_tiles += 1
                            else:
                                zoom_skipped += 1
                                skipped_tiles += 1
                        else:
                            zoom_skipped += 1
                            skipped_tiles += 1
                            
                    except Exception as e:
                        logger.error(f"Error processing tile {zoom}/{x}/{y}: {e}")
                        zoom_skipped += 1
                        skipped_tiles += 1
                
                # Log progress every 1000 tiles
                if total_tiles % 1000 == 0:
                    logger.info(f"Processed {total_tiles} tiles, generated {generated_tiles}, skipped {skipped_tiles}")
            
            logger.info(f"Zoom level {zoom}: Generated {zoom_generated} tiles, skipped {zoom_skipped}")
        
        logger.info("Tile generation completed!")
        logger.info(f"Total tiles processed: {total_tiles}")
        logger.info(f"Tiles generated: {generated_tiles}")
        logger.info(f"Tiles skipped: {skipped_tiles}")
        
        return generated_tiles
    
    def create_viewer_html(self):
        """Create HTML viewer for the tiles"""
        logger.info("Creating viewer.html...")
        
        # Get bounds
        bounds = self.gdf.total_bounds
        min_lon, min_lat, max_lon, max_lat = bounds
        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Karnataka Bengaluru Metro - Fixed PNG Tiles</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ height: 100vh; width: 100%; }}
        .info {{
            position: fixed;
            top: 10px;
            right: 10px;
            background: white;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            z-index: 1000;
            font-family: Arial, sans-serif;
        }}
        .info h3 {{ margin-top: 0; color: #333; }}
        .info p {{ margin: 5px 0; color: #666; }}
        .legend {{
            position: fixed;
            bottom: 10px;
            right: 10px;
            background: white;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            z-index: 1000;
            font-family: Arial, sans-serif;
        }}
        .legend h4 {{ margin-top: 0; color: #333; }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 5px 0;
        }}
        .legend-color {{
            width: 20px;
            height: 3px;
            margin-right: 10px;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    
    <div class="info">
        <h3>Karnataka Bengaluru Metro</h3>
        <p><strong>Fixed Tiles</strong></p>
        <p>Robust geometry processing</p>
        <p>Spatial indexing</p>
        <p>Anti-aliasing</p>
        <p>Bounds: {min_lon:.4f}, {min_lat:.4f} to {max_lon:.4f}, {max_lat:.4f}</p>
    </div>
    
    <div class="legend">
        <h4>Metro Lines</h4>
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
    
    <script>
        // Initialize map
        var map = L.map('map').setView([{center_lat}, {center_lon}], 11);
        
        // Add base layer
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors'
        }}).addTo(map);
        
        // Add metro layer
        const metroLayer = L.tileLayer('http://localhost:3000/{{z}}/{{x}}/{{y}}.png', {{
            attribution: 'Karnataka Bengaluru Metro - Fixed Tiles',
            opacity: 0.8
        }});
        
        metroLayer.addTo(map);
        
        // Add layer control
        var baseMaps = {{
            "OpenStreetMap": L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '© OpenStreetMap contributors'
            }})
        }};
        
        var overlayMaps = {{
            "Metro Lines": metroLayer
        }};
        
        L.control.layers(baseMaps, overlayMaps).addTo(map);
    </script>
</body>
</html>"""
        
        with open(self.output_dir / "viewer.html", "w") as f:
            f.write(html_content)
        
        logger.info("Created viewer.html")
    
    def create_tilejson(self):
        """Create TileJSON file"""
        logger.info("Creating tilejson.json...")
        
        # Get bounds
        bounds = self.gdf.total_bounds
        min_lon, min_lat, max_lon, max_lat = bounds
        
        tilejson = {
            "tilejson": "3.0.0",
            "name": "Karnataka Bengaluru Metro - Fixed Tiles",
            "description": "High-quality metro tiles with robust geometry processing",
            "version": "1.0.0",
            "attribution": "Karnataka Bengaluru Metro",
            "template": "http://localhost:3000/{z}/{x}/{y}.png",
            "tiles": ["http://localhost:3000/{z}/{x}/{y}.png"],
            "minzoom": 4,
            "maxzoom": 18,
            "bounds": [min_lon, min_lat, max_lon, max_lat],
            "center": [(min_lon + max_lon) / 2, (min_lat + max_lat) / 2, 11]
        }
        
        with open(self.output_dir / "tilejson.json", "w") as f:
            json.dump(tilejson, f, indent=2)
        
        logger.info("Created tilejson.json")
    
    def print_help(self):
        """Print help information"""
        print("""
Karnataka Bengaluru Metro Tile Generator - Fixed Version

This script generates high-quality PNG tiles from Karnataka Bengaluru Metro GeoJSON data.

Key Features:
- Robust geometry processing (fixes self-intersections, simplifies dense geometries)
- Spatial indexing for efficient tile generation
- Anti-aliasing for smooth lines
- Color-coded metro lines (Blue, Purple, Green, Yellow, Pink)
- Station markers at line endpoints
- Proper coordinate precision handling

Usage:
    python karnataka_bengaluru_metro_tiles_fixed.py [options]

Options:
    --force              Force regeneration of existing tiles
    --min-zoom ZOOM      Minimum zoom level (default: 4)
    --max-zoom ZOOM      Maximum zoom level (default: 18)

Output:
    - PNG tiles in z/x/y format
    - viewer.html for local testing
    - tilejson.json for tile metadata

The script processes the metro data to fix common geometry issues and generates
high-quality tiles suitable for web mapping applications.
        """)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Generate Karnataka Bengaluru Metro tiles')
    parser.add_argument('--force', action='store_true', help='Force regeneration of existing tiles')
    parser.add_argument('--min-zoom', type=int, default=4, help='Minimum zoom level')
    parser.add_argument('--max-zoom', type=int, default=18, help='Maximum zoom level')
    parser.add_argument('--help-detailed', action='store_true', help='Show detailed help')
    
    args = parser.parse_args()
    
    if args.help_detailed:
        generator = KarnatakaBengaluruMetroTileGenerator.__new__(KarnatakaBengaluruMetroTileGenerator)
        generator.print_help()
        return
    
    try:
        # Set up paths
        data_dir = Path(__file__).parent.parent.parent / "data/karnataka/bengaluru/metro"
        output_dir = Path(__file__).parent.parent.parent / "karnataka_bengaluru_metro_tiles"
        
        # Initialize generator
        generator = KarnatakaBengaluruMetroTileGenerator(
            data_dir=data_dir,
            output_dir=output_dir,
            skip_existing=not args.force
        )
        
        # Generate tiles
        generated_count = generator.generate_tiles(args.min_zoom, args.max_zoom)
        
        # Create supporting files
        generator.create_viewer_html()
        generator.create_tilejson()
        
        logger.info("Karnataka Bengaluru Metro tile generation completed!")
        logger.info(f"Total tiles generated: {generated_count}")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    main()
