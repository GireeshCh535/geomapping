"""
Django management command to insert Warangal master plan data
This creates ONE layer (warangal_master_plan_2015) with all masterplan files as features
Following the hierarchy: telangana -> warangal -> warangal_master_plan_2015 -> all features
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
    help = 'Insert Warangal master plan data into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Delete existing Warangal masterplan data before inserting new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting Warangal Master Plan Data Insertion')
        )
        
        try:
            with transaction.atomic():
                # Setup basic entities
                self.setup_state_and_city()
                self.setup_layer_categories()
                
                # Delete existing data if requested
                if options['delete_existing']:
                    self.delete_existing_warangal_masterplan_data()
                
                # Create the SINGLE master plan layer
                self.create_master_plan_layer()
                
                # Create styles for all zone types
                self.create_city_layer_styles()
                
                # Process all masterplan files into the single layer
                self.process_all_masterplan_files()
                
                self.stdout.write(
                    self.style.SUCCESS('✅ Warangal Master Plan Data Insertion Completed Successfully!')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error during data insertion: {str(e)}')
            )
            raise CommandError(f'Data insertion failed: {str(e)}')

    def setup_state_and_city(self):
        """Setup Telangana state and Warangal city"""
        self.stdout.write('Setting up Telangana state and Warangal city...')
        
        # Create or get Telangana state
        self.state, created = State.objects.get_or_create(
            slug='telangana',
            defaults={
                'name': 'Telangana',
                'code': 'TS',
                'center_lat': 18.1124,
                'center_lng': 79.0193,
                'default_zoom': 7,
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(f'  ✅ Created state: {self.state.name}')
        else:
            self.stdout.write(f'  ✅ Found existing state: {self.state.name}')
        
        # Create or get Warangal city
        self.city, created = City.objects.get_or_create(
            slug='warangal',
            defaults={
                'name': 'Warangal',
                'state': 'Telangana',  # Legacy field
                'state_ref': self.state,
                'center_lat': 17.9689,
                'center_lng': 79.5941,
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
        """Setup layer categories for Warangal masterplan"""
        self.stdout.write('Setting up layer categories...')
        
        # Define categories for Warangal masterplan
        categories = [
            ('RESIDENTIAL', 'Residential', 'Residential zones and housing areas', '#FFB6C1'),
            ('COMMERCIAL', 'Commercial', 'Commercial and business zones', '#FFD700'),
            ('INDUSTRIAL', 'Industrial', 'Industrial zones and manufacturing areas', '#D2691E'),
            ('MIXED_USE', 'Mixed Use', 'Mixed-use development zones', '#9370DB'),
            ('GOVERNMENT', 'Government', 'Government and administrative zones', '#4169E1'),
            ('PUBLIC', 'Public/Semi-Public', 'Public and semi-public facilities', '#32CD32'),
            ('EDUCATION', 'Education', 'Educational institutions and campuses', '#FF6347'),
            ('HEALTH', 'Health', 'Healthcare facilities and medical zones', '#FF1493'),
            ('DEFENSE', 'Defense', 'Defense and military zones', '#8B0000'),
            ('PROTECTED', 'Protected/Forest', 'Protected areas and forests', '#228B22'),
            ('PARKS_GREEN', 'Parks & Green Spaces', 'Parks, gardens, and green spaces', '#00FF00'),
            ('WATER_BODIES', 'Water Bodies', 'Lakes, rivers, and water bodies', '#00BFFF'),
            ('TRANSPORT', 'Transportation', 'Transportation infrastructure', '#696969'),
            ('UTILITIES', 'Utilities', 'Utility infrastructure and services', '#A9A9A9'),
            ('AGRICULTURAL', 'Agricultural', 'Agricultural land and farming areas', '#90EE90'),
            ('BURIAL', 'Burial/Cemetery', 'Burial grounds and cemeteries', '#2F4F4F'),
            ('RELIGIOUS', 'Religious', 'Religious and cultural sites', '#8B4513'),
            ('HERITAGE', 'Heritage', 'Heritage and cultural areas', '#CD853F'),
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

    def delete_existing_warangal_masterplan_data(self):
        """Delete existing Warangal masterplan data"""
        self.stdout.write('Deleting existing Warangal masterplan data...')
        
        # Delete the masterplan layer and all its features
        deleted_layers = DataLayer.objects.filter(
            city=self.city,
            slug='warangal_master_plan_2015'
        ).delete()
        
        if deleted_layers[0] > 0:
            self.stdout.write(f'  ✅ Deleted {deleted_layers[0]} existing masterplan layers')
        
        # Delete any existing layer groups
        deleted_groups = LayerGroup.objects.filter(
            city=self.city,
            slug='warangal_master_plan_2015'
        ).delete()
        
        if deleted_groups[0] > 0:
            self.stdout.write(f'  ✅ Deleted {deleted_groups[0]} existing layer groups')

    def create_master_plan_layer(self):
        """Create the single masterplan layer"""
        self.stdout.write('Creating Warangal Master Plan 2015 layer...')
        
        # Create layer group
        self.layer_group, created = LayerGroup.objects.get_or_create(
            city=self.city,
            slug='warangal_master_plan_2015',
            defaults={
                'name': 'Warangal Master Plan 2015',
                'description': 'Comprehensive master plan data for Warangal including all land use zones',
                'category': self.categories['MIXED_USE'],
                'directory_path': 'data/Telangana/warangal/master_plan/',
                'default_color': '#9370DB',
                'default_stroke': '#333333',
                'default_opacity': 0.7,
                'display_order': 0,
                'is_visible': True,
                'min_zoom': 8,
                'max_zoom': 18
            }
        )
        
        if created:
            self.stdout.write(f'  ✅ Created layer group: {self.layer_group.name}')
        
        # Create the main data layer
        self.masterplan_layer, created = DataLayer.objects.get_or_create(
            city=self.city,
            slug='warangal_master_plan_2015',
            defaults={
                'name': 'Warangal Master Plan 2015',
                'description': 'Complete master plan data for Warangal with all land use zones and infrastructure',
                'category': self.categories['MIXED_USE'],
                'layer_group': self.layer_group,
                'file_format': 'GEOJSON',
                'is_directory': True,
                'file_pattern': '*.geojson',
                'file_path': 'data/Telangana/warangal/master_plan/',
                'geometry_type': 'POLYGON',
                'categorization_method': 'FILENAME',
                'is_processed': False,
                'feature_count': 0,
                'is_true': True,  # Make it visible by default
                'tiles_generated': False,
                'data_source': 'KUDA (Kakatiya Urban Development Authority)',
            }
        )
        
        if created:
            self.stdout.write(f'  ✅ Created masterplan layer: {self.masterplan_layer.name}')
        else:
            self.stdout.write(f'  ✅ Found existing masterplan layer: {self.masterplan_layer.name}')

    def create_city_layer_styles(self):
        """Create city-specific layer styles for all categories"""
        self.stdout.write('Creating city-specific layer styles...')
        
        # Define specific colors for Warangal masterplan categories
        style_configs = {
            'RESIDENTIAL': {'fill_color': '#FFB6C1', 'pattern': 'SOLID'},
            'COMMERCIAL': {'fill_color': '#FFD700', 'pattern': 'HATCHED'},
            'INDUSTRIAL': {'fill_color': '#D2691E', 'pattern': 'CROSS_HATCHED'},
            'MIXED_USE': {'fill_color': '#9370DB', 'pattern': 'STRIPED'},
            'GOVERNMENT': {'fill_color': '#4169E1', 'pattern': 'SOLID'},
            'PUBLIC': {'fill_color': '#32CD32', 'pattern': 'DOTTED'},
            'EDUCATION': {'fill_color': '#FF6347', 'pattern': 'HATCHED'},
            'HEALTH': {'fill_color': '#FF1493', 'pattern': 'SOLID'},
            'DEFENSE': {'fill_color': '#8B0000', 'pattern': 'CROSS_HATCHED'},
            'PROTECTED': {'fill_color': '#228B22', 'pattern': 'SOLID'},
            'PARKS_GREEN': {'fill_color': '#00FF00', 'pattern': 'DOTTED'},
            'WATER_BODIES': {'fill_color': '#00BFFF', 'pattern': 'SOLID'},
            'TRANSPORT': {'fill_color': '#696969', 'pattern': 'STRIPED'},
            'UTILITIES': {'fill_color': '#A9A9A9', 'pattern': 'HATCHED'},
            'AGRICULTURAL': {'fill_color': '#90EE90', 'pattern': 'DOTTED'},
            'BURIAL': {'fill_color': '#2F4F4F', 'pattern': 'CROSS_HATCHED'},
            'RELIGIOUS': {'fill_color': '#8B4513', 'pattern': 'SOLID'},
            'HERITAGE': {'fill_color': '#CD853F', 'pattern': 'SOLID'},
            'UNCLASSIFIED': {'fill_color': '#CCCCCC', 'pattern': 'SOLID'},
        }
        
        for category_code, config in style_configs.items():
            if category_code in self.categories:
                style, created = CityLayerStyle.objects.get_or_create(
                    city=self.city,
                    category=self.categories[category_code],
                    defaults={
                        'fill_color': config['fill_color'],
                        'stroke_color': '#333333',
                        'opacity': 0.7,
                        'stroke_width': 1,
                        'fill_pattern': config['pattern'],
                        'pattern_color': config['fill_color'],
                        'pattern_spacing': 10,
                        'pattern_angle': 45,
                        'pattern_size': 3,
                        'is_visible': True,
                        'min_zoom': 8,
                        'max_zoom': 18
                    }
                )
                
                if created:
                    self.stdout.write(f'  ✅ Created style for {category_code}')

    def process_all_masterplan_files(self):
        """Process all masterplan GeoJSON files into the single layer"""
        self.stdout.write('Processing all masterplan files...')
        
        masterplan_dir = Path('data/Telangana/warangal/master_plan/')
        geojson_files = list(masterplan_dir.glob('*.geojson'))
        
        self.stdout.write(f'Found {len(geojson_files)} masterplan files to process')
        
        total_features = 0
        processed_files = 0
        error_files = []
        
        for geojson_file in geojson_files:
            try:
                self.stdout.write(f'  Processing: {geojson_file.name}')
                features_added = self.process_masterplan_file(geojson_file)
                total_features += features_added
                processed_files += 1
                self.stdout.write(f'    ✅ Added {features_added} features')
                
            except Exception as e:
                error_files.append((geojson_file.name, str(e)))
                self.stdout.write(f'    ❌ Error processing {geojson_file.name}: {str(e)}')
        
        # Update layer statistics
        self.masterplan_layer.feature_count = total_features
        self.masterplan_layer.is_processed = True
        self.masterplan_layer.save()
        
        # Update layer group statistics
        self.layer_group.save()
        
        self.stdout.write(f'\n📊 Processing Summary:')
        self.stdout.write(f'  ✅ Successfully processed: {processed_files} files')
        self.stdout.write(f'  ❌ Errors: {len(error_files)} files')
        self.stdout.write(f'  📈 Total features added: {total_features:,}')
        
        if error_files:
            self.stdout.write(f'\n❌ Files with errors:')
            for filename, error in error_files:
                self.stdout.write(f'  - {filename}: {error}')

    def process_masterplan_file(self, geojson_file):
        """Process a single masterplan GeoJSON file"""
        with open(geojson_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        features = data.get('features', [])
        if not features:
            return 0
        
        # Determine category based on filename
        category_code = self.get_category_from_filename(geojson_file.stem)
        category = self.categories.get(category_code, self.categories['UNCLASSIFIED'])
        
        features_added = 0
        skipped_none_geometry = 0
        
        for feature_data in features:
            try:
                # Extract geometry
                geometry_data = feature_data.get('geometry')
                if geometry_data is None:
                    skipped_none_geometry += 1
                    continue
                
                # Handle 3D coordinates by converting to 2D
                if geometry_data.get('type') in ['LineString', 'MultiLineString', 'Polygon', 'MultiPolygon']:
                    # Convert 3D coordinates to 2D by removing Z values
                    if geometry_data.get('type') == 'LineString':
                        geometry_data['coordinates'] = [[coord[0], coord[1]] for coord in geometry_data['coordinates']]
                    elif geometry_data.get('type') == 'MultiLineString':
                        geometry_data['coordinates'] = [[[coord[0], coord[1]] for coord in line] for line in geometry_data['coordinates']]
                    elif geometry_data.get('type') == 'Polygon':
                        geometry_data['coordinates'] = [[[coord[0], coord[1]] for coord in ring] for ring in geometry_data['coordinates']]
                    elif geometry_data.get('type') == 'MultiPolygon':
                        geometry_data['coordinates'] = [[[[coord[0], coord[1]] for coord in ring] for ring in poly] for poly in geometry_data['coordinates']]
                
                # Create geometry
                geometry = GEOSGeometry(json.dumps(geometry_data))
                geometry.srid = 4326
                
                # Extract attributes
                attributes = feature_data.get('properties', {})
                if attributes is None:
                    attributes = {}
                
                # Clean properties to ensure JSON serialization
                cleaned_properties = {}
                for key, value in attributes.items():
                    if value is None:
                        cleaned_properties[key] = None
                    elif isinstance(value, (str, int, float, bool)):
                        cleaned_properties[key] = value
                    elif isinstance(value, (list, dict)):
                        try:
                            json.dumps(value)  # Test if it's JSON serializable
                            cleaned_properties[key] = value
                        except (TypeError, ValueError):
                            cleaned_properties[key] = str(value)
                    else:
                        cleaned_properties[key] = str(value)
                
                # Create GeoFeature
                geo_feature = GeoFeature.objects.create(
                    layer=self.masterplan_layer,
                    geometry=geometry,
                    source_layer_name=geojson_file.stem,
                    zone_category=category.name,
                    zone_subcategory=geojson_file.stem,
                    
                    # Warangal-specific fields
                    kuda=attributes.get('KUDA', ''),
                    ex_pr=attributes.get('Ex_PR', ''),
                    
                    # Common fields
                    area=attributes.get('Area') or attributes.get('Shape_Area'),
                    shape_length=attributes.get('Shape_Length'),
                    shape_area=attributes.get('Shape_Area'),
                    objectid=attributes.get('OBJECTID'),
                    fid=attributes.get('fid'),
                    
                    # Store all original properties
                    properties=cleaned_properties,
                    is_valid=True
                )
                
                features_added += 1
                
            except Exception as e:
                self.stdout.write(f'    ⚠️  Error processing feature in {geojson_file.name}: {str(e)}')
                continue
        
        if skipped_none_geometry > 0:
            self.stdout.write(f'    ⚠️ Skipped {skipped_none_geometry} features with None geometry')
        
        return features_added

    def get_category_from_filename(self, filename):
        """Map filename to category code"""
        filename_lower = filename.lower()
        
        if 'residential' in filename_lower:
            return 'RESIDENTIAL'
        elif 'commercial' in filename_lower:
            return 'COMMERCIAL'
        elif 'industrial' in filename_lower:
            return 'INDUSTRIAL'
        elif 'mixed' in filename_lower or 'mixeduse' in filename_lower:
            return 'MIXED_USE'
        elif 'public' in filename_lower:
            return 'PUBLIC'
        elif 'transport' in filename_lower or 'transportation' in filename_lower:
            return 'TRANSPORT'
        elif 'utility' in filename_lower or 'utilities' in filename_lower:
            return 'UTILITIES'
        elif 'recreational' in filename_lower:
            return 'PARKS_GREEN'
        elif 'water' in filename_lower:
            return 'WATER_BODIES'
        elif 'forest' in filename_lower:
            return 'PROTECTED'
        elif 'agriculture' in filename_lower or 'agricultural' in filename_lower:
            return 'AGRICULTURAL'
        elif 'heritage' in filename_lower:
            return 'HERITAGE'
        elif 'railway' in filename_lower:
            return 'TRANSPORT'
        elif 'air' in filename_lower or 'airstrip' in filename_lower:
            return 'TRANSPORT'
        elif 'growth' in filename_lower or 'corridor' in filename_lower:
            return 'DEVELOPMENT'
        elif 'hill' in filename_lower or 'buffer' in filename_lower:
            return 'PROTECTED'
        elif 'zoological' in filename_lower or 'park' in filename_lower:
            return 'PARKS_GREEN'
        else:
            return 'UNCLASSIFIED'
