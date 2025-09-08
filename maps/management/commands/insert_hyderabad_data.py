"""
Django management command to insert Hyderabad data for multiple layer types
This creates separate layers for each data type: highways, metro, roads, etc.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.gis.geos import GEOSGeometry
from django.utils.text import slugify
from pathlib import Path
import json
import glob

from maps.models import (
    State, City, LayerCategory, DataLayer, GeoFeature, 
    CityLayerStyle, LayerGroup
)


class Command(BaseCommand):
    help = 'Insert Hyderabad data for multiple layer types'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Delete existing Hyderabad data before inserting new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting Hyderabad Data Insertion')
        )
        
        try:
            with transaction.atomic():
                # Setup basic entities
                self.setup_state_and_city()
                self.setup_layer_categories()
                
                # Delete existing data if requested
                if options['delete_existing']:
                    self.delete_existing_hyderabad_data()
                
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
                self.style.SUCCESS('\n✅ HYDERABAD DATA INSERTION COMPLETED SUCCESSFULLY!')
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
            code='TS',
            defaults={
                'name': 'Telangana',
                'slug': 'telangana',
                'center_lat': 18.1124,
                'center_lng': 79.0193,
                'default_zoom': 7
            }
        )
        if created:
            self.stdout.write(f"  ✅ Created state: {self.state.name}")
        else:
            self.stdout.write(f"  📍 Found existing state: {self.state.name}")
        
        # Create/update City
        self.city, created = City.objects.get_or_create(
            slug='hyderabad',
            defaults={
                'name': 'Hyderabad',
                'state': 'Telangana',
                'state_ref': self.state,
                'center_lat': 17.3850,
                'center_lng': 78.4867,
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
            ('HIGHWAYS', 'Highways', 'National and state highways'),
            ('METRO', 'Metro', 'Metro rail lines and stations'),
            ('ROADS', 'Roads', 'City roads and street network'),
            ('BOUNDARY', 'Boundary', 'City and administrative boundaries'),
            ('DEVELOPMENT', 'Development', 'Development zones and areas'),
            ('SPECIAL', 'Special Zones', 'Special economic zones and areas'),
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
            'hyderabad_future_city': {
                'name': 'Hyderabad Future City',
                'description': 'Future City Development Authority boundary',
                'category': 'BOUNDARY',
                'data_path': 'data/Telangana/Hyderabad/future-city',
                'file_pattern': '*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#FF6B6B',
                'stroke': '#CC0000',
                'stroke_width': 2
            },
            'hyderabad_highways': {
                'name': 'Hyderabad Highways',
                'description': 'National and state highways around Hyderabad',
                'category': 'HIGHWAYS',
                'data_path': 'data/Telangana/Hyderabad/highways',
                'file_pattern': '*.geojson',
                'geometry_type': 'LINESTRING',
                'color': '#FFA500',
                'stroke': '#FF8C00',
                'stroke_width': 3
            },
            'hyderabad_master_plan___roads': {
                'name': 'Hyderabad Master Plan Roads',
                'description': 'HMDA master plan road network',
                'category': 'ROADS',
                'data_path': 'data/Telangana/Hyderabad/master-plan-roads',
                'file_pattern': '*.geojson',
                'geometry_type': 'LINESTRING',
                'color': '#808080',
                'stroke': '#404040',
                'stroke_width': 2
            },
            'hyderabad_metro': {
                'name': 'Hyderabad Metro',
                'description': 'Metro rail lines and stations',
                'category': 'METRO',
                'data_path': 'data/Telangana/Hyderabad/metro-lines',
                'file_pattern': '*.geojson',
                'geometry_type': 'LINESTRING',
                'color': '#00CED1',
                'stroke': '#008B8B',
                'stroke_width': 4
            },
            'hyderabad_ratan_tata_road': {
                'name': 'Ratan Tata Road',
                'description': 'Ratan Tata Road corridor',
                'category': 'ROADS',
                'data_path': 'data/Telangana/Hyderabad/ratan-tata-road',
                'file_pattern': '*.geojson',
                'geometry_type': 'LINESTRING',
                'color': '#32CD32',
                'stroke': '#228B22',
                'stroke_width': 3
            },
            'hyderabad_rrr': {
                'name': 'Hyderabad Regional Ring Road',
                'description': 'Regional Ring Road (RRR) around Hyderabad',
                'category': 'HIGHWAYS',
                'data_path': 'data/Telangana/Hyderabad/rrr',
                'file_pattern': '*.geojson',
                'geometry_type': 'LINESTRING',
                'color': '#FF1493',
                'stroke': '#DC143C',
                'stroke_width': 4
            }
        }

    def delete_existing_hyderabad_data(self):
        """Delete existing Hyderabad data to start fresh"""
        self.stdout.write("🗑️ Deleting existing Hyderabad data...")
        
        # Delete features first (due to foreign key constraints)
        features_deleted = GeoFeature.objects.filter(layer__city=self.city).count()
        GeoFeature.objects.filter(layer__city=self.city).delete()
        self.stdout.write(f"  🗑️ Deleted {features_deleted} features")
        
        # Delete layers
        layers_deleted = DataLayer.objects.filter(city=self.city).count()
        DataLayer.objects.filter(city=self.city).delete()
        self.stdout.write(f"  🗑️ Deleted {layers_deleted} layers")
        
        # Delete layer styles
        styles_deleted = CityLayerStyle.objects.filter(city=self.city).count()
        CityLayerStyle.objects.filter(city=self.city).delete()
        self.stdout.write(f"  🗑️ Deleted {styles_deleted} layer styles")

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
                    'feature_count': 0
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
                    for feature_data in features:
                        try:
                            # Create geometry - handle 3D coordinates by converting to 2D
                            geom_data = feature_data['geometry']
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
                            
                            # Extract properties
                            properties = feature_data.get('properties', {})
                            
                            # Create feature with appropriate field mapping
                            feature = self.create_feature_for_layer(
                                layer, geometry, properties, file_name, layer_slug
                            )
                            
                            file_feature_count += 1
                            layer_feature_count += 1
                            total_features += 1
                            
                        except Exception as e:
                            self.stdout.write(f"      ⚠️ Error processing feature: {e}")
                            continue
                    
                    self.stdout.write(f"      ✅ Inserted {file_feature_count} features from {file_name}")
                    
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
        
        # Common fields
        feature_data = {
            'layer': layer,
            'geometry': geometry,
            'source_layer_name': file_name,
            'properties': properties
        }
        
        # Layer-specific field mapping
        if layer_slug == 'hyderabad_highways':
            feature_data.update({
                'name': properties.get('Name', ''),
                'zone_category': properties.get('Notation', ''),
                'plot_category': properties.get('End_to_End_Points', ''),
                'symbology': properties.get('Notation', ''),
                'area': properties.get('Shape_Length'),
                'objectid': properties.get('OBJECTID'),
            })
        elif layer_slug == 'hyderabad_master_plan___roads':
            feature_data.update({
                'name': properties.get('Name', ''),
                'zone_category': properties.get('Category', ''),
                'plot_category': properties.get('Type', ''),
                'symbology': properties.get('Category', ''),
                'area': properties.get('Shape_Length'),
                'objectid': properties.get('OBJECTID'),
            })
        elif layer_slug == 'hyderabad_metro':
            feature_data.update({
                'name': properties.get('Name', ''),
                'zone_category': properties.get('Type', ''),
                'plot_category': properties.get('Phase', ''),
                'symbology': properties.get('Type', ''),
                'area': properties.get('Shape_Length'),
                'objectid': properties.get('OBJECTID'),
            })
        elif layer_slug == 'hyderabad_ratan_tata_road':
            feature_data.update({
                'name': properties.get('Name', ''),
                'zone_category': properties.get('Type', ''),
                'plot_category': properties.get('Category', ''),
                'symbology': properties.get('Type', ''),
                'area': properties.get('Shape_Length'),
                'objectid': properties.get('OBJECTID'),
            })
        elif layer_slug == 'hyderabad_rrr':
            feature_data.update({
                'name': properties.get('Name', ''),
                'zone_category': properties.get('Type', ''),
                'plot_category': properties.get('Category', ''),
                'symbology': properties.get('Type', ''),
                'area': properties.get('Shape_Length'),
                'objectid': properties.get('OBJECTID'),
            })
        elif layer_slug == 'hyderabad_future_city':
            feature_data.update({
                'name': properties.get('Name', ''),
                'zone_category': properties.get('Type', ''),
                'plot_category': properties.get('Category', ''),
                'symbology': properties.get('Type', ''),
                'area': properties.get('Shape_Area'),
                'objectid': properties.get('OBJECTID'),
            })
        else:
            # Default mapping
            feature_data.update({
                'name': properties.get('Name', '') or properties.get('name', ''),
                'zone_category': properties.get('Type', '') or properties.get('category', ''),
                'plot_category': properties.get('Category', '') or properties.get('type', ''),
                'symbology': properties.get('Type', '') or properties.get('category', ''),
                'area': properties.get('Shape_Area') or properties.get('Shape_Length'),
                'objectid': properties.get('OBJECTID') or properties.get('objectid'),
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
