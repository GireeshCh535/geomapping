#!/usr/bin/env python3
"""
Test the generated static PNG tiles
"""

from PIL import Image
import os

def test_static_tiles():
    """Test generated static tiles"""
    
    print("🎨 Testing Generated Static PNG Tiles")
    print("=" * 50)
    
    # Test a master plan tile
    tile_path = "static/tiles_png/karnataka/bengaluru/bengaluru_master_plan_2015/tiles_png/10_732_474.png"
    
    if os.path.exists(tile_path):
        print(f"✅ Found tile: {tile_path}")
        
        # Analyze the image
        img = Image.open(tile_path)
        print(f"   Image size: {img.size}")
        print(f"   Image mode: {img.mode}")
        print(f"   File size: {os.path.getsize(tile_path)} bytes")
        
        # Get color data
        if img.mode == 'RGBA':
            # Convert to RGB for analysis
            img_rgb = img.convert('RGB')
            colors = img_rgb.getcolors(maxcolors=10000)
            
            if colors:
                print(f"   Found {len(colors)} unique colors")
                # Sort by frequency
                colors.sort(key=lambda x: x[0], reverse=True)
                
                print("   Top 10 colors:")
                for i, (count, (r, g, b)) in enumerate(colors[:10]):
                    hex_color = f"#{r:02x}{g:02x}{b:02x}"
                    print(f"     {hex_color}: {count} pixels")
                    
                    # Check if this matches expected colors
                    if hex_color.lower() == '#ffc400':  # Residential Mixed
                        print(f"     ✅ Matches Residential Mixed color!")
                    elif hex_color.lower() == '#004da8':  # Commercial Central
                        print(f"     ✅ Matches Commercial Central color!")
                    elif hex_color.lower() == '#aa66b2':  # Industrial
                        print(f"     ✅ Matches Industrial color!")
                    elif hex_color.lower() == '#267300':  # Drains
                        print(f"     ✅ Matches Drains color!")
            else:
                print("   No colors found (possibly transparent)")
        else:
            print(f"   Image mode {img.mode} not supported for color analysis")
    else:
        print(f"❌ Tile not found: {tile_path}")
    
    # Test a highways tile
    highways_tile = "static/tiles_png/karnataka/bengaluru/bengaluru_highways/tiles_png/10_732_474.png"
    if os.path.exists(highways_tile):
        print(f"\n✅ Found highways tile: {highways_tile}")
        img = Image.open(highways_tile)
        print(f"   File size: {os.path.getsize(highways_tile)} bytes")
        print(f"   Image size: {img.size}")
    else:
        print(f"\n❌ Highways tile not found: {highways_tile}")

if __name__ == "__main__":
    test_static_tiles()
