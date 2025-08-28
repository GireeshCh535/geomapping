#!/usr/bin/env python3
"""
Fast S3 upload script for Karnataka Bengaluru tiles
Uploads highways, STRR, and workspace tile sets to S3 with proper mapping and deletion of existing files
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

class FastKarnatakaBengaluruTilesUploader:
    """
    Fast uploader for Karnataka Bengaluru tiles to S3
    """

    def __init__(self):
        self.s3_client = self.get_s3_client()
        self.s3_bucket = 'gis-portal-layers'
        self.s3_region = 'ap-south-1'

        # Local tile directories and their S3 mappings
        self.folder_mappings = {
            'karnataka_bengaluru_highways_tiles': 'karnataka/bengaluru/bengaluru_highways',
            'karnataka_bengaluru_strr_tiles': 'karnataka/bengaluru/bengaluru_strr',
            'karnataka_bengaluru_workspace_tiles': 'karnataka/bengaluru/bengaluru_workspaces'
        }

        logger.info("Karnataka Bengaluru Tiles Uploader initialized")
        logger.info(f"S3 Bucket: {self.s3_bucket}")
        logger.info(f"S3 Region: {self.s3_region}")

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

    def upload_directory_to_s3(self, local_dir, s3_prefix):
        """Upload an entire directory to S3"""
        local_path = Path(local_dir)

        if not local_path.exists():
            logger.warning(f"Local directory does not exist: {local_path}")
            return 0

        # Delete existing objects under this prefix
        self.delete_s3_prefix(s3_prefix)

        # Find all PNG files in the directory
        png_files = list(local_path.rglob("*.png"))
        logger.info(f"Found {len(png_files)} PNG files in {local_dir}")

        if not png_files:
            logger.warning(f"No PNG files found in {local_dir}")
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
                    logger.error(f"Error uploading {file_path}: {e}")
                    failed_count += 1

        logger.info(f"Completed upload for {local_dir}: {uploaded_count} successful, {failed_count} failed")
        return uploaded_count

    def upload_all_tiles(self):
        """Upload all Karnataka Bengaluru tile sets to S3"""
        logger.info("Starting upload of all Karnataka Bengaluru tiles")

        total_uploaded = 0

        for local_dir, s3_prefix in self.folder_mappings.items():
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing: {local_dir}")
            logger.info(f"S3 Prefix: {s3_prefix}")
            logger.info(f"{'='*60}")

            try:
                uploaded_count = self.upload_directory_to_s3(local_dir, s3_prefix)
                total_uploaded += uploaded_count
                logger.info(f"Successfully uploaded {uploaded_count} files for {local_dir}")

            except Exception as e:
                logger.error(f"Error uploading {local_dir}: {e}")

        logger.info(f"\n{'='*60}")
        logger.info(f"UPLOAD COMPLETED")
        logger.info(f"Total files uploaded: {total_uploaded}")
        logger.info(f"{'='*60}")

        return total_uploaded

def main():
    """Main function"""
    logger.info("Starting Karnataka Bengaluru tiles upload to S3")

    try:
        uploader = FastKarnatakaBengaluruTilesUploader()
        total_uploaded = uploader.upload_all_tiles()

        logger.info(f"Karnataka Bengaluru tiles upload completed! Total files: {total_uploaded}")

    except Exception as e:
        logger.error(f"Error during upload: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
