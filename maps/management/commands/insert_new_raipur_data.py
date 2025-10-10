#!/usr/bin/env python3
"""
Django management command to insert New Raipur master plan data
Creates ONE layer (new_raipur_masterplan) with all masterplan files as features
Following the hierarchy: State (Chhattisgarh) -> City (New Raipur) -> DataLayer -> GeoFeatures from all files
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
    CityLayerStyle, LayerGroup, CityZoneMapping
)


class Command(BaseCommand):
    help = 'Insert New Raipur master plan data into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Delete existing New Raipur masterplan data before inserting new data',
        )
        parser.add_argument(
            '--data-dir',
            type=str,
            default='data/chhatisgarh/new-raipur/new_raipur_masterplan/',
            help='Directory containing the master plan data files',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting New Raipur Master Plan Data Insertion')
        )
        
        self.data_dir = Path(options['data_dir'])
        
        if not self.data_dir.exists():
            raise CommandError(f'Data directory does not exist: {self.data_dir}')
        
        try:
            with transaction.atomic():
                # Setup basic entities
                self.setup_state_and_city()
                self.setup_layer_categories()
                
                # Delete existing data if requested
                if options['delete_existing']:
                    self.delete_existing_new_raipur_masterplan_data()
                
                # Create ONE master plan layer and process all files into it
                self.create_and_populate_master_plan_layer()
                
                # Create city-specific styles
                self.create_city_layer_styles()
                
                # Create zone mappings for better categorization
                self.create_zone_mappings()
                
                # Print summary
                self.print_summary()
                
                self.stdout.write(
                    self.style.SUCCESS('✅ New Raipur Master Plan Data Insertion Completed Successfully!')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error during data insertion: {str(e)}')
            )
            raise CommandError(f'Data insertion failed: {str(e)}')

    def setup_state_and_city(self):
        """Setup Chhattisgarh state and New Raipur city"""
        self.stdout.write('Setting up Chhattisgarh state and New Raipur city...')
        
        # Create or get Chhattisgarh state
        self.state, created = State.objects.get_or_create(
            code='CG',
            defaults={
                'name': 'Chhattisgarh',
                'slug': 'chhattisgarh',
                'center_lat': 21.2787,
                'center_lng': 81.8661,
                'default_zoom': 7,
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(f'  ✅ Created state: {self.state.name}')
        else:
            self.stdout.write(f'  ✅ Found existing state: {self.state.name}')
        
        # Create or get New Raipur city
        self.city, created = City.objects.get_or_create(
            slug='new-raipur',
            defaults={
                'name': 'New Raipur',
                'state': 'Chhattisgarh',
                'state_ref': self.state,
                'center_lat': 21.1574,
                'center_lng': 81.7842,
                'min_zoom': 8,
                'max_zoom': 18,
                'is_active': True
            }
        )
        
        # Update state_ref if city exists but doesn't have it
        if not created and not self.city.state_ref:
            self.city.state_ref = self.state
            self.city.save()
        
        if created:
            self.stdout.write(f'  ✅ Created city: {self.city.name}')
        else:
            self.stdout.write(f'  ✅ Found existing city: {self.city.name}')

    def setup_layer_categories(self):
        """Setup layer categories for New Raipur masterplan"""
        self.stdout.write('Setting up layer categories...')
        
        categories = [
            ('BOUNDARIES', 'Administrative Boundaries', 'City and administrative boundaries', '#800080'),
            ('PLANNING', 'Planning Areas', 'Urban planning and development areas', '#FFE4B5'),
            ('RESIDENTIAL', 'Residential', 'Residential zones and housing areas', '#FFB6C1'),
            ('COMMERCIAL', 'Commercial', 'Commercial and business zones', '#FFD700'),
            ('INDUSTRIAL', 'Industrial', 'Industrial zones and manufacturing areas', '#D2691E'),
            ('MIXED_USE', 'Mixed Use', 'Mixed-use development zones', '#9370DB'),
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
            else:
                self.stdout.write(f'  ✅ Found existing category: {name}')

    def delete_existing_new_raipur_masterplan_data(self):
        """Delete existing New Raipur masterplan data"""
        self.stdout.write('Deleting existing New Raipur masterplan data...')
        
        # Delete the master plan layer and all its features
        deleted_count = 0
        
        # Find and delete THE master plan layer
        try:
            layer = DataLayer.objects.get(
                city=self.city,
                slug='new_raipur_masterplan'
            )
            feature_count = layer.geofeature_set.count()
            layer.delete()
            deleted_count = 1
            self.stdout.write(f'  ✅ Deleted master plan layer with {feature_count} features')
        except DataLayer.DoesNotExist:
            self.stdout.write('  ℹ️ No existing New Raipur masterplan layer found')
        
        # Also delete any layer groups
        LayerGroup.objects.filter(city=self.city, slug='new_raipur_masterplan').delete()

    def create_and_populate_master_plan_layer(self):
        """Create ONE master plan layer and populate it with features from all files"""
        self.stdout.write('\nCreating and populating New Raipur master plan layer...')
        
        # Get all GeoJSON and JSON files in the directory
        geojson_files = list(self.data_dir.glob('*.geojson'))
        json_files = list(self.data_dir.glob('*.json'))
        all_files = geojson_files + json_files
        
        # Also check subdirectories if needed
        geojson_files_recursive = list(self.data_dir.rglob('*.geojson'))
        json_files_recursive = list(self.data_dir.rglob('*.json'))
        
        # Use recursive search if more files found in subdirectories
        if len(geojson_files_recursive + json_files_recursive) > len(all_files):
            all_files = geojson_files_recursive + json_files_recursive
            self.stdout.write(f'  📂 Including files from subdirectories')
        
        if not all_files:
            self.stdout.write(f'  ⚠️ No GeoJSON/JSON files found in {self.data_dir}')
            # Create empty layer structure for consistency
            layer_group, created = LayerGroup.objects.get_or_create(
                city=self.city,
                slug='new_raipur_masterplan',
                defaults={
                    'name': 'New Raipur Master Plan',
                    'description': 'New Raipur Development Authority master plan data',
                    'category': self.categories['PLANNING'],
                    'directory_path': str(self.data_dir),
                    'default_color': '#FFE4B5',
                    'default_stroke': '#FF8C00',
                    'default_opacity': 0.7,
                    'display_order': 0,
                    'is_visible': True,
                    'min_zoom': 8,
                    'max_zoom': 18
                }
            )
            
            self.master_plan_layer, created = DataLayer.objects.get_or_create(
                city=self.city,
                slug='new_raipur_masterplan',
                defaults={
                    'name': 'New Raipur Master Plan',
                    'description': 'Comprehensive New Raipur master plan including all boundaries and land use zones',
                    'category': self.categories['PLANNING'],
                    'layer_group': layer_group,
                    'file_format': 'GEOJSON',
                    'file_path': str(self.data_dir),
                    'is_directory': True,
                    'file_pattern': '*.geojson,*.json',
                    'source_files': [],
                    'geometry_type': 'POLYGON',
                    'categorization_method': 'FILENAME',
                    'is_processed': True,
                    'feature_count': 0,
                    'is_true': True,
                    'data_source': 'New Raipur Development Authority',
                }
            )
            
            # Initialize empty tracking variables
            self.processed_files = []
            self.failed_files = []
            self.total_features_imported = 0
            
            self.stdout.write(f'  ✅ Created empty master plan layer structure')
            return
        
        self.stdout.write(f'📁 Found {len(all_files)} files to process:')
        for f in all_files:
            relative_path = f.relative_to(self.data_dir) if self.data_dir in f.parents else f.name
            self.stdout.write(f'  - {relative_path}')
        
        # Create a layer group for organization
        layer_group, created = LayerGroup.objects.get_or_create(
            city=self.city,
            slug='new_raipur_masterplan',
            defaults={
                'name': 'New Raipur Master Plan',
                'description': 'New Raipur Development Authority master plan data',
                'category': self.categories['PLANNING'],
                'directory_path': str(self.data_dir),
                'default_color': '#FFE4B5',
                'default_stroke': '#FF8C00',
                'default_opacity': 0.7,
                'display_order': 0,
                'is_visible': True,
                'min_zoom': 8,
                'max_zoom': 18
            }
        )
        
        # Collect source file names for the layer
        source_file_names = [f.name for f in all_files]
        
        # Create or update THE SINGLE master plan layer
        self.master_plan_layer, created = DataLayer.objects.get_or_create(
            city=self.city,
            slug='new_raipur_masterplan',
            defaults={
                'name': 'New Raipur Master Plan',
                'description': 'Comprehensive New Raipur master plan including all boundaries and land use zones',
                'category': self.categories['PLANNING'],
                'layer_group': layer_group,
                'file_format': 'GEOJSON',
                'file_path': str(self.data_dir),
                'is_directory': True,  # This layer represents a directory of files
                'file_pattern': '*.geojson,*.json',
                'source_files': source_file_names,  # Store list of all source files
                'geometry_type': 'POLYGON',  # Will be updated based on actual features
                'categorization_method': 'FILENAME',
                'is_processed': False,
                'feature_count': 0,
                'is_true': True,  # Make visible by default
                'data_source': 'New Raipur Development Authority',
            }
        )
        
        if created:
            self.stdout.write(f'  ✅ Created master plan layer: {self.master_plan_layer.name}')
        else:
            self.stdout.write(f'  ✅ Found existing master plan layer: {self.master_plan_layer.name}')
            # Update source files list
            self.master_plan_layer.source_files = source_file_names
            self.master_plan_layer.save()
            
            # Delete existing features before re-importing
            deleted_count = self.master_plan_layer.geofeature_set.all().delete()[0]
            if deleted_count > 0:
                self.stdout.write(f'    Deleted {deleted_count} existing features')
        
        # Track processing statistics
        self.processed_files = []
        self.failed_files = []
        self.total_features_imported = 0
        geometry_types = set()
        
        # Process each file and add features to THE SINGLE layer
        for file_path in all_files:
            try:
                self.stdout.write(f'\n📄 Processing file: {file_path.name}')
                features_count, geom_type = self.process_file_into_layer(file_path)
                
                if geom_type:
                    geometry_types.add(geom_type)
                
                self.processed_files.append((file_path.name, features_count))
                self.total_features_imported += features_count
                
            except Exception as e:
                self.failed_files.append((file_path.name, str(e)))
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Error processing {file_path.name}: {str(e)}')
                )
                continue
        
        # Update layer statistics
        self.master_plan_layer.feature_count = self.total_features_imported
        self.master_plan_layer.is_processed = True
        
        # Set geometry type based on most common type found
        if geometry_types:
            # Prefer POLYGON/MULTIPOLYGON if present
            if 'MULTIPOLYGON' in geometry_types:
                self.master_plan_layer.geometry_type = 'MULTIPOLYGON'
            elif 'POLYGON' in geometry_types:
                self.master_plan_layer.geometry_type = 'POLYGON'
            else:
                self.master_plan_layer.geometry_type = list(geometry_types)[0]
        
        # Calculate bounding box
        bbox = self.calculate_layer_bbox(self.master_plan_layer)
        if bbox:
            self.stdout.write(f'\n  📍 Layer bounding box: {bbox}')
        
        self.master_plan_layer.save()
        
        self.stdout.write(f'\n✅ Master plan layer populated with {self.total_features_imported:,} features from {len(self.processed_files)} files')

    def process_file_into_layer(self, file_path):
        """Process a single file and add its features to the master plan layer"""
        
        # Read the file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.stdout.write(f'  ❌ Invalid JSON in {file_path.name}: {str(e)}')
            return 0, None
        except Exception as e:
            self.stdout.write(f'  ❌ Error reading {file_path.name}: {str(e)}')
            return 0, None
        
        features = data.get('features', [])
        if not features:
            self.stdout.write(f'  ⚠️ No features found in {file_path.name}')
            return 0, None
        
        # Determine category based on filename
        category = self.determine_category_from_filename(file_path.stem)
        
        # Get geometry type from first feature
        first_geom_type = self.get_geometry_type(features[0])
        
        features_added = 0
        
        for idx, feature_data in enumerate(features, 1):
            try:
                # Extract geometry
                geometry_data = feature_data.get('geometry')
                if not geometry_data:
                    continue
                
                # Convert to GEOSGeometry
                geometry = GEOSGeometry(json.dumps(geometry_data))
                
                # Handle 3D geometries by converting to 2D
                if geometry.hasz:
                    geometry = self.flatten_geometry(geometry)
                
                # Validate geometry
                if not geometry.valid:
                    geometry = geometry.buffer(0)
                    if not geometry.valid:
                        self.stdout.write(f'    ⚠️ Invalid geometry at feature {idx}, skipping')
                        continue
                
                # Extract properties
                properties = feature_data.get('properties', {})
                
                # Create GeoFeature
                geo_feature = GeoFeature.objects.create(
                    layer=self.master_plan_layer,
                    geometry=geometry,
                    name=self.extract_feature_name(properties, file_path.stem, idx),
                    source_layer_name=file_path.stem,  # Store which file this came from
                    zone_category=category.name,
                    zone_subcategory=file_path.stem,  # Use filename as subcategory
                    
                    # Store numeric fields
                    area=self.safe_float(properties.get('Area')),
                    shape_length=self.safe_float(properties.get('Shape_Length')),
                    shape_area=self.safe_float(properties.get('Shape_Area')),
                    objectid=self.safe_int(properties.get('OBJECTID', idx)),
                    fid=self.safe_int(properties.get('FID', idx)),
                    
                    # Store all properties
                    properties=properties,
                    is_valid=True
                )
                
                features_added += 1
                
            except Exception as e:
                self.stdout.write(f'    ⚠️ Error processing feature {idx}: {str(e)}')
                continue
        
        self.stdout.write(f'  ✅ Added {features_added} features from {file_path.name}')
        return features_added, first_geom_type

    def determine_category_from_filename(self, filename):
        """Determine the appropriate category based on filename"""
        filename_lower = filename.lower()
        
        if any(term in filename_lower for term in ['boundary', 'boundaries', 'cma_boundary', 'city_boundary']):
            return self.categories['BOUNDARIES']
        elif any(term in filename_lower for term in ['residential', 'housing']):
            return self.categories.get('RESIDENTIAL', self.categories['PLANNING'])
        elif any(term in filename_lower for term in ['commercial', 'business']):
            return self.categories.get('COMMERCIAL', self.categories['PLANNING'])
        elif any(term in filename_lower for term in ['industrial']):
            return self.categories.get('INDUSTRIAL', self.categories['PLANNING'])
        elif any(term in filename_lower for term in ['mixed']):
            return self.categories.get('MIXED_USE', self.categories['PLANNING'])
        else:
            return self.categories['PLANNING']

    def get_geometry_type(self, feature):
        """Determine geometry type from a feature"""
        geometry = feature.get('geometry', {})
        geom_type = geometry.get('type', '').upper()
        
        # Map GeoJSON types to model choices
        type_mapping = {
            'POLYGON': 'POLYGON',
            'MULTIPOLYGON': 'MULTIPOLYGON',
            'POINT': 'POINT',
            'MULTIPOINT': 'POINT',
            'LINESTRING': 'LINESTRING',
            'MULTILINESTRING': 'MULTILINESTRING',
        }
        
        return type_mapping.get(geom_type, 'POLYGON')

    def flatten_geometry(self, geometry):
        """Convert 3D geometry to 2D"""
        geom_dict = json.loads(geometry.geojson)
        
        def remove_z_from_coords(coords):
            """Recursively remove Z coordinates"""
            if isinstance(coords[0], (int, float)):
                return coords[:2]
            else:
                return [remove_z_from_coords(coord) for coord in coords]
        
        if 'coordinates' in geom_dict:
            geom_dict['coordinates'] = remove_z_from_coords(geom_dict['coordinates'])
        
        return GEOSGeometry(json.dumps(geom_dict))

    def extract_feature_name(self, properties, source_name, index):
        """Extract a meaningful name for the feature"""
        # Try various common name fields
        name_fields = ['Name', 'name', 'NAME', 'City_Name', 'Zone_Name', 
                      'Area_Name', 'Title', 'Label', 'Description']
        
        for field in name_fields:
            if field in properties and properties[field]:
                return str(properties[field])
        
        # Fallback to source name with index
        return f"{source_name} - Feature {index}"

    def safe_float(self, value):
        """Safely convert value to float"""
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def safe_int(self, value):
        """Safely convert value to integer"""
        if value is None or value == '':
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def calculate_layer_bbox(self, layer):
        """Calculate bounding box for a layer from its features"""
        try:
            from django.contrib.gis.db.models import Extent
            
            extent = layer.geofeature_set.aggregate(
                extent=Extent('geometry')
            )['extent']
            
            if extent:
                layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax = extent
                layer.save(update_fields=['bbox_xmin', 'bbox_ymin', 'bbox_xmax', 'bbox_ymax'])
                return extent
        except Exception as e:
            self.stdout.write(f'    ⚠️ Could not calculate bbox: {str(e)}')
        return None

    def create_city_layer_styles(self):
        """Create city-specific layer styles for New Raipur"""
        self.stdout.write('\nCreating city-specific layer styles...')
        
        style_configs = {
            'BOUNDARIES': {
                'fill_color': '#800080',
                'stroke_color': '#4B0082',
                'opacity': 0.3,
                'stroke_width': 2,
                'fill_pattern': 'SOLID'
            },
            'PLANNING': {
                'fill_color': '#FFE4B5',
                'stroke_color': '#FF8C00',
                'opacity': 0.5,
                'stroke_width': 1,
                'fill_pattern': 'SOLID'
            },
            'RESIDENTIAL': {
                'fill_color': '#FFB6C1',
                'stroke_color': '#FF69B4',
                'opacity': 0.6,
                'stroke_width': 1,
                'fill_pattern': 'SOLID'
            },
            'COMMERCIAL': {
                'fill_color': '#FFD700',
                'stroke_color': '#FFA500',
                'opacity': 0.6,
                'stroke_width': 1,
                'fill_pattern': 'HATCHED'
            },
            'INDUSTRIAL': {
                'fill_color': '#D2691E',
                'stroke_color': '#8B4513',
                'opacity': 0.6,
                'stroke_width': 1,
                'fill_pattern': 'CROSS_HATCHED'
            },
            'MIXED_USE': {
                'fill_color': '#9370DB',
                'stroke_color': '#6B46C1',
                'opacity': 0.6,
                'stroke_width': 1,
                'fill_pattern': 'STRIPED'
            },
            'UNCLASSIFIED': {
                'fill_color': '#CCCCCC',
                'stroke_color': '#666666',
                'opacity': 0.5,
                'stroke_width': 1,
                'fill_pattern': 'SOLID'
            },
        }
        
        for category_code, config in style_configs.items():
            if category_code in self.categories:
                style, created = CityLayerStyle.objects.update_or_create(
                    city=self.city,
                    category=self.categories[category_code],
                    defaults={
                        'fill_color': config['fill_color'],
                        'stroke_color': config['stroke_color'],
                        'opacity': config['opacity'],
                        'stroke_width': config['stroke_width'],
                        'fill_pattern': config['fill_pattern'],
                        'is_visible': True,
                        'min_zoom': 8,
                        'max_zoom': 18
                    }
                )
                
                if created:
                    self.stdout.write(f'  ✅ Created style for {category_code}')
                else:
                    self.stdout.write(f'  ✅ Updated style for {category_code}')

    def create_zone_mappings(self):
        """Create zone mappings for New Raipur"""
        self.stdout.write('\nCreating zone mappings...')
        
        # Check if master_plan_layer exists and has features
        if not hasattr(self, 'master_plan_layer') or not self.master_plan_layer:
            self.stdout.write('  ℹ️ No master plan layer found, skipping zone mappings')
            return
        
        # Get unique source_layer_names (filenames) from features
        source_layers = self.master_plan_layer.geofeature_set.values_list(
            'source_layer_name', flat=True
        ).distinct()
        
        if not source_layers:
            self.stdout.write('  ℹ️ No features found, skipping zone mappings')
            return
        
        for source_layer in source_layers:
            if not source_layer:
                continue
            
            # Determine category based on source layer name
            category = self.determine_category_from_filename(source_layer)
            
            # Get the style for this category
            try:
                style = CityLayerStyle.objects.get(city=self.city, category=category)
            except CityLayerStyle.DoesNotExist:
                # Create a default style if it doesn't exist
                style = CityLayerStyle.objects.create(
                    city=self.city,
                    category=category,
                    fill_color=category.default_color,
                    stroke_color=category.default_stroke,
                    opacity=category.default_opacity
                )
            
            # Get feature count for this source
            feature_count = self.master_plan_layer.geofeature_set.filter(
                source_layer_name=source_layer
            ).count()
            
            # Create zone mapping
            zone_mapping, created = CityZoneMapping.objects.update_or_create(
                city=self.city,
                zone_name=source_layer,
                defaults={
                    'category': category,
                    'style': style,
                    'feature_count': feature_count,
                    'is_active': True
                }
            )
            
            if created:
                self.stdout.write(f'  ✅ Created zone mapping for "{source_layer}" ({feature_count} features)')
            else:
                self.stdout.write(f'  ✅ Updated zone mapping for "{source_layer}" ({feature_count} features)')

    def print_summary(self):
        """Print a detailed summary of the imported data"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('📊 IMPORT SUMMARY'))
        self.stdout.write('='*60)
        
        # State and City info
        self.stdout.write(f'\n📍 Location:')
        self.stdout.write(f'  State: {self.state.name} ({self.state.code})')
        self.stdout.write(f'  City: {self.city.name}')
        
        # Files processed
        if hasattr(self, 'processed_files'):
            self.stdout.write(f'\n📁 Files Processed:')
            self.stdout.write(f'  Successfully processed: {len(self.processed_files)}')
            self.stdout.write(f'  Failed: {len(self.failed_files) if hasattr(self, "failed_files") else 0}')
            
            if self.processed_files:
                self.stdout.write(f'\n  Details:')
                for filename, features_count in self.processed_files:
                    self.stdout.write(f'    • {filename}: {features_count:,} features')
            
            if hasattr(self, 'failed_files') and self.failed_files:
                self.stdout.write(f'\n  Failed files:')
                for filename, error in self.failed_files:
                    self.stdout.write(f'    • {filename}: {error}')
        
        # Layer info
        self.stdout.write(f'\n📂 Master Plan Layer:')
        if hasattr(self, 'master_plan_layer'):
            self.stdout.write(f'  Name: {self.master_plan_layer.name}')
            self.stdout.write(f'  Total features: {self.master_plan_layer.feature_count:,}')
            self.stdout.write(f'  Geometry type: {self.master_plan_layer.geometry_type}')
            self.stdout.write(f'  Is directory: {self.master_plan_layer.is_directory}')
            if self.master_plan_layer.source_files:
                self.stdout.write(f'  Source files: {len(self.master_plan_layer.source_files)}')
        
        # Feature breakdown by source file
        if hasattr(self, 'master_plan_layer') and self.master_plan_layer:
            from django.db.models import Count
            source_stats = self.master_plan_layer.geofeature_set.values(
                'source_layer_name'
            ).annotate(
                count=Count('id')
            ).order_by('source_layer_name')
            
            if source_stats:
                self.stdout.write(f'\n🗺️ Features by Source File:')
                for stat in source_stats:
                    self.stdout.write(f'  • {stat["source_layer_name"]}: {stat["count"]:,} features')
            else:
                self.stdout.write(f'\n🗺️ Features by Source File:')
                self.stdout.write(f'  • No features found in any source files')
        
        # Zone mappings
        zone_mappings = CityZoneMapping.objects.filter(city=self.city)
        if zone_mappings.exists():
            self.stdout.write(f'\n🏷️ Zone Mappings Created: {zone_mappings.count()}')
        
        self.stdout.write('\n' + '='*60)
