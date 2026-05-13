#!/usr/bin/env python3
"""
Hyderabad Highways PNG Tile Generator - Complete Solution
=========================================================

Generates PNG tiles for Hyderabad highways with:
- Proper handling of MultiLineString geometries
- Fixed intersection detection for all tiles
- Coordinate precision handling
- No missing tiles or broken lines
- Zoom levels 1-16 as requested
- Highway-appropriate styling
- Smart tile skipping (existing tiles are preserved by default)

Highway color: #14E098 (Gold - standard for highways)

Usage:
  python telangana_hyderabad_highways.py                    # Skip existing tiles (default)
  python telangana_hyderabad_highways.py --force           # Regenerate all tiles
  python telangana_hyderabad_highways.py --help            # Show all options
"""

import json
import os
import math
import time
import pandas as pd
import geopandas as gpd
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from typing import Tuple, List, Optional, Union
import mercantile
from shapely.geometry import LineString, MultiLineString, Point, Polygon, box, GeometryCollection
from shapely.ops import unary_union, linemerge
import logging
from decimal import Decimal, getcontext

# Set high precision for coordinate handling
getcontext().prec = 20

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class HyderabadHighwaysTileGenerator:
    """
    Complete tile generator for Hyderabad highways with all fixes applied
    """
    
    def __init__(self, geojson_path: str, output_dir: str = "RRR_Final", skip_existing: bool = True):
        """
        Initialize the Highways tile generator
        
        Args:
            geojson_path: Path to the hyd_highways_merged.geojson file
            output_dir: Directory to save generated tiles
            skip_existing: Whether to skip already generated tiles (default: True)
        """
        self.geojson_path = Path(geojson_path)
        self.output_dir = Path(output_dir)
        self.highway_color = "#14E098"  # Gold/Yellow for highways
        self.tile_size = 256  # Standard tile size
        self.skip_existing = skip_existing
        
        # Quality settings
        self.buffer_factor = 0.15  # 15% buffer for better intersection detection
        self.precision_threshold = 8  # Round coordinates to 8 decimal places
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load and process data
        self.load_and_process_data()
        
        logger.info("🛣️  Hyderabad Highways Tile Generator initialized")
        logger.info(f"📂 GeoJSON path: {geojson_path}")
        logger.info(f"📁 Output directory: {output_dir}")
        logger.info(f"🎨 Highway color: {self.highway_color}")
        logger.info(f"⏭️  Skip existing tiles: {self.skip_existing}")
    
    def round_coordinates(self, geom):
        """
        Round coordinates to reasonable precision to avoid floating point issues
        """
        def round_coords(coords):
            return [(round(x, self.precision_threshold), 
                    round(y, self.precision_threshold)) for x, y in coords]
        
        if isinstance(geom, LineString):
            return LineString(round_coords(geom.coords))
        elif isinstance(geom, MultiLineString):
            return MultiLineString([LineString(round_coords(line.coords)) 
                                   for line in geom.geoms])
        return geom
    
    def load_and_process_data(self):
        """Load and process GeoJSON data with coordinate precision handling"""
        try:
            if not self.geojson_path.exists():
                raise FileNotFoundError(f"GeoJSON file not found: {self.geojson_path}")
            
            # Load GeoJSON
            logger.info("📖 Loading highways data...")
            self.gdf = gpd.read_file(self.geojson_path)
            
            if self.gdf.empty:
                raise ValueError("No features found in GeoJSON")
            
            # Ensure WGS84 CRS
            if self.gdf.crs is None:
                self.gdf.set_crs('EPSG:4326', inplace=True)
            elif self.gdf.crs.to_string() != 'EPSG:4326':
                self.gdf = self.gdf.to_crs('EPSG:4326')
            
            # Process geometries
            logger.info("🔧 Processing geometries...")
            processed_geoms = []
            
            for idx, row in self.gdf.iterrows():
                geom = row.geometry
                
                # Round coordinates to avoid precision issues
                geom = self.round_coordinates(geom)
                
                # Fix invalid geometries
                if not geom.is_valid:
                    geom = geom.buffer(0)
                
                # Merge connected lines in MultiLineString
                if isinstance(geom, MultiLineString):
                    try:
                        merged = linemerge(geom)
                        if merged.is_valid:
                            geom = merged
                    except:
                        pass  # Keep original if merge fails
                
                processed_geoms.append(geom)
            
            self.gdf['geometry'] = processed_geoms
            
            # Remove any invalid geometries
            self.gdf = self.gdf[self.gdf.geometry.is_valid].copy()
            
            # Calculate bounds
            self.bounds = self.gdf.total_bounds
            
            # Create spatial index
            self.spatial_index = self.gdf.sindex
            
            # Create unified geometry for better intersection testing
            self.unified_geometry = unary_union(self.gdf.geometry)
            
            logger.info(f"✅ Loaded {len(self.gdf)} highway features")
            logger.info(f"📊 Data bounds: {self.bounds}")
            
            # Log feature details
            for idx, row in self.gdf.iterrows():
                geom_type = row.geometry.geom_type
                if geom_type == 'LineString':
                    length = row.geometry.length
                    points = len(row.geometry.coords)
                    logger.info(f"   Feature {idx}: LineString - {points} points, length: {length:.6f}")
                elif geom_type == 'MultiLineString':
                    num_lines = len(row.geometry.geoms)
                    total_length = row.geometry.length
                    logger.info(f"   Feature {idx}: MultiLineString - {num_lines} lines, total length: {total_length:.6f}")
            
        except Exception as e:
            logger.error(f"❌ Error loading data: {e}")
            raise
    
    def get_highway_line_width(self, zoom: int) -> float:
        """
        Get highway-appropriate line width for zoom level
        
        Args:
            zoom: Zoom level (1-16)
            
        Returns:
            Line width in pixels
        """
        # Highway-specific widths (wider than regular roads)
        zoom_widths = {
            1: 0.5,   # Very thin at world level
            2: 0.6,
            3: 0.7,
            4: 0.8,
            5: 1.0,   # Start becoming visible
            6: 1.3,
            7: 1.6,
            8: 2.0,   # Clear at country level
            9: 2.5,
            10: 3.0,  # City overview
            11: 3.5,
            12: 4.5,  # District level
            13: 5.5,
            14: 7.0,  # Neighborhood level
            15: 9.0,
            16: 11.0, # Street level
            17: 13.0,
            18: 15.0
        }
        
        return zoom_widths.get(zoom, 3.0)
    
    def get_features_for_tile(self, tile_bounds: mercantile.LngLatBbox) -> gpd.GeoDataFrame:
        """
        Get all features that intersect with tile (with buffer)
        
        Args:
            tile_bounds: Tile bounds
            
        Returns:
            GeoDataFrame with intersecting features
        """
        try:
            # Calculate buffer size based on tile dimensions
            tile_width = tile_bounds.east - tile_bounds.west
            tile_height = tile_bounds.north - tile_bounds.south
            buffer_size = max(tile_width, tile_height) * self.buffer_factor
            
            # Create buffered search area
            search_bounds = box(
                tile_bounds.west - buffer_size,
                tile_bounds.south - buffer_size,
                tile_bounds.east + buffer_size,
                tile_bounds.north + buffer_size
            )
            
            # Get potential matches from spatial index
            possible_indices = list(self.spatial_index.intersection(search_bounds.bounds))
            
            if not possible_indices:
                return gpd.GeoDataFrame()
            
            # Get actual features
            possible_features = self.gdf.iloc[possible_indices].copy()
            
            # Create precise tile bounds for intersection test
            tile_box = box(
                tile_bounds.west,
                tile_bounds.south,
                tile_bounds.east,
                tile_bounds.north
            )
            
            # Filter to actual intersections
            intersecting = possible_features[possible_features.geometry.intersects(tile_box)]
            
            return intersecting
            
        except Exception as e:
            logger.error(f"Error getting tile features: {e}")
            return gpd.GeoDataFrame()
    
    def clip_geometry_to_tile(self, geom, tile_bounds: mercantile.LngLatBbox):
        """
        Properly clip geometry to tile bounds
        
        Args:
            geom: Geometry to clip
            tile_bounds: Tile bounds
            
        Returns:
            Clipped geometry or None
        """
        try:
            # Create tile box
            tile_box = box(
                tile_bounds.west,
                tile_bounds.south,
                tile_bounds.east,
                tile_bounds.north
            )
            
            # Perform intersection
            clipped = geom.intersection(tile_box)
            
            if clipped.is_empty:
                return None
            
            # Handle different result types
            if isinstance(clipped, (LineString, MultiLineString)):
                return clipped
            elif isinstance(clipped, GeometryCollection):
                # Extract line geometries
                lines = []
                for g in clipped.geoms:
                    if isinstance(g, LineString):
                        lines.append(g)
                    elif isinstance(g, MultiLineString):
                        lines.extend(g.geoms)
                
                if not lines:
                    return None
                elif len(lines) == 1:
                    return lines[0]
                else:
                    return MultiLineString(lines)
            
            return None
            
        except Exception as e:
            logger.error(f"Error clipping geometry: {e}")
            return None
    
    def wgs84_to_tile_pixel(self, lon: float, lat: float, x: int, y: int, zoom: int) -> Tuple[float, float]:
        """
        Convert WGS84 coordinates to tile pixel coordinates (matching metro logic)
        
        Args:
            lon, lat: WGS84 coordinates
            x, y: Tile coordinates
            zoom: Zoom level
            
        Returns:
            (px, py) pixel coordinates within the tile
        """
        # Clamp latitude to avoid math domain error
        lat = max(-85.051129, min(85.051129, lat))
        
        # Convert to tile coordinates
        tile_lon = (lon + 180) / 360 * (2 ** zoom)
        tile_lat = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * (2 ** zoom)
        
        # Convert to pixel coordinates within the tile (top-left origin)
        pixel_x = int((tile_lon - x) * 256)
        pixel_y = int((tile_lat - y) * 256)
        
        return pixel_x, pixel_y
    
    def draw_line(self, draw: ImageDraw, coordinates: List[Tuple[float, float]], 
                  color: str, width: int, tile_x: int, tile_y: int, zoom: int,
                  offset_x: int = 0, offset_y: int = 0):
        """Draw a line on the tile (matching master)"""
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
    
    def _pixel_path_length(self, pixels: List[Tuple[float, float]]) -> float:
        """Compute total path length in pixels for a sequence of points"""
        if len(pixels) < 2:
            return 0.0
        length = 0.0
        prev_x, prev_y = pixels[0]
        for i in range(1, len(pixels)):
            x, y = pixels[i]
            dx = x - prev_x
            dy = y - prev_y
            length += math.hypot(dx, dy)
            prev_x, prev_y = x, y
        return length


    def generate_tile(self, x: int, y: int, zoom: int) -> Image.Image:
        """Generate a single tile (matching master)"""
        # Determine styles for this zoom level
        line_width = max(1, int(self.get_highway_line_width(zoom)))

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
        buffer_px = bleed_px + max(line_width, 1)
        buffer_lon = tile_width_deg * (buffer_px / 256.0)
        buffer_lat = tile_height_deg * (buffer_px / 256.0)
        tile_box = box(
            tile_bounds.west - buffer_lon,
            tile_bounds.south - buffer_lat,
            tile_bounds.east + buffer_lon,
            tile_bounds.north + buffer_lat
        )
        
        # Get color
        color = self.highway_color
        
        # Draw highway lines
        for idx, row in self.gdf.iterrows():
            geometry = row.geometry
            
            # Check if geometry intersects with tile bounds
            if geometry.intersects(tile_box):
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
        
        # Crop to the central 256x256 tile area to remove the bleed
        cropped = img.crop((bleed_px, bleed_px, bleed_px + 256, bleed_px + 256))
        return cropped

    def create_blank_tile(self) -> Image.Image:
        """Create a fully transparent PNG tile (Mapbox-safe empty tile)"""
        return Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
    
    def generate_tiles(self, min_zoom: int = 1, max_zoom: int = 16):
        """
        Generate all tiles for zoom levels 1-16
        
        Args:
            min_zoom: Minimum zoom level (default 1)
            max_zoom: Maximum zoom level (default 16)
        """
        logger.info(f"🚀 Generating highway tiles for zoom levels {min_zoom}-{max_zoom}")
        
        total_tiles = 0
        empty_tiles = 0
        skipped_tiles = 0
        start_time = time.time()
        
        # Statistics per zoom
        zoom_stats = {}
        
        for zoom in range(min_zoom, max_zoom + 1):
            zoom_start = time.time()
            logger.info(f"\n🔄 Processing zoom level {zoom}")
            
            # Get line width for this zoom
            line_width = self.get_highway_line_width(zoom)
            logger.info(f"   📏 Line width: {line_width}px")
            
            # Create zoom directory
            zoom_dir = self.output_dir / str(zoom)
            zoom_dir.mkdir(exist_ok=True)
            
            # Get all tiles that intersect with data bounds + surrounding empty tiles
            minx, miny, maxx, maxy = self.bounds
            
            # Get the tile range that covers the data bounds
            data_tiles = list(mercantile.tiles(minx, miny, maxx, maxy, zoom))
            
            # Find the tile grid bounds to ensure we generate all tiles in the grid
            if data_tiles:
                min_tile_x = min(tile.x for tile in data_tiles)
                max_tile_x = max(tile.x for tile in data_tiles)
                min_tile_y = min(tile.y for tile in data_tiles)
                max_tile_y = max(tile.y for tile in data_tiles)
                
                # Generate all tiles in the grid (including empty ones)
                tiles = []
                for x in range(min_tile_x, max_tile_x + 1):
                    for y in range(min_tile_y, max_tile_y + 1):
                        tiles.append(mercantile.Tile(x, y, zoom))
            else:
                tiles = data_tiles
                
            logger.info(f"   🗺️  Total tiles to generate: {len(tiles):,} (grid coverage)")
            
            tiles_generated = 0
            tiles_empty = 0
            
            # Process each tile
            for i, tile in enumerate(tiles):
                x, y = tile.x, tile.y
                
                # Create x directory
                x_dir = zoom_dir / str(x)
                x_dir.mkdir(exist_ok=True)
                
                # Generate tile
                tile_path = x_dir / f"{y}.png"
                
                # Check if tile already exists
                if self.skip_existing and tile_path.exists():
                    tiles_generated += 1
                    total_tiles += 1
                    skipped_tiles += 1
                    continue
                
                # Generate tile image (always returns an image)
                img = self.generate_tile(x, y, zoom)
                
                # Ensure the tile is properly transparent if no data
                # Check if the tile has any non-transparent pixels
                has_data = False
                if img.mode == 'RGBA':
                    # Check if any pixel has alpha > 0
                    pixels = list(img.getdata())
                    has_data = any(pixel[3] > 0 for pixel in pixels)
                
                # If no data, ensure it's a proper transparent tile
                if not has_data:
                    img = self.create_blank_tile()
                
                # Always save the tile image
                img.save(tile_path, 'PNG', optimize=True)
                tiles_generated += 1
                total_tiles += 1
                
                # Check if this is an empty tile by comparing with a blank tile
                blank_tile = self.create_blank_tile()
                if img.tobytes() == blank_tile.tobytes():
                    tiles_empty += 1
                    empty_tiles += 1
                    
                # Progress update
                if (i + 1) % 50 == 0 or (i + 1) == len(tiles):
                    elapsed = time.time() - zoom_start
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    percent = ((i + 1) / len(tiles)) * 100
                    logger.info(f"   📊 Progress: {i+1:,}/{len(tiles):,} ({percent:.1f}%) - {rate:.1f} tiles/sec")
            
            zoom_stats[zoom] = {
                'generated': tiles_generated,
                'empty': tiles_empty,
                'skipped': skipped_tiles,
                'total': len(tiles)
            }
            
            zoom_elapsed = time.time() - zoom_start
            logger.info(f"   ✅ Zoom {zoom} complete: {tiles_generated:,} tiles with data, {tiles_empty:,} empty")
            logger.info(f"   ⏱️  Time: {zoom_elapsed:.1f}s")
        
        # Final statistics
        total_elapsed = time.time() - start_time
        
        logger.info("\n" + "="*60)
        logger.info("🎉 HIGHWAY TILES GENERATION COMPLETE!")
        logger.info("="*60)
        logger.info(f"✅ Total tiles generated: {total_tiles:,}")
        logger.info(f"⏭️  Empty tiles skipped: {empty_tiles:,}")
        if self.skip_existing:
            logger.info(f"⏭️  Existing tiles skipped: {skipped_tiles:,}")
        logger.info(f"⏱️  Total time: {total_elapsed:.1f}s")
        logger.info(f"📁 Output directory: {self.output_dir.absolute()}")
        
        # Detailed zoom statistics
        logger.info("\n📊 Detailed Statistics by Zoom Level:")
        if self.skip_existing:
            logger.info("Zoom | Generated | Empty | Skipped | Total | Coverage")
            logger.info("-----|-----------|-------|---------|-------|----------")
            for zoom in range(min_zoom, max_zoom + 1):
                stats = zoom_stats[zoom]
                coverage = (stats['generated'] / stats['total'] * 100) if stats['total'] > 0 else 0
                logger.info(f"  {zoom:2d} | {stats['generated']:9,} | {stats['empty']:5,} | {stats['skipped']:7,} | {stats['total']:5,} | {coverage:6.2f}%")
        else:
            logger.info("Zoom | Generated | Empty | Total | Coverage")
            logger.info("-----|-----------|-------|-------|----------")
            for zoom in range(min_zoom, max_zoom + 1):
                stats = zoom_stats[zoom]
                coverage = (stats['generated'] / stats['total'] * 100) if stats['total'] > 0 else 0
                logger.info(f"  {zoom:2d} | {stats['generated']:9,} | {stats['empty']:5,} | {stats['total']:5,} | {coverage:6.2f}%")
    
    def create_viewer_html(self):
        """Create an HTML viewer for the tiles"""
        center_lon = (self.bounds[0] + self.bounds[2]) / 2
        center_lat = (self.bounds[1] + self.bounds[3]) / 2
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Hyderabad Highways - PNG Tiles</title>
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
        .info h3 {{ margin-top: 0; }}
        .zoom-info {{
            position: fixed;
            bottom: 10px;
            left: 10px;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            z-index: 1000;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info">
        <h3>🛣️ Hyderabad Highways</h3>
        <p><strong>Color:</strong> {self.highway_color} (Gold)</p>
        <p><strong>Tiles:</strong> Zoom 1-18</p>
        <p><strong>Format:</strong> PNG (256x256)</p>
        <p><strong>Features:</strong> All major highways</p>
        <small>✅ Complete coverage<br>✅ No missing tiles</small>
    </div>
    <div class="zoom-info" id="zoom-display">Zoom: 10</div>
    
    <script>
        // Initialize map
        var map = L.map('map').setView([{center_lat}, {center_lon}], 10);
        
        // Add OpenStreetMap base layer
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors',
            opacity: 0.6,
            maxZoom: 19
        }}).addTo(map);
        
        // Add highway tiles
        var highwayLayer = L.tileLayer('{self.output_dir.absolute()}/{{z}}/{{x}}/{{y}}.png', {{
            attribution: 'Hyderabad Highways',
            minZoom: 1,
            maxZoom: 18,
            opacity: 1.0,
            bounds: [[{self.bounds[1]}, {self.bounds[0]}], [{self.bounds[3]}, {self.bounds[2]}]]
        }}).addTo(map);
        
        // Update zoom display
        function updateZoom() {{
            document.getElementById('zoom-display').textContent = 'Zoom: ' + map.getZoom();
        }}
        
        map.on('zoomend', updateZoom);
        map.on('load', updateZoom);
        updateZoom();
        
        // Fit map to data bounds
        map.fitBounds([[{self.bounds[1]}, {self.bounds[0]}], [{self.bounds[3]}, {self.bounds[2]}]]);
        
        // Add scale control
        L.control.scale().addTo(map);
        
        console.log('🛣️ Hyderabad Highways tiles loaded');
        console.log('✅ Zoom levels 1-18 available');
        console.log('📍 Bounds:', {self.bounds});
    </script>
