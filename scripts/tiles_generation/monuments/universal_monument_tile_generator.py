#!/usr/bin/env python3
"""
Universal Monument Tile Generator
Generates tiles for monument boundaries (Protected, Prohibited, Regulated zones)
Colors are read from GeoJSON properties (fill/stroke fields)
"""

import json
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import shape, box, Point, Polygon
from rtree import index


class MonumentTileGenerator:
    def __init__(self, data_dir, output_dir, monument_name):
        """
        Initialize Monument Tile Generator
        
        Args:
            data_dir: Directory containing combined_boundaries.geojson
            output_dir: Output directory for tiles
            monument_name: Name of the monument for display
        """
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.monument_name = monument_name
        self.tile_size = 256
        self.spatial_index = index.Index()
        self.feature_id_counter = 0
        self.feature_lookup = {}
    
    def hex_to_rgb(self, hex_color):
        """Convert hex to RGB"""
        if hex_color is None:
            return None
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def load_geojson(self):
        """Load monument boundaries GeoJSON"""
        geojson_file = self.data_dir / 'combined_boundaries.geojson'
        
        if not geojson_file.exists():
            print(f"✗ File not found: {geojson_file}")
            return False
        
        print(f"📖 Loading: {geojson_file}")
        
        try:
            with open(geojson_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            features = data.get('features', [])
            
            for feature in features:
                try:
                    geom = shape(feature['geometry'])
                    
                    if not geom.is_valid:
                        geom = geom.buffer(0)
                    
                    if geom.is_empty:
                        continue
                    
                    props = feature.get('properties', {})
                    
                    # Extract colors from properties
                    fill_color = props.get('fill', props.get('fill-color', '#E52323'))
                    stroke_color = props.get('stroke', props.get('stroke-color', '#000000'))
                    boundary_type = props.get('boundary_type', 'unknown')
                    
                    feature_data = {
                        'geometry': geom,
                        'fill_color': fill_color,
                        'stroke_color': stroke_color,
                        'boundary_type': boundary_type,
                        'properties': props,
                        'area': geom.area
                    }
                    
                    bounds = geom.bounds
                    self.spatial_index.insert(self.feature_id_counter, bounds)
                    self.feature_lookup[self.feature_id_counter] = feature_data
                    self.feature_id_counter += 1
                    
                except Exception as e:
                    continue
            
            print(f"✓ Loaded: {self.feature_id_counter} features")
            
            # Show boundary types
            boundary_types = {}
            for feat_data in self.feature_lookup.values():
                bt = feat_data['boundary_type']
                if bt not in boundary_types:
                    boundary_types[bt] = {
                        'count': 0,
                        'fill': feat_data['fill_color'],
                        'stroke': feat_data['stroke_color']
                    }
                boundary_types[bt]['count'] += 1
            
            print(f"\nBoundary Types:")
            for bt, info in boundary_types.items():
                print(f"  • {bt.title():<15} - {info['count']} features (Fill: {info['fill']}, Stroke: {info['stroke']})")
            
            return True
            
        except Exception as e:
            print(f"✗ Error loading GeoJSON: {e}")
            return False
    
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
        """Create patterns: hatch, dots - clipped to polygon boundary"""
        # Draw base fill first
        if base:
            draw.polygon(poly, fill=base)
        
        if len(poly) < 3:
            return
        
        xs, ys = zip(*poly)
        min_x, max_x = int(min(xs)), int(max(xs))
        min_y, max_y = int(min(ys)), int(max(ys))
        
        # Create polygon shape for clipping
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
                                  buffered_size, fill_rgb, outline_rgb, boundary_type):
        """Render polygon with interior rings (holes) properly"""
        lon_range = tile_bounds.east - tile_bounds.west
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
        
        # Semi-transparent fill for monument zones
        fill_rgba = fill_rgb + (180,) if fill_rgb else None
        outline_rgba = outline_rgb + (255,) if outline_rgb else (0, 0, 0, 255)
        
        if fill_rgba:
            poly_draw.polygon(exterior_pixels, fill=fill_rgba)
        
        if len(exterior_pixels) > 1:
            closed_pixels = exterior_pixels + [exterior_pixels[0]]
            poly_draw.line(closed_pixels, fill=outline_rgba, width=2)
        
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
                    poly_draw.line(closed_interior, fill=outline_rgba, width=2)
        
        return poly_img
    
    def render_tile(self, tile):
        """Render a single tile with seamless boundaries"""
        tile_bounds = mercantile.bounds(tile)
        buffer_degrees = 0.01
        buffered_bounds = box(
            tile_bounds.west - buffer_degrees,
            tile_bounds.south - buffer_degrees,
            tile_bounds.east + buffer_degrees,
            tile_bounds.north + buffer_degrees
        )
        
        candidate_ids = list(self.spatial_index.intersection(buffered_bounds.bounds))
        
        if not candidate_ids:
            return None
        
        # Render order: regulated (largest) -> prohibited -> protected (smallest, on top)
        ordered_features = []
        for feature_id in candidate_ids:
            feature_data = self.feature_lookup[feature_id]
            geom = feature_data['geometry']
            
            if not geom.intersects(buffered_bounds):
                continue
            
            # Render order: regulated (3), prohibited (2), protected (1)
            order = {'regulated': 3, 'prohibited': 2, 'protected': 1}.get(feature_data['boundary_type'], 0)
            ordered_features.append((order, feature_id, feature_data))
        
        if not ordered_features:
            return None
        
        # Sort by order (largest zones first)
        ordered_features.sort(key=lambda x: x[0], reverse=True)
        
        scale = 4  # Use 4x scale for better quality
        img_size = self.tile_size * scale
        buffer_pixels = int(img_size * 0.1)
        buffered_size = img_size + (2 * buffer_pixels)
        
        img_buffered = Image.new('RGBA', (buffered_size, buffered_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img_buffered)
        
        for order, feature_id, feature_data in ordered_features:
            geom = feature_data['geometry']
            fill_rgb = self.hex_to_rgb(feature_data['fill_color'])
            stroke_rgb = self.hex_to_rgb(feature_data['stroke_color'])
            boundary_type = feature_data['boundary_type']
            
            if isinstance(geom, Polygon):
                if geom.area < 1e-10:
                    continue
                
                poly_img = self.render_polygon_with_holes(
                    draw, geom, tile_bounds, img_size, buffer_pixels,
                    buffered_size, fill_rgb, stroke_rgb, boundary_type
                )
                
                if poly_img:
                    img_buffered = Image.alpha_composite(img_buffered, poly_img)
            
            elif hasattr(geom, 'geoms'):
                for poly in geom.geoms:
                    if poly.area < 1e-10:
                        continue
                    
                    poly_img = self.render_polygon_with_holes(
                        draw, poly, tile_bounds, img_size, buffer_pixels,
                        buffered_size, fill_rgb, stroke_rgb, boundary_type
                    )
                    
                    if poly_img:
                        img_buffered = Image.alpha_composite(img_buffered, poly_img)
        
        # Crop and downsample
        img = img_buffered.crop((buffer_pixels, buffer_pixels, 
                                buffered_size - buffer_pixels, 
                                buffered_size - buffer_pixels))
        
        img = img.resize((self.tile_size, self.tile_size), Image.LANCZOS)
        return img
    
    def generate_tiles(self, min_zoom=9, max_zoom=18):
        """Generate tiles for monument"""
        print(f"\n{'='*80}")
        print(f"GENERATING MONUMENT TILES (Zoom {min_zoom}-{max_zoom})")
        print(f"Monument: {self.monument_name}")
        print(f"{'='*80}")
        
        bounds = self.get_bounds()
        print(f"Bounds: [{bounds[1]:.6f}, {bounds[0]:.6f}] to [{bounds[3]:.6f}, {bounds[2]:.6f}]\n")
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        total_tiles = 0
        overall_start = time.time()
        
        for zoom in range(min_zoom, max_zoom + 1):
            zoom_start = time.time()
            
            tiles = list(mercantile.tiles(
                bounds[0], bounds[1], bounds[2], bounds[3], 
                zooms=[zoom]
            ))
            
            print(f"Zoom {zoom:2d} | {len(tiles):>5} tiles", end=" ", flush=True)
            
            zoom_dir = self.output_dir / str(zoom)
            rendered = 0
            
            for tile in tiles:
                img = self.render_tile(tile)
                
                if img is not None:
                    tile_dir = zoom_dir / str(tile.x)
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    
                    tile_path = tile_dir / f"{tile.y}.png"
                    img.save(tile_path, 'PNG', optimize=False)
                    rendered += 1
            
            zoom_elapsed = time.time() - zoom_start
            speed = rendered / zoom_elapsed if zoom_elapsed > 0 else 0
            print(f"| ✓ {rendered:>5} in {zoom_elapsed:.1f}s ({speed:.1f} t/s)")
            
            total_tiles += rendered
        
        overall_elapsed = time.time() - overall_start
        print(f"\n{'='*80}")
        print(f"✓ COMPLETE: {total_tiles:,} tiles in {overall_elapsed:.1f}s")
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
  <title>{self.monument_name} - Protected Area</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    body, html, #map {{ margin:0; padding:0; height:100%; }}
    .info {{ padding: 10px; background: white; border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.2); }}
    .legend {{ line-height: 18px; color: #555; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.2); }}
    .legend i {{ width: 18px; height: 18px; float: left; margin-right: 8px; opacity: 0.7; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const map = L.map('map').setView([{center_lat:.6f}, {center_lon:.6f}], 15);
    
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
      attribution: 'Esri',
      maxZoom: 19
    }}).addTo(map);
    
    L.tileLayer('./{{z}}/{{x}}/{{y}}.png', {{
      minZoom: 9,
      maxZoom: 18,
      opacity: 0.8,
      attribution: '{self.monument_name}'
    }}).addTo(map);
    
    const info = L.control({{position: 'topright'}});
    info.onAdd = function() {{
      this._div = L.DomUtil.create('div', 'info');
      this._div.innerHTML = '<b>{self.monument_name}</b><br/>Protected Monument Area<br/>Zoom: ' + map.getZoom();
      return this._div;
    }};
    info.addTo(map);
    
    const legend = L.control({{position: 'bottomright'}});
    legend.onAdd = function() {{
      this._div = L.DomUtil.create('div', 'legend');
      this._div.innerHTML = '<b>Monument Zones</b><br/>' +
        '<i style="background:#E52323"></i> Protected<br/>' +
        '<i style="background:#FFFF2B"></i> Prohibited (100m)<br/>' +
        '<i style="background:#36FF36"></i> Regulated (300m)';
      return this._div;
    }};
    legend.addTo(map);
    
    map.on('zoomend', function() {{
      info._div.innerHTML = '<b>{self.monument_name}</b><br/>Protected Monument Area<br/>Zoom: ' + map.getZoom();
    }});
  </script>
</body>
</html>"""
        
        (self.output_dir / 'index.html').write_text(html)
        print(f"✓ Viewer saved: {self.output_dir}/index.html")


def main():
    if len(sys.argv) < 2:
        print("="*80)
        print("UNIVERSAL MONUMENT TILE GENERATOR")
        print("="*80)
        print("\nUsage:")
        print(f"  python {sys.argv[0]} <monument_directory> [output_directory] [monument_name]")
        print("\nExample:")
        print(f"  python {sys.argv[0]} \\")
        print(f"    monument_data_set1/Karnataka/Bangalore\\ Circle/Bangalore/Fort \\")
        print(f"    monument_tiles/bangalore_fort \\")
        print(f"    'Bangalore Fort'")
        print("\nRequired:")
        print("  - combined_boundaries.geojson in monument directory")
        print("\nBoundary Types:")
        print("  • Protected (Red #E52323) - Monument itself")
        print("  • Prohibited (Yellow #FFFF2B) - 100m buffer, NMA NOC required")
        print("  • Regulated (Green #36FF36) - 300m buffer, State NOC required")
        print("="*80)
        sys.exit(1)
    
    data_dir = Path(sys.argv[1])
    
    # Default output and name from directory
    if len(sys.argv) > 2:
        output_dir = Path(sys.argv[2])
    else:
        monument_name_clean = data_dir.name.lower().replace(' ', '_').replace('&', 'and')
        output_dir = Path(f"monument_tiles/{monument_name_clean}")
    
    monument_name = sys.argv[3] if len(sys.argv) > 3 else data_dir.name
    
    if not data_dir.exists():
        print(f"✗ Monument directory not found: {data_dir}")
        sys.exit(1)
    
    print("="*80)
    print("MONUMENT TILE GENERATOR")
    print("="*80)
    print(f"Monument: {monument_name}")
    print(f"Input:    {data_dir}")
    print(f"Output:   {output_dir}")
    print("="*80)
    
    generator = MonumentTileGenerator(data_dir, output_dir, monument_name)
    
    if not generator.load_geojson():
        sys.exit(1)
    
    if generator.feature_id_counter == 0:
        print("✗ No features loaded!")
        sys.exit(1)
    
    generator.generate_tiles(min_zoom=9, max_zoom=18)
    generator.generate_html_viewer()
    
    print(f"\n💡 To view: cd {output_dir} && python3 -m http.server 8020")
    print(f"   Then open: http://localhost:8020/\n")


if __name__ == '__main__':
    main()

