#!/usr/bin/env python3
"""
Test script to check the specific Hyderabad highways tile 9/367/231
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

def test_specific_hyderabad_tile():
    """Test the specific tile 9/367/231"""
    
    print("🔍 Testing Specific Hyderabad Tile (9/367/231)")
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
        
        # Generate MVT tile
        print(f"\n🗺️  Generating MVT tile for {test_zoom}/{test_x}/{test_y}")
        mvt_data = vector_service.generate_tile(layer, test_zoom, test_x, test_y)
        
        if not mvt_data:
            print("❌ Failed to generate MVT tile")
            return
        
        print(f"✅ MVT generated: {len(mvt_data)} bytes")
        
        # Render to PNG with FIXED edge rendering
        print(f"\n🎨 Rendering PNG tile with FIXED edge rendering")
        png_data = render_service.combined_mvt_to_png(mvt_data, [layer], test_zoom, test_x, test_y)
        
        if not png_data:
            print("❌ Failed to render PNG tile")
            return
        
        print(f"✅ PNG rendered: {len(png_data)} bytes")
        
        # Analyze the image for edge artifacts
        print(f"\n🔍 Analyzing tile for edge artifacts")
        img = Image.open(io.BytesIO(png_data))
        print(f"   Image size: {img.size}")
        print(f"   Image mode: {img.mode}")
        
        if img.mode == 'RGBA':
            # Check for unwanted colors at edges
            edge_colors = analyze_edge_colors(img)
            
            print(f"   Edge analysis:")
            print(f"     Total edge pixels: {edge_colors['total_edge_pixels']}")
            print(f"     Transparent edge pixels: {edge_colors['transparent_edge_pixels']}")
            print(f"     Edge colors: {edge_colors['edge_color_count']}")
            print(f"     Center colors: {edge_colors['center_color_count']}")
            
            if edge_colors['unwanted_colors']:
                print("   ❌ Found unwanted colors at tile edges:")
                for color, count in edge_colors['unwanted_colors']:
                    print(f"     {color}: {count} pixels")
            else:
                print("   ✅ No unwanted colors found at tile edges")
            
            if edge_colors['pattern_artifacts']:
                print("   ⚠️  Potential pattern artifacts:")
                for color, count in edge_colors['pattern_artifacts']:
                    print(f"     {color}: {count} pixels (semi-transparent)")
            
            # Check for transparency at edges
            if edge_colors['transparent_edges']:
                print("   ✅ Tile edges are properly transparent")
            else:
                print("   ⚠️  Tile edges may not be fully transparent")
            
            # Check for color consistency
            if edge_colors['consistent_colors']:
                print("   ✅ Colors are consistent across the tile")
            else:
                print("   ⚠️  Color consistency issues detected")
                
        else:
            print(f"⚠️  Image mode {img.mode} not supported for analysis")
        
        # Save test tile for visual inspection
        test_tile_path = f"hyderabad_highways_fixed_{test_zoom}_{test_x}_{test_y}.png"
        with open(test_tile_path, 'wb') as f:
            f.write(png_data)
        print(f"\n💾 Fixed tile saved as: {test_tile_path}")
        
        # Also save a version with edge highlighting
        highlight_edges(img, f"hyderabad_highways_edges_{test_zoom}_{test_x}_{test_y}.png")
        
        # Try to retrieve the original tile from S3 for comparison
        print(f"\n🔄 Comparing with original tile from S3")
        try:
            import requests
            s3_url = f"https://gis-portal-layers.s3.amazonaws.com/telangana/hyderabad/hyderabad_highways/{test_zoom}/{test_x}/{test_y}.png"
            response = requests.get(s3_url)
            
            if response.status_code == 200:
                original_data = response.content
                print(f"✅ Retrieved original tile: {len(original_data)} bytes")
                
                # Save original for comparison
                original_tile_path = f"hyderabad_highways_original_{test_zoom}_{test_x}_{test_y}.png"
                with open(original_tile_path, 'wb') as f:
                    f.write(original_data)
                print(f"💾 Original tile saved as: {original_tile_path}")
                
                # Compare sizes
                print(f"   Original tile size: {len(original_data)} bytes")
                print(f"   Fixed tile size: {len(png_data)} bytes")
                
                # Analyze original tile
                original_img = Image.open(io.BytesIO(original_data))
                print(f"   Original image size: {original_img.size}")
                print(f"   Original image mode: {original_img.mode}")
                
                if original_img.mode == 'RGBA':
                    original_edge_colors = analyze_edge_colors(original_img)
                    print(f"   Original edge non-transparent pixels: {original_edge_colors['transparent_edge_pixels']}")
                
            else:
                print(f"❌ Failed to retrieve original tile: {response.status_code}")
                
        except Exception as e:
            print(f"⚠️  Could not retrieve original tile: {e}")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

def analyze_edge_colors(img):
    """Analyze tile for unwanted colors at edges"""
    
    width, height = img.size
    edge_pixels = []
    center_pixels = []
    
    # Sample edge pixels (2 pixel border for better detection)
    for x in range(width):
        edge_pixels.append(img.getpixel((x, 0)))  # Top edge
        edge_pixels.append(img.getpixel((x, 1)))  # Top edge + 1
        edge_pixels.append(img.getpixel((x, height-1)))  # Bottom edge
        edge_pixels.append(img.getpixel((x, height-2)))  # Bottom edge - 1
    
    for y in range(height):
        edge_pixels.append(img.getpixel((0, y)))  # Left edge
        edge_pixels.append(img.getpixel((1, y)))  # Left edge + 1
        edge_pixels.append(img.getpixel((width-1, y)))  # Right edge
        edge_pixels.append(img.getpixel((width-2, y)))  # Right edge - 1
    
    # Sample center pixels for comparison (larger area)
    center_x, center_y = width // 2, height // 2
    for x in range(center_x - 20, center_x + 20):
        for y in range(center_y - 20, center_y + 20):
            if 0 <= x < width and 0 <= y < height:
                center_pixels.append(img.getpixel((x, y)))
    
    # Analyze colors
    edge_colors = {}
    center_colors = {}
    
    for pixel in edge_pixels:
        if pixel[3] > 10:  # Non-transparent (with small threshold)
            edge_colors[pixel] = edge_colors.get(pixel, 0) + 1
    
    for pixel in center_pixels:
        if pixel[3] > 10:  # Non-transparent (with small threshold)
            center_colors[pixel] = center_colors.get(pixel, 0) + 1
    
    # Find unwanted colors (colors that appear at edges but not in center)
    unwanted_colors = []
    for color, count in edge_colors.items():
        if color not in center_colors and count > 10:  # Higher threshold to avoid noise
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            unwanted_colors.append((hex_color, count))
    
    # Check for transparency at edges (more lenient)
    transparent_edges = sum(1 for pixel in edge_pixels if pixel[3] < 10) > len(edge_pixels) * 0.8
    
    # Check for color consistency (more lenient)
    consistent_colors = len(edge_colors) <= len(center_colors) + 5  # Allow more variation
    
    # Additional analysis: check for pattern artifacts
    pattern_artifacts = []
    for color, count in edge_colors.items():
        if count > 50:  # Significant color presence
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            # Check if this color is likely a pattern artifact
            if color[3] < 200:  # Semi-transparent
                pattern_artifacts.append((hex_color, count))
    
    return {
        'unwanted_colors': unwanted_colors,
        'transparent_edges': transparent_edges,
        'consistent_colors': consistent_colors,
        'edge_color_count': len(edge_colors),
        'center_color_count': len(center_colors),
        'pattern_artifacts': pattern_artifacts,
        'total_edge_pixels': len(edge_pixels),
        'transparent_edge_pixels': sum(1 for pixel in edge_pixels if pixel[3] < 10)
    }

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

if __name__ == "__main__":
    test_specific_hyderabad_tile()
