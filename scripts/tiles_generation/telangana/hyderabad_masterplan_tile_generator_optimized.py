#!/usr/bin/env python3
"""
Hyderabad Master Plan - OPTIMIZED TILE GENERATOR
Uses pre-split features for dramatically faster tile generation at high zoom levels
Handles both HMDA and HUDA subdirectories
Reads color mappings from legend.csv in each subdirectory
"""

import json
import csv
import sys
import time
import os
import threading
from pathlib import Path
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import shape, box, Point, Polygon, LineString
from shapely.ops import transform
from rtree import index
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from pyproj import Transformer
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False


class HyderabadMasterPlanTilesOptimized:
    def __init__(self, data_dir, output_dir, max_workers=None):
        """Initialize optimized Hyderabad tile generator"""
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.spatial_index = index.Index()
        self.feature_id_counter = 0
        self.feature_lookup = {}
        self.source_crs = None
        self.needs_transform = None
        self.transformer = None
        
        # Parallel processing
        if max_workers is None:
            # Use 60% of available CPUs, but cap at 32 for stability
            cpu_count = os.cpu_count() or 80
            max_workers = min(32, max(1, int(cpu_count * 0.6)))
        self.max_workers = max_workers
        
        # Load color mappings from both HMDA and HUDA legend files
        self.color_map = {}
        self._load_legends()
        
        # Pre-compute RGB values
        self._color_map_rgb = None
        self._init_color_cache()
        
        # Thread safety: lock for geometry access (though Shapely should be thread-safe for reads)
        self._geometry_lock = threading.Lock()
    
    def _load_legends(self):
        """Load legend.csv from both HMDA and HUDA subdirectories"""
        for subdir in ['HMDA', 'HUDA']:
            legend_file = self.data_dir / subdir / 'legend.csv'
            if legend_file.exists():
                print(f"📖 Loading {subdir} legend from: {legend_file}")
                self._load_single_legend(legend_file)
            else:
                print(f"⚠️  {subdir} legend not found: {legend_file}")
    
    def _load_single_legend(self, legend_file):
        """Load a single legend.csv file"""
        try:
            with open(legend_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    category = row.get('category', '').strip()
                    if not category:
                        continue
                    
                    category_norm = self.normalize_category(category)
                    
                    color_info = {}
                    fill = row.get('fill_color', '').strip()
                    color_info['fill'] = fill if fill else None
                    
                    outline = row.get('outline_color', '').strip()
                    color_info['outline'] = outline if outline else '#000000'
                    
                    pattern = row.get('pattern', '').strip().lower()
                    if pattern:
                        color_info['pattern'] = pattern
                        pattern_color = row.get('pattern_color', '').strip()
                        color_info['pattern_color'] = pattern_color if pattern_color else '#000000'
                    
                    self.color_map[category_norm] = color_info
                    
                    # Also add underscore version
                    category_underscore = category_norm.replace(' ', '_')
                    self.color_map[category_underscore] = color_info
        except Exception as e:
            print(f"⚠️  Error loading legend: {e}")
    
    def _init_color_cache(self):
        """Pre-compute RGB values for all colors"""
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
        if zoom <= 10:
            return 2
        elif zoom <= 13:
            return 1
        else:
            return 1
    
    def load_geojson_files(self):
        """Load GeoJSON files from both HMDA and HUDA subdirectories"""
        print("\n" + "="*80)
        print("LOADING HYDERABAD GEOJSON DATA (HMDA + HUDA) - OPTIMIZED")
        print("="*80)
        
        all_files = []
        for subdir in ['HMDA', 'HUDA']:
            subdir_path = self.data_dir / subdir
            if subdir_path.exists():
                files = sorted(subdir_path.glob('*.geojson'))
                all_files.extend([(f, subdir) for f in files])
        
        total_files = len(all_files)
        total_features = 0
        
        print(f"Found {total_files} files\n")
        
        load_start = time.time()
        
        for idx, (geojson_file, subdir) in enumerate(all_files, 1):
            file_name = geojson_file.stem
            file_size = geojson_file.stat().st_size / 1024 / 1024
            
            print(f"[{idx:2d}/{total_files}] [{subdir:4s}] {file_name:<45} ({file_size:6.2f} MB)", end=" ", flush=True)
            
            try:
                with open(geojson_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                features = data.get('features', [])
                loaded = 0
                
                # CRS detection (first file only)
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
                    
                    if self.source_crs and self.source_crs != 'EPSG:4326' and HAS_PYPROJ:
                        try:
                            self.transformer = Transformer.from_crs(self.source_crs, 'EPSG:4326', always_xy=True)
                            self.needs_transform = True
                            print(f"✓ Coordinate transformation enabled: {self.source_crs} -> EPSG:4326")
                        except Exception as e:
                            print(f"⚠️ Could not initialize transformer: {e}")
                            self.needs_transform = False
                    else:
                        self.needs_transform = False
                
                for feature in features:
                    try:
                        geom = shape(feature['geometry'])
                        
                        # Transform if needed
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
                        
                        # Use original category if available, otherwise derive from filename
                        raw_category = (
                            props.get("ORIGINAL_CATEGORY")
                            or props.get("LANDUSE_CATEGORY")
                            or props.get("CATEGORY")
                            or props.get("Name")
                            or props.get("name")
                            or props.get("LAYER")
                            or file_name
                        )
                        category_norm = self.normalize_category(str(raw_category)) or self.normalize_category(file_name) or file_name.upper()
                        
                        feature_data = {
                            'geometry': geom,
                            'category': category_norm,
                            'filename': file_name,
                            'subdir': subdir,
                            'properties': props,
                            'area': geom.area
                        }
                        
                        bounds = geom.bounds
                        self.spatial_index.insert(self.feature_id_counter, bounds)
                        self.feature_lookup[self.feature_id_counter] = feature_data
                        self.feature_id_counter += 1
                        loaded += 1
                        
                    except Exception as e:
                        # Only log first few errors per file to avoid spam
                        if idx <= 3 and loaded == 0:
                            print(f"\n⚠️  Error loading feature from {file_name}: {e}")
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
        """Create patterns: hatch, dots, cross_hatch, dashed, dotted"""
        if base:
            draw.polygon(poly, fill=base)
        
        if len(poly) < 3:
            return
        
        xs, ys = zip(*poly)
        min_x, max_x = int(min(xs)), int(max(xs))
        min_y, max_y = int(min(ys)), int(max(ys))
        
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
    
    def get_buffer_degrees(self, zoom):
        """Get adaptive buffer size based on zoom level"""
        if zoom <= 10:
            return 0.01
        elif zoom <= 13:
            return 0.005
        elif zoom <= 16:
            return 0.001
        else:
            return 0.0003
    
    def render_tile_seamless(self, tile):
        """Render a single tile with seamless boundaries"""
        tile_bounds = mercantile.bounds(tile)
        zoom = tile.z
        buffer_degrees = self.get_buffer_degrees(zoom)
        buffered_bounds = box(
            tile_bounds.west - buffer_degrees,
            tile_bounds.south - buffer_degrees,
            tile_bounds.east + buffer_degrees,
            tile_bounds.north + buffer_degrees
        )
        
        # Thread-safe spatial index query
        try:
            candidate_ids = list(self.spatial_index.intersection(buffered_bounds.bounds))
        except Exception as e:
            # Fallback if spatial index has issues
            return None
        
        if not candidate_ids:
            return None
        
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
        
        # Fast bounds pre-filtering
        # Create a local copy of candidate features to avoid concurrent access issues
        features_to_render = []
        
        with self._geometry_lock:
            for feature_id in candidate_ids:
                try:
                    feature_data = self.feature_lookup[feature_id]
                    # Get bounds and category while holding lock
                    geom = feature_data['geometry']
                    geom_bounds = geom.bounds
                    category = feature_data['category']
                    
                    # Fast bounds check
                    if (geom_bounds[2] < buffered_bounds.bounds[0] or
                        geom_bounds[0] > buffered_bounds.bounds[2] or
                        geom_bounds[3] < buffered_bounds.bounds[1] or
                        geom_bounds[1] > buffered_bounds.bounds[3]):
                        continue
                    
                    # Store feature data for rendering (geometry access is read-only)
                    features_to_render.append({
                        'geometry': geom,
                        'category': category,
                        'bounds': geom_bounds
                    })
                except Exception as e:
                    # Skip problematic features
                    continue
        
        # Now render features (geometry operations are read-only, should be thread-safe)
        for feat_data in features_to_render:
            try:
                geom = feat_data['geometry']
                
                # Precise geometry intersection check
                if not geom.intersects(buffered_bounds):
                    continue
                
                category = feat_data['category']
                color_info = color_map.get(category, color_map.get('DEFAULT', {'fill': (204, 204, 204), 'outline': (153, 153, 153)}))
                
                fill_rgb = color_info.get('fill')
                
                if isinstance(geom, Polygon):
                    if geom.area < 1e-10:
                        continue
                    
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
                    
            except Exception as e:
                # Skip problematic geometries
                continue
        
        if rendered_count == 0:
            return None
        
        img = img_buffered.crop((buffer_pixels, buffer_pixels, 
                                buffered_size - buffer_pixels, 
                                buffered_size - buffer_pixels))
        
        img = img.resize((self.tile_size, self.tile_size), Image.LANCZOS)
        return img
    
    def generate_single_tile(self, tile, zoom_dir):
        """Generate a single tile - used for parallel processing"""
        tile_dir = zoom_dir / str(tile.x)
        tile_path = tile_dir / f"{tile.y}.png"
        
        if tile_path.exists():
            return 'exists'
        
        img = self.render_tile_seamless(tile)
        
        if img is not None:
            tile_dir.mkdir(parents=True, exist_ok=True)
            img.save(tile_path, 'PNG', optimize=False)
            return 'rendered'
        return 'empty'
    
    def generate_tiles(self, min_zoom=7, max_zoom=15):
        """Generate seamless tiles with parallel processing"""
        print(f"\n{'='*80}")
        print(f"GENERATING HYDERABAD TILES (Zoom {min_zoom}-{max_zoom}) - OPTIMIZED")
        print(f"Mode: SEAMLESS - NO TILE BOUNDARIES")
        print(f"Parallel workers: {self.max_workers}")
        print(f"{'='*80}")
        
        bounds = self.get_bounds()
        print(f"Bounds: [{bounds[1]:.4f}, {bounds[0]:.4f}] to [{bounds[3]:.4f}, {bounds[2]:.4f}]\n")
        
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
            
            print(f"Zoom {zoom:2d} | {total_for_zoom:,} tiles | Scale: {scale}x | Min: {min_size:.1f}px | Workers: {self.max_workers}", 
                  end=" ", flush=True)
            
            zoom_dir = self.output_dir / str(zoom)
            rendered = 0
            skipped_exists = 0
            skipped_empty = 0
            errors = 0
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_tile = {
                    executor.submit(self.generate_single_tile, tile, zoom_dir): tile
                    for tile in tiles
                }
                
                completed = 0
                for future in as_completed(future_to_tile):
                    completed += 1
                    try:
                        result = future.result()
                        if result == 'rendered':
                            rendered += 1
                        elif result == 'exists':
                            skipped_exists += 1
                        elif result == 'empty':
                            skipped_empty += 1
                    except Exception as e:
                        errors += 1
                        if errors <= 5 or errors % 1000 == 0:
                            print(f"\n⚠️  Error in tile generation (zoom {zoom}): {e}")
                    
                    if completed % 1000 == 0 or completed == total_for_zoom:
                        elapsed = time.time() - zoom_start
                        rate = completed / elapsed if elapsed > 0 else 0
                        print(f"\rZoom {zoom:2d} | Progress: {completed:,}/{total_for_zoom:,} | "
                              f"Rendered: {rendered:,} | Exists: {skipped_exists:,} | Empty: {skipped_empty:,} | "
                              f"Errors: {errors:,} | Rate: {rate:.1f} t/s", end="", flush=True)
            
            zoom_elapsed = time.time() - zoom_start
            speed = rendered / zoom_elapsed if zoom_elapsed > 0 else 0
            print(f"\rZoom {zoom:2d} | {total_for_zoom:,} tiles | Scale: {scale}x | "
                  f"✓ {rendered:,} rendered, {skipped_exists:,} existed, {skipped_empty:,} empty, "
                  f"{errors:,} errors in {zoom_elapsed:.1f}s ({speed:.1f} t/s)")
            
            total_tiles += rendered
        
        overall_elapsed = time.time() - overall_start
        print(f"\n{'='*80}")
        print(f"✓ COMPLETE: {total_tiles:,} tiles in {overall_elapsed:.1f}s "
              f"({overall_elapsed/60:.1f} min)")
        print(f"{'='*80}\n")
    
    def generate_html_viewer(self):
        """Generate HTML viewer"""
        bounds = self.get_bounds()
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Hyderabad Master Plan - Seamless Tiles (Optimized)</title>
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
      attribution: 'Hyderabad Master Plan (HMDA + HUDA) - Optimized'
    }}).addTo(map);
    
    const info = L.control({{position: 'topright'}});
    info.onAdd = function() {{
      this._div = L.DomUtil.create('div', 'info');
      this._div.innerHTML = '<b>Hyderabad Master Plan</b><br/>HMDA + HUDA (Optimized)<br/>Zoom: ' + map.getZoom();
      return this._div;
    }};
    info.addTo(map);
    
    map.on('zoomend', function() {{
      info._div.innerHTML = '<b>Hyderabad Master Plan</b><br/>HMDA + HUDA (Optimized)<br/>Zoom: ' + map.getZoom();
    }});
  </script>
