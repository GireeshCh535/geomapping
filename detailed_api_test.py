#!/usr/bin/env python3
"""
Detailed API Testing Script for GeoMapping Application
Tests API endpoints and analyzes response content
"""

import requests
import json
from datetime import datetime

# Base URL for the API
BASE_URL = "http://localhost:8000/api"

def test_endpoint_with_details(url, test_name):
    """Test endpoint and show detailed response"""
    print(f"\n🔍 Testing: {test_name}")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"✅ {test_name}: PASS")
                
                # Show response structure
                if isinstance(data, dict):
                    print(f"Response Keys: {list(data.keys())}")
                    if 'count' in data:
                        print(f"Total Count: {data['count']}")
                    if 'results' in data:
                        print(f"Results Count: {len(data['results'])}")
                        if data['results']:
                            print(f"Sample Item Keys: {list(data['results'][0].keys())}")
                elif isinstance(data, list):
                    print(f"Response Length: {len(data)}")
                    if data:
                        print(f"Sample Item Keys: {list(data[0].keys())}")
                
                return True, data
            except json.JSONDecodeError:
                print(f"❌ {test_name}: FAIL - Invalid JSON")
                return False, None
        else:
            print(f"❌ {test_name}: FAIL - Status {response.status_code}")
            return False, None
            
    except Exception as e:
        print(f"❌ {test_name}: FAIL - {str(e)}")
        return False, None

def test_hierarchy_api():
    """Test hierarchy API with detailed analysis"""
    print("\n" + "="*60)
    print("🏗️  TESTING HIERARCHY API")
    print("="*60)
    
    url = f"{BASE_URL}/hierarchy/"
    success, data = test_endpoint_with_details(url, "Complete Hierarchy API")
    
    if success and data:
        hierarchy = data.get('hierarchy', [])
        print(f"\n📊 Hierarchy Analysis:")
        print(f"Total States: {len(hierarchy)}")
        
        for state in hierarchy:
            state_info = state.get('state', {})
            cities = state.get('cities', [])
            stats = state.get('statistics', {})
            
            print(f"\n🏛️  State: {state_info.get('name', 'Unknown')} ({state_info.get('slug', 'unknown')})")
            print(f"   Cities: {len(cities)}")
            print(f"   Total Layers: {stats.get('total_layers', 0)}")
            print(f"   Total Features: {stats.get('total_features', 0)}")
            
            for city in cities:
                city_stats = city.get('statistics', {})
                layers = city.get('layers', [])
                live_layers = [l for l in layers if l.get('is_live', False)]
                
                print(f"   🏙️  City: {city.get('name', 'Unknown')} ({city.get('slug', 'unknown')})")
                print(f"      Status: {city.get('status', 'unknown')}")
                print(f"      Total Layers: {city_stats.get('total_layers', 0)}")
                print(f"      Processed Layers: {city_stats.get('processed_layers', 0)}")
                print(f"      Live Layers: {len(live_layers)}")
                print(f"      Total Features: {city_stats.get('total_features', 0)}")

def test_states_api():
    """Test states API"""
    print("\n" + "="*60)
    print("🏛️  TESTING STATES API")
    print("="*60)
    
    url = f"{BASE_URL}/states/"
    success, data = test_endpoint_with_details(url, "States API")
    
    if success and data:
        states = data.get('results', [])
        print(f"\n📊 States Analysis:")
        print(f"Total States: {len(states)}")
        
        for state in states:
            print(f"   🏛️  {state.get('name', 'Unknown')} ({state.get('slug', 'unknown')}) - Active: {state.get('is_active', False)}")

def test_cities_api():
    """Test cities API"""
    print("\n" + "="*60)
    print("🏙️  TESTING CITIES API")
    print("="*60)
    
    url = f"{BASE_URL}/cities/"
    success, data = test_endpoint_with_details(url, "Cities API")
    
    if success and data:
        cities = data.get('results', [])
        print(f"\n📊 Cities Analysis:")
        print(f"Total Cities: {len(cities)}")
        
        for city in cities:
            print(f"   🏙️  {city.get('name', 'Unknown')} ({city.get('slug', 'unknown')}) - State: {city.get('state_name', 'Unknown')}")

