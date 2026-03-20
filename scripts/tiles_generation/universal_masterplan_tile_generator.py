#!/usr/bin/env python3
"""
Universal Master Plan Tile Generator
Reads color mappings from legend.csv in the data directory
Works for ANY city/region with proper legend.csv configuration
"""

import argparse
import json
import csv
import math
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import shape, box, Point, Polygon, LineString, MultiPolygon
from shapely.ops import transform
from rtree import index

try:
    from pyproj import Transformer
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False
    print("Warning: pyproj not available. Coordinate transformation disabled.")


class UniversalMasterPlanTiles:
    def __init__(self, data_dir, output_dir, legend_file='legend.csv'):
        """
        Initialize Universal Tile Generator
        
        Args:
            data_dir: Directory containing GeoJSON files and legend.csv
            output_dir: Output directory for tiles
            legend_file: Name of the legend CSV file (default: legend.csv)
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.legend_file = self.data_dir / legend_file
        self.tile_size = 256
        self.spatial_index = index.Index()
        self.feature_id_counter = 0
        self.feature_lookup = {}
        self.source_crs = None
        self.needs_transform = None
        self.transformer = None
        
        # Load color mappings from CSV
        self.color_map = self._load_legend_csv()
        
        # Pre-compute RGB values for faster access
        self._color_map_rgb = None
        self._init_color_cache()
        
    def _load_legend_csv(self):
        """
        Load color mappings from legend.csv
        
        Expected CSV format:
        category,fill_color,outline_color,pattern,pattern_color
        Residential,#ffff00,#000000,,
        Commercial,#ff0000,#000000,,
        Green Belt,#ffffff,#000000,hatch,#00ff00
        Heritage,#d0ffb8,#000000,dotted,#000000
        """
        if not self.legend_file.exists():
            print(f"⚠️  Legend file not found: {self.legend_file}")
            print("Creating default color map...")
            return self._get_default_color_map()
        
        print(f"📖 Loading legend from: {self.legend_file}")
        color_map = {}
        
        try:
            with open(self.legend_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    category = row.get('category', '').strip()
                    if not category:
                        continue
                    
                    # Normalize category (uppercase with spaces)
                    category_norm = self.normalize_category(category)
                    
                    color_info = {}
                    
                    # Fill color (can be empty for pattern-only fills)
                    fill = row.get('fill_color', '').strip()
                    color_info['fill'] = fill if fill else None
                    
                    # Outline color (default to black if not specified)
                    outline = row.get('outline_color', '').strip()
                    color_info['outline'] = outline if outline else '#000000'
                    
                    # Pattern (hatch, dots, cross_hatch, dashed, dotted)
                    pattern = row.get('pattern', '').strip().lower()
                    if pattern:
                        color_info['pattern'] = pattern
                        pattern_color = row.get('pattern_color', '').strip()
                        color_info['pattern_color'] = pattern_color if pattern_color else '#000000'
                    
                    color_map[category_norm] = color_info
                    
                    # Also add underscore version
                    category_underscore = category_norm.replace(' ', '_')
                    color_map[category_underscore] = color_info
            
            print(f"✓ Loaded {len(color_map) // 2} categories from legend")
            return color_map
            
        except Exception as e:
            print(f"⚠️  Error loading legend: {e}")
            print("Using default color map...")
            return self._get_default_color_map()
    
    def _get_default_color_map(self):
        """Fallback color map if legend.csv is missing"""
        return {
            'DEFAULT': {'fill': '#CCCCCC', 'outline': '#999999'},
            'RESIDENTIAL': {'fill': '#FFFF00', 'outline': '#000000'},
            'COMMERCIAL': {'fill': '#FF0000', 'outline': '#000000'},
            'INDUSTRIAL': {'fill': '#A900E6', 'outline': '#000000'},
            'GREEN': {'fill': '#4CE600', 'outline': '#000000'},
            'WATER': {'fill': '#73DFFF', 'outline': '#000000'},
        }
    
    def _init_color_cache(self):
        """Pre-compute RGB values for all colors to avoid repeated conversions"""
        self._color_map_rgb = {}
        for key, value in self.color_map.items():
            rgb_value = {}
            if 'fill' in value and value['fill']:
                rgb_value['fill'] = self.hex_to_rgb(value['fill'])
            else:
                rgb_value['fill'] = None
            if 'outline' in value and value['outline']:
                rgb_value['outline'] = self.hex_to_rgb(value['outline'])
            else:
                rgb_value['outline'] = (0, 0, 0)
            if 'pattern_color' in value and value['pattern_color']:
                rgb_value['pattern_color'] = self.hex_to_rgb(value['pattern_color'])
            # Copy other keys
            for k, v in value.items():
                if k not in ['fill', 'outline', 'pattern_color']:
                    rgb_value[k] = v
            self._color_map_rgb[key] = rgb_value
    
    def normalize_category(self, value):
        """Normalize category name"""
        if not value:
            return None
        value = " ".join(str(value).replace("_", " ").split())
        return value.upper()
    
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
        if zoom <= 8:
            return 3
        elif zoom <= 10:
            return 2
        elif zoom <= 13:
            return 1
        else:
            return 1

    def _meters_per_pixel_at_lat(self, zoom, lat):
        """Web Mercator ground resolution (meters per pixel) at given latitude and zoom."""
        return 40075016.686 * math.cos(math.radians(lat)) / (256 * (2 ** zoom))

    def _get_wgs84_merc_transformers(self):
        """Lazy-init pyproj transformers for meter-accurate buffering (cached)."""
        if not HAS_PYPROJ:
            return None, None
        if not hasattr(self, '_tr_wgs_to_merc'):
            self._tr_wgs_to_merc = Transformer.from_crs('EPSG:4326', 'EPSG:3857', always_xy=True)
            self._tr_merc_to_wgs = Transformer.from_crs('EPSG:3857', 'EPSG:4326', always_xy=True)
        return self._tr_wgs_to_merc, self._tr_merc_to_wgs

    def _buffer_geom_meters(self, geom, meters):
        """Buffer geometry by distance in meters (EPSG:3857) for correct coastal strips."""
        if meters <= 0 or geom is None or geom.is_empty:
            return geom
        fwd, rev = self._get_wgs84_merc_transformers()
        if fwd is None or rev is None:
            return self._buffer_geom_meters_fallback_degrees(geom, meters)

        def to_merc(x, y, z=None):
            return fwd.transform(x, y)

        def to_wgs(x, y, z=None):
            return rev.transform(x, y)

        try:
            if geom.geom_type == 'Polygon':
                g2 = transform(to_merc, geom)
                g2 = g2.buffer(meters)
                return transform(to_wgs, g2)
            if geom.geom_type == 'MultiPolygon':
                parts = []
                for p in geom.geoms:
                    g2 = transform(to_merc, p)
                    g2 = g2.buffer(meters)
                    parts.append(transform(to_wgs, g2))
                if not parts:
                    return geom
                return MultiPolygon(parts)
            return geom
        except Exception:
            return geom

    def _buffer_geom_meters_fallback_degrees(self, geom, meters):
        """Approximate buffer in degrees when pyproj is unavailable (~111 km/deg)."""
        try:
            deg_buf = min(max(meters, 0) / 111320.0, 0.012)
            if deg_buf <= 0:
                return geom
            return geom.buffer(deg_buf)
        except Exception:
            return geom

    def _expand_thin_polygon_for_low_zoom(self, geom, zoom, tile_bounds, img_size,
                                          lon_range, lat_range):
        """
        Coastal / narrow CRZ strips map to sub-pixel width at low zoom; raster fill disappears.
        Expand thin axis-aligned bounds in pixel space so fills stay visible after downscale.
        """
        if zoom > 11 or geom is None or geom.is_empty:
            return geom
        if min(lon_range, lat_range) <= 0:
            return geom
        try:
            min_lon, min_lat, max_lon, max_lat = geom.bounds
        except Exception:
            return geom
        px_w = abs((max_lon - min_lon) / lon_range * img_size)
        px_h = abs((max_lat - min_lat) / lat_range * img_size)
        min_px = min(px_w, px_h) if px_w > 0 and px_h > 0 else 0
        # Target ~3px in supersampled space so LANCZOS downscale to 256 still shows color
        TARGET = 3.0
        if min_px >= TARGET:
            return geom
        deficit = TARGET - min_px
        lat_mid = (tile_bounds.north + tile_bounds.south) / 2
        m_per_px = self._meters_per_pixel_at_lat(zoom, lat_mid)
        meters = min(deficit * m_per_px, 400.0)
        if meters < 2.0:
            return geom
        return self._buffer_geom_meters(geom, meters)

    def load_geojson_files(self):
        """Load all GeoJSON files from data directory"""
        print("\n" + "="*80)
        print("LOADING GEOJSON DATA")
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
                
                # Detect CRS from GeoJSON file (check first file only)
                if self.needs_transform is None and idx == 1:
                    crs_info = data.get('crs', {})
                    if crs_info:
                        crs_name = crs_info.get('properties', {}).get('name', '')
                        if 'EPSG:3857' in crs_name or '3857' in crs_name:
                            self.source_crs = 'EPSG:3857'
                            print(f"\n✓ Detected CRS: EPSG:3857 (Web Mercator)")
                        elif 'EPSG:4326' in crs_name or '4326' in crs_name:
                            self.source_crs = 'EPSG:4326'
                            print(f"\n✓ Detected CRS: EPSG:4326 (WGS84)")
                        else:
                            # Try to detect from coordinates
                            if data.get('features'):
                                test_geom = shape(data['features'][0]['geometry'])
                                x, y = test_geom.bounds[0], test_geom.bounds[1]
                                if 8000000 < x < 9000000 and 1300000 < y < 1400000:
                                    self.source_crs = 'EPSG:3857'
                                    print(f"\n✓ Detected CRS: EPSG:3857 (Web Mercator) from coordinates")
                                elif abs(x) < 180 and abs(y) < 90:
                                    self.source_crs = 'EPSG:4326'
                                    print(f"\n✓ Detected CRS: EPSG:4326 (WGS84) from coordinates")
                    
                    # Setup transformer if needed
                    if self.source_crs and self.source_crs != 'EPSG:4326':
                        if HAS_PYPROJ:
                            try:
                                self.transformer = Transformer.from_crs(self.source_crs, 'EPSG:4326', always_xy=True)
                                self.needs_transform = True
                                print(f"✓ Coordinate transformation enabled: {self.source_crs} -> EPSG:4326")
                            except Exception as e:
                                print(f"⚠️ Could not initialize transformer: {e}")
                                self.needs_transform = False
                        else:
                            print("⚠️ pyproj not available. Cannot transform coordinates.")
                            self.needs_transform = False
                    else:
                        self.needs_transform = False
                
                for feature in features:
                    try:
                        geom = shape(feature['geometry'])
                        
                        # Transform geometry to WGS84 if needed
                        if self.needs_transform and self.transformer:
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
                        name_value = props.get("Name") or props.get("name") or props.get("NAME")
                        raw_category = (
                            props.get("LANDUSE_CATEGORY")
                            or props.get("Layer Name")
                            or props.get("Layer_Name")
                            or props.get("LAYER_NAME")
                            or props.get("LANDUSE_CATEGORY")
                            or props.get("LANDUSE_SUBCAT_LEVEL_1")
                            or props.get("CATEGORY")
                            or props.get("SUB_CATEGO")
                            or name_value
                            or props.get("Label")
                            or props.get("use")
                            or props.get("use1")
                            or props.get("LAYER")
                            or file_name
                        )
                        category_norm = self.normalize_category(str(raw_category)) if raw_category else self.normalize_category(file_name) or file_name.upper()
                        
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
        
        elif ptype == "cross_hatch":
            if poly_shape is None:
                return
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
                                  buffered_size, fill_rgb, color_info, outline_width=1, lon_range=None, lat_range=None):
        """Render polygon with interior rings (holes) properly"""
        if lon_range is None:
            lon_range = tile_bounds.east - tile_bounds.west
        if lat_range is None:
            lat_range = tile_bounds.north - tile_bounds.south
        
        exterior_pixels = []
        for coord in polygon.exterior.coords:
            lon, lat = coord[0], coord[1]
            px = ((lon - tile_bounds.west) / lon_range * img_size) + buffer_pixels
            py = ((tile_bounds.north - lat) / lat_range * img_size) + buffer_pixels
            exterior_pixels.append((int(px), int(py)))
        
        if len(exterior_pixels) < 3:
            return None
        
        poly_img = Image.new('RGBA', (buffered_size, buffered_size), (0, 0, 0, 0))
        poly_draw = ImageDraw.Draw(poly_img)
        
        fill_rgba = fill_rgb + (255,) if fill_rgb else None
        black_outline = (0, 0, 0, 255)
        
        if 'pattern' in color_info:
            pattern_color_rgb = color_info.get('pattern_color', (0, 0, 0))
            self.create_pattern(poly_draw, exterior_pixels, fill_rgb, 
                             color_info['pattern'], 
                             pattern_color_rgb,
                             buffered_size)
        elif fill_rgba:
            poly_draw.polygon(exterior_pixels, fill=fill_rgba)
        
        if len(exterior_pixels) > 1:
            closed_pixels = exterior_pixels + [exterior_pixels[0]]
            poly_draw.line(closed_pixels, fill=black_outline, width=outline_width)
        
        for interior in polygon.interiors:
            interior_pixels = []
            for coord in interior.coords:
                lon, lat = coord[0], coord[1]
                px = ((lon - tile_bounds.west) / lon_range * img_size) + buffer_pixels
                py = ((tile_bounds.north - lat) / lat_range * img_size) + buffer_pixels
                interior_pixels.append((int(px), int(py)))
            
            if len(interior_pixels) >= 3:
                poly_draw.polygon(interior_pixels, fill=(0, 0, 0, 0))
                if len(interior_pixels) > 1:
                    closed_interior = interior_pixels + [interior_pixels[0]]
                    poly_draw.line(closed_interior, fill=black_outline, width=outline_width)
        
        return poly_img
    
    def render_tile_seamless(self, tile):
        """Render a single tile with seamless boundaries"""
        tile_bounds = mercantile.bounds(tile)
        buffer_degrees = 0.01
        buffered_bounds = box(
            tile_bounds.west - buffer_degrees,
            tile_bounds.south - buffer_degrees,
            tile_bounds.east + buffer_degrees,
            tile_bounds.north + buffer_degrees
        )
        
        candidate_ids = list(self.spatial_index.intersection(buffered_bounds.bounds))
        
        if not candidate_ids:
            return None
        
        zoom = tile.z
        scale = self.get_zoom_scale(zoom)
        min_size = self.get_min_feature_size(zoom, scale)
        outline_width = self.get_outline_width(zoom)
        
        img_size = self.tile_size * scale
        buffer_pixels = int(img_size * 0.1)
        buffered_size = img_size + (2 * buffer_pixels)
        img_buffered = Image.new('RGBA', (buffered_size, buffered_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img_buffered)
        
        lon_range = tile_bounds.east - tile_bounds.west
        lat_range = tile_bounds.north - tile_bounds.south
        
        color_map = self._color_map_rgb
        rendered_count = 0
        
        for feature_id in candidate_ids:
            try:
                feature_data = self.feature_lookup[feature_id]
                geom = feature_data['geometry']
                
                if not geom.intersects(buffered_bounds):
                    continue
                
                category = feature_data['category']
                color_info = color_map.get(category, color_map.get('DEFAULT', {'fill': (204, 204, 204), 'outline': (153, 153, 153)}))
                
                fill_rgb = color_info.get('fill')
                # GeoJSON HEX fallback when legend has no fill / category mismatch
                props_fb = feature_data.get('properties') or {}
                if fill_rgb is None and not color_info.get('pattern'):
                    hex_val = props_fb.get('HEX') or props_fb.get('hex')
                    if hex_val:
                        try:
                            fill_rgb = self.hex_to_rgb(str(hex_val).strip())
                        except (ValueError, TypeError):
                            pass
                
                if isinstance(geom, Polygon):
                    if geom.area < 1e-10:
                        continue
                    geom = self._expand_thin_polygon_for_low_zoom(
                        geom, zoom, tile_bounds, img_size, lon_range, lat_range
                    )
                    
                    poly_img = self.render_polygon_with_holes(
                        draw, geom, tile_bounds, img_size, buffer_pixels,
                        buffered_size, fill_rgb, color_info, outline_width,
                        lon_range, lat_range
                    )
                    
                    if poly_img:
                        img_buffered = Image.alpha_composite(img_buffered, poly_img)
                    
                    rendered_count += 1
                
                elif hasattr(geom, 'geoms'):
                    for poly in geom.geoms:
                        if poly.area < 1e-10:
                            continue
                        poly = self._expand_thin_polygon_for_low_zoom(
                            poly, zoom, tile_bounds, img_size, lon_range, lat_range
                        )
                        
                        poly_img = self.render_polygon_with_holes(
                            draw, poly, tile_bounds, img_size, buffer_pixels,
                            buffered_size, fill_rgb, color_info, outline_width,
                            lon_range, lat_range
                        )
                        
                        if poly_img:
                            img_buffered = Image.alpha_composite(img_buffered, poly_img)
                        
                        rendered_count += 1
                
                else:
                    if hasattr(geom, 'x') and hasattr(geom, 'y'):
                        lon, lat = geom.x, geom.y
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
        
        img = img_buffered.crop((buffer_pixels, buffer_pixels, 
                                buffered_size - buffer_pixels, 
                                buffered_size - buffer_pixels))
        
        img = img.resize((self.tile_size, self.tile_size), Image.LANCZOS)
        return img
    
    def generate_tiles(self, min_zoom=7, max_zoom=18, force=False):
        """Generate seamless tiles"""
        print(f"\n{'='*80}")
        print(f"GENERATING TILES (Zoom {min_zoom}-{max_zoom})" + (" [FORCE]" if force else ""))
        print(f"Mode: SEAMLESS - NO TILE BOUNDARIES")
        print(f"{'='*80}")
        
        bounds = self.get_bounds()
        print(f"Bounds: [{bounds[1]:.4f}, {bounds[0]:.4f}] to [{bounds[3]:.4f}, {bounds[2]:.4f}]\n")
        
        # Create output directory upfront
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
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
                tile_dir = zoom_dir / str(tile.x)
                tile_path = tile_dir / f"{tile.y}.png"

                # Skip rendering if this tile already exists (unless --force)
                if not force and tile_path.exists():
                    continue

                img = self.render_tile_seamless(tile)
                
                if img is not None:
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    
                    img.save(tile_path, 'PNG', optimize=False)
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
    
    def generate_html_viewer(self, city_name="Master Plan"):
        """Generate HTML viewer"""
        bounds = self.get_bounds()
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{city_name} - Seamless Tiles</title>
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
      attribution: '{city_name}'
    }}).addTo(map);
    
    const info = L.control({{position: 'topright'}});
    info.onAdd = function() {{
      this._div = L.DomUtil.create('div', 'info');
      this._div.innerHTML = '<b>{city_name}</b><br/>Seamless tiles<br/>Zoom: ' + map.getZoom();
      return this._div;
    }};
    info.addTo(map);
    
    map.on('zoomend', function() {{
      info._div.innerHTML = '<b>{city_name}</b><br/>Seamless tiles<br/>Zoom: ' + map.getZoom();
    }});
  </script>
</body>
</html>"""
        
        (self.output_dir / 'index.html').write_text(html)
        print(f"✓ Viewer saved: {self.output_dir}/index.html")


