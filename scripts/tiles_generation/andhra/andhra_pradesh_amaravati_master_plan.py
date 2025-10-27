#!/usr/bin/env python3
"""
Amaravati Master Plan - FIXED Tile Generator
Solves: 1) Features disappearing at zoom 8-14
        2) Overlapping features
        3) Missing features
"""

import json
import os
import time
from pathlib import Path
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import shape, box
from rtree import index

class AmaravatiFixedTileGenerator:
    def __init__(self, data_dir, output_dir):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.spatial_index = index.Index()
        self.feature_id_counter = 0
        self.feature_lookup = {}
        
    def get_color_map(self):
        """Exact color mapping for all Amaravati zones"""
        return {
            'Burial Ground': {
                'type': 'dotted',
                'base': '#FFFFFF',
                'dot': '#E39E00',
                'solid_lowzoom': '#E39E00'
            },
            'C1 -Mixed use zone': {'fill': '#73B2FF'},
            'C2- General commercial zone': {'fill': '#00C5FF', 'outline': '#000000'},
            'C3-Neighbourhood centre zone': {'fill': '#00C5FF'},
            'C4-Town centre zone': {'fill': '#00A9E6'},
            'C5-Regional centre zone': {'fill': '#0070FF'},
            'C6-Central business district zone': {'fill': '#005CE6'},
            'Commercial Vacant': {'fill': '#C5E2FF'},
            'I1-Business park zone': {'fill': '#FFBEE8'},
            'I2-Logistics zone': {'fill': '#FF73DF'},
            'I3-Non polluting industry zone': {'fill': '#B6B6B6', 'outline': '#000000'},
            'Not Available': {'fill': '#CCCCCC'},
            'P1-Passive zone': {'fill': '#267300'},
            'P2-Active zone': {'fill': '#38A800'},
            'P3-Protected zone': {'fill': '#BEE8FF'},
            'P3-Protected zone Hills': {'fill': '#4C7300'},
            'PGN-G': {'fill': '#4C7300'},
            'PGN-V': {'fill': '#897044'},
            'R1-Village planning zone': {
                'type': 'hatched',
                'base': '#FFFFFF',
                'hatch': '#000000',
                'solid_lowzoom': '#EEEEEE'
            },
            'R3-Medium to high density zone': {'fill': '#F5CA7A'},
            'R4-High density zone': {'fill': '#E69800'},
            'RAA': {'fill': '#FFAA00'},
            'Residential Vacant': {'fill': '#FFD37F'},
            'S2-Education zone': {'fill': '#FF7F7F'},
            'S3-Special zone': {'fill': '#D7B09E'},
            'SC1a-Mixed Use': {'fill': '#0070FF'},
            'SC1b - Mixed Use': {'fill': '#73B2FF'},
            'SP1- Passive Zone': {'fill': '#267300'},
            'SP2- Active Zone': {'fill': '#38A800'},
            'SP3-Protected Zone': {'fill': '#00C5FF'},
            'SR2 Low Density Housing': {'fill': '#FFFFBE'},
            'SR4 - High Density Private': {'fill': '#FFAA00'},
            'SS1 - Government Zone': {'fill': '#E60000'},
            'SS2a- Education Zone': {'fill': '#FF7F7F'},
            'SS2b Cultural Zone': {'fill': '#C500FF'},
            'SS2c Health Zone': {'fill': '#D3FFBE'},
            'SS3 - Special Zone': {'fill': '#A83800'},
            'SU1-Reserve Zone': {'fill': '#E1E1E1'},
            'SU2 - Road Network': {'fill': '#82817D'},
            'U1-Reserve zone': {'fill': '#CCCCCC'},
            'U2- Road Reserve Zone': {'fill': '#82817D'}
        }
    
    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def load_geojson_files(self):
        """Load all GeoJSON files and build spatial index"""
        print("\n" + "="*80)
        print("LOADING GEOJSON DATA")
        print("="*80)
        
        geojson_files = sorted(self.data_dir.glob('*.geojson'))
        total_files = len(geojson_files)
        total_features = 0
        
        print(f"Found {total_files} GeoJSON files\n")
        
        load_start = time.time()
        
        for idx, geojson_file in enumerate(geojson_files, 1):
            zone_name = geojson_file.stem
            file_size = geojson_file.stat().st_size / 1024 / 1024
            
            print(f"[{idx:2d}/{total_files}] {zone_name:<45} ({file_size:6.2f} MB)", end=" ", flush=True)
            
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
                        
                        feature_data = {
                            'geometry': geom,
                            'zone': zone_name,
                            'properties': feature.get('properties', {})
                        }
                        
                        bounds = geom.bounds
                        self.spatial_index.insert(self.feature_id_counter, bounds)
                        self.feature_lookup[self.feature_id_counter] = feature_data
                        self.feature_id_counter += 1
                        loaded += 1
                        
                    except:
                        continue
                
                total_features += loaded
                print(f"✓ {loaded:>6,} features")
                
            except Exception as e:
                print(f"✗ Error: {e}")
                continue
        
        load_elapsed = time.time() - load_start
        
        print(f"\n{'='*80}")
        print(f"LOADED: {total_features:,} features in {load_elapsed:.1f}s")
        print(f"{'='*80}\n")
    
    def get_bounds(self):
        """Calculate geographic bounds"""
        min_lon, min_lat = float('inf'), float('inf')
        max_lon, max_lat = float('-inf'), float('-inf')
        
        for feature_data in self.feature_lookup.values():
            bounds = feature_data['geometry'].bounds
            min_lon = min(min_lon, bounds[0])
            min_lat = min(min_lat, bounds[1])
            max_lon = max(max_lon, bounds[2])
            max_lat = max(max_lat, bounds[3])
        
        return (min_lon, min_lat, max_lon, max_lat)
    
    def draw_diagonal_hatch(self, draw, coords, base_rgb, hatch_rgb, scale):
        """Fast diagonal hatch pattern"""
        draw.polygon(coords, fill=base_rgb, outline=None)
        
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        spacing = 6 * scale
        for offset in range(int(-max_y + min_y), int(max_x - min_x), spacing):
            x1 = min_x + max(0, offset)
            y1 = min_y + max(0, -offset)
            x2 = min_x + min(max_x - min_x, max_y - min_y + offset)
            y2 = min_y + min(max_y - min_y, max_x - min_x - offset)
            draw.line([(x1, y1), (x2, y2)], fill=hatch_rgb, width=scale)
    
    def draw_dots(self, draw, coords, base_rgb, dot_rgb, scale):
        """Fast dot pattern"""
        draw.polygon(coords, fill=base_rgb, outline=None)
        
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        spacing = 8 * scale
        dot_size = 2 * scale
        
        for x in range(int(min_x), int(max_x), spacing):
            for y in range(int(min_y), int(max_y), spacing):
                draw.ellipse([x - dot_size, y - dot_size, 
                            x + dot_size, y + dot_size], fill=dot_rgb)
    
    def render_tile(self, tile):
        """Render tile with FIXED visibility and NO overlapping"""
        z, x, y = tile.z, tile.x, tile.y
        
        # 2x scale for anti-aliasing
        scale = 2
        img_size = self.tile_size * scale
        
        is_low_zoom = z < 14
        
        img = Image.new('RGBA', (img_size, img_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        tile_bounds = mercantile.bounds(tile)
        tile_bbox = box(tile_bounds.west, tile_bounds.south, 
                       tile_bounds.east, tile_bounds.north)
        
        # Fast spatial query
        intersecting_ids = list(self.spatial_index.intersection(tile_bbox.bounds))
        
        if not intersecting_ids:
            return None
        
        color_map = self.get_color_map()
        
        # FIX 1: NO BUFFERING - prevents overlapping
        # FIX 2: Simplify ONLY at very low zoom - prevents disappearing
        simplification_tolerance = {
            7: 0.0008,
            8: 0.0004,
            9: 0.0002,
            10: 0.0001,
            11: 0.00005,
            12: 0.00002,
            13: 0.00001,
            14: 0
        }
        tolerance = simplification_tolerance.get(z, 0)
        
        # Render features
        for feature_id in intersecting_ids:
            feature_data = self.feature_lookup[feature_id]
            geom = feature_data['geometry']
            zone = feature_data['zone']
            
            if not geom.intersects(tile_bbox):
                continue
            
            if zone not in color_map:
                continue
            
            color_info = color_map[zone]
            
            # Clip to tile bounds
            try:
                geom = geom.intersection(tile_bbox)
                if geom.is_empty:
                    continue
            except:
                continue
            
            # FIX 3: Smart simplification - only if feature is large enough
            if tolerance > 0 and geom.area > tolerance * 10:
                try:
                    simplified = geom.simplify(tolerance, preserve_topology=True)
                    # Only use simplified version if it's still valid and visible
                    if simplified.is_valid and not simplified.is_empty and simplified.area > tolerance:
                        geom = simplified
                except:
                    pass  # Keep original if simplification fails
            
            # Handle MultiPolygon and Polygon
            if geom.geom_type == 'Polygon':
                polygons = [geom]
            elif geom.geom_type == 'MultiPolygon':
                polygons = list(geom.geoms)
            else:
                continue
            
            for polygon in polygons:
                # Convert to pixel coordinates
                pixel_coords = []
                for coord in polygon.exterior.coords:
                    lon, lat = coord[0], coord[1]
                    px = (lon - tile_bounds.west) / (tile_bounds.east - tile_bounds.west) * img_size
                    py = (tile_bounds.north - lat) / (tile_bounds.north - tile_bounds.south) * img_size
                    pixel_coords.append((px, py))
                
                if len(pixel_coords) < 3:
                    continue
                
                # FIX 4: Small feature handling - draw point if too small
                xs = [p[0] for p in pixel_coords]
                ys = [p[1] for p in pixel_coords]
                width = max(xs) - min(xs)
                height = max(ys) - min(ys)
                
                # If feature is smaller than 2x2 pixels, draw a small point
                if width < 2 * scale and height < 2 * scale:
                    center_x = sum(xs) / len(xs)
                    center_y = sum(ys) / len(ys)
                    radius = 1.5 * scale
                    
                    if color_info.get('type') in ['dotted', 'hatched']:
                        fill_rgb = self.hex_to_rgb(color_info.get('solid_lowzoom', 
                                                   color_info.get('base', '#FFFFFF')))
                    else:
                        fill_rgb = self.hex_to_rgb(color_info['fill'])
                    
                    draw.ellipse([center_x - radius, center_y - radius, 
                                center_x + radius, center_y + radius], fill=fill_rgb)
                    continue
                
                # Render based on type
                if color_info.get('type') == 'dotted':
                    if is_low_zoom and 'solid_lowzoom' in color_info:
                        fill_rgb = self.hex_to_rgb(color_info['solid_lowzoom'])
                        draw.polygon(pixel_coords, fill=fill_rgb, outline=None)
                    else:
                        base_rgb = self.hex_to_rgb(color_info['base'])
                        dot_rgb = self.hex_to_rgb(color_info['dot'])
                        self.draw_dots(draw, pixel_coords, base_rgb, dot_rgb, scale)
                
                elif color_info.get('type') == 'hatched':
                    if is_low_zoom and 'solid_lowzoom' in color_info:
                        fill_rgb = self.hex_to_rgb(color_info['solid_lowzoom'])
                        draw.polygon(pixel_coords, fill=fill_rgb, outline=None)
                    else:
                        base_rgb = self.hex_to_rgb(color_info['base'])
                        hatch_rgb = self.hex_to_rgb(color_info['hatch'])
                        self.draw_diagonal_hatch(draw, pixel_coords, base_rgb, hatch_rgb, scale)
                
                else:
                    fill_rgb = self.hex_to_rgb(color_info['fill'])
                    draw.polygon(pixel_coords, fill=fill_rgb, outline=None)
                    
                    # Draw outline if specified
                    if color_info.get('outline'):
                        outline_rgb = self.hex_to_rgb(color_info['outline'])
                        draw.line(pixel_coords + [pixel_coords[0]], 
                                fill=outline_rgb, width=scale)
        
        # Downsample for anti-aliasing
        img = img.resize((self.tile_size, self.tile_size), Image.LANCZOS)
        return img
    
    def generate_tiles(self, min_zoom=7, max_zoom=18):
        """Generate tiles with progress tracking"""
        print(f"\n{'='*80}")
        print(f"GENERATING TILES (Zoom {min_zoom}-{max_zoom})")
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
            print(f"Zoom {zoom:2d} | {total_for_zoom:,} tiles", end=" ", flush=True)
            
            zoom_dir = self.output_dir / str(zoom)
            rendered = 0
            
            for tile in tiles:
                img = self.render_tile(tile)
                
                if img is not None:
                    tile_dir = zoom_dir / str(tile.x)
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    
                    tile_path = tile_dir / f"{tile.y}.png"
                    img.save(tile_path, 'PNG', optimize=True)
                    rendered += 1
            
            zoom_elapsed = time.time() - zoom_start
            speed = rendered / zoom_elapsed if zoom_elapsed > 0 else 0
            print(f"| ✓ {rendered:,} rendered in {zoom_elapsed:.1f}s ({speed:.1f} tiles/s)")
            
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
  <title>Amaravati Master Plan</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>body, html, #map {{ margin:0; padding:0; height:100%; }}</style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const map = L.map('map').setView([{center_lat:.6f}, {center_lon:.6f}], 12);
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
      maxZoom: 19
    }}).addTo(map);
    L.tileLayer('./{{z}}/{{x}}/{{y}}.png', {{
      minZoom: 7, maxZoom: 18, opacity: 0.8
    }}).addTo(map);
  </script>
</body>
</html>"""
        
        (self.output_dir / 'index.html').write_text(html)
        print(f"✓ Viewer: {self.output_dir}/index.html")


def main():
    data_dir = Path('/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping/data/andhra_pradesh/amaravati/master_plan')
    output_dir = Path('./amaravati_tiles')
    
    print("="*80)
    print("AMARAVATI MASTER PLAN - FIXED TILE GENERATOR")
    print("="*80)
    
    generator = AmaravatiFixedTileGenerator(data_dir, output_dir)
    generator.load_geojson_files()
    generator.generate_tiles(min_zoom=7, max_zoom=18)
    generator.generate_html_viewer()
    
    print(f"\nTo view: cd {output_dir} && python3 -m http.server 8007\n")


if __name__ == '__main__':
    main()