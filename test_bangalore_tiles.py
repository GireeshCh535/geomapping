#!/usr/bin/env python3
"""
Test Bangalore Tile Coordinates
Tests valid tile coordinates for Bangalore area
"""

import requests
import sys

def test_tile_url(base_url, city_slug, layer_slug, z, x, y):
    """Test a specific tile URL and return response info."""
    url = f"{base_url}/api/tiles/{city_slug}/{layer_slug}/{z}/{x}/{y}.mvt"
    
    try:
        response = requests.get(url, timeout=10)
        return {
            'url': url,
            'status_code': response.status_code,
            'content_length': len(response.content),
            'content_type': response.headers.get('content-type', ''),
            'success': response.status_code == 200
        }
    except Exception as e:
        return {
            'url': url,
            'error': str(e),
            'success': False
        }

def test_bangalore_tiles():
    """Test various Bangalore tile coordinates."""
    
    # Base URL - adjust if your server is running on different port
    base_url = "http://localhost:8000"
    city_slug = "bangalore"
    
    # Valid Bangalore tile coordinates from your coordinates.js
    test_tiles = [
        # Residential Main (largest layer)
        ("residential_main_", 12, 3119, 3222),
        ("residential_main_", 12, 3113, 3217),
        ("residential_main_", 12, 3125, 3228),
        
        # State Forest Protected
        ("stateforest_valley_protectedland_", 12, 3116, 3224),
        ("stateforest_valley_protectedland_", 12, 3113, 3216),
        ("stateforest_valley_protectedland_", 12, 3124, 3232),
        
        # Commercial Central
        ("commercial_central_", 12, 3117, 3221),
        ("commercial_central_", 12, 3115, 3220),
        ("commercial_central_", 12, 3119, 3222),
        
        # Agricultural Land
        ("agricultural_land", 12, 3118, 3223),
        ("agricultural_land", 12, 3111, 3216),
        ("agricultural_land", 12, 3127, 3233),
        
        # High Tech
        ("hightech", 12, 3118, 3224),
        
        # Combined tiles
        ("combined", 12, 3118, 3221),
        ("combined", 12, 3119, 3222),
    ]
    
    print("🧪 TESTING BANGALORE TILES")
    print("=" * 60)
    print(f"Base URL: {base_url}")
    print(f"City: {city_slug}")
    print()
    
    successful_tiles = []
    
    for layer_slug, z, x, y in test_tiles:
        result = test_tile_url(base_url, city_slug, layer_slug, z, x, y)
        
        if result['success']:
            status = "✅"
            successful_tiles.append((layer_slug, z, x, y, result['content_length']))
        else:
            status = "❌"
        
        print(f"{status} {layer_slug} {z}/{x}/{y}")
        print(f"   URL: {result['url']}")
        
        if result['success']:
            print(f"   Size: {result['content_length']:,} bytes")
            print(f"   Type: {result['content_type']}")
        else:
            print(f"   Error: {result.get('error', f'HTTP {result.get('status_code', 'Unknown')}')}")
        print()
    
    # Summary
    print("📊 SUMMARY")
    print("=" * 30)
    print(f"Total tiles tested: {len(test_tiles)}")
    print(f"Successful: {len(successful_tiles)}")
    print(f"Failed: {len(test_tiles) - len(successful_tiles)}")
    
    if successful_tiles:
        print("\n🎯 TILES WITH DATA (download these):")
        print("-" * 40)
        for layer_slug, z, x, y, size in successful_tiles:
            if size > 25:  # More than just empty tile
                print(f"✅ {layer_slug} {z}/{x}/{y} ({size:,} bytes)")
                print(f"   curl -o {layer_slug}_{z}_{x}_{y}.mvt \"{base_url}/api/tiles/{city_slug}/{layer_slug}/{z}/{x}/{y}.mvt\"")
    
    return successful_tiles

def generate_download_commands(successful_tiles):
    """Generate curl commands to download tiles with data."""
    base_url = "http://localhost:8000"
    city_slug = "bangalore"
    
    print("\n📥 DOWNLOAD COMMANDS")
    print("=" * 30)
    
    for layer_slug, z, x, y, size in successful_tiles:
        if size > 25:  # Only tiles with actual data
            filename = f"{layer_slug}_{z}_{x}_{y}.mvt"
            url = f"{base_url}/api/tiles/{city_slug}/{layer_slug}/{z}/{x}/{y}.mvt"
            print(f"curl -o {filename} \"{url}\"")

def main():
    print("🚀 Bangalore Tile Testing Tool")
    print("Make sure your Django server is running on localhost:8000")
    print()
    
    try:
        successful_tiles = test_bangalore_tiles()
        generate_download_commands(successful_tiles)
        
    except KeyboardInterrupt:
        print("\n⏹️  Testing interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Make sure your Django server is running and accessible")

if __name__ == "__main__":
    main() 