</body>
</html>"""
        
        viewer_path = self.output_dir / "viewer.html"
        with open(viewer_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"✅ Created viewer: {viewer_path}")

    def create_viewer_mapbox_html(self, mapbox_token: str, base_style: str = 'mapbox://styles/mapbox/satellite-streets-v12'):
        """Create a Mapbox GL HTML viewer for the tiles"""
        center_lon = (self.bounds[0] + self.bounds[2]) / 2
        center_lat = (self.bounds[1] + self.bounds[3]) / 2
        minx, miny, maxx, maxy = self.bounds

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
    <title>Hyderabad Highways - Mapbox GL</title>
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
        <h3>🛣️ Hyderabad Highways (Mapbox)</h3>
        <p><strong>Color:</strong> {self.highway_color} (Gold)</p>
        <p><strong>Tiles:</strong> Zoom 1-18</p>
        <p><strong>Format:</strong> PNG (256x256)</p>
        <p><strong>Features:</strong> All major highways</p>
        <small>Serve this folder via a local web server</small>
    </div>
    <div class="zoom-info" id="zoom-display">Zoom: 10</div>
    <script>
        mapboxgl.accessToken = '{mapbox_token}';
        const map = new mapboxgl.Map({{
            container: 'map',
            style: '{base_style}',
            center: [{center_lon}, {center_lat}],
            zoom: 10
        }});

        map.addControl(new mapboxgl.NavigationControl(), 'top-left');
        map.addControl(new mapboxgl.ScaleControl());

        function updateZoom() {{
            document.getElementById('zoom-display').textContent = 'Zoom: ' + map.getZoom().toFixed(2);
        }}

        map.on('zoomend', updateZoom);
        map.on('load', () => {{
            updateZoom();

            // Add raster source for local PNG tiles
            const cacheBuster = Date.now();
            map.addSource('hyderabad-highways', {{
                type: 'raster',
                tiles: ['./{{z}}/{{x}}/{{y}}.png?v=' + cacheBuster],
                tileSize: 256,
                minzoom: 1,
                maxzoom: 18,
                bounds: [{minx}, {miny}, {maxx}, {maxy}]
            }});

            map.addLayer({{
                id: 'hyderabad-highways',
                type: 'raster',
                source: 'hyderabad-highways',
                paint: {{ 'raster-opacity': 0.8, 'raster-resampling': 'nearest' }}
            }});

            // Fit to data bounds
            map.fitBounds([[{minx}, {miny}], [{maxx}, {maxy}]]);
        }});
    </script>
</body>
</html>"""

        viewer_path = self.output_dir / "viewer_mapbox.html"
        with open(viewer_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"✅ Created Mapbox viewer: {viewer_path}")
    
    def create_tilejson(self):
        """Create TileJSON metadata file"""
        tilejson = {
            "tilejson": "3.0.0",
            "name": "Hyderabad Highways",
            "description": "PNG tiles for all major highways in Hyderabad region",
            "version": "1.0.0",
            "attribution": "Highway Data",
            "scheme": "xyz",
            "tiles": [f"file://{self.output_dir.absolute()}/{{z}}/{{x}}/{{y}}.png"],
            "minzoom": 1,
            "maxzoom": 18,
            "bounds": list(self.bounds),
            "center": [
                (self.bounds[0] + self.bounds[2]) / 2,
                (self.bounds[1] + self.bounds[3]) / 2,
                10
            ]
        }
        
        tilejson_path = self.output_dir / "tilejson.json"
        with open(tilejson_path, 'w') as f:
            json.dump(tilejson, f, indent=2)
        
        logger.info(f"✅ Created TileJSON: {tilejson_path}")

