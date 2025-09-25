"""
Django management command to insert BMRDA (Bengaluru Metropolitan Region Development Authority) data
This creates separate layers for each planning area:
- Anekal_Boundary.geojson -> bengaluru_anekal_masterplan
- ChikkaballapuraPlanningAreaBoundary.geojson -> bengaluru_chikkaballapura_masterplan  
- HosakoteBoundary.geojson -> bengaluru_hosakote_masterplan
- Nelamangala_SompuraBoundary.geojson -> bengaluru_nelamangala_masterplan
Following the hierarchy: karnataka -> bengaluru -> [individual_planning_area_layers] -> features
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.gis.geos import GEOSGeometry
from django.utils.text import slugify
from pathlib import Path
import json
import glob
import os

from maps.models import (
    State, City, LayerCategory, DataLayer, GeoFeature, 
    CityLayerStyle, LayerGroup
)


class Command(BaseCommand):
    help = 'Insert BMRDA planning area boundary data into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Delete existing BMRDA data before inserting new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting BMRDA Planning Area Data Insertion')
        )
        
        try:
            with transaction.atomic():
                # Setup basic entities
                self.setup_state_and_city()
                self.setup_layer_categories()
                
                # Delete existing data if requested
                if options['delete_existing']:
                    self.delete_existing_bmrda_data()
                
                # Define layer configurations for each planning area
                self.layer_configs = self.get_layer_configurations()
                
                # Create all individual BMRDA layers
                self.create_all_bmrda_layers()
                
                # Create styles for all planning areas
                self.create_city_layer_styles()
                
                # Process all BMRDA boundary files into their respective layers
                self.process_all_bmrda_files()
                
                self.stdout.write(
                    self.style.SUCCESS('✅ BMRDA Planning Area Data Insertion Completed Successfully!')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error during data insertion: {str(e)}')
            )
            raise CommandError(f'Data insertion failed: {str(e)}')

    def setup_state_and_city(self):
        """Setup Karnataka state and Bengaluru city"""
        self.stdout.write('Setting up Karnataka state and Bengaluru city...')
        
        # Create or get Karnataka state
        self.state, created = State.objects.get_or_create(
            slug='karnataka',
            defaults={
                'name': 'Karnataka',
                'code': 'KA',
                'center_lat': 15.3173,
                'center_lng': 75.7139,
                'default_zoom': 7,
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(f'  ✅ Created state: {self.state.name}')
        else:
            self.stdout.write(f'  ✅ Found existing state: {self.state.name}')
        
        # Create or get Bengaluru city
        self.city, created = City.objects.get_or_create(
            slug='bengaluru',
            defaults={
                'name': 'Bengaluru',
                'state': 'Karnataka',  # Legacy field
                'state_ref': self.state,
                'center_lat': 12.9716,
                'center_lng': 77.5946,
                'min_zoom': 8,
                'max_zoom': 18,
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(f'  ✅ Created city: {self.city.name}')
        else:
            self.stdout.write(f'  ✅ Found existing city: {self.city.name}')

    def setup_layer_categories(self):
        """Setup layer categories for BMRDA planning areas"""
        self.stdout.write('Setting up layer categories...')
        
        # Define categories for BMRDA planning areas
        categories = [
            ('PLANNING_AREA', 'Planning Area', 'Urban planning and development zones', '#FF6B35'),
            ('BOUNDARY', 'Boundary', 'Administrative and planning boundaries', '#4ECDC4'),
            ('GOVERNMENT', 'Government', 'Government and administrative zones', '#45B7D1'),
            ('UNCLASSIFIED', 'Unclassified', 'Unclassified or miscellaneous areas', '#CCCCCC'),
        ]
        
        self.categories = {}
        for code, name, description, color in categories:
            category, created = LayerCategory.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'description': description,
                    'default_color': color,
                    'default_stroke': '#333333',
                    'default_opacity': 0.7,
                    'display_order': 0,
                    'is_active': True
                }
            )
            self.categories[code] = category
            
            if created:
                self.stdout.write(f'  ✅ Created category: {name}')

    def get_layer_configurations(self):
        """Define configurations for each BMRDA planning area layer"""
        return {
            'bengaluru_anekal_masterplan': {
                'name': 'Anekal Masterplan',
                'description': 'Anekal planning area boundary',
                'category': 'PLANNING_AREA',
                'file_path': 'data/karnataka/BMRDA/Anekal_Boundary.geojson',
                'color': '#FF6B35',
                'stroke': '#E53E3E',
                'stroke_width': 2
            },
            'bengaluru_chikkaballapura_masterplan': {
                'name': 'Chikkaballapura Masterplan',
                'description': 'Chikkaballapura planning area boundary',
                'category': 'PLANNING_AREA',
                'file_path': 'data/karnataka/BMRDA/ChikkaballapuraPlanningAreaBoundary.geojson',
                'color': '#4ECDC4',
                'stroke': '#38B2AC',
                'stroke_width': 2
            },
            'bengaluru_hosakote_masterplan': {
                'name': 'Hosakote Masterplan',
                'description': 'Hosakote planning area boundary',
                'category': 'PLANNING_AREA',
                'file_path': 'data/karnataka/BMRDA/HosakoteBoundary.geojson',
                'color': '#45B7D1',
                'stroke': '#3182CE',
                'stroke_width': 2
            },
            'bengaluru_nelamangala_masterplan': {
                'name': 'Nelamangala Masterplan',
                'description': 'Nelamangala Sompura planning area boundary',
                'category': 'PLANNING_AREA',
                'file_path': 'data/karnataka/BMRDA/Nelamangala_SompuraBoundary.geojson',
                'color': '#96CEB4',
                'stroke': '#68D391',
                'stroke_width': 2
            }
        }

    def delete_existing_bmrda_data(self):
        """Delete existing BMRDA data"""
        self.stdout.write('Deleting existing BMRDA data...')
        
        # Define the layer slugs to delete
        layer_slugs = [
            'bengaluru_anekal_masterplan',
            'bengaluru_chikkaballapura_masterplan', 
            'bengaluru_hosakote_masterplan',
            'bengaluru_nelamangala_masterplan'
        ]
        
        # Delete features first (due to foreign key constraints)
        features_deleted = GeoFeature.objects.filter(
            layer__city=self.city,
            layer__slug__in=layer_slugs
        ).count()
        GeoFeature.objects.filter(
            layer__city=self.city,
            layer__slug__in=layer_slugs
        ).delete()
        self.stdout.write(f"  🗑️ Deleted {features_deleted} features")
        
        # Delete layers
        layers_deleted = DataLayer.objects.filter(
            city=self.city,
            slug__in=layer_slugs
        ).count()
        DataLayer.objects.filter(
            city=self.city,
            slug__in=layer_slugs
        ).delete()
        self.stdout.write(f"  🗑️ Deleted {layers_deleted} layers")
        
        # Delete any existing layer groups
        deleted_groups = LayerGroup.objects.filter(
            city=self.city,
            slug__in=layer_slugs
        ).count()
        LayerGroup.objects.filter(
            city=self.city,
            slug__in=layer_slugs
        ).delete()
        self.stdout.write(f"  🗑️ Deleted {deleted_groups} layer groups")

    def create_all_bmrda_layers(self):
        """Create all individual BMRDA planning area layers"""
        self.stdout.write('Creating all BMRDA planning area layers...')
        
        self.layers = {}
        created_count = 0
        
        for layer_slug, config in self.layer_configs.items():
            # Get category
            category = self.categories[config['category']]
            
            # Check if file exists
            file_path = Path(config['file_path'])
            if not file_path.exists():
                self.stdout.write(f"  ⚠️ Data file not found: {file_path}")
                continue
            
            # Create layer
            layer, created = DataLayer.objects.get_or_create(
                city=self.city,
                slug=layer_slug,
                defaults={
                    'name': config['name'],
                    'description': config['description'],
                    'category': category,
                    'file_format': 'GEOJSON',
                    'file_path': str(file_path),
                    'is_directory': False,
                    'source_files': [str(file_path)],
                    'categorization_method': 'FILENAME',
                    'geometry_type': 'POLYGON',
                    'is_processed': False,
                    'feature_count': 0,
                    'is_true': True,  # Make it visible by default
                    'data_source': 'Bengaluru Metropolitan Region Development Authority (BMRDA)',
                }
            )
            
            self.layers[layer_slug] = layer
            
            if created:
                created_count += 1
                self.stdout.write(f"  ✅ Created layer: {layer.name}")
            else:
                self.stdout.write(f"  📍 Found existing layer: {layer.name}")
        
        self.stdout.write(f"  📊 Created {created_count} new layers")

    def create_city_layer_styles(self):
        """Create city-specific layer styles for all BMRDA planning areas"""
        self.stdout.write('Creating city-specific layer styles...')
        
        created_count = 0
        
        for layer_slug, config in self.layer_configs.items():
            try:
                category = self.categories[config['category']]
                
                # Create style
                style, created = CityLayerStyle.objects.get_or_create(
                    city=self.city,
                    category=category,
                    defaults={
                        'fill_color': config['color'],
                        'stroke_color': config['stroke'],
                        'opacity': 0.8,
                        'stroke_width': config['stroke_width'],
                        'fill_pattern': 'SOLID',
                        'pattern_color': '',
                        'pattern_spacing': 8,
                        'pattern_angle': 45,
                        'pattern_size': 1,
                        'secondary_fill_color': '',
                        'is_visible': True
                    }
                )
                if created:
                    created_count += 1
                    self.stdout.write(f'  ✅ Created style for {config["name"]} → {category.name}')
            except Exception as e:
                self.stdout.write(f'  ⚠️ Error creating style for {config["name"]}: {e}')
        
        self.stdout.write(f'  📊 Created {created_count} new layer styles')

    def process_all_bmrda_files(self):
        """Process all BMRDA GeoJSON files into their respective layers"""
        self.stdout.write('Processing all BMRDA boundary files...')
        
        total_features = 0
        processed_files = 0
        error_files = []
        
        for layer_slug, layer in self.layers.items():
            config = self.layer_configs[layer_slug]
            file_path = Path(config['file_path'])
            
            if not file_path.exists():
                self.stdout.write(f"  ⚠️ Data file not found: {file_path}")
                continue
            
            try:
                self.stdout.write(f'  Processing: {file_path.name}')
                features_added = self.process_bmrda_file(file_path, layer, layer_slug)
                total_features += features_added
                processed_files += 1
                self.stdout.write(f'    ✅ Added {features_added} features')
                
                # Update layer statistics
                layer.feature_count = features_added
                layer.is_processed = True
                layer.save()
                
            except Exception as e:
                error_files.append((file_path.name, str(e)))
                self.stdout.write(f'    ❌ Error processing {file_path.name}: {str(e)}')
        
        self.stdout.write(f'\n📊 Processing Summary:')
        self.stdout.write(f'  ✅ Successfully processed: {processed_files} files')
        self.stdout.write(f'  ❌ Errors: {len(error_files)} files')
        self.stdout.write(f'  📈 Total features added: {total_features:,}')
        
        if error_files:
            self.stdout.write(f'\n❌ Files with errors:')
            for filename, error in error_files:
                self.stdout.write(f'  - {filename}: {error}')

    def process_bmrda_file(self, geojson_file, layer, layer_slug):
        """Process a single BMRDA GeoJSON file into its specific layer"""
        with open(geojson_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        features = data.get('features', [])
        if not features:
            return 0
        
        # Get configuration for this layer
        config = self.layer_configs[layer_slug]
        category = self.categories[config['category']]
        
        # Get planning area name from configuration
        planning_area_name = config['name']
        
        features_added = 0
        
        for feature_data in features:
            try:
                # Extract geometry
                geometry_data = feature_data.get('geometry')
                if not geometry_data:
                    continue
                
                # Convert to GEOS geometry
                geometry = GEOSGeometry(json.dumps(geometry_data))
                geometry.srid = 4326  # BMRDA data is in WGS84
                
                # Extract attributes
                attributes = feature_data.get('properties', {})
                
                # Create GeoFeature
                geo_feature = GeoFeature.objects.create(
                    layer=layer,
                    geometry=geometry,
                    source_layer_name=geojson_file.stem,
                    zone_category=category.name,
                    zone_subcategory=planning_area_name,
                    
                    # BMRDA-specific fields
                    name=planning_area_name,
                    area=geometry.area if hasattr(geometry, 'area') else None,
                    shape_area=geometry.area if hasattr(geometry, 'area') else None,
                    objectid=attributes.get('id') or attributes.get('FID'),
                    
                    # Store all original properties
                    properties=attributes,
                    is_valid=True
                )
                
                features_added += 1
                
            except Exception as e:
                self.stdout.write(f'    ⚠️  Error processing feature in {geojson_file.name}: {str(e)}')
                continue
        
        return features_added

