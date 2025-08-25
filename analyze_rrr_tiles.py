#!/usr/bin/env python3
"""
Analyze RRR tiles for quality and completeness
"""

import os
import sys
from PIL import Image
import glob

def analyze_rrr_tiles():
    """Analyze the generated RRR tiles"""
    
    print("🔍 Analyzing RRR Tiles Quality")
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
    
    # Analyze by zoom level
    zoom_stats = {}
    total_size = 0
    transparent_tiles = 0
    small_tiles = 0
    
    for tile_file in tile_files:
        try:
            # Extract zoom level from filename
            filename = os.path.basename(tile_file)
            parts = filename.replace('.png', '').split('_')
            if len(parts) >= 3:
                zoom = int(parts[0])
                x = int(parts[1])
                y = int(parts[2])
                
                # Get file size
                file_size = os.path.getsize(tile_file)
                total_size += file_size
                
                # Analyze image content
                with Image.open(tile_file) as img:
                    # Check if image is mostly transparent
                    if img.mode == 'RGBA':
                        # Count non-transparent pixels
                        non_transparent = 0
                        total_pixels = img.width * img.height
                        
                        for px in range(img.width):
                            for py in range(img.height):
                                pixel = img.getpixel((px, py))
                                if pixel[3] > 10:  # Non-transparent
                                    non_transparent += 1
                        
                        transparency_ratio = non_transparent / total_pixels
                        
                        if transparency_ratio < 0.01:  # Less than 1% non-transparent
                            transparent_tiles += 1
                        
                        if file_size < 500:  # Very small files might be empty
                            small_tiles += 1
                        
                        # Store stats by zoom level
                        if zoom not in zoom_stats:
                            zoom_stats[zoom] = {
                                'count': 0,
                                'total_size': 0,
                                'transparent': 0,
                                'small': 0,
                                'avg_size': 0,
                                'tiles': []
                            }
                        
                        zoom_stats[zoom]['count'] += 1
                        zoom_stats[zoom]['total_size'] += file_size
                        zoom_stats[zoom]['tiles'].append({
                            'x': x, 'y': y, 'size': file_size, 'transparency': transparency_ratio
                        })
                        
                        if transparency_ratio < 0.01:
                            zoom_stats[zoom]['transparent'] += 1
                        if file_size < 500:
                            zoom_stats[zoom]['small'] += 1
                
        except Exception as e:
            print(f"❌ Error analyzing {tile_file}: {e}")
    
    # Print summary statistics
    print(f"\n📈 Overall Statistics:")
    print(f"   Total tiles: {len(tile_files)}")
    print(f"   Total size: {total_size / 1024:.1f} KB")
    print(f"   Average size: {total_size / len(tile_files):.0f} bytes")
    print(f"   Transparent tiles: {transparent_tiles} ({transparent_tiles/len(tile_files)*100:.1f}%)")
    print(f"   Small tiles (<500B): {small_tiles} ({small_tiles/len(tile_files)*100:.1f}%)")
    
    # Print zoom level statistics
    print(f"\n🔍 Zoom Level Analysis:")
    for zoom in sorted(zoom_stats.keys()):
        stats = zoom_stats[zoom]
        avg_size = stats['total_size'] / stats['count'] if stats['count'] > 0 else 0
        
        print(f"\n   📍 Zoom {zoom}:")
        print(f"      Tiles: {stats['count']}")
        print(f"      Total size: {stats['total_size'] / 1024:.1f} KB")
        print(f"      Average size: {avg_size:.0f} bytes")
        print(f"      Transparent: {stats['transparent']} ({stats['transparent']/stats['count']*100:.1f}%)")
        print(f"      Small tiles: {stats['small']} ({stats['small']/stats['count']*100:.1f}%)")
        
        # Check for potential issues
        if stats['transparent'] > stats['count'] * 0.5:
            print(f"      ⚠️  HIGH TRANSPARENCY RATE - Many tiles appear empty")
        
        if stats['small'] > stats['count'] * 0.3:
            print(f"      ⚠️  MANY SMALL TILES - Possible rendering issues")
        
        # Show some sample tiles
        print(f"      Sample tiles:")
        for i, tile in enumerate(stats['tiles'][:5]):
            print(f"        {tile['x']}/{tile['y']}: {tile['size']}B, {tile['transparency']*100:.1f}% opaque")
    
    # Check for coverage gaps
    print(f"\n🔍 Coverage Analysis:")
    for zoom in sorted(zoom_stats.keys()):
        stats = zoom_stats[zoom]
        tiles = stats['tiles']
        
        if tiles:
            # Check if tiles form a continuous area
            x_coords = [t['x'] for t in tiles]
            y_coords = [t['y'] for t in tiles]
            
            x_range = max(x_coords) - min(x_coords) + 1
            y_range = max(y_coords) - min(y_coords) + 1
            expected_tiles = x_range * y_range
            actual_tiles = len(tiles)
            
            print(f"   📍 Zoom {zoom}: {actual_tiles}/{expected_tiles} tiles ({actual_tiles/expected_tiles*100:.1f}% coverage)")
            
            if actual_tiles < expected_tiles * 0.8:
                print(f"      ⚠️  POTENTIAL COVERAGE GAPS - Missing tiles detected")
    
    # Quality assessment
    print(f"\n🎯 Quality Assessment:")
    
    if transparent_tiles / len(tile_files) < 0.1:
        print(f"   ✅ GOOD: Low transparency rate ({transparent_tiles/len(tile_files)*100:.1f}%)")
    else:
        print(f"   ⚠️  CONCERN: High transparency rate ({transparent_tiles/len(tile_files)*100:.1f}%)")
    
    if small_tiles / len(tile_files) < 0.2:
        print(f"   ✅ GOOD: Low small tile rate ({small_tiles/len(tile_files)*100:.1f}%)")
    else:
        print(f"   ⚠️  CONCERN: Many small tiles ({small_tiles/len(tile_files)*100:.1f}%)")
    
    if len(zoom_stats) >= 3:
        print(f"   ✅ GOOD: Comprehensive zoom coverage ({len(zoom_stats)} levels)")
    else:
        print(f"   ⚠️  LIMITED: Only {len(zoom_stats)} zoom levels")
    
    print(f"\n📋 Summary:")
    if transparent_tiles / len(tile_files) < 0.1 and small_tiles / len(tile_files) < 0.2:
        print(f"   🎉 EXCELLENT: RRR tiles appear to be rendering correctly!")
        print(f"   ✅ No significant transparency issues")
        print(f"   ✅ No significant rendering problems")
        print(f"   ✅ Good file size distribution")
    elif transparent_tiles / len(tile_files) < 0.3 and small_tiles / len(tile_files) < 0.5:
        print(f"   ✅ GOOD: RRR tiles are mostly working well")
        print(f"   ⚠️  Some minor issues detected but overall acceptable")
    else:
        print(f"   ❌ ISSUES: Significant problems detected with RRR tile rendering")
        print(f"   🔧 May need further investigation and fixes")

if __name__ == "__main__":
    analyze_rrr_tiles()
