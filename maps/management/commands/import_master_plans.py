# maps/management/commands/import_master_plans.py
"""
Import master plans following hierarchical structure:
State (slug) → City (slug) → Layer Group (slug) → Files

Usage:
python manage.py import_master_plans --data-dir /path/to/data
python manage.py import_master_plans --data-dir /path/to/data --state karnataka --city bengaluru
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.gis.geos import GEOSGeometry, Polygon, MultiPolygon
from django.utils.text import slugify
from maps.models import (
    State, City, LayerCategory, DataLayer, 
    GeoFeature, LayerGroup, CityLayerStyle
)
from maps.config import DATA_IMPORT_CONFIG, LAYER_CATEGORIES
from maps.services import DataImportService
import json
import os
from pathlib import Path
from datetime import datetime
import traceback

class Command(BaseCommand):
    help = 'Import master plan data following State → City → Layer Group hierarchy'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--data-dir',
            required=True,
            help='Base directory containing state/city/layer_group structure'
        )
        parser.add_argument(
            '--state',
            help='Specific state slug to import (e.g., karnataka)'
        )
        parser.add_argument(
            '--city',
            help='Specific city slug to import (e.g., bengaluru)'
        )
        parser.add_argument(
            '--layer-group',
            default='master-plan',
            help='Layer group slug (default: master-plan)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-import, clearing existing data'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate import without saving'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed progress'
        )
        
    def handle(self, *args, **options):
        data_dir = Path(options['data_dir'])
        
        if not data_dir.exists():
            self.stdout.write(self.style.ERROR(f"❌ Data directory not found: {data_dir}"))
            return
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🚀 MASTER PLAN HIERARCHICAL IMPORT'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Import statistics
        self.stats = {
            'states_created': 0,
            'cities_created': 0,
            'layer_groups_created': 0,
            'layers_created': 0,
            'features_imported': 0,
            'errors': []
        }
        
        try:
            with transaction.atomic():
                # Process states from config
                states_to_process = self._get_states_to_process(options)
                
                for state_slug in states_to_process:
                    self._process_state(
                        state_slug, 
                        data_dir, 
                        options
                    )
                
                if options['dry_run']:
                    self.stdout.write(self.style.WARNING("\n🔄 DRY RUN - Rolling back all changes"))
                    raise Exception("Dry run complete")
                
                # Print summary
                self._print_summary()
                
        except Exception as e:
            if "Dry run complete" not in str(e):
                self.stdout.write(self.style.ERROR(f"\n❌ Import failed: {e}"))
                if options['verbose']:
                    self.stdout.write(traceback.format_exc())
    
    def _get_states_to_process(self, options):
        """Get list of states to process based on options"""
        if options['state']:
            # Specific state requested
            state_slug = options['state']
            if state_slug not in DATA_IMPORT_CONFIG['states']:
                self.stdout.write(self.style.ERROR(f"❌ State '{state_slug}' not found in config"))
                return []
            return [state_slug]
        else:
            # Process all states
            return list(DATA_IMPORT_CONFIG['states'].keys())
    
    def _process_state(self, state_slug, data_dir, options):
        """Process a single state and its cities"""
        state_config = DATA_IMPORT_CONFIG['states'][state_slug]
        
        self.stdout.write(f"\n📦 Processing State: {state_config['name']} ({state_slug})")
        self.stdout.write('-' * 50)
        
        # Create or get state
        state = self._ensure_state(state_slug, state_config)
        
        # Process cities
        cities_to_process = self._get_cities_to_process(state_config, options)
        
        for city_slug in cities_to_process:
            city_config = state_config['cities'][city_slug]
            self._process_city(
                state, 
                city_slug, 
                city_config, 
                data_dir, 
                options
            )
    
    def _get_cities_to_process(self, state_config, options):
        """Get list of cities to process for a state"""
        if options['city']:
            # Specific city requested
            city_slug = options['city']
            if city_slug not in state_config['cities']:
                self.stdout.write(self.style.ERROR(f"  ❌ City '{city_slug}' not found in state"))
                return []
            return [city_slug]
        else:
            # Process all cities in state
            return list(state_config['cities'].keys())
    
    def _process_city(self, state, city_slug, city_config, data_dir, options):
        """Process a single city and its layer groups"""
        
        self.stdout.write(f"\n  🏙️  Processing City: {city_config['name']} ({city_slug})")
        
        # Create or get city
        city = self._ensure_city(state, city_slug, city_config)
        
        # Process layer groups
        layer_group_slug = options['layer_group']
        
        if layer_group_slug not in city_config.get('layer_groups', {}):
            self.stdout.write(self.style.ERROR(f"    ❌ Layer group '{layer_group_slug}' not found"))
            return
        
        layer_group_config = city_config['layer_groups'][layer_group_slug]
        self._process_layer_group(
            city, 
            layer_group_slug, 
            layer_group_config, 
            data_dir, 
            city_config,
            options
        )
    
    def _process_layer_group(self, city, group_slug, group_config, data_dir, city_config, options):
        """Process a layer group and import its files"""
        
        self.stdout.write(f"    📂 Processing Layer Group: {group_config['name']} ({group_slug})")
        
        # Create or get layer group
        layer_group = self._ensure_layer_group(city, group_slug, group_config)
        
        # Clear existing data if force
        if options['force'] and not options['dry_run']:
            self._clear_existing_data(city, layer_group)
        
        # Get data path
        data_path = data_dir / group_config['path']
        
        if not data_path.exists():
            self.stdout.write(self.style.ERROR(f"      ❌ Data path not found: {data_path}"))
            self.stats['errors'].append(f"Path not found: {data_path}")
            return
        
        # Import each file
        files = group_config.get('files', {})
        self.stdout.write(f"      📄 Found {len(files)} files to import")
        
        import_service = DataImportService()
        
        for filename, file_config in files.items():
            file_path = data_path / filename
            
            if not file_path.exists():
                self.stdout.write(self.style.WARNING(f"        ⚠️  File not found: {filename}"))
                self.stats['errors'].append(f"File not found: {filename}")
                continue
            
            try:
                # Import the file
                result = self._import_file(
                    import_service,
                    city,
                    layer_group,
                    file_path,
                    file_config,
                    city_config,
                    options  # Pass options for verbose flag
                )
                
                if result:
                    self.stdout.write(self.style.SUCCESS(
                        f"        ✅ {filename}: {result['features']} features"
                    ))
                    self.stats['layers_created'] += 1
                    self.stats['features_imported'] += result['features']
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"        ❌ {filename}: {e}"))
                self.stats['errors'].append(f"{filename}: {str(e)}")
                if options['verbose']:
                    self.stdout.write(traceback.format_exc())
    
    def _import_file(self, import_service, city, layer_group, file_path, file_config, city_config, options):
        """Import a single file"""
        
        # Create layer slug from filename
        layer_slug = slugify(file_path.stem)
        
        # Check if layer already exists
        if not options['force']:
            existing = DataLayer.objects.filter(
                city=city,
                layer_group=layer_group,
                slug=layer_slug
            ).exists()
            
            if existing:
                if options['verbose']:
                    self.stdout.write(f"          ⏭️  Skipping existing: {layer_slug}")
                return None
        
        # Get or create category
        category = self._ensure_category(file_config.get('category', 'MIXED_USE'))
        
        # Create data layer
        layer = DataLayer.objects.create(
            name=file_config['name'],
            slug=layer_slug,
            city=city,
            layer_group=layer_group,
            category=category,
            description=file_config.get('description', ''),
            source_file=file_path.name,
            data_format=city_config.get('data_format', 'geojson'),
            feature_count=0,
            is_active=True
        )
        
        # Create style configuration
        self._create_layer_style(city, layer, file_config, options.get('verbose', False))
        
        # Import features using the service
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        feature_count = self._import_features_from_data(
            layer,
            data,
            city_config
        )
        
        # Update feature count
        layer.feature_count = feature_count
        layer.is_processed = True  # Mark as processed
        layer.save()
        
        return {'features': feature_count}
    
    def _import_features_from_data(self, layer, data, city_config):
        """Import features from JSON data"""
        
        features_to_create = []
        plu_field = city_config.get('plu_field', 'PLU')
        data_format = city_config.get('data_format', 'geojson')
        
        if data_format == 'esri_json':
            # Handle ESRI JSON format (Bengaluru)
            if 'features' in data:
                for feature in data['features']:
                    geometry_data = feature.get('geometry', {})
                    properties = feature.get('attributes', {})
                    
                    if 'rings' in geometry_data:
                        try:
                            rings = geometry_data['rings']
                            if rings and len(rings) > 0:
                                polygon = Polygon(rings[0])
                                
                                plu_value = properties.get(plu_field, '')
                                
                                features_to_create.append(
                                    GeoFeature(
                                        layer=layer,
                                        geometry=polygon,
                                        properties=properties,
                                        plu_code=str(plu_value)[:50] if plu_value else None
                                    )
                                )
                        except Exception:
                            continue
        
        else:
            # Handle standard GeoJSON format
            if 'features' in data:
                for feature in data['features']:
                    geometry_data = feature.get('geometry', {})
                    properties = feature.get('properties', {})
                    
                    try:
                        if geometry_data.get('type') == 'Polygon':
                            coords = geometry_data.get('coordinates', [])
                            if coords and len(coords) > 0:
                                polygon = Polygon(coords[0])
                                
                                plu_value = properties.get(plu_field, '')
                                
                                features_to_create.append(
                                    GeoFeature(
                                        layer=layer,
                                        geometry=polygon,
                                        properties=properties,
                                        plu_code=str(plu_value)[:50] if plu_value else None
                                    )
                                )
                    except Exception:
                        continue
        
        # Bulk create features
        if features_to_create:
            GeoFeature.objects.bulk_create(features_to_create, batch_size=500)
        
        return len(features_to_create)
    
    def _create_layer_style(self, city, layer, file_config, verbose=False):
        """Create style configuration for a layer"""
        
        color_config = file_config.get('color', '#CCCCCC')
        
        # Check if CityLayerStyle model exists and create appropriately
        try:
            from maps.models import CityLayerStyle
            
            # Delete existing style if any
            CityLayerStyle.objects.filter(city=city, category=layer.category).delete()
            
            if isinstance(color_config, dict):
                # Pattern style
                if 'hatch' in color_config:
                    pattern = 'HATCHED'
                    pattern_color = color_config.get('hatch', '#000000')
                elif 'dot' in color_config:
                    pattern = 'DOTTED'
                    pattern_color = color_config.get('dot', '#000000')
                else:
                    pattern = 'SOLID'
                    pattern_color = None
                
                fill_color = color_config.get('solid', '#CCCCCC')
            else:
                # Solid color
                pattern = 'SOLID'
                fill_color = color_config
                pattern_color = None
            
            CityLayerStyle.objects.create(
                city=city,
                category=layer.category,  # Use category instead of layer
                fill_color=fill_color,
                fill_pattern=pattern,
                pattern_color=pattern_color or fill_color,
                stroke_color=fill_color,
                stroke_width=1,
                fill_opacity=0.7,
                stroke_opacity=1.0
            )
        except Exception as e:
            # If CityLayerStyle doesn't exist or has different fields, skip
            if verbose:
                self.stdout.write(f"        ⚠️ Could not create style: {e}")
    
    def _ensure_state(self, state_slug, state_config):
        """Create or get state"""
        state, created = State.objects.get_or_create(
            slug=state_slug,
            defaults={
                'name': state_config['name'],
                'code': state_config['code'],
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f"  ✅ Created state: {state.name}")
            self.stats['states_created'] += 1
        return state
    
    def _ensure_city(self, state, city_slug, city_config):
        """Create or get city"""
        city, created = City.objects.get_or_create(
            slug=city_slug,
            defaults={
                'name': city_config['name'],
                'state': city_config['name'],  # Legacy field
                'state_ref': state,
                'center_lat': city_config.get('center_lat', 0),
                'center_lng': city_config.get('center_lng', 0),
                'min_zoom': 8,
                'max_zoom': 18,
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f"    ✅ Created city: {city.name}")
            self.stats['cities_created'] += 1
        return city
    
    def _ensure_layer_group(self, city, group_slug, group_config):
        """Create or get layer group"""
        # Create a default category for layer groups
        category = self._ensure_category('MIXED_USE')
        
        # Get directory path from config
        directory_path = group_config.get('path', f"{city.state_ref.slug}/{city.slug}/{group_slug.replace('-', '_')}")
        
        layer_group, created = LayerGroup.objects.get_or_create(
            city=city,
            slug=group_slug,
            defaults={
                'name': group_config['name'],
                'description': group_config.get('description', ''),
                'category': category,  # Required field
                'directory_path': directory_path,  # Required field
                'display_order': group_config.get('display_order', 1),
                'is_visible': True,  # This field exists
                'default_color': '#666666',
                'default_stroke': '#333333',
                'default_opacity': 0.7
            }
        )
        if created:
            self.stdout.write(f"      ✅ Created layer group: {layer_group.name}")
            self.stats['layer_groups_created'] += 1
        return layer_group
    
    def _ensure_category(self, category_code):
        """Create or get layer category"""
        category_info = LAYER_CATEGORIES.get(category_code, {})
        category, _ = LayerCategory.objects.get_or_create(
            code=category_code,
            defaults={
                'name': category_info.get('name', category_code),
                'description': category_info.get('description', ''),
                'default_color': category_info.get('default_color', '#CCCCCC'),
                'default_opacity': category_info.get('default_opacity', 0.8)
            }
        )
        return category
    
    def _clear_existing_data(self, city, layer_group):
        """Clear existing data for a city's layer group"""
        self.stdout.write("      🗑️  Clearing existing data...")
        
        # Delete features
        deleted_features = GeoFeature.objects.filter(
            layer__city=city,
            layer__layer_group=layer_group
        ).delete()
        
        # Delete layers
        deleted_layers = DataLayer.objects.filter(
            city=city,
            layer_group=layer_group
        ).delete()
        
        self.stdout.write(f"        Deleted {deleted_features[0]} features, {deleted_layers[0]} layers")
    
    def _print_summary(self):
        """Print import summary"""
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("📊 IMPORT SUMMARY"))
        self.stdout.write("=" * 70)
        
        self.stdout.write(f"✅ States created: {self.stats['states_created']}")
        self.stdout.write(f"✅ Cities created: {self.stats['cities_created']}")
        self.stdout.write(f"✅ Layer groups created: {self.stats['layer_groups_created']}")
        self.stdout.write(f"✅ Layers created: {self.stats['layers_created']}")
        self.stdout.write(f"✅ Features imported: {self.stats['features_imported']:,}")
        
        if self.stats['errors']:
            self.stdout.write(f"\n⚠️  Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:5]:
                self.stdout.write(f"  - {error}")
            if len(self.stats['errors']) > 5:
                self.stdout.write(f"  ... and {len(self.stats['errors']) - 5} more")