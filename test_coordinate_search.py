#!/usr/bin/env python3
"""
Test script for the Enhanced Coordinate Search API
==================================================

This script demonstrates how to use the coordinate search API to find data at specific locations.

Usage:
    python test_coordinate_search.py

Requirements:
    - requests library
    - Valid API endpoint
"""

import requests
import json
from typing import Dict, Any

class CoordinateSearchTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def test_coordinate_search(self, lat: float, lng: float, city_slug: str = None, radius: int = 100) -> Dict[str, Any]:
        """
        Test coordinate search API
        
        Args:
            lat: Latitude coordinate
            lng: Longitude coordinate
            city_slug: Optional city slug to limit search
            radius: Search radius in meters
            
        Returns:
            API response as dictionary
        """
        if city_slug:
            url = f"{self.base_url}/api/cities/{city_slug}/search-coords-test/"
        else:
            url = f"{self.base_url}/api/search-coords-test/"
        
        params = {
            'lat': lat,
            'lng': lng,
            'radius': radius
        }
        
        try:
            print(f"🔍 Searching coordinates: {lat}, {lng}")
            print(f"📍 URL: {url}")
            print(f"📊 Parameters: {params}")
            print("-" * 60)
            
            response = self.session.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                self._print_success_response(data)
            else:
                self._print_error_response(response)
                
            return response.json() if response.status_code == 200 else None
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            return None
    
    def _print_success_response(self, data: Dict[str, Any]):
        """Print successful API response in a formatted way"""
        print("✅ SUCCESS: Data found at coordinates!")
        print()
        
        # Search point info
        search_point = data.get('search_point', {})
        print(f"📍 Search Point:")
        print(f"   Latitude: {search_point.get('latitude')}")
        print(f"   Longitude: {search_point.get('longitude')}")
        print(f"   WKT: {search_point.get('wkt')}")
        print()
        
        # State and city info
        state = data.get('state', {})
        city = data.get('city', {})
        print(f"🏛️  Administrative Info:")
        print(f"   State: {state.get('name')} ({state.get('code')})")
        print(f"   City: {city.get('name')}")
        print(f"   City Center: {city.get('center_lat')}, {city.get('center_lng')}")
        print()
        
        # Features found
        features = data.get('features', [])
        if features:
            print(f"🎯 Features at this location ({len(features)} found):")
            for i, feature in enumerate(features, 1):
                print(f"   {i}. {feature.get('feature_name')}")
                print(f"      Layer: {feature.get('layer_name')} ({feature.get('category_name')})")
                print(f"      Area: {feature.get('area', {}).get('acres', 'N/A')} acres")
                print(f"      Color: {feature.get('color')}")
                print()
        
        # Nearby features
        nearby_features = data.get('nearby_features', [])
        if nearby_features:
            print(f"🔍 Nearby features ({len(nearby_features)} found):")
            for i, feature in enumerate(nearby_features[:5], 1):  # Show first 5
                distance = feature.get('distance_meters', 'N/A')
                print(f"   {i}. {feature.get('feature_name')} ({distance}m away)")
                print(f"      Layer: {feature.get('layer_name')} ({feature.get('category_name')})")
                print()
        
        # Summary
        print(f"📝 Summary: {data.get('summary', 'N/A')}")
        print()
        
        # Metadata
        metadata = data.get('metadata', {})
        if metadata:
            print(f"📊 Metadata:")
            print(f"   API Version: {metadata.get('api_version')}")
            print(f"   Search Radius: {metadata.get('search_radius_meters')}m")
            print(f"   Total Features: {metadata.get('total_features_found')}")
            print(f"   Total Nearby: {metadata.get('total_nearby_features')}")
            print(f"   Timestamp: {metadata.get('search_timestamp')}")
    
    def _print_error_response(self, response):
        """Print error response in a formatted way"""
        print(f"❌ ERROR: {response.status_code}")
        print()
        
        try:
            error_data = response.json()
            print(f"Error: {error_data.get('error', 'Unknown error')}")
            print(f"Message: {error_data.get('message', 'No message provided')}")
            
            if 'example' in error_data:
                print(f"Example: {error_data['example']}")
            
            if 'parameters' in error_data:
                print("Required Parameters:")
                for param, desc in error_data['parameters'].items():
                    print(f"   {param}: {desc}")
                    
        except json.JSONDecodeError:
            print(f"Response text: {response.text}")
    
    def run_demo_tests(self):
        """Run a series of demo tests with different coordinates"""
        print("🚀 COORDINATE SEARCH API DEMO")
        print("=" * 60)
        print()
        
        # Test 1: Bengaluru city center
        print("🧪 TEST 1: Bengaluru City Center")
        print("=" * 40)
        self.test_coordinate_search(
            lat=12.9716, 
            lng=77.5946, 
            city_slug="bengaluru",
            radius=200
        )
        print("\n" + "=" * 80 + "\n")
        
        # Test 2: Hyderabad city center
        print("🧪 TEST 2: Hyderabad City Center")
        print("=" * 40)
        self.test_coordinate_search(
            lat=17.3850, 
            lng=78.4867, 
            city_slug="hyderabad",
            radius=300
        )
        print("\n" + "=" * 80 + "\n")
        
        # Test 3: Global search (no city specified)
        print("🧪 TEST 3: Global Search (Bengaluru coordinates)")
        print("=" * 40)
        self.test_coordinate_search(
            lat=12.9716, 
            lng=77.5946, 
            radius=500
        )
        print("\n" + "=" * 80 + "\n")
        
        # Test 4: Invalid coordinates
        print("🧪 TEST 4: Invalid Coordinates")
        print("=" * 40)
        self.test_coordinate_search(
            lat=200.0,  # Invalid latitude
            lng=77.5946,
            city_slug="bengaluru"
        )
        print("\n" + "=" * 80 + "\n")
        
        # Test 5: Missing parameters
        print("🧪 TEST 5: Missing Parameters")
        print("=" * 40)
        url = f"{self.base_url}/api/cities/bengaluru/search-coords-test/"
        try:
            response = self.session.get(url)  # No parameters
            self._print_error_response(response)
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
        
        print("\n" + "=" * 80 + "\n")
        print("🎉 Demo tests completed!")

def main():
    """Main function to run the coordinate search tests"""
    
    # Initialize tester
    tester = CoordinateSearchTester()
    
    # Run demo tests
    tester.run_demo_tests()
    
    print("\n📚 API USAGE EXAMPLES:")
    print("=" * 40)
    print("1. Search within Bengaluru:")
    print("   GET /api/cities/bengaluru/search-coords-test/?lat=12.9716&lng=77.5946&radius=200")
    print()
    print("2. Search within Hyderabad:")
    print("   GET /api/cities/hyderabad/search-coords-test/?lat=17.3850&lng=78.4867&radius=300")
    print()
    print("3. Global search (all cities):")
    print("   GET /api/search-coords-test/?lat=12.9716&lng=77.5946&radius=500")
    print()
    print("4. Small radius search:")
    print("   GET /api/cities/bengaluru/search-coords-test/?lat=12.9716&lng=77.5946&radius=50")
    print()
    print("5. Large radius search:")
    print("   GET /api/cities/hyderabad/search-coords-test/?lat=17.3850&lng=78.4867&radius=1000")

if __name__ == "__main__":
    main()
