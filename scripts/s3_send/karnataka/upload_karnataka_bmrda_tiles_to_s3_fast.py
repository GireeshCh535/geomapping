#!/usr/bin/env python3
"""
Fast S3 upload script for Karnataka BMRDA master plan tiles
Uploads all BMRDA tile sets to S3 with proper mapping and deletion of existing files
"""

import os
import sys
import boto3
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError, NoCredentialsError
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from django.conf import settings

# Configure enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class FastKarnatakaBMRDATilesUploader:
    """
    Fast uploader for Karnataka BMRDA master plan tiles to S3
    """
    
    def __init__(self, delete_existing=True):
        self.s3_client = self.get_s3_client()
        self.s3_bucket = 'gis-portal-layers'
        self.s3_region = 'ap-south-1'
        self.delete_existing = delete_existing
        
        # Local tile directories and their S3 mappings
        self.folder_mappings = {
            # 'anekal_masterplan_tiles': 'karnataka/bengaluru/bengaluru_anekal_masterplan',
            # 'hosakote_masterplan_tiles': 'karnataka/bengaluru/bengaluru_hosakote_masterplan',
            # 'chikkaballapura_masterplan_tiles': 'karnataka/bengaluru/bengaluru_chikkaballapura_masterplan',
            'nelamangala_masterplan_tiles': 'karnataka/bengaluru/bengaluru_nelamangala_masterplan'
        }
        
        logger.info("Karnataka BMRDA Tiles Uploader initialized")
        logger.info(f"S3 Bucket: {self.s3_bucket}")
        logger.info(f"S3 Region: {self.s3_region}")
        logger.info(f"Delete existing files: {self.delete_existing}")
    
    def get_s3_client(self):
        """Get S3 client with proper credentials"""
        try:
            return boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
        except Exception as e:
            logger.error(f"❌ Error creating S3 client: {e}")
            raise
    
    def get_existing_s3_objects(self, prefix):
        """Get set of existing S3 object keys under a prefix"""
        logger.info(f"🔍 Checking existing objects under prefix: {prefix}")
        
        try:
            existing_keys = set()
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=prefix)

            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        existing_keys.add(obj['Key'])

            logger.info(f"📊 Found {len(existing_keys)} existing objects under prefix: {prefix}")
            return existing_keys

        except Exception as e:
            logger.error(f"❌ Error listing existing objects under prefix {prefix}: {e}")
            return set()

    def delete_s3_prefix(self, prefix):
        """Delete all objects under a given S3 prefix"""
        logger.info(f"🗑️  Deleting existing objects under prefix: {prefix}")
        
        try:
            # List all objects with the prefix
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=prefix)
            
            objects_to_delete = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects_to_delete.append({'Key': obj['Key']})
            
            if objects_to_delete:
                # Delete objects in batches of 1000 (S3 limit)
                batch_size = 1000
                for i in range(0, len(objects_to_delete), batch_size):
                    batch = objects_to_delete[i:i + batch_size]
                    response = self.s3_client.delete_objects(
                        Bucket=self.s3_bucket,
                        Delete={'Objects': batch}
                    )
                    
                    deleted_count = len(response.get('Deleted', []))
                    logger.info(f"Deleted {deleted_count} objects from batch {i//batch_size + 1}")
                
                logger.info(f"✅ Successfully deleted {len(objects_to_delete)} objects under prefix: {prefix}")
            else:
                logger.info(f"No existing objects found under prefix: {prefix}")
                
        except ClientError as e:
            logger.error(f"❌ Error deleting objects under prefix {prefix}: {e}")
            raise
    
    def upload_file_to_s3(self, local_path, s3_key):
        """Upload a single file to S3"""
        try:
            self.s3_client.upload_file(
                local_path,
                self.s3_bucket,
                s3_key,
                ExtraArgs={
                    'StorageClass': 'STANDARD_IA',
                    'ContentType': 'image/png'
                }
            )
            return True
        except Exception as e:
            logger.error(f"❌ Error uploading {local_path} to {s3_key}: {e}")
            return False
    
    def upload_directory_to_s3(self, local_dir, s3_prefix):
        """Upload an entire directory to S3"""
        local_path = Path(local_dir)
        
        if not local_path.exists():
            logger.warning(f"⚠️  Local directory does not exist: {local_path}")
            return 0
        
        # Handle existing files based on delete_existing flag
        existing_s3_keys = set()
        if self.delete_existing:
            # Delete existing objects under this prefix
            self.delete_s3_prefix(s3_prefix)
        else:
            # Get existing S3 objects to skip them
            existing_s3_keys = self.get_existing_s3_objects(s3_prefix)
        
        # Find all PNG files in the directory
        png_files = list(local_path.rglob("*.png"))
        logger.info(f"📊 Found {len(png_files)} PNG files in {local_dir}")
        
        if not png_files:
            logger.warning(f"⚠️  No PNG files found in {local_dir}")
            return 0
        
        # Filter out files that already exist in S3 (if not deleting)
        files_to_upload = []
        skipped_count = 0
        
        for png_file in png_files:
            relative_path = png_file.relative_to(local_path)
            s3_key = f"{s3_prefix}/{relative_path}"
            
            if not self.delete_existing and s3_key in existing_s3_keys:
                skipped_count += 1
            else:
                files_to_upload.append(png_file)
        
        logger.info(f"📤 Files to upload: {len(files_to_upload)}")
        logger.info(f"⏭️  Files to skip (already exist): {skipped_count}")
        
        if not files_to_upload:
            logger.info("All files already exist in S3, nothing to upload")
            return 0
        
        # Upload files using ThreadPoolExecutor for parallel processing
        uploaded_count = 0
        failed_count = 0
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit upload tasks for files that need to be uploaded
            future_to_file = {}
            for png_file in files_to_upload:
                # Calculate S3 key
                relative_path = png_file.relative_to(local_path)
                s3_key = f"{s3_prefix}/{relative_path}"
                
                future = executor.submit(self.upload_file_to_s3, str(png_file), s3_key)
                future_to_file[future] = str(png_file)
            
            # Process completed uploads
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    success = future.result()
                    if success:
                        uploaded_count += 1
                        if uploaded_count % 100 == 0:
                            logger.info(f"Uploaded {uploaded_count} files from {local_dir}...")
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"❌ Error uploading {file_path}: {e}")
                    failed_count += 1
        
        logger.info(f"Completed upload for {local_dir}: {uploaded_count} successful, {failed_count} failed, {skipped_count} skipped")
        return uploaded_count
    
    def upload_all_tiles(self):
        """Upload all BMRDA tile sets to S3"""
        logger.info("Starting upload of all Karnataka BMRDA master plan tiles")
        
        total_uploaded = 0
        
        for local_dir, s3_prefix in self.folder_mappings.items():
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing: {local_dir}")
            logger.info(f"S3 Prefix: {s3_prefix}")
            logger.info(f"{'='*60}")
            
            try:
                uploaded_count = self.upload_directory_to_s3(local_dir, s3_prefix)
                total_uploaded += uploaded_count
                logger.info(f"✅ Successfully uploaded {uploaded_count} files for {local_dir}")
                
            except Exception as e:
                logger.error(f"❌ Error uploading {local_dir}: {e}")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"UPLOAD COMPLETED")
        logger.info(f"Total files uploaded: {total_uploaded}")
        logger.info(f"{'='*60}")
        
        return total_uploaded

def main():
    """Main function"""
    logger.info("Starting Karnataka BMRDA tiles upload to S3")
    
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

        uploader = FastKarnatakaBMRDATilesUploader(delete_existing=delete_existing)
        total_uploaded = uploader.upload_all_tiles()
        
        logger.info(f"🎉 Karnataka BMRDA tiles upload completed! Total files: {total_uploaded}")
        
    except KeyboardInterrupt:
        logger.info("Upload cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Error during upload: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
