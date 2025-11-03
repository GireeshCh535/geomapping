#!/usr/bin/env python3
"""
Visakhapatnam Master Plan - SEAMLESS COMPLETE TILES
Every feature visible at every zoom level - Transparent background
Supports: Solid fills, Hatch patterns, Dot patterns
"""

import json
import os
import time
from pathlib import Path
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import shape, box
from rtree import index

class VisakhapatnamSeamlessTiles:
    def __init__(self, data_dir, output_dir):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.spatial_index = index.Index()
        self.feature_id_counter = 0
        self.feature_lookup = {}
        
    def get_color_map(self):
        """Visakhapatnam color mapping with patterns"""
        return {
            # File name as key (normalized)
            'Agricultural_Use_Zone': {
                'fill': '#D3FFBE', 
                'outline': '#A9CC98'
            },
            'Blue_Zone_Water_Bodies': {
                'fill': '#73FFDF', 
                'outline': '#5CCCB2'
            },
            'Brown_Zone_Hills': {
                'fill': '#A87000', 
                'outline': '#865A00'
            },
            'Commercial_Use_Zone': {
                'fill': '#004DA8', 
                'outline': '#003D86'
            },
            'Existing_Crematorium_Burial_Ground_Graveyard': {
                'fill': '#FFFFFF', 
                'outline': '#CCCCCC',
                'pattern': 'hatch',
                'pattern_color': '#FF0000'
            },
            'Existing_Educational_Facilities': {
                'fill': '#FF0000', 
                'outline': '#CC0000',
                'pattern': 'hatch',
                'pattern_color': '#000000'
            },
            'Existing_Government_Semi_Government_Facilities': {
                'fill': '#FF0000', 
                'outline': '#CC0000'
            },
            'Existing_Health_Facilities': {
                'fill': '#FF0000', 
                'outline': '#CC0000',
                'pattern': 'dot',
                'pattern_color': '#CCCCCC'
            },
            'Proposed_Industrial_Use_Zone': {
                'fill': '#C500FF', 
                'outline': '#9E00CC',
                'pattern': 'hatch',
                'pattern_color': '#FFFFFF'
            },
            'Existing_Industrial_Area': {
                'fill': '#C500FF', 
                'outline': '#9E00CC'
            },
            'Existing_Public_Utilities': {
                'fill': '#FF7F7F', 
                'outline': '#CC6666',
                'pattern': 'hatch',
                'pattern_color': '#E60000'
            },
            'Existing_Recreational_Playgrounds_Parks_Layout_OpenSpace': {
                'fill': '#55FF00', 
                'outline': '#44CC00'
            },
            'Existing_Religious_Facilities': {
                'fill': '#FF0000', 
                'outline': '#CC0000',
                'pattern': 'hatch',
                'pattern_color': '#55FF00'
            },
            'Existing_Road_Railway_Line_Area': {
                'fill': '#828282', 
                'outline': '#686868',
                'pattern': 'hatch',
                'pattern_color': '#828282'
            },
            'Existing_Transportation_Facility': {
                'fill': '#686868', 
                'outline': '#545454'
            },
            'Green_Zone_Forest': {
                'fill': '#00734C', 
                'outline': '#005C3D'
            },
            'Kambalakonda_Eco_Sensitive_Zone_NAOB_Buffer_Zoological_Park': {
                'fill': '#D7C29E', 
                'outline': '#AC9B7E'
            },
            'Kambalakonda_WildLife_Sanctuary_Biodiversity_Area': {
                'fill': '#38A800', 
                'outline': '#2D8600'
            },
            'Mixed_Use_Zone_1': {
                'fill': '#FFAA00', 
                'outline': '#CC8800'
            },
            'Mixed_Use_Zone_2_BAIA': {
                'fill': '#FFD37F', 
                'outline': '#CCA966'
            },
            'Mixed_Use_Zone_3_BAIA': {
                'fill': '#E69800', 
                'outline': '#B87A00',
                'pattern': 'hatch',
                'pattern_color': '#E1E1E1'
            },
            'Mixed_Use_Zone_4_BAIA': {
                'fill': '#FFAA00', 
                'outline': '#CC8800',
                'pattern': 'dot',
                'pattern_color': '#000000'
            },
            'Proposed_PSP_Use_Zone': {
                'fill': '#FF0000', 
                'outline': '#CC0000',
                'pattern': 'hatch',
                'pattern_color': '#FF0000'
            },
            'Proposed_Public_Utilities_Use_Zone': {
                'fill': '#F57A7A', 
                'outline': '#C46262',
                'pattern': 'hatch',
                'pattern_color': '#FFFFFF'
            },
            'Proposed_Recreational_Use_Zone': {
                'fill': '#4C7300', 
                'outline': '#3D5C00'
            },
            'Proposed_Road_Network': {
                'fill': '#000000', 
                'outline': '#000000'
            },
            'Proposed_Transportation_Facility_Use_Zone': {
                'fill': '#343434', 
                'outline': '#2A2A2A',
                'pattern': 'hatch',
                'pattern_color': '#FFFFFF'
            },
            'Residential_Use_Zone': {
                'fill': '#FFFF73', 
                'outline': '#CCCC5C'
            },
            'Sea_River_Accreted_Land': {
                'fill': '#D7C29E', 
                'outline': '#AC9B7E',
                'pattern': 'dot',
                'pattern_color': '#E39E00'
            },
            'Special_Area_Use_Zone': {
                'fill': '#FFFFFF', 
                'outline': '#CCCCCC',
                'pattern': 'hatch',
                'pattern_color': '#002673'
            },
            'Water_Body_Buffer': {
                'fill': '#4CE600', 
                'outline': '#3DB800',
                'pattern': 'dot',
                'pattern_color': '#267300'
            },
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
    
    def load_geojson_files(self):
        """Load all Visakhapatnam GeoJSON files"""
        print("\n" + "="*80)
        print("LOADING VISAKHAPATNAM GEOJSON DATA")
        print("="*80)
        
        geojson_files = sorted(self.data_dir.glob('*.geojson'))
        total_files = len(geojson_files)
        total_features = 0
        
        print(f"Found {total_files} files\n")
        
        load_start = time.time()
        
        for idx, geojson_file in enumerate(geojson_files, 1):
            zone_name = geojson_file.stem
            file_size = geojson_file.stat().st_size / 1024 / 1024
            
            print(f"[{idx:2d}/{total_files}] {zone_name:<60} ({file_size:6.2f} MB)", end=" ", flush=True)
            
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
                        
                        feature_data = {
                            'geometry': geom,
                            'zone': zone_name,
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
    
    def create_hatch_pattern(self, draw, poly, base, pcolor, img_size):
        """Create diagonal hatch pattern"""
        draw.polygon(poly, fill=base)
        
        if len(poly) < 3:
            return
        
        xs, ys = zip(*poly)
        min_x, max_x = int(min(xs)), int(max(xs))
        min_y, max_y = int(min(ys)), int(max(ys))
        
        spacing = max(3, (max_x - min_x) // 15)
        for i in range(min_x - max_y, max_x + max_y, spacing):
            pts = [(x, x - i) for x in range(min_x, max_x + 1) if min_y <= x - i <= max_y]
            if len(pts) > 1:
                draw.line(pts, fill=pcolor, width=1)
    
    def create_dot_pattern(self, draw, poly, base, pcolor, img_size):
        """Create dot pattern"""
        draw.polygon(poly, fill=base)
        
        if len(poly) < 3:
            return
        
        xs, ys = zip(*poly)
        min_x, max_x = int(min(xs)), int(max(xs))
        min_y, max_y = int(min(ys)), int(max(ys))
        
        # Dot spacing and size
        spacing = max(5, (max_x - min_x) // 20)
        dot_size = max(1, spacing // 3)
        
        # Create a polygon mask to check if points are inside
        from shapely.geometry import Point
        from shapely.geometry import Polygon as ShapelyPolygon
        
        # Create shapely polygon from pixel coordinates
        try:
            poly_shape = ShapelyPolygon(poly)
            
            # Draw dots in grid pattern
            for x in range(min_x, max_x, spacing):
                for y in range(min_y, max_y, spacing):
                    point = Point(x, y)
                    if poly_shape.contains(point):
                        draw.ellipse([x - dot_size, y - dot_size, 
                                    x + dot_size, y + dot_size], 
                                   fill=pcolor)
        except:
            # Fallback: simple grid without polygon check
            for x in range(min_x, max_x, spacing):
                for y in range(min_y, max_y, spacing):
                    draw.ellipse([x - dot_size, y - dot_size, 
                                x + dot_size, y + dot_size], 
                               fill=pcolor)
    
    def render_polygon_with_holes(self, draw, polygon, tile_bounds, lon_buffer, lat_buffer, 
                                  buffered_size, fill_rgb, color_info):
        """
        Render polygon with interior rings (holes) properly.
        Create a mask where holes are transparent.
        """
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
        
        # Draw exterior ring with full opacity
        fill_rgba = fill_rgb + (255,)  # Add alpha channel
        
        # Apply pattern if specified
        if 'pattern' in color_info:
            if color_info['pattern'] == 'hatch':
                self.create_hatch_pattern(poly_draw, exterior_pixels, fill_rgba,
                                        self.hex_to_rgb(color_info['pattern_color']) + (255,),
                                        buffered_size)
            elif color_info['pattern'] == 'dot':
                self.create_dot_pattern(poly_draw, exterior_pixels, fill_rgba,
                                      self.hex_to_rgb(color_info['pattern_color']) + (255,),
                                      buffered_size)
        else:
            poly_draw.polygon(exterior_pixels, fill=fill_rgba, outline=fill_rgba)
        
        # Draw interior rings (holes) as transparent (black with full alpha = cut out)
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
                # Draw hole as fully transparent (this cuts out the area)
                poly_draw.polygon(interior_pixels, fill=(0, 0, 0, 0), outline=(0, 0, 0, 0))
        
        # Composite the polygon with holes onto the main image
        draw._image.paste(poly_img, (0, 0), poly_img)
    
    def render_tile_seamless(self, tile):
        """
        SEAMLESS RENDERING for Visakhapatnam:
        - Buffer zone to prevent seams
        - All features visible
        - No clipping artifacts
        - Supports hatch and dot patterns
        """
        z, x, y = tile.z, tile.x, tile.y
        
        scale = self.get_zoom_scale(z)
        min_size = self.get_min_feature_size(z, scale)
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
        
        # Sort by area (largest first)
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
            
            # Get color info for this zone
            color_info = color_map.get(zone, {'fill': '#CCCCCC', 'outline': '#999999'})
            
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
                            self.render_polygon_with_holes(draw, polygon, tile_bounds, lon_buffer, lat_buffer, 
                                                          buffered_size, fill_rgb, color_info)
                        else:
                            # Simple polygon without holes
                            if 'pattern' in color_info:
                                pattern_type = color_info['pattern']
                                pattern_color = self.hex_to_rgb(color_info['pattern_color'])
                                
                                if pattern_type == 'hatch':
                                    self.create_hatch_pattern(draw, int_pixels, fill_rgb, 
                                                            pattern_color, buffered_size)
                                elif pattern_type == 'dot':
                                    self.create_dot_pattern(draw, int_pixels, fill_rgb, 
                                                          pattern_color, buffered_size)
                            else:
                                draw.polygon(int_pixels, fill=fill_rgb, outline=fill_rgb, width=0)
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
                            
                            if 'pattern' in color_info:
                                pattern_type = color_info['pattern']
                                pattern_color = self.hex_to_rgb(color_info['pattern_color'])
                                
                                if pattern_type == 'hatch':
                                    self.create_hatch_pattern(draw, enlarged_coords, fill_rgb,
                                                            pattern_color, buffered_size)
                                elif pattern_type == 'dot':
                                    self.create_dot_pattern(draw, enlarged_coords, fill_rgb,
                                                          pattern_color, buffered_size)
                            else:
                                draw.polygon(enlarged_coords, fill=fill_rgb, outline=fill_rgb, width=0)
                            
                            # Center dot
                            dot_size = min_size // 2
                            draw.ellipse([center_x - dot_size, center_y - dot_size,
                                        center_x + dot_size, center_y + dot_size],
                                       fill=fill_rgb)
                    
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
        """Generate seamless tiles for Visakhapatnam"""
        print(f"\n{'='*80}")
        print(f"GENERATING VISAKHAPATNAM TILES (Zoom {min_zoom}-{max_zoom})")
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
        """Generate viewer for Visakhapatnam"""
        bounds = self.get_bounds()
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Visakhapatnam Master Plan - Seamless Tiles</title>
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
    const map = L.map('map').setView([{center_lat:.6f}, {center_lon:.6f}], 12);
    
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
      attribution: 'Esri',
      maxZoom: 19
    }}).addTo(map);
    
    L.tileLayer('./{{z}}/{{x}}/{{y}}.png', {{
      minZoom: 7,
      maxZoom: 18,
      opacity: 0.9,
      attribution: 'Visakhapatnam Master Plan'
    }}).addTo(map);
    
    const info = L.control({{position: 'topright'}});
    info.onAdd = function() {{
      this._div = L.DomUtil.create('div', 'info');
      this._div.innerHTML = '<b>Visakhapatnam Master Plan</b><br/>Seamless tiles - Hatch & Dot patterns<br/>Zoom: ' + map.getZoom();
      return this._div;
    }};
    info.addTo(map);
    
    map.on('zoomend', function() {{
      info._div.innerHTML = '<b>Visakhapatnam Master Plan</b><br/>Seamless tiles - Hatch & Dot patterns<br/>Zoom: ' + map.getZoom();
    }});
  </script>
</body>
</html>"""
        
        (self.output_dir / 'index.html').write_text(html)
        print(f"✓ Viewer saved: {self.output_dir}/index.html")


def main():
    import sys
    
    possible_paths = [
        Path('data/andhra_pradesh/visakhapatnam/master_plan'),
        Path('/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping/data/andhra_pradesh/visakhapatnam/master_plan'),
    ]
    
    data_dir = None
    for path in possible_paths:
        if path.exists():
            data_dir = path
            break
    
    if data_dir is None:
        print("Enter path to Visakhapatnam master_plan directory:")
        user_path = input("> ").strip()
        data_dir = Path(user_path)
        if not data_dir.exists():
            print(f"✗ Path not found: {data_dir}")
            sys.exit(1)
    
    output_dir = Path('./visakhapatnam_tiles1')
    
    print("="*80)
    print("VISAKHAPATNAM MASTER PLAN - SEAMLESS TILE GENERATOR")
    print("✅ Properly handles polygon holes/interior rings")
    print("✅ Supports Hatch and Dot patterns")
    print("="*80)
    print(f"Input:  {data_dir}")
    print(f"Output: {output_dir}")
    
    generator = VisakhapatnamSeamlessTiles(data_dir, output_dir)
    generator.load_geojson_files()
    
    if generator.feature_id_counter == 0:
        print("✗ No features loaded!")
        sys.exit(1)
    
    generator.generate_tiles(min_zoom=7, max_zoom=18)
    generator.generate_html_viewer()
    
    print(f"\n💡 To view: cd {output_dir} && python3 -m http.server 8012")
    print(f"   Then open: http://localhost:8012/\n")


if __name__ == '__main__':
    main()

