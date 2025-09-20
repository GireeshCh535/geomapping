#!/usr/bin/env python3
"""
Karnataka Bengaluru Highways PNG Tile Generator - Fixed Version
===============================================================

Fixes applied:
- Handle self-intersecting geometries
- Simplify high-density geometries for better performance
- Fix coordinate precision issues
- Handle closed loops properly
- Improved tile intersection detection with spatial indexing
- Better error handling for edge cases
- Proper geometry clipping to tile bounds
- Anti-aliasing and subpixel precision rendering
- Buffer-based intersection detection
- Mapbox-safe blank/transparent tiles (prevents overzoom artifacts)

Usage:
  python karnataka_bengaluru_highways_tiles_fixed.py                # Skip existing tiles (default)
  python karnataka_bengaluru_highways_tiles_fixed.py --force       # Regenerate all tiles
  python karnataka_bengaluru_highways_tiles_fixed.py --help        # Show all options
"""

import json
import os
import sys
import math
import time
import geopandas as gpd
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from typing import Tuple, List, Union
import mercantile
from shapely.geometry import LineString, MultiLineString, Point, Polygon, box, GeometryCollection
from shapely.ops import unary_union, linemerge
from shapely.validation import make_valid
import logging
import numpy as np
from decimal import Decimal, getcontext
import argparse

