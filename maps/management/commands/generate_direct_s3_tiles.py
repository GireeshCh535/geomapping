# maps/management/commands/generate_direct_s3_tiles.py
"""
Management command to generate tiles directly to S3 without local storage
"""

from django.core.management.base import BaseCommand
from maps.s3_direct_tile_service import S3DirectTileGenerationService
import time

class Command(BaseCommand):
    help = 'Generate and upload tiles directly to S3 (no local storage)'
    
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
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting Direct S3 Tile Generation...'))
        
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
        
        # Determine tile types
        tile_types = []
        if options['type'] in ['png', 'both']:
            tile_types.append('png')
        if options['type'] in ['mvt', 'both']:
            tile_types.append('mvt')
        
        # Generate real estate tiles
        if options['real_estate']:
            self._generate_real_estate_tiles(service, options, tile_types)
        
        # Generate city tiles
        elif options['city']:
            self._generate_city_tiles(service, options['city'], options, tile_types)
        
        # Generate all cities
        elif options['all_cities']:
            self._generate_all_cities(service, options, tile_types)
        
        else:
            self.stdout.write(self.style.WARNING("⚠️  Please specify --city, --all-cities, or --real-estate"))
            return
        
        # Summary
        total_time = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(f"\n🎉 Generation completed in {total_time:.1f} seconds!"))
        self.stdout.write("🌐 Your tiles are now available via CloudFront!")
    
    def _test_connection(self, service):
        """Test S3 connection"""
        self.stdout.write("🔍 Testing S3 connection...")
        
        result = service.test_connection()
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS("✅ S3 Connection successful!"))
            self.stdout.write(f"   Bucket: {result['bucket']}")
            self.stdout.write(f"   Region: {result['region']}")
            self.stdout.write(f"   CloudFront: {result.get('cloudfront_domain', 'Not configured')}")
            self.stdout.write(f"   Objects in bucket: {result.get('object_count', 'Unknown')}")
        else:
            self.stdout.write(self.style.ERROR(f"❌ Connection failed: {result['error']}"))
            self.stdout.write("\n🔧 Troubleshooting:")
            self.stdout.write("   1. Check AWS credentials in settings.py")
            self.stdout.write("   2. Verify bucket name: 'gis-portal'")
            self.stdout.write("   3. Ensure bucket exists in ap-south-1 region")
            self.stdout.write("   4. Check IAM permissions for S3 access")
    
    def _generate_city_tiles(self, service, city_slug, options, tile_types):
        """Generate tiles for a specific city"""
        
        self.stdout.write(f"\n🏙️  Generating {'/'.join(tile_types).upper()} tiles for {city_slug}...")
        self.stdout.write(f"   Zoom levels: {options['min_zoom']}-{options['max_zoom']}")
        
        result = service.generate_and_upload_city_tiles(
            city_slug=city_slug,
            min_zoom=options['min_zoom'],
            max_zoom=options['max_zoom'],
            tile_types=tile_types
        )
        
        self._display_generation_result(result, f"{city_slug} City")
    
    def _generate_all_cities(self, service, options, tile_types):
        """Generate tiles for all cities"""
        
        from maps.models import City
        
        cities = City.objects.filter(is_active=True).values_list('slug', flat=True)
        
        if not cities:
            self.stdout.write(self.style.WARNING("No active cities found"))
            return
        
        self.stdout.write(f"\n🌍 Generating {'/'.join(tile_types).upper()} tiles for {len(cities)} cities...")
        
        total_results = {
            'cities_processed': 0,
            'cities_successful': 0,
            'total_tiles_generated': 0,
            'total_size_mb': 0
        }
        
        for city_slug in cities:
            self.stdout.write(f"\n--- Processing {city_slug.upper()} ---")
            
            result = service.generate_and_upload_city_tiles(
                city_slug=city_slug,
                min_zoom=options['min_zoom'],
                max_zoom=options['max_zoom'],
                tile_types=tile_types
            )
            
            total_results['cities_processed'] += 1
            
            if result['success']:
                total_results['cities_successful'] += 1
                total_results['total_tiles_generated'] += result['results']['generated_tiles']
                total_results['total_size_mb'] += result['results']['total_size_mb']
                
                self.stdout.write(self.style.SUCCESS(f"✅ {city_slug} completed successfully"))
                self.stdout.write(f"   Generated: {result['results']['generated_tiles']} tiles")
                self.stdout.write(f"   Success rate: {result['success_rate']}")
            else:
                self.stdout.write(self.style.ERROR(f"❌ {city_slug} failed: {result.get('error', 'Unknown error')}"))
        
        # Summary
        self.stdout.write(f"\n📊 ALL CITIES SUMMARY:")
        self.stdout.write(f"   Cities processed: {total_results['cities_processed']}")
        self.stdout.write(f"   Cities successful: {total_results['cities_successful']}")
        self.stdout.write(f"   Total tiles generated: {total_results['total_tiles_generated']}")
        self.stdout.write(f"   Total size: {total_results['total_size_mb']:.1f} MB")
    
    def _generate_real_estate_tiles(self, service, options, tile_types):
        """Generate real estate tiles"""
        
        data_type = options['data_type']
        
        self.stdout.write(f"\n🏡 Generating real estate tiles ({data_type})...")
        self.stdout.write(f"   Tile types: {'/'.join(tile_types).upper()}")
        self.stdout.write(f"   Zoom levels: {options['min_zoom']}-{options['max_zoom']}")
        
        result = service.generate_and_upload_real_estate_tiles(
            data_type=data_type,
            min_zoom=options['min_zoom'],
            max_zoom=options['max_zoom'],
            tile_types=tile_types
        )
        
        self._display_generation_result(result, f"Real Estate {data_type}")
    
    def _display_generation_result(self, result, description):
        """Display generation results"""
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f"✅ {description} generation successful!"))
            
            if 'results' in result:
                res = result['results']
                self.stdout.write(f"   📊 Total tiles: {res['total_tiles']}")
                self.stdout.write(f"   ✅ Generated: {res['generated_tiles']}")
                self.stdout.write(f"   ❌ Failed: {res['failed_tiles']}")
                self.stdout.write(f"   📈 Success rate: {result.get('success_rate', 'N/A')}")
                self.stdout.write(f"   💾 Total size: {res['total_size_mb']:.1f} MB")
                
                if res.get('png_uploads'):
                    self.stdout.write(f"   🖼️  PNG uploads: {res['png_uploads']}")
                if res.get('mvt_uploads'):
                    self.stdout.write(f"   🗂️  MVT uploads: {res['mvt_uploads']}")
                
                # Show errors if any
                if res.get('errors'):
                    self.stdout.write(self.style.WARNING(f"   ⚠️  Errors encountered: {len(res['errors'])}"))
                    for i, error in enumerate(res['errors'][:3]):  # Show first 3 errors
                        self.stdout.write(f"      {i+1}. {error}")
                    if len(res['errors']) > 3:
                        self.stdout.write(f"      ... and {len(res['errors']) - 3} more")
                
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
    
    def _validate_tiles(self, service, city_slug, min_zoom, max_zoom):
        """Validate generated tiles (optional)"""
        # Implementation for tile validation
        # Check if tiles exist in S3 and are accessible
        pass