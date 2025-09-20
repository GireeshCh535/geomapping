"""
Django management command to insert Bengaluru infrastructure data
This creates separate layers for: highways, metro, STRR, and workspace
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
    help = 'Insert Bengaluru infrastructure data for highways, metro, STRR, and workspace'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Delete existing Bengaluru infrastructure data before inserting new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting Bengaluru Infrastructure Data Insertion')
        )
        
        try:
            with transaction.atomic():
                # Setup basic entities
                self.setup_state_and_city()
                self.setup_layer_categories()
                
                # Delete existing data if requested
                if options['delete_existing']:
                    self.delete_existing_bengaluru_infrastructure_data()
                
                # Define layer configurations
                self.layer_configs = self.get_layer_configurations()
                
                # Create all layers
                self.create_all_layers()
                
                # Create styles for all layer types
                self.create_city_layer_styles()
                
                # Process all files into their respective layers
                self.process_all_files_into_layers()
                
                # Calculate bounds for all layers
                self.calculate_all_layer_bounds()
            
            self.stdout.write(
                self.style.SUCCESS('\n✅ BENGALURU INFRASTRUCTURE DATA INSERTION COMPLETED SUCCESSFULLY!')
            )
            
            # Print summary
            total_layers = DataLayer.objects.filter(city=self.city).count()
            total_features = GeoFeature.objects.filter(layer__city=self.city).count()
            total_styles = CityLayerStyle.objects.filter(city=self.city).count()
            
            self.stdout.write(f"📊 Summary:")
            self.stdout.write(f"   • Layers created: {total_layers}")
            self.stdout.write(f"   • Features inserted: {total_features}")
            self.stdout.write(f"   • Styles created: {total_styles}")
            self.stdout.write(f"   • City: {self.city.name}")
            self.stdout.write(f"   • State: {self.state.name}")
            
        except Exception as e:
            raise CommandError(f'Error inserting data: {e}')

    def setup_state_and_city(self):
        """Create or update State and City records"""
        self.stdout.write("🏛️ Setting up State and City...")
        
        # Create/update State
        self.state, created = State.objects.get_or_create(
            code='KA',
            defaults={
                'name': 'Karnataka',
                'slug': 'karnataka',
                'center_lat': 15.3173,
                'center_lng': 75.7139,
                'default_zoom': 7
            }
        )
        if created:
            self.stdout.write(f"  ✅ Created state: {self.state.name}")
        else:
            self.stdout.write(f"  📍 Found existing state: {self.state.name}")
        
        # Create/update City
        self.city, created = City.objects.get_or_create(
            slug='bengaluru',
            defaults={
                'name': 'Bengaluru',
                'state': 'Karnataka',
                'state_ref': self.state,
                'center_lat': 12.9716,
                'center_lng': 77.5946,
                'min_zoom': 8,
                'max_zoom': 18
            }
        )
        if created:
            self.stdout.write(f"  ✅ Created city: {self.city.name}")
        else:
            self.stdout.write(f"  📍 Found existing city: {self.city.name}")

    def setup_layer_categories(self):
        """Create layer categories if they don't exist"""
        self.stdout.write("📂 Setting up layer categories...")
        
        categories_to_create = [
            ('TRANSPORT', 'Transportation', 'Transportation infrastructure'),
            ('INDUSTRIAL', 'Industrial', 'Industrial zones and manufacturing'),
            ('UNCLASSIFIED', 'Unclassified', 'Unclassified or miscellaneous areas'),
        ]
        
        created_count = 0
        for code, name, description in categories_to_create:
            category, created = LayerCategory.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'description': description,
                    'default_color': '#CCCCCC',
                    'default_stroke': '#333333',
                    'default_opacity': 0.7
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f"  ✅ Created category: {name}")
        
        self.stdout.write(f"  📊 Created {created_count} new categories")

    def get_layer_configurations(self):
        """Define configurations for each layer type"""
        return {
            'bengaluru_highways': {
                'name': 'Highways',
                'description': 'National Highways and major roads in Bengaluru',
                'category': 'TRANSPORT',
                'data_path': 'data/karnataka/bengaluru/highways',
                'file_pattern': '*.geojson',
                'geometry_type': 'MULTILINESTRING',
                'color': '#FF6B6B',
                'stroke': '#E53E3E',
                'stroke_width': 3
            },
            'bengaluru_metro': {
                'name': 'Metro lines',
                'description': 'Bangalore Metro lines - Phases 1, 2, 2A & 2B',
                'category': 'TRANSPORT',
                'data_path': 'data/karnataka/bengaluru/metro',
                'file_pattern': '*.geojson',
                'geometry_type': 'MULTILINESTRING',
                'color': '#3182CE',
                'stroke': '#2C5282',
                'stroke_width': 4
            },
            'bengaluru_strr': {
                'name': 'STRR',
                'description': 'Satellite Town Ring Road',
                'category': 'TRANSPORT',
                'data_path': 'data/karnataka/bengaluru/strr',
                'file_pattern': '*.geojson',
                'geometry_type': 'MULTILINESTRING',
                'color': '#38A169',
                'stroke': '#2F855A',
                'stroke_width': 3
            },
            'bengaluru_workspaces': {
                'name': 'Workspaces',
                'description': 'Industrial areas and workspaces in Bengaluru',
                'category': 'INDUSTRIAL',
                'data_path': 'data/karnataka/bengaluru/workspace',
                'file_pattern': '*.geojson',
                'geometry_type': 'MULTIPOLYGON',
                'color': '#D69E2E',
                'stroke': '#B7791F',
                'stroke_width': 2
            }
        }

    def delete_existing_bengaluru_infrastructure_data(self):
        """Delete existing Bengaluru infrastructure data to start fresh"""
        self.stdout.write("🗑️ Deleting existing Bengaluru infrastructure data...")
        
        # Define the layer slugs to delete (including any old/duplicate slugs)
        layer_slugs = [
            'bengaluru_highways', 
            'bengaluru_strr', 
            'bengaluru_workspaces',
            # Include any old/duplicate layer slugs that might exist
            'bengaluru_metro',  # Old metro layer slug
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

    def create_all_layers(self):
        """Create all layer records"""
        self.stdout.write("📁 Creating all layers...")
        
        self.layers = {}
        created_count = 0
        
        for layer_slug, config in self.layer_configs.items():
            # Get category
            category = LayerCategory.objects.get(code=config['category'])
            
            # Get data directory
            data_dir = Path(config['data_path'])
            if not data_dir.exists():
                self.stdout.write(f"  ⚠️ Data directory not found: {data_dir}")
                continue
            
            # Get source files
            source_files = list(data_dir.glob(config['file_pattern']))
            
            if not source_files:
                self.stdout.write(f"  ⚠️ No files found for pattern: {config['file_pattern']}")
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
                    'file_path': str(data_dir),
                    'is_directory': True,
                    'file_pattern': config['file_pattern'],
                    'source_files': [str(f) for f in source_files],
                    'categorization_method': 'FILENAME',
                    'geometry_type': config['geometry_type'],
                    'is_processed': False,
                    'feature_count': 0,
                    'is_true': True  # Make it visible by default
                }
            )
            
            self.layers[layer_slug] = layer
            
            if created:
                created_count += 1
                self.stdout.write(f"  ✅ Created layer: {layer.name}")
                self.stdout.write(f"    📊 Contains {len(source_files)} source files")
            else:
                self.stdout.write(f"  📍 Found existing layer: {layer.name}")
        
        self.stdout.write(f"  📊 Created {created_count} new layers")

    def create_city_layer_styles(self):
        """Create city-specific layer styles for all layer types"""
        self.stdout.write("🎨 Creating city layer styles...")
        
        created_count = 0
        
        for layer_slug, config in self.layer_configs.items():
            try:
                category = LayerCategory.objects.get(code=config['category'])
                
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
                    self.stdout.write(f"  ✅ Created style for {config['name']} → {category.name}")
            except LayerCategory.DoesNotExist:
                self.stdout.write(f"  ⚠️ Category not found for {config['name']}: {config['category']}")
        
        self.stdout.write(f"  📊 Created {created_count} new layer styles")

    def process_all_files_into_layers(self):
        """Process all GeoJSON files into their respective layers"""
        self.stdout.write("📁 Processing all GeoJSON files into layers...")
        
        total_features = 0
        
        for layer_slug, layer in self.layers.items():
            config = self.layer_configs[layer_slug]
            data_dir = Path(config['data_path'])
            
            if not data_dir.exists():
                self.stdout.write(f"  ⚠️ Data directory not found: {data_dir}")
                continue
            
            geojson_files = list(data_dir.glob(config['file_pattern']))
            self.stdout.write(f"  📄 Processing {layer.name} ({len(geojson_files)} files)...")
            
            layer_feature_count = 0
            
            for file_path in sorted(geojson_files):
                file_name = file_path.stem
                self.stdout.write(f"    📄 Processing {file_name}...")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        geojson_data = json.load(f)
                    
                    features = geojson_data.get('features', [])
                    self.stdout.write(f"      📊 Processing {len(features)} features...")
                    
                    file_feature_count = 0
                    skipped_none_geometry = 0
                    
                    for feature_data in features:
                        try:
                            # Create geometry - handle 3D coordinates by converting to 2D
                            geom_data = feature_data.get('geometry')
                            if geom_data is None:
                                skipped_none_geometry += 1
                                continue
                                
                            if geom_data.get('type') in ['LineString', 'MultiLineString', 'Polygon', 'MultiPolygon']:
                                # Convert 3D coordinates to 2D by removing Z values
                                if geom_data.get('type') == 'LineString':
                                    geom_data['coordinates'] = [[coord[0], coord[1]] for coord in geom_data['coordinates']]
                                elif geom_data.get('type') == 'MultiLineString':
                                    geom_data['coordinates'] = [[[coord[0], coord[1]] for coord in line] for line in geom_data['coordinates']]
                                elif geom_data.get('type') == 'Polygon':
                                    geom_data['coordinates'] = [[[coord[0], coord[1]] for coord in ring] for ring in geom_data['coordinates']]
                                elif geom_data.get('type') == 'MultiPolygon':
                                    geom_data['coordinates'] = [[[[coord[0], coord[1]] for coord in ring] for ring in poly] for poly in geom_data['coordinates']]
                            
                            # Check if the GeoJSON has a CRS and transform coordinates if needed
                            crs = geojson_data.get('crs', {})
                            source_srid = 4326  # Default to WGS84
                            
                            if crs.get('type') == 'name' and 'EPSG::3857' in crs.get('properties', {}).get('name', ''):
                                source_srid = 3857  # Web Mercator
                            
                            # Create geometry without SRID first
                            geometry = GEOSGeometry(json.dumps(geom_data))
                            
                            # Set the correct SRID and transform if needed
                            if source_srid != 4326:
                                geometry.srid = source_srid
                                geometry.transform(4326)
                            else:
                                geometry.srid = 4326
                            
                            # Extract properties - handle None case and clean data
                            properties = feature_data.get('properties', {})
                            if properties is None:
                                properties = {}
                            
                            # Clean properties to ensure JSON serialization
                            cleaned_properties = {}
                            for key, value in properties.items():
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
                            
                            # Create feature with appropriate field mapping
                            feature = self.create_feature_for_layer(
                                layer, geometry, cleaned_properties, file_name, layer_slug
                            )
                            
                            file_feature_count += 1
                            layer_feature_count += 1
                            total_features += 1
                            
                        except Exception as e:
                            self.stdout.write(f"      ⚠️ Error processing feature: {e}")
                            continue
                    
                    self.stdout.write(f"      ✅ Inserted {file_feature_count} features from {file_name}")
                    if skipped_none_geometry > 0:
                        self.stdout.write(f"      ⚠️ Skipped {skipped_none_geometry} features with None geometry")
                    
                except Exception as e:
                    self.stdout.write(f"      ❌ Error processing file {file_name}: {e}")
                    continue
            
            # Update layer statistics
            layer.feature_count = layer_feature_count
            layer.is_processed = True
            layer.save()
            
            self.stdout.write(f"    ✅ Total features for {layer.name}: {layer_feature_count}")
        
        self.stdout.write(f"  ✅ Total features inserted across all layers: {total_features}")

    def create_feature_for_layer(self, layer, geometry, properties, file_name, layer_slug):
        """Create a GeoFeature with appropriate field mapping based on layer type"""
        
        # Ensure properties is not None
        if properties is None:
            properties = {}
        
        # Common fields
        feature_data = {
            'layer': layer,
            'geometry': geometry,
            'source_layer_name': file_name,
            'properties': properties
        }
        
        # Layer-specific field mapping
        if layer_slug == 'bengaluru_highways':
            feature_data.update({
                'name': properties.get('Name', '') or '',
                'zone_category': properties.get('Notation', '') or '',
                'zone_subcategory': properties.get('Width', '') or '',
                'area': properties.get('Shape_Length'),
                'shape_length': properties.get('Shape_Length'),
                'objectid': properties.get('OBJECTID'),
            })
        elif layer_slug == 'bengaluru_metro':
            feature_data.update({
                'name': properties.get('Name ', '') or properties.get('Name', '') or '',
                'zone_category': properties.get('linecolour', '') or '',
                'zone_subcategory': properties.get('fromjunction', '') or '',
                'area': properties.get('length'),
                'shape_length': properties.get('st_length(shape)'),
                'objectid': properties.get('objectid'),
                'fid': properties.get('fid'),
            })
        elif layer_slug == 'bengaluru_strr':
            feature_data.update({
                'name': properties.get('Name', '') or '',
                'zone_category': properties.get('Notation', '') or '',
                'zone_subcategory': properties.get('Current_Status', '') or '',
                'area': properties.get('Shape_Length'),
                'shape_length': properties.get('Shape_Length'),
                'objectid': properties.get('OBJECTID'),
            })
        elif layer_slug == 'bengaluru_workspaces':
            feature_data.update({
                'name': properties.get('Name', '') or '',
                'zone_category': properties.get('Type', '') or '',
                'zone_subcategory': properties.get('Industry', '') or '',
                'area': properties.get('Size(Acre)'),
                'objectid': properties.get('OBJECTID'),
            })
        
        return GeoFeature.objects.create(**feature_data)

    def calculate_all_layer_bounds(self):
        """Calculate bounding boxes for all layers"""
        self.stdout.write("📐 Calculating layer bounds...")
        
        calculated_count = 0
        for layer_slug, layer in self.layers.items():
            try:
                layer.calculate_bbox()
                calculated_count += 1
                self.stdout.write(f"  ✅ Calculated bounds for {layer.name}")
            except Exception as e:
                self.stdout.write(f"  ⚠️ Error calculating bounds for {layer.name}: {e}")
        
        self.stdout.write(f"  📊 Calculated bounds for {calculated_count} layers")
