#!/usr/bin/env python3
"""
Test for specific color #FFC400 in the PNG tile
"""

from PIL import Image
import os

def test_specific_color():
    """Test for specific color in the tile"""
    
    print("🎨 Testing for #FFC400 color in PNG tile")
    print("=" * 50)
    
    tile_path = "static/tiles_png/karnataka/bengaluru/bengaluru_master_plan_2015/tiles_png/10_732_474.png"
    
    if os.path.exists(tile_path):
        print(f"✅ Found tile: {tile_path}")
        
        # Analyze the image
        img = Image.open(tile_path)
        print(f"   Image size: {img.size}")
        print(f"   Image mode: {img.mode}")
        print(f"   File size: {os.path.getsize(tile_path)} bytes")
        
        # Get all colors
        if img.mode == 'RGBA':
            # Convert to RGB for analysis
            img_rgb = img.convert('RGB')
            colors = img_rgb.getcolors(maxcolors=10000)
            
            if colors:
                print(f"   Found {len(colors)} unique colors")
                
                # Look specifically for #FFC400
                target_color = (255, 196, 0)  # #FFC400 in RGB
                found_target = False
                
                print("   All colors:")
                for count, (r, g, b) in colors:
                    hex_color = f"#{r:02x}{g:02x}{b:02x}"
                    print(f"     {hex_color}: {count} pixels")
                    
                    if (r, g, b) == target_color:
                        found_target = True
                        print(f"     ✅ FOUND TARGET COLOR #FFC400: {count} pixels!")
                
                if not found_target:
                    print("     ❌ Target color #FFC400 not found!")
                    
                    # Check for similar colors
                    print("   Checking for similar colors:")
                    for count, (r, g, b) in colors:
                        hex_color = f"#{r:02x}{g:02x}{b:02x}"
                        # Check if it's close to orange
                        if r > 200 and g > 100 and b < 100:
                            print(f"     Similar orange: {hex_color}: {count} pixels")
            else:
                print("   No colors found (possibly transparent)")
        else:
            print(f"   Image mode {img.mode} not supported for color analysis")
    else:
        print(f"❌ Tile not found: {tile_path}")

if __name__ == "__main__":
    test_specific_color()
