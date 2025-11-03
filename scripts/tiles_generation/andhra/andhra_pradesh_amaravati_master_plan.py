#!/usr/bin/env python3
"""
Amaravati Master Plan - ENHANCED DENSE COMPLETE TILES
Every feature visible at every zoom level - Professional quality
"""

import json
import os
import time
from pathlib import Path
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import shape, box
from rtree import index

class AmaravatiEnhancedTiles:
    def __init__(self, data_dir, output_dir):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.spatial_index = index.Index()
        self.feature_id_counter = 0
        self.feature_lookup = {}
        
    def get_color_map(self):
        """Complete color mapping with all Amaravati zones"""
        return {
            'Burial Ground': {'fill': '#E39E00', 'outline': '#B87E00'},
            'C1 -Mixed use zone': {'fill': '#73B2FF', 'outline': '#5A8FCC'},
            'C2- General commercial zone': {'fill': '#00C5FF', 'outline': '#009ECC'},
            'C3-Neighbourhood centre zone': {'fill': '#00C5FF', 'outline': '#009ECC'},
            'C4-Town centre zone': {'fill': '#00A9E6', 'outline': '#0087B8'},
            'C5-Regional centre zone': {'fill': '#0070FF', 'outline': '#005ACC'},
            'C6-Central business district zone': {'fill': '#005CE6', 'outline': '#004AB8'},
            'Commercial Vacant': {'fill': '#C5E2FF', 'outline': '#9EBFE6'},
            'I1-Business park zone': {'fill': '#FFBEE8', 'outline': '#CC98BA'},
            'I2-Logistics zone': {'fill': '#FF73DF', 'outline': '#CC5CB2'},
            'I3-Non polluting industry zone': {'fill': '#A900E6', 'outline': '#8700B8'},
            'Not Available': {'fill': '#CCCCCC', 'outline': '#999999'},
            'P1-Passive zone': {'fill': '#267300', 'outline': '#1D5C00'},
            'P2-Active zone': {'fill': '#38A800', 'outline': '#2D8600'},
            'P3-Protected zone': {'fill': '#BEE8FF', 'outline': '#98BAE6'},
            'P3-Protected zone Hills': {'fill': '#4C7300', 'outline': '#3D5C00'},
            'PGN-G': {'fill': '#4C7300', 'outline': '#3D5C00'},
            'PGN-V': {'fill': '#897044', 'outline': '#6D5A36'},
            'R1-Village planning zone': {'fill': '#FFFFFF', 'outline': '#CCCCCC'},
            'R3-Medium to high density zone': {'fill': '#F5CA7A', 'outline': '#C4A262'},
            'R4-High density zone': {'fill': '#E69800', 'outline': '#B87A00'},
            'RAA': {'fill': '#FFAA00', 'outline': '#CC8800'},
            'Residential Vacant': {'fill': '#FFD37F', 'outline': '#CCA966'},
            'S2-Education zone': {'fill': '#FF7F7F', 'outline': '#CC6666'},
            'S3-Special zone': {'fill': '#D7B09E', 'outline': '#AC8D7E'},
            'SC1a-Mixed Use': {'fill': '#0070FF', 'outline': '#005ACC'},
            'SC1b - Mixed Use': {'fill': '#73B2FF', 'outline': '#5A8FCC'},
            'SP1- Passive Zone': {'fill': '#267300', 'outline': '#1D5C00'},
            'SP2- Active Zone': {'fill': '#38A800', 'outline': '#2D8600'},
            'SP3-Protected Zone': {'fill': '#00C5FF', 'outline': '#009ECC'},
            'SR2 Low Density Housing': {'fill': '#FFFFBE', 'outline': '#CCCC98'},
            'SR4 - High Density Private': {'fill': '#FFAA00', 'outline': '#CC8800'},
            'SS1 - Government Zone': {'fill': '#E60000', 'outline': '#B80000'},
            'SS2a- Education Zone': {'fill': '#FF7F7F', 'outline': '#CC6666'},
            'SS2b Cultural Zone': {'fill': '#C500FF', 'outline': '#9E00CC'},
            'SS2c Health Zone': {'fill': '#D3FFBE', 'outline': '#A9CC98'},
            'SS3 - Special Zone': {'fill': '#A83800', 'outline': '#862D00'},
            'SU1-Reserve Zone': {'fill': '#E1E1E1', 'outline': '#B4B4B4'},
            'SU2 - Road Network': {'fill': '#82817D', 'outline': '#686764'},
            'U1-Reserve zone': {'fill': '#CCCCCC', 'outline': '#A3A3A3'},
            'U2- Road Reserve Zone': {'fill': '#82817D', 'outline': '#686764'},
            'U2- Road reserve zone': {'fill': '#82817D', 'outline': '#686764'},
        }
    
    def hex_to_rgb(self, hex_color):
        """Convert hex to RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def get_zoom_scale(self, zoom):
        """Get rendering scale based on zoom level for consistency"""
        if zoom <= 10:
            return 6  # Maximum detail at low zoom
        elif zoom <= 13:
            return 5
        elif zoom <= 16:
            return 4
        else:
            return 3  # Still good detail at high zoom
    
    def get_min_feature_size(self, zoom, scale):
        """Minimum feature size in pixels (after scaling)"""
        if zoom <= 10:
            return 4 * scale  # Large at overview
        elif zoom <= 13:
            return 3 * scale
        elif zoom <= 16:
            return 2 * scale
        else:
            return 1.5 * scale
    
    def load_geojson_files(self):
        """Load all GeoJSON with spatial indexing"""
        print("\n" + "="*80)
        print("LOADING GEOJSON DATA - ENHANCED MODE")
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
                        
                        if geom.is_empty:
                            continue
                        
                        props = feature.get('properties', {})
                        feature_zone = props.get('symbology', props.get('plot_categ', zone_name))
                        
                        feature_data = {
                            'geometry': geom,
                            'zone': feature_zone,
                            'properties': props,
                            'area': geom.area  # Store area for size-based rendering
                        }
                        
                        bounds = geom.bounds
                        self.spatial_index.insert(self.feature_id_counter, bounds)
                        self.feature_lookup[self.feature_id_counter] = feature_data
                        self.feature_id_counter += 1
                        loaded += 1
                        
                    except Exception as e:
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
    
    def render_tile_enhanced(self, tile):
        """
        ENHANCED RENDERING: 
        - All features visible at all zooms
        - Zoom-adaptive scaling
        - Smart minimum sizes
        - Outline + fill for visibility
        """
        z, x, y = tile.z, tile.x, tile.y
        
        # Zoom-adaptive scale
        scale = self.get_zoom_scale(z)
        min_size = self.get_min_feature_size(z, scale)
        img_size = self.tile_size * scale
        
        # Render buffer to eliminate seams (5% buffer on each side)
        buffer_ratio = 0.05
        buffer_pixels = int(img_size * buffer_ratio)
        buffered_size = img_size + (2 * buffer_pixels)
        
        img = Image.new('RGBA', (buffered_size, buffered_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        tile_bounds = mercantile.bounds(tile)
        
        # Expand tile bounds by buffer ratio for seamless edges
        width = tile_bounds.east - tile_bounds.west
        height = tile_bounds.north - tile_bounds.south
        buffered_west = tile_bounds.west - (width * buffer_ratio)
        buffered_south = tile_bounds.south - (height * buffer_ratio)
        buffered_east = tile_bounds.east + (width * buffer_ratio)
        buffered_north = tile_bounds.north + (height * buffer_ratio)
        
        tile_bbox = box(buffered_west, buffered_south, buffered_east, buffered_north)
        
        # Get ALL features in buffered tile area
        intersecting_ids = list(self.spatial_index.intersection(tile_bbox.bounds))
        
        if not intersecting_ids:
            return None
        
        color_map = self.get_color_map()
        rendered_count = 0
        
        # Sort by area (larger features first, small on top)
        features_to_render = []
        for feature_id in intersecting_ids:
            feature_data = self.feature_lookup[feature_id]
            if feature_data['geometry'].intersects(tile_bbox):
                features_to_render.append((feature_data['area'], feature_id, feature_data))
        
        features_to_render.sort(key=lambda x: x[0], reverse=True)
        
        # Render ALL features
        for area, feature_id, feature_data in features_to_render:
            geom = feature_data['geometry']
            zone = feature_data['zone']
            
            # Get color with fallback
            color_info = color_map.get(zone, {'fill': '#CCCCCC', 'outline': '#999999'})
            fill_rgb = self.hex_to_rgb(color_info['fill'])
            outline_rgb = self.hex_to_rgb(color_info.get('outline', color_info['fill']))
            
            # Clip to tile
            try:
                clipped_geom = geom.intersection(tile_bbox)
                if clipped_geom.is_empty:
                    continue
                geom = clipped_geom
            except:
                pass
            
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
                    # Convert to pixels using buffered bounds
                    pixel_coords = []
                    for coord in polygon.exterior.coords:
                        lon, lat = coord[0], coord[1]
                        px = (lon - buffered_west) / (buffered_east - buffered_west) * buffered_size
                        py = (buffered_north - lat) / (buffered_north - buffered_south) * buffered_size
                        pixel_coords.append((px, py))
                    
                    if len(pixel_coords) < 3:
                        continue
                    
                    # Calculate feature size
                    xs = [p[0] for p in pixel_coords]
                    ys = [p[1] for p in pixel_coords]
                    width = max(xs) - min(xs)
                    height = max(ys) - min(ys)
                    feature_size = max(width, height)
                    
                    # ENHANCED: Render with outline for visibility
                    if feature_size >= min_size:
                        # Normal size - render with outline
                        draw.polygon(pixel_coords, fill=fill_rgb, outline=outline_rgb, width=max(1, scale//2))
                    else:
                        # Small feature - enlarge around center
                        center_x = sum(xs) / len(xs)
                        center_y = sum(ys) / len(ys)
                        
                        # Scale polygon around center
                        scale_factor = min_size / max(feature_size, 0.1)
                        enlarged_coords = []
                        for px, py in pixel_coords:
                            new_x = center_x + (px - center_x) * scale_factor
                            new_y = center_y + (py - center_y) * scale_factor
                            enlarged_coords.append((new_x, new_y))
                        
                        # Render enlarged
                        draw.polygon(enlarged_coords, fill=fill_rgb, outline=outline_rgb, width=max(1, scale//2))
                        
                        # Add center dot for extra visibility
                        dot_size = min_size // 2
                        draw.ellipse([center_x - dot_size, center_y - dot_size,
                                    center_x + dot_size, center_y + dot_size],
                                   fill=fill_rgb)
                    
                    rendered_count += 1
                    
                except Exception as e:
                    # Fallback: render as dot at centroid
                    try:
                        centroid = polygon.centroid
                        cx = (centroid.x - buffered_west) / (buffered_east - buffered_west) * buffered_size
                        cy = (buffered_north - centroid.y) / (buffered_north - buffered_south) * buffered_size
                        dot_size = min_size // 2
                        draw.ellipse([cx - dot_size, cy - dot_size, cx + dot_size, cy + dot_size],
                                   fill=fill_rgb, outline=outline_rgb)
                        rendered_count += 1
                    except:
                        pass
        
        if rendered_count == 0:
            return None
        
        # Crop to remove buffer and get seamless edges
        img = img.crop((buffer_pixels, buffer_pixels, 
                       buffer_pixels + img_size, buffer_pixels + img_size))
        
        # High-quality downsample to final tile size
        img = img.resize((self.tile_size, self.tile_size), Image.LANCZOS)
        return img
    
    def generate_tiles(self, min_zoom=7, max_zoom=18):
        """Generate enhanced complete tiles"""
        print(f"\n{'='*80}")
        print(f"GENERATING ENHANCED TILES (Zoom {min_zoom}-{max_zoom})")
        print(f"Mode: ALL FEATURES VISIBLE AT ALL ZOOMS")
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
                img = self.render_tile_enhanced(tile)
                
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
        """Generate interactive viewer"""
        bounds = self.get_bounds()
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Amaravati Master Plan - Enhanced Tiles</title>
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
    
    // Base layer
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
      attribution: 'Esri',
      maxZoom: 19
    }}).addTo(map);
    
    // Amaravati tiles
    L.tileLayer('./{{z}}/{{x}}/{{y}}.png', {{
      minZoom: 7,
      maxZoom: 18,
      opacity: 0.9,
      attribution: 'Amaravati Master Plan'
    }}).addTo(map);
    
    // Info box
    const info = L.control({{position: 'topright'}});
    info.onAdd = function() {{
      this._div = L.DomUtil.create('div', 'info');
      this._div.innerHTML = '<b>Amaravati Master Plan</b><br/>All features visible at all zooms<br/>Zoom: ' + map.getZoom();
      return this._div;
    }};
    info.addTo(map);
    
    map.on('zoomend', function() {{
      info._div.innerHTML = '<b>Amaravati Master Plan</b><br/>All features visible at all zooms<br/>Zoom: ' + map.getZoom();
    }});
  </script>
</body>
</html>"""
        
        (self.output_dir / 'index.html').write_text(html)
        print(f"✓ Viewer saved: {self.output_dir}/index.html")


