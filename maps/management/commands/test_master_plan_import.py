# maps/management/commands/test_master_plan_import.py
"""
Test importing a single master plan file to debug the 0 features issue
Command: python manage.py test_master_plan_import --file "data/karnataka/bengaluru/master_plan/Agricultural_Land.json"
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from maps.models import City, DataLayer, LayerCategory, LayerGroup, GeoFeature
from maps.config import detect_data_format, convert_esri_to_geojson_geometry, optimize_coordinates
from django.contrib.gis.geos import GEOSGeometry
import json
import os

class Command(BaseCommand):
    help = 'Test importing a single master plan file with detailed debugging'
    
    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Path to master plan JSON file')
        parser.add_argument('--limit', type=int, default=10, help='Limit features to import (for testing)')
        parser.add_argument('--force', action='store_true', help='Force re-import')
    
    def handle(self, *args, **options):
        file_path = options['file']
        limit = options['limit']
        
        self.stdout.write(self.style.SUCCESS(f"🧪 TESTING SINGLE FILE IMPORT: {file_path}"))
        
        try:
            # Load file
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Get city and layer group
            city = City.objects.get(slug='bengaluru')
            master_plan_group = LayerGroup.objects.get(city=city, slug='master_plan')
            
            # Create test layer
            layer_name = os.path.basename(file_path).replace('.json', '')
            
            # Remove existing test layer if force
            if options['force']:
                DataLayer.objects.filter(city=city, slug=layer_name).delete()
            
            # Get or create layer
            layer, created = DataLayer.objects.get_or_create(
                city=city,
                slug=layer_name,
                defaults={
                    'layer_group': master_plan_group,
                    'name': layer_name.replace('_', ' ').title(),
                    'category': LayerCategory.objects.get(code='AGRICULTURAL'),
                    'description': f'Test import of {layer_name}',
                    'file_format': 'ESRI_JSON',
                    'original_filename': os.path.basename(file_path),
                    'categorization_method': 'MANUAL',
                    'is_processed': False
                }
            )
            
            self.stdout.write(f"📋 Layer: {layer.name} ({'created' if created else 'existing'})")
            
            # Test format detection
            detected_format = detect_data_format(data)
            self.stdout.write(f"🎯 Detected format: {detected_format}")
            
            # Get features
            features = data.get('features', [])
            self.stdout.write(f"📊 Total features in file: {len(features)}")
            
            if not features:
                self.stdout.write("❌ No features found in file")
                return
            
            # Test importing limited features
            imported = 0
            failed = 0
            
            for i, feature_data in enumerate(features[:limit]):
                self.stdout.write(f"\n🔍 Testing feature {i+1}/{min(limit, len(features))}:")
                
                try:
                    # Extract data
                    esri_geometry = feature_data.get('geometry', {})
                    attributes = feature_data.get('attributes', {})
                    
                    self.stdout.write(f"   📐 Geometry keys: {list(esri_geometry.keys())}")
                    self.stdout.write(f"   📋 Attribute keys: {list(attributes.keys())[:5]}...")
                    
                    # Test geometry conversion
                    geojson_geom = convert_esri_to_geojson_geometry(esri_geometry)
                    if not geojson_geom:
                        self.stdout.write(f"   ❌ Geometry conversion failed")
                        failed += 1
                        continue
                    
                    self.stdout.write(f"   ✅ Converted to: {geojson_geom['type']}")
                    
                    # Test Django geometry creation
                    try:
                        geometry = GEOSGeometry(json.dumps(geojson_geom))
                        self.stdout.write(f"   ✅ Django geometry created")
                    except Exception as geom_error:
                        self.stdout.write(f"   ❌ Django geometry failed: {geom_error}")
                        failed += 1
                        continue
                    
                    # Test attribute processing
                    try:
                        processed_attrs = self._process_bangalore_attributes(attributes, layer)
                        self.stdout.write(f"   ✅ Attributes processed: {list(processed_attrs.keys())[:3]}...")
                    except Exception as attr_error:
                        self.stdout.write(f"   ❌ Attribute processing failed: {attr_error}")
                        failed += 1
                        continue
                    
                    # Test database creation
                    try:
                        geo_feature = GeoFeature.objects.create(
                            layer=layer,
                            geometry=geometry,
                            **processed_attrs
                        )
                        self.stdout.write(f"   ✅ GeoFeature created: ID {geo_feature.id}")
                        imported += 1
                    except Exception as db_error:
                        self.stdout.write(f"   ❌ Database creation failed: {db_error}")
                        failed += 1
                        continue
                        
                except Exception as e:
                    self.stdout.write(f"   ❌ Feature processing failed: {e}")
                    failed += 1
                    continue
            
            self.stdout.write(f"\n📊 TEST RESULTS:")
            self.stdout.write(f"   Features tested: {min(limit, len(features))}")
            self.stdout.write(f"   Successfully imported: {imported}")
            self.stdout.write(f"   Failed: {failed}")
            
            if imported > 0:
                self.stdout.write(f"✅ SUCCESS! The import logic is working.")
                self.stdout.write(f"🚀 You can now run the full import:")
                self.stdout.write(f"   docker-compose exec web python manage.py import_city_layers --city bengaluru --data-dir \"data/karnataka/bengaluru\" --layer-groups \"master_plan\" --force")
            else:
                self.stdout.write(f"❌ All features failed - check the error details above")
                
        except Exception as e:
            self.stdout.write(f"❌ Test failed: {e}")
            import traceback
            self.stdout.write(traceback.format_exc())
    
    def _process_bangalore_attributes(self, esri_attrs, layer):
        """Simplified attribute processing for testing"""
        
        def safe_get(d, key, default=''):
            value = d.get(key, default)
            return str(value).strip() if value is not None else str(default)
        
        # Extract basic info
        plu_cd = safe_get(esri_attrs, 'PLU_Cd', '')
        plu_tp_pro = safe_get(esri_attrs, 'PLU_Tp_pro', '')
        plu_prop_l = safe_get(esri_attrs, 'PLU_prop_l', '')
        
        # Create simple name
        name = plu_tp_pro or plu_prop_l or f"Feature {plu_cd}" or "Unnamed Feature"
        
        return {
            'name': name[:200],
            'description': plu_prop_l[:500] if plu_prop_l else '',
            'source_layer_name': layer.name,
            'plu_primary_code': plu_cd,
            'derived_category': layer.category.code,
            'land_use_type': layer.category.code,
            'source_attributes': esri_attrs,
        } 