def test_layers_api():
    """Test layers API"""
    print("\n" + "="*60)
    print("🗺️  TESTING LAYERS API")
    print("="*60)
    
    url = f"{BASE_URL}/layers/"
    success, data = test_endpoint_with_details(url, "Layers API")
    
    if success and data:
        layers = data.get('results', [])
        print(f"\n📊 Layers Analysis:")
        print(f"Total Layers: {len(layers)}")
        
        # Group by city
        city_layers = {}
        for layer in layers:
            city = layer.get('city_name', 'Unknown')
            if city not in city_layers:
                city_layers[city] = []
            city_layers[city].append(layer)
        
        for city, city_layer_list in city_layers.items():
            print(f"\n   🏙️  {city}: {len(city_layer_list)} layers")
            processed = [l for l in city_layer_list if l.get('is_processed', False)]
            with_tiles = [l for l in city_layer_list if l.get('has_tiles', False)]
            print(f"      Processed: {len(processed)}")
            print(f"      With Tiles: {len(with_tiles)}")
            
            for layer in city_layer_list[:3]:  # Show first 3 layers
                print(f"      - {layer.get('name', 'Unknown')} ({layer.get('category_name', 'Unknown')})")

def test_features_api():
    """Test features API"""
    print("\n" + "="*60)
    print("📍 TESTING FEATURES API")
    print("="*60)
    
    url = f"{BASE_URL}/features/"
    success, data = test_endpoint_with_details(url, "Features API")
    
    if success and data:
        features = data.get('features', [])
        print(f"\n📊 Features Analysis:")
        print(f"Total Features: {len(features)}")
        
        if features:
            # Show sample feature
            sample = features[0]
            print(f"\n📋 Sample Feature:")
            print(f"   ID: {sample.get('id')}")
            print(f"   Layer: {sample.get('properties', {}).get('layer_name', 'Unknown')}")
            print(f"   City: {sample.get('properties', {}).get('city_name', 'Unknown')}")
            print(f"   Category: {sample.get('properties', {}).get('category_name', 'Unknown')}")

def test_coordinate_search():
    """Test coordinate search functionality"""
    print("\n" + "="*60)
    print("🔍 TESTING COORDINATE SEARCH")
    print("="*60)
    
    # Test Bengaluru coordinates
    lat, lng = 12.9716, 77.5946
    url = f"{BASE_URL}/cities/bengaluru/search-coords-test/?lat={lat}&lng={lng}"
    success, data = test_endpoint_with_details(url, "Coordinate Search (Bengaluru)")
    
    if success and data:
        print(f"\n📊 Search Results:")
        print(f"Found: {data.get('found', False)}")
        print(f"Containing Features: {len(data.get('containing_features', []))}")
        print(f"Nearby Features: {len(data.get('nearby_features', []))}")
        print(f"Summary: {data.get('summary', 'No summary')}")

def test_tile_coordinates():
    """Test tile coordinates functionality"""
    print("\n" + "="*60)
    print("🧩 TESTING TILE COORDINATES")
    print("="*60)
    
    lat, lng = 12.9716, 77.5946
    url = f"{BASE_URL}/cities/bengaluru/tiles/coordinates/?lat={lat}&lng={lng}&zoom=12"
    success, data = test_endpoint_with_details(url, "Tile Coordinates (Bengaluru)")
    
    if success and data:
        print(f"\n📊 Tile Analysis:")
        center_tile = data.get('center_tile', {})
        print(f"Center Tile: z={center_tile.get('z')}, x={center_tile.get('x')}, y={center_tile.get('y')}")
        print(f"Surrounding Tiles: {len(data.get('surrounding_tiles', []))}")

def main():
    """Main test function"""
    print("🚀 Starting Detailed API Testing")
    print("="*60)
    
    # Test all major endpoints
    test_hierarchy_api()
    test_states_api()
    test_cities_api()
    test_layers_api()
    test_features_api()
    test_coordinate_search()
    test_tile_coordinates()
    
    print("\n" + "="*60)
    print("🎉 Detailed API Testing Complete!")
    print("="*60)

if __name__ == "__main__":
    main()
