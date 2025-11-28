#!/usr/bin/env python3
"""
Puducherry Master Plan - SEAMLESS COMPLETE TILES
Every feature visible at every zoom level - Transparent background
"""

import json
import os
import time
from pathlib import Path
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import shape, box, Point, Polygon, LineString
from shapely.ops import transform
from rtree import index
try:
    from pyproj import Transformer
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False
    print("Warning: pyproj not available. Coordinate transformation disabled.")

class PuducherrySeamlessTiles:
    def __init__(self, data_dir, output_dir, source_crs='EPSG:32644'):
        """
        Initialize Puducherry tile generator
        
        Args:
            data_dir: Directory containing GeoJSON files
            output_dir: Output directory for tiles
            source_crs: Source CRS of the GeoJSON data (default: EPSG:32644 for UTM Zone 44N)
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.spatial_index = index.Index()
        self.feature_id_counter = 0
        self.feature_lookup = {}
        self.source_crs = source_crs
        self.needs_transform = False
        
        # Setup coordinate transformation if pyproj is available
        if HAS_PYPROJ:
            try:
                self.transformer = Transformer.from_crs(source_crs, 'EPSG:4326', always_xy=True)
                self.needs_transform = True
                print(f"✓ Coordinate transformation enabled: {source_crs} -> EPSG:4326")
            except Exception as e:
                print(f"⚠️ Could not initialize transformer: {e}")
                self.needs_transform = False
        else:
            # Try to detect if transformation is needed by checking first file
            self.needs_transform = None  # Will be determined during loading
        
    def normalize_category(self, value):
        """Normalize category name"""
        if not value:
            return None
        value = " ".join(str(value).replace("_", " ").split())
        return value.upper()
    
    def get_color_map(self):
        """Puducherry color mapping based on user specifications"""
        return {
            # AGRICULTURAL ZONE - Solid Fill: #adffaf, Outline: #000000
            "AGRICULTURAL ZONE": {'fill': '#adffaf', 'outline': '#000000'},
            "AGRICULTURAL_ZONE": {'fill': '#adffaf', 'outline': '#000000'},
            
            # EXISTING COMMERCIAL ZONE - Solid Fill: #3d5fea, Outline: #000000
            "EXISTING COMMERCIAL ZONE": {'fill': '#3d5fea', 'outline': '#000000'},
            "EXISTING_COMMERCIAL_ZONE": {'fill': '#3d5fea', 'outline': '#000000'},
            
            # EXISTING MIXED COMMERCIAL ZONE - Solid Fill: #ffffff, Hatched Fill: #44b7ff, Outline: #000000
            "EXISTING MIXED COMMERCIAL ZONE": {'fill': '#ffffff', 'outline': '#000000', 'pattern': 'hatch', 'pattern_color': '#44b7ff'},
            "EXISTING_MIXED_COMMERCIAL_ZONE": {'fill': '#ffffff', 'outline': '#000000', 'pattern': 'hatch', 'pattern_color': '#44b7ff'},
            
            # EXISTING MIXED RESIDENTIAL ZONE - Solid Fill: #fef787, Hatched Fill: #ff0009, Outline: #000000
            "EXISTING MIXED RESIDENTIAL ZONE": {'fill': '#fef787', 'outline': '#000000', 'pattern': 'hatch', 'pattern_color': '#ff0009'},
            "EXISTING_MIXED_RESIDENTIAL_ZONE": {'fill': '#fef787', 'outline': '#000000', 'pattern': 'hatch', 'pattern_color': '#ff0009'},
            
            # EXISTING PROTECTIVE AND UNDEVELOPED USE ZONE - Solid Fill: #8bc1ff, Outline: #000000
            "EXISTING PROTECTIVE AND UNDEVELOPED USE ZONE": {'fill': '#8bc1ff', 'outline': '#000000'},
            "EXISTING_PROTECTIVE_AND_UNDEVELOPED_USE_ZONE": {'fill': '#8bc1ff', 'outline': '#000000'},
            "EXISTING PROTECTIVE AND UNDEVELOPED USE": {'fill': '#8bc1ff', 'outline': '#000000'},
            
            # EXISTING PUBLIC & SEMI PUBLIC ZONE - Solid Fill: #ee6966, Outline: #000000
            "EXISTING PUBLIC & SEMI PUBLIC ZONE": {'fill': '#ee6966', 'outline': '#000000'},
            "EXISTING_PUBLIC_&_SEMI_PUBLIC_ZONE": {'fill': '#ee6966', 'outline': '#000000'},
            "EXISTING PUBLIC AND SEMI PUBLIC ZONE": {'fill': '#ee6966', 'outline': '#000000'},
            "EXISTING_PUBLIC_AND_SEMI_PUBLIC_ZONE": {'fill': '#ee6966', 'outline': '#000000'},
            
            # EXISTING RECREATIONAL/TOURISM ZONE - Solid Fill: #95ff21, Outline: #000000
            "EXISTING RECREATIONAL/TOURISM ZONE": {'fill': '#95ff21', 'outline': '#000000'},
            "EXISTING_RECREATIONAL/TOURISM_ZONE": {'fill': '#95ff21', 'outline': '#000000'},
            "EXISTING RECREATIONAL TOURISM ZONE": {'fill': '#95ff21', 'outline': '#000000'},
            "EXISTING_RECREATIONAL_TOURISM_ZONE": {'fill': '#95ff21', 'outline': '#000000'},
            
            # EXISTING RESIDENTIAL ZONE - Solid Fill: #fffbb7, Outline: #000000
            "EXISTING RESIDENTIAL ZONE": {'fill': '#fffbb7', 'outline': '#000000'},
            "EXISTING_RESIDENTIAL_ZONE": {'fill': '#fffbb7', 'outline': '#000000'},
            
            # EXISTING TRANSPORTATION AND COMMUNICATION - Solid Fill: #d5d5d5, Outline: #000000
            "EXISTING TRANSPORTATION AND COMMUNICATION": {'fill': '#d5d5d5', 'outline': '#000000'},
            "EXISTING_TRANSPORTATION_AND_COMMUNICATION": {'fill': '#d5d5d5', 'outline': '#000000'},
            "EXISTING TRANSPORTATION & COMMUNICATION": {'fill': '#d5d5d5', 'outline': '#000000'},
            
            # INDUSTRIAL ZONE - Solid Fill: #ea00ea, Outline: #000000
            "INDUSTRIAL ZONE": {'fill': '#ea00ea', 'outline': '#000000'},
            "INDUSTRIAL_ZONE": {'fill': '#ea00ea', 'outline': '#000000'},
            
            # INFORMAL RESIDENTIAL ZONE - Solid Fill: #dbf400, Outline: #000000
            "INFORMAL RESIDENTIAL ZONE": {'fill': '#dbf400', 'outline': '#000000'},
            "INFORMAL_RESIDENTIAL_ZONE": {'fill': '#dbf400', 'outline': '#000000'},
            
            # PROPOSED COMMERCIAL ZONE - Solid Fill: #181679, Outline: #000000
            "PROPOSED COMMERCIAL ZONE": {'fill': '#181679', 'outline': '#000000'},
            "PROPOSED_COMMERCIAL_ZONE": {'fill': '#181679', 'outline': '#000000'},
            
            # PROPOSED MIXED COMMERCIAL ZONE - Solid Fill: #ffffff, Dotted Fill: #0e07ff, Outline: #000000
            "PROPOSED MIXED COMMERCIAL ZONE": {'fill': '#ffffff', 'outline': '#000000', 'pattern': 'dotted', 'pattern_color': '#0e07ff'},
            "PROPOSED_MIXED_COMMERCIAL_ZONE": {'fill': '#ffffff', 'outline': '#000000', 'pattern': 'dotted', 'pattern_color': '#0e07ff'},
            
            # PROPOSED MIXED INDUSTRIAL USE ZONE - Solid Fill: #ffffff, Dotted Fill: #76028e, Outline: #000000
            "PROPOSED MIXED INDUSTRIAL USE ZONE": {'fill': '#ffffff', 'outline': '#000000', 'pattern': 'dotted', 'pattern_color': '#76028e'},
            "PROPOSED_MIXED_INDUSTRIAL_USE_ZONE": {'fill': '#ffffff', 'outline': '#000000', 'pattern': 'dotted', 'pattern_color': '#76028e'},
            
            # PROPOSED MIXED RESIDENTIAL ZONE - Solid Fill: #fff000, Hatched Fill and Outline: #000000
            "PROPOSED MIXED RESIDENTIAL ZONE": {'fill': '#fff000', 'outline': '#000000', 'pattern': 'hatch', 'pattern_color': '#000000'},
            "PROPOSED_MIXED_RESIDENTIAL_ZONE": {'fill': '#fff000', 'outline': '#000000', 'pattern': 'hatch', 'pattern_color': '#000000'},
            
            # PROPOSED PROTECTIVE AND UNDEVELOPED USE ZONE - No Solid Fill, Hatched Fill: #ff0014, Outline: #000000
            "PROPOSED PROTECTIVE AND UNDEVELOPED USE ZONE": {'fill': None, 'outline': '#000000', 'pattern': 'hatch', 'pattern_color': '#ff0014'},
            "PROPOSED_PROTECTIVE_AND_UNDEVELOPED_USE_ZONE": {'fill': None, 'outline': '#000000', 'pattern': 'hatch', 'pattern_color': '#ff0014'},
            "PROPOSED PROTECTIVE AND UNDEVELOPED USE": {'fill': None, 'outline': '#000000', 'pattern': 'hatch', 'pattern_color': '#ff0014'},
            
            # PROPOSED PUBLIC & SEMI PUBLIC - Solid Fill: #ff0009, Outline: #000000
            "PROPOSED PUBLIC & SEMI PUBLIC": {'fill': '#ff0009', 'outline': '#000000'},
            "PROPOSED_PUBLIC_&_SEMI_PUBLIC": {'fill': '#ff0009', 'outline': '#000000'},
            "PROPOSED PUBLIC AND SEMI PUBLIC": {'fill': '#ff0009', 'outline': '#000000'},
            "PROPOSED_PUBLIC_AND_SEMI_PUBLIC": {'fill': '#ff0009', 'outline': '#000000'},
            
            # PROPOSED RECREATIONAL/TOURISM ZONE - Solid Fill: #ffffff, Dotted Fill: #4daf4a, Outline: #000000
            "PROPOSED RECREATIONAL/TOURISM ZONE": {'fill': '#ffffff', 'outline': '#000000', 'pattern': 'dotted', 'pattern_color': '#4daf4a'},
            "PROPOSED_RECREATIONAL/TOURISM_ZONE": {'fill': '#ffffff', 'outline': '#000000', 'pattern': 'dotted', 'pattern_color': '#4daf4a'},
            "PROPOSED RECREATIONAL TOURISM ZONE": {'fill': '#ffffff', 'outline': '#000000', 'pattern': 'dotted', 'pattern_color': '#4daf4a'},
            "PROPOSED_RECREATIONAL_TOURISM_ZONE": {'fill': '#ffffff', 'outline': '#000000', 'pattern': 'dotted', 'pattern_color': '#4daf4a'},
            
            # PROPOSED RESIDENTIAL ZONE - Solid Fill: #fff000, Outline: #000000
            "PROPOSED RESIDENTIAL ZONE": {'fill': '#fff000', 'outline': '#000000'},
            "PROPOSED_RESIDENTIAL_ZONE": {'fill': '#fff000', 'outline': '#000000'},
            
            # PROPOSED TRANSPORTATION AND COMMUNICATION - Solid Fill: #acacac, Outline: #000000
            "PROPOSED TRANSPORTATION AND COMMUNICATION": {'fill': '#acacac', 'outline': '#000000'},
            "PROPOSED_TRANSPORTATION_AND_COMMUNICATION": {'fill': '#acacac', 'outline': '#000000'},
            "PROPOSED TRANSPORTATION & COMMUNICATION": {'fill': '#acacac', 'outline': '#000000'},
            
            # ROADS - Solid Fill: #ffffff, Outline: #000000
            "ROADS": {'fill': '#ffffff', 'outline': '#000000'},
            "ROAD": {'fill': '#ffffff', 'outline': '#000000'},
        }
    
    def hex_to_rgb(self, hex_color):
        """Convert hex to RGB"""
        if hex_color is None:
            return None
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def get_zoom_scale(self, zoom):
        """Get rendering scale based on zoom level"""
        if zoom <= 10:
            return 6
        elif zoom <= 13:
            return 5
        elif zoom <= 16:
            return 4
        else:
            return 3
    
    def get_min_feature_size(self, zoom, scale):
        """Minimum feature size in pixels"""
        if zoom <= 10:
            return 4 * scale
        elif zoom <= 13:
            return 3 * scale
        elif zoom <= 16:
            return 2 * scale
        else:
            return 1.5 * scale
    
    def get_outline_width(self, zoom):
        """Get outline width based on zoom level"""
        if zoom <= 10:
            return 2
        elif zoom <= 13:
            return 1
        else:
            return 1
    
    def load_geojson_files(self):
        """Load all Puducherry GeoJSON files"""
        print("\n" + "="*80)
        print("LOADING PUDUCHERRY GEOJSON DATA")
        print("="*80)
        
        geojson_files = sorted(self.data_dir.glob('*.geojson'))
        total_files = len(geojson_files)
        total_features = 0
        
        print(f"Found {total_files} files\n")
        
        load_start = time.time()
        
        for idx, geojson_file in enumerate(geojson_files, 1):
            file_name = geojson_file.stem
            file_size = geojson_file.stat().st_size / 1024 / 1024
            
            print(f"[{idx:2d}/{total_files}] {file_name:<50} ({file_size:6.2f} MB)", end=" ", flush=True)
            
            try:
                with open(geojson_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                features = data.get('features', [])
                loaded = 0
                
                for feature in features:
                    try:
                        geom = shape(feature['geometry'])
                        
                        # Detect if coordinates need transformation (check first feature)
                        if self.needs_transform is None:
                            # Check if coordinates look like projected (large numbers)
                            if geom.bounds[0] > 1000 or geom.bounds[1] > 1000:
                                print(f"\n⚠️  Detected projected coordinates. Attempting transformation...")
                                if HAS_PYPROJ:
                                    # Try common UTM zones for India
                                    for zone in [43, 44, 45]:  # Common UTM zones for India
                                        try:
                                            test_transformer = Transformer.from_crs(f'EPSG:326{zone}', 'EPSG:4326', always_xy=True)
                                            test_point = test_transformer.transform(geom.bounds[0], geom.bounds[1])
                                            # Check if result is reasonable lat/lon for India
                                            if 6 < test_point[1] < 36 and 68 < test_point[0] < 98:
                                                self.source_crs = f'EPSG:326{zone}'
                                                self.transformer = test_transformer
                                                self.needs_transform = True
                                                print(f"✓ Detected CRS: {self.source_crs}")
                                                break
                                        except:
                                            continue
                                    if not self.needs_transform:
                                        print("⚠️  Could not determine source CRS. Using coordinates as-is.")
                                        self.needs_transform = False
                                else:
                                    self.needs_transform = False
                            else:
                                self.needs_transform = False
                        
                        # Transform geometry to WGS84 if needed
                        if self.needs_transform:
                            # Create a wrapper function for shapely.ops.transform
                            def transform_func(x, y, z=None):
                                result = self.transformer.transform(x, y)
                                if z is not None:
                                    return (result[0], result[1], z)
                                return result
                            geom = transform(transform_func, geom)
                        
                        if not geom.is_valid:
                            geom = geom.buffer(0)
                        
                        if geom.is_empty:
                            continue
                        
                        props = feature.get('properties', {})
                        # Try multiple property fields for category
                        raw_category = (
                            props.get("LANDUSE_CATEGORY")
                            or props.get("LANDUSE_SUBCAT_LEVEL_1")
                            or props.get("CATEGORY")
                            or props.get("SUB_CATEGO")
                            or props.get("Name")
                            or props.get("name")
                            or props.get("Label")
                            or props.get("use")
                            or file_name
                        )
                        category_norm = self.normalize_category(str(raw_category)) or self.normalize_category(file_name) or file_name.upper()
                        
                        feature_data = {
                            'geometry': geom,
                            'category': category_norm,
                            'filename': file_name,
                            'properties': props,
                            'area': geom.area
                        }
                        
                        bounds = geom.bounds
                        self.spatial_index.insert(self.feature_id_counter, bounds)
                        self.feature_lookup[self.feature_id_counter] = feature_data
                        self.feature_id_counter += 1
                        loaded += 1
                        
                    except:
                        continue
                
                total_features += loaded
                print(f"✓ {loaded:>7,}")
                
            except Exception as e:
                print(f"✗ {e}")
                continue
        
        load_elapsed = time.time() - load_start
        print(f"\n{'='*80}")
        print(f"LOADED: {total_features:,} features in {load_elapsed:.1f}s")
        print(f"{'='*80}\n")
    
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
    
    def create_pattern(self, draw, poly, base, ptype, pcolor, img_size):
        """Create patterns: hatch, dots, cross_hatch, dashed, dotted - clipped to polygon boundary"""
        # Draw base fill first
        if base:
            draw.polygon(poly, fill=base)
        
        if len(poly) < 3:
            return
        
        xs, ys = zip(*poly)
        min_x, max_x = int(min(xs)), int(max(xs))
        min_y, max_y = int(min(ys)), int(max(ys))
        
        # Create polygon shape for clipping
        try:
            poly_shape = Polygon(poly)
            if not poly_shape.is_valid:
                poly_shape = poly_shape.buffer(0)
        except:
            poly_shape = None
        
        if ptype == "hatch":
            if poly_shape is None:
                return
            spacing = max(5, (max_x - min_x) // 12)
            for i in range(min_x - max_y, max_x + max_y, spacing):
                # Create full hatch line
                line_pts = [(x, x - i) for x in range(min_x - 10, max_x + 10) if min_y - 10 <= x - i <= max_y + 10]
                if len(line_pts) < 2:
                    continue
                # Create LineString and clip to polygon
                try:
                    line = LineString(line_pts)
                    clipped = line.intersection(poly_shape)
                    if clipped.is_empty:
                        continue
                    # Draw clipped line segments
                    if clipped.geom_type == 'LineString':
                        clipped_pts = list(clipped.coords)
                        if len(clipped_pts) >= 2:
                            int_pts = [(int(x), int(y)) for x, y in clipped_pts]
                            draw.line(int_pts, fill=pcolor, width=2)
                    elif clipped.geom_type == 'MultiLineString':
                        for line_seg in clipped.geoms:
                            clipped_pts = list(line_seg.coords)
                            if len(clipped_pts) >= 2:
                                int_pts = [(int(x), int(y)) for x, y in clipped_pts]
                                draw.line(int_pts, fill=pcolor, width=2)
                except:
                    continue
        
        elif ptype == "cross_hatch":
            if poly_shape is None:
                return
            # Draw two sets of perpendicular hatch lines
            spacing = max(5, (max_x - min_x) // 12)
            # First set (diagonal from top-left to bottom-right)
            for i in range(min_x - max_y, max_x + max_y, spacing):
                line_pts = [(x, x - i) for x in range(min_x - 10, max_x + 10) if min_y - 10 <= x - i <= max_y + 10]
                if len(line_pts) < 2:
                    continue
                try:
                    line = LineString(line_pts)
                    clipped = line.intersection(poly_shape)
                    if clipped.is_empty:
                        continue
                    if clipped.geom_type == 'LineString':
                        clipped_pts = list(clipped.coords)
                        if len(clipped_pts) >= 2:
                            int_pts = [(int(x), int(y)) for x, y in clipped_pts]
                            draw.line(int_pts, fill=pcolor, width=2)
                    elif clipped.geom_type == 'MultiLineString':
                        for line_seg in clipped.geoms:
                            clipped_pts = list(line_seg.coords)
                            if len(clipped_pts) >= 2:
                                int_pts = [(int(x), int(y)) for x, y in clipped_pts]
                                draw.line(int_pts, fill=pcolor, width=2)
                except:
                    continue
            # Second set (diagonal from top-right to bottom-left)
            for i in range(min_x + max_y, max_x - min_y, spacing):
                line_pts = [(x, i - x) for x in range(min_x - 10, max_x + 10) if min_y - 10 <= i - x <= max_y + 10]
                if len(line_pts) < 2:
                    continue
                try:
                    line = LineString(line_pts)
                    clipped = line.intersection(poly_shape)
                    if clipped.is_empty:
                        continue
                    if clipped.geom_type == 'LineString':
                        clipped_pts = list(clipped.coords)
                        if len(clipped_pts) >= 2:
                            int_pts = [(int(x), int(y)) for x, y in clipped_pts]
                            draw.line(int_pts, fill=pcolor, width=2)
                    elif clipped.geom_type == 'MultiLineString':
                        for line_seg in clipped.geoms:
                            clipped_pts = list(line_seg.coords)
                            if len(clipped_pts) >= 2:
                                int_pts = [(int(x), int(y)) for x, y in clipped_pts]
                                draw.line(int_pts, fill=pcolor, width=2)
                except:
                    continue
        
        elif ptype == "dashed":
            if poly_shape is None:
                return
            spacing = max(5, (max_x - min_x) // 12)
            dash_length = 8
            gap_length = 4
            for i in range(min_x - max_y, max_x + max_y, spacing):
                line_pts = [(x, x - i) for x in range(min_x - 10, max_x + 10) if min_y - 10 <= x - i <= max_y + 10]
                if len(line_pts) < 2:
                    continue
                try:
                    line = LineString(line_pts)
                    clipped = line.intersection(poly_shape)
                    if clipped.is_empty:
                        continue
                    if clipped.geom_type == 'LineString':
                        clipped_pts = list(clipped.coords)
                        if len(clipped_pts) >= 2:
                            # Draw dashed line by creating segments
                            total_length = len(clipped_pts)
                            j = 0
                            while j < total_length - 1:
                                end_idx = min(j + dash_length, total_length - 1)
                                if end_idx > j:
                                    int_pts = [(int(x), int(y)) for x, y in clipped_pts[j:end_idx+1]]
                                    if len(int_pts) >= 2:
                                        draw.line(int_pts, fill=pcolor, width=2)
                                j += dash_length + gap_length
                    elif clipped.geom_type == 'MultiLineString':
                        for line_seg in clipped.geoms:
                            clipped_pts = list(line_seg.coords)
                            if len(clipped_pts) >= 2:
                                total_length = len(clipped_pts)
                                j = 0
                                while j < total_length - 1:
                                    end_idx = min(j + dash_length, total_length - 1)
                                    if end_idx > j:
                                        int_pts = [(int(x), int(y)) for x, y in clipped_pts[j:end_idx+1]]
                                        if len(int_pts) >= 2:
                                            draw.line(int_pts, fill=pcolor, width=2)
                                    j += dash_length + gap_length
                except:
                    continue
        
        elif ptype == "dotted":
            if poly_shape is None:
                return
            spacing = max(5, (max_x - min_x) // 12)
            dot_spacing = 4
            dot_radius = 2
            for i in range(min_x - max_y, max_x + max_y, spacing):
                line_pts = [(x, x - i) for x in range(min_x - 10, max_x + 10) if min_y - 10 <= x - i <= max_y + 10]
                if len(line_pts) < 2:
                    continue
                try:
                    line = LineString(line_pts)
                    clipped = line.intersection(poly_shape)
                    if clipped.is_empty:
                        continue
                    if clipped.geom_type == 'LineString':
                        clipped_pts = list(clipped.coords)
                        # Draw dots along the line
                        for j in range(0, len(clipped_pts), dot_spacing):
                            pt = clipped_pts[j]
                            try:
                                if poly_shape.contains(Point(pt)):
                                    draw.ellipse([int(pt[0])-dot_radius, int(pt[1])-dot_radius, 
                                                int(pt[0])+dot_radius, int(pt[1])+dot_radius], fill=pcolor)
                            except:
                                continue
                    elif clipped.geom_type == 'MultiLineString':
                        for line_seg in clipped.geoms:
                            clipped_pts = list(line_seg.coords)
                            for j in range(0, len(clipped_pts), dot_spacing):
                                pt = clipped_pts[j]
                                try:
                                    if poly_shape.contains(Point(pt)):
                                        draw.ellipse([int(pt[0])-dot_radius, int(pt[1])-dot_radius, 
                                                    int(pt[0])+dot_radius, int(pt[1])+dot_radius], fill=pcolor)
                                except:
                                    continue
                except:
                    continue
        
        elif ptype == "dots":
            spacing = 24
            dot_radius = 3
            for y in range(min_y, max_y + 1, spacing):
                for x in range(min_x, max_x + 1, spacing):
                    try:
                        if poly_shape is not None and poly_shape.contains(Point(x, y)):
                            draw.ellipse([x-dot_radius, y-dot_radius, x+dot_radius, y+dot_radius], fill=pcolor)
                    except:
                        continue
    
    def render_polygon_with_holes(self, draw, polygon, tile_bounds, img_size, buffer_pixels,
                                  buffered_size, fill_rgb, color_info, outline_width=1):
        """
        Render polygon with interior rings (holes) properly.
        Create a mask where holes are transparent.
        """
        # Create a temporary image for this polygon with alpha channel
        poly_img = Image.new('RGBA', (buffered_size, buffered_size), (0, 0, 0, 0))
        poly_draw = ImageDraw.Draw(poly_img)
        
        # Convert exterior ring to pixel coordinates
        # Use actual tile bounds for consistent alignment across tiles
        exterior_pixels = []
        lon_range = tile_bounds.east - tile_bounds.west
        lat_range = tile_bounds.north - tile_bounds.south
        for coord in polygon.exterior.coords:
            lon, lat = coord[0], coord[1]
            # Convert to pixel coordinates using actual tile bounds
            px = ((lon - tile_bounds.west) / lon_range * img_size) + buffer_pixels
            py = ((tile_bounds.north - lat) / lat_range * img_size) + buffer_pixels
            exterior_pixels.append((int(px), int(py)))
        
        if len(exterior_pixels) < 3:
            return
        
        # Draw exterior ring with full opacity and black outline
        fill_rgba = fill_rgb + (255,) if fill_rgb else None  # Add alpha channel
        black_outline = (0, 0, 0, 255)  # Black outline
        
        # Check if pattern should be applied
        if 'pattern' in color_info:
            # Apply pattern (dots, hatch, etc.)
            pattern_color = self.hex_to_rgb(color_info['pattern_color'])
            self.create_pattern(poly_draw, exterior_pixels, fill_rgb, 
                             color_info['pattern'], 
                             pattern_color,
                             buffered_size)
        else:
            # Draw fill first, then outline on top for precise boundaries
            if fill_rgba:
                poly_draw.polygon(exterior_pixels, fill=fill_rgba)
        
        # Draw black outline
        if len(exterior_pixels) > 1:
            closed_pixels = exterior_pixels + [exterior_pixels[0]]
            poly_draw.line(closed_pixels, fill=black_outline, width=outline_width)
        
        # Draw interior rings (holes) as transparent (black with full alpha = cut out)
        for interior in polygon.interiors:
            interior_pixels = []
            for coord in interior.coords:
                lon, lat = coord[0], coord[1]
                # Convert to pixel coordinates using actual tile bounds
                px = ((lon - tile_bounds.west) / lon_range * img_size) + buffer_pixels
                py = ((tile_bounds.north - lat) / lat_range * img_size) + buffer_pixels
                interior_pixels.append((int(px), int(py)))
            
            if len(interior_pixels) >= 3:
                # Draw hole as transparent (cut out from fill)
                poly_draw.polygon(interior_pixels, fill=(0, 0, 0, 0))
                # Draw hole outline
                if len(interior_pixels) > 1:
                    closed_interior = interior_pixels + [interior_pixels[0]]
                    poly_draw.line(closed_interior, fill=black_outline, width=outline_width)
        
        # Composite polygon onto main image
        return poly_img
    
    def render_tile_seamless(self, tile):
        """Render a single tile with seamless boundaries"""
        tile_bounds = mercantile.bounds(tile)
        buffer_degrees = 0.01  # Buffer in degrees
        buffered_bounds = box(
            tile_bounds.west - buffer_degrees,
            tile_bounds.south - buffer_degrees,
            tile_bounds.east + buffer_degrees,
            tile_bounds.north + buffer_degrees
        )
        
        # Find features intersecting buffered tile area
        candidate_ids = list(self.spatial_index.intersection(buffered_bounds.bounds))
        
        if not candidate_ids:
            return None
        
        zoom = tile.z
        scale = self.get_zoom_scale(zoom)
        min_size = self.get_min_feature_size(zoom, scale)
        outline_width = self.get_outline_width(zoom)
        
        # Create buffered image
        img_size = self.tile_size * scale
        buffer_pixels = int(img_size * 0.1)
        buffered_size = img_size + (2 * buffer_pixels)
        img_buffered = Image.new('RGBA', (buffered_size, buffered_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img_buffered)
        
        color_map = self.get_color_map()
        rendered_count = 0
        
        for feature_id in candidate_ids:
            try:
                feature_data = self.feature_lookup[feature_id]
                geom = feature_data['geometry']
                
                if not geom.intersects(buffered_bounds):
                    continue
                
                category = feature_data['category']
                color_info = color_map.get(category, {'fill': '#FFFFFF', 'outline': '#CCCCCC'})
                
                fill_hex = color_info.get('fill')
                fill_rgb = self.hex_to_rgb(fill_hex) if fill_hex else None
                
                if isinstance(geom, Polygon):
                    if geom.area < 1e-10:
                        continue
                    
                    # Render polygon with holes
                    poly_img = self.render_polygon_with_holes(
                        draw, geom, tile_bounds, img_size, buffer_pixels,
                        buffered_size, fill_rgb, color_info, outline_width
                    )
                    
                    if poly_img:
                        # Composite polygon image onto main image
                        img_buffered = Image.alpha_composite(img_buffered, poly_img)
                        
                        # Apply patterns if specified
                        if 'pattern' in color_info and fill_rgb is not None:
                            # Get exterior ring coordinates for pattern
                            exterior_pixels = []
                            lon_range = tile_bounds.east - tile_bounds.west
                            lat_range = tile_bounds.north - tile_bounds.south
                            for coord in geom.exterior.coords:
                                lon, lat = coord[0], coord[1]
                                px = ((lon - tile_bounds.west) / lon_range * img_size) + buffer_pixels
                                py = ((tile_bounds.north - lat) / lat_range * img_size) + buffer_pixels
                                exterior_pixels.append((int(px), int(py)))
                            
                            if len(exterior_pixels) >= 3:
                                pattern_color = self.hex_to_rgb(color_info.get('pattern_color', '#000000'))
                                self.create_pattern(
                                    draw, exterior_pixels, fill_rgb,
                                    color_info['pattern'], pattern_color, buffered_size
                                )
                                # Redraw outline after pattern
                                if len(exterior_pixels) > 1:
                                    closed_pixels = exterior_pixels + [exterior_pixels[0]]
                                    draw.line(closed_pixels, fill=(0, 0, 0), width=outline_width)
                        elif 'pattern' in color_info and fill_rgb is None:
                            # Pattern only, no fill
                            exterior_pixels = []
                            lon_range = tile_bounds.east - tile_bounds.west
                            lat_range = tile_bounds.north - tile_bounds.south
                            for coord in geom.exterior.coords:
                                lon, lat = coord[0], coord[1]
                                px = ((lon - tile_bounds.west) / lon_range * img_size) + buffer_pixels
                                py = ((tile_bounds.north - lat) / lat_range * img_size) + buffer_pixels
                                exterior_pixels.append((int(px), int(py)))
                            
                            if len(exterior_pixels) >= 3:
                                pattern_color = self.hex_to_rgb(color_info.get('pattern_color', '#000000'))
                                self.create_pattern(
                                    draw, exterior_pixels, None,
                                    color_info['pattern'], pattern_color, buffered_size
                                )
                                # Draw outline
                                if len(exterior_pixels) > 1:
                                    closed_pixels = exterior_pixels + [exterior_pixels[0]]
                                    outline_color = self.hex_to_rgb(color_info.get('outline', '#000000'))
                                    draw.line(closed_pixels, fill=outline_color, width=outline_width)
                    
                    rendered_count += 1
                
                elif hasattr(geom, 'geoms'):  # MultiPolygon
                    for poly in geom.geoms:
                        if poly.area < 1e-10:
                            continue
                        
                        poly_img = self.render_polygon_with_holes(
                            draw, poly, tile_bounds, img_size, buffer_pixels,
                            buffered_size, fill_rgb, color_info, outline_width
                        )
                        
                        if poly_img:
                            img_buffered = Image.alpha_composite(img_buffered, poly_img)
                            
                            # Apply patterns if specified
                            if 'pattern' in color_info:
                                exterior_pixels = []
                                lon_range = tile_bounds.east - tile_bounds.west
                                lat_range = tile_bounds.north - tile_bounds.south
                                for coord in poly.exterior.coords:
                                    lon, lat = coord[0], coord[1]
                                    px = ((lon - tile_bounds.west) / lon_range * img_size) + buffer_pixels
                                    py = ((tile_bounds.north - lat) / lat_range * img_size) + buffer_pixels
                                    exterior_pixels.append((int(px), int(py)))
                                
                                if len(exterior_pixels) >= 3:
                                    pattern_color = self.hex_to_rgb(color_info.get('pattern_color', '#000000'))
                                    self.create_pattern(
                                        draw, exterior_pixels, fill_rgb,
                                        color_info['pattern'], pattern_color, buffered_size
                                    )
                                    if len(exterior_pixels) > 1:
                                        closed_pixels = exterior_pixels + [exterior_pixels[0]]
                                        draw.line(closed_pixels, fill=(0, 0, 0), width=outline_width)
                        
                        rendered_count += 1
                
                else:
                    # Point or very small feature - render as dot
                    if hasattr(geom, 'x') and hasattr(geom, 'y'):
                        lon, lat = geom.x, geom.y
                        lon_range = tile_bounds.east - tile_bounds.west
                        lat_range = tile_bounds.north - tile_bounds.south
                        px = ((lon - tile_bounds.west) / lon_range * img_size) + buffer_pixels
                        py = ((tile_bounds.north - lat) / lat_range * img_size) + buffer_pixels
                        
                        if fill_rgb:
                            dot_size = max(2, min_size // 2)
                            draw.ellipse([px - dot_size, py - dot_size,
                                        px + dot_size, py + dot_size],
                                       fill=fill_rgb, outline=(0, 0, 0), width=outline_width)
                            rendered_count += 1
                    
            except:
                pass
        
        if rendered_count == 0:
            return None
        
        # Crop buffer
        img = img_buffered.crop((buffer_pixels, buffer_pixels, 
                                buffered_size - buffer_pixels, 
                                buffered_size - buffer_pixels))
        
        # Downsample
        img = img.resize((self.tile_size, self.tile_size), Image.LANCZOS)
        return img
    
    def generate_tiles(self, min_zoom=7, max_zoom=18):
        """Generate seamless tiles for Puducherry"""
        print(f"\n{'='*80}")
        print(f"GENERATING PUDUCHERRY TILES (Zoom {min_zoom}-{max_zoom})")
        print(f"Mode: SEAMLESS - NO TILE BOUNDARIES")
        print(f"{'='*80}")
        
        bounds = self.get_bounds()
        print(f"Bounds: [{bounds[1]:.4f}, {bounds[0]:.4f}] to [{bounds[3]:.4f}, {bounds[2]:.4f}]\n")
        
        total_tiles = 0
        overall_start = time.time()
        
        for zoom in range(min_zoom, max_zoom + 1):
            zoom_start = time.time()
            
            tiles = list(mercantile.tiles(
                bounds[0], bounds[1], bounds[2], bounds[3], 
                zooms=[zoom]
            ))
            
            total_for_zoom = len(tiles)
            scale = self.get_zoom_scale(zoom)
            min_size = self.get_min_feature_size(zoom, scale)
            
            print(f"Zoom {zoom:2d} | {total_for_zoom:,} tiles | Scale: {scale}x | Min: {min_size:.1f}px", 
                  end=" ", flush=True)
            
            zoom_dir = self.output_dir / str(zoom)
            rendered = 0
            
            for tile in tiles:
                img = self.render_tile_seamless(tile)
                
                if img is not None:
                    tile_dir = zoom_dir / str(tile.x)
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    
                    tile_path = tile_dir / f"{tile.y}.png"
                    img.save(tile_path, 'PNG', optimize=True)
                    rendered += 1
            
            zoom_elapsed = time.time() - zoom_start
            speed = rendered / zoom_elapsed if zoom_elapsed > 0 else 0
            print(f"| ✓ {rendered:,} in {zoom_elapsed:.1f}s ({speed:.1f} t/s)")
            
            total_tiles += rendered
        
        overall_elapsed = time.time() - overall_start
        print(f"\n{'='*80}")
        print(f"✓ COMPLETE: {total_tiles:,} tiles in {overall_elapsed:.1f}s "
              f"({overall_elapsed/60:.1f} min)")
        print(f"{'='*80}\n")
    
    def generate_html_viewer(self):
        """Generate viewer for Puducherry"""
        bounds = self.get_bounds()
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Puducherry Master Plan - Seamless Tiles</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    body, html, #map {{ margin:0; padding:0; height:100%; }}
    .info {{ padding: 10px; background: white; border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.2); }}
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const map = L.map('map').setView([{center_lat:.6f}, {center_lon:.6f}], 11);
    
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
      attribution: 'Esri',
      maxZoom: 19
    }}).addTo(map);
    
    L.tileLayer('./{{z}}/{{x}}/{{y}}.png', {{
      minZoom: 7,
      maxZoom: 18,
      opacity: 0.9,
      attribution: 'Puducherry Master Plan'
    }}).addTo(map);
    
    const info = L.control({{position: 'topright'}});
    info.onAdd = function() {{
      this._div = L.DomUtil.create('div', 'info');
      this._div.innerHTML = '<b>Puducherry Master Plan</b><br/>Seamless tiles - no boundaries<br/>Zoom: ' + map.getZoom();
      return this._div;
    }};
    info.addTo(map);
    
    map.on('zoomend', function() {{
      info._div.innerHTML = '<b>Puducherry Master Plan</b><br/>Seamless tiles - no boundaries<br/>Zoom: ' + map.getZoom();
    }});
  </script>
</body>
</html>"""
        
        (self.output_dir / 'index.html').write_text(html)
        print(f"✓ Viewer saved: {self.output_dir}/index.html")


