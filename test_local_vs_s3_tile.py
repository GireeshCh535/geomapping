#!/usr/bin/env python3
"""
Test script to compare locally generated tile with S3 version
"""

import os
import sys
import django
from PIL import Image
import io
import requests

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

def test_local_vs_s3_tile():
    """Compare locally generated tile with S3 version"""
    
    print("🔍 Comparing Local vs S3 Tile (10/736/461)")
    print("=" * 60)
    
    # Test the specific tile coordinates
    test_zoom = 10
    test_x = 736
    test_y = 461
    
    # Local tile path
    local_path = f"static/tiles_png/telangana/hyderabad/hyderabad_highways/tiles_png/{test_zoom}_{test_x}_{test_y}.png"
    
    # S3 tile URL
    s3_url = f"https://gis-portal-layers.s3.amazonaws.com/telangana/hyderabad/hyderabad_highways/{test_zoom}/{test_x}/{test_y}.png"
    
    try:
        # Check if local tile exists
        if os.path.exists(local_path):
            print(f"✅ Local tile found: {local_path}")
            
            # Load local tile
            local_img = Image.open(local_path)
            print(f"   Local tile size: {os.path.getsize(local_path)} bytes")
            print(f"   Local image size: {local_img.size}")
            print(f"   Local image mode: {local_img.mode}")
            
            # Analyze local tile edges
            print(f"\n🔍 Local Tile Edge Analysis:")
            analyze_edges_detailed(local_img, "Local Tile")
            
        else:
            print(f"❌ Local tile not found: {local_path}")
            local_img = None
        
        # Fetch S3 tile
        print(f"\n🌐 Fetching S3 tile: {s3_url}")
        try:
            response = requests.get(s3_url)
            if response.status_code == 200:
                s3_tile_data = response.content
                print(f"✅ Retrieved S3 tile: {len(s3_tile_data)} bytes")
                
                # Load S3 tile
                s3_img = Image.open(io.BytesIO(s3_tile_data))
                print(f"   S3 image size: {s3_img.size}")
                print(f"   S3 image mode: {s3_img.mode}")
                
                # Analyze S3 tile edges
                print(f"\n🔍 S3 Tile Edge Analysis:")
                analyze_edges_detailed(s3_img, "S3 Tile")
                
                # Save S3 tile for comparison
                s3_path = f"hyderabad_highways_s3_{test_zoom}_{test_x}_{test_y}.png"
                with open(s3_path, 'wb') as f:
                    f.write(s3_tile_data)
                print(f"💾 S3 tile saved as: {s3_path}")
                
            else:
                print(f"❌ Failed to retrieve S3 tile: {response.status_code}")
                s3_img = None
        except Exception as e:
            print(f"❌ Error fetching S3 tile: {e}")
            s3_img = None
        
        # Compare if we have both tiles
        if local_img and s3_img:
            print(f"\n🔄 Comparison:")
            local_size = os.path.getsize(local_path)
            s3_size = len(s3_tile_data) if 's3_tile_data' in locals() else 0
            
            print(f"   Local tile size: {local_size} bytes")
            print(f"   S3 tile size: {s3_size} bytes")
            
            if local_size != s3_size:
                print(f"   ⚠️  Tile sizes differ - Local tile has edge fixes applied!")
            else:
                print(f"   ✅ Tile sizes match")
            
            # Compare edge pixels
            local_edge_pixels = count_edge_pixels(local_img)
            s3_edge_pixels = count_edge_pixels(s3_img)
            
            print(f"   Local edge non-transparent pixels: {local_edge_pixels}")
            print(f"   S3 edge non-transparent pixels: {s3_edge_pixels}")
            
            if local_edge_pixels < s3_edge_pixels:
                improvement = ((s3_edge_pixels - local_edge_pixels) / s3_edge_pixels) * 100
                print(f"   ✅ Local tile has {improvement:.1f}% fewer edge artifacts!")
            elif local_edge_pixels == 0 and s3_edge_pixels > 0:
                print(f"   🎉 Local tile has NO edge artifacts (100% improvement)!")
            else:
                print(f"   ⚠️  No improvement in edge artifacts")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

def analyze_edges_detailed(img, label):
    """Perform detailed edge analysis"""
    width, height = img.size
    
    # Count non-transparent pixels at edges
    edge_pixels = []
    for x in range(width):
        edge_pixels.append(img.getpixel((x, 0)))  # Top edge
        edge_pixels.append(img.getpixel((x, height-1)))  # Bottom edge
    
    for y in range(height):
        edge_pixels.append(img.getpixel((0, y)))  # Left edge
        edge_pixels.append(img.getpixel((width-1, y)))  # Right edge
    
    non_transparent = [p for p in edge_pixels if p[3] > 10]
    unique_colors = set(p[:3] for p in non_transparent)
    
    print(f"   {label} - Non-transparent edge pixels: {len(non_transparent)}")
    print(f"   {label} - Unique edge colors: {len(unique_colors)}")
    
    if unique_colors:
        print(f"   {label} - Edge colors: {[f'#{r:02x}{g:02x}{b:02x}' for r, g, b in list(unique_colors)[:3]]}")
    
    # Check each edge separately
    edges = {
        'top': [],
        'bottom': [],
        'left': [],
        'right': []
    }
    
    # Sample edge pixels
    for x in range(width):
        edges['top'].append(img.getpixel((x, 0)))
        edges['bottom'].append(img.getpixel((x, height-1)))
    
    for y in range(height):
        edges['left'].append(img.getpixel((0, y)))
        edges['right'].append(img.getpixel((width-1, y)))
    
    for edge_name, pixels in edges.items():
        non_transparent_count = sum(1 for p in pixels if p[3] > 10)
        if non_transparent_count > 0:
            print(f"   {label} - {edge_name.capitalize()} edge: {non_transparent_count} non-transparent pixels")
    
    # Also check center area
    center_x, center_y = width // 2, height // 2
    center_pixels = []
    for x in range(center_x - 20, center_x + 20):
        for y in range(center_y - 20, center_y + 20):
            if 0 <= x < width and 0 <= y < height:
                center_pixels.append(img.getpixel((x, y)))
    
    center_non_transparent = [p for p in center_pixels if p[3] > 10]
    print(f"   {label} - Center non-transparent pixels: {len(center_non_transparent)}")

def count_edge_pixels(img):
    """Count non-transparent pixels at edges"""
    width, height = img.size
    
    edge_pixels = []
    for x in range(width):
        edge_pixels.append(img.getpixel((x, 0)))  # Top edge
        edge_pixels.append(img.getpixel((x, height-1)))  # Bottom edge
    
    for y in range(height):
        edge_pixels.append(img.getpixel((0, y)))  # Left edge
        edge_pixels.append(img.getpixel((width-1, y)))  # Right edge
    
    non_transparent = [p for p in edge_pixels if p[3] > 10]
    return len(non_transparent)

if __name__ == "__main__":
    test_local_vs_s3_tile()
