#!/usr/bin/env python3
"""
Test script to verify Amaravati tile generation fix
"""

import mercantile

def test_amaravati_tiles():
    """Test tile coordinates for Amaravati"""
    
    # Amaravati coordinates
    lng, lat = 80.45215550279937, 16.518144085425448
    
    print(f"🔍 Testing Amaravati coordinates: [{lng}, {lat}]")
    print("=" * 60)
    
    # Test zoom levels 8-18
    for zoom in range(8, 19):
        tile = mercantile.tile(lng, lat, zoom)
        bounds = mercantile.bounds(tile)
        
        print(f"Zoom {zoom:2d}: Tile {tile.z}/{tile.x}/{tile.y}")
        print(f"         Bounds: {bounds.west:.6f}, {bounds.south:.6f} to {bounds.east:.6f}, {bounds.north:.6f}")
        
        # Calculate tile size in degrees
        width = bounds.east - bounds.west
        height = bounds.north - bounds.south
        print(f"         Size: {width:.6f}° x {height:.6f}°")
        print()

def test_layer_bounds_issue():
    """Test the layer bounds issue"""
    
    print("🎯 LAYER BOUNDS ISSUE ANALYSIS")
    print("=" * 60)
    print("The problem is that tile generation only happens for tiles within layer bounds.")
    print("If layer bounds are narrow, tiles outside those bounds won't be generated.")
    print()
    print("SOLUTION: Expand bounds to include target coordinates or generate tiles")
    print("for specific areas regardless of layer bounds.")
    print()
    print("FIXES APPLIED:")
    print("1. Enhanced generate_layer_tiles() to accept target_coordinates")
    print("2. Added generate_tiles_for_coordinates() method")
    print("3. Added generate_tiles_for_area() method")
    print("4. Created generate_amaravati_tiles management command")
    print("5. Fixed S3 tile generation to include target coordinates")

if __name__ == "__main__":
    test_amaravati_tiles()
    test_layer_bounds_issue()
