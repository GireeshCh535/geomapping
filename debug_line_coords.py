#!/usr/bin/env python3
"""
Debug script to examine line coordinates in detail
"""

import os
import sys
import django
import mapbox_vector_tile

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from maps.models import DataLayer, City, State
from maps.services import VectorTileService

def debug_line_coordinates():
    """Debug line coordinates in detail"""
    
    print("🔍 Debugging Line Coordinates")
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
        
        # Generate MVT tile
        mvt_data = vector_service.generate_tile(layer, test_zoom, test_x, test_y)
        
        if not mvt_data:
            print("❌ Failed to generate MVT tile")
            return
        
        # Decode and analyze MVT data
        decoded_data = mapbox_vector_tile.decode(mvt_data)
        
        for layer_name, layer_data in decoded_data.items():
            features = layer_data.get('features', [])
            
            for i, feature in enumerate(features):
                print(f"\nFeature {i}:")
                geometry = feature.get('geometry', {})
                geom_type = geometry.get('type', '')
                coords = geometry.get('coordinates', [])
                
                print(f"  Type: {geom_type}")
                print(f"  Raw coordinates: {coords}")
                
                if geom_type == 'LineString':
                    # Test coordinate scaling
                    tile_size = 256
                    scaled_coords = []
                    
                    for coord in coords:
                        if (isinstance(coord, (list, tuple)) and len(coord) >= 2 and
                            isinstance(coord[0], (int, float)) and isinstance(coord[1], (int, float))):
                            # Scale coordinates
                            x = int((coord[0] / 4096.0) * tile_size)
                            y = int((coord[1] / 4096.0) * tile_size)
                            scaled_coords.append((x, y))
                    
                    print(f"  Scaled coordinates: {scaled_coords}")
                    
                    # Check if coordinates are within bounds
                    for x, y in scaled_coords:
                        if 0 <= x < tile_size and 0 <= y < tile_size:
                            print(f"    ✅ Point ({x}, {y}) is within bounds")
                        else:
                            print(f"    ❌ Point ({x}, {y}) is OUT OF BOUNDS")
        
        # Also check the original features
        print(f"\n🔍 Original Features in Database:")
        import mercantile
        from django.contrib.gis.geos import Polygon
        
        bounds = mercantile.bounds(test_x, test_y, test_zoom)
        tile_bounds = Polygon.from_bbox([
            bounds.west, bounds.south, 
            bounds.east, bounds.north
        ])
        
        features_in_tile = layer.geofeature_set.filter(
            geometry__intersects=tile_bounds,
            is_valid=True
        )
        
        for feature in features_in_tile[:2]:
            print(f"\nFeature {feature.id}:")
            print(f"  Geometry type: {feature.geometry.geom_type}")
            print(f"  Coordinates: {feature.geometry.num_coords}")
            
            # Get a sample of coordinates
            if hasattr(feature.geometry, 'coords'):
                sample_coords = list(feature.geometry.coords)[:5]
                print(f"  Sample coords: {sample_coords}")
        
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_line_coordinates()
