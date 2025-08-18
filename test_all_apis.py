#!/usr/bin/env python3
"""
Comprehensive API Testing Script for GeoMapping Application
Tests all API endpoints to ensure they are working correctly
"""

import requests
import json
import sys
from datetime import datetime

# Base URL for the API
BASE_URL = "http://localhost:8000/api"

# Test data
TEST_COORDINATES = {
    'bengaluru': {'lat': 12.9716, 'lng': 77.5946},
    'visakhapatnam': {'lat': 17.6868, 'lng': 83.2185},
    'amaravati': {'lat': 16.5062, 'lng': 80.6480}
}

def log_test(test_name, status, response=None, error=None):
    """Log test results"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if status == "PASS":
        print(f"✅ [{timestamp}] {test_name}: PASS")
    elif status == "FAIL":
        print(f"❌ [{timestamp}] {test_name}: FAIL")
        if error:
            print(f"   Error: {error}")
        if response:
            print(f"   Status Code: {response.status_code}")
            try:
                print(f"   Response: {response.text[:200]}...")
            except:
                print(f"   Response: {response.text}")
    elif status == "WARN":
        print(f"⚠️  [{timestamp}] {test_name}: WARN - {error}")

def test_endpoint(url, method="GET", data=None, expected_status=200, test_name=None):
    """Test a single endpoint"""
    if test_name is None:
        test_name = f"{method} {url}"
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            return False, f"Unsupported method: {method}"
        
        if response.status_code == expected_status:
            return True, None
        else:
            return False, f"Expected status {expected_status}, got {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return False, "Connection refused - server may not be running"
    except requests.exceptions.Timeout:
        return False, "Request timeout"
    except Exception as e:
        return False, str(e)

def test_router_endpoints():
    """Test all router-based endpoints (ViewSets)"""
    print("\n🔍 Testing Router Endpoints (ViewSets)...")
    
    router_endpoints = [
        "/states/",
        "/cities/",
        "/categories/",
        "/layer-groups/",
        "/layers/",
        "/features/",
    ]
    
    for endpoint in router_endpoints:
        url = f"{BASE_URL}{endpoint}"
        success, error = test_endpoint(url, test_name=f"Router: {endpoint}")
        if success:
            log_test(f"Router: {endpoint}", "PASS")
        else:
            log_test(f"Router: {endpoint}", "FAIL", error=error)

def test_hierarchy_api():
    """Test the complete hierarchy API"""
    print("\n🔍 Testing Hierarchy API...")
    
    url = f"{BASE_URL}/hierarchy/"
    success, error = test_endpoint(url, test_name="Complete Hierarchy API")
    
    if success:
        log_test("Complete Hierarchy API", "PASS")
        
        # Test if response contains expected structure
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if 'hierarchy' in data:
                log_test("Hierarchy Structure", "PASS")
            else:
                log_test("Hierarchy Structure", "WARN", error="Response missing 'hierarchy' key")
                
        except Exception as e:
            log_test("Hierarchy Structure", "WARN", error=f"Could not parse response: {e}")
    else:
        log_test("Complete Hierarchy API", "FAIL", error=error)

def test_tile_endpoints():
    """Test tile-related endpoints"""
    print("\n🔍 Testing Tile Endpoints...")
    
    # Test tile coordinates endpoint
    for city, coords in TEST_COORDINATES.items():
        url = f"{BASE_URL}/cities/{city}/tiles/coordinates/?lat={coords['lat']}&lng={coords['lng']}&zoom=12"
        success, error = test_endpoint(url, test_name=f"Tile Coordinates: {city}")
        if success:
            log_test(f"Tile Coordinates: {city}", "PASS")
        else:
            log_test(f"Tile Coordinates: {city}", "FAIL", error=error)
    
    # Test available tiles endpoint
    for city in TEST_COORDINATES.keys():
        url = f"{BASE_URL}/cities/{city}/tiles/available/?zoom=12"
        success, error = test_endpoint(url, test_name=f"Available Tiles: {city}")
        if success:
            log_test(f"Available Tiles: {city}", "PASS")
        else:
            log_test(f"Available Tiles: {city}", "FAIL", error=error)

def test_coordinate_search():
    """Test coordinate search endpoints"""
    print("\n🔍 Testing Coordinate Search Endpoints...")
    
    for city, coords in TEST_COORDINATES.items():
        url = f"{BASE_URL}/cities/{city}/search-coords-test/?lat={coords['lat']}&lng={coords['lng']}"
        success, error = test_endpoint(url, test_name=f"Coordinate Search: {city}")
        if success:
            log_test(f"Coordinate Search: {city}", "PASS")
        else:
            log_test(f"Coordinate Search: {city}", "FAIL", error=error)

def test_combined_layer_center():
    """Test combined layer center endpoint"""
    print("\n🔍 Testing Combined Layer Center Endpoints...")
    
    # Test with different state/city combinations
    test_cases = [
        ("karnataka", "bengaluru"),
        ("andhra-pradesh", "visakhapatnam"),
        ("andhra-pradesh", "amaravati"),
    ]
    
    for state, city in test_cases:
        url = f"{BASE_URL}/center/{state}/{city}/"
        success, error = test_endpoint(url, test_name=f"Combined Layer Center: {state}/{city}")
        if success:
            log_test(f"Combined Layer Center: {state}/{city}", "PASS")
        else:
            log_test(f"Combined Layer Center: {state}/{city}", "FAIL", error=error)

def test_cloudfront_tiles():
    """Test CloudFront tile endpoints"""
    print("\n🔍 Testing CloudFront Tile Endpoints...")
    
    # Test some sample tile URLs
    test_tiles = [
        ("karnataka", "bengaluru", "master_plan_2015", 12, 2048, 2048, "png"),
        ("karnataka", "bengaluru", "master_plan_2015", 12, 2048, 2048, "mvt"),
        ("andhra-pradesh", "visakhapatnam", "master_plan", 12, 2048, 2048, "png"),
    ]
    
    for state, city, layer, z, x, y, format_type in test_tiles:
        url = f"{BASE_URL}/tiles/{state}/{city}/{layer}/{z}/{x}/{y}.{format_type}"
        # These might return 302 redirects or 404s, both are acceptable
        success, error = test_endpoint(url, expected_status=[200, 302, 404], 
                                     test_name=f"CloudFront Tile: {state}/{city}/{layer}")
        if success:
            log_test(f"CloudFront Tile: {state}/{city}/{layer}", "PASS")
        else:
            log_test(f"CloudFront Tile: {state}/{city}/{layer}", "WARN", 
                    error=f"Expected 200/302/404, got error: {error}")

def test_api_documentation():
    """Test API documentation endpoints"""
    print("\n🔍 Testing API Documentation Endpoints...")
    
    doc_endpoints = [
        "/api/schema/",
        "/api/docs/",
        "/api/redoc/",
    ]
    
    for endpoint in doc_endpoints:
        url = f"http://localhost:8000{endpoint}"
        success, error = test_endpoint(url, test_name=f"API Docs: {endpoint}")
        if success:
            log_test(f"API Docs: {endpoint}", "PASS")
        else:
            log_test(f"API Docs: {endpoint}", "FAIL", error=error)

def test_error_handling():
    """Test error handling for invalid requests"""
    print("\n🔍 Testing Error Handling...")
    
    # Test invalid city
    url = f"{BASE_URL}/cities/invalid-city/tiles/coordinates/?lat=12.9716&lng=77.5946&zoom=12"
    success, error = test_endpoint(url, expected_status=404, test_name="Invalid City (404)")
    if success:
        log_test("Invalid City (404)", "PASS")
    else:
        log_test("Invalid City (404)", "FAIL", error=error)
    
    # Test missing parameters
    url = f"{BASE_URL}/cities/bengaluru/tiles/coordinates/"
    success, error = test_endpoint(url, expected_status=400, test_name="Missing Parameters (400)")
    if success:
        log_test("Missing Parameters (400)", "PASS")
    else:
        log_test("Missing Parameters (400)", "FAIL", error=error)
    
    # Test invalid coordinates
    url = f"{BASE_URL}/cities/bengaluru/tiles/coordinates/?lat=999&lng=999&zoom=12"
    success, error = test_endpoint(url, expected_status=400, test_name="Invalid Coordinates (400)")
    if success:
        log_test("Invalid Coordinates (400)", "PASS")
    else:
        log_test("Invalid Coordinates (400)", "FAIL", error=error)

def main():
    """Main test function"""
    print("🚀 Starting Comprehensive API Testing")
    print("=" * 50)
    
    # Test if server is reachable
    try:
        response = requests.get(f"{BASE_URL}/states/", timeout=5)
        print(f"✅ Server is reachable at {BASE_URL}")
    except Exception as e:
        print(f"❌ Server is not reachable at {BASE_URL}")
        print(f"   Error: {e}")
        print("   Make sure the Django server is running on port 8000")
        sys.exit(1)
    
    # Run all tests
    test_router_endpoints()
    test_hierarchy_api()
    test_tile_endpoints()
    test_coordinate_search()
    test_combined_layer_center()
    test_cloudfront_tiles()
    test_api_documentation()
    test_error_handling()
    
    print("\n" + "=" * 50)
    print("🎉 API Testing Complete!")
    print("Check the results above for any issues.")

if __name__ == "__main__":
    main()
