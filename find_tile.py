#!/usr/bin/env python3
"""
Find tile coordinates for specific feature coordinates
"""

import mercantile

def find_tile_for_coords(lng, lat, zoom_levels=[10, 11, 12, 13, 14]):
    """Find tile coordinates for given longitude/latitude"""
    
    print(f"📍 Coordinates: ({lng}, {lat})")
    print("=" * 50)
    
    for zoom in zoom_levels:
        tile = mercantile.tile(lng, lat, zoom)
        print(f"Zoom {zoom}: {tile.z}/{tile.x}/{tile.y}")
        
        # Get tile bounds
        bounds = mercantile.bounds(tile)
        print(f"  Bounds: {bounds.west:.4f}, {bounds.south:.4f} to {bounds.east:.4f}, {bounds.north:.4f}")

if __name__ == "__main__":
    # Test coordinates from the features
    test_coords = [
        (77.5805, 12.8025),
        (77.5806, 12.8027),
        (77.5807, 12.8028),
    ]
    
    for lng, lat in test_coords:
        print(f"\n🔍 Finding tiles for ({lng}, {lat}):")
        find_tile_for_coords(lng, lat)
        print()
