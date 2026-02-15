#!/usr/bin/env python3
"""
Django management command to insert Chennai Master Plan data
Creates ONE layer with all files under it (following Amaravati pattern)
"""

import os
import sys
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import GEOSGeometry
from django.db import transaction
from django.utils import timezone
import json

# Add the project root to the Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent.parent
sys.path.insert(0, str(project_root))

from maps.models import State, City, DataLayer, GeoFeature, LayerCategory, CityLayerStyle


class Command(BaseCommand):
    help = 'Insert Chennai Master Plan data - Creates ONE layer with all files'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Force regeneration')
        parser.add_argument('--delete-existing', action='store_true', help='Delete existing data first')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting Chennai Master Plan Data Insertion'))
        
        # Data directory
        self.data_dir = Path(project_root) / "data" / "tamil_nadu" / "chennai" / "chennai_master_plan"
        
        if not self.data_dir.exists():
            raise CommandError(f'Data directory not found: {self.data_dir}')
        
        try:
            # Setup entities
            self.setup_state_and_city()
            self.setup_layer_category()
            
            # Delete if requested
            if options['delete_existing']:
                self.delete_existing_data()
            
            # Create layer and styles
            self.create_city_layer_style()
            self.create_master_plan_layer()
            
            # Process files
            self.process_all_files(options['force'])
            
            # Finalize
            self.calculate_layer_bounds()
            self.print_summary()
            
            self.stdout.write(self.style.SUCCESS('\n✅ CHENNAI DATA INSERTION COMPLETED!'))
            
        except Exception as e:
            raise CommandError(f'Error: {e}')

    def setup_state_and_city(self):
        """Create or get State and City"""
        self.stdout.write("\n🏛️ Setting up State and City...")
        
        # Tamil Nadu State
        self.state, created = State.objects.get_or_create(
            code='TN',
            defaults={
                'name': 'Tamil Nadu',
                'slug': 'tamil-nadu',
                'center_lat': 11.1271,
                'center_lng': 78.6569,
                'default_zoom': 7,
                'is_active': True
            }
        )
        action = "Created" if created else "Found"
        self.stdout.write(f"  ✅ {action} state: {self.state.name}")
        
        # Chennai City
        self.city, created = City.objects.get_or_create(
            slug='chennai',
            defaults={
                'name': 'Chennai',
                'state': 'Tamil Nadu',
                'state_ref': self.state,
                'center_lat': 13.0827,
                'center_lng': 80.2707,
                'min_zoom': 8,
                'max_zoom': 18,
                'is_active': True
            }
        )
        
        # Ensure state_ref is set
        if not self.city.state_ref:
            self.city.state_ref = self.state
            self.city.save()
        
        action = "Created" if created else "Found"
        self.stdout.write(f"  ✅ {action} city: {self.city.name}")

    def setup_layer_category(self):
        """Create or get BOUNDARIES category"""
        self.stdout.write("\n📂 Setting up layer category...")
        
        self.category, created = LayerCategory.objects.get_or_create(
            code='BOUNDARIES',
            defaults={
                'name': 'Administrative Boundaries',
                'description': 'Administrative boundaries and jurisdictional areas',
                'default_color': '#FF6B6B',
                'default_stroke': '#D63031',
                'default_opacity': 0.3,
                'display_order': 1,
                'is_active': True
            }
        )
        action = "Created" if created else "Found"
        self.stdout.write(f"  ✅ {action} category: {self.category.name}")

    def delete_existing_data(self):
        """Delete existing Chennai data"""
        self.stdout.write("\n🗑️ Deleting existing Chennai data...")
        
        # Delete features
        count = GeoFeature.objects.filter(layer__city=self.city).delete()[0]
        self.stdout.write(f"  🗑️ Deleted {count} features")
        
        # Delete layers
        count = DataLayer.objects.filter(city=self.city).delete()[0]
        self.stdout.write(f"  🗑️ Deleted {count} layers")
        
        # Delete styles
        count = CityLayerStyle.objects.filter(city=self.city).delete()[0]
        self.stdout.write(f"  🗑️ Deleted {count} layer styles")

    def create_city_layer_style(self):
        """Create city-specific layer style"""
        self.stdout.write("\n🎨 Creating city layer style...")
        
        self.style_obj, created = CityLayerStyle.objects.get_or_create(
            city=self.city,
            category=self.category,
            defaults={
                'fill_color': '#FF6B6B',
                'stroke_color': '#D63031',
                'opacity': 0.3,
                'stroke_width': 2,
                'fill_pattern': 'SOLID',
                'is_visible': True,
                'min_zoom': 8,
                'max_zoom': 18
            }
        )
        action = "Created" if created else "Found"
        self.stdout.write(f"  ✅ {action} style for Chennai boundaries")

    def create_master_plan_layer(self):
        """Create the single master plan layer"""
        self.stdout.write("\n📄 Creating master plan layer...")
        
        # Get all files
        geojson_files = list(self.data_dir.glob("*.geojson"))
        tif_files = list(self.data_dir.glob("*.tif"))
        all_files = geojson_files + tif_files
        
        self.stdout.write(f"  📊 Found {len(geojson_files)} GeoJSON + {len(tif_files)} TIF files")
        
        # Create layer
        self.layer, created = DataLayer.objects.get_or_create(
            city=self.city,
            slug='chennai-master-plan',
            defaults={
                'name': 'Chennai Master Plan',
                'category': self.category,
                'description': 'Chennai Master Plan boundaries and proposed land use data (2026)',
                'original_filename': 'chennai_master_plan',
                'file_format': 'GEOJSON',
                'file_path': str(self.data_dir),
                'is_directory': True,
                'file_pattern': '*.geojson',
                'source_files': [f.name for f in all_files],
                'categorization_method': 'FILENAME',
                'geometry_type': 'POLYGON',
                'is_processed': False,
                'feature_count': 0,
                'is_true': True,
                'tiles_generated': False,
                'data_source': 'Chennai Metropolitan Development Authority (CMDA)',
                'last_updated': timezone.now()
            }
        )
        
        if not created:
            # Update existing layer
            self.layer.source_files = [f.name for f in all_files]
            self.layer.file_path = str(self.data_dir)
            self.layer.is_directory = True
            self.layer.file_pattern = '*.geojson'
            self.layer.save()
        
        action = "Created" if created else "Updated"
        self.stdout.write(f"  ✅ {action} layer: {self.layer.name}")

    def process_all_files(self, force=False):
        """Process all GeoJSON files into the single layer"""
        self.stdout.write("\n📁 Processing GeoJSON files...")
        
        # Delete existing features if force
        if force:
            count = GeoFeature.objects.filter(layer=self.layer).delete()[0]
            if count > 0:
                self.stdout.write(f"  🗑️ Deleted {count} existing features")
        
        geojson_files = list(self.data_dir.glob("*.geojson"))
        total_features = 0
        
        for file_path in sorted(geojson_files):
            self.stdout.write(f"\n  📄 Processing {file_path.name}...")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Handle both FeatureCollection and single Feature
                features = data.get('features', [])
                if not features and data.get('type') in ['Feature', 'Polygon', 'MultiPolygon']:
                    features = [data]
                
                file_features = 0
                
                for idx, feature_data in enumerate(features):
                    try:
                        # Get geometry
                        if feature_data.get('type') == 'Feature':
                            geometry_data = feature_data.get('geometry')
                            properties = feature_data.get('properties', {})
                        else:
                            geometry_data = feature_data
                            properties = {}
                        
                        if not geometry_data:
                            continue
                        
                        # Create GEOS geometry
                        geometry = GEOSGeometry(json.dumps(geometry_data))
                        
                        # Skip empty geometries
                        if geometry.empty:
                            continue
                        
                        # Fix invalid geometry
                        if not geometry.valid:
                            geometry = geometry.buffer(0)
                            if not geometry.valid:
                                continue
                        
                        # Create feature name
                        feature_name = (
                            properties.get('name') or
                            properties.get('Name') or
                            properties.get('boundary_type') or
                            f"{file_path.stem}_Feature_{idx + 1}"
                        )
                        
                        # Skip duplicates unless force
                        if not force:
                            exists = GeoFeature.objects.filter(
                                layer=self.layer,
                                source_layer_name=file_path.stem,
                                name=feature_name
                            ).exists()
                            if exists:
                                continue
                        
                        # Create feature
                        GeoFeature.objects.create(
                            layer=self.layer,
                            geometry=geometry,
                            name=feature_name,
                            description=properties.get('description', ''),
                            source_layer_name=file_path.stem,
                            zone_category=properties.get('type', 'Administrative Boundary'),
                            zone_subcategory=properties.get('subtype', ''),
                            area=self._safe_float(properties.get('area')),
                            shape_length=self._safe_float(properties.get('perimeter')),
                            shape_area=self._safe_float(properties.get('area')),
                            objectid=self._safe_int(properties.get('id')),
                            properties=properties,
                            is_valid=True
                        )
                        
                        file_features += 1
                        total_features += 1
                        
                    except Exception as e:
                        self.stdout.write(f"    ⚠️ Error: {e}")
                        continue
                
                self.stdout.write(f"    ✅ Added {file_features} features")
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"    ❌ Failed: {e}"))
        
        # Update layer
        self.layer.feature_count = total_features
        self.layer.is_processed = total_features > 0
        self.layer.last_updated = timezone.now()
        self.layer.save()
        
        self.stdout.write(f"\n  📊 Total features inserted: {total_features}")

    def calculate_layer_bounds(self):
        """Calculate bounding box for the layer"""
        self.stdout.write("\n📍 Calculating layer bounds...")
        
        try:
            bbox = self.layer.calculate_bbox()
            if bbox:
                self.stdout.write(f"  ✅ Bounds: {bbox}")
        except Exception as e:
            self.stdout.write(f"  ⚠️ Error: {e}")

    def print_summary(self):
        """Print final summary"""
        self.stdout.write("\n" + "="*50)
        self.stdout.write("📊 SUMMARY")
        self.stdout.write("="*50)
        
        total_features = GeoFeature.objects.filter(layer=self.layer).count()
        
        self.stdout.write(f"• State: {self.state.name}")
        self.stdout.write(f"• City: {self.city.name}")
        self.stdout.write(f"• Layer: {self.layer.name}")
        self.stdout.write(f"• Is Directory: {self.layer.is_directory}")
        self.stdout.write(f"• File Path: {self.layer.file_path}")
        self.stdout.write(f"• File Pattern: {self.layer.file_pattern}")
        self.stdout.write(f"• Source Files: {len(self.layer.source_files)}")
        self.stdout.write(f"• Total Features: {total_features}")
        self.stdout.write(f"• Processed: {self.layer.is_processed}")
        self.stdout.write(f"• Has Bounds: {self.layer.has_valid_bbox()}")

    def _safe_float(self, value):
        """Convert to float safely"""
        try:
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value):
        """Convert to int safely"""
        try:
            return int(value) if value is not None else None
        except (ValueError, TypeError):
            return None