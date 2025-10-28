#!/usr/bin/env python3
"""
Warangal Master Plan - FIXED Tile Generator
Solves: Features disappearing at zoom 8-16 and appearing only at 17+
"""

import json
import os
import time
from pathlib import Path
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import shape, box
from rtree import index

class WarangalFixedTileGenerator:
    def __init__(self, data_dir, output_dir):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.spatial_index = index.Index()
        self.feature_id_counter = 0
        self.feature_lookup = {}
        
    def get_color_map(self):
        """Exact color mapping for all Warangal zones"""
        return {
            'Agriculture': {'fill': '#D3FFBE'},
            
            'AirStrip': {
                'type': 'hatched',
                'base': '#FF00C5',
                'hatch': '#FFFFFF',
                'solid_lowzoom': '#FF66D9'
            },
            
            'Commercial': {'fill': '#0070FF'},
            'Forest': {'fill': '#267300'},
            'Growth Corridor': {'fill': '#FFBEE8'},
            'Growth Corridor 2': {'fill': '#FF73DF'},
            
            'Heritage': {
                'type': 'hatched',
                'base': '#FFA77F',
                'hatch': '#732600',
                'solid_lowzoom': '#FFB899'
            },
            
            'Hill Buffer': {'fill': '#55FF00'},
            'Hillocks': {'fill': '#A87000'},
            'Industrial': {'fill': '#C500FF'},
            'Mixed Use': {'fill': '#FFAA00'},
            'Public and Semi-Public': {'fill': '#FF0000'},
            
            'Public Utilities': {
                'type': 'hatched',
                'base': '#E69800',
                'hatch': '#FF0000',
                'solid_lowzoom': '#FFB033'
            },
            
            'Railway Land': {'fill': '#CCCCCC'},
            'Recreational': {'fill': '#55FF00'},
            'Residential': {'fill': '#FFFF00'},
            'ResidentialExpansion': {'fill': '#9C9C9C'},
            'Road Buffer': {'fill': '#4E4E4E'},
            'Transportation': {'fill': '#B2B2B2'},
            'Water Bodies': {'fill': '#00C5FF'},
            'Water Bodies Buffer': {'fill': '#55FF00'},
            'Zoological Park': {'fill': '#38A800'}
        }
    
    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def load_geojson_files(self):
        """Load all GeoJSON files and build spatial index"""
        print("\n" + "="*80)
        print("LOADING GEOJSON DATA - WARANGAL")
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
    
    def render_tile(self, tile):
        """Render tile with FIXED visibility - no disappearing features"""
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
        
        # CRITICAL: Track if we actually rendered anything
        features_rendered = False
        
        # ULTRA-CONSERVATIVE simplification - only at very low zooms
        # This ensures features NEVER disappear
        simplification_tolerance = {
            7: 0.0001,   # ~11m - very gentle
            8: 0.00005,  # ~5.5m
            9: 0.00002,  # ~2.2m
            10: 0.00001, # ~1.1m
            11: 0.000005,# ~0.55m
            12: 0        # No simplification from zoom 12+
        }
        tolerance = simplification_tolerance.get(z, 0)
        
        # Render features
        for feature_id in intersecting_ids:
            feature_data = self.feature_lookup[feature_id]
            geom = feature_data['geometry']
            zone = feature_data['zone']
            
            # CRITICAL: Skip if doesn't actually intersect (spatial index can have false positives)
            if not geom.intersects(tile_bbox):
                continue
            
            if zone not in color_map:
                continue
            
            color_info = color_map[zone]
            
            # CRITICAL: Store original geometry for fallback
            original_geom = geom
            
            # Clip to tile bounds - STRICT clipping
            try:
                geom = geom.intersection(tile_bbox)
                if geom.is_empty or not geom.is_valid:
                    continue
                # ADDITIONAL: Check if clipped geometry has meaningful area
                if geom.area < 1e-10:  # Essentially zero area
                    continue
            except:
                continue
            
            # ULTRA-SAFE simplification
            # Only simplify VERY LARGE features at low zoom
            if tolerance > 0 and z < 12 and geom.area > tolerance * 100:
                try:
                    simplified = geom.simplify(tolerance, preserve_topology=True)
                    # Very strict validation - use original if ANY doubt
                    if (simplified.is_valid and 
                        not simplified.is_empty and 
                        simplified.area > geom.area * 0.7):  # Must keep 70% of area
                        geom = simplified
                    else:
                        geom = original_geom.intersection(tile_bbox)  # Use original
                except:
                    geom = original_geom.intersection(tile_bbox)  # Use original on error
            
            # Handle MultiPolygon and Polygon
            if geom.geom_type == 'Polygon':
                polygons = [geom]
            elif geom.geom_type == 'MultiPolygon':
                polygons = list(geom.geoms)
            else:
                continue
            
            for polygon in polygons:
                # Skip invalid polygons
                if not polygon.is_valid or polygon.is_empty:
                    continue
                    
                # Convert to pixel coordinates
                pixel_coords = []
                try:
                    for coord in polygon.exterior.coords:
                        lon, lat = coord[0], coord[1]
                        px = (lon - tile_bounds.west) / (tile_bounds.east - tile_bounds.west) * img_size
                        py = (tile_bounds.north - lat) / (tile_bounds.north - tile_bounds.south) * img_size
                        pixel_coords.append((px, py))
                except:
                    continue
                
                if len(pixel_coords) < 3:
                    continue
                
                # CRITICAL FIX: Better small feature handling
                xs = [p[0] for p in pixel_coords]
                ys = [p[1] for p in pixel_coords]
                width = max(xs) - min(xs)
                height = max(ys) - min(ys)
                
                # If feature is VERY tiny (< 1px), draw a larger point for visibility
                if width < 1 * scale or height < 1 * scale:
                    center_x = sum(xs) / len(xs)
                    center_y = sum(ys) / len(ys)
                    # Larger radius for better visibility
                    radius = 2 * scale  # Was 1.5, now 2 for better visibility
                    
                    if color_info.get('type') == 'hatched':
                        fill_rgb = self.hex_to_rgb(color_info.get('solid_lowzoom', 
                                                   color_info.get('base', '#FFFFFF')))
                    else:
                        fill_rgb = self.hex_to_rgb(color_info['fill'])
                    
                    draw.ellipse([center_x - radius, center_y - radius, 
                                center_x + radius, center_y + radius], fill=fill_rgb)
                    features_rendered = True
                    continue
                
                # ADDITIONAL: For small but not tiny features, ensure minimum rendering size
                if width < 3 * scale or height < 3 * scale:
                    # Draw both the polygon AND a point for visibility
                    center_x = sum(xs) / len(xs)
                    center_y = sum(ys) / len(ys)
                    
                    if color_info.get('type') == 'hatched':
                        fill_rgb = self.hex_to_rgb(color_info.get('solid_lowzoom', 
                                                   color_info.get('base', '#FFFFFF')))
                    else:
                        fill_rgb = self.hex_to_rgb(color_info['fill'])
                    
                    # Draw a small filled circle at center
                    radius = 1.5 * scale
                    draw.ellipse([center_x - radius, center_y - radius, 
                                center_x + radius, center_y + radius], fill=fill_rgb)
                    features_rendered = True
                
                # Render based on type - with fallbacks
                try:
                    if color_info.get('type') == 'hatched':
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
                    
                    features_rendered = True
                    
                except Exception as e:
                    # FALLBACK: If pattern drawing fails, draw solid color
                    try:
                        if color_info.get('type') == 'hatched':
                            fill_rgb = self.hex_to_rgb(color_info.get('solid_lowzoom', 
                                                       color_info.get('base', '#FFFFFF')))
                        else:
                            fill_rgb = self.hex_to_rgb(color_info['fill'])
                        draw.polygon(pixel_coords, fill=fill_rgb, outline=None)
                        features_rendered = True
                    except:
                        pass  # Skip if even fallback fails
        
        # CRITICAL: Only return tile if we actually rendered something
        if not features_rendered:
            return None
        
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
  <title>Warangal Master Plan</title>
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
    import sys
    
    # Try multiple possible paths
    possible_paths = [
        Path('/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping/data/Telangana/warangal/master_plan'),
        Path('/home/gamyam/1acre/geomapping/data/Telangana/warangal/master_plan'),
        Path('./data/Telangana/warangal/master_plan'),
        Path('../../../data/Telangana/warangal/master_plan')
    ]
    
    # Find the correct path
    data_dir = None
    for path in possible_paths:
        if path.exists():
            data_dir = path
            break
    
    # If still not found, ask user
    if data_dir is None:
        print("="*80)
        print("ERROR: Could not find GeoJSON data directory")
        print("="*80)
        print("\nTried the following paths:")
        for path in possible_paths:
            print(f"  - {path}")
        print("\nPlease provide the correct path to the master_plan directory:")
        user_path = input("> ").strip()
        data_dir = Path(user_path)
        
        if not data_dir.exists():
            print(f"\n✗ Error: Directory does not exist: {data_dir}")
            sys.exit(1)
    
    output_dir = Path('./warangal_tiles')
    
    print("="*80)
    print("WARANGAL MASTER PLAN - FIXED TILE GENERATOR")
    print("="*80)
    print(f"\nData directory: {data_dir}")
    print(f"Output directory: {output_dir}")
    
    generator = WarangalFixedTileGenerator(data_dir, output_dir)
    generator.load_geojson_files()
    
    # Check if any files were loaded
    if generator.feature_id_counter == 0:
        print("\n✗ Error: No features loaded. Please check:")
        print(f"  1. Directory exists: {data_dir}")
        print(f"  2. Directory contains .geojson files")
        print(f"  3. Files are readable")
        sys.exit(1)
    
    generator.generate_tiles(min_zoom=7, max_zoom=18)
    generator.generate_html_viewer()
    
    print(f"\nTo view: cd {output_dir} && python3 -m http.server 8009\n")


if __name__ == '__main__':
    main()