def main():
    import sys
    
    # Try common paths
    possible_paths = [
        Path('data/andhra_pradesh/amaravati/master_plan'),
        Path('/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping/data/andhra_pradesh/amaravati/master_plan'),
    ]
    
    data_dir = None
    for path in possible_paths:
        if path.exists():
            data_dir = path
            break
    
    if data_dir is None:
        print("Enter path to master_plan directory:")
        user_path = input("> ").strip()
        data_dir = Path(user_path)
        if not data_dir.exists():
            print(f"✗ Path not found: {data_dir}")
            sys.exit(1)
    
    output_dir = Path('./amaravati_tiles')
    
    print("="*80)
    print("AMARAVATI MASTER PLAN - ENHANCED TILE GENERATOR")
    print("All features visible at all zoom levels")
    print("="*80)
    print(f"Input:  {data_dir}")
    print(f"Output: {output_dir}")
    
    generator = AmaravatiEnhancedTiles(data_dir, output_dir)
    generator.load_geojson_files()
    
    if generator.feature_id_counter == 0:
        print("✗ No features loaded!")
        sys.exit(1)
    
    generator.generate_tiles(min_zoom=7, max_zoom=18)
    generator.generate_html_viewer()
    
    print(f"\n💡 To view: cd {output_dir} && python3 -m http.server 8010")
    print(f"   Then open: http://localhost:8010/\n")


if __name__ == '__main__':
    main()