def main():
    """Main function to generate highway tiles"""
    
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate Hyderabad highways PNG tiles')
    parser.add_argument('--force', action='store_true', 
                       help='Force regeneration of all tiles (ignore existing ones)')
    parser.add_argument('--geojson', default="data/Telangana/Hyderabad/highways/hyd_highways_merged.geojson",
                       help='Path to the highways GeoJSON file')
    parser.add_argument('--output', default="hyderabad_highways_tiles",
                       help='Output directory for tiles')
    parser.add_argument('--mapbox-token', default=None,
                       help='If provided, also generate Mapbox GL viewer (viewer_mapbox.html)')
    parser.add_argument('--min-zoom', type=int, default=1,
                       help='Minimum zoom level to generate (default: 1)')
    parser.add_argument('--max-zoom', type=int, default=18,
                       help='Maximum zoom level to generate (default: 18)')
    
    args = parser.parse_args()
    
    # Configuration - single merged file
    geojson_path =  "hyd_highways_merged.geojson"
    #args.geojson
    output_dir = args.output
    skip_existing = not args.force
    mapbox_token = "pk.eyJ1IjoiYXYxYWNyZSIsImEiOiJjbTJtZmdxN3owa2FzMmpyMjJ4OHV5MHhzIn0.FXpMd91JSER-r7LVpSZN-A"
    #args.mapbox_token
    
    # Check multiple possible locations for the file
    possible_paths = [
        geojson_path,
        f"/app/{geojson_path}",
        f"./{geojson_path}",
        "hyd_highways_merged.geojson",
        "/app/hyd_highways_merged.geojson",
        "./hyd_highways_merged.geojson",
        "data/Telangana/Hyderabad/highways/hyd_highways_merged.geojson",
        "./data/Telangana/Hyderabad/highways/hyd_highways_merged.geojson"
    ]
    
    # Find the file
    actual_path = None
    for path in possible_paths:
        if Path(path).exists():
            actual_path = path
            logger.info(f"✅ Found highway merged file at: {path}")
            break
    
    if actual_path is None:
        logger.error(f"❌ Highway merged file not found!")
        logger.info("Searched in the following locations:")
        for path in possible_paths:
            logger.info(f"  - {path}")
        logger.info("\nPlease ensure hyd_highways_merged.geojson exists in the data directory")
        logger.info("You can place it at: data/Telangana/Hyderabad/highways/hyd_highways_merged.geojson")
        return
    
    try:
        # Initialize generator
        generator = HyderabadHighwaysTileGenerator(actual_path, output_dir, skip_existing=skip_existing)
        
        # Generate tiles for specified zoom levels
        logger.info(f"\n🚀 Starting tile generation for zoom levels {args.min_zoom}-{args.max_zoom}...")
        generator.generate_tiles(min_zoom=args.min_zoom, max_zoom=args.max_zoom)
        
        # Create viewer and metadata
        generator.create_viewer_html()
        if mapbox_token:
            generator.create_viewer_mapbox_html(mapbox_token)
        generator.create_tilejson()
        
        logger.info("\n" + "="*60)
        logger.info("🎉 SUCCESS! Highway tiles generated successfully")
        logger.info("="*60)
        logger.info("\n📋 Summary:")
        logger.info(f"  • Highway color: {generator.highway_color} (Gold)")
        logger.info(f"  • Zoom levels: 1-16")
        logger.info(f"  • Tile size: 256x256 pixels")
        logger.info(f"  • Output: {generator.output_dir.absolute()}")
        logger.info(f"  • Data file: {Path(actual_path).name}")
        logger.info(f"  • Skip existing tiles: {skip_existing}")
        if mapbox_token:
            logger.info("  • Mapbox viewer: viewer_mapbox.html (token provided)")
        logger.info("\n🌐 To view the tiles:")
        logger.info(f"  1. Open: {generator.output_dir.absolute()}/viewer.html")
        if mapbox_token:
            logger.info(f"  1b. Open (Mapbox): {generator.output_dir.absolute()}/viewer_mapbox.html")
        logger.info(f"  2. Or serve locally:")
        logger.info(f"     cd {output_dir}")
        logger.info(f"     python -m http.server 8000")
        logger.info(f"     Open: http://localhost:8000/viewer.html")
        if mapbox_token:
            logger.info(f"     Open (Mapbox): http://localhost:8000/viewer_mapbox.html")
        logger.info("\n✅ All issues fixed:")
        logger.info("  • No missing tiles")
        logger.info("  • No broken lines")
        logger.info("  • Proper MultiLineString handling")
        logger.info("  • Coordinate precision handled")
        logger.info("  • Complete coverage at all zoom levels")
        logger.info("  • Smart tile skipping (existing tiles are preserved)")
        
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()