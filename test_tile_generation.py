#!/usr/bin/env python3
"""
Test Tile Generation Process
Tests the actual tile generation to verify it's working correctly
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from maps.models import City, DataLayer
from maps.services import VectorTileService
import mercantile

def test_layer_bounds():
    """Test layer bounds calculation"""
    print("🔍 TESTING LAYER BOUNDS")
    print("=" * 50)
    
    try:
        # Get Bangalore city
        city = City.objects.get(slug='bangalore')
        print(f"✅ Found city: {city.name}")
        
        # Get processed layers
        layers = DataLayer.objects.filter(city=city, is_processed=True)
        print(f"✅ Found {layers.count()} processed layers")
        
        tile_service = VectorTileService()
        
        for layer in layers:
            print(f"\n📂 Layer: {layer.name} ({layer.slug})")
            print(f"   Features: {layer.feature_count:,}")
            
            # Get bounds
            bounds = tile_service._get_layer_bounds(layer)
            if bounds:
                print(f"   Bounds: {bounds['west']:.6f}°W to {bounds['east']:.6f}°E, "
                      f"{bounds['south']:.6f}°S to {bounds['north']:.6f}°N")
                
                # Test tile generation for zoom 12
                tiles = list(mercantile.tiles(
                    bounds['west'], bounds['south'],
                    bounds['east'], bounds['north'],
                    12
                ))
                
                print(f"   Zoom 12 tiles: {len(tiles)}")
                if tiles:
                    print(f"   Sample tiles: {[f'{t.z}/{t.x}/{t.y}' for t in tiles[:5]]}")
                    
                    # Test first tile
                    first_tile = tiles[0]
                    mvt_data = tile_service.generate_tile(layer, first_tile.z, first_tile.x, first_tile.y)
                    
                    if mvt_data:
                        print(f"   ✅ Sample tile {first_tile.z}/{first_tile.x}/{first_tile.y}: {len(mvt_data)} bytes")
                    else:
                        print(f"   ⚠️  Sample tile {first_tile.z}/{first_tile.x}/{first_tile.y}: No data")
            else:
                print(f"   ❌ No bounds available")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_specific_tiles():
    """Test specific tile coordinates from coordinates.js"""
    print("\n🧪 TESTING SPECIFIC TILES")
    print("=" * 50)
    
    try:
        city = City.objects.get(slug='bangalore')
        tile_service = VectorTileService()
        
        # Test coordinates from your coordinates.js file
        test_coords = [
            # Residential Main
            ("residential_main_", 12, 3119, 3222),
            # State Forest Protected  
            ("stateforest_valley_protectedland_", 12, 3116, 3224),
            # Commercial Central
            ("commercial_central_", 12, 3117, 3221),
            # Agricultural Land
            ("agricultural_land", 12, 3118, 3223),
            # High Tech
            ("hightech", 12, 3118, 3224),
        ]
        
        for layer_slug, z, x, y in test_coords:
            try:
                layer = DataLayer.objects.get(city=city, slug=layer_slug)
                print(f"\n🔹 Testing {layer_slug} {z}/{x}/{y}")
                
                mvt_data = tile_service.generate_tile(layer, z, x, y)
                
                if mvt_data:
                    print(f"   ✅ Generated: {len(mvt_data)} bytes")
                    
                    # Validate the MVT
                    import mapbox_vector_tile
                    decoded = mapbox_vector_tile.decode(mvt_data)
                    if decoded:
                        total_features = sum(len(layer_data.get('features', [])) for layer_data in decoded.values())
                        print(f"   📊 Features: {total_features}")
                        for layer_name, layer_data in decoded.items():
                            features = layer_data.get('features', [])
                            print(f"   📋 Layer '{layer_name}': {len(features)} features")
                    else:
                        print(f"   ❌ Failed to decode MVT")
                else:
                    print(f"   ⚠️  No data generated")
                    
            except DataLayer.DoesNotExist:
                print(f"   ❌ Layer not found: {layer_slug}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_test_tiles():
    """Generate some test tiles and save them"""
    print("\n📁 GENERATING TEST TILES")
    print("=" * 50)
    
    try:
        city = City.objects.get(slug='bangalore')
        tile_service = VectorTileService()
        
        # Find a layer with data
        layer = DataLayer.objects.filter(city=city, is_processed=True, feature_count__gt=0).first()
        
        if not layer:
            print("❌ No layers with data found")
            return False
        
        print(f"📂 Using layer: {layer.name} ({layer.feature_count:,} features)")
        
        # Generate a few test tiles
        test_tiles = [
            (12, 3119, 3222),  # From coordinates.js
            (12, 3116, 3224),  # From coordinates.js
            (12, 3117, 3221),  # From coordinates.js
        ]
        
        for z, x, y in test_tiles:
            print(f"\n🔹 Generating tile {z}/{x}/{y}")
            
            mvt_data = tile_service.generate_tile(layer, z, x, y)
            
            if mvt_data:
                filename = f"test_tile_{layer.slug}_{z}_{x}_{y}.mvt"
                with open(filename, 'wb') as f:
                    f.write(mvt_data)
                
                print(f"   ✅ Saved: {filename} ({len(mvt_data)} bytes)")
                
                # Validate
                import mapbox_vector_tile
                decoded = mapbox_vector_tile.decode(mvt_data)
                if decoded:
                    total_features = sum(len(layer_data.get('features', [])) for layer_data in decoded.values())
                    print(f"   📊 Features: {total_features}")
            else:
                print(f"   ⚠️  No data")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🚀 Tile Generation Test Suite")
    print("=" * 60)
    
    # Test 1: Layer bounds
    if not test_layer_bounds():
        print("❌ Layer bounds test failed")
        return
    
    # Test 2: Specific tiles
    if not test_specific_tiles():
        print("❌ Specific tiles test failed")
        return
    
    # Test 3: Generate test files
    if not generate_test_tiles():
        print("❌ Test tile generation failed")
        return
    
    print("\n✅ All tests completed successfully!")
    print("\n📋 Next steps:")
    print("1. Check the generated test_tile_*.mvt files")
    print("2. Validate them with: python validate_mvt.py test_tile_*.mvt")
    print("3. Start your Django server and test via HTTP")

if __name__ == "__main__":
    main() 