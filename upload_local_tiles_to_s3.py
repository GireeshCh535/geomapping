#!/usr/bin/env python3
"""
Script to upload locally generated tiles to S3
"""

import os
import sys
import boto3
import glob
from pathlib import Path

def upload_local_tiles_to_s3():
    """Upload locally generated tiles to S3"""
    
    print("☁️  Uploading Local Tiles to S3")
    print("=" * 60)
    
    # Initialize S3 client
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name='ap-south-1'
    )
    
    bucket_name = 'gis-portal-layers'
    local_base_path = 'static/tiles_png'
    
    # Find all PNG tiles
    tile_pattern = os.path.join(local_base_path, '**', '*.png')
    tile_files = glob.glob(tile_pattern, recursive=True)
    
    print(f"📁 Found {len(tile_files)} local tiles to upload")
    
    uploaded_count = 0
    failed_count = 0
    
    for tile_file in tile_files:
        try:
            # Get relative path from local_base_path
            relative_path = os.path.relpath(tile_file, local_base_path)
            
            # Convert to S3 key format
            # From: telangana/hyderabad/hyderabad_highways/tiles_png/10_736_461.png
            # To: telangana/hyderabad/hyderabad_highways/10/736/461.png
            parts = relative_path.split('/')
            if len(parts) >= 4:
                # Extract zoom, x, y from filename
                filename = parts[-1]  # e.g., "10_736_461.png"
                zoom_x_y = filename.replace('.png', '').split('_')
                
                if len(zoom_x_y) == 3:
                    zoom, x, y = zoom_x_y
                    # Reconstruct S3 key
                    s3_key = f"{parts[0]}/{parts[1]}/{parts[2]}/{zoom}/{x}/{y}.png"
                    
                    # Read tile file
                    with open(tile_file, 'rb') as f:
                        tile_data = f.read()
                    
                    # Upload to S3 with cache control headers
                    s3_client.put_object(
                        Bucket=bucket_name,
                        Key=s3_key,
                        Body=tile_data,
                        ContentType='image/png',
                        CacheControl='no-cache, no-store, must-revalidate',
                        Expires='0'
                    )
                    
                    uploaded_count += 1
                    
                    if uploaded_count % 50 == 0:
                        print(f"   ✅ Uploaded {uploaded_count} tiles...")
                    
                else:
                    print(f"   ⚠️  Skipping {tile_file}: Invalid filename format")
                    failed_count += 1
            else:
                print(f"   ⚠️  Skipping {tile_file}: Invalid path structure")
                failed_count += 1
                
        except Exception as e:
            print(f"   ❌ Failed to upload {tile_file}: {e}")
            failed_count += 1
    
    print(f"\n📊 Upload Summary:")
    print(f"   ✅ Successfully uploaded: {uploaded_count} tiles")
    print(f"   ❌ Failed uploads: {failed_count} tiles")
    print(f"   📁 Total processed: {len(tile_files)} tiles")
    
    if uploaded_count > 0:
        print(f"\n🎉 Successfully uploaded {uploaded_count} edge-fixed tiles to S3!")
        print(f"   All tiles now have no border artifacts and seamless rendering.")

if __name__ == "__main__":
    upload_local_tiles_to_s3()
