#!/usr/bin/env python3
"""
Amaravati Master Plan - DENSE COMPLETE TILES
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

class AmaravatiDenseCompleteTiles:
    def __init__(self, data_dir, output_dir):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.spatial_index = index.Index()
        self.feature_id_counter = 0
        self.feature_lookup = {}
        
    def get_color_map(self):
        """Complete color mapping with all variations"""
        return {
            # Filenames
            'Burial Ground': {'fill': '#E39E00'},
            'C1 -Mixed use zone': {'fill': '#73B2FF'},
            'C2- General commercial zone': {'fill': '#00C5FF'},
            'C3-Neighbourhood centre zone': {'fill': '#00C5FF'},
            'C4-Town centre zone': {'fill': '#00A9E6'},
            'C5-Regional centre zone': {'fill': '#0070FF'},
            'C6-Central business district zone': {'fill': '#005CE6'},
            'Commercial Vacant': {'fill': '#C5E2FF'},
            'I1-Business park zone': {'fill': '#FFBEE8'},
            'I2-Logistics zone': {'fill': '#FF73DF'},
            'I3-Non polluting industry zone': {'fill': '#B6B6B6'},
            'Not Available': {'fill': '#CCCCCC'},
            'P1-Passive zone': {'fill': '#267300'},
            'P2-Active zone': {'fill': '#38A800'},
            'P3-Protected zone': {'fill': '#BEE8FF'},
            'P3-Protected zone Hills': {'fill': '#4C7300'},
            'PGN-G': {'fill': '#4C7300'},
            'PGN-V': {'fill': '#897044'},
            'R1-Village planning zone': {'fill': '#EEEEEE'},
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
            'U2- Road Reserve Zone': {'fill': '#82817D'},
            
            # Symbology variations (from GeoJSON properties)
            'R4-High density zone': {'fill': '#FFAA00'},
            'R3-Medium to high density zone': {'fill': '#F5CA7A'},
            'SC1a-Mixed Use': {'fill': '#0070FF'},
            'SC1a - Mixed Use': {'fill': '#0070FF'},
            'SC1b-Mixed Use': {'fill': '#73B2FF'},
            'SC1b - Mixed Use': {'fill': '#73B2FF'},
            'Super Block C': {'fill': '#73B2FF'},  # SC1b plot_categ
            'SS1-Government Zone': {'fill': '#E60000'},
            'SS2a-Education Zone': {'fill': '#FF7F7F'},
            'SS2b-Cultural Zone': {'fill': '#C500FF'},
            'SS2c-Health Zone': {'fill': '#D3FFBE'},
            'SS3-Special Zone': {'fill': '#A83800'},
        }
    
    def hex_to_rgb(self, hex_color):
        """Convert hex to RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def load_geojson_files(self):
        """Load all GeoJSON with symbology-based naming"""
        print("\n" + "="*80)
        print("LOADING GEOJSON DATA - DENSE MODE")
        print("="*80)
        
        geojson_files = sorted(self.data_dir.glob('*.geojson'))
        total_files = len(geojson_files)
        total_features = 0
        
        print(f"Found {total_files} files\n")
        
        load_start = time.time()
        
        for idx, geojson_file in enumerate(geojson_files, 1):
            zone_name = geojson_file.stem
            file_size = geojson_file.stat().st_size / 1024 / 1024
            
            print(f"[{idx:2d}/{total_files}] {zone_name:<50} ({file_size:6.2f} MB)", end=" ", flush=True)
            
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
                        
                        props = feature.get('properties', {})
                        # Use symbology, fallback to plot_categ, then filename
                        feature_zone = props.get('symbology', props.get('plot_categ', zone_name))
                        
                        feature_data = {
                            'geometry': geom,
                            'zone': feature_zone,
                            'properties': props
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
        """
        DENSE RENDERING: Every tile shows ALL data in its bounds
        NO empty spaces - complete coverage
        """
        z, x, y = tile.z, tile.x, tile.y
        
        # Higher resolution for complete coverage
        scale = 4  # Always 4x for maximum density
        img_size = self.tile_size * scale
        
        img = Image.new('RGBA', (img_size, img_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        tile_bounds = mercantile.bounds(tile)
        tile_bbox = box(tile_bounds.west, tile_bounds.south, 
                       tile_bounds.east, tile_bounds.north)
        
        # Get ALL features in tile
        intersecting_ids = list(self.spatial_index.intersection(tile_bbox.bounds))
        
        if not intersecting_ids:
            return None
        
        color_map = self.get_color_map()
        rendered_count = 0
        
        # Render EVERY feature - no filtering
        for feature_id in intersecting_ids:
            feature_data = self.feature_lookup[feature_id]
            geom = feature_data['geometry']
            zone = feature_data['zone']
            
            # Quick intersection check
            if not geom.intersects(tile_bbox):
                continue
            
            # Get color with fallback
            if zone not in color_map:
                color_info = {'fill': '#CCCCCC'}  # Default grey
            else:
                color_info = color_map[zone]
            
            fill_rgb = self.hex_to_rgb(color_info['fill'])
            
            # Clip to tile (but keep original if clipping fails)
            try:
                clipped_geom = geom.intersection(tile_bbox)
                if clipped_geom.is_empty:
                    continue
                geom = clipped_geom
            except:
                pass  # Use original
            
            # Handle all geometry types
            if geom.geom_type == 'Polygon':
                polygons = [geom]
            elif geom.geom_type == 'MultiPolygon':
                polygons = list(geom.geoms)
            else:
                continue
            
            # Render each polygon
            for polygon in polygons:
                try:
                    # Convert coordinates to pixels
                    pixel_coords = []
                    for coord in polygon.exterior.coords:
                        lon, lat = coord[0], coord[1]
                        px = (lon - tile_bounds.west) / (tile_bounds.east - tile_bounds.west) * img_size
                        py = (tile_bounds.north - lat) / (tile_bounds.north - tile_bounds.south) * img_size
                        pixel_coords.append((px, py))
                    
                    if len(pixel_coords) < 3:
                        continue
                    
                    # DENSE RENDERING: Fill completely with outline
                    draw.polygon(pixel_coords, fill=fill_rgb, outline=fill_rgb, width=2)
                    
                    # Add extra coverage at center for small features
                    xs = [p[0] for p in pixel_coords]
                    ys = [p[1] for p in pixel_coords]
                    center_x = sum(xs) / len(xs)
                    center_y = sum(ys) / len(ys)
                    width = max(xs) - min(xs)
                    height = max(ys) - min(ys)
                    
                    # For small features, add filled circle
                    if width < 8 * scale or height < 8 * scale:
                        radius = max(2 * scale, int(min(width, height) / 2))
                        draw.ellipse([center_x - radius, center_y - radius, 
                                    center_x + radius, center_y + radius], 
                                   fill=fill_rgb, outline=fill_rgb)
                    
                    rendered_count += 1
                    
                except Exception as e:
                    # Fallback: just draw a dot
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
        
        # Downsample with LANCZOS for quality
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
  <title>Amaravati Master Plan - Dense Tiles</title>
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
        Path('data/andhra_pradesh/amaravati/master_plan'),
        Path('/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping/data/andhra_pradesh/amaravati/master_plan'),
        Path('/home/gamyam/1acre/geomapping/data/andhra_pradesh/amaravati/master_plan'),
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
    
    output_dir = Path('./tiles/amaravati_dense')
    
    print("="*80)
    print("AMARAVATI - DENSE COMPLETE TILES GENERATOR")
    print("="*80)
    print(f"Data: {data_dir}")
    print(f"Output: {output_dir}")
    
    generator = AmaravatiDenseCompleteTiles(data_dir, output_dir)
    generator.load_geojson_files()
    
    if generator.feature_id_counter == 0:
        print("✗ No features loaded!")
        sys.exit(1)
    
    generator.generate_tiles(min_zoom=5, max_zoom=18)
    generator.generate_html_viewer()
    
    print(f"\nView: cd {output_dir} && python3 -m http.server 8010\n")


if __name__ == '__main__':
    main()