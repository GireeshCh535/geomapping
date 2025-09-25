# maps/management/commands/generate_tiles_fixed.py
"""
Generate tiles with correct layer grouping based on actual imported data
"""

from django.core.management.base import BaseCommand
from django.contrib.gis.db.models import Extent
from maps.models import City, DataLayer, State, GeoFeature, LayerGroup
from maps.config import DATA_IMPORT_CONFIG
from maps.services import VectorTileService
from maps.tile_rendering_service import TileRenderingService
from maps.s3_direct_tile_service import S3DirectTileGenerationService
import mercantile
import time

class Command(BaseCommand):
    help = 'Generate tiles for city layer groups with correct grouping'
    
    def add_arguments(self, parser):
        parser.add_argument('--city', required=True, help='City slug')
        parser.add_argument('--layer-groups', required=True, help='Comma-separated layer groups')
        parser.add_argument('--type', nargs='+', default=['png'], choices=['png', 'mvt'])
        parser.add_argument('--min-zoom', type=int, default=8)
        parser.add_argument('--max-zoom', type=int, default=14)
        parser.add_argument('--test', action='store_true', help='Test mode - generate only few tiles')
        parser.add_argument('--verbose', action='store_true', help='Verbose output')
        
    def handle(self, *args, **options):
        city_slug = options['city']
        layer_groups = options['layer_groups'].split(',')
        tile_types = options['type']
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        test_mode = options['test']
        verbose = options['verbose']
        
        # Get city (handle Bengaluru/Bangalore naming)
        try:
            city = City.objects.get(slug=city_slug)
        except City.DoesNotExist:
            if city_slug == 'bengaluru':
                try:
                    city = City.objects.get(slug='bangalore')
                except:
                    city = City.objects.get(name__icontains='bangalore')
            else:
                self.stdout.write(self.style.ERROR(f'City not found: {city_slug}'))
                return
        
        # Get state
        state = city.state_ref
        if not state:
            state = State.objects.filter(name__icontains='karnataka').first()
        
        self.stdout.write(self.style.SUCCESS(f'🏙️  City: {city.name}'))
        self.stdout.write(f'📍 State: {state.name if state else "Unknown"}')
        
        # Initialize services
        s3_service = S3DirectTileGenerationService()
        vector_service = VectorTileService()
        render_service = TileRenderingService()
        
        # Get configuration
        config_city_slug = 'bengaluru' if city.slug == 'bangalore' else city_slug
        city_config = None
        for state_slug, state_config in DATA_IMPORT_CONFIG['states'].items():
            if config_city_slug in state_config.get('cities', {}):
                city_config = state_config['cities'][config_city_slug]
                break
        
        if not city_config:
            self.stdout.write(self.style.ERROR(f'No configuration found for {config_city_slug}'))
            return
        
        # Process each layer group
        total_stats = {'tiles': 0, 'time': 0}
        
        for group_slug in layer_groups:
            group_slug = group_slug.strip()
            start_time = time.time()
            
            self.stdout.write(f'\n{"="*60}')
            self.stdout.write(f'📁 Processing Layer Group: {group_slug}')
            self.stdout.write(f'{"="*60}')
            
            if group_slug not in city_config.get('layer_groups', {}):
                self.stdout.write(self.style.WARNING(f'⚠️  Layer group "{group_slug}" not in configuration'))
                continue
            
            group_config = city_config['layer_groups'][group_slug]
            
            # Get layers for this group
            layers = self._get_layers_for_group(city, group_config, verbose)
            
            if not layers:
                self.stdout.write(self.style.WARNING(f'⚠️  No layers found for {group_slug}'))
                continue
            
            # Calculate bounds
            self.stdout.write(f'\n📊 Statistics:')
            total_features = sum(layer.feature_count for layer in layers)
            self.stdout.write(f'  Layers: {len(layers)}')
            self.stdout.write(f'  Features: {total_features:,}')
            
            # Get actual bounds from features
            all_features = GeoFeature.objects.filter(layer__in=layers)
            if not all_features.exists():
                self.stdout.write(self.style.WARNING('  ⚠️  No features found in database'))
                continue
            
            extent = all_features.aggregate(Extent('geometry'))['geometry__extent']
            if not extent:
                self.stdout.write(self.style.WARNING('  ⚠️  Could not calculate bounds'))
                continue
            
            bounds = {
                'west': extent[0],
                'south': extent[1], 
                'east': extent[2],
                'north': extent[3]
            }
            
            self.stdout.write(f'  Bounds: [{bounds["west"]:.4f}, {bounds["south"]:.4f}] to [{bounds["east"]:.4f}, {bounds["north"]:.4f}]')
            
            # Generate tiles
            tile_count = self._generate_tiles_for_group(
                s3_service, vector_service, render_service,
                state, city, group_slug, layers, bounds,
                min_zoom, max_zoom, tile_types, test_mode, verbose
            )
            
            elapsed = time.time() - start_time
            total_stats['tiles'] += tile_count
            total_stats['time'] += elapsed
            
            self.stdout.write(self.style.SUCCESS(f'\n✅ Generated {tile_count} tiles in {elapsed:.1f} seconds'))
            
            # Show S3 paths
            if tile_count > 0:
                state_slug = state.slug if state else 'karnataka'
                self.stdout.write(f'\n📁 S3 Location:')
                self.stdout.write(f'  Bucket: {s3_service.bucket_name}')
                self.stdout.write(f'  Path: {state_slug}/{city.slug}/{group_slug}/{{z}}/{{x}}/{{y}}.png')
                if s3_service.cloudfront_domain:
                    self.stdout.write(f'  CDN: https://{s3_service.cloudfront_domain}/{state_slug}/{city.slug}/{group_slug}/{{z}}/{{x}}/{{y}}.png')
        
        # Final summary
        self.stdout.write(f'\n{"="*60}')
        self.stdout.write(self.style.SUCCESS('🎉 TILE GENERATION COMPLETE'))
        self.stdout.write(f'{"="*60}')
        self.stdout.write(f'Total tiles: {total_stats["tiles"]:,}')
        self.stdout.write(f'Total time: {total_stats["time"]:.1f} seconds')
    
    def _get_layers_for_group(self, city, group_config, verbose=False):
        """Get layers that belong to this group"""
        layers = []
        files = group_config.get('files', {})
        
        self.stdout.write(f'\n📋 Finding layers:')
        
        for filename, file_config in files.items():
            layer_name = file_config['name']
            
            # Try multiple methods to find the layer
            layer = None
            
            # Method 1: By exact name
            layer = DataLayer.objects.filter(city=city, name=layer_name).first()
            
            # Method 2: By filename
            if not layer:
                layer = DataLayer.objects.filter(city=city, original_filename=filename).first()
            
            # Method 3: By slug (from filename)
            if not layer:
                from django.utils.text import slugify
                layer_slug = slugify(filename.replace('.json', '').replace('.geojson', ''))
                layer = DataLayer.objects.filter(city=city, slug=layer_slug).first()
            
            # Method 4: By partial name match
            if not layer:
                layer = DataLayer.objects.filter(
                    city=city, 
                    name__icontains=layer_name.split()[0]
                ).first()
            
            if layer:
                layers.append(layer)
                self.stdout.write(f'  ✓ {layer.name}: {layer.feature_count:,} features')
            elif verbose:
                self.stdout.write(f'  ⚠️  Not found: {layer_name} ({filename})')
        
        return layers
    
    def _generate_tiles_for_group(self, s3_service, vector_service, render_service,
                                  state, city, group_slug, layers, bounds,
                                  min_zoom, max_zoom, tile_types, test_mode, verbose):
        """Generate tiles for a layer group"""
        
        tile_count = 0
        state_slug = state.slug if state else 'karnataka'
        
        self.stdout.write(f'\n🗺️  Generating tiles:')
        
        for zoom in range(min_zoom, max_zoom + 1):
            # Get tiles for this zoom level
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'],
                zoom
            ))
            
            self.stdout.write(f'  Zoom {zoom}: {len(tiles)} tiles')
            
            # Limit tiles in test mode
            if test_mode:
                tiles = tiles[:5]
                self.stdout.write(f'    (Test mode: processing only 5 tiles)')
            
            # Process each tile
            for i, tile in enumerate(tiles):
                z, x, y = tile.z, tile.x, tile.y
                
                try:
                    # Generate combined MVT for all layers
                    mvt_data = vector_service.generate_combined_mvt_for_layers(layers, z, x, y)
                    
                    if not mvt_data or len(mvt_data) == 0:
                        continue
                    
                    # Upload MVT if requested
                    if 'mvt' in tile_types:
                        mvt_key = f"{state_slug}/{city.slug}/{group_slug}/{z}/{x}/{y}.mvt"
                        result = s3_service.upload_bytes_to_s3(
                            mvt_data, mvt_key, 'application/vnd.mapbox-vector-tile'
                        )
                        if not result['success'] and verbose:
                            self.stdout.write(f'    ⚠️  MVT upload failed: {z}/{x}/{y}')
                    
                    # Generate and upload PNG if requested
                    if 'png' in tile_types:
                        # Use appropriate rendering based on group
                        if group_slug == 'master-plan':
                            # Multi-color rendering for master plan
                            png_data = render_service.combined_mvt_to_png(mvt_data, layers, z, x, y)
                        else:
                            # Single color for infrastructure (highways, metro, etc.)
                            png_data = self._render_single_color_png(mvt_data, '#14e098')
                        
                        if png_data:
                            png_key = f"{state_slug}/{city.slug}/{group_slug}/{z}/{x}/{y}.png"
                            result = s3_service.upload_bytes_to_s3(png_data, png_key, 'image/png')
                            if not result['success'] and verbose:
                                self.stdout.write(f'    ⚠️  PNG upload failed: {z}/{x}/{y}')
                    
                    tile_count += 1
                    
                    # Progress indicator
                    if tile_count % 100 == 0:
                        self.stdout.write(f'    Progress: {tile_count} tiles generated...')
                        
                except Exception as e:
                    if verbose:
                        self.stdout.write(f'    ❌ Error on tile {z}/{x}/{y}: {e}')
        
        return tile_count
    
    def _render_single_color_png(self, mvt_data, color):
        """Render PNG with single color for infrastructure layers"""
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
        
        # Draw all features
        for layer_name, layer_data in decoded.items():
            features = layer_data.get('features', [])
            
            for feature in features:
                geom = feature.get('geometry')
                if not geom:
                    continue
                
                geom_type = geom.get('type')
                coords = geom.get('coordinates', [])
                
                # Scale coordinates (MVT uses 0-4096 space)
                def scale_coords(coord):
                    if isinstance(coord, (list, tuple)) and len(coord) >= 2:
                        return (coord[0] * 256 / 4096, coord[1] * 256 / 4096)
                    return coord
                
                try:
                    if geom_type in ['LineString', 'MultiLineString']:
                        # Draw lines
                        if geom_type == 'LineString':
                            scaled = [scale_coords(c) for c in coords]
                            if len(scaled) >= 2:
                                draw.line(scaled, fill=stroke_color, width=3)
                        else:
                            for line in coords:
                                scaled = [scale_coords(c) for c in line]
                                if len(scaled) >= 2:
                                    draw.line(scaled, fill=stroke_color, width=3)
                    
                    elif geom_type in ['Polygon', 'MultiPolygon']:
                        # Draw polygons
                        if geom_type == 'Polygon':
                            if coords and len(coords[0]) > 2:
                                scaled = [scale_coords(c) for c in coords[0]]
                                draw.polygon(scaled, fill=fill_color, outline=stroke_color)
                        else:
                            for poly in coords:
                                if poly and len(poly[0]) > 2:
                                    scaled = [scale_coords(c) for c in poly[0]]
                                    draw.polygon(scaled, fill=fill_color, outline=stroke_color)
                
                except Exception:
                    pass
        
        # Save as PNG
        output = io.BytesIO()
        img.save(output, format='PNG', optimize=True)
        return output.getvalue()