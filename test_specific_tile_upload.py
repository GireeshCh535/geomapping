#!/usr/bin/env python3
"""
Test script to upload a specific tile and verify S3 upload
"""

import os
import sys
import django
import boto3
import requests
from PIL import Image
import io

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from maps.models import DataLayer, City, State
from maps.services import VectorTileService
from maps.tile_rendering_service import TileRenderingService

def test_specific_tile_upload():
    """Test uploading a specific tile and verify S3 upload"""
    
    print("🔍 Testing Specific Tile Upload (10/736/461)")
    print("=" * 60)
    
    # Initialize services
    vector_service = VectorTileService()
    render_service = TileRenderingService()
    
    # Test the specific tile coordinates
    test_zoom = 10
    test_x = 736
    test_y = 461
    
    try:
        state = State.objects.get(slug='telangana')
        city = City.objects.get(slug='hyderabad', state_ref=state)
        layer = DataLayer.objects.get(slug='hyderabad_highways')
        
        print(f"✅ Testing layer: {layer.slug}")
        
        # Generate MVT tile
        print(f"\n🗺️  Generating MVT tile for {test_zoom}/{test_x}/{test_y}")
        mvt_data = vector_service.generate_tile(layer, test_zoom, test_x, test_y)
        
        if not mvt_data:
            print("❌ Failed to generate MVT tile")
            return
        
        print(f"✅ MVT generated: {len(mvt_data)} bytes")
        
        # Render to PNG with our fixed service
        print(f"\n🎨 Rendering PNG tile with FIXED edge rendering")
        png_data = render_service.combined_mvt_to_png(mvt_data, [layer], test_zoom, test_x, test_y)
        
        if not png_data:
            print("❌ Failed to render PNG tile")
            return
        
        print(f"✅ PNG rendered: {len(png_data)} bytes")
        
        # Save our fixed tile locally
        fixed_path = f"hyderabad_highways_fixed_{test_zoom}_{test_x}_{test_y}.png"
        with open(fixed_path, 'wb') as f:
            f.write(png_data)
        print(f"💾 Fixed tile saved locally as: {fixed_path}")
        
        # Analyze our fixed tile
        fixed_img = Image.open(io.BytesIO(png_data))
        print(f"\n🔍 Fixed Tile Analysis:")
        print(f"   Image size: {fixed_img.size}")
        print(f"   Image mode: {fixed_img.mode}")
        
        # Count edge pixels
        width, height = fixed_img.size
        edge_pixels = []
        for x in range(width):
            edge_pixels.append(fixed_img.getpixel((x, 0)))  # Top edge
            edge_pixels.append(fixed_img.getpixel((x, height-1)))  # Bottom edge
        
        for y in range(height):
            edge_pixels.append(fixed_img.getpixel((0, y)))  # Left edge
            edge_pixels.append(fixed_img.getpixel((width-1, y)))  # Right edge
        
        non_transparent = [p for p in edge_pixels if p[3] > 10]
        print(f"   Non-transparent edge pixels: {len(non_transparent)}")
        
        if len(non_transparent) == 0:
            print(f"   ✅ Perfect! No edge artifacts")
        else:
            print(f"   ⚠️  Still has {len(non_transparent)} edge artifacts")
        
        # Upload to S3 directly
        print(f"\n☁️  Uploading to S3 directly...")
        
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name='ap-south-1'
        )
        
        # S3 key
        s3_key = f"telangana/hyderabad/hyderabad_highways/{test_zoom}/{test_x}/{test_y}.png"
        bucket_name = 'gis-portal-layers'
        
        # Upload with cache control headers
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=png_data,
            ContentType='image/png',
            CacheControl='no-cache, no-store, must-revalidate',
            Expires='0'
        )
        
        print(f"✅ Uploaded to S3: s3://{bucket_name}/{s3_key}")
        print(f"   Cache control: no-cache, no-store, must-revalidate")
        
        # Wait a moment for S3 to propagate
        import time
        print(f"\n⏳ Waiting 5 seconds for S3 propagation...")
        time.sleep(5)
        
        # Test fetching the uploaded tile
        print(f"\n🌐 Testing S3 fetch with cache busting...")
        
        # Try with cache busting parameter
        s3_url = f"https://gis-portal-layers.s3.amazonaws.com/{s3_key}?t={int(time.time())}"
        print(f"   URL: {s3_url}")
        
        try:
            response = requests.get(s3_url, headers={'Cache-Control': 'no-cache'})
            if response.status_code == 200:
                s3_tile_data = response.content
                print(f"✅ Retrieved S3 tile: {len(s3_tile_data)} bytes")
                
                # Compare sizes
                if len(s3_tile_data) == len(png_data):
                    print(f"✅ Tile sizes match - upload successful!")
                else:
                    print(f"⚠️  Tile sizes differ: S3={len(s3_tile_data)}, Local={len(png_data)}")
                
                # Save S3 tile for comparison
                s3_path = f"hyderabad_highways_s3_after_upload_{test_zoom}_{test_x}_{test_y}.png"
                with open(s3_path, 'wb') as f:
                    f.write(s3_tile_data)
                print(f"💾 S3 tile saved as: {s3_path}")
                
                # Analyze S3 tile
                s3_img = Image.open(io.BytesIO(s3_tile_data))
                s3_edge_pixels = []
                for x in range(width):
                    s3_edge_pixels.append(s3_img.getpixel((x, 0)))
                    s3_edge_pixels.append(s3_img.getpixel((x, height-1)))
                
                for y in range(height):
                    s3_edge_pixels.append(s3_img.getpixel((0, y)))
                    s3_edge_pixels.append(s3_img.getpixel((width-1, y)))
                
                s3_non_transparent = [p for p in s3_edge_pixels if p[3] > 10]
                print(f"   S3 tile edge pixels: {len(s3_non_transparent)}")
                
                if len(s3_non_transparent) == 0:
                    print(f"   ✅ S3 tile has no edge artifacts!")
                else:
                    print(f"   ⚠️  S3 tile still has {len(s3_non_transparent)} edge artifacts")
                    
            else:
                print(f"❌ Failed to retrieve S3 tile: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error fetching S3 tile: {e}")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_specific_tile_upload()
