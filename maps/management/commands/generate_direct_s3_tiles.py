# maps/management/commands/generate_direct_s3_tiles.py
"""
FIXED Management command to generate valid tiles directly to S3 without local storage
This version fixes the empty tile generation issue
"""

from django.core.management.base import BaseCommand
from maps.s3_direct_tile_service import S3DirectTileGenerationService
from maps.models import City, DataLayer
from maps.services import VectorTileService
from maps.tile_rendering_service import TileRenderingService
import time
import logging
import mercantile

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generate and upload valid tiles directly to S3 (no local storage) - FIXED VERSION'
    
    def add_arguments(self, parser):
        # City options
        parser.add_argument('--city', help='Generate tiles for specific city (bangalore, hyderabad, etc.)')
        parser.add_argument('--all-cities', action='store_true', help='Generate tiles for all cities')
        
        # Real estate options
        parser.add_argument('--real-estate', action='store_true', help='Generate real estate tiles')
        parser.add_argument('--data-type', choices=['plots', 'lands', 'combined'], default='combined', 
                          help='Real estate data type')
        
        # Tile options
        parser.add_argument('--type', choices=['png', 'mvt', 'both'], default='both', 
                          help='Tile format to generate')
        parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=14, help='Maximum zoom level')
        
        # Utility options
        parser.add_argument('--test-connection', action='store_true', help='Test S3 connection only')
        parser.add_argument('--force', action='store_true', help='Force regeneration of existing tiles')
        parser.add_argument('--validate', action='store_true', help='Validate generated tiles after upload')
        parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting FIXED Direct S3 Tile Generation...'))
        
        # Enable debug logging if requested
        if options['debug']:
            logging.getLogger('maps').setLevel(logging.DEBUG)
        
        # Initialize service
        service = S3DirectTileGenerationService()
        
        # Test connection first
        if options['test_connection']:
            self._test_connection(service)
            return
        
        # Test connection before proceeding
        connection_test = service.test_connection()
        if not connection_test['success']:
            self.stdout.write(self.style.ERROR(f"❌ S3 Connection failed: {connection_test['error']}"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"✅ Connected to S3 bucket: {connection_test['bucket']}"))
        if connection_test.get('cloudfront_domain'):
            self.stdout.write(f"🌐 CloudFront domain: {connection_test['cloudfront_domain']}")
        
        start_time = time.time()
        
        # Convert type argument to list
        tile_types = []
        if options['type'] == 'png':
            tile_types = ['png']
        elif options['type'] == 'mvt':
            tile_types = ['mvt']
        else:  # both
            tile_types = ['png', 'mvt']
        
        self.stdout.write(f"📊 Tile types to generate: {', '.join(tile_types)}")
        
        # Generate real estate tiles
        if options['real_estate']:
            result = self._generate_real_estate_tiles(service, options, tile_types)
            self._print_results("Real Estate", result)
        
        # Generate city tiles
        elif options['city']:
            result = self._generate_city_tiles(service, options['city'], options, tile_types)
            self._print_results(f"City ({options['city']})", result)
        
        # Generate all city tiles
        elif options['all_cities']:
            self._generate_all_cities(service, options, tile_types)
        
        else:
            self.stdout.write(self.style.WARNING("⚠️  Please specify --city, --all-cities, or --real-estate"))
            return
        
        # Summary
        total_time = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(f"\n🎉 Generation completed in {total_time:.1f} seconds!"))
        self.stdout.write("🌐 Your tiles are now available via CloudFront!")
    
    def _generate_city_tiles(self, service, city_slug, options, tile_types):
        """Generate tiles for a specific city with proper validation"""
        self.stdout.write(f"\n🏙️  Generating tiles for city: {city_slug}")
        
        try:
            # Get city and validate
            city = City.objects.get(slug=city_slug, is_active=True)
            layers = DataLayer.objects.filter(
                city=city,
                is_processed=True
            ).select_related('category', 'city')
            
            if not layers.exists():
                self.stdout.write(self.style.ERROR(f"❌ No processed layers found for city: {city_slug}"))
                return {'success': False, 'error': 'No processed layers'}
            
            self.stdout.write(f"📂 Found {layers.count()} processed layers:")
            for layer in layers:
                feature_count = layer.feature_count or 0
                self.stdout.write(f"   • {layer.name} ({feature_count:,} features)")
            
            # Use the FIXED generation method
            result = self._generate_city_tiles_fixed(
                service, city_slug, layers, options, tile_types
            )
            
            return result
            
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            return {'success': False, 'error': 'City not found'}
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error generating city tiles: {e}"))
            return {'success': False, 'error': str(e)}
    
    def _generate_city_tiles_fixed(self, service, city_slug, layers, options, tile_types):
        """FIXED: Generate city tiles with proper PNG rendering"""
        
        # Initialize tile services
        vector_service = VectorTileService()
        render_service = TileRenderingService()
        
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        
        # Calculate bounds from layers
        bounds = self._get_city_bounds_from_layers(layers)
        if not bounds:
            return {'success': False, 'error': 'Could not determine city bounds'}
        
        self.stdout.write(f"📊 City bounds: {bounds}")
        
        # Generate tile coordinates
        tiles_to_generate = []
        for zoom in range(min_zoom, max_zoom + 1):
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'],
                zoom
            ))
            tiles_to_generate.extend([(tile.z, tile.x, tile.y) for tile in tiles])
        
        self.stdout.write(f"📊 Will generate {len(tiles_to_generate)} tiles across zoom levels {min_zoom}-{max_zoom}")
        
        # Initialize results
        results = {
            'total_tiles': len(tiles_to_generate),
            'generated_tiles': 0,
            'failed_tiles': 0,
            'png_uploads': 0,
            'mvt_uploads': 0,
            'total_size_mb': 0,
            'errors': []
        }
        
        # Process tiles one by one (to avoid memory issues)
        for i, (z, x, y) in enumerate(tiles_to_generate):
            if i % 100 == 0:
                self.stdout.write(f"   Progress: {i}/{len(tiles_to_generate)} tiles ({(i/len(tiles_to_generate)*100):.1f}%)")
            
            try:
                # Generate MVT data using VectorTileService
                mvt_data = vector_service.generate_combined_tile(layers, z, x, y)
                
                # Check if we have valid MVT data
                if not mvt_data or len(mvt_data) == 0:
                    # Generate empty tile for areas with no data
                    if 'png' in tile_types:
                        empty_png = render_service.create_empty_tile()
                        png_key = f"{city_slug}/combined/{z}_{x}_{y}.png"
                        png_result = service.upload_bytes_to_s3(empty_png, png_key, 'image/png')
                        if png_result['success']:
                            results['png_uploads'] += 1
                            results['total_size_mb'] += len(empty_png) / (1024 * 1024)
                    
                    if 'mvt' in tile_types:
                        # Upload empty MVT
                        mvt_key = f"{city_slug}/combined/{z}_{x}_{y}.mvt"
                        mvt_result = service.upload_bytes_to_s3(b'', mvt_key, 'application/vnd.mapbox-vector-tile')
                        if mvt_result['success']:
                            results['mvt_uploads'] += 1
                    
                    results['generated_tiles'] += 1
                    continue
                
                # Upload MVT if requested
                if 'mvt' in tile_types:
                    mvt_key = f"{city_slug}/combined/{z}_{x}_{y}.mvt"
                    mvt_result = service.upload_bytes_to_s3(mvt_data, mvt_key, 'application/vnd.mapbox-vector-tile')
                    if mvt_result['success']:
                        results['mvt_uploads'] += 1
                        results['total_size_mb'] += len(mvt_data) / (1024 * 1024)
                    else:
                        results['errors'].append(f"MVT upload failed for {z}/{x}/{y}: {mvt_result.get('error')}")
                        results['failed_tiles'] += 1
                        continue
                
                # Generate and upload PNG if requested
                if 'png' in tile_types:
                    # FIXED: Use the proper PNG rendering method
                    png_data = render_service.combined_mvt_to_png(mvt_data, layers, z, x, y)
                    
                    if png_data and len(png_data) > 0:
                        png_key = f"{city_slug}/combined/{z}_{x}_{y}.png"
                        png_result = service.upload_bytes_to_s3(png_data, png_key, 'image/png')
                        if png_result['success']:
                            results['png_uploads'] += 1
                            results['total_size_mb'] += len(png_data) / (1024 * 1024)
                        else:
                            results['errors'].append(f"PNG upload failed for {z}/{x}/{y}: {png_result.get('error')}")
                            results['failed_tiles'] += 1
                            continue
                    else:
                        # Fallback to empty tile if PNG generation fails
                        empty_png = render_service.create_empty_tile()
                        png_key = f"{city_slug}/combined/{z}_{x}_{y}.png"
                        png_result = service.upload_bytes_to_s3(empty_png, png_key, 'image/png')
                        if png_result['success']:
                            results['png_uploads'] += 1
                            results['total_size_mb'] += len(empty_png) / (1024 * 1024)
                
                results['generated_tiles'] += 1
                
            except Exception as e:
                logger.error(f"Error generating tile {z}/{x}/{y}: {e}")
                results['errors'].append(f"Tile {z}/{x}/{y}: {str(e)}")
                results['failed_tiles'] += 1
        
        # Calculate success rate
        success_rate = (results['generated_tiles'] / results['total_tiles']) * 100 if results['total_tiles'] > 0 else 0
        
        return {
            'success': True,
            'city': city_slug,
            'results': results,
            'success_rate': f"{success_rate:.1f}%",
            'sample_urls': self._generate_sample_urls(service, city_slug, min_zoom, max_zoom)
        }
    
    def _get_city_bounds_from_layers(self, layers):
        """Calculate bounds from all layers"""
        bounds = None
        vector_service = VectorTileService()
        
        for layer in layers:
            layer_bounds = vector_service._get_layer_bounds(layer)
            if layer_bounds:
                if not bounds:
                    bounds = layer_bounds.copy()
                else:
                    bounds['west'] = min(bounds['west'], layer_bounds['west'])
                    bounds['south'] = min(bounds['south'], layer_bounds['south'])
                    bounds['east'] = max(bounds['east'], layer_bounds['east'])
                    bounds['north'] = max(bounds['north'], layer_bounds['north'])
        
        return bounds
    
    def _generate_real_estate_tiles(self, service, options, tile_types):
        """Generate real estate tiles"""
        self.stdout.write(f"\n🏡 Generating real estate tiles...")
        
        result = service.generate_and_upload_real_estate_tiles(
            data_type=options['data_type'],
            min_zoom=options['min_zoom'],
            max_zoom=options['max_zoom'],
            tile_types=tile_types
        )
        
        return result
    
    def _generate_all_cities(self, service, options, tile_types):
        """Generate tiles for all active cities"""
        self.stdout.write(f"\n🌆 Generating tiles for all cities...")
        
        cities = City.objects.filter(is_active=True)
        if not cities.exists():
            self.stdout.write(self.style.WARNING("⚠️  No active cities found"))
            return
        
        self.stdout.write(f"📂 Found {cities.count()} active cities")
        
        for i, city in enumerate(cities):
            self.stdout.write(f"\n[{i+1}/{cities.count()}] Processing {city.name}...")
            
            result = self._generate_city_tiles(service, city.slug, options, tile_types)
            self._print_results(f"City ({city.slug})", result)
    
    def _generate_sample_urls(self, service, city_slug, min_zoom, max_zoom):
        """Generate sample URLs for testing"""
        sample_urls = {}
        
        # Generate CloudFront URLs if available
        if service.cloudfront_domain:
            base_url = f"https://{service.cloudfront_domain}"
        else:
            base_url = f"https://{service.bucket_name}.s3.{service.region}.amazonaws.com"
        
        # Sample PNG and MVT URLs
        mid_zoom = (min_zoom + max_zoom) // 2
        sample_urls.update({
            'city_tile_png': f"{base_url}/{city_slug}/combined/{mid_zoom}_1024_1024.png",
            'city_tile_mvt': f"{base_url}/{city_slug}/combined/{mid_zoom}_1024_1024.mvt",
            'template_png': f"{base_url}/{city_slug}/combined/{{z}}_{{x}}_{{y}}.png",
            'template_mvt': f"{base_url}/{city_slug}/combined/{{z}}_{{x}}_{{y}}.mvt"
        })
        
        return sample_urls
    
    def _test_connection(self, service):
        """Test S3 connection"""
        self.stdout.write("🔍 Testing S3 connection...")
        
        result = service.test_connection()
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS("✅ S3 Connection successful!"))
            self.stdout.write(f"   Bucket: {result['bucket']}")
            self.stdout.write(f"   Region: {result['region']}")
            if result.get('cloudfront_domain'):
                self.stdout.write(f"   CloudFront: {result['cloudfront_domain']}")
        else:
            self.stdout.write(self.style.ERROR(f"❌ S3 Connection failed: {result['error']}"))
    
    def _print_results(self, description, result):
        """Print generation results"""
        if result.get('success'):
            self.stdout.write(self.style.SUCCESS(f"✅ {description} generation completed!"))
            
            if 'results' in result:
                res = result['results']
                self.stdout.write(f"   📊 Total tiles: {res.get('total_tiles', 0)}")
                self.stdout.write(f"   ✅ Generated: {res.get('generated_tiles', 0)}")
                self.stdout.write(f"   ❌ Failed: {res.get('failed_tiles', 0)}")
                self.stdout.write(f"   🖼️  PNG uploads: {res.get('png_uploads', 0)}")
                self.stdout.write(f"   📦 MVT uploads: {res.get('mvt_uploads', 0)}")
                self.stdout.write(f"   💾 Total size: {res.get('total_size_mb', 0):.2f} MB")
                
                if res.get('errors'):
                    self.stdout.write(f"   ⚠️  First few errors:")
                    for error in res['errors'][:3]:
                        self.stdout.write(f"      {error}")
                    if len(res['errors']) > 3:
                        self.stdout.write(f"      ... and {len(res['errors']) - 3} more")
            
            # Show success rate
            if 'success_rate' in result:
                self.stdout.write(f"   📈 Success rate: {result['success_rate']}")
            
            # Show sample URLs
            if result.get('sample_urls'):
                self.stdout.write(f"\n📋 Sample URLs for testing:")
                for key, url in result['sample_urls'].items():
                    self.stdout.write(f"   {key}: {url}")
        else:
            self.stdout.write(self.style.ERROR(f"❌ {description} generation failed!"))
            if 'error' in result:
                self.stdout.write(f"   Error: {result['error']}")
            
            if 'results' in result:
                res = result['results']
                self.stdout.write(f"   📊 Total tiles attempted: {res.get('total_tiles', 0)}")
                self.stdout.write(f"   ✅ Generated: {res.get('generated_tiles', 0)}")
                self.stdout.write(f"   ❌ Failed: {res.get('failed_tiles', 0)}")