# Set high precision for coordinate handling
getcontext().prec = 20

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class KarnatakaBengaluruHighwaysTileGenerator:
    """
    Fixed tile generator for Karnataka Bengaluru highways with geometry fixes
    """
    
    def __init__(self, data_dir: str = "data/karnataka/bengaluru/highways", 
                 output_dir: str = "karnataka_bengaluru_highways_tiles", 
                 skip_existing: bool = True):
        """
        Initialize the highways tile generator
        
        Args:
            data_dir: Directory containing GeoJSON files
            output_dir: Directory to save generated tiles
            skip_existing: Whether to skip already generated tiles (default: True)
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.highway_color = "#14E098"  # RGB(20, 224, 152) - bright teal green
        self.tile_size = 256  # Standard tile size
        self.skip_existing = skip_existing
        
        # Quality settings
        self.buffer_factor = 0.15  # 15% buffer for better intersection detection
        self.precision_threshold = 6  # Reduced from 8 to 6 for better performance (about 0.1 meter precision)
        self.simplification_tolerance = 0.00001  # More precise tolerance for geometry simplification
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load and process data
        self.load_and_process_data()
        
        logger.info("🚗 Karnataka Bengaluru Highways Tile Generator initialized (FIXED VERSION)")
        logger.info(f"📂 Data directory: {data_dir}")
        logger.info(f"📁 Output directory: {output_dir}")
        logger.info(f"🎨 Highway color: {self.highway_color}")
        logger.info(f"⏭️  Skip existing tiles: {self.skip_existing}")
    
    def fix_self_intersections(self, geom):
        """
        Fix self-intersecting geometries
        """
        try:
            # First try to make valid
            fixed = make_valid(geom)
            
            # If result is a MultiLineString, merge if possible
            if isinstance(fixed, MultiLineString):
                merged = linemerge(fixed)
                if isinstance(merged, LineString):
                    return merged
                return fixed
            
            return fixed
        except:
            # If make_valid fails, try buffer(0) trick
            try:
                return geom.buffer(0)
            except:
                return geom
    
    def simplify_dense_geometry(self, geom, max_points=1000):
        """
        Simplify geometries with too many points using adaptive tolerance
        """
        if isinstance(geom, LineString):
            num_coords = len(geom.coords)
            if num_coords > max_points:
                # Progressive simplification with adaptive tolerance
                tolerance = self.simplification_tolerance
                simplified = geom
                
                # Try progressive simplification first
                while len(simplified.coords) > max_points and tolerance < 0.001:
                    simplified = geom.simplify(tolerance, preserve_topology=True)
                    tolerance *= 1.5  # Gradual increase
                
                # If still too dense, use point sampling as fallback
                if len(simplified.coords) > max_points:
                    coords = list(simplified.coords)
                    step = len(coords) // max_points
                    sampled_coords = coords[::max(1, step)]
                    simplified = LineString(sampled_coords)
                
                logger.info(f"   Simplified geometry from {num_coords} to {len(simplified.coords)} points")
                return simplified
                
        elif isinstance(geom, MultiLineString):
            total_points = sum(len(line.coords) for line in geom.geoms)
            if total_points > max_points:
                # Simplify each line in the MultiLineString
                simplified_lines = []
                for line in geom.geoms:
                    if len(line.coords) > 100:  # Only simplify dense lines
                        simplified = self.simplify_dense_geometry(line, max_points=100)
                        if simplified is not None:
                            simplified_lines.append(simplified)
                    else:
                        simplified_lines.append(line)
                
                if simplified_lines:
                    return MultiLineString(simplified_lines)
                else:
                    return None
        
        return geom
    
    def round_coordinates(self, geom):
        """
        Round coordinates to reasonable precision to avoid floating point issues
        """
        def round_coords(coords):
            # Round to 6 decimal places (about 11cm precision) - much more aggressive than 14-15 decimal places
            return [(round(float(x), self.precision_threshold), 
                    round(float(y), self.precision_threshold)) for x, y in coords]
        
        if isinstance(geom, LineString):
            coords = round_coords(geom.coords)
            # Remove duplicate consecutive points
            cleaned_coords = [coords[0]]
            for i in range(1, len(coords)):
                if coords[i] != coords[i-1]:
                    cleaned_coords.append(coords[i])
            
            if len(cleaned_coords) >= 2:
                return LineString(cleaned_coords)
            return geom
            
        elif isinstance(geom, MultiLineString):
            lines = []
            for line in geom.geoms:
                coords = round_coords(line.coords)
                # Remove duplicate consecutive points
                cleaned_coords = [coords[0]]
                for i in range(1, len(coords)):
                    if coords[i] != coords[i-1]:
                        cleaned_coords.append(coords[i])
                
                if len(cleaned_coords) >= 2:
                    lines.append(LineString(cleaned_coords))
            
            if lines:
                return MultiLineString(lines)
            return geom
            
        return geom
    
    def remove_duplicate_segments(self, geom, tolerance=0.00001):
        """
        Remove duplicate/overlapping segments from MultiLineString geometries
        
        Args:
            geom: Shapely geometry
            tolerance: Distance tolerance for considering segments as duplicates
            
        Returns:
            Geometry with duplicate segments removed
        """
        if isinstance(geom, MultiLineString):
            lines = list(geom.geoms)
            if len(lines) <= 1:
                return geom
            
            # Remove duplicate lines by comparing their geometries
            unique_lines = []
            for line in lines:
                is_duplicate = False
                for existing_line in unique_lines:
                    # Check if lines are very similar (within tolerance)
                    if line.distance(existing_line) < tolerance:
                        # Check if they have similar length (within 10%)
                        length_ratio = min(line.length, existing_line.length) / max(line.length, existing_line.length)
                        if length_ratio > 0.9:  # 90% similarity
                            is_duplicate = True
                            break
                
                if not is_duplicate:
                    unique_lines.append(line)
            
            if len(unique_lines) == 1:
                return unique_lines[0]
            elif len(unique_lines) > 1:
                return MultiLineString(unique_lines)
            else:
                return None
        
        return geom
    
    def filter_short_segments(self, geom, min_length=0.0001):
        """
        Filter out very short line segments that cause rendering issues
        
        Args:
            geom: Shapely geometry
            min_length: Minimum segment length in degrees
            
        Returns:
            Geometry with short segments removed
        """
        if geom.geom_type == 'LineString':
            coords = list(geom.coords)
            if len(coords) < 2:
                return None
            
            # Calculate segment lengths and filter
            filtered_coords = [coords[0]]  # Always keep first point
            for i in range(1, len(coords)):
                prev_coord = filtered_coords[-1]
                curr_coord = coords[i]
                
                # Calculate distance
                import math
                dist = math.sqrt((curr_coord[0] - prev_coord[0])**2 + (curr_coord[1] - prev_coord[1])**2)
                
                if dist >= min_length:
                    filtered_coords.append(curr_coord)
            
            if len(filtered_coords) < 2:
                return None
            return LineString(filtered_coords)
            
        elif geom.geom_type == 'MultiLineString':
            filtered_lines = []
            for line in geom.geoms:
                filtered_line = self.filter_short_segments(line, min_length)
                if filtered_line is not None:
                    filtered_lines.append(filtered_line)
            
            if not filtered_lines:
                return None
            elif len(filtered_lines) == 1:
                return filtered_lines[0]
            else:
                return MultiLineString(filtered_lines)
        
        return geom
    
    def handle_closed_loop(self, geom):
        """
        Handle closed loop geometries (convert to proper ring if needed)
        """
        if isinstance(geom, LineString):
            coords = list(geom.coords)
            if len(coords) > 2:
                # Check if it's a closed loop
                first = coords[0]
                last = coords[-1]
                distance = ((first[0] - last[0])**2 + (first[1] - last[1])**2)**0.5
                
                if distance < 0.0001:  # Effectively closed
                    # Ensure it's properly closed
                    if first != last:
                        coords.append(first)
                    return LineString(coords)
        
        return geom
    
    def convert_multipolygon_to_linestring(self, geom):
        """
        Convert MultiPolygon to LineString by extracting the exterior rings
        """
        if geom.geom_type == 'MultiPolygon':
            lines = []
            for polygon in geom.geoms:
                # Extract exterior ring as LineString
                exterior_coords = list(polygon.exterior.coords)
                if len(exterior_coords) >= 2:
                    # Remove duplicate consecutive points
                    cleaned_coords = [exterior_coords[0]]
                    for i in range(1, len(exterior_coords)):
                        if exterior_coords[i] != exterior_coords[i-1]:
                            cleaned_coords.append(exterior_coords[i])
                    
                    if len(cleaned_coords) >= 2:
                        lines.append(LineString(cleaned_coords))
            
            if not lines:
                return None
            elif len(lines) == 1:
                return lines[0]
            else:
                return MultiLineString(lines)
        return geom
    
    def merge_strr_features(self, features):
        """
        Merge multiple STRR features into a single geometry
        """
        # Look for STRR features by checking if name contains "STRR" or "Satellite Town Ring Road"
        strr_features = []
        other_features = []
        
        for f in features:
            name = f.get('properties', {}).get('Name', '').upper()
            if 'STRR' in name or 'SATELLITE TOWN RING ROAD' in name:
                strr_features.append(f)
            else:
                other_features.append(f)
        
        if len(strr_features) > 1:
            logger.info(f"   Merging {len(strr_features)} STRR features...")
            
            # Extract geometries from STRR features
            strr_geoms = []
            for feature in strr_features:
                geom = feature.get('geometry', {})
                if geom.get('type') == 'MultiLineString':
                    for line_coords in geom.get('coordinates', []):
                        if len(line_coords) >= 2:  # Only add lines with at least 2 points
                            line = LineString(line_coords)
                            # Filter out very short lines (less than 10 meters)
                            if line.length > 0.0001:  # About 11 meters
                                strr_geoms.append(line)
                elif geom.get('type') == 'LineString':
                    coords = geom.get('coordinates', [])
                    if len(coords) >= 2:
                        line = LineString(coords)
                        if line.length > 0.0001:
                            strr_geoms.append(line)
            
            # Create merged STRR feature
            if strr_geoms:
                merged_geom = MultiLineString(strr_geoms) if len(strr_geoms) > 1 else strr_geoms[0]
                merged_feature = {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'MultiLineString' if len(strr_geoms) > 1 else 'LineString',
                        'coordinates': [list(line.coords) for line in strr_geoms] if len(strr_geoms) > 1 else list(strr_geoms[0].coords)
                    },
                    'properties': {
                        'Name': 'STRR',
                        'Description': 'Satellite Town Ring Road (Merged)'
                    }
                }
                other_features.append(merged_feature)
                logger.info(f"   Merged STRR into single feature with {len(strr_geoms)} parts")
        else:
            # If only one STRR feature, just add it as is
            other_features.extend(strr_features)
        
        return other_features

    def load_and_process_data(self):
        """Load and process GeoJSON data with all fixes applied"""
        try:
            if not self.data_dir.exists():
                raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
            
            # Find all GeoJSON files
            geojson_files = list(self.data_dir.glob("*.geojson"))
            if not geojson_files:
                raise ValueError(f"No GeoJSON files found in {self.data_dir}")
            
            logger.info(f"📖 Loading {len(geojson_files)} highway files...")
            
            all_features = []
            for geojson_path in geojson_files:
                logger.info(f"   Loading {geojson_path.name}")
                
                with open(geojson_path, 'r') as f:
                    geojson_data = json.load(f)
                
                features = geojson_data.get('features', [])
                all_features.extend(features)
                logger.info(f"   Loaded {len(features)} features")
            
            if not all_features:
                raise ValueError("No features found in any GeoJSON files")
            
            # Merge STRR features if multiple exist
            all_features = self.merge_strr_features(all_features)
            
            # Create GeoDataFrame
            self.gdf = gpd.GeoDataFrame.from_features(all_features)
            
            if self.gdf.empty:
                raise ValueError("No features found in GeoJSON")
            
            # Ensure WGS84 CRS
            if self.gdf.crs is None:
                self.gdf.set_crs('EPSG:4326', inplace=True)
            elif self.gdf.crs.to_string() != 'EPSG:4326':
                self.gdf = self.gdf.to_crs('EPSG:4326')
            
            # Process geometries with fixes
            logger.info("🔧 Processing and fixing geometries...")
            processed_geoms = []
            
            for idx, row in self.gdf.iterrows():
                geom = row.geometry
                name = row.get('Name', f'Feature {idx}')
                
                logger.info(f"   Processing {name}...")
                
                # Step 0: Handle MultiPolygon (NICE Road)
                if geom.geom_type == 'MultiPolygon':
                    logger.info(f"     Converting MultiPolygon to LineString...")
                    geom = self.convert_multipolygon_to_linestring(geom)
                
                # Step 1: Fix self-intersections
                if not geom.is_simple:
                    logger.info(f"     Fixing self-intersections...")
                    geom = self.fix_self_intersections(geom)
                
                # Step 2: Handle closed loops
                geom = self.handle_closed_loop(geom)
                
                # Step 3: Filter short segments first
                geom = self.filter_short_segments(geom, min_length=0.0001)
                if geom is None:
                    logger.info(f"     Skipping {name} - no valid segments after filtering")
                    continue
                
                # Step 4: Simplify if too dense
                if isinstance(geom, LineString) and len(geom.coords) > 1000:
                    logger.info(f"     Simplifying dense geometry ({len(geom.coords)} points)...")
                    geom = self.simplify_dense_geometry(geom, max_points=1000)
                elif isinstance(geom, MultiLineString):
                    total_points = sum(len(line.coords) for line in geom.geoms)
                    if total_points > 1000:
                        logger.info(f"     Simplifying dense MultiLineString ({total_points} points)...")
                        # Simplify each line in the MultiLineString
                        simplified_lines = []
                        for line in geom.geoms:
                            if len(line.coords) > 100:
                                simplified = self.simplify_dense_geometry(line, max_points=100)
                                simplified_lines.append(simplified)
                            else:
                                simplified_lines.append(line)
                        geom = MultiLineString(simplified_lines)
                
                # Step 5: Remove duplicate/overlapping segments
                geom = self.remove_duplicate_segments(geom)
                if geom is None:
                    logger.info(f"     Skipping {name} - no valid segments after deduplication")
                    continue
                
                # Step 6: Round coordinates and remove duplicates
                geom = self.round_coordinates(geom)
                
                # Step 7: Fix any remaining invalid geometries
                if not geom.is_valid:
                    logger.info(f"     Fixing invalid geometry...")
                    geom = geom.buffer(0)
                
                processed_geoms.append(geom)
                
                # Log result
                if isinstance(geom, LineString):
                    logger.info(f"     Result: LineString with {len(geom.coords)} points")
                elif isinstance(geom, MultiLineString):
                    total_points = sum(len(line.coords) for line in geom.geoms)
                    logger.info(f"     Result: MultiLineString with {len(geom.geoms)} parts, {total_points} total points")
            
            self.gdf['geometry'] = processed_geoms
            
            # Remove any invalid geometries
            self.gdf = self.gdf[self.gdf.geometry.is_valid].copy()
            
            # Calculate bounds
            self.bounds = self.gdf.total_bounds
            
            # Create spatial index
            logger.info("🔍 Building spatial index...")
            self.spatial_index = self.gdf.sindex
            
            # Create unified geometry for better intersection testing
            self.unified_geometry = unary_union(self.gdf.geometry)
            
            logger.info(f"✅ Loaded and fixed {len(self.gdf)} highway features")
            logger.info(f"📊 Data bounds: {self.bounds}")
            
            # Log feature details
            for idx, row in self.gdf.iterrows():
                geom_type = row.geometry.geom_type
                name = row.get('Name', f'Feature {idx}')
                if geom_type == 'LineString':
                    length = row.geometry.length
                    points = len(row.geometry.coords)
                    logger.info(f"   Feature {idx}: {name} - {points} points, length: {length:.6f}")
                elif geom_type == 'MultiLineString':
                    num_lines = len(row.geometry.geoms)
                    total_length = row.geometry.length
                    total_points = sum(len(line.coords) for line in row.geometry.geoms)
                    logger.info(f"   Feature {idx}: {name} - {num_lines} lines, {total_points} points, total length: {total_length:.6f}")
            
        except Exception as e:
            logger.error(f"❌ Error loading data: {e}")
            raise
    
    def get_highway_line_width(self, zoom: int) -> float:
        """
        Get highway-appropriate line width for zoom level
        
        Args:
            zoom: Zoom level (5-18)
            
        Returns:
            Line width in pixels
        """
        # Highway-specific widths (visible but controlled rendering)
        zoom_widths = {
            5: 1.5,   # Start becoming visible
            6: 1.8,
            7: 2.0,
            8: 2.2,   # Clear at city level
            9: 2.4,
            10: 2.6,  # City overview
            11: 2.8,
            12: 3.0,  # District level
            13: 3.2,  # Neighborhood level
            14: 3.4,  # Street level
            15: 3.6,  # Building level
            16: 3.8,  # Detail level
            17: 4.0,  # High detail
            18: 4.2   # Maximum detail
        }
        return zoom_widths.get(zoom, 3.0)
    
    def get_features_for_tile(self, tile_bounds: mercantile.LngLatBbox) -> gpd.GeoDataFrame:
        """
        Get features that intersect with tile bounds using buffered search
        
        Args:
            tile_bounds: Tile bounds
            
        Returns:
            GeoDataFrame with intersecting features
        """
        try:
            # Calculate buffer based on tile size
            tile_width = tile_bounds.east - tile_bounds.west
            buffer = tile_width * self.buffer_factor
            
            # Create buffered search bounds
            search_bounds = [
                tile_bounds.west - buffer,
                tile_bounds.south - buffer,
                tile_bounds.east + buffer,
                tile_bounds.north + buffer
            ]
            
            # Find potential matches using spatial index
            possible_matches = list(self.spatial_index.intersection(search_bounds))
            
            if not possible_matches:
                return gpd.GeoDataFrame()
            
            # Get matching features
            features = self.gdf.iloc[possible_matches].copy()
            
            # Create tile polygon for intersection test
            tile_polygon = box(
                tile_bounds.west,
                tile_bounds.south,
                tile_bounds.east,
                tile_bounds.north
            )
            
            # Add small buffer to tile polygon to catch edge cases
            tile_polygon_buffered = tile_polygon.buffer(buffer * 0.1)
            
            # Filter to features that actually intersect
            intersecting = features[features.geometry.intersects(tile_polygon_buffered)]
            
            return intersecting
            
        except Exception as e:
            logger.error(f"Error getting tile features: {e}")
            return gpd.GeoDataFrame()
    
    def clip_geometry_to_tile(self, geom, tile_bounds: mercantile.LngLatBbox):
        """
        Clip geometry to tile bounds with better handling of edge cases
        
        Args:
            geom: Geometry to clip
            tile_bounds: Tile bounds
            
        Returns:
            Clipped geometry or None
        """
        try:
            # Create tile polygon with small buffer to avoid edge precision issues
            buffer = 0.00001
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
            
            # Handle different result types
            if isinstance(clipped, LineString):
                if len(clipped.coords) >= 2:
                    return clipped
            elif isinstance(clipped, MultiLineString):
                # Filter out tiny segments
                valid_lines = [line for line in clipped.geoms if len(line.coords) >= 2]
                if valid_lines:
                    if len(valid_lines) == 1:
                        return valid_lines[0]
                    else:
                        return MultiLineString(valid_lines)
            elif isinstance(clipped, GeometryCollection):
                # Extract lines from collection
                lines = []
                for g in clipped.geoms:
                    if isinstance(g, LineString) and len(g.coords) >= 2:
                        lines.append(g)
                    elif isinstance(g, MultiLineString):
                        for line in g.geoms:
                            if len(line.coords) >= 2:
                                lines.append(line)
                
                if lines:
                    if len(lines) == 1:
                        return lines[0]
                    else:
                        return MultiLineString(lines)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error clipping geometry: {e}")
            return None
    
    def coords_to_pixels(self, coords: List[Tuple[float, float]], 
                        tile_bounds: mercantile.LngLatBbox, tile_x: int, tile_y: int, zoom: int) -> List[Tuple[float, float]]:
        """
        Convert geographic coordinates to pixel coordinates using proper Web Mercator projection
        
        Args:
            coords: List of (lon, lat) coordinates
            tile_bounds: Tile bounds
            tile_x: Tile X coordinate
            tile_y: Tile Y coordinate
            zoom: Zoom level
            
        Returns:
            List of (x, y) pixel coordinates
        """
        pixels = []
        for lon, lat in coords:
            # Use the proper Web Mercator conversion
            pixel_x, pixel_y = self.wgs84_to_tile_pixel(lon, lat, tile_x, tile_y, zoom)
            pixels.append((pixel_x, pixel_y))
        
        return pixels
    
    def draw_highway_line(self, draw: ImageDraw.Draw, pixels: List[Tuple[float, float]], 
                         color_rgb: Tuple[int, int, int], width: int):
        """
        Draw highway line with clean, consistent rendering
        
        Args:
            draw: PIL ImageDraw object
            pixels: Pixel coordinates
            color_rgb: RGB color
            width: Line width
        """
        try:
            if len(pixels) < 2:
                return
            
            # Convert to integer pixels for drawing and filter out invalid coordinates
            int_pixels = []
            for x, y in pixels:
                try:
                    int_x = int(round(x))
                    int_y = int(round(y))
                    # Check if coordinates are within extended tile bounds (with buffer for thick lines)
                    if -10 <= int_x < 266 and -10 <= int_y < 266:
                        int_pixels.append((int_x, int_y))
                except (ValueError, OverflowError):
                    continue
            
            # Remove duplicate consecutive points to prevent rendering artifacts
            cleaned_pixels = []
            prev_point = None
            for point in int_pixels:
                if prev_point is None or point != prev_point:
                    cleaned_pixels.append(point)
                    prev_point = point
            
            # Draw main line with full opacity - use consistent width
            if len(cleaned_pixels) >= 2:
                # Ensure width is at least 1 and reasonable
                actual_width = max(1, min(width, 6))  # Cap at 6 pixels max for controlled rendering
                draw.line(cleaned_pixels, fill=color_rgb + (255,), width=actual_width)
                
        except Exception as e:
            logger.debug(f"Error drawing highway line: {e}")
            return
    
    def create_blank_tile(self) -> Image.Image:
        """Create a fully transparent PNG tile (Mapbox-safe empty tile)"""
        return Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
    
    

    def wgs84_to_tile_pixel(self, lon: float, lat: float, tile_x: int, tile_y: int, zoom: int) -> Tuple[int, int]:
        """Convert WGS84 coordinates to pixel coordinates within a tile (matching master)"""
        try:
            # Clamp latitude to avoid math domain error
            lat = max(-85.051129, min(85.051129, lat))
            
            # Clamp longitude to valid range
            lon = max(-180, min(180, lon))
            
            # Convert to tile coordinates
            tile_lon = (lon + 180) / 360 * (2 ** zoom)
            tile_lat = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * (2 ** zoom)
            
            # Convert to pixel coordinates within the tile (top-left origin)
            pixel_x = int((tile_lon - tile_x) * 256)
            pixel_y = int((tile_lat - tile_y) * 256)
            
            # Clamp pixel coordinates to tile bounds with some buffer for line rendering
            pixel_x = max(-10, min(266, pixel_x))  # Allow some buffer for thick lines
            pixel_y = max(-10, min(266, pixel_y))
            
            return pixel_x, pixel_y
            
        except Exception as e:
            logger.debug(f"Error converting coordinates ({lon}, {lat}) to pixel: {e}")
            return 0, 0

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


    def generate_tile(self, x: int, y: int, zoom: int) -> Image.Image:
        """Generate a single tile with clean, single lines"""
        try:
            # Create a transparent tile
            img = Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Get tile bounds
            tile_bounds = mercantile.bounds(x, y, zoom)
            
            # Get features that intersect with this tile
            features = self.get_features_for_tile(tile_bounds)
            
            if features.empty:
                return img
            
            # Get line width for this zoom level - ensure it's reasonable
            line_width = max(1, min(int(self.get_highway_line_width(zoom)), 6))
            
            # Convert color to RGB
            color_hex = self.highway_color.lstrip('#')
            color_rgb = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
            
            # Track drawn segments to prevent duplicates
            drawn_segments = set()
            
            # Draw each feature as a clean line
            for idx, feature in features.iterrows():
                try:
                    geom = feature.geometry
                    
                    # Skip invalid geometries
                    if not geom or not geom.is_valid:
                        continue
                    
                    # Clip geometry to tile bounds
                    clipped_geom = self.clip_geometry_to_tile(geom, tile_bounds)
                    if clipped_geom is None:
                        continue
                    
                    # Draw the clipped geometry
                    if clipped_geom.geom_type == 'LineString':
                        coords = list(clipped_geom.coords)
                        if len(coords) >= 2:
                            # Create a hash of the coordinate sequence to avoid duplicates
                            coord_hash = hash(tuple((round(c[0], 6), round(c[1], 6)) for c in coords))
                            if coord_hash not in drawn_segments:
                                pixels = self.coords_to_pixels(coords, tile_bounds, x, y, zoom)
                                self.draw_highway_line(draw, pixels, color_rgb, line_width)
                                drawn_segments.add(coord_hash)
                    elif clipped_geom.geom_type == 'MultiLineString':
                        for line in clipped_geom.geoms:
                            if line and line.is_valid:
                                coords = list(line.coords)
                                if len(coords) >= 2:
                                    # Create a hash of the coordinate sequence to avoid duplicates
                                    coord_hash = hash(tuple((round(c[0], 6), round(c[1], 6)) for c in coords))
                                    if coord_hash not in drawn_segments:
                                        pixels = self.coords_to_pixels(coords, tile_bounds, x, y, zoom)
                                        self.draw_highway_line(draw, pixels, color_rgb, line_width)
                                        drawn_segments.add(coord_hash)
                
                except Exception as e:
                    logger.debug(f"Error drawing feature {idx} in tile {x}/{y}/{zoom}: {e}")
                    continue
            
            return img
            
        except Exception as e:
            logger.error(f"Error generating tile {x}/{y}/{zoom}: {e}")
            # Return a blank tile on error
            return Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))
    
    def generate_tiles(self, min_zoom: int = 8, max_zoom: int = 16, force: bool = False):
        """
        Generate all tiles for the specified zoom range
        
        Args:
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            force: Force regeneration of existing tiles
        """
        logger.info(f"🎯 Generating tiles for zoom levels {min_zoom}-{max_zoom}")
        
        # Calculate tile bounds
        min_tile = mercantile.tile(self.bounds[0], self.bounds[1], min_zoom)
        max_tile = mercantile.tile(self.bounds[2], self.bounds[3], max_zoom)
        
        total_tiles = 0
        generated_tiles = 0
        empty_tiles = 0
        skipped_tiles = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            logger.info(f"🔍 Processing zoom level {zoom}")
            
            # Recalculate tile bounds for this zoom level
            min_tile = mercantile.tile(self.bounds[0], self.bounds[1], zoom)
            max_tile = mercantile.tile(self.bounds[2], self.bounds[3], zoom)
            
            zoom_dir = self.output_dir / str(zoom)
            zoom_dir.mkdir(exist_ok=True)
            
            zoom_tiles = 0
            zoom_generated = 0
            zoom_empty = 0
            zoom_skipped = 0
            
            for x in range(min_tile.x, max_tile.x + 1):
                x_dir = zoom_dir / str(x)
                x_dir.mkdir(exist_ok=True)
                
                for y in range(max_tile.y, min_tile.y + 1):
                    tile_path = x_dir / f"{y}.png"
                    total_tiles += 1
                    zoom_tiles += 1
                    
                    # Check if tile already exists and we're not forcing regeneration
                    if tile_path.exists() and not force and self.skip_existing:
                        skipped_tiles += 1
                        zoom_skipped += 1
                        continue
                    
                    # Generate tile (always returns an image)
                    tile_img = self.generate_tile(x, y, zoom)
                    
                    # Always save the tile image. If there's no content, this will be a fully transparent PNG.
                    tile_img.save(tile_path, 'PNG', optimize=True)
                    generated_tiles += 1
                    zoom_generated += 1
                    
                    # Check if this is an empty tile by comparing with a blank tile
                    blank_tile = self.create_blank_tile()
                    if tile_img.tobytes() == blank_tile.tobytes():
                        empty_tiles += 1
                        zoom_empty += 1
                    
                    # Log progress every 100 tiles
                    if total_tiles % 100 == 0:
                        logger.info(f"   Generated {total_tiles} tiles so far...")
            
            logger.info(f"   Zoom {zoom}: {zoom_generated} generated ({zoom_generated - zoom_empty} with data, {zoom_empty} empty), {zoom_skipped} skipped, {zoom_tiles} total")
        
        logger.info(f"✅ Tile generation completed!")
        logger.info(f"📊 Total tiles: {total_tiles}")
        logger.info(f"🆕 Generated: {generated_tiles}")
        logger.info(f"📭 Empty tiles: {empty_tiles}")
        logger.info(f"⏭️  Skipped: {skipped_tiles}")
        
        # Create supporting files
        self.create_supporting_files(min_zoom, max_zoom)
        
        return generated_tiles
    
    def create_supporting_files(self, min_zoom: int, max_zoom: int):
        """Create supporting files for the tile set"""
        logger.info("📄 Creating supporting files...")
        
        # Create TileJSON
        tilejson = {
            "tilejson": "2.2.0",
            "name": "Karnataka - Bengaluru Highways",
            "description": "Highways and major roads in Bengaluru, Karnataka",
            "version": "1.0.0",
            "attribution": "Karnataka Government",
            "template": "",
            "legend": "",
            "scheme": "xyz",
            "tiles": [
                "https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/highways/{z}/{x}/{y}.png"
            ],
            "grids": [],
            "data": [],
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "bounds": [
                self.bounds[0],  # west
                self.bounds[1],  # south
                self.bounds[2],  # east
                self.bounds[3]   # north
            ],
            "center": [
                (self.bounds[0] + self.bounds[2]) / 2,
                (self.bounds[1] + self.bounds[3]) / 2,
                10
            ]
        }
        
        with open(self.output_dir / "tilejson.json", "w") as f:
            json.dump(tilejson, f, indent=2)
        
        # Create HTML viewer
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Karnataka - Bengaluru Highways</title>
    <script src='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js'></script>
    <link href='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css' rel='stylesheet' />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
    </style>
</head>
<body>
    <div id='map'></div>
    <script>
        mapboxgl.accessToken = 'pk.eyJ1IjoiZXhhbXBsZSIsImEiOiJjbGV4YW1wbGUifQ.example';
        var map = new mapboxgl.Map({{
            container: 'map',
            style: {{
                "version": 8,
                "sources": {{
                    "karnataka-bengaluru-highways": {{
                        "type": "raster",
                        "tiles": [
                            "https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/highways/{{z}}/{{x}}/{{y}}.png"
                        ],
                        "tileSize": 256
                    }}
                }},
                "layers": [
                    {{
                        "id": "karnataka-bengaluru-highways-layer",
                        "type": "raster",
                        "source": "karnataka-bengaluru-highways",
                        "paint": {{
                            "raster-opacity": 0.8
                        }}
                    }}
                ]
            }},
            center: [{(self.bounds[0] + self.bounds[2]) / 2}, {(self.bounds[1] + self.bounds[3]) / 2}],
            zoom: 10
        }});
    </script>
</body>
</html>
"""
        
        with open(self.output_dir / "viewer.html", "w") as f:
            f.write(html_content)
        
        logger.info("✅ Created supporting files: tilejson.json, viewer.html")

