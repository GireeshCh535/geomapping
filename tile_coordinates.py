#!/usr/bin/env python3
"""
Tile Coordinate Analysis Script
Helps understand tile coordinates and investigate tile generation issues
"""

import sys
import os
import math

def tile_to_lat_lon(x, y, z):
    """
    Convert tile coordinates to lat/lon bounds.
    
    Args:
        x, y: Tile coordinates
        z: Zoom level
    
    Returns:
        tuple: (min_lat, min_lon, max_lat, max_lon)
    """
    n = 2.0 ** z
    lon_west = x / n * 360.0 - 180.0
    lon_east = (x + 1) / n * 360.0 - 180.0
    lat_north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    lat_south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    
    return lat_south, lon_west, lat_north, lon_east

def filename_to_coordinates(filename):
    """
    Try to extract coordinates from filename.
    Common patterns: z/x/y.mvt, tile_z_x_y.mvt, etc.
    """
    basename = os.path.basename(filename)
    name_without_ext = os.path.splitext(basename)[0]
    
    # Try different patterns
    patterns = [
        r'(\d+)_(\d+)_(\d+)',  # z_x_y
        r'tile_(\d+)_(\d+)_(\d+)',  # tile_z_x_y
        r'(\d+)/(\d+)/(\d+)',  # z/x/y
    ]
    
    import re
    for pattern in patterns:
        match = re.search(pattern, name_without_ext)
        if match:
            return tuple(map(int, match.groups()))
    
    return None

def analyze_tile_coordinates(filename):
    """
    Analyze tile coordinates and provide useful information.
    """
    print("🗺️  TILE COORDINATE ANALYSIS")
    print("=" * 50)
    
    # Try to extract coordinates from filename
    coords = filename_to_coordinates(filename)
    
    if coords:
        z, x, y = coords
        print(f"📍 Extracted coordinates from filename:")
        print(f"   Zoom level (z): {z}")
        print(f"   X coordinate: {x}")
        print(f"   Y coordinate: {y}")
        print()
        
        # Calculate bounds
        lat_south, lon_west, lat_north, lon_east = tile_to_lat_lon(x, y, z)
        
        print(f"🌍 Tile bounds:")
        print(f"   North: {lat_north:.6f}°")
        print(f"   South: {lat_south:.6f}°")
        print(f"   East:  {lon_east:.6f}°")
        print(f"   West:  {lon_west:.6f}°")
        print()
        
        print(f"📏 Tile size at this zoom level:")
        print(f"   Total tiles at zoom {z}: {2**z * 2**z:,}")
        print(f"   Tile width: {lon_east - lon_west:.6f}°")
        print(f"   Tile height: {lat_north - lat_south:.6f}°")
        print()
        
        # Check if this might be outside common bounds
        print(f"🔍 Coordinate analysis:")
        if lat_north > 85 or lat_south < -85:
            print("   ⚠️  Tile extends beyond normal map bounds")
        if lon_east > 180 or lon_west < -180:
            print("   ⚠️  Tile extends beyond longitude bounds")
        
        # Check zoom level appropriateness
        if z < 0:
            print("   ❌ Invalid zoom level (negative)")
        elif z > 22:
            print("   ⚠️  Very high zoom level (may cause issues)")
        elif z < 5:
            print("   ℹ️  Low zoom level (large area, may be empty)")
        else:
            print("   ✅ Zoom level looks reasonable")
        
    else:
        print("❓ Could not extract coordinates from filename")
        print(f"   Filename: {os.path.basename(filename)}")
        print()
        print("💡 Expected filename patterns:")
        print("   - z_x_y.mvt (e.g., 12_1234_5678.mvt)")
        print("   - tile_z_x_y.mvt")
        print("   - z/x/y.mvt")
        print()
        print("🔍 Please provide coordinates manually:")
        print("   python tile_coordinates.py <z> <x> <y>")

def manual_coordinate_analysis(z, x, y):
    """
    Analyze manually provided coordinates.
    """
    print(f"🗺️  MANUAL COORDINATE ANALYSIS")
    print("=" * 50)
    print(f"📍 Coordinates: z={z}, x={x}, y={y}")
    print()
    
    # Calculate bounds
    lat_south, lon_west, lat_north, lon_east = tile_to_lat_lon(x, y, z)
    
    print(f"🌍 Tile bounds:")
    print(f"   North: {lat_north:.6f}°")
    print(f"   South: {lat_south:.6f}°")
    print(f"   East:  {lon_east:.6f}°")
    print(f"   West:  {lon_west:.6f}°")
    print()
    
    print(f"📏 Tile size:")
    print(f"   Width: {lon_east - lon_west:.6f}°")
    print(f"   Height: {lat_north - lat_south:.6f}°")
    print()
    
    # Provide debugging suggestions
    print("💡 Debugging suggestions:")
    print("-" * 30)
    print("1. Check if your data covers this geographic area")
    print("2. Verify the zoom level is appropriate for your data")
    print("3. Check tile generation logs for this specific tile")
    print("4. Try generating adjacent tiles to see if they have data")
    print("5. Verify your data source and bounds")

def main():
    if len(sys.argv) == 2:
        # Analyze filename
        filename = sys.argv[1]
        analyze_tile_coordinates(filename)
    elif len(sys.argv) == 4:
        # Manual coordinates
        try:
            z, x, y = map(int, sys.argv[1:4])
            manual_coordinate_analysis(z, x, y)
        except ValueError:
            print("❌ Invalid coordinates. Please provide integers.")
            print("Usage: python tile_coordinates.py <z> <x> <y>")
    else:
        print("Usage:")
        print("  python tile_coordinates.py <filename>")
        print("  python tile_coordinates.py <z> <x> <y>")
        print()
        print("Examples:")
        print("  python tile_coordinates.py 30408.mvt")
        print("  python tile_coordinates.py 12 1234 5678")

if __name__ == "__main__":
    main() 