#!/usr/bin/env python
"""
CORRECTED test script for mapbox-vector-tile==2.0.1
This tests the proper LIST format and finds tiles with actual data
"""

import os
import django
import json

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from maps.models import City, DataLayer, GeoFeature
from maps.services import VectorTileService
from django.contrib.gis.geos import Polygon
import mercantile

def test_mapbox_vector_tile_correct_format():
    """Test the CORRECT format for mapbox-vector-tile==2.0.1"""
    print("🧪 Testing mapbox-vector-tile CORRECT Format")
    print("=" * 50)
    
    try:
        import mapbox_vector_tile
        print("✅ mapbox-vector-tile imported successfully")
        
        # CORRECT format for version 2.0.1 - LIST of dictionaries with 'name' key
        correct_format = [{
            'name': 'test_layer',
            'features': [
                {
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [0, 0]
                    },
                    'properties': {
                        'name': 'test_feature',
                        'id': 1
                    }
                }
            ]
        }]
        
        print("Testing CORRECT format (list of dicts with 'name' key)...")
        encoded = mapbox_vector_tile.encode(correct_format)
        print(f"✅ Correct format works: {len(encoded)} bytes")
        
        # Test decoding
        decoded = mapbox_vector_tile.decode(encoded)
        print(f"✅ Decoded successfully: {list(decoded.keys())}")
        
        # Test multiple layers
        multi_layer_format = [
            {
                'name': 'layer1',
                'features': [
                    {
                        'geometry': {'type': 'Point', 'coordinates': [0, 0]},
                        'properties': {'name': 'feature1'}
                    }
                ]
            },
            {
                'name': 'layer2', 
                'features': [
                    {
                        'geometry': {'type': 'Point', 'coordinates': [1, 1]},
                        'properties': {'name': 'feature2'}
                    }
                ]
            }
        ]
        
        encoded_multi = mapbox_vector_tile.encode(multi_layer_format)
        decoded_multi = mapbox_vector_tile.decode(encoded_multi)
        print(f"✅ Multi-layer format works: {list(decoded_multi.keys())}")
        
    except Exception as e:
        print(f"❌ mapbox-vector-tile test error: {e}")
        import traceback
        traceback.print_exc()

def find_tiles_with_data():
    """Find tiles that actually contain data"""
    print("\n🔍 Finding Tiles With Data")
    print("=" * 50)
    
    # Get a layer with the most features
    layers = DataLayer.objects.filter(
        is_processed=True,
        feature_count__gt=0
    ).order_by('-feature_count')[:3]
    
    if not layers.exists():
        print("❌ No layers with features found")
        return
    
    for layer in layers:
        print(f"\n📂 Testing layer: {layer.name} ({layer.feature_count} features)")
        
        # Calculate bounds if missing
        if not all([layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax]):
            print("   Calculating bounds...")
            layer.calculate_bbox()
            layer.refresh_from_db()
        
        if not all([layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax]):
            print("   ❌ No bounds available")
            continue
        
        print(f"   Bounds: {layer.bbox_xmin:.4f}, {layer.bbox_ymin:.4f} to {layer.bbox_xmax:.4f}, {layer.bbox_ymax:.4f}")
        
        # Test different zoom levels
        for zoom in [10, 11, 12, 13]:
            # Get tiles that intersect with layer bounds
            tiles = list(mercantile.tiles(
                layer.bbox_xmin, layer.bbox_ymin,
                layer.bbox_xmax, layer.bbox_ymax,
                zoom
            ))
            
            print(f"   Zoom {zoom}: {len(tiles)} total tiles")
            
            # Test first 3 tiles
            tiles_with_data = 0
            for i, tile in enumerate(tiles[:3]):
                # Check if tile intersects with features
                tile_bounds = mercantile.bounds(tile.x, tile.y, tile.z)
                tile_polygon = Polygon.from_bbox([
                    tile_bounds.west, tile_bounds.south, 
                    tile_bounds.east, tile_bounds.north
                ])
                
                # Count features in this tile
                feature_count = GeoFeature.objects.filter(
                    layer=layer,
                    geometry__intersects=tile_polygon,
                    is_valid=True
                ).count()
                
                if feature_count > 0:
                    tiles_with_data += 1
                    print(f"      ✅ Tile {tile.z}/{tile.x}/{tile.y}: {feature_count} features")
                    
                    # Test MVT generation for this tile
                    service = VectorTileService()
                    mvt_data = service.generate_tile(layer, tile.z, tile.x, tile.y)
                    if mvt_data:
                        print(f"         ✅ MVT generated: {len(mvt_data)} bytes")
                        
                        # Test decoding
                        try:
                            import mapbox_vector_tile
                            decoded = mapbox_vector_tile.decode(mvt_data)
                            print(f"         ✅ Decoded layers: {list(decoded.keys())}")
                            
                            # Provide test URL
                            print(f"         🔗 Test URL: /api/tiles/{layer.city.slug}/{layer.slug}/{tile.z}/{tile.x}/{tile.y}.mvt")
                            
                        except Exception as decode_error:
                            print(f"         ❌ Decode error: {decode_error}")
                    else:
                        print(f"         ❌ No MVT data generated")
                        
                    # Only test first working tile per zoom level
                    break
            
            if tiles_with_data == 0:
                print(f"      ⚠️  No tiles with data at zoom {zoom}")

