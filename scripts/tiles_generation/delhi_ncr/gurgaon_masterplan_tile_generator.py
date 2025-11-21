#!/usr/bin/env python3
"""
Gurgaon Master Plan - SEAMLESS COMPLETE TILES
Every feature visible at every zoom level - Transparent background
"""

import json
import os
import time
from pathlib import Path
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import shape, box, Point, Polygon, LineString
from rtree import index

class GurgaonSeamlessTiles:
    def __init__(self, data_dir, output_dir):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.spatial_index = index.Index()
        self.feature_id_counter = 0
        self.feature_lookup = {}
        
    def normalize_category(self, value):
        """Normalize category name"""
        if not value:
            return None
        value = " ".join(str(value).replace("_", " ").split())
        return value.upper()
    
    def get_color_map(self):
        """Gurgaon color mapping - matches geotif_gurgaon.py"""
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        return {
            "100 RESIDENTIAL (GROUP HOUSING/PLOTTED)": {'fill': '#FFFF73', 'outline': '#CCCC5C'},
            "1000 NATURAL CONSERVATION ZONE HUBS)": {'fill': '#38A800', 'outline': '#2D8600'},
            "200 COMMERCIAL": {'fill': '#BED2FF', 'outline': '#98A8CC'},
            "300 INDUSTRIAL": {'fill': '#A80084', 'outline': '#86006A'},
            "400 TRANSPORT AND COMMUNICATION": {'fill': '#828282', 'outline': '#686868'},
            "500 PUBLIC UTILITIES": {'fill': '#A83800', 'outline': '#862D00'},
            "600 PUBLIC AND SEMI PUBLIC USE": {'fill': '#E60000', 'outline': '#B80000'},
            "700 OPEN SPACES": {'fill': '#F57A7A', 'outline': '#C46262', 'pattern': 'hatch', 'pattern_color': '#FFFFFF'},
            "800 AGRICULTURE ZONE": {'fill': '#FFFFFF', 'outline': '#CCCCCC', 'pattern': 'dots', 'pattern_color': '#4CE600'},
            "800 AGGRICULTURE ZONE": {'fill': '#FFFFFF', 'outline': '#CCCCCC', 'pattern': 'dots', 'pattern_color': '#4CE600'},
            "900 SPECIAL ZONE": {'fill': '#DF73FF', 'outline': '#B25CCC'},
            "H6 WORLD TRADE HUB": {'fill': '#FFFF00', 'outline': '#CCCC00'},
            "HUBS": {'fill': '#FFAA00', 'outline': '#CC8800'},
        }
    
    def hex_to_rgb(self, hex_color):
        """Convert hex to RGB"""
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
        """Load all Gurgaon GeoJSON files"""
        print("\n" + "="*80)
        print("LOADING GURGAON GEOJSON DATA")
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
                        if not geom.is_valid:
                            geom = geom.buffer(0)
                        
                        if geom.is_empty:
                            continue
                        
                        props = feature.get('properties', {})
                        raw_category = (
                            props.get("ppt_full")
                            or props.get("classtext")
                            or props.get("class")
                            or props.get("NAME")
                            or props.get("name")
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
        """Create patterns: hatch, dots, or airplane - clipped to polygon boundary"""
        if len(poly) < 3:
            return
        
        # Draw base fill first
        if base:
            draw.polygon(poly, fill=base)
        
        xs, ys = zip(*poly)
        min_x, max_x = int(min(xs)), int(max(xs))
        min_y, max_y = int(min(ys)), int(max(ys))
        
        # Create polygon shape for clipping - ensure it's valid
        try:
            poly_shape = Polygon(poly)
            if not poly_shape.is_valid:
                poly_shape = poly_shape.buffer(0)
        except:
            # If polygon creation fails, use bounding box for dots
            poly_shape = None
        
        if ptype == "hatch":
            spacing = max(3, (max_x - min_x) // 15)
            for i in range(min_x - max_y, max_x + max_y, spacing):
                # Create full hatch line
                line_pts = [(x, x - i) for x in range(min_x - 10, max_x + 10) if min_y - 10 <= x - i <= max_y + 10]
                if len(line_pts) < 2:
                    continue
                # Create LineString and clip to polygon
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
        elif ptype == "dots":
            spacing = 24
            dot_radius = 3
            
            # Draw dots across the polygon area
            for y in range(min_y, max_y + 1, spacing):
                for x in range(min_x, max_x + 1, spacing):
                    # Check if point is inside polygon
                    if poly_shape is not None:
                        try:
                            point = Point(x, y)
                            if poly_shape.contains(point):
                                draw.ellipse([x-dot_radius, y-dot_radius, x+dot_radius, y+dot_radius], fill=pcolor)
                        except:
                            # Fallback: draw dot if within bounding box
                            draw.ellipse([x-dot_radius, y-dot_radius, x+dot_radius, y+dot_radius], fill=pcolor)
                    else:
                        # If polygon shape is None, draw dots in bounding box
                        draw.ellipse([x-dot_radius, y-dot_radius, x+dot_radius, y+dot_radius], fill=pcolor)
        elif ptype == "airplane":
            spacing = 18
            for y in range(min_y, max_y + 1, spacing):
                for x in range(min_x, max_x + 1, spacing):
                    if poly_shape.contains(Point(x, y)):
                        # Draw cross pattern (airplane marker)
                        draw.line([(x-3, y), (x+3, y)], fill=pcolor, width=1)
                        draw.line([(x, y-3), (x, y+3)], fill=pcolor, width=1)
                        draw.line([(x-2, y-2), (x+2, y+2)], fill=pcolor, width=1)
                        draw.line([(x-2, y+2), (x+2, y-2)], fill=pcolor, width=1)
    
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
            # Draw fill first (if exists), then outline on top for precise boundaries
            if fill_rgb:
                fill_rgba = fill_rgb + (255,)  # Add alpha channel
                poly_draw.polygon(exterior_pixels, fill=fill_rgba)
        
        # Draw black outline
        if len(exterior_pixels) > 1:
            closed_pixels = exterior_pixels + [exterior_pixels[0]]
            poly_draw.line(closed_pixels, fill=black_outline, width=outline_width)
        
        # Draw interior rings (holes) as transparent
        for interior in polygon.interiors:
            interior_pixels = []
            for coord in interior.coords:
                lon, lat = coord[0], coord[1]
                # Convert to pixel coordinates using actual tile bounds
                px = ((lon - tile_bounds.west) / lon_range * img_size) + buffer_pixels
                py = ((tile_bounds.north - lat) / lat_range * img_size) + buffer_pixels
                interior_pixels.append((int(px), int(py)))
            
            if len(interior_pixels) >= 3:
                poly_draw.polygon(interior_pixels, fill=(0, 0, 0, 0), outline=(0, 0, 0, 0))
        
        # Composite the polygon with holes onto the main image
        draw._image.paste(poly_img, (0, 0), poly_img)
    
    def render_tile_seamless(self, tile):
        """
        SEAMLESS RENDERING for Gurgaon:
        - Buffer zone to prevent seams
        - All features visible
        - No clipping artifacts
        """
        z, x, y = tile.z, tile.x, tile.y
        
        scale = self.get_zoom_scale(z)
        min_size = self.get_min_feature_size(z, scale)
        outline_width = self.get_outline_width(z)
        img_size = self.tile_size * scale
        
        # Buffer zone
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
        rendered_count = 0
        
        # Sort by area
        features_to_render = []
        for feature_id in intersecting_ids:
            feature_data = self.feature_lookup[feature_id]
            if feature_data['geometry'].intersects(tile_bbox_buffered):
                features_to_render.append((feature_data['area'], feature_id, feature_data))
        
        features_to_render.sort(key=lambda x: x[0], reverse=True)
        
        # Render all features
        for area, feature_id, feature_data in features_to_render:
            geom = feature_data['geometry']
            category = feature_data['category']
            filename = feature_data['filename']
            
            # Try category first, then filename
            color_info = color_map.get(category, color_map.get(self.normalize_category(filename), {'fill': '#CCCCCC', 'outline': '#999999'}))
            
            fill_color = color_info.get('fill')
            fill_rgb = self.hex_to_rgb(fill_color) if fill_color else None
            outline_color = color_info.get('outline', fill_color or '#000000')
            outline_rgb = self.hex_to_rgb(outline_color)
            
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
                    # Use actual tile bounds for consistent alignment across tiles
                    pixel_coords = []
                    lon_range = tile_bounds.east - tile_bounds.west
                    lat_range = tile_bounds.north - tile_bounds.south
                    for coord in polygon.exterior.coords:
                        lon, lat = coord[0], coord[1]
                        # Convert to pixel coordinates using actual tile bounds
                        px = ((lon - tile_bounds.west) / lon_range * img_size) + buffer_pixels
                        py = ((tile_bounds.north - lat) / lat_range * img_size) + buffer_pixels
                        pixel_coords.append((px, py))
                    
                    if len(pixel_coords) < 3:
                        continue
                    
                    xs = [p[0] for p in pixel_coords]
                    ys = [p[1] for p in pixel_coords]
                    width = max(xs) - min(xs)
                    height = max(ys) - min(ys)
                    feature_size = max(width, height)
                    
                    # Check if polygon has interior rings (holes)
                    has_holes = len(polygon.interiors) > 0
                    
                    if feature_size >= min_size:
                        # Normal rendering
                        int_pixels = [(int(x), int(y)) for x, y in pixel_coords]
                        
                        if has_holes:
                            # Render polygon with holes using mask
                            self.render_polygon_with_holes(draw, polygon, tile_bounds, img_size, buffer_pixels,
                                                          buffered_size, fill_rgb, color_info, outline_width)
                        else:
                            # Simple polygon without holes - draw with black outline
                            black_outline = (0, 0, 0)  # Black outline
                            if 'pattern' in color_info:
                                self.create_pattern(draw, int_pixels, fill_rgb, 
                                                 color_info['pattern'], 
                                                 self.hex_to_rgb(color_info['pattern_color']),
                                                 buffered_size)
                                # Draw black outline after pattern - use line for precise boundaries
                                if len(int_pixels) > 1:
                                    # Close the polygon by adding first point at end
                                    closed_pixels = int_pixels + [int_pixels[0]]
                                    draw.line(closed_pixels, fill=black_outline, width=outline_width)
                            elif fill_rgb:
                                # Draw fill first, then outline on top for precise boundaries
                                draw.polygon(int_pixels, fill=fill_rgb)
                                if len(int_pixels) > 1:
                                    closed_pixels = int_pixels + [int_pixels[0]]
                                    draw.line(closed_pixels, fill=black_outline, width=outline_width)
                            else:
                                # Outline only - draw black outline
                                if len(int_pixels) > 1:
                                    closed_pixels = int_pixels + [int_pixels[0]]
                                    draw.line(closed_pixels, fill=black_outline, width=outline_width)
                    else:
                        # Enlarge small features (skip if has holes - too complex)
                        if not has_holes:
                            center_x = sum(xs) / len(xs)
                            center_y = sum(ys) / len(ys)
                            
                            scale_factor = min_size / max(feature_size, 0.1)
                            enlarged_coords = []
                            for px, py in pixel_coords:
                                new_x = center_x + (px - center_x) * scale_factor
                                new_y = center_y + (py - center_y) * scale_factor
                                enlarged_coords.append((int(new_x), int(new_y)))
                            
                            # Draw with black outline
                            black_outline = (0, 0, 0)  # Black outline
                            if 'pattern' in color_info:
                                self.create_pattern(draw, enlarged_coords, fill_rgb,
                                                 color_info['pattern'],
                                                 self.hex_to_rgb(color_info['pattern_color']),
                                                 buffered_size)
                                # Draw black outline after pattern - use line for precise boundaries
                                if len(enlarged_coords) > 1:
                                    closed_coords = enlarged_coords + [enlarged_coords[0]]
                                    draw.line(closed_coords, fill=black_outline, width=outline_width)
                            elif fill_rgb:
                                # Draw fill first, then outline on top
                                draw.polygon(enlarged_coords, fill=fill_rgb)
                                if len(enlarged_coords) > 1:
                                    closed_coords = enlarged_coords + [enlarged_coords[0]]
                                    draw.line(closed_coords, fill=black_outline, width=outline_width)
                            else:
                                # Outline only - draw black outline
                                if len(enlarged_coords) > 1:
                                    closed_coords = enlarged_coords + [enlarged_coords[0]]
                                    draw.line(closed_coords, fill=black_outline, width=outline_width)
                            
                            # Center dot with black outline (only if fill exists)
                            if fill_rgb:
                                dot_size = min_size // 2
                                draw.ellipse([center_x - dot_size, center_y - dot_size,
                                            center_x + dot_size, center_y + dot_size],
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
        """Generate seamless tiles for Gurgaon"""
        print(f"\n{'='*80}")
        print(f"GENERATING GURGAON TILES (Zoom {min_zoom}-{max_zoom})")
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
        """Generate viewer for Gurgaon"""
        bounds = self.get_bounds()
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Gurgaon Master Plan - Seamless Tiles</title>
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
      attribution: 'Gurgaon Master Plan'
    }}).addTo(map);
    
    const info = L.control({{position: 'topright'}});
    info.onAdd = function() {{
      this._div = L.DomUtil.create('div', 'info');
      this._div.innerHTML = '<b>Gurgaon Master Plan</b><br/>Seamless tiles - no boundaries<br/>Zoom: ' + map.getZoom();
      return this._div;
    }};
    info.addTo(map);
    
    map.on('zoomend', function() {{
      info._div.innerHTML = '<b>Gurgaon Master Plan</b><br/>Seamless tiles - no boundaries<br/>Zoom: ' + map.getZoom();
    }});
  </script>
