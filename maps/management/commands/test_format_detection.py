# maps/management/commands/test_format_detection.py
"""
Test the format detection on your actual files
Command: python manage.py test_format_detection --file "data/karnataka/bengaluru/master_plan/Agricultural_Land.json"
"""

from django.core.management.base import BaseCommand
import json

class Command(BaseCommand):
    help = 'Test format detection on actual files'
    
    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Path to test file')
    
    def handle(self, *args, **options):
        file_path = options['file']
        
        try:
            # Load the file
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.stdout.write(f"🔍 Testing format detection for: {file_path}")
            
            # Check key characteristics
            self.stdout.write(f"\n📊 File characteristics:")
            self.stdout.write(f"   Top-level keys: {list(data.keys())[:10]}...")  # Show first 10 keys
            
            # Check for ESRI indicators
            esri_indicators = ['displayFieldName', 'fieldAliases', 'geometryType', 'spatialReference']
            found_esri = [key for key in esri_indicators if key in data]
            if found_esri:
                self.stdout.write(f"   ✅ ESRI indicators found: {found_esri}")
            
            # Check features
            if 'features' in data and data['features']:
                first_feature = data['features'][0]
                self.stdout.write(f"   Feature keys: {list(first_feature.keys())}")
                
                if 'attributes' in first_feature:
                    self.stdout.write(f"   ✅ Has 'attributes' (ESRI style)")
                    attr_keys = list(first_feature['attributes'].keys())[:10]
                    self.stdout.write(f"   Attribute keys: {attr_keys}...")
                    
                if 'properties' in first_feature:
                    self.stdout.write(f"   ✅ Has 'properties' (GeoJSON style)")
                
                if 'geometry' in first_feature:
                    geometry = first_feature['geometry']
                    self.stdout.write(f"   Geometry keys: {list(geometry.keys())}")
                    
                    if 'rings' in geometry:
                        self.stdout.write(f"   ✅ Has 'rings' (ESRI polygon)")
                    if 'paths' in geometry:
                        self.stdout.write(f"   ✅ Has 'paths' (ESRI line)")
                    if 'type' in geometry and 'coordinates' in geometry:
                        self.stdout.write(f"   ✅ Has 'type'+'coordinates' (GeoJSON)")
            
            # Test our detection function
            from maps.config import detect_data_format
            detected_format = detect_data_format(data)
            
            self.stdout.write(f"\n🎯 DETECTED FORMAT: {detected_format}")
            
            if detected_format == 'ESRI_JSON':
                self.stdout.write(f"✅ Correctly detected as ESRI JSON!")
            elif detected_format == 'GEOJSON':
                self.stdout.write(f"❌ Incorrectly detected as GeoJSON - this should be ESRI JSON")
            else:
                self.stdout.write(f"❓ Unknown format detected")
                
        except Exception as e:
            self.stdout.write(f"❌ Error: {e}")
            import traceback
            self.stdout.write(traceback.format_exc())