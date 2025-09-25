#!/usr/bin/env python3
"""
Upload Bangalore Metro Tiles to S3
Uploads generated metro tiles to S3 bucket with proper organization
"""

import os
import sys
import boto3
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set Django settings
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

class MetroTilesS3Uploader:
    def __init__(self, delete_existing=True):
        self.local_tiles_dir = project_root / "karnataka_bengaluru_metro_tiles"
        self.s3_bucket = 'gis-portal-layers'
        self.s3_prefix = 'karnataka/bengaluru/bengaluru_metro'
        self.delete_existing = delete_existing
        
        # Configure S3 client
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        logger.info("=" * 80)
        logger.info("🚀 BANGALORE METRO TILES S3 UPLOADER INITIALIZED")
        logger.info("=" * 80)
        logger.info(f"📂 Local directory    : {self.local_tiles_dir}")
        logger.info(f"🪣 S3 bucket          : {self.s3_bucket}")
        logger.info(f"📍 S3 prefix          : {self.s3_prefix}")
        logger.info(f"🗑️  Delete existing    : {self.delete_existing}")
        logger.info("=" * 80)
    
    def get_existing_s3_objects(self):
        """Get set of existing S3 object keys"""
        logger.info(f"🔍 Checking existing objects in s3://{self.s3_bucket}/{self.s3_prefix}/")
        
        try:
            existing_keys = set()
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=self.s3_prefix)

            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        existing_keys.add(obj['Key'])

            logger.info(f"📊 Found {len(existing_keys)} existing objects in S3")
            return existing_keys

        except Exception as e:
            logger.error(f"❌ Error listing existing objects: {e}")
            return set()

    def delete_existing_s3_folder(self):
        """Delete existing files in the S3 folder before upload"""
        logger.info(f"🗑️  Deleting existing files in s3://{self.s3_bucket}/{self.s3_prefix}/")
        
        try:
            # List all objects in the prefix
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=self.s3_prefix)
            
            objects_to_delete = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects_to_delete.append({'Key': obj['Key']})
            
            if objects_to_delete:
                # Delete objects in batches of 1000
                for i in range(0, len(objects_to_delete), 1000):
                    batch = objects_to_delete[i:i+1000]
                    self.s3_client.delete_objects(
                        Bucket=self.s3_bucket,
                        Delete={'Objects': batch}
                    )
                logger.info(f"✅ Successfully deleted {len(objects_to_delete)} existing files")
            else:
                logger.info("ℹ️  No existing files found to delete")
                
        except Exception as e:
            logger.error(f"❌ Error deleting existing files: {e}")
    
    def upload_file(self, file_path: Path) -> bool:
        """Upload a single file to S3"""
        try:
            # Calculate S3 key
            relative_path = file_path.relative_to(self.local_tiles_dir)
            s3_key = f"{self.s3_prefix}/{relative_path}"
            
            # Upload file
            self.s3_client.upload_file(
                str(file_path),
                self.s3_bucket,
                s3_key,
                ExtraArgs={
                    'ContentType': 'image/png',
                    'StorageClass': 'STANDARD_IA'
                }
            )
            return True
        except Exception as e:
            print(f"Error uploading {file_path}: {e}")
            return False
    
    def upload_directory_to_s3(self):
        """Upload entire directory to S3 using parallel processing"""
        if not self.local_tiles_dir.exists():
            logger.error(f"❌ Local tiles directory does not exist: {self.local_tiles_dir}")
            return
        
        # Handle existing files based on delete_existing flag
        existing_s3_keys = set()
        if self.delete_existing:
            # Delete existing files first
            self.delete_existing_s3_folder()
        else:
            # Get existing S3 objects to skip them
            existing_s3_keys = self.get_existing_s3_objects()
        
        # Find all PNG files
        png_files = list(self.local_tiles_dir.rglob("*.png"))
        print(f"Found {len(png_files)} PNG files to upload")
        
        if not png_files:
            print("No PNG files found to upload")
            return
        
        # Filter out files that already exist in S3 (if not deleting)
        files_to_upload = []
        skipped_count = 0
        
        for file_path in png_files:
            relative_path = file_path.relative_to(self.local_tiles_dir)
            s3_key = f"{self.s3_prefix}/{relative_path}"
            
            if not self.delete_existing and s3_key in existing_s3_keys:
                skipped_count += 1
            else:
                files_to_upload.append(file_path)
        
        logger.info(f"📤 Files to upload: {len(files_to_upload)}")
        logger.info(f"⏭️  Files to skip (already exist): {skipped_count}")
        
        if not files_to_upload:
            logger.info("✅ All files already exist in S3, nothing to upload")
            return
        
        # Upload files in parallel
        start_time = time.time()
        successful_uploads = 0
        failed_uploads = 0
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit upload tasks for files that need to be uploaded
            future_to_file = {
                executor.submit(self.upload_file, file_path): file_path 
                for file_path in files_to_upload
            }
            
            # Process completed uploads
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    success = future.result()
                    if success:
                        successful_uploads += 1
                    else:
                        failed_uploads += 1
                    
                    # Progress update every 1000 files
                    if (successful_uploads + failed_uploads) % 1000 == 0:
                        elapsed = time.time() - start_time
                        rate = (successful_uploads + failed_uploads) / elapsed
                        progress = successful_uploads + failed_uploads
                        percent = (progress / len(files_to_upload)) * 100
                        logger.info(f"📊 Progress: {progress}/{len(files_to_upload)} files "
                                  f"({percent:.1f}%) | Rate: {rate:.1f} files/sec | "
                                  f"Success: {successful_uploads} | Failed: {failed_uploads}")
                        
                except Exception as e:
                    logger.error(f"❌ Error processing {file_path}: {e}")
                    failed_uploads += 1
        
        end_time = time.time()
        total_time = end_time - start_time
        
        logger.info("\n" + "=" * 80)
        logger.info("📊 UPLOAD SUMMARY - BANGALORE METRO TILES")
        logger.info("=" * 80)
        logger.info(f"📁 Total files found      : {len(png_files)}")
        logger.info(f"⏭️  Files skipped          : {skipped_count}")
        logger.info(f"✅ Files uploaded         : {successful_uploads}")
        logger.info(f"❌ Failed uploads         : {failed_uploads}")
        logger.info(f"⏱️  Total time            : {total_time:.2f} seconds")
        if files_to_upload and total_time > 0:
            avg_rate = len(files_to_upload) / total_time
            logger.info(f"⚡ Average upload rate    : {avg_rate:.1f} files/second")
        logger.info(f"🌐 S3 location           : s3://{self.s3_bucket}/{self.s3_prefix}/")
        logger.info(f"🔗 CloudFront URL        : https://d17yosovmfjm4.cloudfront.net/{self.s3_prefix}/")
        logger.info("=" * 80)