</body>
</html>"""
        
        (self.output_dir / 'index.html').write_text(html)
        print(f"✓ Viewer saved: {self.output_dir}/index.html")


def main():
    # Use pre-split data directory
    data_dir = Path('data/Telangana/Hyderabad/master_plan_split')
    output_dir = Path('./hyderabad_tiles_seamless_optimized')
    
    if not data_dir.exists():
        print(f"✗ Preprocessed data directory not found: {data_dir}")
        print(f"\n💡 Please run preprocessing first:")
        print(f"   python3 scripts/tiles_generation/telangana/preprocess_hyderabad_features.py")
        sys.exit(1)
    
    print("="*80)
    print("HYDERABAD MASTER PLAN - OPTIMIZED TILE GENERATOR")
    print("✅ Uses pre-split features for faster spatial indexing")
    print("✅ Handles polygon holes/interior rings")
    print("✅ Supports hatch and dotted patterns")
    print("✅ Processes both HMDA and HUDA data")
    print("="*80)
    print(f"Input:  {data_dir}")
    print(f"Output: {output_dir}")
    
    generator = HyderabadMasterPlanTilesOptimized(data_dir, output_dir)
    generator.load_geojson_files()
    
    if generator.feature_id_counter == 0:
        print("✗ No features loaded!")
        sys.exit(1)
    
    generator.generate_tiles(min_zoom=7, max_zoom=18)
    generator.generate_html_viewer()
    
    print(f"\n💡 To view: cd {output_dir} && python3 -m http.server 8011")
    print(f"   Then open: http://localhost:8011/\n")


if __name__ == '__main__':
    main()
