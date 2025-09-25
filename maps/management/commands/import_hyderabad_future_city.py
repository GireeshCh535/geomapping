# maps/management/commands/import_hyderabad_future_city.py
"""
Import command for Hyderabad Future City FCDA Boundary data
Usage: python manage.py import_hyderabad_future_city --data-dir data
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.gis.geos import Polygon, MultiPolygon
from django.utils.text import slugify
from django.utils import timezone
from maps.models import (
    State, City, LayerCategory, DataLayer, 
    GeoFeature, CityLayerStyle
)
from maps.config import DATA_IMPORT_CONFIG
import json
import os
from pathlib import Path
import traceback

class Command(BaseCommand):
    help = 'Import Hyderabad Future City FCDA Boundary data with proper styling'
    
    def add_arguments(self, parser):
        parser.add_argument('--data-dir', type=str, required=True, help='Data directory path')
        parser.add_argument('--force', action='store_true', help='Force reimport existing data')
        parser.add_argument('--dry-run', action='store_true', help='Dry run without saving')
        parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    def handle(self, *args, **options):
        """Handle the command"""
        
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS("🏗️  HYDERABAD FUTURE CITY IMPORT"))
        self.stdout.write(self.style.SUCCESS("=" * 70))
        
        # Initialize stats
        self.stats = {
            'layers': 0,
            'features': 0,
            'files_processed': 0,
            'errors': []
        }
        
        data_dir = Path(options['data_dir'])
        
        # Get Hyderabad future city config
        hyderabad_config = DATA_IMPORT_CONFIG['states']['telangana']['cities']['hyderabad']
        future_city_config = hyderabad_config['layer_groups']['future-city']
        
        try:
            self._process_future_city_import(data_dir, future_city_config, options)
            
            if options['dry_run']:
                self.stdout.write(self.style.WARNING("\n🔄 DRY RUN - No changes made"))
            
            self._print_summary()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Import failed: {e}"))
            if options['verbose']:
                self.stdout.write(traceback.format_exc())
    
    def _process_future_city_import(self, data_dir, future_city_config, options):
        """Process Hyderabad Future City import"""
        
        # Get or create state and city
        state, _ = State.objects.get_or_create(
            slug='telangana',
            defaults={
                'name': 'Telangana',
                'code': 'TS',
                'center_lat': 18.1124,
                'center_lng': 79.0193,
                'default_zoom': 7
            }
        )
        
        city, _ = City.objects.get_or_create(
            slug='hyderabad',
            defaults={
                'name': 'Hyderabad',
                'state_ref': state,
                'center_lat': 17.3850,
                'center_lng': 78.4867,
                'min_zoom': 8,
                'max_zoom': 18
            }
        )
        
        # Get or create planning category
        planning_category, _ = LayerCategory.objects.get_or_create(
            code='PLANNING',
            defaults={
                'name': 'Planning',
                'description': 'Planning and development zones'
            }
        )
        
        # Process FCDA Boundary
        fcda_file = future_city_config['files']['FCDA Boundary.geojson']
        fcda_path = data_dir / future_city_config['path'] / 'FCDA Boundary.geojson'
        
        if fcda_path.exists():
            self._import_fcda_boundary(
                fcda_path, city, planning_category, 
                fcda_file, options
            )
        else:
            self.stdout.write(self.style.WARNING(f"⚠️ FCDA Boundary file not found: {fcda_path}"))
    
    def _import_fcda_boundary(self, file_path, city, category, config, options):
        """Import FCDA Boundary with proper styling"""
        
        self.stdout.write(f"\n🏗️ Processing FCDA Boundary: {file_path.name}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
            
            # Create or update the layer
            layer, created = DataLayer.objects.update_or_create(
                city=city,
                slug='hyderabad_fcda_boundary',
                defaults={
                    'name': config['name'],
                    'category': category,
                    'description': 'Hyderabad Future City Development Authority (FCDA) Boundary',
                    'file_path': str(file_path),
                    'file_format': 'GEOJSON',
                    'geometry_type': 'MULTIPOLYGON',
                    'is_processed': False
                }
            )
            
            if created:
                self.stdout.write(f"✅ Created FCDA Boundary layer: {layer.name}")
            else:
                self.stdout.write(f"🔄 Updated FCDA Boundary layer: {layer.name}")
            
            # Process features
            features = geojson_data.get('features', [])
            feature_count = 0
            
            for feature in features:
                if self._process_fcda_feature(feature, layer, config, options):
                    feature_count += 1
            
            # Update layer statistics
            layer.feature_count = feature_count
            layer.is_processed = True
            layer.save()
            
            self.stats['layers'] += 1
            self.stats['features'] += feature_count
            self.stats['files_processed'] += 1
            
            self.stdout.write(f"✅ Imported {feature_count} FCDA Boundary features")
            
        except Exception as e:
            error_msg = f"Error processing FCDA Boundary: {e}"
            self.stdout.write(self.style.ERROR(f"❌ {error_msg}"))
            self.stats['errors'].append(error_msg)
    
    def _process_fcda_feature(self, feature, layer, config, options):
        """Process individual FCDA Boundary feature"""
        
        try:
            geometry = feature.get('geometry')
            properties = feature.get('properties', {})
            
            if not geometry or geometry.get('type') not in ['Polygon', 'MultiPolygon']:
                return False
            
            # Create geometry
            if geometry.get('type') == 'Polygon':
                geom = Polygon(geometry['coordinates'][0])
            else:  # MultiPolygon
                geom = MultiPolygon([Polygon(ring) for ring in geometry['coordinates'][0]])
            
            # Create feature properties with styling information
            feature_properties = {
                'name': properties.get('Name', 'FCDA'),
                'object_id': properties.get('OBJECTID', 1),
                'shape_length': properties.get('Shape_Leng', 0),
                'shape_area': properties.get('Shape_Area', 0),
                'fill_color': config['color'],
                'border_color': config.get('border_color', '#C3C3C3'),
                'opacity': config.get('opacity', 0.5),
                'type': config.get('type', 'boundary'),
                'original_properties': properties
            }
            
            # Create GeoFeature
            geo_feature = GeoFeature(
                layer=layer,
                geometry=geom,
                zone_category='FCDA Boundary',
                name=properties.get('Name', 'FCDA'),
                properties=feature_properties,
                source_layer_name=layer.name
            )
            
            if not options['dry_run']:
                geo_feature.save()
            
            if options['verbose']:
                self.stdout.write(f"  🏗️ FCDA Boundary: {properties.get('Name', 'FCDA')}")
            
            return True
            
        except Exception as e:
            if options['verbose']:
                self.stdout.write(self.style.ERROR(f"  ❌ Error processing feature: {e}"))
            return False
    
    def _print_summary(self):
        """Print import summary"""
        
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS("📊 HYDERABAD FUTURE CITY IMPORT SUMMARY"))
        self.stdout.write(self.style.SUCCESS("=" * 70))
        
        self.stdout.write(f"✅ Layers processed: {self.stats['layers']}")
        self.stdout.write(f"✅ Features imported: {self.stats['features']}")
        self.stdout.write(f"✅ Files processed: {self.stats['files_processed']}")
        
        if self.stats['errors']:
            self.stdout.write(self.style.ERROR(f"❌ Errors: {len(self.stats['errors'])}"))
            for error in self.stats['errors']:
                self.stdout.write(self.style.ERROR(f"  - {error}"))
        
        self.stdout.write(self.style.SUCCESS("\n🎉 Hyderabad Future City import completed!"))