def main():
    parser = argparse.ArgumentParser(
        description="Universal Master Plan Tile Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Required in data directory:
  - *.geojson files (your GeoJSON data)
  - legend.csv (color mapping configuration)

legend.csv format:
  category,fill_color,outline_color,pattern,pattern_color
  Residential,#ffff00,#000000,,
  Green Belt,#ffffff,#000000,hatch,#00ff00

Supported patterns: hatch, dots, cross_hatch, dashed, dotted
        """,
    )
    parser.add_argument("data_directory", help="Directory containing GeoJSON files and legend.csv")
    parser.add_argument(
        "output_directory",
        nargs="?",
        default=None,
        help="Output directory for tiles (default: <data_directory_name>_tiles)",
    )
    parser.add_argument(
        "city_name",
        nargs="?",
        default=None,
        help="City/region name for viewer (default: derived from data directory)",
    )
    parser.add_argument(
        "--min-zoom",
        type=int,
        default=7,
        metavar="Z",
        help="Minimum zoom level (default: 7)",
    )
    parser.add_argument(
        "--max-zoom",
        type=int,
        default=18,
        metavar="Z",
        help="Maximum zoom level (default: 18)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate tiles even if they already exist",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_directory)
    output_dir = Path(args.output_directory) if args.output_directory else Path(f"./{data_dir.name}_tiles")
    city_name = args.city_name if args.city_name else data_dir.name.title()

    if not data_dir.exists():
        print(f"✗ Data directory not found: {data_dir}")
        sys.exit(1)

    if args.min_zoom > args.max_zoom:
        print("✗ --min-zoom must be <= --max-zoom")
        sys.exit(1)

    print("="*80)
    print("UNIVERSAL MASTER PLAN TILE GENERATOR")
    print("✅ Handles polygon holes/interior rings")
    print("✅ Supports all pattern types")
    print("✅ Auto-detects CRS and transforms coordinates")
    print("✅ Optimized for speed")
    print("="*80)
    print(f"Input:  {data_dir}")
    print(f"Output: {output_dir}")
    print(f"City:   {city_name}")
    print(f"Zoom:   {args.min_zoom}-{args.max_zoom}" + (" (force)" if args.force else ""))

    generator = UniversalMasterPlanTiles(data_dir, output_dir)
    generator.load_geojson_files()

    if generator.feature_id_counter == 0:
        print("✗ No features loaded!")
        sys.exit(1)

    generator.generate_tiles(
        min_zoom=args.min_zoom,
        max_zoom=args.max_zoom,
        force=args.force,
    )
    generator.generate_html_viewer(city_name)
    
    print(f"\n💡 To view: cd {output_dir} && python3 -m http.server 8001")
    print(f"   Then open: http://localhost:8001/\n")


if __name__ == '__main__':
    main()