</body>
</html>"""
        
        (self.output_dir / 'index.html').write_text(html)
        print(f"✓ Viewer saved: {self.output_dir}/index.html")


def main():
    import sys
    
    possible_paths = [
        Path('data/delhi_ncr/gurgaon/master_plan'),
        Path('/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping/data/delhi_ncr/gurgaon/master_plan'),
    ]
    
    data_dir = None
    for path in possible_paths:
        if path.exists():
            data_dir = path
            break
    
    if data_dir is None:
        print("Enter path to Gurgaon master_plan directory:")
        user_path = input("> ").strip()
        data_dir = Path(user_path)
        if not data_dir.exists():
            print(f"✗ Path not found: {data_dir}")
            sys.exit(1)
    
    output_dir = Path('./gurgaon_tiles_seamless')
    
    print("="*80)
    print("GURGAON MASTER PLAN - SEAMLESS TILE GENERATOR")
    print("✅ Properly handles polygon holes/interior rings")
    print("="*80)
    print(f"Input:  {data_dir}")
    print(f"Output: {output_dir}")
    
    generator = GurgaonSeamlessTiles(data_dir, output_dir)
    generator.load_geojson_files()
    
    if generator.feature_id_counter == 0:
        print("✗ No features loaded!")
        sys.exit(1)
    
    generator.generate_tiles(min_zoom=7, max_zoom=18)
    generator.generate_html_viewer()
    
    print(f"\n💡 To view: cd {output_dir} && python3 -m http.server 8005")
    print(f"   Then open: http://localhost:8005/\n")


if __name__ == '__main__':
    main()

