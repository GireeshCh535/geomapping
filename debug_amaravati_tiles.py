#!/usr/bin/env python3
"""
Debug script for Amaravati tile generation issue
Tests coordinates [80.45215550279937, 16.518144085425448] across zoom levels 8-18
"""

import os
import sys
import django
import mercantile

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from maps.models import City, DataLayer, GeoFeature
from maps.services import VectorTileService

def test_amaravati_coordinates():
    """Test tile generation for Amaravati coordinates across zoom levels"""
    
    test_lng, test_lat = 80.45215550279937, 16.518144085425448
    
    print(f"🔍 Testing Amaravati coordinates: [{test_lng}, {test_lat}]")
    print("=" * 80)
    
    try:
        city = City.objects.get(slug='amaravati', is_active=True)
        print(f"✅ Found city: {city.name}")
        
        layers = DataLayer.objects.filter(city=city, is_processed=True).select_related('category')
        print(f"📋 Found {layers.count()} processed layers")
        
        if not layers.exists():
            print("❌ No processed layers found for Amaravati")
            return
        
        tile_service = VectorTileService()
        
        # Test each zoom level
        for zoom in range(8, 19):
            print(f"\n📍 Testing Zoom Level {zoom}")
            print("-" * 40)
            
            tile = mercantile.tile(test_lng, test_lat, zoom)
            bounds = mercantile.bounds(tile)
            
            print(f"   Tile: {tile.z}/{tile.x}/{tile.y}")
            print(f"   Bounds: {bounds.west:.6f}, {bounds.south:.6f} to {bounds.east:.6f}, {bounds.north:.6f}")
            
            for layer in layers:
                print(f"\n   📂 Layer: {layer.name} ({layer.slug})")
                
                total_features = GeoFeature.objects.filter(layer=layer, is_valid=True).count()
                print(f"      Total features: {total_features}")
                
                if total_features == 0:
                    print(f"      ⚠️  No features in layer")
                    continue
                
                layer_bounds = tile_service._get_layer_bounds(layer)
                if layer_bounds:
                    print(f"      Layer bounds: {layer_bounds}")
                    
                    tile_bounds_polygon = tile_service._get_tile_bounds(tile.z, tile.x, tile.y)
                    
                    intersecting_features = GeoFeature.objects.filter(
                        layer=layer,
                        geometry__intersects=tile_bounds_polygon,
                        is_valid=True
                    ).count()
                    
                    print(f"      Features in tile: {intersecting_features}")
                    
                    if intersecting_features > 0:
                        print(f"      🔧 Attempting tile generation...")
                        mvt_data = tile_service.generate_tile(layer, tile.z, tile.x, tile.y)
                        
                        if mvt_data:
                            print(f"      ✅ Tile generated: {len(mvt_data)} bytes")
                        else:
                            print(f"      ❌ Tile generation failed")
                    else:
                        print(f"      ⚠️  No features intersect with tile bounds")
                else:
                    print(f"      ❌ No bounds available for layer")
        
    except City.DoesNotExist:
        print(f"❌ City 'amaravati' not found")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 AMARAVATI TILE DEBUGGING SCRIPT")
    print("=" * 80)
    
    test_amaravati_coordinates()
    
    print(f"\n✅ Debugging complete!")
