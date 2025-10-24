#!/usr/bin/env python3
"""
Amaravati Master Plan - Perfect Tile Generator
Generates map tiles with exact colors for every coordinate
No boundaries between zones - seamless color application
"""

import json
import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import shape, Point, box
from shapely.ops import unary_union
from rtree import index
import math

class AmaravatiPerfectTileGenerator:
    def __init__(self, data_dir, output_dir):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.features_by_zone = {}
        self.spatial_index = index.Index()
        self.feature_id_counter = 0
        self.feature_lookup = {}
        
    def get_perfect_color_map(self):
        """Exact color mapping for all Amaravati zones with special handling for patterns"""
        return {
            # Burial Ground - Dotted pattern with E39E00 dots on FFFFFF
            'Burial Ground': {
                'type': 'dotted',
                'base': '#FFFFFF',
                'dot': '#E39E00',
                'outline': None
            },
            
            # Commercial Zones
            'C1 -Mixed use zone': {'fill': '#73B2FF', 'outline': None},
            'C2- General commercial zone': {'fill': '#00C5FF', 'outline': '#665b5b'},
            'C3-Neighbourhood centre zone': {'fill': '#00C5FF', 'outline': None},
            'C4-Town centre zone': {'fill': '#00A9E6', 'outline': None},
            'C5-Regional centre zone': {'fill': '#0070FF', 'outline': None},
            'C6-Central business district zone': {'fill': '#005CE6', 'outline': None},
            'Commercial Vacant': {'fill': '#C5E2FF', 'outline': None},
            
            # Industrial Zones
            'I1-Business park zone': {'fill': '#FFBEE8', 'outline': None},
            'I2-Logistics zone': {'fill': '#FF73DF', 'outline': None},
            'I3-Non polluting industry zone': {'fill': '#A900E6', 'outline': None},
            
            # Not Available
            'Not Available': {'fill': '#b6b6b6', 'outline': '#000000'},
            
            # Parks/Recreation
            'P1-Passive zone': {'fill': '#267300', 'outline': None},
            'P2-Active zone': {'fill': '#38A800', 'outline': None},
            'P3-Protected zone': {'fill': '#BEE8FF', 'outline': None},
            'P3-Protected zone Hills': {'fill': '#4C7300', 'outline': None},
            
            # PGN Zones
            'PGN-G': {'fill': '#4C7300', 'outline': None},
            'PGN-V': {'fill': '#897044', 'outline': None},
            
            # Residential Zones
            'R1-Village planning zone': {
                'type': 'hatched',
                'base': '#FFFFFF',
                'hatch': '#000000',
                'outline': None
            },
            'R3-Medium to high density zone': {'fill': '#F5CA7A', 'outline': None},
            'R4-High density zone': {'fill': '#E69800', 'outline': None},
            'RAA': {'fill': '#FFAA00', 'outline': None},
            'Residential Vacant': {'fill': '#FFD37F', 'outline': None},
            
            # Special/Services
            'S2-Education zone': {'fill': '#FF7F7F', 'outline': None},
            'S3-Special zone': {'fill': '#D7B09E', 'outline': None},
            
            # Smart City Mixed Use
            'SC1a-Mixed Use': {'fill': '#0070FF', 'outline': None},
            'SC1b - Mixed Use': {'fill': '#73B2FF', 'outline': None},
            
            # Smart City Parks
            'SP1- Passive Zone': {'fill': '#267300', 'outline': None},
            'SP2- Active Zone': {'fill': '#38A800', 'outline': None},
            'SP3-Protected Zone': {'fill': '#00C5FF', 'outline': None},
            
            # Smart City Residential
            'SR2 Low Density Housing': {'fill': '#FFFFBE', 'outline': None},
            'SR4 - High Density Private': {'fill': '#FFAA00', 'outline': None},
            
            # Smart City Services
            'SS1 - Government Zone': {'fill': '#E60000', 'outline': None},
            'SS2a- Education Zone': {'fill': '#FF7F7F', 'outline': None},
            'SS2b Cultural Zone': {'fill': '#C500FF', 'outline': None},
            'SS2c Health Zone': {'fill': '#D3FFBE', 'outline': None},
            'SS3 - Special Zone': {'fill': '#A83800', 'outline': None},
            
            # Smart City Utilities
            'SU1-Reserve Zone': {'fill': '#E1E1E1', 'outline': None},
            'SU2 - Road Network': {'fill': '#FFFFFF', 'outline': '#665b5b'},
            
            # Utilities
            'U1-Reserve zone': {'fill': '#CCCCCC', 'outline': None},
            'U2- Road Reserve Zone': {'fill': '#FFFFFF', 'outline': '#665b5b'},
        }
    
    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def load_geojson_files(self):
        """Load all GeoJSON files and build spatial index"""
        print("Loading GeoJSON files and building spatial index...")
        
        geojson_files = sorted(self.data_dir.glob('*.geojson'))
        total_features = 0
        
        for geojson_file in geojson_files:
            zone_name = geojson_file.stem
            print(f"  Loading: {zone_name}...")
            
            try:
                with open(geojson_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                features = data.get('features', [])
                self.features_by_zone[zone_name] = []
                
                for feature in features:
                    try:
                        geom = shape(feature['geometry'])
                        if not geom.is_valid:
                            geom = geom.buffer(0)
                        
                        # Store feature with zone info
                        feature_data = {
                            'geometry': geom,
                            'zone': zone_name,
                            'properties': feature.get('properties', {})
                        }
                        
                        self.features_by_zone[zone_name].append(feature_data)
                        
                        # Add to spatial index
                        bounds = geom.bounds
                        self.spatial_index.insert(self.feature_id_counter, bounds)
                        self.feature_lookup[self.feature_id_counter] = feature_data
                        self.feature_id_counter += 1
                        
                    except Exception as e:
                        print(f"    Warning: Skipping invalid feature in {zone_name}: {e}")
                        continue
                
                total_features += len(self.features_by_zone[zone_name])
                print(f"    Loaded {len(self.features_by_zone[zone_name])} features")
                
            except Exception as e:
                print(f"    Error loading {zone_name}: {e}")
                continue
        
        print(f"\nTotal features loaded: {total_features:,}")
        print(f"Spatial index built with {self.feature_id_counter:,} entries")
    
    def get_bounds(self):
        """Calculate geographic bounds of all data"""
        min_lon, min_lat = float('inf'), float('inf')
        max_lon, max_lat = float('-inf'), float('-inf')
        
        for zone_features in self.features_by_zone.values():
            for feature_data in zone_features:
                bounds = feature_data['geometry'].bounds
                min_lon = min(min_lon, bounds[0])
                min_lat = min(min_lat, bounds[1])
                max_lon = max(max_lon, bounds[2])
                max_lat = max(max_lat, bounds[3])
        
        return (min_lon, min_lat, max_lon, max_lat)
    
    def draw_dotted_pattern(self, draw, polygon_points, base_color, dot_color, scale=2):
        """Draw dotted pattern for Burial Ground"""
        dot_spacing = 8 * scale  # Spacing between dots
        dot_radius = 2 * scale    # Dot size
        
        # Draw base fill
        draw.polygon(polygon_points, fill=base_color, outline=None)
        
        # Get bounding box
        xs = [p[0] for p in polygon_points]
        ys = [p[1] for p in polygon_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        # Draw dots in grid pattern
        for x in range(int(min_x), int(max_x), dot_spacing):
            for y in range(int(min_y), int(max_y), dot_spacing):
                # Check if point is inside polygon using ray casting
                if self.point_in_polygon((x, y), polygon_points):
                    draw.ellipse([x - dot_radius, y - dot_radius, 
                                 x + dot_radius, y + dot_radius], fill=dot_color)
    
    def point_in_polygon(self, point, polygon):
        """Check if point is inside polygon using ray casting"""
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def draw_hatch_pattern_clipped(self, draw, polygon_points, base_color, hatch_color, scale=2):
        """Draw hatched pattern clipped to polygon boundary"""
        # Draw base fill first
        draw.polygon(polygon_points, fill=base_color, outline=None)
        
        # Get bounding box
        xs = [p[0] for p in polygon_points]
        ys = [p[1] for p in polygon_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        # Create mask for clipping
        mask = Image.new('L', (int(max_x - min_x) + 10, int(max_y - min_y) + 10), 0)
        mask_draw = ImageDraw.Draw(mask)
        
        # Draw polygon on mask
        offset_points = [(x - min_x + 5, y - min_y + 5) for x, y in polygon_points]
        mask_draw.polygon(offset_points, fill=255)
        
        # Draw diagonal hatch lines
        spacing = 6 * scale
        width = int(max_x - min_x)
        height = int(max_y - min_y)
        
        for offset in range(-height, width, spacing):
            # Draw diagonal lines from top-left to bottom-right
            x1, y1 = offset, 0
            x2, y2 = offset + height, height
            
            # Check if line intersects polygon using mask
            for i in range(max(0, -offset), min(width, width - offset)):
                x = int(min_x + i)
                y = int(min_y + i - offset)
                if 0 <= i < mask.width and 0 <= (i - offset) < mask.height:
                    if mask.getpixel((i, i - offset)) > 0:
                        draw.point((x, y), fill=hatch_color)
    
    def render_tile(self, tile):
        """Render a single tile with anti-aliasing"""
        z, x, y = tile.z, tile.x, tile.y
        
        # Use 2x scale for anti-aliasing
        scale = 2
        img_size = self.tile_size * scale
        
        # Create high-resolution image
        img = Image.new('RGBA', (img_size, img_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Get tile bounds in lat/lon
        tile_bounds = mercantile.bounds(tile)
        tile_bbox = box(tile_bounds.west, tile_bounds.south, 
                       tile_bounds.east, tile_bounds.north)
        
        # Query spatial index for features that might intersect this tile
        intersecting_ids = list(self.spatial_index.intersection(tile_bbox.bounds))
        
        if not intersecting_ids:
            return None  # Empty tile
        
        # Get color map
        color_map = self.get_perfect_color_map()
        
        # Collect features by zone for rendering order
        features_to_render = []
        for feature_id in intersecting_ids:
            feature_data = self.feature_lookup[feature_id]
            if feature_data['geometry'].intersects(tile_bbox):
                features_to_render.append(feature_data)
        
        if not features_to_render:
            return None
        
        # Render features (no particular order needed - seamless boundaries)
        for feature_data in features_to_render:
            geom = feature_data['geometry']
            zone = feature_data['zone']
            
            if zone not in color_map:
                continue
            
            color_info = color_map[zone]
            
            # Convert geometry coordinates to pixel coordinates
            if geom.geom_type == 'Polygon':
                polygons = [geom]
            elif geom.geom_type == 'MultiPolygon':
                polygons = list(geom.geoms)
            else:
                continue
            
            for polygon in polygons:
                # Convert exterior coordinates to pixels
                pixel_coords = []
                for lon, lat in polygon.exterior.coords:
                    # Convert lat/lon to pixel coordinates
                    px = (lon - tile_bounds.west) / (tile_bounds.east - tile_bounds.west) * img_size
                    py = (tile_bounds.north - lat) / (tile_bounds.north - tile_bounds.south) * img_size
                    pixel_coords.append((px, py))
                
                if len(pixel_coords) < 3:
                    continue
                
                # Handle special patterns
                if color_info.get('type') == 'dotted':
                    # Dotted pattern (Burial Ground)
                    base_rgb = self.hex_to_rgb(color_info['base'])
                    dot_rgb = self.hex_to_rgb(color_info['dot'])
                    self.draw_dotted_pattern(draw, pixel_coords, base_rgb, dot_rgb, scale)
                
                elif color_info.get('type') == 'hatched':
                    # Hatched pattern (R1)
                    base_rgb = self.hex_to_rgb(color_info['base'])
                    hatch_rgb = self.hex_to_rgb(color_info['hatch'])
                    self.draw_hatch_pattern_clipped(draw, pixel_coords, base_rgb, hatch_rgb, scale)
                
                else:
                    # Solid fill
                    fill_color = self.hex_to_rgb(color_info['fill'])
                    outline_color = self.hex_to_rgb(color_info['outline']) if color_info.get('outline') else None
                    
                    # Draw polygon with NO outline to ensure seamless boundaries
                    draw.polygon(pixel_coords, fill=fill_color, outline=None)
                    
                    # Only draw outline if explicitly specified AND it's different from fill
                    if outline_color and outline_color != fill_color:
                        draw.polygon(pixel_coords, outline=outline_color, width=scale)
        
        # Downsample for anti-aliasing
        img = img.resize((self.tile_size, self.tile_size), Image.LANCZOS)
        
        return img
    
    def generate_tiles(self, min_zoom=0, max_zoom=18):
        """Generate tiles for specified zoom levels"""
        print(f"\nGenerating tiles (zoom {min_zoom}-{max_zoom})...")
        
        # Get data bounds
        bounds = self.get_bounds()
        print(f"Data bounds: {bounds}")
        
        total_tiles = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            print(f"\n  Zoom level {zoom}:")
            
            # Get tiles that cover the bounds
            tiles = list(mercantile.tiles(
                bounds[0], bounds[1], bounds[2], bounds[3], 
                zooms=[zoom]
            ))
            
            zoom_dir = self.output_dir / str(zoom)
            tiles_rendered = 0
            
            for tile in tiles:
                img = self.render_tile(tile)
                
                if img is not None:
                    # Save tile
                    tile_dir = zoom_dir / str(tile.x)
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    
                    tile_path = tile_dir / f"{tile.y}.png"
                    img.save(tile_path, 'PNG', optimize=True)
                    tiles_rendered += 1
            
            print(f"    Generated {tiles_rendered} tiles")
            total_tiles += tiles_rendered
        
        print(f"\n✓ Total tiles generated: {total_tiles:,}")
    
    def generate_html_viewer(self, mapbox_token=None):
        """Generate simple HTML viewer"""
        bounds = self.get_bounds()
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
  <title>Amaravati Master Plan</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    body, html, #map {{ margin: 0; padding: 0; height: 100%; width: 100%; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const map = L.map('map').setView([{center_lat}, {center_lon}], 12);
    
    // Add satellite base layer
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
      attribution: '© Esri, Maxar, GeoEye, Earthstar Geographics',
      maxZoom: 19
    }}).addTo(map);
    
    // Add Amaravati tiles
    L.tileLayer('./{{z}}/{{x}}/{{y}}.png', {{
      minZoom: 0,
      maxZoom: 18,
      opacity: 0.8
    }}).addTo(map);
    
    map.fitBounds([[{bounds[1]}, {bounds[0]}], [{bounds[3]}, {bounds[2]}]]);
  </script>
</body>
</html>"""
        
        html_path = self.output_dir / 'index.html'
        with open(html_path, 'w') as f:
            f.write(html_content)
        
        print(f"\n✓ HTML viewer created: {html_path}")


def main():
    # Configuration
    data_dir = Path('data/andhra_pradesh/amaravati/master_plan')
    output_dir = Path('amaravati_tiles')
    
    print("="*80)
    print("AMARAVATI MASTER PLAN - PERFECT TILE GENERATOR")
    print("="*80)
    
    # Create generator
    generator = AmaravatiPerfectTileGenerator(data_dir, output_dir)
    
    # Load data
    generator.load_geojson_files()
    
    # Generate tiles
    generator.generate_tiles(min_zoom=0, max_zoom=18)
    
    # Create HTML viewer
    generator.generate_html_viewer()
    
    print("\n" + "="*80)
    print("TILE GENERATION COMPLETE!")
    print("="*80)
    print(f"\nOutput directory: {output_dir.absolute()}")
    print(f"\nTo view:")
    print(f"  cd {output_dir}")
    print(f"  python3 -m http.server 8007")
    print(f"  Open: http://localhost:8007/")
    print()


if __name__ == '__main__':
    main()

