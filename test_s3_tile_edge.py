#!/usr/bin/env python3
"""
Test script to check S3 tile edge issues
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

from maps.models import DataLayer, City, State
from maps.services import VectorTileService
from maps.tile_rendering_service import TileRenderingService

def test_s3_tile_edge():
    """Test the specific S3 tile that has edge issues"""
    
    print("🔍 Testing S3 Tile Edge Issues (10/736/461)")
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
        
        # First, get the tile from S3
        s3_url = f"https://gis-portal-layers.s3.amazonaws.com/telangana/hyderabad/hyderabad_highways/{test_zoom}/{test_x}/{test_y}.png"
        print(f"\n🌐 Fetching tile from S3: {s3_url}")
        
        try:
            response = requests.get(s3_url)
            if response.status_code == 200:
                s3_tile_data = response.content
                print(f"✅ Retrieved S3 tile: {len(s3_tile_data)} bytes")
                
                # Save S3 tile
                s3_path = f"hyderabad_highways_s3_{test_zoom}_{test_x}_{test_y}.png"
                with open(s3_path, 'wb') as f:
                    f.write(s3_tile_data)
                print(f"💾 S3 tile saved as: {s3_path}")
                
                # Analyze S3 tile
                s3_img = Image.open(io.BytesIO(s3_tile_data))
                print(f"\n🔍 S3 Tile Analysis:")
                print(f"   Image size: {s3_img.size}")
                print(f"   Image mode: {s3_img.mode}")
                
                if s3_img.mode == 'RGBA':
                    analyze_edges_detailed(s3_img, "S3 Tile")
            else:
                print(f"❌ Failed to retrieve S3 tile: {response.status_code}")
                s3_tile_data = None
        except Exception as e:
            print(f"❌ Error fetching S3 tile: {e}")
            s3_tile_data = None
        
        # Generate MVT tile with our fixed service
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
        
        # Save our fixed tile
        fixed_path = f"hyderabad_highways_fixed_{test_zoom}_{test_x}_{test_y}.png"
        with open(fixed_path, 'wb') as f:
            f.write(png_data)
        print(f"💾 Fixed tile saved as: {fixed_path}")
        
        # Analyze our fixed tile
        fixed_img = Image.open(io.BytesIO(png_data))
        print(f"\n🔍 Fixed Tile Analysis:")
        print(f"   Image size: {fixed_img.size}")
        print(f"   Image mode: {fixed_img.mode}")
        
        if fixed_img.mode == 'RGBA':
            analyze_edges_detailed(fixed_img, "Fixed Tile")
        
        # Compare if we have both tiles
        if s3_tile_data:
            print(f"\n🔄 Comparison:")
            print(f"   S3 tile size: {len(s3_tile_data)} bytes")
            print(f"   Fixed tile size: {len(png_data)} bytes")
            
            if len(s3_tile_data) != len(png_data):
                print(f"   ⚠️  Tile sizes differ - S3 tile may be cached or different")
            else:
                print(f"   ✅ Tile sizes match")
        
        # Test edge cleanup manually
        print(f"\n🧹 Testing Manual Edge Cleanup:")
        test_img = fixed_img.copy()
        render_service._cleanup_tile_edges(test_img)
        
        # Analyze after manual cleanup
        print(f"\n🔍 After Manual Edge Cleanup:")
        analyze_edges_detailed(test_img, "Manual Cleanup")
        
        # Save manually cleaned tile
        manual_path = f"hyderabad_highways_manual_cleanup_{test_zoom}_{test_x}_{test_y}.png"
        test_img.save(manual_path)
        print(f"💾 Manually cleaned tile saved as: {manual_path}")
        
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
        print(f"   {label} - Edge colors: {[f'#{r:02x}{g:02x}{b:02x}' for r, g, b in list(unique_colors)[:5]]}")
    
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

if __name__ == "__main__":
    test_s3_tile_edge()
