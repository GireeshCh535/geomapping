#!/usr/bin/env python3
"""
Upload Bangalore Metro Tiles to S3
Uploads generated metro tiles to S3 bucket with proper organization
"""

import os
import sys
import boto3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')

import django
django.setup()

from django.conf import settings

class MetroTilesS3Uploader:
    def __init__(self):
        self.local_tiles_dir = project_root / "karnataka_bengaluru_metro_tiles"
        self.s3_bucket = 'gis-portal-layers'
        self.s3_prefix = 'karnataka/bengaluru/bengaluru_metro'
        
        # Configure S3 client
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        print(f"Local tiles directory: {self.local_tiles_dir}")
        print(f"S3 bucket: {self.s3_bucket}")
        print(f"S3 prefix: {self.s3_prefix}")
    
    def delete_existing_s3_folder(self):
        """Delete existing files in the S3 folder before upload"""
        print(f"Deleting existing files in s3://{self.s3_bucket}/{self.s3_prefix}/")
        
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
                print(f"Deleted {len(objects_to_delete)} existing files")
            else:
                print("No existing files to delete")
                
        except Exception as e:
            print(f"Error deleting existing files: {e}")
    
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
            print(f"Error: Local tiles directory {self.local_tiles_dir} does not exist")
            return
        
        # Delete existing files first
        self.delete_existing_s3_folder()
        
        # Find all PNG files
        png_files = list(self.local_tiles_dir.rglob("*.png"))
        print(f"Found {len(png_files)} PNG files to upload")
        
        if not png_files:
            print("No PNG files found to upload")
            return
        
        # Upload files in parallel
        start_time = time.time()
        successful_uploads = 0
        failed_uploads = 0
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all upload tasks
            future_to_file = {
                executor.submit(self.upload_file, file_path): file_path 
                for file_path in png_files
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
                        print(f"Progress: {successful_uploads + failed_uploads}/{len(png_files)} "
                              f"({rate:.1f} files/sec)")
                        
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    failed_uploads += 1
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n=== UPLOAD SUMMARY ===")
        print(f"Total files: {len(png_files)}")
        print(f"Successful uploads: {successful_uploads}")
        print(f"Failed uploads: {failed_uploads}")
        print(f"Total time: {total_time:.2f} seconds")
        print(f"Average rate: {len(png_files)/total_time:.1f} files/second")
        print(f"S3 location: s3://{self.s3_bucket}/{self.s3_prefix}/")

def main():
    """Main function"""
    print("=== Bangalore Metro Tiles S3 Uploader ===")
    
    uploader = MetroTilesS3Uploader()
    uploader.upload_directory_to_s3()
    
    print("Upload completed!")

if __name__ == "__main__":
    main()
