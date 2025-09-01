#!/usr/bin/env python3
"""
Script to upload Warangal tiles from local folders to S3
Maps local folders to S3 paths and handles deletion/overwrite of existing files
OPTIMIZED FOR FAST UPLOADS with parallel processing
"""

import os
import sys
import boto3
import glob
from pathlib import Path
import logging
from botocore.exceptions import ClientError, NoCredentialsError
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from botocore.config import Config

# Add Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
import django
django.setup()

from django.conf import settings

# Configure enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class FastWarangalTilesUploader:
    """
    Fast upload Warangal tiles from local folders to S3 with parallel processing
    """
    
    def __init__(self, max_workers=20, delete_existing=True):
        # S3 Configuration with optimized settings
        self.bucket_name = 'gis-portal-layers'
        self.region = 'ap-south-1'
        self.max_workers = max_workers
        self.delete_existing = delete_existing
        
        # Optimized S3 client configuration
        s3_config = Config(
            region_name=self.region,
            retries={'max_attempts': 3, 'mode': 'adaptive'},
            max_pool_connections=50,
            tcp_keepalive=True,
            connect_timeout=10,
            read_timeout=30
        )
        
        # Initialize S3 client with optimized config
        self.s3_client = boto3.client(
            's3',
            config=s3_config,
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        )
        
        # Base local path
        self.local_base_path = Path('warangal_master_plan_tiles')
        
        # Mapping configuration
        self.folder_mappings = {
            'warangal_master_plan_tiles': 'telangana/warangal/warangal_master_plan'
        }
        
        # Statistics with thread safety
        self.stats = {
            'folders_processed': 0,
            'files_uploaded': 0,
            'files_failed': 0,
            'files_deleted': 0,
            'files_skipped': 0,
            'bytes_uploaded': 0
        }
        self.stats_lock = threading.Lock()
        
        logger.info(f"Delete existing files: {self.delete_existing}")
    
    def update_stats(self, key, value):
        """Thread-safe stats update"""
        with self.stats_lock:
            self.stats[key] += value
    
    def test_s3_connection(self):
        """Test S3 connection and bucket access"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"✅ Successfully connected to S3 bucket: {self.bucket_name}")
            return True
        except NoCredentialsError:
            logger.error("❌ AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
            return False
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"❌ Bucket {self.bucket_name} not found")
            elif error_code == '403':
                logger.error(f"❌ Access denied to bucket {self.bucket_name}")
            else:
                logger.error(f"❌ S3 connection error: {e}")
            return False
    
    def get_existing_s3_objects(self, s3_prefix):
        """Get set of existing S3 object keys under a prefix"""
        logger.info(f"🔍 Checking existing objects under prefix: {s3_prefix}")
        
        try:
            existing_keys = set()
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=s3_prefix)

            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        existing_keys.add(obj['Key'])

            logger.info(f"   📊 Found {len(existing_keys)} existing objects under prefix: {s3_prefix}")
            return existing_keys

        except Exception as e:
            logger.error(f"❌ Error listing existing objects under prefix {s3_prefix}: {e}")
            return set()

    def delete_existing_s3_folder(self, s3_prefix):
        """Delete all objects in an S3 folder/prefix with parallel processing"""
        try:
            logger.info(f"🗑️  Deleting existing S3 folder: {s3_prefix}")
            
            # List all objects with the prefix
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=s3_prefix)
            
            objects_to_delete = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects_to_delete.append({'Key': obj['Key']})
            
            if objects_to_delete:
                # Delete objects in batches of 1000 (S3 limit)
                for i in range(0, len(objects_to_delete), 1000):
                    batch = objects_to_delete[i:i+1000]
                    response = self.s3_client.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={'Objects': batch}
                    )
                    
                    deleted_count = len(response.get('Deleted', []))
                    self.update_stats('files_deleted', deleted_count)
                    logger.info(f"   ✅ Deleted {deleted_count} files from {s3_prefix}")
            else:
                logger.info(f"   ℹ️  No existing files found in {s3_prefix}")
                
        except Exception as e:
            logger.error(f"❌ Error deleting S3 folder {s3_prefix}: {e}")
    
    def upload_file_to_s3(self, local_file_path, s3_key):
        """Upload a single file to S3 with optimized settings"""
        try:
            # Determine content type based on file extension
            content_type = self.get_content_type(local_file_path)
            
            # Upload file with optimized settings
            self.s3_client.upload_file(
                local_file_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': content_type,
                    'CacheControl': 'no-cache, no-store, must-revalidate',
                    'StorageClass': 'STANDARD_IA'  # Faster access for frequently accessed tiles
                }
            )
            
            file_size = os.path.getsize(local_file_path)
            self.update_stats('files_uploaded', 1)
            self.update_stats('bytes_uploaded', file_size)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to upload {local_file_path} to {s3_key}: {e}")
            self.update_stats('files_failed', 1)
            return False
    
    def get_content_type(self, file_path):
        """Get MIME content type based on file extension"""
        ext = Path(file_path).suffix.lower()
        content_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.mvt': 'application/vnd.mapbox-vector-tile',
            '.json': 'application/json',
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.xml': 'application/xml',
            '.txt': 'text/plain'
        }
        return content_types.get(ext, 'application/octet-stream')
    
    def upload_files_parallel(self, file_tasks):
        """Upload files in parallel using ThreadPoolExecutor"""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all upload tasks
            future_to_file = {
                executor.submit(self.upload_file_to_s3, local_path, s3_key): (local_path, s3_key)
                for local_path, s3_key in file_tasks
            }
            
            # Process completed uploads
            completed = 0
            for future in as_completed(future_to_file):
                local_path, s3_key = future_to_file[future]
                try:
                    success = future.result()
                    completed += 1
                    
                    # Log progress every 500 files
                    if completed % 500 == 0:
                        logger.info(f"🎉    📤 Uploaded {completed}/{len(file_tasks)} files...")
                        
                except Exception as e:
                    logger.error(f"❌ Exception in parallel upload: {e}")
    
    def upload_folder_to_s3(self, local_folder, s3_prefix):
        """Upload all files from a local folder to S3 with parallel processing"""
        logger.info(f"📁 Processing folder: {local_folder} -> {s3_prefix}")
        
        # Handle existing files based on delete_existing flag
        existing_s3_keys = set()
        if self.delete_existing:
            # Delete existing S3 folder first
            self.delete_existing_s3_folder(s3_prefix)
        else:
            # Get existing S3 objects to skip them
            existing_s3_keys = self.get_existing_s3_objects(s3_prefix)
        
        # Find all files in the local folder
        local_path = Path(local_folder)
        if not local_path.exists():
            logger.error(f"❌ Local folder does not exist: {local_folder}")
            return False
        
        # Get all files recursively with optimized patterns
        all_files = []
        file_patterns = ['**/*.png', '**/*.mvt', '**/*.json', '**/*.html']
        
        for pattern in file_patterns:
            all_files.extend(local_path.glob(pattern))
        
        if not all_files:
            logger.warning(f"⚠️  ⚠️  No files found in {local_folder}")
            return False
        
        logger.info(f"   📊 Found {len(all_files)} files to upload")
        
        # Prepare upload tasks and filter out existing files
        file_tasks = []
        skipped_count = 0
        
        for file_path in all_files:
            # Calculate relative path from local folder
            relative_path = file_path.relative_to(local_path)
            
            # Create S3 key
            s3_key = f"{s3_prefix}/{relative_path}"
            
            if not self.delete_existing and s3_key in existing_s3_keys:
                skipped_count += 1
                self.update_stats('files_skipped', 1)
            else:
                file_tasks.append((str(file_path), s3_key))
        
        logger.info(f"   📤 Files to upload: {len(file_tasks)}")
        logger.info(f"   ⏭️  Files to skip (already exist): {skipped_count}")
        
        if not file_tasks:
            logger.info("   ℹ️  All files already exist in S3, nothing to upload")
            return True
        
        # Upload files in parallel
        logger.info(f"   🚀 Starting parallel upload with {self.max_workers} workers...")
        self.upload_files_parallel(file_tasks)
        
        return True
    
    def process_all_mappings(self):
        """Process all folder mappings with parallel processing"""
        logger.info("🚀 Starting FAST Warangal tiles upload to S3")
        logger.info(f"⚡ Using {self.max_workers} parallel workers")
        logger.info("=" * 60)
        
        # Test S3 connection first
        if not self.test_s3_connection():
            return False
        
        # Process each mapping
        for local_folder, s3_prefix in self.folder_mappings.items():
            local_path = self.local_base_path
            
            if local_path.exists():
                logger.info(f"\n📂 Processing: {local_folder}")
                success = self.upload_folder_to_s3(str(local_path), s3_prefix)
                if success:
                    self.update_stats('folders_processed', 1)
                    logger.info(f"✅ Completed: {local_folder}")
                else:
                    logger.error(f"❌ Failed: {local_folder}")
            else:
                logger.warning(f"⚠️  ⚠️  Local folder not found: {local_path}")
        
        return True
    
    def print_summary(self):
        """Print upload summary"""
        logger.info("\n" + "=" * 60)
        logger.info("📊 FAST UPLOAD SUMMARY")
        logger.info("=" * 60)
        logger.info(f"📁 Folders processed: {self.stats['folders_processed']}")
        logger.info(f"📤 Files uploaded: {self.stats['files_uploaded']}")
        logger.info(f"🗑️  Files deleted: {self.stats['files_deleted']}")
        logger.info(f"⏭️  Files skipped: {self.stats['files_skipped']}")
        logger.info(f"❌ Files failed: {self.stats['files_failed']}")
        logger.info(f"💾 Bytes uploaded: {self.stats['bytes_uploaded']}")
        logger.info(f"⚡ Parallel workers used: {self.max_workers}")
        
        if self.stats['files_uploaded'] > 0:
            logger.info("🎉 Fast upload completed successfully!")
        else:
            logger.warning("⚠️  No files were uploaded")

def main():
    """Main function with configurable parallel workers"""
    # You can adjust the number of parallel workers based on your system
    max_workers = int(os.environ.get('MAX_WORKERS', '5'))  # Reduced for memory efficiency
    
    try:
        # Ask user whether to delete existing files
        while True:
            delete_choice = input("\nDo you want to delete existing files in S3 before upload? (y/n): ").lower().strip()
            if delete_choice in ['y', 'yes']:
                delete_existing = True
                logger.info("Will delete existing files before upload")
                break
            elif delete_choice in ['n', 'no']:
                delete_existing = False
                logger.info("Will skip existing files and upload only missing ones")
                break
            else:
                print("Please enter 'y' for yes or 'n' for no")
    
        uploader = FastWarangalTilesUploader(max_workers=max_workers, delete_existing=delete_existing)
        
        success = uploader.process_all_mappings()
        uploader.print_summary()
        
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n⚠️  Upload interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
