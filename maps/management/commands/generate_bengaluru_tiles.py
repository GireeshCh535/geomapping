# maps/management/commands/generate_bengaluru_tiles.py
"""
Generate tiles for Bengaluru with correct layer grouping
"""

from django.core.management.base import BaseCommand
from django.contrib.gis.db.models import Extent
from maps.models import City, DataLayer, State, GeoFeature
from maps.s3_direct_tile_service import S3DirectTileGenerationService
from maps.services import VectorTileService
from maps.tile_rendering_service import TileRenderingService
import mercantile

class Command(BaseCommand):
    help = 'Generate tiles for Bengaluru with correct layer grouping'
    
    def add_arguments(self, parser):
        parser.add_argument('--groups', nargs='+', default=['master-plan'], 
                          choices=['master-plan', 'highways', 'metro', 'strr', 'workspace'])
        parser.add_argument('--type', nargs='+', default=['png'], choices=['png', 'mvt'])
        parser.add_argument('--min-zoom', type=int, default=8)
        parser.add_argument('--max-zoom', type=int, default=14)
        parser.add_argument('--test', action='store_true', help='Test mode - generate only few tiles')
        
    def handle(self, *args, **options):
        groups = options['groups']
        tile_types = options['type']
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        test_mode = options['test']
        
        # Get Bengaluru city
        city = City.objects.filter(name__icontains='bangalore').first()
        if not city:
            self.stdout.write(self.style.ERROR('City not found'))
            return
        
        state = city.state_ref or State.objects.filter(name='Karnataka').first()
        
        self.stdout.write(self.style.SUCCESS(f'🏙️  City: {city.name}'))
        self.stdout.write(f'📍 State: {state.name if state else "Unknown"}')
        
        # Define layer groups with actual layer slugs
        LAYER_GROUPS = {
            'master-plan': {
                'name': 'Master Plan 2015',
                'layers': [
                    'commercial_business', 'residential_mixed', 'residential_main',
                    'commercial_central', 'industrial', 'hightech',
                    'public_semipublic', 'defense', 'stateforest_valley_protectedland',
                    'parks_greenspaces_sports_playgrounds_cemetery_burialgrounds',
                    'lake_tank', 'road_rail_airport_transport',
                    'power_water_garbagefacility_treatmentplant', 'agricultural_land',
                    'unclassified_use', 'drains'
                ],
                'use_individual_colors': True
            },
            'highways': {
                'name': 'Highways',
                'layers': [
                    'bellaryroad_nh44', 'bengaluruchennaiexpressway_ne7',
                    'bengalurumysururoad_nh275', 'hosurroad_nh48',
                    'kanakpuraroad_nh948', 'madrasroad_nh75',
                    'nice_road', 'tumakururoad_nh48'
                ],
                'color': '#14e098'
            },
            'metro': {
                'name': 'Metro',
                'layers': ['bangalore-metro-phases-122a2b'],
                'color': '#14e098'
            },
            'strr': {
                'name': 'STRR',
                'layers': ['strr'],
                'color': '#14e098'
            },
            'workspace': {
                'name': 'Workspace',
                'layers': ['blr_industrial_area_processed'],
                'color': '#14e098'
            }
        }
        
        # Initialize services
        s3_service = S3DirectTileGenerationService()
        vector_service = VectorTileService()
        render_service = TileRenderingService()
        
        # Process each requested group
        for group_slug in groups:
            if group_slug not in LAYER_GROUPS:
                self.stdout.write(self.style.WARNING(f'Unknown group: {group_slug}'))
                continue
            
            group_config = LAYER_GROUPS[group_slug]
            self.stdout.write(f'\n📁 Processing: {group_config["name"]}')
            
            # Get actual layers
            layers = []
            total_features = 0
            
            for layer_slug in group_config['layers']:
                layer = DataLayer.objects.filter(city=city, slug=layer_slug).first()
                if layer:
                    layers.append(layer)
                    total_features += layer.feature_count
                    self.stdout.write(f'  ✓ {layer.name}: {layer.feature_count} features')
                else:
                    self.stdout.write(f'  ⚠️  Not found: {layer_slug}')
            
            if not layers:
                self.stdout.write('  ❌ No layers found')
                continue
            
            self.stdout.write(f'  📊 Total: {len(layers)} layers, {total_features:,} features')
            
            # Get bounds from actual features
            all_features = GeoFeature.objects.filter(layer__in=layers)
            
            if not all_features.exists():
                self.stdout.write('  ⚠️  No features found')
                continue
            
            extent = all_features.aggregate(Extent('geometry'))['geometry__extent']
            
            if not extent:
                self.stdout.write('  ⚠️  Could not get bounds')
                continue
            
            bounds = {
                'west': extent[0],
                'south': extent[1],
                'east': extent[2],
                'north': extent[3]
            }
            
            self.stdout.write(f'  📍 Bounds: [{bounds["west"]:.4f}, {bounds["south"]:.4f}, {bounds["east"]:.4f}, {bounds["north"]:.4f}]')
            
            # Generate tiles
            tile_count = 0
            
            for zoom in range(min_zoom, max_zoom + 1):
                tiles = list(mercantile.tiles(
                    bounds['west'], bounds['south'],
                    bounds['east'], bounds['north'],
                    zoom
                ))
                
                self.stdout.write(f'\n  Zoom {zoom}: {len(tiles)} tiles to generate')
                
                # Limit tiles in test mode
                if test_mode:
                    tiles = tiles[:5]
                    self.stdout.write(f'    (Test mode: processing only 5 tiles)')
                
                for tile in tiles:
                    z, x, y = tile.z, tile.x, tile.y
                    
                    try:
                        # Generate combined MVT for all layers in group
                        mvt_data = vector_service.generate_combined_mvt_for_layers(layers, z, x, y)
                        
                        if not mvt_data or len(mvt_data) == 0:
                            continue
                        
                        # S3 key structure
                        state_slug = state.slug if state else 'karnataka'
                        base_key = f"{state_slug}/{city.slug}/{group_slug}/{z}/{x}/{y}"
                        
                        # Upload MVT
                        if 'mvt' in tile_types:
                            mvt_key = f"{base_key}.mvt"
                            result = s3_service.upload_bytes_to_s3(
                                mvt_data, mvt_key, 'application/vnd.mapbox-vector-tile'
                            )
                            if not result['success']:
                                self.stdout.write(f'    ⚠️  MVT upload failed: {z}/{x}/{y}')
                        
                        # Generate and upload PNG
                        if 'png' in tile_types:
                            # For master plan, use individual colors
                            # For others, use single color
                            if group_config.get('use_individual_colors'):
                                png_data = render_service.combined_mvt_to_png(mvt_data, layers, z, x, y)
                            else:
                                # Simple single-color rendering
                                png_data = self._render_single_color_png(mvt_data, group_config.get('color', '#14e098'))
                            
                            if png_data:
                                png_key = f"{base_key}.png"
                                result = s3_service.upload_bytes_to_s3(png_data, png_key, 'image/png')
                                if not result['success']:
                                    self.stdout.write(f'    ⚠️  PNG upload failed: {z}/{x}/{y}')
                        
                        tile_count += 1
                        
                        if tile_count % 100 == 0:
                            self.stdout.write(f'    Progress: {tile_count} tiles generated...')
                    
                    except Exception as e:
                        self.stdout.write(f'    ❌ Error on tile {z}/{x}/{y}: {e}')
                        if test_mode:
                            import traceback
                            self.stdout.write(traceback.format_exc())
            
            self.stdout.write(self.style.SUCCESS(f'\n  ✅ Generated {tile_count} tiles for {group_slug}'))
            
            # Show S3 paths
            if tile_count > 0:
                state_slug = state.slug if state else 'karnataka'
                self.stdout.write(f'\n  📁 S3 Path: s3://{s3_service.bucket_name}/{state_slug}/{city.slug}/{group_slug}/')
                self.stdout.write(f'  🌐 Example URL: https://your-cdn.cloudfront.net/{state_slug}/{city.slug}/{group_slug}/{min_zoom}/x/y.png')
    
    def _render_single_color_png(self, mvt_data, color):
        """Render PNG with single color for all features"""
        import mapbox_vector_tile
        from PIL import Image, ImageDraw
        import io
        
        try:
            decoded = mapbox_vector_tile.decode(mvt_data)
        except:
            return None
        
        img = Image.new('RGBA', (256, 256), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        
        # Parse color
        if color.startswith('#'):
            color = color[1:]
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        fill_color = (r, g, b, 180)
        stroke_color = (r, g, b, 255)
        
        # Draw all features with same color
        for layer_name, layer_data in decoded.items():
            features = layer_data.get('features', [])
            
            for feature in features:
                geom = feature.get('geometry')
                if not geom:
                    continue
                
                geom_type = geom.get('type')
                coords = geom.get('coordinates', [])
                
                # Scale coordinates to tile size (256x256)
                # MVT uses 0-4096 coordinate space
                def scale_coords(coord):
                    if isinstance(coord, (list, tuple)) and len(coord) >= 2:
                        return (coord[0] * 256 / 4096, coord[1] * 256 / 4096)
                    return coord
                
                try:
                    if geom_type == 'LineString':
                        # Draw line
                        scaled = [scale_coords(c) for c in coords]
                        if len(scaled) >= 2:
                            draw.line(scaled, fill=stroke_color, width=2)
                    
                    elif geom_type == 'MultiLineString':
                        # Draw multiple lines
                        for line in coords:
                            scaled = [scale_coords(c) for c in line]
                            if len(scaled) >= 2:
                                draw.line(scaled, fill=stroke_color, width=2)
                    
                    elif geom_type == 'Polygon':
                        # Draw polygon
                        if coords and len(coords[0]) > 2:
                            scaled = [scale_coords(c) for c in coords[0]]
                            draw.polygon(scaled, fill=fill_color, outline=stroke_color)
                    
                    elif geom_type == 'MultiPolygon':
                        # Draw multiple polygons
                        for poly in coords:
                            if poly and len(poly[0]) > 2:
                                scaled = [scale_coords(c) for c in poly[0]]
                                draw.polygon(scaled, fill=fill_color, outline=stroke_color)
                
                except Exception:
                    pass  # Skip malformed geometries
        
        # Save as PNG
        output = io.BytesIO()
        img.save(output, format='PNG', optimize=True)
        return output.getvalue()