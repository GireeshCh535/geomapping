#!/usr/bin/env python3
"""
Universal Heritage Sites Tile Generator
Generates tiles for heritage sites with protected/prohibited/regulated zones
Colors are read directly from GeoJSON properties (fill, stroke)
"""

import json
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw
import mercantile
from shapely.geometry import shape, box, Polygon, MultiPolygon
from shapely.ops import transform
from rtree import index

try:
    from pyproj import Transformer, CRS
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False


class UniversalHeritageTileGenerator:
    def __init__(self, geojson_file, output_dir, site_name):
        """
        Initialize heritage site tile generator
        
        Args:
            geojson_file: Path to heritage site GeoJSON file
            output_dir: Output directory for tiles
            site_name: Name of the heritage site (for display)
        """
        self.geojson_file = Path(geojson_file)
        self.output_dir = Path(output_dir)
        self.site_name = site_name
        self.tile_size = 256
        self.spatial_index = index.Index()
        self.feature_id_counter = 0
        self.feature_lookup = {}
        self.source_crs = None
        self.needs_transform = False
        self.transformer = None
        
        # Standard heritage zone colors
        self.zone_colors = {
            'protected': {'fill': '#E52323', 'outline': '#E52323'},
            'prohibited': {'fill': '#FFFF2B', 'outline': '#FFFF2B'},
            'regulated': {'fill': '#36FF36', 'outline': '#36FF36'}
        }
        
        # Pre-compute RGB values
        self._init_color_cache()
    
    def _init_color_cache(self):
        """Pre-compute RGB values for all zone colors"""
        self._color_cache = {}
        for zone, colors in self.zone_colors.items():
            self._color_cache[zone] = {
                'fill': self.hex_to_rgb(colors['fill']),
                'outline': self.hex_to_rgb(colors['outline'])
            }
    
    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def detect_crs(self, first_feature):
        """Detect CRS from GeoJSON and set up transformation if needed"""
        if not HAS_PYPROJ:
            self.needs_transform = False
            return
        
        try:
            coords = first_feature['geometry']['coordinates']
            if first_feature['geometry']['type'] == 'MultiPolygon':
                first_coord = coords[0][0][0]
            elif first_feature['geometry']['type'] == 'Polygon':
                first_coord = coords[0][0]
            else:
                self.needs_transform = False
                return
            
            lon, lat = first_coord[0], first_coord[1]
            
            # Check if coordinates are in Web Mercator (EPSG:3857)
            if abs(lon) > 180 or abs(lat) > 90:
                print(f"🔄 Detected projected coordinates (likely EPSG:3857)")
                self.source_crs = CRS.from_epsg(3857)
                self.needs_transform = True
                self.transformer = Transformer.from_crs(
                    self.source_crs, 
                    CRS.from_epsg(4326),
                    always_xy=True
                )
            else:
                self.needs_transform = False
                
        except Exception as e:
            print(f"⚠️  Could not detect CRS: {e}")
            self.needs_transform = False
    
    def transform_geometry(self, geom):
        """Transform geometry from source CRS to WGS84 if needed"""
        if not self.needs_transform or not self.transformer:
            return geom
        return transform(self.transformer.transform, geom)
    
    def load_geojson(self):
        """Load heritage site GeoJSON file or merge all .geojson files in a directory"""
        print(f"\n{'='*80}")
        print(f"LOADING HERITAGE SITE: {self.site_name}")
        print(f"{'='*80}")
        
        if self.geojson_file.is_dir():
            files = sorted(self.geojson_file.glob("*.geojson"))
            if not files:
                raise FileNotFoundError(f"No GeoJSON files found in directory: {self.geojson_file}")
            print(f"Directory: {self.geojson_file} ({len(files)} files)")
            features = []
            for fpath in files:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    feats = data.get('features', [])
                    features.extend(feats)
            print(f"Found {len(features)} features (merged from directory)")
        else:
            print(f"File: {self.geojson_file.name}\n")
            if not self.geojson_file.exists():
                raise FileNotFoundError(f"GeoJSON file not found: {self.geojson_file}")
            with open(self.geojson_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            features = data.get('features', [])
            print(f"Found {len(features)} features")
        
        # Detect CRS from first feature
        if features:
            self.detect_crs(features[0])
        
        # Load features
        zone_counts = {'protected': 0, 'prohibited': 0, 'regulated': 0, 'other': 0}
        
        for feature in features:
            try:
                geom = shape(feature['geometry'])
                
                # Transform if needed
                geom = self.transform_geometry(geom)
                
                if geom is None or geom.is_empty:
                    continue
                
                props = feature.get('properties', {})
                boundary_type = props.get('boundary_type', 'unknown').lower()
                
                # Get colors from properties (fallback to standard colors)
                fill_color = props.get('fill', self.zone_colors.get(boundary_type, {}).get('fill', '#CCCCCC'))
                stroke_color = props.get('stroke', self.zone_colors.get(boundary_type, {}).get('outline', '#000000'))
                
                feature_data = {
                    'geometry': geom,
                    'boundary_type': boundary_type,
                    'fill_color': fill_color,
                    'stroke_color': stroke_color,
                    'properties': props,
                    'area': geom.area
                }
                
                bounds = geom.bounds
                self.spatial_index.insert(self.feature_id_counter, bounds)
                self.feature_lookup[self.feature_id_counter] = feature_data
                self.feature_id_counter += 1
                
                # Count zone types
                if boundary_type in zone_counts:
                    zone_counts[boundary_type] += 1
                else:
                    zone_counts['other'] += 1
                
            except Exception as e:
                print(f"⚠️  Error loading feature: {e}")
                continue
        
        print(f"\n✓ Loaded {self.feature_id_counter} features:")
        print(f"  - Protected:  {zone_counts['protected']}")
        print(f"  - Prohibited: {zone_counts['prohibited']}")
        print(f"  - Regulated:  {zone_counts['regulated']}")
        if zone_counts['other'] > 0:
            print(f"  - Other:      {zone_counts['other']}")
    
    def get_bounds(self):
        """Get geographic bounds of all features"""
        min_lon, min_lat = float('inf'), float('inf')
        max_lon, max_lat = float('-inf'), float('-inf')
        
        for feature_data in self.feature_lookup.values():
            bounds = feature_data['geometry'].bounds
            min_lon = min(min_lon, bounds[0])
            min_lat = min(min_lat, bounds[1])
            max_lon = max(max_lon, bounds[2])
            max_lat = max(max_lat, bounds[3])
        
        return (min_lon, min_lat, max_lon, max_lat)
    
    def get_zoom_scale(self, zoom):
        """Get rendering scale based on zoom level"""
        if zoom <= 10:
            return 6
        elif zoom <= 13:
            return 5
        elif zoom <= 15:
            return 4
        else:
            return 3
    
    def get_min_feature_size(self, zoom, scale):
        """Get minimum feature size in pixels for filtering"""
        base_sizes = {
            7: 24, 8: 24, 9: 24, 10: 24,
            11: 15, 12: 15, 13: 15,
            14: 8, 15: 8, 16: 8,
            17: 4.5, 18: 4.5
        }
        return base_sizes.get(zoom, 4)
    
    def render_polygon_with_holes(self, draw, polygon, tile_bounds, img_size, buffer_pixels,
                                  buffered_size, fill_rgb, outline_rgb, boundary_type):
        """Render polygon with interior rings (holes) properly - mirrors monument rendering"""
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
        
        fill_rgba = fill_rgb + (180,) if fill_rgb else None  # 70% opacity to match monument tiles
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
    
    def render_tile_seamless(self, tile):
        """Render a single tile with seamless boundaries - match monument renderer"""
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
        
        # Render order: regulated (largest) -> prohibited -> protected (smallest on top)
        ordered_features = []
        for feature_id in candidate_ids:
            feature_data = self.feature_lookup[feature_id]
            geom = feature_data['geometry']
            
            if not geom.intersects(buffered_bounds):
                continue
            
            order = {'regulated': 3, 'prohibited': 2, 'protected': 1}.get(feature_data['boundary_type'], 0)
            ordered_features.append((order, feature_id, feature_data))
        
        if not ordered_features:
            return None
        
        ordered_features.sort(key=lambda x: x[0], reverse=True)
        
        scale = 4  # fixed to match monument renderer
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
        
        img = img_buffered.crop((buffer_pixels, buffer_pixels,
                                buffered_size - buffer_pixels,
                                buffered_size - buffer_pixels))
        
        img = img.resize((self.tile_size, self.tile_size), Image.LANCZOS)
        
        return img
    
    def generate_tiles(self, min_zoom=7, max_zoom=18):
        """Generate seamless tiles for all zoom levels"""
        print(f"\n{'='*80}")
        print(f"GENERATING TILES (Zoom {min_zoom}-{max_zoom})")
        print(f"Mode: SEAMLESS - NO TILE BOUNDARIES")
        print(f"{'='*80}")
        
        bounds = self.get_bounds()
        print(f"Bounds: [{bounds[1]:.4f}, {bounds[0]:.4f}] to [{bounds[3]:.4f}, {bounds[2]:.4f}]\n")
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        total_tiles = 0
        overall_start = time.time()
        
        for zoom in range(min_zoom, max_zoom + 1):
            zoom_start = time.time()
            
            tiles = list(mercantile.tiles(
                bounds[0], bounds[1], bounds[2], bounds[3],
                zooms=[zoom]
            ))
            
            total_for_zoom = len(tiles)
            
            print(f"Zoom {zoom:2d} | {total_for_zoom:,} tiles | Scale: 4x | Min: 0.0px",
                  end=" ", flush=True)
            
            zoom_dir = self.output_dir / str(zoom)
            rendered = 0
            
            for tile in tiles:
                img = self.render_tile_seamless(tile)
                
                if img is not None:
                    tile_dir = zoom_dir / str(tile.x)
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    
                    tile_path = tile_dir / f"{tile.y}.png"
                    img.save(tile_path, 'PNG', optimize=False)
                    rendered += 1
            
            zoom_elapsed = time.time() - zoom_start
            speed = rendered / zoom_elapsed if zoom_elapsed > 0 else 0
            print(f"| ✓ {rendered:,} in {zoom_elapsed:.1f}s ({speed:.1f} t/s)")
            
            total_tiles += rendered
        
        overall_elapsed = time.time() - overall_start
        print(f"\n{'='*80}")
        print(f"✓ COMPLETE: {total_tiles:,} tiles in {overall_elapsed:.1f}s")
        print(f"{'='*80}\n")
        
        return total_tiles
    
    def generate_html_viewer(self):
        """Generate HTML viewer for the tiles"""
        bounds = self.get_bounds()
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{self.site_name} - Heritage Zones</title>
    <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no">
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet">
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
        .legend {{
            position: absolute;
            bottom: 30px;
            right: 10px;
            background: white;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            font-family: Arial, sans-serif;
        }}
        .legend h4 {{ margin: 0 0 10px 0; font-size: 14px; }}
        .legend-item {{ display: flex; align-items: center; margin: 5px 0; font-size: 12px; }}
        .legend-color {{ width: 20px; height: 20px; margin-right: 8px; border: 1px solid #333; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="legend">
        <h4>{self.site_name}</h4>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #E52323;"></div>
            <span>Protected</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #FFFF2B;"></div>
            <span>Prohibited</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: #36FF36;"></div>
            <span>Regulated</span>
        </div>
    </div>
    <script>
        mapboxgl.accessToken = 'pk.eyJ1IjoiYXYxYWNyZSIsImEiOiJjbTJtZmdxN3owa2FzMmpyMjJ4OHV5MHhzIn0.FXpMd91JSER-r7LVpSZN-A';
        const map = new mapboxgl.Map({{
            container: 'map',
            style: 'mapbox://styles/mapbox/satellite-streets-v12',
            center: [{center_lon}, {center_lat}],
            zoom: 14
        }});
        
        map.on('load', () => {{
            map.addSource('heritage-tiles', {{
                type: 'raster',
                tiles: ['http://localhost:8000/{{z}}/{{x}}/{{y}}.png'],
                tileSize: 256,
                minzoom: 7,
                maxzoom: 18
            }});
            
            map.addLayer({{
                id: 'heritage-tiles',
                type: 'raster',
                source: 'heritage-tiles',
                paint: {{ 'raster-opacity': 0.8 }}
            }});
        }});
        
        map.addControl(new mapboxgl.NavigationControl());
    </script>
</body>
</html>"""
        
        viewer_path = self.output_dir / 'index.html'
        viewer_path.write_text(html, encoding='utf-8')
        print(f"✓ Viewer saved: {viewer_path}\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python universal_heritage_tile_generator.py <geojson_file_or_directory> [site_name]")
        print("\nExample:")
        print('  python universal_heritage_tile_generator.py \\')
        print('    "heritage_sites/bengaluru" \\')
        print('    "Bengaluru Heritage Sites"')
        sys.exit(1)
    
    geojson_file = sys.argv[1]
    geo_path = Path(geojson_file)
    site_name = sys.argv[2] if len(sys.argv) > 2 else geo_path.stem.replace('_', ' ')
    
    # Force output under heritage_tiles_updated/<city>/<site_slug>
    parts_lower = [p.lower() for p in geo_path.parts]
    if any("bengaluru" in p or "bangalore" in p for p in parts_lower):
        city_folder = "bengaluru"
    elif any("hyderabad" in p for p in parts_lower):
        city_folder = "hyderabad"
    else:
        city_folder = "misc"
    site_slug = geo_path.stem.lower().replace(' ', '_')
    output_dir = Path("heritage_tiles_updated") / city_folder / site_slug
    
    try:
        generator = UniversalHeritageTileGenerator(geojson_file, output_dir, site_name)
        generator.load_geojson()
        
        if generator.feature_id_counter == 0:
            print("✗ No features loaded!")
            sys.exit(1)
        
        generator.generate_tiles(min_zoom=7, max_zoom=18)
        generator.generate_html_viewer()
        
        print(f"💡 To view tiles:")
        print(f"   cd {output_dir} && python3 -m http.server 8000")
        print(f"   Then open: http://localhost:8000/\n")
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

