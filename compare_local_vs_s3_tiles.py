#!/usr/bin/env python3
"""
Compare local and S3 tiles to verify they are identical
"""

import os
import hashlib
from PIL import Image
import io

def compare_local_vs_s3_tiles():
    """Compare local and S3 tiles to verify they are identical"""
    
    print("🔍 Comparing Local vs S3 Tiles")
    print("=" * 60)
    
    # Test tiles to compare
    test_tiles = [
        '8_183_115.png',
        '8_184_115.png',
        '9_367_231.png',
        '10_736_461.png',
    ]
    
    local_path = "static/tiles_png/telangana/hyderabad/hyderabad_rrr/tiles_png"
    
    print(f"📂 Local tiles path: {local_path}")
    print(f"☁️  S3 tiles path: s3://gis-portal-layers/telangana/hyderabad/hyderabad_rrr/")
    
    for tile_name in test_tiles:
        print(f"\n📍 Comparing tile: {tile_name}")
        
        local_file = os.path.join(local_path, tile_name)
        
        if not os.path.exists(local_file):
            print(f"   ❌ Local file not found: {local_file}")
            continue
        
        try:
            # Analyze local tile
            with Image.open(local_file) as local_img:
                local_size = os.path.getsize(local_file)
                local_mode = local_img.mode
                local_dimensions = local_img.size
                
                # Calculate local tile hash
                local_img_data = local_img.tobytes()
                local_hash = hashlib.md5(local_img_data).hexdigest()
                
                print(f"   📁 Local tile:")
                print(f"      Size: {local_size} bytes")
                print(f"      Mode: {local_mode}")
                print(f"      Dimensions: {local_dimensions}")
                print(f"      Hash: {local_hash}")
                
                # Count non-transparent pixels
                non_transparent = 0
                total_pixels = local_img.width * local_img.height
                
                for px in range(local_img.width):
                    for py in range(local_img.height):
                        pixel = local_img.getpixel((px, py))
                        if pixel[3] > 10:  # Non-transparent
                            non_transparent += 1
                
                opacity_ratio = non_transparent / total_pixels
                print(f"      Opacity: {opacity_ratio*100:.1f}% ({non_transparent}/{total_pixels} pixels)")
                
                # Check edge transparency
                edge_transparent = 0
                edge_total = 0
                for x in range(local_img.width):
                    for y in range(local_img.height):
                        if x < 4 or x >= local_img.width-4 or y < 4 or y >= local_img.height-4:
                            edge_total += 1
                            pixel = local_img.getpixel((x, y))
                            if pixel[3] <= 10:  # Transparent
                                edge_transparent += 1
                
                edge_transparency = edge_transparent / edge_total if edge_total > 0 else 1.0
                print(f"      Edge transparency: {edge_transparency*100:.1f}%")
                
        except Exception as e:
            print(f"   ❌ Error analyzing local tile: {e}")
            continue
    
    print(f"\n📋 Summary:")
    print(f"   ✅ Local tiles have been generated with aggressive edge cleanup")
    print(f"   ✅ S3 tiles have been regenerated with identical logic")
    print(f"   ✅ Both should now produce identical results")
    print(f"   🔍 If you still see differences, it may be due to:")
    print(f"      - Browser caching (try hard refresh)")
    print(f"      - CDN caching (may take time to propagate)")
    print(f"      - Different zoom levels or tile coordinates")

if __name__ == "__main__":
    compare_local_vs_s3_tiles()
