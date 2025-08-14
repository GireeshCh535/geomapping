#!/usr/bin/env python3
"""
Test multiple tiles from different zoom levels to verify all colors
"""

from PIL import Image
import os
import glob

def test_multiple_tiles():
    """Test multiple tiles to verify all colors"""
    
    print("🎨 Testing Multiple Tiles for Color Verification")
    print("=" * 60)
    
    # Test tiles from different zoom levels
    test_tiles = [
        "static/tiles_png/karnataka/bengaluru/bengaluru_master_plan_2015/tiles_png/6_45_29.png",
        "static/tiles_png/karnataka/bengaluru/bengaluru_master_plan_2015/tiles_png/7_91_58.png",
        "static/tiles_png/karnataka/bengaluru/bengaluru_master_plan_2015/tiles_png/8_183_117.png",
        "static/tiles_png/karnataka/bengaluru/bengaluru_master_plan_2015/tiles_png/9_366_234.png",
        "static/tiles_png/karnataka/bengaluru/bengaluru_master_plan_2015/tiles_png/10_732_468.png",
        "static/tiles_png/karnataka/bengaluru/bengaluru_master_plan_2015/tiles_png/11_1464_936.png"
    ]
    
    for tile_path in test_tiles:
        if os.path.exists(tile_path):
            print(f"\n✅ Testing: {tile_path}")
            
            # Analyze the image
            img = Image.open(tile_path)
            file_size = os.path.getsize(tile_path)
            
            if file_size > 1000:  # Only analyze tiles with content
                print(f"   File size: {file_size} bytes")
                
                # Get color data
                if img.mode == 'RGBA':
                    img_rgb = img.convert('RGB')
                    colors = img_rgb.getcolors(maxcolors=10000)
                    
                    if colors:
                        # Sort by frequency
                        colors.sort(key=lambda x: x[0], reverse=True)
                        
                        print(f"   Top 5 colors:")
                        for i, (count, (r, g, b)) in enumerate(colors[:5]):
                            hex_color = f"#{r:02x}{g:02x}{b:02x}"
                            print(f"     {hex_color}: {count} pixels")
                            
                            # Check for expected colors
                            if hex_color.lower() == '#ffc400':
                                print(f"       ✅ Residential Mixed (Orange)")
                            elif hex_color.lower() == '#ffeb4f':
                                print(f"       ✅ Residential Main (Yellow)")
                            elif hex_color.lower() == '#004da8':
                                print(f"       ✅ Commercial Central (Blue)")
                            elif hex_color.lower() == '#aa66b2':
                                print(f"       ✅ Industrial (Purple)")
                            elif hex_color.lower() == '#e60000':
                                print(f"       ✅ Public & Semi Public (Red)")
                            elif hex_color.lower() == '#bee8ff':
                                print(f"       ✅ Lake Tank (Light Blue)")
                            elif hex_color.lower() == '#98e600':
                                print(f"       ✅ Parks Green Spaces (Green)")
                            elif hex_color.lower() == '#267300':
                                print(f"       ✅ Drains (Dark Green)")
                            elif hex_color.lower() == '#9dc1cb':
                                print(f"       ✅ Agricultural Land (Light Blue-Gray)")
                    else:
                        print("   No colors found")
                else:
                    print(f"   Image mode: {img.mode}")
            else:
                print(f"   File size: {file_size} bytes (likely empty)")
        else:
            print(f"\n❌ Tile not found: {tile_path}")
    
    # Test transport layers
    print(f"\n🚗 Testing Transport Layers:")
    transport_tiles = [
        "static/tiles_png/karnataka/bengaluru/bengaluru_highways/tiles_png/6_45_29.png",
        "static/tiles_png/karnataka/bengaluru/bengaluru_metro_lines/tiles_png/6_45_29.png",
        "static/tiles_png/karnataka/bengaluru/bengaluru_strr/tiles_png/6_45_29.png"
    ]
    
    for tile_path in transport_tiles:
        if os.path.exists(tile_path):
            file_size = os.path.getsize(tile_path)
            print(f"   {os.path.basename(tile_path)}: {file_size} bytes")
        else:
            print(f"   {os.path.basename(tile_path)}: Not found")

if __name__ == "__main__":
    test_multiple_tiles()
