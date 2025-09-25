#!/usr/bin/env python3
"""
Fast S3 Upload Script for Andhra Pradesh Master Plan Tiles
Uploads Amaravati and Visakhapatnam tiles to S3 with parallel processing
"""

import os
import boto3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError
import threading

# Add Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
import django
django.setup()

from django.conf import settings

# S3 Configuration
S3_BUCKET = 'gis-portal-layers'
S3_REGION = 'ap-south-1'

# Upload mappings
UPLOAD_MAPPINGS = {
    'amaravati_master_plan_tiles': 'andhra-pradesh/amaravati/amaravati_master_plan/',
    'visakhapatnam_master_plan_tiles': 'andhra-pradesh/visakhapatnam/visakhapatnam_master_plan/'
}

# Threading lock for progress tracking
progress_lock = threading.Lock()
uploaded_count = 0
skipped_count = 0
total_files = 0
delete_existing = True  # Global variable

def get_s3_client():
    """Get S3 client with credentials from Django settings"""
    try:
        # Initialize S3 client with Django settings
        s3_client = boto3.client(
            's3',
            region_name=S3_REGION,
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        )
        
        # Test the connection
        s3_client.head_bucket(Bucket=S3_BUCKET)
        print(f"✅ Connected to S3 bucket: {S3_BUCKET:,}")
        return s3_client
    except NoCredentialsError:
        print("❌ AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in Django settings")
        return None
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"❌ Bucket {S3_BUCKET:,} not found!")
        elif error_code == '403':
            print(f"❌ Access denied to bucket {S3_BUCKET:,}. Check your credentials.")
        else:
            print(f"❌ Error connecting to S3: {e}")
        return None
    except Exception as e:
        print(f"❌ Error creating S3 client: {e}")
        return None

def get_existing_s3_objects(s3_client, s3_prefix: str):
    """Get set of existing S3 object keys under a prefix"""
    try:
        print(f"🔍 Checking existing objects under prefix: {s3_prefix}")
        
        existing_keys = set()
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=s3_prefix)

        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    existing_keys.add(obj['Key'])

        print(f"   📊 Found {len(existing_keys)} existing objects under prefix: {s3_prefix}")
        return existing_keys

    except Exception as e:
        print(f"❌ Error listing existing objects under prefix {s3_prefix}: {e}")
        return set()

def delete_existing_s3_folder(s3_client, s3_prefix: str):
    """Delete all objects in an S3 folder/prefix"""
    try:
        print(f"🗑️  Deleting existing S3 folder: {s3_prefix}")
        
        # List all objects with the prefix
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=s3_prefix)
        
        objects_to_delete = []
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    objects_to_delete.append({'Key': obj['Key']})
        
        if objects_to_delete:
            # Delete objects in batches of 1000 (S3 limit)
            for i in range(0, len(objects_to_delete), 1000):
                batch = objects_to_delete[i:i+1000]
                response = s3_client.delete_objects(
                    Bucket=S3_BUCKET,
                    Delete={'Objects': batch}
                )
                
                deleted_count = len(response.get('Deleted', []))
                print(f"   ✅ Deleted {deleted_count} files from {s3_prefix}")
        else:
            print(f"   ℹ️  No existing files found in {s3_prefix}")
            
    except Exception as e:
        print(f"❌ Error deleting S3 folder {s3_prefix}: {e}")

def upload_file_to_s3(s3_client, local_path: Path, s3_key: str):
    """Upload a single file to S3"""
    global uploaded_count
    
    try:
        # Upload file (no need to check if exists since we delete first)
        s3_client.upload_file(
            str(local_path),
            S3_BUCKET,
            s3_key,
            ExtraArgs={
                'StorageClass': 'STANDARD_IA',
                'ContentType': 'image/png'
            }
        )
        
        with progress_lock:
            uploaded_count += 1
            if uploaded_count % 100 == 0:
                print(f"⏳ Progress: {uploaded_count}/{total_files} files uploaded")
        
        return True
        
    except Exception as e:
        print(f"❌ Error uploading {local_path}: {e}")
        return False

def get_all_png_files(directory: Path):
    """Get all PNG files in directory recursively"""
    png_files = []
    for file_path in directory.rglob("*.png"):
        png_files.append(file_path)
    return png_files

