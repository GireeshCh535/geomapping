# maps/management/commands/fix_s3_tile_paths.py
"""
Management command to fix S3 tile paths and ensure consistency
Usage: python manage.py fix_s3_tile_paths --state karnataka --city bengaluru --layer bengaluru_master_plan_2015

This command:
1. Lists existing tiles in S3
2. Validates path consistency
3. Can rename/move tiles to correct paths
4. Updates database records if needed
"""

import boto3
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from botocore.exceptions import ClientError
from maps.models import State, City, DataLayer
from maps.tile_path_service import TilePathService

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fix S3 tile paths and ensure consistency across the system'
    
    def __init__(self):
        super().__init__()
        self.bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'gis-portal-layers')
        self.region = getattr(settings, 'AWS_S3_REGION_NAME', 'ap-south-1')
        self.s3_client = boto3.client(
            's3',
            region_name=self.region,
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        )
        self.tile_path_service = TilePathService()
    
    def add_arguments(self, parser):
        parser.add_argument('--state', type=str, help='State slug (e.g., karnataka)')
        parser.add_argument('--city', type=str, help='City slug (e.g., bengaluru)')
        parser.add_argument('--layer', type=str, help='Layer slug (e.g., bengaluru_master_plan_2015)')
        parser.add_argument('--list-only', action='store_true', help='Only list tiles, do not fix')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be done without executing')
        parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🔧 S3 TILE PATH FIXER'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        try:
            # Test S3 connection
            self._test_s3_connection()
            
            # Get filter parameters
            state_slug = options.get('state')
            city_slug = options.get('city')
            layer_slug = options.get('layer')
            
            # List tiles in S3
            tiles = self._list_s3_tiles(state_slug, city_slug, layer_slug)
            
            if not tiles:
                self.stdout.write(self.style.WARNING("⚠️  No tiles found in S3"))
                return
            
            self.stdout.write(f"📊 Found {len(tiles)} tiles in S3")
            
            # Analyze tile paths
            path_analysis = self._analyze_tile_paths(tiles)
            
            # Display analysis
            self._display_path_analysis(path_analysis)
            
            if options['list_only']:
                return
            
            # Fix paths if needed
            if path_analysis['inconsistent_paths']:
                self._fix_tile_paths(path_analysis['inconsistent_paths'], options)
            else:
                self.stdout.write(self.style.SUCCESS("✅ All tile paths are consistent!"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {str(e)}"))
            if options['verbose']:
                import traceback
                self.stdout.write(traceback.format_exc())
    
    def _test_s3_connection(self):
        """Test S3 connection"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            self.stdout.write(f"✅ S3 connection successful: {self.bucket_name}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise Exception(f"S3 bucket not found: {self.bucket_name}")
            elif error_code == '403':
                raise Exception(f"Access denied to S3 bucket: {self.bucket_name}")
            else:
                raise Exception(f"S3 connection failed: {error_code}")
    
    def _list_s3_tiles(self, state_slug=None, city_slug=None, layer_slug=None):
        """List tiles in S3 with optional filtering"""
        tiles = []
        
        try:
            # Build prefix for filtering
            prefix = ""
            if state_slug:
                prefix += f"{state_slug}/"
                if city_slug:
                    prefix += f"{city_slug}/"
                    if layer_slug:
                        prefix += f"{layer_slug}/"
            
            # List objects in S3
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            for page in page_iterator:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        # Only include tile files
                        if key.endswith('.png') or key.endswith('.mvt'):
                            tiles.append({
                                'key': key,
                                'size': obj['Size'],
                                'last_modified': obj['LastModified']
                            })
            
            return tiles
            
        except ClientError as e:
            self.stdout.write(self.style.ERROR(f"❌ Error listing S3 objects: {e}"))
            return []
    
    def _analyze_tile_paths(self, tiles):
        """Analyze tile paths for consistency"""
        analysis = {
            'total_tiles': len(tiles),
            'consistent_paths': [],
            'inconsistent_paths': [],
            'path_patterns': {},
            'errors': []
        }
        
        for tile in tiles:
            key = tile['key']
            
            # Parse the path
            parsed = self.tile_path_service.parse_tile_path(key)
            
            if parsed:
                # Check if this is a consistent path
                expected_key = self.tile_path_service.generate_s3_key(
                    parsed['state_slug'],
                    parsed['city_slug'],
                    parsed['layer_slug'],
                    parsed['z'],
                    parsed['x'],
                    parsed['y'],
                    parsed['format_type']
                )
                
                if key == expected_key:
                    analysis['consistent_paths'].append(tile)
                else:
                    analysis['inconsistent_paths'].append({
                        'current': tile,
                        'expected': expected_key,
                        'parsed': parsed
                    })
                
                # Track path patterns
                pattern = f"{parsed['state_slug']}/{parsed['city_slug']}/{parsed['layer_slug']}"
                if pattern not in analysis['path_patterns']:
                    analysis['path_patterns'][pattern] = 0
                analysis['path_patterns'][pattern] += 1
            else:
                analysis['errors'].append({
                    'key': key,
                    'error': 'Could not parse path'
                })
        
        return analysis
    
    def _display_path_analysis(self, analysis):
        """Display path analysis results"""
        self.stdout.write(f"\n📊 PATH ANALYSIS:")
        self.stdout.write(f"   Total tiles: {analysis['total_tiles']}")
        self.stdout.write(f"   Consistent paths: {len(analysis['consistent_paths'])}")
        self.stdout.write(f"   Inconsistent paths: {len(analysis['inconsistent_paths'])}")
        self.stdout.write(f"   Errors: {len(analysis['errors'])}")
        
        if analysis['path_patterns']:
            self.stdout.write(f"\n📁 Path patterns found:")
            for pattern, count in sorted(analysis['path_patterns'].items()):
                self.stdout.write(f"   {pattern}: {count} tiles")
        
        if analysis['inconsistent_paths']:
            self.stdout.write(f"\n⚠️  Inconsistent paths:")
            for item in analysis['inconsistent_paths'][:5]:  # Show first 5
                self.stdout.write(f"   Current: {item['current']['key']}")
                self.stdout.write(f"   Expected: {item['expected']}")
                self.stdout.write("")
            
            if len(analysis['inconsistent_paths']) > 5:
                self.stdout.write(f"   ... and {len(analysis['inconsistent_paths']) - 5} more")
        
        if analysis['errors']:
            self.stdout.write(f"\n❌ Path parsing errors:")
            for error in analysis['errors'][:5]:  # Show first 5
                self.stdout.write(f"   {error['key']}: {error['error']}")
    
    def _fix_tile_paths(self, inconsistent_paths, options):
        """Fix inconsistent tile paths"""
        if options['dry_run']:
            self.stdout.write(f"\n🔄 DRY RUN - Would fix {len(inconsistent_paths)} paths:")
            for item in inconsistent_paths[:3]:  # Show first 3
                self.stdout.write(f"   Move: {item['current']['key']}")
                self.stdout.write(f"   To:   {item['expected']}")
                self.stdout.write("")
            return
        
        self.stdout.write(f"\n🔧 Fixing {len(inconsistent_paths)} inconsistent paths...")
        
        fixed_count = 0
        failed_count = 0
        
        for item in inconsistent_paths:
            try:
                current_key = item['current']['key']
                expected_key = item['expected']
                
                # Copy object to new location
                self.s3_client.copy_object(
                    Bucket=self.bucket_name,
                    CopySource={'Bucket': self.bucket_name, 'Key': current_key},
                    Key=expected_key
                )
                
                # Delete old object
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=current_key
                )
                
                fixed_count += 1
                if options['verbose']:
                    self.stdout.write(f"   ✅ Fixed: {current_key} → {expected_key}")
                
            except Exception as e:
                failed_count += 1
                self.stdout.write(f"   ❌ Failed to fix {item['current']['key']}: {e}")
        
        self.stdout.write(f"\n📊 Fix results:")
        self.stdout.write(f"   Fixed: {fixed_count}")
        self.stdout.write(f"   Failed: {failed_count}")
        
        if fixed_count > 0:
            self.stdout.write(self.style.SUCCESS("✅ Tile paths have been fixed!"))
