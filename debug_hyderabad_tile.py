#!/usr/bin/env python3
"""
Debug script to examine the Hyderabad highways MVT data
"""

import os
import sys
import django
import mapbox_vector_tile
import json

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from maps.models import DataLayer, City, State
from maps.services import VectorTileService

def debug_hyderabad_mvt():
    """Debug the Hyderabad highways MVT data"""
    
    print("🔍 Debugging Hyderabad Highways MVT Data")
    print("=" * 60)
    
    # Initialize services
    vector_service = VectorTileService()
    
    # Test the specific tile coordinates
    test_zoom = 9
    test_x = 367
    test_y = 231
    
    try:
        state = State.objects.get(slug='telangana')
        city = City.objects.get(slug='hyderabad', state_ref=state)
        layer = DataLayer.objects.get(slug='hyderabad_highways')
        
        print(f"✅ Testing layer: {layer.slug}")
        print(f"   City: {city.name}")
        print(f"   State: {state.name}")
        print(f"   Features: {layer.geofeature_set.count()}")
        
        # Generate MVT tile
        print(f"\n🗺️  Generating MVT tile for {test_zoom}/{test_x}/{test_y}")
        mvt_data = vector_service.generate_tile(layer, test_zoom, test_x, test_y)
        
        if not mvt_data:
            print("❌ Failed to generate MVT tile")
            return
        
        print(f"✅ MVT generated: {len(mvt_data)} bytes")
        
        # Decode and analyze MVT data
        print(f"\n🔍 Analyzing MVT Data")
        decoded_data = mapbox_vector_tile.decode(mvt_data)
        
        print(f"   Layers in MVT: {list(decoded_data.keys())}")
        
        for layer_name, layer_data in decoded_data.items():
            print(f"\n   Layer: {layer_name}")
            features = layer_data.get('features', [])
            print(f"   Features: {len(features)}")
            
            for i, feature in enumerate(features[:3]):  # Show first 3 features
                print(f"     Feature {i}:")
                print(f"       Type: {feature.get('geometry', {}).get('type', 'Unknown')}")
                print(f"       Properties: {feature.get('properties', {})}")
                
                geometry = feature.get('geometry', {})
                if geometry.get('type') == 'LineString':
                    coords = geometry.get('coordinates', [])
                    print(f"       LineString coordinates: {len(coords)} points")
                    if coords:
                        print(f"       First point: {coords[0]}")
                        print(f"       Last point: {coords[-1]}")
                elif geometry.get('type') == 'Polygon':
                    coords = geometry.get('coordinates', [])
                    print(f"       Polygon rings: {len(coords)}")
                    if coords and coords[0]:
                        print(f"       First ring points: {len(coords[0])}")
                        print(f"       First point: {coords[0][0]}")
        
        # Check if features are being filtered out
        print(f"\n🔍 Checking Feature Filtering")
        
        # Get tile bounds
        import mercantile
        bounds = mercantile.bounds(test_x, test_y, test_zoom)
        print(f"   Tile bounds: {bounds}")
        
        # Check features in tile
        from django.contrib.gis.geos import Polygon
        tile_bounds = Polygon.from_bbox([
            bounds.west, bounds.south, 
            bounds.east, bounds.north
        ])
        
        features_in_tile = layer.geofeature_set.filter(
            geometry__intersects=tile_bounds,
            is_valid=True
        )
        
        print(f"   Features intersecting tile: {features_in_tile.count()}")
        
        for feature in features_in_tile[:3]:
            print(f"     Feature {feature.id}:")
            print(f"       Geometry type: {feature.geometry.geom_type}")
            print(f"       Coordinates: {feature.geometry.num_coords}")
            print(f"       Properties: {feature.source_layer_name}, {feature.plu_primary_code}")
        
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_hyderabad_mvt()
