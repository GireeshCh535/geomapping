#!/usr/bin/env python3
"""
Test coordinate transformation for RRR tiles
"""

import os
import sys
import django
import mercantile

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from maps.models import DataLayer, GeoFeature

def test_coordinate_transform():
    """Test coordinate transformation for problematic tiles"""
    
    print("🔍 Testing Coordinate Transformation")
    print("=" * 60)
    
    layer = DataLayer.objects.get(slug='hyderabad_rrr')
    features = GeoFeature.objects.filter(layer=layer)
    
    # Test the problematic tile
    z, x, y = 10, 733, 462
    
    # Get tile bounds
    bounds = mercantile.bounds(x, y, z)
    print(f"📍 Tile {z}/{x}/{y} bounds: {bounds}")
    
    # Get features that should intersect
    from django.contrib.gis.geos import Polygon
    bbox_polygon = Polygon.from_bbox((
        bounds.west, bounds.south, bounds.east, bounds.north
    ))
    
    features_in_tile = GeoFeature.objects.filter(
        layer=layer,
        geometry__intersects=bbox_polygon
    )
    
    print(f"📊 Features in tile: {features_in_tile.count()}")
    
    for i, feature in enumerate(features_in_tile):
        print(f"\n📍 Feature {i}:")
        print(f"   Type: {feature.geometry.geom_type}")
        print(f"   Length: {feature.geometry.length}")
        print(f"   Original coords: {len(feature.geometry.coords)} points")
        
        # Test coordinate transformation
        coords = feature.geometry.coords
        print(f"   First 3 original coords: {coords[:3]}")
        
        # Transform to tile coordinates with proper clamping
        transformed_coords = []
        for coord in coords:
            lng, lat = coord
            tile_x = (lng - bounds.west) / (bounds.east - bounds.west) * 4096
            tile_y = (bounds.north - lat) / (bounds.north - bounds.south) * 4096
            
            # Clamp coordinates to valid range (0-4096)
            tile_x = max(0, min(4096, int(tile_x)))
            tile_y = max(0, min(4096, int(tile_y)))
            
            transformed_coords.append([tile_x, tile_y])
        
        print(f"   First 3 transformed coords: {transformed_coords[:3]}")
        
        # Check if coordinates are reasonable
        if transformed_coords:
            min_x = min(c[0] for c in transformed_coords)
            max_x = max(c[0] for c in transformed_coords)
            min_y = min(c[1] for c in transformed_coords)
            max_y = max(c[1] for c in transformed_coords)
            
            print(f"   Transformed bounds: x({min_x}-{max_x}), y({min_y}-{max_y})")
            print(f"   Extent: {max_x - min_x} x {max_y - min_y}")
            
            # Check if coordinates are within reasonable range
            if min_x < -1000 or max_x > 5096 or min_y < -1000 or max_y > 5096:
                print(f"   ⚠️  COORDINATES OUT OF RANGE!")
            elif max_x - min_x > 5000 or max_y - min_y > 5000:
                print(f"   ⚠️  EXTENT TOO LARGE!")
            else:
                print(f"   ✅ Coordinates look reasonable")

if __name__ == "__main__":
    test_coordinate_transform()
