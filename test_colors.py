#!/usr/bin/env python3
"""
Simple test to verify tile colors
"""

import requests
from PIL import Image
import io

def test_tile_colors():
    """Test tile generation and check colors"""
    
    print("🎨 Testing Tile Color Generation")
    print("=" * 50)
    
    # Test the master plan tile
    url = "http://localhost:8000/api/tiles/bengaluru/bengaluru_master_plan_2015/12/2930/1901.png"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print(f"✅ Tile generated successfully ({len(response.content)} bytes)")
            
            # Analyze the image
            img = Image.open(io.BytesIO(response.content))
            print(f"   Image size: {img.size}")
            print(f"   Image mode: {img.mode}")
            
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
                else:
                    print("   No colors found (possibly transparent)")
            else:
                print(f"   Image mode {img.mode} not supported for color analysis")
        else:
            print(f"❌ Failed to generate tile: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_tile_colors()
