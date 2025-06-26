#!/usr/bin/env python
"""
Analyze what's actually inside the MVT tiles
This will tell us exactly what source-layer names to use
"""

import os
import django
import requests

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from maps.models import DataLayer
import mapbox_vector_tile

def analyze_mvt_tile(city_slug, layer_slug, z, x, y):
    """Download and analyze a specific MVT tile"""
    
    url = f"http://localhost:8000/api/tiles/{city_slug}/{layer_slug}/{z}/{x}/{y}.mvt"
    print(f"\n🔍 Analyzing: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Size: {len(response.content)} bytes")
        
        if response.status_code == 200 and len(response.content) > 0:
            # Decode MVT
            try:
                decoded = mapbox_vector_tile.decode(response.content)
                print(f"   ✅ Successfully decoded MVT")
                print(f"   📊 Layers in MVT: {list(decoded.keys())}")
                
                for layer_name, layer_data in decoded.items():
                    features = layer_data.get('features', [])
                    print(f"   📂 Layer '{layer_name}': {len(features)} features")
                    
                    if features:
                        # Show sample feature properties
                        sample_props = features[0].get('properties', {})
                        print(f"      Sample properties: {list(sample_props.keys())}")
                        
                        # Show sample values
                        for key, value in list(sample_props.items())[:3]:
                            print(f"         {key}: {value}")
                
                return decoded
                
            except Exception as decode_error:
                print(f"   ❌ MVT decode error: {decode_error}")
                return None
        else:
            print(f"   ⚠️  No data or error")
            return None
            
    except Exception as e:
        print(f"   ❌ Request error: {e}")
        return None

def test_working_coordinates():
    """Test the coordinates we know have data"""
    
    print("🎯 Testing Known Working Coordinates")
    print("=" * 50)
    
    # From your test results
    working_tiles = [
        ('bangalore', 'residential_main', 10, 732, 474),    # 30,974 features
        ('bangalore', 'agricultural_land', 10, 732, 474),   # 2,514 features  
        ('bangalore', 'defense', 10, 732, 474),             # Should have data
        ('bangalore', 'residential_main', 11, 1464, 948),   # 221 features
    ]
    
    results = {}
    
    for city, layer, z, x, y in working_tiles:
        print(f"\n📍 Testing {layer} at {z}/{x}/{y}")
        decoded = analyze_mvt_tile(city, layer, z, x, y)
        if decoded:
            results[layer] = {
                'tile_coords': f"{z}/{x}/{y}",
                'mvt_layers': list(decoded.keys()),
                'features': {name: len(data.get('features', [])) for name, data in decoded.items()}
            }
    
    return results

def generate_frontend_config(results):
    """Generate the correct frontend configuration"""
    
    print(f"\n🔧 FRONTEND CONFIGURATION")
    print("=" * 50)
    
    print("Use these EXACT source-layer names in your map.html:")
    print("")
    
    for layer_slug, data in results.items():
        mvt_layers = data['mvt_layers']
        if mvt_layers:
            print(f"Layer: {layer_slug}")
            print(f"   Source-layer: '{mvt_layers[0]}'  // Use this exact string")
            print(f"   Tile coords: {data['tile_coords']}")
            print(f"   Features: {data['features']}")
            print("")

def test_defense_specifically():
    """Test Defense layer specifically since that's what user was testing"""
    
    print(f"\n🛡️  DEFENSE LAYER SPECIFIC TEST")
    print("=" * 50)
    
    # Try multiple coordinates for Defense layer
    defense_coords = [
        (10, 732, 474),  # Same as other working layers
        (11, 1464, 948), # Higher zoom
        (12, 2928, 1896), # Even higher zoom
    ]
    
    for z, x, y in defense_coords:
        print(f"\n🔍 Defense at {z}/{x}/{y}")
        decoded = analyze_mvt_tile('bangalore', 'defense', z, x, y)
        
        if decoded:
            print(f"   🎉 FOUND DATA!")
            return z, x, y, decoded
    
    print(f"   ❌ No data found in any tested coordinates")
    return None

def main():
    print("🔍 MVT Tile Analysis")
    print("=" * 60)
    
    # Test working coordinates
    results = test_working_coordinates()
    
    # Test Defense specifically
    defense_result = test_defense_specifically()
    
    # Generate frontend config
    if results:
        generate_frontend_config(results)
    
    print(f"\n🎯 SOLUTION FOR YOUR MAP:")
    print("=" * 50)
    
    if results:
        print("1. In your map.html, use these source-layer names:")
        for layer_slug, data in results.items():
            if data['mvt_layers']:
                print(f"   '{layer_slug}' layer → source-layer: '{data['mvt_layers'][0]}'")
        
        print(f"\n2. Make sure map is positioned at coordinates where data exists:")
        print(f"   Center: [77.6, 13.0]")
        print(f"   Zoom: 10-11")
        
        print(f"\n3. Test with these specific tile coordinates that have data:")
        for layer_slug, data in results.items():
            print(f"   {layer_slug}: {data['tile_coords']}")
            
        print(f"\n4. If Defense layer has no data, try a different layer first:")
        if 'residential_main' in results:
            print(f"   Residential Main has {results['residential_main']['features']} features - try this first!")
    
    else:
        print("❌ No working tiles found. Check if Django server is running.")

if __name__ == '__main__':
    main()