#!/usr/bin/env python3
"""
Tile ID Decoder
Attempts to decode tile IDs and find corresponding coordinates
"""

import sys
import math

def decode_tile_id(tile_id):
    """
    Try to decode a tile ID number into possible coordinates.
    Common encoding schemes:
    - z * 1000000 + x * 1000 + y
    - x * 1000 + y (assuming fixed zoom)
    - Hash of coordinates
    """
    
    print(f"🔍 DECODING TILE ID: {tile_id}")
    print("=" * 50)
    
    # Method 1: z * 1000000 + x * 1000 + y
    print("📊 Method 1: z * 1000000 + x * 1000 + y")
    for z in range(0, 23):  # Common zoom levels
        remainder = tile_id - (z * 1000000)
        if remainder >= 0:
            x = remainder // 1000
            y = remainder % 1000
            if x < 2**z and y < 2**z:  # Valid tile coordinates
                print(f"   z={z}, x={x}, y={y} -> {z}/{x}/{y}")
    
    print()
    
    # Method 2: x * 1000 + y (assuming zoom 12 for Bangalore)
    print("📊 Method 2: x * 1000 + y (zoom 12)")
    z = 12
    x = tile_id // 1000
    y = tile_id % 1000
    if x < 2**z and y < 2**z:
        print(f"   z={z}, x={x}, y={y} -> {z}/{x}/{y}")
        # Calculate bounds for this tile
        bounds = tile_to_lat_lon(x, y, z)
        print(f"   Bounds: {bounds[0]:.6f}°S, {bounds[1]:.6f}°W to {bounds[2]:.6f}°N, {bounds[3]:.6f}°E")
    
    print()
    
    # Method 3: Different multipliers
    print("📊 Method 3: Alternative multipliers")
    multipliers = [100, 1000, 10000, 100000]
    for mult in multipliers:
        x = tile_id // mult
        y = tile_id % mult
        for z in range(8, 16):  # Common zoom range
            if x < 2**z and y < 2**z:
                print(f"   mult={mult}: z={z}, x={x}, y={y} -> {z}/{x}/{y}")
    
    print()
    
    # Method 4: Check if it's a hash of coordinates
    print("📊 Method 4: Possible hash values")
    # Common hash: (x << 16) | y
    x = (tile_id >> 16) & 0xFFFF
    y = tile_id & 0xFFFF
    for z in range(8, 16):
        if x < 2**z and y < 2**z:
            print(f"   hash: z={z}, x={x}, y={y} -> {z}/{x}/{y}")

def tile_to_lat_lon(x, y, z):
    """Convert tile coordinates to lat/lon bounds."""
    n = 2.0 ** z
    lon_west = x / n * 360.0 - 180.0
    lon_east = (x + 1) / n * 360.0 - 180.0
    lat_north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    lat_south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    
    return lat_south, lon_west, lat_north, lon_east

def check_bangalore_bounds(coords_list):
    """
    Check if any of the decoded coordinates fall within Bangalore bounds.
    """
    print("\n🌍 BANGALORE BOUNDS CHECK")
    print("=" * 40)
    
    # Bangalore approximate bounds
    bangalore_bounds = {
        'min_lat': 12.7,
        'max_lat': 13.2,
        'min_lng': 77.4,
        'max_lng': 77.8
    }
    
    print(f"Bangalore bounds: {bangalore_bounds['min_lat']}°S to {bangalore_bounds['max_lat']}°N, "
          f"{bangalore_bounds['min_lng']}°W to {bangalore_bounds['max_lng']}°E")
    print()
    
    for z, x, y in coords_list:
        bounds = tile_to_lat_lon(x, y, z)
        lat_south, lon_west, lat_north, lon_east = bounds
        
        # Check if tile intersects with Bangalore
        intersects = (
            lat_south <= bangalore_bounds['max_lat'] and
            lat_north >= bangalore_bounds['min_lat'] and
            lon_west <= bangalore_bounds['max_lng'] and
            lon_east >= bangalore_bounds['min_lng']
        )
        
        status = "✅ INTERSECTS" if intersects else "❌ OUTSIDE"
        print(f"{status} {z}/{x}/{y}: {lat_south:.3f}°S to {lat_north:.3f}°N, "
              f"{lon_west:.3f}°W to {lon_east:.3f}°E")

def main():
    if len(sys.argv) != 2:
        print("Usage: python decode_tile_id.py <tile_id>")
        print("Example: python decode_tile_id.py 30408")
        sys.exit(1)
    
    try:
        tile_id = int(sys.argv[1])
        decode_tile_id(tile_id)
        
        # Generate some test coordinates to check
        test_coords = []
        
        # Method 2 result (most likely)
        z, x, y = 12, tile_id // 1000, tile_id % 1000
        if x < 2**z and y < 2**z:
            test_coords.append((z, x, y))
        
        # Add some other possibilities
        for z in range(10, 15):
            remainder = tile_id - (z * 1000000)
            if remainder >= 0:
                x = remainder // 1000
                y = remainder % 1000
                if x < 2**z and y < 2**z:
                    test_coords.append((z, x, y))
        
        if test_coords:
            check_bangalore_bounds(test_coords)
        
    except ValueError:
        print("❌ Invalid tile ID. Please provide a number.")
        sys.exit(1)

if __name__ == "__main__":
    main() 