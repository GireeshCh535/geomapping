#!/usr/bin/env python3
"""
Visakhapatnam Master Plan - Tile Generator
Converts GeoJSON files to PNG tiles (zoom 7-18) with custom styling
"""

import json
import os
import time
from pathlib import Path
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import shape, box
from rtree import index

class VisakhapatnamTileGenerator:
    def __init__(self, data_dir, output_dir):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.spatial_index = index.Index()
        self.feature_id_counter = 0
        self.feature_lookup = {}
        
    def get_color_map(self):
        """Exact color mapping for all Visakhapatnam zones"""
        return {
            'Agricultural_Use_Zone': {'fill': '#D3FFBE'},
            'Blue_Zone_Water_Bodies': {'fill': '#73FFDF'},
            'Brown_Zone_Hills': {'fill': '#A87000'},
            'Commercial_Use_Zone': {'fill': '#004DA8'},
            
            'Existing_Crematorium_Burial_Ground_Graveyard': {
                'type': 'hatched',
                'base': '#FFFFFF',
                'hatch': '#FF0000',
                'solid_lowzoom': '#FF8080'
            },
            
            'Existing_Educational_Facilities': {
                'type': 'hatched',
                'base': '#FF0000',
                'hatch': '#000000',
                'solid_lowzoom': '#CC0000'
            },
            
            'Existing_Government_Semi_Government_Facilities': {'fill': '#FF0000'},
            
            'Existing_Health_Facilities': {
                'type': 'dotted',
                'base': '#FF0000',
                'dot': '#CCCCCC',
                'solid_lowzoom': '#FF6666'
            },
            
            'Proposed_Industrial_Use_Zone': {
                'type': 'hatched',
                'base': '#C500FF',
                'hatch': '#FFFFFF',
                'solid_lowzoom': '#D966FF'
            },
            
            'Existing_Industrial_Area': {'fill': '#C500FF'},
            
            'Existing_Public_Utilities': {
                'type': 'hatched',
                'base': '#FF7F7F',
                'hatch': '#E60000',
                'solid_lowzoom': '#FF9999'
            },
            
            'Existing_Recreational_Playgrounds_Parks_Layout_OpenSpace': {'fill': '#55FF00'},
            
            'Existing_Religious_Facilities': {
                'type': 'hatched',
                'base': '#FF0000',
                'hatch': '#55FF00',
                'solid_lowzoom': '#FF6666'
            },
            
            'Existing_Road_Railway_Line_Area': {
                'type': 'hatched',
                'base': '#828282',
                'hatch': '#828282',
                'solid_lowzoom': '#828282'
            },
            
            'Existing_Transportation_Facility': {'fill': '#686868'},
            'Green_Zone_Forest': {'fill': '#00734C'},
            'Kambalakonda_Eco_Sensitive_Zone_NAOB_Buffer_Zoological_Park': {'fill': '#D7C29E'},
            'Kambalakonda_WildLife_Sanctuary_Biodiversity_Area': {'fill': '#38A800'},
            'Mixed_Use_Zone_1': {'fill': '#FFAA00'},
            'Mixed_Use_Zone_2_BAIA': {'fill': '#FFD37F'},
            
            'Mixed_Use_Zone_3_BAIA': {
                'type': 'hatched',
                'base': '#E69800',
                'hatch': '#E1E1E1',
                'solid_lowzoom': '#F0B000'
            },
            
            'Mixed_Use_Zone_4_BAIA': {
                'type': 'dotted',
                'base': '#FFAA00',
                'dot': '#000000',
                'solid_lowzoom': '#FFBB33'
            },
            
            'Proposed_PSP_Use_Zone': {
                'type': 'hatched',
                'base': '#FFFFFF',
                'hatch': '#FF0000',
                'solid_lowzoom': '#FFCCCC'
            },
            
            'Proposed_Public_Utilities_Use_Zone': {
                'type': 'hatched',
                'base': '#F57A7A',
                'hatch': '#FFFFFF',
                'solid_lowzoom': '#FF9999'
            },
            
            'Proposed_Recreational_Use_Zone': {'fill': '#4C7300'},
            'Proposed_Road_Network': {'fill': '#000000'},
            
            'Proposed_Transportation_Facility_Use_Zone': {
                'type': 'hatched',
                'base': '#343434',
                'hatch': '#FFFFFF',
                'solid_lowzoom': '#555555'
            },
            
            'Residential_Use_Zone': {'fill': '#FFFF73'},
            
            'Sea_River_Accreted_Land': {
                'type': 'dotted',
                'base': '#D7C29E',
                'dot': '#E39E00',
                'solid_lowzoom': '#E0D0B0'
            },
            
            'Special_Area_Use_Zone': {
                'type': 'hatched',
                'base': '#FFFFFF',
                'hatch': '#002673',
                'solid_lowzoom': '#CCE0FF'
            },
            
            'Water_Body_Buffer': {
                'type': 'dotted',
                'base': '#4CE600',
                'dot': '#267300',
                'solid_lowzoom': '#66FF33'
            }
        }
    
    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def load_geojson_files(self):
        """Load all GeoJSON files and build spatial index"""
        print("\n" + "="*80)
        print("LOADING GEOJSON DATA - VISAKHAPATNAM")
        print("="*80)
        
        geojson_files = sorted(self.data_dir.glob('*.geojson'))
        total_files = len(geojson_files)
        total_features = 0
        
        print(f"Found {total_files} GeoJSON files\n")
        
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
                print(f"✓ {loaded:>7,} features")
                
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
        
        # Smart simplification - prevents disappearing features
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
            
            # Smart simplification - only if feature is large enough
            if tolerance > 0 and geom.area > tolerance * 10:
                try:
                    simplified = geom.simplify(tolerance, preserve_topology=True)
                    if simplified.is_valid and not simplified.is_empty and simplified.area > tolerance:
                        geom = simplified
                except:
                    pass
            
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
                
                # Small feature handling
                xs = [p[0] for p in pixel_coords]
                ys = [p[1] for p in pixel_coords]
                width = max(xs) - min(xs)
                height = max(ys) - min(ys)
                
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
  <title>Visakhapatnam Master Plan</title>
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
    data_dir = Path('/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping/data/andhra_pradesh/visakhapatnam/master_plan')
    output_dir = Path('./tiles/visakhapatnam')
    
    print("="*80)
    print("VISAKHAPATNAM MASTER PLAN - TILE GENERATOR")
    print("="*80)
    
    generator = VisakhapatnamTileGenerator(data_dir, output_dir)
    generator.load_geojson_files()
    generator.generate_tiles(min_zoom=7, max_zoom=18)
    generator.generate_html_viewer()
    
    print(f"\nTo view: cd {output_dir} && python3 -m http.server 8008\n")


if __name__ == '__main__':
    main()