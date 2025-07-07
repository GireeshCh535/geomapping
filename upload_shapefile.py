#!/usr/bin/env python
"""
Shapefile Upload Helper
This script helps upload shapefiles to the geomapping system.
"""

import os
import sys
import subprocess
from pathlib import Path

def upload_shapefile(shp_path, city_slug, category_code):
    """
    Upload a shapefile to the geomapping system
    
    Args:
        shp_path: Path to the .shp file
        city_slug: City slug (bangalore, vizag, amaravati)
        category_code: Category code (RESIDENTIAL, COMMERCIAL, etc.)
    """
    
    if not os.path.exists(shp_path):
        print(f"❌ Shapefile not found: {shp_path}")
        return False
    
    # Get the directory containing the shapefile
    shp_dir = Path(shp_path).parent
    shp_name = Path(shp_path).name
    
    print(f"🔍 Uploading shapefile: {shp_path}")
    print(f"🏙️  City: {city_slug}")
    print(f"📂 Category: {category_code}")
    
    try:
        # Step 1: Copy shapefile to Docker container
        print("\n📋 Step 1: Copying shapefile to Docker container...")
        result = subprocess.run([
            'docker', 'cp', str(shp_dir), 'geomapping-web-1:/app/shapefile_data'
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Error copying shapefile: {result.stderr}")
            return False
        
        print("✅ Shapefile copied to container")
        
        # Step 2: Convert to GeoJSON inside container
        print("\n📋 Step 2: Converting to GeoJSON...")
        convert_cmd = f"""
        cd /app/shapefile_data && \
        ogr2ogr -f GeoJSON {shp_name.replace('.shp', '.geojson')} {shp_name}
        """
        
        result = subprocess.run([
            'docker-compose', 'exec', '-T', 'web', 'bash', '-c', convert_cmd
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Error converting shapefile: {result.stderr}")
            return False
        
        print("✅ Shapefile converted to GeoJSON")
        
        # Step 3: Import the GeoJSON file
        print("\n📋 Step 3: Importing GeoJSON file...")
        
        # Create import script
        import_script = f"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from maps.services import DataImportService
from maps.models import City, LayerCategory

def import_shapefile():
    try:
        # Get city and category
        city = City.objects.get(slug='{city_slug}')
        category = LayerCategory.objects.get(code='{category_code}')
        
        # Read the converted GeoJSON file
        geojson_path = '/app/shapefile_data/{shp_name.replace('.shp', '.geojson')}'
        with open(geojson_path, 'rb') as f:
            content = f.read()
        
        # Create file upload object
        file_obj = SimpleUploadedFile(
            '{shp_name.replace('.shp', '.geojson')}',
            content,
            content_type='application/geo+json'
        )
        
        # Import the data
        import_service = DataImportService()
        result = import_service.import_file(file_obj, city, category)
        
        print(f"✅ Shapefile imported successfully!")
        print(f"   Result: {{result}}")
        
        # Show final counts
        from maps.models import DataLayer, GeoFeature
        layer_count = DataLayer.objects.filter(city=city).count()
        feature_count = GeoFeature.objects.filter(layer__city=city).count()
        print(f"   {city.name}: {{layer_count}} layers, {{feature_count}} features")
        
    except Exception as e:
        print(f"❌ Error importing shapefile: {{e}}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    import_shapefile()
"""
        
        # Write import script to container
        with open('temp_import_script.py', 'w') as f:
            f.write(import_script)
        
        subprocess.run([
            'docker', 'cp', 'temp_import_script.py', 'geomapping-web-1:/app/temp_import_script.py'
        ])
        
        # Run import script
        result = subprocess.run([
            'docker-compose', 'exec', '-T', 'web', 'python', 'temp_import_script.py'
        ], capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print(f"⚠️  Warnings: {result.stderr}")
        
        # Cleanup
        os.remove('temp_import_script.py')
        
        print(f"\n🎉 Shapefile upload completed!")
        print(f"💡 You can now view the data at: http://localhost/")
        
        return True
        
    except Exception as e:
        print(f"❌ Error uploading shapefile: {e}")
        return False

def main():
    """Main function for command line usage"""
    if len(sys.argv) < 4:
        print("Usage: python upload_shapefile.py <shapefile_path> <city_slug> <category_code>")
        print("Example: python upload_shapefile.py data.shp bangalore RESIDENTIAL")
        print("\nAvailable cities: bangalore, vizag, amaravati")
        print("Available categories: RESIDENTIAL, COMMERCIAL, INDUSTRIAL, AGRICULTURAL, etc.")
        return
    
    shp_path = sys.argv[1]
    city_slug = sys.argv[2]
    category_code = sys.argv[3]
    
    upload_shapefile(shp_path, city_slug, category_code)

if __name__ == "__main__":
    main() 