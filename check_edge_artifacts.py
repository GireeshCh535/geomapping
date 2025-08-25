#!/usr/bin/env python3
"""
Check for edge artifacts in RRR tiles
"""

import os
import sys
from PIL import Image
import glob

def check_edge_artifacts():
    """Check for edge artifacts in RRR tiles"""
    
    print("🔍 Checking for Edge Artifacts in RRR Tiles")
    print("=" * 60)
    
    # Path to the tiles
    tiles_path = "static/tiles_png/telangana/hyderabad/hyderabad_rrr/tiles_png"
    
    if not os.path.exists(tiles_path):
        print(f"❌ Tiles directory not found: {tiles_path}")
        return
    
    # Get all PNG files
    tile_files = glob.glob(os.path.join(tiles_path, "*.png"))
    
    if not tile_files:
        print(f"❌ No tile files found in {tiles_path}")
        return
    
    print(f"📊 Found {len(tile_files)} tile files")
    
    # Check a few sample tiles
    sample_tiles = tile_files[:5]  # Check first 5 tiles
    
    for tile_file in sample_tiles:
        try:
            filename = os.path.basename(tile_file)
            print(f"\n📍 Analyzing {filename}:")
            
            with Image.open(tile_file) as img:
                if img.mode != 'RGBA':
                    print(f"   ❌ Not RGBA mode: {img.mode}")
                    continue
                
                # Check edge pixels (4-pixel border)
                edge_colors = set()
                center_colors = set()
                edge_pixels = 0
                center_pixels = 0
                
                for x in range(img.width):
                    for y in range(img.height):
                        pixel = img.getpixel((x, y))
                        if pixel[3] > 10:  # Non-transparent
                            rgb = pixel[:3]
                            
                            # Check if pixel is in edge area (4-pixel border)
                            if x < 4 or x >= img.width-4 or y < 4 or y >= img.height-4:
                                edge_colors.add(rgb)
                                edge_pixels += 1
                            else:
                                center_colors.add(rgb)
                                center_pixels += 1
                
                print(f"   Edge pixels: {edge_pixels}")
                print(f"   Center pixels: {center_pixels}")
                print(f"   Edge colors: {edge_colors}")
                print(f"   Center colors: {center_colors}")
                
                # Check for colors that only appear at edges
                edge_only_colors = edge_colors - center_colors
                if edge_only_colors:
                    print(f"   ⚠️  EDGE ARTIFACTS DETECTED!")
                    print(f"   Colors only at edges: {edge_only_colors}")
                    
                    # Check if these are the expected RRR color
                    expected_color = (20, 224, 152)  # #14E098
                    for color in edge_only_colors:
                        if color == expected_color:
                            print(f"   ✅ Edge color is expected RRR color: {color}")
                        else:
                            print(f"   ❌ Unexpected edge color: {color}")
                else:
                    print(f"   ✅ No edge artifacts detected")
                
                # Check edge transparency
                edge_transparent = 0
                edge_total = 0
                for x in range(img.width):
                    for y in range(img.height):
                        if x < 4 or x >= img.width-4 or y < 4 or y >= img.height-4:
                            edge_total += 1
                            pixel = img.getpixel((x, y))
                            if pixel[3] <= 10:  # Transparent
                                edge_transparent += 1
                
                edge_transparency = edge_transparent / edge_total if edge_total > 0 else 1.0
                print(f"   Edge transparency: {edge_transparency*100:.1f}%")
                
                if edge_transparency < 0.8:
                    print(f"   ⚠️  LOW EDGE TRANSPARENCY - may have artifacts")
                else:
                    print(f"   ✅ Good edge transparency")
                
        except Exception as e:
            print(f"❌ Error analyzing {tile_file}: {e}")
    
    # Check if edge cleanup is being applied
    print(f"\n🔍 Checking Edge Cleanup Implementation:")
    
    # Check if the edge cleanup method exists in the rendering service
    try:
        from maps.tile_rendering_service import TileRenderingService
        render_service = TileRenderingService()
        
        if hasattr(render_service, '_cleanup_tile_edges'):
            print(f"   ✅ _cleanup_tile_edges method exists")
        else:
            print(f"   ❌ _cleanup_tile_edges method missing")
            
        if hasattr(render_service, '_clear_tile_edges'):
            print(f"   ✅ _clear_tile_edges method exists")
        else:
            print(f"   ❌ _clear_tile_edges method missing")
            
    except Exception as e:
        print(f"   ❌ Error checking rendering service: {e}")

if __name__ == "__main__":
    check_edge_artifacts()
