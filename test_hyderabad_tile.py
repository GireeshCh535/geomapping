#!/usr/bin/env python3
"""
Test script to analyze the specific Hyderabad highways tile with border color issues
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

def test_hyderabad_highways_tile():
    """Test the specific problematic Hyderabad highways tile"""
    
    print("🔍 Testing Hyderabad Highways Tile (9/367/231)")
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
        print(f"   City: {city.name}")
        print(f"   State: {state.name}")
        print(f"   Features: {layer.geofeature_set.count()}")
        print(f"   Bounds: {layer.bbox_xmin}, {layer.bbox_ymin}, {layer.bbox_xmax}, {layer.bbox_ymax}")
        
        # Generate MVT tile
        print(f"\n🗺️  Generating MVT tile for {test_zoom}/{test_x}/{test_y}")
        mvt_data = vector_service.generate_tile(layer, test_zoom, test_x, test_y)
        
        if not mvt_data:
            print("❌ Failed to generate MVT tile")
            return
        
        print(f"✅ MVT generated: {len(mvt_data)} bytes")
        
        # Render to PNG using the FIXED rendering service
        print(f"\n🎨 Rendering PNG tile with FIXED edge rendering")
        png_data = render_service.combined_mvt_to_png(mvt_data, [layer], test_zoom, test_x, test_y)
        
        if not png_data:
            print("❌ Failed to render PNG tile")
            return
        
        print(f"✅ PNG rendered: {len(png_data)} bytes")
        
        # Analyze the image in detail
        print(f"\n🔍 Detailed Edge Analysis")
        img = Image.open(io.BytesIO(png_data))
        print(f"   Image size: {img.size}")
        print(f"   Image mode: {img.mode}")
        
        if img.mode == 'RGBA':
            # Detailed edge analysis
            detailed_edge_analysis(img)
            
            # Save the tile for visual inspection
            test_tile_path = f"hyderabad_highways_fixed_{test_zoom}_{test_x}_{test_y}.png"
            with open(test_tile_path, 'wb') as f:
                f.write(png_data)
            print(f"\n💾 Fixed tile saved as: {test_tile_path}")
            
            # Also save a version with edge highlighting
            highlight_edges(img, f"hyderabad_highways_edges_{test_zoom}_{test_x}_{test_y}.png")
            
        else:
            print(f"⚠️  Image mode {img.mode} not supported for analysis")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

def detailed_edge_analysis(img):
    """Perform detailed analysis of tile edges"""
    
    width, height = img.size
    
    # Analyze each edge separately
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
    
    print(f"   Edge Analysis:")
    
    for edge_name, pixels in edges.items():
        non_transparent = [p for p in pixels if p[3] > 10]
        unique_colors = set(p[:3] for p in non_transparent)
        
        print(f"     {edge_name.capitalize()} edge:")
        print(f"       Total pixels: {len(pixels)}")
        print(f"       Non-transparent: {len(non_transparent)}")
        print(f"       Unique colors: {len(unique_colors)}")
        
        if unique_colors:
            print(f"       Colors: {[f'#{r:02x}{g:02x}{b:02x}' for r, g, b in list(unique_colors)[:5]]}")
        
        # Check for pattern-like artifacts
        semi_transparent = [p for p in non_transparent if 10 < p[3] < 200]
        if semi_transparent:
            print(f"       Semi-transparent pixels: {len(semi_transparent)}")
    
    # Check center area
    center_x, center_y = width // 2, height // 2
    center_pixels = []
    for x in range(center_x - 30, center_x + 30):
        for y in range(center_y - 30, center_y + 30):
            if 0 <= x < width and 0 <= y < height:
                center_pixels.append(img.getpixel((x, y)))
    
    center_non_transparent = [p for p in center_pixels if p[3] > 10]
    center_unique_colors = set(p[:3] for p in center_non_transparent)
    
    print(f"     Center area:")
    print(f"       Total pixels: {len(center_pixels)}")
    print(f"       Non-transparent: {len(center_non_transparent)}")
    print(f"       Unique colors: {len(center_unique_colors)}")
    
    if center_unique_colors:
        print(f"       Colors: {[f'#{r:02x}{g:02x}{b:02x}' for r, g, b in list(center_unique_colors)[:5]]}")

def highlight_edges(img, filename):
    """Create a version of the image with edges highlighted for visual inspection"""
    
    width, height = img.size
    highlighted = img.copy()
    
    # Draw red border around edges where there are non-transparent pixels
    for x in range(width):
        for y in range(height):
            pixel = img.getpixel((x, y))
            if pixel[3] > 10:  # Non-transparent
                # Check if it's near an edge
                if x < 5 or x >= width - 5 or y < 5 or y >= height - 5:
                    highlighted.putpixel((x, y), (255, 0, 0, 255))  # Red
    
    highlighted.save(filename)
    print(f"   Edge-highlighted version saved as: {filename}")

def compare_with_original():
    """Compare with the original tile if it exists"""
    print(f"\n🔄 Comparing with original tile")
    
    # Try to fetch the original tile from the API
    import requests
    
    try:
        url = "http://localhost:8000/api/tiles/telangana/hyderabad/hyderabad_highways/9/367/231.png"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ Retrieved original tile: {len(response.content)} bytes")
            
            # Save original for comparison
            with open("hyderabad_highways_original_9_367_231.png", "wb") as f:
                f.write(response.content)
            print(f"💾 Original tile saved as: hyderabad_highways_original_9_367_231.png")
            
            # Analyze original
            img_original = Image.open(io.BytesIO(response.content))
            print(f"   Original image size: {img_original.size}")
            print(f"   Original image mode: {img_original.mode}")
            
            if img_original.mode == 'RGBA':
                # Quick edge check
                edge_pixels = []
                for x in range(img_original.size[0]):
                    edge_pixels.append(img_original.getpixel((x, 0)))  # Top edge
                    edge_pixels.append(img_original.getpixel((x, img_original.size[1]-1)))  # Bottom edge
                
                for y in range(img_original.size[1]):
                    edge_pixels.append(img_original.getpixel((0, y)))  # Left edge
                    edge_pixels.append(img_original.getpixel((img_original.size[0]-1, y)))  # Right edge
                
                non_transparent_edges = [p for p in edge_pixels if p[3] > 10]
                print(f"   Original edge non-transparent pixels: {len(non_transparent_edges)}")
                
        else:
            print(f"❌ Failed to retrieve original tile: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error retrieving original tile: {e}")

if __name__ == "__main__":
    test_hyderabad_highways_tile()
    compare_with_original()
