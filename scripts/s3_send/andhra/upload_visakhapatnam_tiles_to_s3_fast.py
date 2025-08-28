#!/usr/bin/env python3
"""
Fast S3 upload script for Visakhapatnam master plan tiles
Uploads Visakhapatnam tile set to S3 with proper mapping and deletion of existing files
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FastVisakhapatnamTilesUploader:
    """
    Fast uploader for Visakhapatnam master plan tiles to S3
    """
    
    def __init__(self):
        self.s3_client = self.get_s3_client()
        self.s3_bucket = 'gis-portal-layers'
        self.s3_region = 'ap-south-1'
        
        # Local tile directory and S3 mapping
        self.local_dir = 'visakhapatnam_master_plan_tiles'
        self.s3_prefix = 'andhra-pradesh/visakhapatnam/visakhapatnam_master_plan'
        
        logger.info("Visakhapatnam Tiles Uploader initialized")
        logger.info(f"S3 Bucket: {self.s3_bucket}")
        logger.info(f"S3 Region: {self.s3_region}")
        logger.info(f"Local Directory: {self.local_dir}")
        logger.info(f"S3 Prefix: {self.s3_prefix}")
    
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
            logger.error(f"Error creating S3 client: {e}")
            raise
    
    def delete_s3_prefix(self, prefix):
        """Delete all objects under a given S3 prefix"""
        logger.info(f"Deleting existing objects under prefix: {prefix}")
        
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
                
                logger.info(f"Successfully deleted {len(objects_to_delete)} objects under prefix: {prefix}")
            else:
                logger.info(f"No existing objects found under prefix: {prefix}")
                
        except ClientError as e:
            logger.error(f"Error deleting objects under prefix {prefix}: {e}")
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
            logger.error(f"Error uploading {local_path} to {s3_key}: {e}")
            return False
    
    def upload_tiles_to_s3(self):
        """Upload Visakhapatnam tiles to S3"""
        local_path = Path(self.local_dir)
        
        if not local_path.exists():
            logger.error(f"Local directory does not exist: {local_path}")
            return 0
        
        # Delete existing objects under this prefix
        self.delete_s3_prefix(self.s3_prefix)
        
        # Find all PNG files in the directory
        png_files = list(local_path.rglob("*.png"))
        logger.info(f"Found {len(png_files)} PNG files in {self.local_dir}")
        
        if not png_files:
            logger.warning(f"No PNG files found in {self.local_dir}")
            return 0
        
        # Upload files using ThreadPoolExecutor for parallel processing
        uploaded_count = 0
        failed_count = 0
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit upload tasks
            future_to_file = {}
            for png_file in png_files:
                # Calculate S3 key
                relative_path = png_file.relative_to(local_path)
                s3_key = f"{self.s3_prefix}/{relative_path}"
                
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
                            logger.info(f"Uploaded {uploaded_count} files from {self.local_dir}...")
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Error uploading {file_path}: {e}")
                    failed_count += 1
        
        logger.info(f"Completed upload for {self.local_dir}: {uploaded_count} successful, {failed_count} failed")
        return uploaded_count

def main():
    """Main function"""
    logger.info("Starting Visakhapatnam tiles upload to S3")
    
    try:
        uploader = FastVisakhapatnamTilesUploader()
        uploaded_count = uploader.upload_tiles_to_s3()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"UPLOAD COMPLETED")
        logger.info(f"Total files uploaded: {uploaded_count}")
        logger.info(f"S3 Path: s3://gis-portal-layers/{uploader.s3_prefix}/")
        logger.info(f"CloudFront URL: https://d17yosovmfjm4.cloudfront.net/{uploader.s3_prefix}/")
        logger.info(f"{'='*60}")
        
        logger.info(f"Visakhapatnam tiles upload completed! Total files: {uploaded_count}")
        
    except Exception as e:
        logger.error(f"Error during upload: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
