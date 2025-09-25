"""
Import command for Hyderabad Metro data (lines + stations combined)
Usage: python manage.py import_hyderabad_metro_combined --data-dir data
"""

from django.core.management.base import BaseCommand
from django.contrib.gis.geos import LineString, Point
from django.utils.text import slugify
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
    help = 'Import Hyderabad Metro data (lines + stations) into a single combined layer'
    
    def add_arguments(self, parser):
        parser.add_argument('--data-dir', type=str, required=True, help='Path to the base data directory')
        parser.add_argument('--force', action='store_true', help='Force re-import and overwrite existing data')
        parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without saving changes')
        parser.add_argument('--verbose', action='store_true', help='Enable verbose output')

    def handle(self, *args, **options):
        data_dir = Path(options['data_dir'])
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🚇 HYDERABAD METRO COMBINED IMPORT'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        self.stats = {
            'layers': 0,
            'features': 0,
            'lines': 0,
            'stations': 0,
            'errors': []
        }
        
        try:
            self._process_metro_import(data_dir, options)
            
            if options['dry_run']:
                self.stdout.write(self.style.WARNING("\n🔄 DRY RUN - No changes made"))
            
            self._print_summary()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Import failed: {e}"))
            if options['verbose']:
                self.stdout.write(traceback.format_exc())
    
    def _process_metro_import(self, data_dir, options):
        """Process Hyderabad metro import with combined lines and stations"""
        
        # Get Hyderabad configuration
        hyderabad_config = DATA_IMPORT_CONFIG['states']['telangana']['cities']['hyderabad']
        metro_config = hyderabad_config['layer_groups']['metro']
        
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
        
        # Get transport category
        transport_category = LayerCategory.objects.get(code='TRANSPORT')
        
        # Create or update the single metro layer
        layer, created = DataLayer.objects.update_or_create(
            city=city,
            slug='hyderabad_metro',
            defaults={
                'name': 'Hyderabad Metro',
                'category': transport_category,
                'description': 'Hyderabad Metro - All Phases with Lines and Stations',
                'file_path': str(data_dir / metro_config['path']),
                'file_format': 'GEOJSON',
                'geometry_type': 'MIXED',
                'is_processed': False
            }
        )
        
        if created:
            self.stdout.write(f"✅ Created combined metro layer: {layer.name}")
        else:
            self.stdout.write(f"🔄 Updated combined metro layer: {layer.name}")
        
        # Get line colors from config
        line_colors = metro_config['files']['Hyd_metro_lines_ph_1&2_Final.geojson'].get('line_colors', {})
        
        # Process metro lines
        metro_lines_path = data_dir / metro_config['path'] / 'Hyd_metro_lines_ph_1&2_Final.geojson'
        if metro_lines_path.exists():
            self._import_metro_lines(metro_lines_path, layer, line_colors, options)
        else:
            self.stdout.write(self.style.WARNING(f"⚠️ Metro lines file not found: {metro_lines_path}"))
        
        # Process metro stations
        metro_stations_path = data_dir / metro_config['path'] / 'Hyd_metro_stations_ph1&2.geojson'
        if metro_stations_path.exists():
            self._import_metro_stations(metro_stations_path, layer, options)
        else:
            self.stdout.write(self.style.WARNING(f"⚠️ Metro stations file not found: {metro_stations_path}"))
        
        # Update layer statistics
        layer.feature_count = self.stats['features']
        layer.is_processed = True
        layer.save()
        
        self.stats['layers'] += 1
    
    def _import_metro_lines(self, file_path, layer, line_colors, options):
        """Import metro lines into the combined layer"""
        
        self.stdout.write(f"\n📊 Processing metro lines: {file_path.name}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
            
            features = geojson_data.get('features', [])
            feature_count = 0
            
            for feature in features:
                if self._process_metro_line_feature(feature, layer, line_colors, options):
                    feature_count += 1
                    self.stats['lines'] += 1
            
            self.stats['features'] += feature_count
            self.stats['files_processed'] = self.stats.get('files_processed', 0) + 1
            
            self.stdout.write(f"✅ Imported {feature_count} metro line features")
            
        except Exception as e:
            error_msg = f"Error processing metro lines: {e}"
            self.stdout.write(self.style.ERROR(f"❌ {error_msg}"))
            self.stats['errors'].append(error_msg)
    
    def _process_metro_line_feature(self, feature, layer, line_colors, options):
        """Process individual metro line feature"""
        
        try:
            geometry = feature.get('geometry')
            properties = feature.get('properties', {})
            
            if not geometry or geometry.get('type') != 'LineString':
                return False
            
            # Get line color from properties
            line_color = properties.get('linecolour', 'Green Line')
            color_hex = line_colors.get(line_color, '#00933D')  # Default green
            
            # Create LineString geometry
            coords = geometry.get('coordinates', [])
            if len(coords) < 2:
                return False
            
            line_geom = LineString(coords)
            
            # Create feature properties with color information
            feature_properties = {
                'feature_type': 'metro_line',
                'line_color': line_color,
                'color_hex': color_hex,
                'from_station': properties.get('from_junct', ''),
                'to_station': properties.get('to_junct', ''),
                'no_of_stations': properties.get('noofstatio', 0),
                'length_km': properties.get('length_km', 0),
                'status': properties.get('Status', 'Existing'),
                'original_properties': properties
            }
            
            # Create GeoFeature
            geo_feature = GeoFeature(
                layer=layer,
                geometry=line_geom,
                zone_category=line_color,
                properties=feature_properties,
                source_layer_name=layer.name
            )
            
            if not options['dry_run']:
                geo_feature.save()
            
            if options['verbose']:
                self.stdout.write(f"  📍 {line_color}: {properties.get('from_junct', '')} → {properties.get('to_junct', '')}")
            
            return True
            
        except Exception as e:
            if options['verbose']:
                self.stdout.write(self.style.ERROR(f"  ❌ Error processing line feature: {e}"))
            return False
    
    def _import_metro_stations(self, file_path, layer, options):
        """Import metro stations into the combined layer"""
        
        self.stdout.write(f"\n🚉 Processing metro stations: {file_path.name}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
            
            features = geojson_data.get('features', [])
            feature_count = 0
            
            for feature in features:
                if self._process_metro_station_feature(feature, layer, options):
                    feature_count += 1
                    self.stats['stations'] += 1
            
            self.stats['features'] += feature_count
            self.stats['files_processed'] = self.stats.get('files_processed', 0) + 1
            
            self.stdout.write(f"✅ Imported {feature_count} metro station features")
            
        except Exception as e:
            error_msg = f"Error processing metro stations: {e}"
            self.stdout.write(self.style.ERROR(f"❌ {error_msg}"))
            self.stats['errors'].append(error_msg)
    
    def _process_metro_station_feature(self, feature, layer, options):
        """Process individual metro station feature"""
        
        try:
            geometry = feature.get('geometry')
            properties = feature.get('properties', {})
            
            if not geometry or geometry.get('type') != 'Point':
                return False
            
            # Create Point geometry
            coords = geometry.get('coordinates', [])
            if len(coords) != 2:
                return False
            
            point_geom = Point(coords)
            
            # Create feature properties
            feature_properties = {
                'feature_type': 'metro_station',
                'station_name': properties.get('name', ''),
                'station_type': properties.get('stationtype', ''),
                'address': properties.get('address', ''),
                'remarks': properties.get('remarks', ''),
                'phone': properties.get('phone', ''),
                'layer': properties.get('layer', ''),
                'color_hex': '#00933D',  # Default station color
                'original_properties': properties
            }
            
            # Create GeoFeature
            geo_feature = GeoFeature(
                layer=layer,
                geometry=point_geom,
                zone_category=properties.get('stationtype', 'General Station') or 'General Station',
                name=properties.get('name', ''),
                properties=feature_properties,
                source_layer_name=layer.name
            )
            
            if not options['dry_run']:
                geo_feature.save()
            
            if options['verbose']:
                self.stdout.write(f"  🚉 {properties.get('name', '')} ({properties.get('stationtype', '')})")
            
            return True
            
        except Exception as e:
            if options['verbose']:
                self.stdout.write(self.style.ERROR(f"  ❌ Error processing station feature: {e}"))
            return False
    
    def _print_summary(self):
        """Print import summary"""
        
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS("📊 HYDERABAD METRO COMBINED IMPORT SUMMARY"))
        self.stdout.write(self.style.SUCCESS("=" * 70))
        
        self.stdout.write(f"✅ Layers processed: {self.stats['layers']}")
        self.stdout.write(f"✅ Total features imported: {self.stats['features']}")
        self.stdout.write(f"✅ Metro lines: {self.stats['lines']}")
        self.stdout.write(f"✅ Metro stations: {self.stats['stations']}")
        self.stdout.write(f"✅ Files processed: {self.stats.get('files_processed', 0)}")
        
        if self.stats['errors']:
            self.stdout.write(self.style.ERROR(f"❌ Errors: {len(self.stats['errors'])}"))
            for error in self.stats['errors']:
                self.stdout.write(self.style.ERROR(f"  - {error}"))
        
        self.stdout.write(self.style.SUCCESS("\n🎉 Hyderabad Metro combined import completed!"))
