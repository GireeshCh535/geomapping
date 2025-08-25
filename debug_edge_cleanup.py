#!/usr/bin/env python3
"""
Debug script to test edge cleanup directly
"""

import os
import sys
import django
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

def debug_edge_cleanup():
    """Debug the edge cleanup process"""
    
    print("🔍 Debugging Edge Cleanup Process")
    print("=" * 60)
    
    # Initialize services
    vector_service = VectorTileService()
    render_service = TileRenderingService()
    
    # Test the specific tile coordinates
    test_zoom = 9
    test_x = 367
    test_y = 231
    
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
        
        # Render to PNG
        print(f"\n🎨 Rendering PNG tile")
        png_data = render_service.combined_mvt_to_png(mvt_data, [layer], test_zoom, test_x, test_y)
        
        if not png_data:
            print("❌ Failed to render PNG tile")
            return
        
        print(f"✅ PNG rendered: {len(png_data)} bytes")
        
        # Load the image
        img = Image.open(io.BytesIO(png_data))
        print(f"   Image size: {img.size}")
        print(f"   Image mode: {img.mode}")
        
        # Analyze before cleanup
        print(f"\n🔍 Before Edge Cleanup:")
        analyze_edges(img, "Before")
        
        # Apply edge cleanup manually
        print(f"\n🧹 Applying Edge Cleanup:")
        render_service._cleanup_tile_edges(img)
        
        # Analyze after cleanup
        print(f"\n🔍 After Edge Cleanup:")
        analyze_edges(img, "After")
        
        # Save the cleaned image
        cleaned_path = f"hyderabad_highways_cleaned_{test_zoom}_{test_x}_{test_y}.png"
        img.save(cleaned_path)
        print(f"\n💾 Cleaned tile saved as: {cleaned_path}")
        
        # Test the _clear_tile_edges method directly
        print(f"\n🧹 Testing Direct Edge Clearing:")
        render_service._clear_tile_edges(img)
        
        # Analyze after direct clearing
        print(f"\n🔍 After Direct Edge Clearing:")
        analyze_edges(img, "Direct")
        
        # Save the directly cleared image
        direct_path = f"hyderabad_highways_direct_cleared_{test_zoom}_{test_x}_{test_y}.png"
        img.save(direct_path)
        print(f"\n💾 Directly cleared tile saved as: {direct_path}")
        
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        import traceback
        traceback.print_exc()

def analyze_edges(img, stage):
    """Analyze edges at different stages"""
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
    
    print(f"   {stage} - Non-transparent edge pixels: {len(non_transparent)}")
    print(f"   {stage} - Unique edge colors: {len(unique_colors)}")
    
    if unique_colors:
        print(f"   {stage} - Edge colors: {[f'#{r:02x}{g:02x}{b:02x}' for r, g, b in list(unique_colors)[:3]]}")
    
    # Also check center area
    center_x, center_y = width // 2, height // 2
    center_pixels = []
    for x in range(center_x - 20, center_x + 20):
        for y in range(center_y - 20, center_y + 20):
            if 0 <= x < width and 0 <= y < height:
                center_pixels.append(img.getpixel((x, y)))
    
    center_non_transparent = [p for p in center_pixels if p[3] > 10]
    print(f"   {stage} - Center non-transparent pixels: {len(center_non_transparent)}")

if __name__ == "__main__":
    debug_edge_cleanup()
