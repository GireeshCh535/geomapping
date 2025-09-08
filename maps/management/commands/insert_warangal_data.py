"""
Django management command to insert Warangal data for multiple layer types
This creates separate layers for each data type: residential, commercial, industrial, etc.
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
    help = 'Insert Warangal data for multiple layer types'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Delete existing Warangal data before inserting new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting Warangal Data Insertion')
        )
        
        try:
            with transaction.atomic():
                # Setup basic entities
                self.setup_state_and_city()
                self.setup_layer_categories()
                
                # Delete existing data if requested
                if options['delete_existing']:
                    self.delete_existing_warangal_data()
                
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
                self.style.SUCCESS('\n✅ WARANGAL DATA INSERTION COMPLETED SUCCESSFULLY!')
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
            slug='warangal',
            defaults={
                'name': 'Warangal',
                'state': 'Telangana',
                'state_ref': self.state,
                'center_lat': 17.9689,
                'center_lng': 79.5941,
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
            ('RESIDENTIAL', 'Residential', 'Residential areas and housing'),
            ('COMMERCIAL', 'Commercial', 'Commercial and business areas'),
            ('INDUSTRIAL', 'Industrial', 'Industrial zones and manufacturing'),
            ('MIXED_USE', 'Mixed Use', 'Mixed use development areas'),
            ('PUBLIC', 'Public/Semi-Public', 'Public and semi-public facilities'),
            ('TRANSPORT', 'Transportation', 'Transportation infrastructure'),
            ('UTILITIES', 'Utilities', 'Public utilities and infrastructure'),
            ('PARKS_GREEN', 'Parks & Green Spaces', 'Parks, recreational areas, and green spaces'),
            ('WATER_BODIES', 'Water Bodies', 'Lakes, rivers, and water features'),
            ('PROTECTED', 'Protected/Forest', 'Protected areas and forests'),
            ('AGRICULTURAL', 'Agricultural', 'Agricultural land and farming areas'),
            ('HERITAGE', 'Heritage', 'Heritage and cultural areas'),
            ('BOUNDARIES', 'Administrative Boundaries', 'City and administrative boundaries'),
            ('DEVELOPMENT', 'Development', 'Development zones and areas'),
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
            'warangal_residential': {
                'name': 'Warangal Residential',
                'description': 'Residential areas and housing zones',
                'category': 'RESIDENTIAL',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'Residential*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#FFB6C1',
                'stroke': '#FF69B4',
                'stroke_width': 1
            },
            'warangal_commercial': {
                'name': 'Warangal Commercial',
                'description': 'Commercial and business areas',
                'category': 'COMMERCIAL',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'Commercial*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#FFD700',
                'stroke': '#FFA500',
                'stroke_width': 1
            },
            'warangal_industrial': {
                'name': 'Warangal Industrial',
                'description': 'Industrial zones and manufacturing areas',
                'category': 'INDUSTRIAL',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'Industrial*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#D2691E',
                'stroke': '#8B4513',
                'stroke_width': 1
            },
            'warangal_mixed_use': {
                'name': 'Warangal Mixed Use',
                'description': 'Mixed use development areas',
                'category': 'MIXED_USE',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'MixedUse*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#9370DB',
                'stroke': '#8A2BE2',
                'stroke_width': 1
            },
            'warangal_public_semipublic': {
                'name': 'Warangal Public & Semi-Public',
                'description': 'Public and semi-public facilities',
                'category': 'PUBLIC',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'Public_and_SemiPublic*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#87CEEB',
                'stroke': '#4682B4',
                'stroke_width': 1
            },
            'warangal_transportation': {
                'name': 'Warangal Transportation',
                'description': 'Transportation infrastructure',
                'category': 'TRANSPORT',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'Transportation*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#808080',
                'stroke': '#2F4F4F',
                'stroke_width': 1
            },
            'warangal_public_utilities': {
                'name': 'Warangal Public Utilities',
                'description': 'Public utilities and infrastructure',
                'category': 'UTILITIES',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'PublicUtilities*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#A9A9A9',
                'stroke': '#696969',
                'stroke_width': 1
            },
            'warangal_recreational': {
                'name': 'Warangal Recreational',
                'description': 'Recreational areas and parks',
                'category': 'PARKS_GREEN',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'Recreational*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#90EE90',
                'stroke': '#228B22',
                'stroke_width': 1
            },
            'warangal_water_bodies': {
                'name': 'Warangal Water Bodies',
                'description': 'Lakes, rivers, and water features',
                'category': 'WATER_BODIES',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'Water_Bodies*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#4169E1',
                'stroke': '#0000CD',
                'stroke_width': 1
            },
            'warangal_forest': {
                'name': 'Warangal Forest',
                'description': 'Forest and protected areas',
                'category': 'PROTECTED',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'Forest*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#228B22',
                'stroke': '#006400',
                'stroke_width': 1
            },
            'warangal_agricultural': {
                'name': 'Warangal Agricultural',
                'description': 'Agricultural land and farming areas',
                'category': 'AGRICULTURAL',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'Agriculture*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#9ACD32',
                'stroke': '#556B2F',
                'stroke_width': 1
            },
            'warangal_heritage': {
                'name': 'Warangal Heritage',
                'description': 'Heritage and cultural areas',
                'category': 'HERITAGE',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'Heritage*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#CD853F',
                'stroke': '#8B4513',
                'stroke_width': 1
            },
            'warangal_railway_land': {
                'name': 'Warangal Railway Land',
                'description': 'Railway land and infrastructure',
                'category': 'TRANSPORT',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'RailwayLand*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#8B4513',
                'stroke': '#654321',
                'stroke_width': 1
            },
            'warangal_zoological_park': {
                'name': 'Warangal Zoological Park',
                'description': 'Zoological park and wildlife areas',
                'category': 'PARKS_GREEN',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'ZoologicalPark*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#32CD32',
                'stroke': '#228B22',
                'stroke_width': 1
            },
            'warangal_air_strip': {
                'name': 'Warangal Air Strip',
                'description': 'Airport and aviation facilities',
                'category': 'TRANSPORT',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'AirStrip*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#708090',
                'stroke': '#2F4F4F',
                'stroke_width': 1
            },
            'warangal_growth_corridor': {
                'name': 'Warangal Growth Corridor',
                'description': 'Growth corridor development areas',
                'category': 'DEVELOPMENT',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'GrowthCorridor*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#FF6347',
                'stroke': '#DC143C',
                'stroke_width': 1
            },
            'warangal_hill_buffer': {
                'name': 'Warangal Hill Buffer',
                'description': 'Hill buffer zones and protection areas',
                'category': 'PROTECTED',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'HillBuffer*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#8B7355',
                'stroke': '#654321',
                'stroke_width': 1
            },
            'warangal_hillocks': {
                'name': 'Warangal Hillocks',
                'description': 'Hillocks and elevated areas',
                'category': 'PROTECTED',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'Hillocks*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#A0522D',
                'stroke': '#8B4513',
                'stroke_width': 1
            },
            'warangal_road_buffer': {
                'name': 'Warangal Road Buffer',
                'description': 'Road buffer zones and setbacks',
                'category': 'TRANSPORT',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'RoadBuffer*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#C0C0C0',
                'stroke': '#808080',
                'stroke_width': 1
            },
            'warangal_water_body_buffer': {
                'name': 'Warangal Water Body Buffer',
                'description': 'Water body buffer zones and protection areas',
                'category': 'WATER_BODIES',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'WaterBodyBuffer*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#87CEFA',
                'stroke': '#4682B4',
                'stroke_width': 1
            },
            'warangal_residential_expansion': {
                'name': 'Warangal Residential Expansion',
                'description': 'Residential expansion areas',
                'category': 'RESIDENTIAL',
                'data_path': 'data/Telangana/warangal/master_plan',
                'file_pattern': 'ResidentialExpansion*.geojson',
                'geometry_type': 'POLYGON',
                'color': '#FFA07A',
                'stroke': '#FF7F50',
                'stroke_width': 1
            }
        }

    def delete_existing_warangal_data(self):
        """Delete existing Warangal data to start fresh"""
        self.stdout.write("🗑️ Deleting existing Warangal data...")
        
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
                            geom_data = feature_data.get('geometry')
                            if geom_data is None:
                                self.stdout.write(f"      ⚠️ Skipping feature with None geometry")
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
                            
                            # Extract properties - handle None case
                            properties = feature_data.get('properties', {})
                            if properties is None:
                                properties = {}
                            
                            # Create feature with appropriate field mapping
                            feature = self.create_feature_for_layer(
                                layer, geometry, properties, file_name, layer_slug
                            )
                            
                            file_feature_count += 1
                            layer_feature_count += 1
                            total_features += 1
                            
                        except Exception as e:
                            self.stdout.write(f"      ⚠️ Error processing feature: {e}")
                            # Debug: print more details about the error
                            import traceback
                            self.stdout.write(f"      Debug: {traceback.format_exc()}")
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
        
        # Warangal-specific field mapping based on the data structure
        feature_data.update({
            'name': properties.get('Name', '') or properties.get('PLU_NAME', ''),
            'zone_category': properties.get('PLU', '') or properties.get('Category', ''),
            'plot_category': properties.get('PLU_Catego', '') or properties.get('Sub_Catego', ''),
            'symbology': properties.get('PLU', '') or properties.get('Category', ''),
            'area': properties.get('Area') or properties.get('Shape_Area'),
            'shape_length': properties.get('Shape_Length'),
            'shape_area': properties.get('Shape_Area'),
            'objectid': properties.get('OBJECTID'),
            'kuda': properties.get('KUDA', ''),
            'ex_pr': properties.get('Ex_PR', ''),
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
