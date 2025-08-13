# maps/management/commands/import_geospatial_data.py
"""
Clean import command for master plans - tested and working
Usage: python manage.py import_geospatial_data --data-dir data --state karnataka --city bengaluru
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.gis.geos import Polygon, MultiPolygon
from django.utils.text import slugify
from django.utils import timezone
from maps.models import (
    State, City, LayerCategory, DataLayer, 
    GeoFeature, LayerGroup, CityLayerStyle
)
from maps.config import DATA_IMPORT_CONFIG, LAYER_CATEGORIES
import json
import os
from pathlib import Path
import traceback

class Command(BaseCommand):
    help = 'Import geospatial data for master plans with proper model fields'
    
    def add_arguments(self, parser):
        parser.add_argument('--data-dir', required=True, help='Base data directory')
        parser.add_argument('--state', help='State slug (e.g., karnataka)')
        parser.add_argument('--city', help='City slug (e.g., bengaluru)')
        parser.add_argument('--force', action='store_true', help='Force re-import')
        parser.add_argument('--dry-run', action='store_true', help='Test without saving')
        parser.add_argument('--verbose', action='store_true', help='Verbose output')
        parser.add_argument('--skip-existing', action='store_true', help='Skip existing layers')
        
    def handle(self, *args, **options):
        data_dir = Path(options['data_dir'])
        
        if not data_dir.exists():
            self.stdout.write(self.style.ERROR(f"❌ Data directory not found: {data_dir}"))
            return
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🚀 GEOSPATIAL DATA IMPORT'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        self.stats = {
            'states': 0,
            'cities': 0,
            'layers': 0,
            'features': 0,
            'skipped': 0,
            'errors': []
        }
        
        try:
            with transaction.atomic():
                self._process_import(data_dir, options)
                
                if options['dry_run']:
                    self.stdout.write(self.style.WARNING("\n🔄 DRY RUN - Rolling back"))
                    raise Exception("Dry run complete")
                
                self._print_summary()
                
        except Exception as e:
            if "Dry run complete" not in str(e):
                self.stdout.write(self.style.ERROR(f"\n❌ Import failed: {e}"))
                if options['verbose']:
                    self.stdout.write(traceback.format_exc())
            else:
                self._print_summary()
    
    def _process_import(self, data_dir, options):
        """Main import process"""
        
        # Get states to process from config
        states_config = DATA_IMPORT_CONFIG.get('states', {})
        
        if options['state']:
            if options['state'] not in states_config:
                raise ValueError(f"State '{options['state']}' not in configuration")
            states_to_process = {options['state']: states_config[options['state']]}
        else:
            states_to_process = states_config
        
        # Process each state
        for state_slug, state_config in states_to_process.items():
            self._process_state(state_slug, state_config, data_dir, options)
    
    def _process_state(self, state_slug, state_config, data_dir, options):
        """Process a single state"""
        
        self.stdout.write(f"\n📦 State: {state_config['name']} ({state_slug})")
        
        # Try to find state by slug first, then by name
        try:
            state = State.objects.get(slug=state_slug)
            self.stdout.write(f"  ✓ Using existing state (by slug): {state.name}")
        except State.DoesNotExist:
            # Try to find by name
            try:
                state = State.objects.get(name=state_config['name'])
                self.stdout.write(f"  ✓ Using existing state (by name): {state.name}")
                # Update slug if different
                if state.slug != state_slug:
                    self.stdout.write(f"    Updating slug from '{state.slug}' to '{state_slug}'")
                    state.slug = state_slug
                    state.save()
            except State.DoesNotExist:
                # Create new state
                state = State.objects.create(
                    slug=state_slug,
                    name=state_config['name'],
                    code=state_config['code'],
                    is_active=True
                )
                self.stats['states'] += 1
                self.stdout.write(f"  ✅ Created state: {state.name}")
        
        # Process cities
        cities_config = state_config.get('cities', {})
        
        if options['city']:
            # Handle city aliases
            city_slug = options['city']
            
            # Map common aliases
            city_aliases = {
                'vizag': 'visakhapatnam',
                'bangalore': 'bengaluru'
            }
            
            if city_slug in city_aliases:
                city_slug = city_aliases[city_slug]
                self.stdout.write(f"  ℹ️  Using city alias: {options['city']} → {city_slug}")
            
            if city_slug not in cities_config:
                self.stdout.write(self.style.ERROR(f"  ❌ City '{city_slug}' not found"))
                return
            cities_to_process = {city_slug: cities_config[city_slug]}
        else:
            cities_to_process = cities_config
        
        for city_slug, city_config in cities_to_process.items():
            self._process_city(state, city_slug, city_config, data_dir, options)
    
    def _process_city(self, state, city_slug, city_config, data_dir, options):
        """Process a single city"""
        
        self.stdout.write(f"\n  🏙️  City: {city_config['name']} ({city_slug})")
        
        # Try to find city by slug first, then by name
        try:
            city = City.objects.get(slug=city_slug)
            self.stdout.write(f"    ✓ Using existing city (by slug): {city.name}")
        except City.DoesNotExist:
            # Try to find by name
            try:
                city = City.objects.get(name=city_config['name'])
                self.stdout.write(f"    ✓ Using existing city (by name): {city.name}")
                # Update slug if different
                if city.slug != city_slug:
                    self.stdout.write(f"      Updating slug from '{city.slug}' to '{city_slug}'")
                    city.slug = city_slug
                    city.save()
            except City.DoesNotExist:
                # Create new city
                city = City.objects.create(
                    slug=city_slug,
                    name=city_config['name'],
                    state=city_config['name'],  # Legacy field
                    state_ref=state,
                    center_lat=city_config.get('center_lat', 0),
                    center_lng=city_config.get('center_lng', 0),
                    min_zoom=8,
                    max_zoom=18,
                    is_active=True
                )
                self.stats['cities'] += 1
                self.stdout.write(f"    ✅ Created city: {city.name}")
        
        # Process master-plan layer group
        layer_groups = city_config.get('layer_groups', {})
        if 'master-plan' in layer_groups:
            group_config = layer_groups['master-plan']
            self._process_layer_group(city, 'master-plan', group_config, data_dir, city_config, options)
        else:
            self.stdout.write(self.style.ERROR(f"    ❌ No master-plan configuration found"))
    
    def _process_layer_group(self, city, group_slug, group_config, data_dir, city_config, options):
        """Process a layer group and its files"""
        
        self.stdout.write(f"    📂 Layer Group: {group_config['name']}")
        
        # Create layer group if model supports it
        layer_group = None
        try:
            category = self._get_or_create_category('MIXED_USE')
            directory_path = group_config.get('path', '')
            
            layer_group, created = LayerGroup.objects.get_or_create(
                city=city,
                slug=group_slug,
                defaults={
                    'name': group_config['name'],
                    'description': group_config.get('description', ''),
                    'category': category,
                    'directory_path': directory_path,
                    'display_order': group_config.get('display_order', 1),
                    'is_visible': True,
                    'default_color': '#666666',
                    'default_stroke': '#333333',
                    'default_opacity': 0.7
                }
            )
            if created:
                self.stdout.write(f"      ✅ Created layer group: {layer_group.name}")
            else:
                self.stdout.write(f"      ✓ Using existing layer group: {layer_group.name}")
        except Exception as e:
            if options['verbose']:
                self.stdout.write(f"      ⚠️  Layer group handling: {e}")
        
        # Get files path
        files_path = data_dir / group_config['path']
        if not files_path.exists():
            self.stdout.write(self.style.ERROR(f"      ❌ Path not found: {files_path}"))
            self.stats['errors'].append(f"Path not found: {files_path}")
            return
        
        files = group_config.get('files', {})
        self.stdout.write(f"      📄 Processing {len(files)} files")
        
        success_count = 0
        for filename, file_config in files.items():
            file_path = files_path / filename
            
            if not file_path.exists():
                self.stdout.write(self.style.WARNING(f"        ⚠️  {filename} not found"))
                self.stats['errors'].append(f"File not found: {filename}")
                continue
            
            try:
                result = self._import_file(
                    city, 
                    layer_group,
                    file_path, 
                    file_config, 
                    city_config, 
                    options
                )
                
                if result == 'skipped':
                    self.stdout.write(f"        ⏭️  {filename}: Already exists")
                    self.stats['skipped'] += 1
                elif result > 0:
                    self.stdout.write(self.style.SUCCESS(f"        ✅ {filename}: {result} features imported"))
                    self.stats['layers'] += 1
                    self.stats['features'] += result
                    success_count += 1
                else:
                    self.stdout.write(self.style.WARNING(f"        ⚠️  {filename}: No features found"))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"        ❌ {filename}: {str(e)}"))
                self.stats['errors'].append(f"{filename}: {str(e)}")
                if options['verbose']:
                    self.stdout.write(traceback.format_exc())
        
        self.stdout.write(f"      ✓ Successfully imported {success_count}/{len(files)} files")
    
    def _import_file(self, city, layer_group, file_path, file_config, city_config, options):
        """Import a single file - returns number of features or 'skipped'"""
        
        layer_slug = slugify(file_path.stem)
        
        # Check if layer exists
        existing_layer = DataLayer.objects.filter(city=city, slug=layer_slug).first()
        
        if existing_layer and not options['force']:
            if options['skip_existing']:
                return 'skipped'
            # Update existing
            layer = existing_layer
            # Clear old features
            GeoFeature.objects.filter(layer=layer).delete()
            action = 'updated'
        else:
            if existing_layer and options['force']:
                # Delete existing layer and features
                existing_layer.delete()
            
            # Get category
            category = self._get_or_create_category(file_config.get('category', 'MIXED_USE'))
            
            # Determine file format
            data_format = city_config.get('data_format', 'geojson')
            if data_format == 'esri_json':
                format_choice = 'ESRI_JSON'
            else:
                format_choice = 'GEOJSON'
            
            # Create new layer
            layer = DataLayer.objects.create(
                city=city,
                category=category,
                name=file_config['name'],
                slug=layer_slug,
                description=file_config.get('description', ''),
                original_filename=str(file_path.name),
                file_format=format_choice,
                categorization_method='MANUAL',
                feature_count=0,
                is_processed=False
            )
            action = 'created'
        
        # Try to create style (ignore errors)
        try:
            self._create_style(city, layer.category, file_config)
        except Exception as e:
            if options['verbose']:
                self.stdout.write(f"          Style warning: {e}")
        
        # Import features
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        features_count = self._import_features(layer, data, city_config, options)
        
        # Update layer metadata
        layer.feature_count = features_count
        layer.is_processed = True
        layer.last_processed = timezone.now()
        layer.save()
        
        return features_count
    
    def _import_features(self, layer, data, city_config, options):
        """Import features from JSON data"""
        
        features_to_create = []
        plu_field = city_config.get('plu_field', 'PLU')
        data_format = city_config.get('data_format', 'geojson')
        error_count = 0
        
        if data_format == 'esri_json' and 'features' in data:
            # ESRI JSON format (Bengaluru)
            for idx, feature in enumerate(data['features']):
                if not feature:
                    continue
                    
                geom = feature.get('geometry')
                props = feature.get('attributes', {})
                
                if not geom:
                    continue
                
                if 'rings' in geom and geom['rings']:
                    try:
                        # Take first ring as exterior
                        rings = geom['rings']
                        if rings and len(rings[0]) > 3:  # Valid polygon needs at least 4 points
                            polygon = Polygon(rings[0])
                            
                            # Add PLU code to properties if it exists
                            if props and plu_field in props:
                                props['_plu_code'] = str(props[plu_field])[:50]
                            
                            # Create feature without plu_code field
                            features_to_create.append(GeoFeature(
                                layer=layer,
                                geometry=polygon,
                                properties=props or {}
                            ))
                    except Exception as e:
                        error_count += 1
                        if options['verbose'] and error_count <= 10:
                            self.stdout.write(f"          Error processing feature {idx}: {e}")
        
        elif 'features' in data:
            # Standard GeoJSON format
            for idx, feature in enumerate(data['features']):
                if not feature:
                    continue
                    
                geom = feature.get('geometry')
                props = feature.get('properties', {})
                
                if not geom:
                    continue
                
                try:
                    geom_type = geom.get('type')
                    coords = geom.get('coordinates')
                    
                    if geom_type == 'Polygon' and coords:
                        if coords and len(coords) > 0 and len(coords[0]) > 3:
                            polygon = Polygon(coords[0])
                            
                            # Add PLU code to properties if it exists
                            if props and plu_field in props:
                                props['_plu_code'] = str(props[plu_field])[:50]
                            
                            # Create feature without plu_code field
                            features_to_create.append(GeoFeature(
                                layer=layer,
                                geometry=polygon,
                                properties=props or {}
                            ))
                    
                    elif geom_type == 'MultiPolygon' and coords:
                        polygons = []
                        for poly_coords in coords:
                            if poly_coords and len(poly_coords) > 0 and len(poly_coords[0]) > 3:
                                polygons.append(Polygon(poly_coords[0]))
                        
                        if polygons:
                            multi_poly = MultiPolygon(polygons)
                            
                            # Add PLU code to properties if it exists
                            if props and plu_field in props:
                                props['_plu_code'] = str(props[plu_field])[:50]
                            
                            features_to_create.append(GeoFeature(
                                layer=layer,
                                geometry=multi_poly,
                                properties=props or {}
                            ))
                                
                except Exception as e:
                    error_count += 1
                    if options['verbose'] and error_count <= 10:
                        self.stdout.write(f"          Error processing feature {idx}: {e}")
        
        # Show total errors if more than 10
        if error_count > 10 and options['verbose']:
            self.stdout.write(f"          ... and {error_count - 10} more errors")
        
        # Bulk create features
        if features_to_create:
            GeoFeature.objects.bulk_create(features_to_create, batch_size=500)
            if options['verbose']:
                self.stdout.write(f"          Created {len(features_to_create)} features")
        
        return len(features_to_create)
    
    def _create_style(self, city, category, file_config):
        """Create style for category - ignore if model doesn't support all fields"""
        
        # Delete existing style for this category
        CityLayerStyle.objects.filter(city=city, category=category).delete()
        
        color_config = file_config.get('color', '#CCCCCC')
        
        # Prepare style data
        style_data = {
            'city': city,
            'category': category,
            'stroke_width': 1
        }
        
        if isinstance(color_config, dict):
            # Pattern style
            if 'hatch' in color_config:
                style_data['fill_pattern'] = 'HATCHED'
                style_data['pattern_color'] = color_config.get('hatch', '#000000')
            elif 'dot' in color_config:
                style_data['fill_pattern'] = 'DOTTED'
                style_data['pattern_color'] = color_config.get('dot', '#000000')
            else:
                style_data['fill_pattern'] = 'SOLID'
                style_data['pattern_color'] = '#000000'
            
            style_data['fill_color'] = color_config.get('solid', '#CCCCCC')
            style_data['stroke_color'] = color_config.get('solid', '#CCCCCC')
        else:
            # Solid color
            style_data['fill_pattern'] = 'SOLID'
            style_data['fill_color'] = color_config
            style_data['stroke_color'] = color_config
            style_data['pattern_color'] = color_config
        
        # Create style
        CityLayerStyle.objects.create(**style_data)
    
    def _get_or_create_category(self, category_code):
        """Get or create category"""
        category_info = LAYER_CATEGORIES.get(category_code, {})
        category, created = LayerCategory.objects.get_or_create(
            code=category_code,
            defaults={
                'name': category_info.get('name', category_code),
                'description': category_info.get('description', ''),
                'default_color': category_info.get('default_color', '#CCCCCC'),
                'default_opacity': category_info.get('default_opacity', 0.8)
            }
        )
        return category
    
    def _print_summary(self):
        """Print import summary"""
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("📊 IMPORT SUMMARY"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"✅ States created: {self.stats['states']}")
        self.stdout.write(f"✅ Cities created: {self.stats['cities']}")
        self.stdout.write(f"✅ Layers imported: {self.stats['layers']}")
        self.stdout.write(f"✅ Features imported: {self.stats['features']:,}")
        
        if self.stats['skipped'] > 0:
            self.stdout.write(f"⏭️  Layers skipped: {self.stats['skipped']}")
        
        if self.stats['errors']:
            self.stdout.write(f"\n⚠️  Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:5]:
                self.stdout.write(f"  - {error}")
            if len(self.stats['errors']) > 5:
                self.stdout.write(f"  ... and {len(self.stats['errors']) - 5} more")
        
        # Show what was created
        self.stdout.write("\n📦 Database Status:")
        try:
            from maps.models import State, City, DataLayer, GeoFeature
            self.stdout.write(f"  Total States: {State.objects.count()}")
            self.stdout.write(f"  Total Cities: {City.objects.count()}")
            self.stdout.write(f"  Total Layers: {DataLayer.objects.count()}")
            self.stdout.write(f"  Total Features: {GeoFeature.objects.count()}")
            
            # Show Bengaluru specific if imported
            bengaluru_layers = DataLayer.objects.filter(city__slug='bengaluru')
            if bengaluru_layers.exists():
                self.stdout.write(f"\n  Bengaluru Layers: {bengaluru_layers.count()}")
                for layer in bengaluru_layers[:5]:
                    self.stdout.write(f"    - {layer.name}: {layer.feature_count} features")
        except Exception as e:
            self.stdout.write(f"  Error getting stats: {e}")