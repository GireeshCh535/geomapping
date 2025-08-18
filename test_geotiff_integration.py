#!/usr/bin/env python3
"""
Test script for GeoTIFF integration functionality
This script tests the GeoTIFF conversion and import capabilities
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path

def test_gdal_installation():
    """Test if GDAL is properly installed"""
    print("🔍 Testing GDAL installation...")
    
    try:
        result = subprocess.run(['gdalinfo', '--version'], 
                              capture_output=True, text=True, check=True)
        print(f"✅ GDAL version: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ GDAL test failed: {e}")
        return False
    except FileNotFoundError:
        print("❌ GDAL not found. Please install GDAL first.")
        return False

def test_geopandas_installation():
    """Test if geopandas is installed"""
    print("🔍 Testing geopandas installation...")
    
    try:
        import geopandas
        print(f"✅ geopandas version: {geopandas.__version__}")
        return True
    except ImportError:
        print("❌ geopandas not found. Please install: pip install geopandas")
        return False

def test_django_environment():
    """Test Django environment setup"""
    print("🔍 Testing Django environment...")
    
    try:
        import django
        from django.conf import settings
        
        # Setup Django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
        django.setup()
        
        # Test imports
        from maps.models import City, LayerCategory, DataLayer
        from maps.geotiff_service import GeoTIFFService
        
        print("✅ Django environment setup successful")
        print(f"✅ Django version: {django.get_version()}")
        
        # Test model access
        cities = City.objects.filter(is_active=True).count()
        categories = LayerCategory.objects.filter(is_active=True).count()
        
        print(f"✅ Found {cities} active cities")
        print(f"✅ Found {categories} layer categories")
        
        return True
        
    except Exception as e:
        print(f"❌ Django environment test failed: {e}")
        return False

def test_geotiff_service():
    """Test GeoTIFF service functionality"""
    print("🔍 Testing GeoTIFF service...")
    
    try:
        from maps.geotiff_service import GeoTIFFService
        
        service = GeoTIFFService()
        print("✅ GeoTIFF service initialized successfully")
        
        # Test service methods
        if hasattr(service, 'process_geotiff_file'):
            print("✅ process_geotiff_file method available")
        else:
            print("❌ process_geotiff_file method not found")
            return False
            
        if hasattr(service, '_convert_geotiff_to_geojson'):
            print("✅ _convert_geotiff_to_geojson method available")
        else:
            print("❌ _convert_geotiff_to_geojson method not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ GeoTIFF service test failed: {e}")
        return False

def test_management_commands():
    """Test if management commands are available"""
    print("🔍 Testing management commands...")
    
    try:
        # Test command help
        result = subprocess.run([
            'python', 'manage.py', 'import_geotiff_layers', '--help'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ import_geotiff_layers command available")
        else:
            print("❌ import_geotiff_layers command not found")
            return False
        
        result = subprocess.run([
            'python', 'manage.py', 'convert_geotiff_to_geojson', '--help'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ convert_geotiff_to_geojson command available")
        else:
            print("❌ convert_geotiff_to_geojson command not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Management command test failed: {e}")
        return False

def create_test_geotiff():
    """Create a simple test GeoTIFF file"""
    print("🔍 Creating test GeoTIFF file...")
    
    try:
        # Create a simple test GeoTIFF using GDAL
        test_tif = Path("test_sample.tif")
        
        # Use gdal_create to create a simple test file
        cmd = [
            'gdal_create', '-outsize', '100', '100', '-a_srs', 'EPSG:4326',
            '-a_ullr', '77.5', '13.0', '77.6', '12.9', str(test_tif)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and test_tif.exists():
            print(f"✅ Test GeoTIFF created: {test_tif}")
            return test_tif
        else:
            print("❌ Failed to create test GeoTIFF")
            return None
            
    except Exception as e:
        print(f"❌ Test GeoTIFF creation failed: {e}")
        return None

def test_conversion_workflow():
    """Test the complete conversion workflow"""
    print("🔍 Testing conversion workflow...")
    
    # Create test file
    test_file = create_test_geotiff()
    if not test_file:
        print("❌ Cannot test workflow without test file")
        return False
    
    try:
        # Test dry run conversion
        cmd = [
            'python', 'manage.py', 'convert_geotiff_to_geojson',
            '--input', str(test_file),
            '--city', 'bengaluru',
            '--category', 'RESIDENTIAL',
            '--dry-run'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Conversion workflow test successful (dry run)")
        else:
            print(f"❌ Conversion workflow test failed: {result.stderr}")
            return False
        
        # Cleanup test file
        test_file.unlink()
        print("✅ Test file cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Conversion workflow test failed: {e}")
        if test_file and test_file.exists():
            test_file.unlink()
        return False

def main():
    """Run all tests"""
    print("=" * 70)
    print("🧪 GEOTIFF INTEGRATION TEST SUITE")
    print("=" * 70)
    
    tests = [
        ("GDAL Installation", test_gdal_installation),
        ("Geopandas Installation", test_geopandas_installation),
        ("Django Environment", test_django_environment),
        ("GeoTIFF Service", test_geotiff_service),
        ("Management Commands", test_management_commands),
        ("Conversion Workflow", test_conversion_workflow),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! GeoTIFF integration is ready to use.")
        print("\n💡 Next steps:")
        print("1. Place your GeoTIFF files in a directory")
        print("2. Run: python manage.py import_geotiff_layers --input /path/to/files --city bengaluru --category RESIDENTIAL --batch")
        print("3. Check the results in the admin interface")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        print("\n🔧 Troubleshooting:")
        print("1. Install GDAL: sudo apt-get install gdal-bin libgdal-dev python3-gdal")
        print("2. Install Python dependencies: pip install -r requirements.txt")
        print("3. Ensure Django is properly configured")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
