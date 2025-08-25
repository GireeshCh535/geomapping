#!/usr/bin/env python3
"""
Test script to verify tile edge rendering fixes
Tests that tiles are generated without unwanted colors and artifacts at boundaries
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

def test_tile_edge_rendering():
    """Test that tiles are generated without edge artifacts"""
    
    print("🔧 Testing Tile Edge Rendering Fixes")
    print("=" * 60)
    
    # Initialize services
    vector_service = VectorTileService()
    render_service = TileRenderingService()
    
    # Test parameters - using Bengaluru coordinates that have data
    test_zoom = 12
    test_x = 2928
    test_y = 1896
    
    # Find a test layer (Bengaluru master plan)
    try:
        state = State.objects.get(slug='karnataka')
        city = City.objects.get(state_ref=state, slug='bengaluru')
        layer = DataLayer.objects.filter(city=city, slug__contains='master_plan').first()
        
        if not layer:
            print("❌ No master plan layer found for Bengaluru")
            return
        
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
        
        # Render to PNG
        print(f"\n🎨 Rendering PNG tile")
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
        test_tile_path = f"test_tile_edge_fix_{test_zoom}_{test_x}_{test_y}.png"
        with open(test_tile_path, 'wb') as f:
            f.write(png_data)
        print(f"\n💾 Test tile saved as: {test_tile_path}")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

def analyze_edge_colors(img):
    """Analyze tile for unwanted colors at edges - IMPROVED"""
    
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

def test_multiple_tiles():
    """Test multiple tiles to ensure consistency"""
    
    print(f"\n🔧 Testing Multiple Tiles for Consistency")
    print("=" * 60)
    
    # Test parameters - using Bengaluru coordinates that have data
    test_zoom = 12
    test_tiles = [
        (2928, 1896),
        (2929, 1896),
        (2928, 1897),
        (2929, 1897)
    ]
    
    try:
        state = State.objects.get(slug='karnataka')
        city = City.objects.get(state_ref=state, slug='bengaluru')
        layer = DataLayer.objects.filter(city=city, slug__contains='master_plan').first()
        
        if not layer:
            print("❌ No master plan layer found for Bengaluru")
            return
        
        vector_service = VectorTileService()
        render_service = TileRenderingService()
        
        tile_results = []
        
        for x, y in test_tiles:
            print(f"\n🗺️  Testing tile {test_zoom}/{x}/{y}")
            
            # Generate MVT
            mvt_data = vector_service.generate_tile(layer, test_zoom, x, y)
            if not mvt_data:
                print(f"   ❌ Failed to generate MVT")
                continue
            
            # Render PNG
            png_data = render_service.combined_mvt_to_png(mvt_data, [layer], test_zoom, x, y)
            if not png_data:
                print(f"   ❌ Failed to render PNG")
                continue
            
            # Analyze
            img = Image.open(io.BytesIO(png_data))
            if img.mode == 'RGBA':
                edge_analysis = analyze_edge_colors(img)
                tile_results.append({
                    'tile': f"{test_zoom}/{x}/{y}",
                    'unwanted_colors': len(edge_analysis['unwanted_colors']),
                    'transparent_edges': edge_analysis['transparent_edges'],
                    'consistent_colors': edge_analysis['consistent_colors']
                })
                
                print(f"   ✅ Generated: {len(png_data)} bytes")
                print(f"   🎨 Unwanted colors: {len(edge_analysis['unwanted_colors'])}")
                print(f"   🔍 Transparent edges: {edge_analysis['transparent_edges']}")
                print(f"   🎯 Consistent colors: {edge_analysis['consistent_colors']}")
            else:
                print(f"   ⚠️  Unsupported image mode: {img.mode}")
        
        # Summary
        print(f"\n📊 Test Summary:")
        print(f"   Tiles tested: {len(tile_results)}")
        
        if tile_results:
            total_unwanted = sum(r['unwanted_colors'] for r in tile_results)
            transparent_count = sum(1 for r in tile_results if r['transparent_edges'])
            consistent_count = sum(1 for r in tile_results if r['consistent_colors'])
            
            print(f"   Total unwanted colors: {total_unwanted}")
            print(f"   Tiles with transparent edges: {transparent_count}/{len(tile_results)}")
            print(f"   Tiles with consistent colors: {consistent_count}/{len(tile_results)}")
            
            if total_unwanted == 0 and transparent_count == len(tile_results):
                print(f"   ✅ All tiles passed edge rendering tests!")
            else:
                print(f"   ⚠️  Some tiles have edge rendering issues")
        
    except Exception as e:
        print(f"❌ Error during multi-tile testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_tile_edge_rendering()
    test_multiple_tiles()