def test_specific_coordinates():
    """Test specific coordinates that should have data"""
    print("\n🎯 Testing Specific Coordinates")
    print("=" * 50)
    
    # Test Bangalore center (should have data)
    bangalore_coords = [
        (12.9716, 77.5946),  # Bangalore center
        (12.9500, 77.6000),  # Slightly offset
        (13.0000, 77.5500),  # North-west
    ]
    
    layer = DataLayer.objects.filter(
        city__slug='bangalore',
        is_processed=True,
        feature_count__gt=0
    ).first()
    
    if not layer:
        print("❌ No Bangalore layers found")
        return
    
    print(f"Testing with layer: {layer.name}")
    
    service = VectorTileService()
    
    for lat, lng in bangalore_coords:
        for zoom in [10, 12, 14]:
            # Convert lat/lng to tile coordinates
            tile_x = int((lng + 180) / 360 * (2 ** zoom))
            tile_y = int((1 - (lat * 3.14159 / 180 + 1.5708) / 3.14159) / 2 * (2 ** zoom))
            
            print(f"\n📍 Testing {lat:.4f}, {lng:.4f} at zoom {zoom} -> tile {zoom}/{tile_x}/{tile_y}")
            
            # Check for features in this area
            tile_bounds = mercantile.bounds(tile_x, tile_y, zoom)
            tile_polygon = Polygon.from_bbox([
                tile_bounds.west, tile_bounds.south, 
                tile_bounds.east, tile_bounds.north
            ])
            
            feature_count = GeoFeature.objects.filter(
                layer=layer,
                geometry__intersects=tile_polygon,
                is_valid=True
            ).count()
            
            print(f"   Features in tile: {feature_count}")
            
            if feature_count > 0:
                mvt_data = service.generate_tile(layer, zoom, tile_x, tile_y)
                if mvt_data:
                    print(f"   ✅ MVT generated: {len(mvt_data)} bytes")
                    print(f"   🔗 Test URL: /api/tiles/{layer.city.slug}/{layer.slug}/{zoom}/{tile_x}/{tile_y}.mvt")
                else:
                    print(f"   ❌ No MVT data generated")

def test_api_endpoints_with_working_tiles():
    """Test API with coordinates that should work"""
    print("\n🌐 Testing API With Working Coordinates")
    print("=" * 50)
    
    import requests
    
    # First find a working tile
    layer = DataLayer.objects.filter(
        is_processed=True,
        feature_count__gt=100,  # Get a layer with substantial data
        bbox_xmin__isnull=False
    ).first()
    
    if not layer:
        print("❌ No suitable layer found")
        return
    
    print(f"Testing with: {layer.name} ({layer.feature_count} features)")
    
    # Calculate center of layer
    center_lat = (layer.bbox_ymin + layer.bbox_ymax) / 2
    center_lng = (layer.bbox_xmin + layer.bbox_xmax) / 2
    
    print(f"Layer center: {center_lat:.4f}, {center_lng:.4f}")
    
    # Test at zoom 11 (good balance)
    zoom = 11
    tile_x = int((center_lng + 180) / 360 * (2 ** zoom))
    tile_y = int((1 - (center_lat * 3.14159 / 180 + 1.5708) / 3.14159) / 2 * (2 ** zoom))
    
    test_url = f"http://localhost:8000/api/tiles/{layer.city.slug}/{layer.slug}/{zoom}/{tile_x}/{tile_y}.mvt"
    print(f"Testing: {test_url}")
    
    try:
        response = requests.get(test_url, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            if len(response.content) > 0:
                print(f"✅ SUCCESS: {len(response.content)} bytes")
                
                # Test decoding
                try:
                    import mapbox_vector_tile
                    decoded = mapbox_vector_tile.decode(response.content)
                    print(f"✅ Decoded successfully: {list(decoded.keys())}")
                    
                    for layer_name, layer_data in decoded.items():
                        feature_count = len(layer_data.get('features', []))
                        print(f"   Layer '{layer_name}': {feature_count} features")
                        
                except Exception as e:
                    print(f"❌ Decode error: {e}")
            else:
                print("⚠️  Empty response")
        else:
            print(f"❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Request error: {e}")

def main():
    print("🔧 FINAL CORRECTED Test for mapbox-vector-tile==2.0.1")
    print("=" * 60)
    
    test_mapbox_vector_tile_correct_format()
    find_tiles_with_data()
    test_specific_coordinates()
    test_api_endpoints_with_working_tiles()
    
    print("\n" + "=" * 60)
    print("🎯 WHAT YOU SHOULD SEE NOW:")
    print("✅ mapbox-vector-tile format test passes")
    print("✅ Tiles with data are found and listed")
    print("✅ MVT generation works without errors")
    print("✅ API returns tiles with actual data")
    
    print("\n🚀 NEXT STEPS:")
    print("1. Apply the FINAL CORRECT services.py changes")
    print("2. Test the working tile URLs provided above")
    print("3. Go to /map/ and try loading layers")
    print("4. Use the tile coordinates shown above in your map")

if __name__ == '__main__':
    main()