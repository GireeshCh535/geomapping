# maps/management/commands/upload_tiles_to_s3.py

from django.core.management.base import BaseCommand
from maps.s3_upload_service import S3TileUploadService
import time

class Command(BaseCommand):
    help = 'Upload generated tiles to S3 for CloudFront distribution'
    
    def add_arguments(self, parser):
        parser.add_argument('--city', help='Upload tiles for specific city (bangalore, hyderabad, etc.)')
        parser.add_argument('--type', choices=['png', 'mvt', 'both'], default='png', help='Tile format to upload')
        parser.add_argument('--real-estate', action='store_true', help='Upload real estate tiles instead of city tiles')
        parser.add_argument('--data-type', choices=['plots', 'lands', 'combined'], default='combined', help='Real estate data type')
        parser.add_argument('--test-connection', action='store_true', help='Test S3 connection only')
        parser.add_argument('--all-cities', action='store_true', help='Upload tiles for all cities')
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting S3 tile upload...'))
        
        # Initialize upload service
        upload_service = S3TileUploadService()
        
        # Test connection first
        if options['test_connection']:
            self._test_connection(upload_service)
            return
        
        # Test connection before proceeding
        connection_test = upload_service.test_connection()
        if not connection_test['success']:
            self.stdout.write(self.style.ERROR(f"❌ S3 Connection failed: {connection_test['error']}"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"✅ Connected to S3 bucket: {connection_test['bucket']}"))
        
        start_time = time.time()
        
        # Upload real estate tiles
        if options['real_estate']:
            self._upload_real_estate_tiles(upload_service, options)
        
        # Upload city tiles
        elif options['city']:
            self._upload_city_tiles(upload_service, options['city'], options['type'])
        
        # Upload all cities
        elif options['all_cities']:
            self._upload_all_cities(upload_service, options['type'])
        
        else:
            self.stdout.write(self.style.WARNING("⚠️  Please specify --city, --all-cities, or --real-estate"))
            return
        
        # Summary
        total_time = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(f"\n🎉 Upload completed in {total_time:.1f} seconds!"))
        self.stdout.write("🌐 Your tiles are now available via CloudFront!")
    
    def _test_connection(self, upload_service):
        """Test S3 connection"""
        self.stdout.write("🔍 Testing S3 connection...")
        
        result = upload_service.test_connection()
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS("✅ S3 Connection successful!"))
            self.stdout.write(f"   Bucket: {result['bucket']}")
            self.stdout.write(f"   Region: {result['region']}")
            self.stdout.write(f"   Objects in bucket: {result.get('object_count', 'Unknown')}")
        else:
            self.stdout.write(self.style.ERROR(f"❌ Connection failed: {result['error']}"))
            self.stdout.write("\n🔧 Troubleshooting:")
            self.stdout.write("   1. Check AWS credentials in settings.py")
            self.stdout.write("   2. Verify bucket name: 'gis-portal'")
            self.stdout.write("   3. Ensure bucket exists in ap-south-1 region")
            self.stdout.write("   4. Check IAM permissions for S3 access")
    
    def _upload_city_tiles(self, upload_service, city_slug, tile_type):
        """Upload tiles for a specific city"""
        
        self.stdout.write(f"\n🏙️  Uploading {tile_type.upper()} tiles for {city_slug}...")
        
        if tile_type in ['png', 'both']:
            self.stdout.write("📤 Uploading PNG tiles...")
            result = upload_service.upload_city_tiles(city_slug, 'png')
            self._display_upload_result(result, f"{city_slug} PNG")
        
        if tile_type in ['mvt', 'both']:
            self.stdout.write("📤 Uploading MVT tiles...")
            result = upload_service.upload_city_tiles(city_slug, 'mvt')
            self._display_upload_result(result, f"{city_slug} MVT")
    
    def _upload_all_cities(self, upload_service, tile_type):
        """Upload tiles for all cities"""
        
        # List of cities (you can make this dynamic by querying the database)
        cities = ['bangalore', 'hyderabad', 'vizag', 'amaravati']
        
        self.stdout.write(f"\n🌍 Uploading {tile_type.upper()} tiles for all cities...")
        
        for city_slug in cities:
            self.stdout.write(f"\n--- Processing {city_slug.upper()} ---")
            self._upload_city_tiles(upload_service, city_slug, tile_type)
    
    def _upload_real_estate_tiles(self, upload_service, options):
        """Upload real estate tiles"""
        
        data_type = options['data_type']
        tile_type = options['type']
        
        self.stdout.write(f"\n🏡 Uploading real estate tiles ({data_type})...")
        
        if tile_type in ['png', 'both']:
            self.stdout.write("📤 Uploading PNG tiles...")
            result = upload_service.upload_real_estate_tiles(data_type, 'png')
            self._display_upload_result(result, f"Real Estate {data_type} PNG")
        
        if tile_type in ['mvt', 'both']:
            self.stdout.write("📤 Uploading MVT tiles...")
            result = upload_service.upload_real_estate_tiles(data_type, 'mvt')
            self._display_upload_result(result, f"Real Estate {data_type} MVT")
    
    def _display_upload_result(self, result, description):
        """Display upload results"""
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f"✅ {description} upload successful!"))
            self.stdout.write(f"   📊 Uploaded: {result['uploaded']}/{result['total']} files")
            self.stdout.write(f"   📈 Success rate: {result.get('success_rate', 'N/A')}")
            if 'total_size_mb' in result:
                self.stdout.write(f"   💾 Total size: {result['total_size_mb']} MB")
            if 'cloudfront_url' in result:
                self.stdout.write(f"   🌐 CloudFront URL: {result['cloudfront_url']}")
        else:
            self.stdout.write(self.style.ERROR(f"❌ {description} upload failed!"))
            self.stdout.write(f"   📊 Uploaded: {result.get('uploaded', 0)}/{result.get('total', 0)} files")
            self.stdout.write(f"   ❌ Failed: {result.get('failed', 0)} files")
            if 'error' in result:
                self.stdout.write(f"   Error: {result['error']}")