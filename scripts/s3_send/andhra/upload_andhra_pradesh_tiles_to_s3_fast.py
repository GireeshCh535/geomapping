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
total_files = 0

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
        print(f"✅ Connected to S3 bucket: {S3_BUCKET}")
        return s3_client
    except NoCredentialsError:
        print("❌ AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in Django settings")
        return None
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"❌ Bucket {S3_BUCKET} not found!")
        elif error_code == '403':
            print(f"❌ Access denied to bucket {S3_BUCKET}. Check your credentials.")
        else:
            print(f"❌ Error connecting to S3: {e}")
        return None
    except Exception as e:
        print(f"❌ Error creating S3 client: {e}")
        return None

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
    
    # Delete existing files in S3 first
    delete_existing_s3_folder(s3_client, s3_prefix)
    
    # Get all PNG files
    png_files = get_all_png_files(local_dir)
    if not png_files:
        print(f"❌ No PNG files found in {local_dir}")
        return False
    
    print(f"📊 Found {len(png_files)} PNG files to upload")
    
    # Update total files count
    with progress_lock:
        total_files += len(png_files)
    
    # Prepare upload tasks
    upload_tasks = []
    for file_path in png_files:
        # Calculate relative path from local directory
        relative_path = file_path.relative_to(local_dir)
        s3_key = f"{s3_prefix}{relative_path}"
        upload_tasks.append((file_path, s3_key))
    
    # Upload files in parallel
    successful_uploads = 0
    failed_uploads = 0
    
    with ThreadPoolExecutor(max_workers=20) as executor:
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
    
    return failed_uploads == 0

def main():
    """Main upload function"""
    print("🚀 Andhra Pradesh Master Plan Tiles S3 Upload")
    print("=" * 50)
    
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
    print(f"📁 Total files processed: {uploaded_count}")
    
    if all_success:
        print("✅ All uploads completed successfully!")
        print("\n🌐 Your tiles are now available at:")
        for local_dir_name, s3_prefix in UPLOAD_MAPPINGS.items():
            print(f"   {s3_prefix} -> s3://{S3_BUCKET}/{s3_prefix}")
    else:
        print("❌ Some uploads failed. Check the logs above.")
    
    return all_success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