def main():
    import sys
    
    possible_paths = [
        Path('data/puducherry/master_plan'),
        Path('/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping/data/puducherry/master_plan'),
    ]
    
    data_dir = None
    for path in possible_paths:
        if path.exists():
            data_dir = path
            break
    
    if data_dir is None:
        print("Enter path to Puducherry master_plan directory:")
        user_path = input("> ").strip()
        data_dir = Path(user_path)
        if not data_dir.exists():
            print(f"✗ Path not found: {data_dir}")
            sys.exit(1)
    
    output_dir = Path('./puducherry_tiles_seamless')
    
    print("="*80)
    print("PUDUCHERRY MASTER PLAN - SEAMLESS TILE GENERATOR")
    print("✅ Properly handles polygon holes/interior rings")
    print("✅ Supports hatch, cross_hatch, dashed, dotted, and dots patterns")
    print("="*80)
    print(f"Input:  {data_dir}")
    print(f"Output: {output_dir}")
    
    generator = PuducherrySeamlessTiles(data_dir, output_dir)
    generator.load_geojson_files()
    
    if generator.feature_id_counter == 0:
        print("✗ No features loaded!")
        sys.exit(1)
    
    generator.generate_tiles(min_zoom=7, max_zoom=18)
    generator.generate_html_viewer()
    
    print(f"\n💡 To view: cd {output_dir} && python3 -m http.server 8001")
    print(f"   Then open: http://localhost:8001/\n")


if __name__ == '__main__':
    main()

