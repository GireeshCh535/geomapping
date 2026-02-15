#!/usr/bin/env python3
"""
Visakhapatnam Master Plan - DENSE COMPLETE TILES
Every tile shows ALL data in its bounds - NO empty spaces
"""

import json
import os
import time
from pathlib import Path
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import shape, box
from rtree import index

class VisakhapatnamDenseCompleteTiles:
    def __init__(self, data_dir, output_dir):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.spatial_index = index.Index()
        self.feature_id_counter = 0
        self.feature_lookup = {}
        
    def get_color_map(self):
        """Complete color mapping for Visakhapatnam"""
        return {
            'x
        }
    
    def hex_to_rgb(self, hex_color):
        """Convert hex to RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def load_geojson_files(self):
        """Load all GeoJSON"""
        print("\n" + "="*80)
        print("LOADING GEOJSON DATA - VISAKHAPATNAM DENSE MODE")
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
    
    def render_tile_dense(self, tile):
        """DENSE RENDERING: Complete coverage, no empty spaces"""
        z, x, y = tile.z, tile.x, tile.y
        
        scale = 4  # Always 4x for maximum density
        img_size = self.tile_size * scale
        
        img = Image.new('RGBA', (img_size, img_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        tile_bounds = mercantile.bounds(tile)
        tile_bbox = box(tile_bounds.west, tile_bounds.south, 
                       tile_bounds.east, tile_bounds.north)
        
        intersecting_ids = list(self.spatial_index.intersection(tile_bbox.bounds))
        
        if not intersecting_ids:
            return None
        
        color_map = self.get_color_map()
        rendered_count = 0
        
        for feature_id in intersecting_ids:
            feature_data = self.feature_lookup[feature_id]
            geom = feature_data['geometry']
            zone = feature_data['zone']
            
            if not geom.intersects(tile_bbox):
                continue
            
            color_info = color_map.get(zone, {'fill': '#CCCCCC'})
            fill_rgb = self.hex_to_rgb(color_info['fill'])
            
            try:
                clipped_geom = geom.intersection(tile_bbox)
                if clipped_geom.is_empty:
                    continue
                geom = clipped_geom
            except:
                pass
            
            if geom.geom_type == 'Polygon':
                polygons = [geom]
            elif geom.geom_type == 'MultiPolygon':
                polygons = list(geom.geoms)
            else:
                continue
            
            for polygon in polygons:
                try:
                    pixel_coords = []
                    for coord in polygon.exterior.coords:
                        lon, lat = coord[0], coord[1]
                        px = (lon - tile_bounds.west) / (tile_bounds.east - tile_bounds.west) * img_size
                        py = (tile_bounds.north - lat) / (tile_bounds.north - tile_bounds.south) * img_size
                        pixel_coords.append((px, py))
                    
                    if len(pixel_coords) < 3:
                        continue
                    
                    # Dense fill with outline
                    draw.polygon(pixel_coords, fill=fill_rgb, outline=fill_rgb, width=2)
                    
                    # Extra coverage for small features
                    xs = [p[0] for p in pixel_coords]
                    ys = [p[1] for p in pixel_coords]
                    center_x = sum(xs) / len(xs)
                    center_y = sum(ys) / len(ys)
                    width = max(xs) - min(xs)
                    height = max(ys) - min(ys)
                    
                    if width < 8 * scale or height < 8 * scale:
                        radius = max(2 * scale, int(min(width, height) / 2))
                        draw.ellipse([center_x - radius, center_y - radius, 
                                    center_x + radius, center_y + radius], 
                                   fill=fill_rgb, outline=fill_rgb)
                    
                    rendered_count += 1
                    
                except:
                    try:
                        xs = [p[0] for p in pixel_coords]
                        ys = [p[1] for p in pixel_coords]
                        center_x = sum(xs) / len(xs)
                        center_y = sum(ys) / len(ys)
                        draw.ellipse([center_x - 2*scale, center_y - 2*scale, 
                                    center_x + 2*scale, center_y + 2*scale], fill=fill_rgb)
                        rendered_count += 1
                    except:
                        pass
        
        if rendered_count == 0:
            return None
        
        img = img.resize((self.tile_size, self.tile_size), Image.LANCZOS)
        return img
    
    def generate_tiles(self, min_zoom=5, max_zoom=18):
        """Generate dense complete tiles"""
        print(f"\n{'='*80}")
        print(f"GENERATING DENSE TILES (Zoom {min_zoom}-{max_zoom})")
        print(f"Mode: COMPLETE COVERAGE - NO EMPTY SPACES")
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
                img = self.render_tile_dense(tile)
                
                if img is not None:
                    tile_dir = zoom_dir / str(tile.x)
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    
                    tile_path = tile_dir / f"{tile.y}.png"
                    img.save(tile_path, 'PNG', optimize=True)
                    rendered += 1
            
            zoom_elapsed = time.time() - zoom_start
            speed = rendered / zoom_elapsed if zoom_elapsed > 0 else 0
            print(f"| ✓ {rendered:,} in {zoom_elapsed:.1f}s ({speed:.1f} tiles/s)")
            
            total_tiles += rendered
        
        overall_elapsed = time.time() - overall_start
        print(f"\n{'='*80}")
        print(f"✓ COMPLETE: {total_tiles:,} tiles in {overall_elapsed:.1f}s "
              f"({overall_elapsed/60:.1f} min)")
        print(f"{'='*80}\n")
    
    def generate_html_viewer(self):
        """Generate viewer"""
        bounds = self.get_bounds()
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Visakhapatnam Master Plan - Dense Tiles</title>
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
      minZoom: 5, maxZoom: 18, opacity: 0.85
    }}).addTo(map);
  </script>
</body>
</html>"""
        
        (self.output_dir / 'index.html').write_text(html)
        print(f"✓ Viewer: {self.output_dir}/index.html")


def main():
    import sys
    
    possible_paths = [
        Path('/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping/data/andhra_pradesh/visakhapatnam/master_plan'),
        Path('/home/gamyam/1acre/geomapping/data/andhra_pradesh/visakhapatnam/master_plan'),
        Path('./data/andhra_pradesh/visakhapatnam/master_plan'),
    ]
    
    data_dir = None
    for path in possible_paths:
        if path.exists():
            data_dir = path
            break
    
    if data_dir is None:
        print("Provide path to master_plan directory:")
        user_path = input("> ").strip()
        data_dir = Path(user_path)
        if not data_dir.exists():
            print(f"✗ {data_dir} not found")
            sys.exit(1)
    
    output_dir = Path('./tiles/visakhapatnam_dense')
    
    print("="*80)
    print("VISAKHAPATNAM - DENSE COMPLETE TILES GENERATOR")
    print("="*80)
    print(f"Data: {data_dir}")
    print(f"Output: {output_dir}")
    
    generator = VisakhapatnamDenseCompleteTiles(data_dir, output_dir)
    generator.load_geojson_files()
    
    if generator.feature_id_counter == 0:
        print("✗ No features loaded!")
        sys.exit(1)
    
    generator.generate_tiles(min_zoom=5, max_zoom=18)
    generator.generate_html_viewer()
    
    print(f"\nView: cd {output_dir} && python3 -m http.server 8012\n")


if __name__ == '__main__':
    main()