def main():
    """Main function"""
    start_time = datetime.now()
    logger.info("\n" + "🚀" * 20)
    logger.info("🚀 BANGALORE METRO TILES S3 UPLOADER STARTED")
    logger.info(f"🕐 Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("🚀" * 20)
    
    try:
        # Ask user whether to delete existing files
        while True:
            delete_choice = input("\n❓ Do you want to delete existing files in S3 before upload? (y/n): ").lower().strip()
            if delete_choice in ['y', 'yes']:
                delete_existing = True
                logger.info("🗑️  User selected: DELETE existing files before upload")
                break
            elif delete_choice in ['n', 'no']:
                delete_existing = False
                logger.info("⏭️  User selected: SKIP existing files, upload only missing ones")
                break
            else:
                print("⚠️  Please enter 'y' for yes or 'n' for no")

        uploader = MetroTilesS3Uploader(delete_existing=delete_existing)
        uploader.upload_directory_to_s3()
        
        end_time = datetime.now()
        total_duration = end_time - start_time
        logger.info("\n" + "🎉" * 20)
        logger.info("🎉 BANGALORE METRO TILES UPLOAD COMPLETED SUCCESSFULLY!")
        logger.info(f"🕐 End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"⏱️  Total duration: {total_duration}")
        logger.info("🎉" * 20)

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Upload cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n❌ Critical error during upload: {e}")
        logger.error("💡 Please check your configuration and try again")
        sys.exit(1)

if __name__ == "__main__":
    main()