def upload_directory_to_s3(s3_client, local_dir: Path, s3_prefix: str):
    """Upload all PNG files from a directory to S3"""
    global total_files
    
    print(f"\n📁 Processing directory: {local_dir}")
    print(f"🎯 S3 destination: {s3_prefix}")
    
    if not local_dir.exists():
        print(f"❌ Directory not found: {local_dir}")
        return False
    
    # Handle existing files based on delete_existing flag
    existing_s3_keys = set()
    if delete_existing:
        # Delete existing files in S3 first
        delete_existing_s3_folder(s3_client, s3_prefix)
    else:
        # Get existing S3 objects to skip them
        existing_s3_keys = get_existing_s3_objects(s3_client, s3_prefix)
    
    # Get all PNG files
    png_files = get_all_png_files(local_dir)
    if not png_files:
        print(f"❌ No PNG files found in {local_dir}")
        return False
    
    print(f"📊 Found {len(png_files)} PNG files to upload")
    
    # Update total files count
    with progress_lock:
        total_files += len(png_files)
    
    # Prepare upload tasks and filter out existing files
    upload_tasks = []
    local_skipped_count = 0
    
    for file_path in png_files:
        # Calculate relative path from local directory
        relative_path = file_path.relative_to(local_dir)
        s3_key = f"{s3_prefix}{relative_path}"
        
        if not delete_existing and s3_key in existing_s3_keys:
            local_skipped_count += 1
        else:
            upload_tasks.append((file_path, s3_key))
    
    print(f"📤 Files to upload: {len(upload_tasks)}")
    print(f"⏭️  Files to skip (already exist): {local_skipped_count}")
    
    if not upload_tasks:
        print(f"ℹ️  All files already exist in S3, nothing to upload")
        with progress_lock:
            global skipped_count
            skipped_count += local_skipped_count
        return True
    
    # Update global skipped count
    with progress_lock:
        skipped_count += local_skipped_count
    
    # Upload files in parallel
    successful_uploads = 0
    failed_uploads = 0
    
    with ThreadPoolExecutor(max_workers=5) as executor:  # Reduced for memory efficiency
        # Submit all upload tasks
        future_to_task = {
            executor.submit(upload_file_to_s3, s3_client, file_path, s3_key): (file_path, s3_key)
            for file_path, s3_key in upload_tasks
        }
        
        # Process completed tasks
        for future in as_completed(future_to_task):
            file_path, s3_key = future_to_task[future]
            try:
                success = future.result()
                if success:
                    successful_uploads += 1
                else:
                    failed_uploads += 1
            except Exception as e:
                print(f"❌ Exception uploading {file_path}: {e}")
                failed_uploads += 1
    
    print(f"✅ Upload complete for {local_dir}")
    print(f"   Success: {successful_uploads}")
    print(f"   Failed: {failed_uploads}")
    print(f"   Skipped: {local_skipped_count}")
    
    return failed_uploads == 0

def main():
    """Main upload function"""
    global delete_existing
    
    print("🚀 Andhra Pradesh Master Plan Tiles S3 Upload")
    print("=" * 50)
    
    try:
        # Ask user whether to delete existing files
        while True:
            delete_choice = input("\nDo you want to delete existing files in S3 before upload? (y/n): ").lower().strip()
            if delete_choice in ['y', 'yes']:
                delete_existing = True
                print("Will delete existing files before upload")
                break
            elif delete_choice in ['n', 'no']:
                delete_existing = False
                print("Will skip existing files and upload only missing ones")
                break
            else:
                print("Please enter 'y' for yes or 'n' for no")
    except KeyboardInterrupt:
        print("\n⚠️  Upload cancelled by user")
        return False
    
    # Get S3 client
    s3_client = get_s3_client()
    if not s3_client:
        return False
    
    # Get current directory
    current_dir = Path.cwd()
    print(f"📂 Working directory: {current_dir}")
    
    start_time = time.time()
    all_success = True
    
    # Upload each directory
    for local_dir_name, s3_prefix in UPLOAD_MAPPINGS.items():
        local_dir = current_dir / local_dir_name
        
        if not local_dir.exists():
            print(f"❌ Directory not found: {local_dir}")
            all_success = False
            continue
        
        success = upload_directory_to_s3(s3_client, local_dir, s3_prefix)
        if not success:
            all_success = False
    
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "=" * 50)
    print("📊 Upload Summary")
    print("=" * 50)
    print(f"⏱️  Total time: {duration:.2f} seconds")
    print(f"📁 Total files uploaded: {uploaded_count}")
    print(f"⏭️  Total files skipped: {skipped_count}")
    
    if all_success:
        print("✅ All uploads completed successfully!")
        print("\n🌐 Your tiles are now available at:")
        for local_dir_name, s3_prefix in UPLOAD_MAPPINGS.items():
            print(f"   {s3_prefix} -> s3://{S3_BUCKET:,}/{s3_prefix}")
    else:
        print("❌ Some uploads failed. Check the logs above.")
    
    return all_success

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Upload cancelled by user")
        exit(0)
