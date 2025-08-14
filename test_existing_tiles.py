#!/usr/bin/env python3
"""
Test existing tiles to verify all colors are working
"""

from PIL import Image
import os

def test_existing_tiles():
    """Test existing tiles to verify all colors"""
    
    print("🎨 Testing Existing Tiles for Color Verification")
    print("=" * 60)
    
    # Test tiles that actually exist
    test_tiles = [
        "static/tiles_png/karnataka/bengaluru/bengaluru_master_plan_2015/tiles_png/6_45_29.png",
        "static/tiles_png/karnataka/bengaluru/bengaluru_master_plan_2015/tiles_png/9_366_237.png",
        "static/tiles_png/karnataka/bengaluru/bengaluru_master_plan_2015/tiles_png/11_1465_950.png",
        "static/tiles_png/karnataka/bengaluru/bengaluru_master_plan_2015/tiles_png/12_2930_1901.png"
    ]
    
    for tile_path in test_tiles:
        if os.path.exists(tile_path):
            print(f"\n✅ Testing: {tile_path}")
            
            # Analyze the image
            img = Image.open(tile_path)
            file_size = os.path.getsize(tile_path)
            
            print(f"   File size: {file_size} bytes")
            
            # Get color data
            if img.mode == 'RGBA':
                img_rgb = img.convert('RGB')
                colors = img_rgb.getcolors(maxcolors=10000)
                
                if colors:
                    # Sort by frequency
                    colors.sort(key=lambda x: x[0], reverse=True)
                    
                    print(f"   Top 10 colors:")
                    for i, (count, (r, g, b)) in enumerate(colors[:10]):
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
                        elif hex_color.lower() == '#70a800':
                            print(f"       ✅ State Forest (Green)")
                        elif hex_color.lower() == '#73b2ff':
                            print(f"       ✅ Commercial Business (Light Blue)")
                        elif hex_color.lower() == '#d79e9e':
                            print(f"       ✅ Power/Water (Pink)")
                        elif hex_color.lower() == '#e1e1e1':
                            print(f"       ✅ Unclassified Use (Light Gray)")
                        elif hex_color.lower() == '#828282':
                            print(f"       ✅ Transport (Gray)")
                else:
                    print("   No colors found")
            else:
                print(f"   Image mode: {img.mode}")
        else:
            print(f"\n❌ Tile not found: {tile_path}")

if __name__ == "__main__":
    test_existing_tiles()