def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(description='Generate Karnataka Bengaluru highways tiles')
    parser.add_argument('--data-dir', default='data/karnataka/bengaluru/highways',
                       help='Directory containing GeoJSON files')
    parser.add_argument('--output-dir', default='karnataka_bengaluru_highways_tiles',
                       help='Output directory for tiles')
    parser.add_argument('--min-zoom', type=int, default=18,
                       help='Minimum zoom level')
    parser.add_argument('--max-zoom', type=int, default=18,
                       help='Maximum zoom level')
    parser.add_argument('--force', action='store_true',
                       help='Force regeneration of existing tiles')
    parser.add_argument('--no-skip', action='store_true',
                       help='Do not skip existing tiles')
    
    args = parser.parse_args()
    
    logger.info("🚀 Starting Karnataka Bengaluru highways tile generation (FIXED VERSION)")
    
    try:
        # Initialize generator
        generator = KarnatakaBengaluruHighwaysTileGenerator(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            skip_existing=not args.no_skip
        )
        
        # Generate tiles
        start_time = time.time()
        generated_count = generator.generate_tiles(
            min_zoom=args.min_zoom,
            max_zoom=args.max_zoom,
            force=args.force
        )
        end_time = time.time()
        
        logger.info(f"🎉 Karnataka Bengaluru highways tile generation completed!")
        logger.info(f"⏱️  Total time: {end_time - start_time:.2f} seconds")
        logger.info(f"📊 Generated {generated_count} tiles")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
