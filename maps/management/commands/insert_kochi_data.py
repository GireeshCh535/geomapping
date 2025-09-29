"""
Django management command to insert Kochi master plan data
This creates ONE layer (kochi_master_plan) with all masterplan files as features
Following the hierarchy: tamil-nadu -> kochi -> kochi_master_plan -> all features

Note: Kochi currently has only raster data (TIFF files), no GeoJSON vector data available.
This command creates the infrastructure ready for when GeoJSON data becomes available.
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
    help = 'Insert Kochi master plan data into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Delete existing Kochi masterplan data before inserting new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting Kochi Master Plan Data Insertion')
        )
        
        try:
            with transaction.atomic():
                # Setup basic entities
                self.setup_state_and_city()
                self.setup_layer_categories()
                
                # Delete existing data if requested
                if options['delete_existing']:
                    self.delete_existing_kochi_masterplan_data()
                
                # Create the SINGLE master plan layer
                self.create_master_plan_layer()
                
                # Create styles for all zone types
                self.create_city_layer_styles()
                
                # Process all masterplan files into the single layer
                self.process_all_masterplan_files()
                
                self.stdout.write(
                    self.style.SUCCESS('✅ Kochi Master Plan Data Insertion Completed Successfully!')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error during data insertion: {str(e)}')
            )
            raise CommandError(f'Data insertion failed: {str(e)}')

    def setup_state_and_city(self):
        """Setup Tamil Nadu state and Kochi city"""
        self.stdout.write('Setting up Tamil Nadu state and Kochi city...')
        
        # First try to get existing Tamil Nadu state by code
        try:
            self.state = State.objects.get(code='TN')
            self.stdout.write(f'  ✅ Found existing state: {self.state.name}')
        except State.DoesNotExist:
            # If not found by code, try by slug
            try:
                self.state = State.objects.get(slug='tamil-nadu')
                self.stdout.write(f'  ✅ Found existing state by slug: {self.state.name}')
            except State.DoesNotExist:
                # Create new state if it doesn't exist
                self.state = State.objects.create(
                    name='Tamil Nadu',
                    slug='tamil-nadu',
                    code='TN',
                    center_lat=11.1271,
                    center_lng=78.6569,
                    default_zoom=7,
                    is_active=True
                )
                self.stdout.write(f'  ✅ Created state: {self.state.name}')
        
        # Create or get Kochi city
        self.city, created = City.objects.get_or_create(
            slug='kochi',
            defaults={
                'name': 'Kochi',
                'state': 'Tamil Nadu',  # Legacy field
                'state_ref': self.state,
                'center_lat': 9.9312,
                'center_lng': 76.2673,
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
        """Setup layer categories for Kochi masterplan"""
        self.stdout.write('Setting up layer categories...')
        
        # Define categories for Kochi masterplan
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
            ('PLANNING', 'Planning Areas', 'Urban planning and development areas', '#FFE4B5'),
            ('BOUNDARIES', 'Administrative Boundaries', 'City and administrative boundaries', '#FFFFFF'),
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

    def delete_existing_kochi_masterplan_data(self):
        """Delete existing Kochi masterplan data"""
        self.stdout.write('Deleting existing Kochi masterplan data...')
        
        # Delete the masterplan layer and all its features
        deleted_layers = DataLayer.objects.filter(
            city=self.city,
            slug='kochi_master_plan'
        ).delete()
        
        if deleted_layers[0] > 0:
            self.stdout.write(f'  ✅ Deleted {deleted_layers[0]} existing masterplan layers')
        
        # Delete any existing layer groups
        deleted_groups = LayerGroup.objects.filter(
            city=self.city,
            slug='kochi_master_plan'
        ).delete()
        
        if deleted_groups[0] > 0:
            self.stdout.write(f'  ✅ Deleted {deleted_groups[0]} existing layer groups')

    def create_master_plan_layer(self):
        """Create the single masterplan layer"""
        self.stdout.write('Creating Kochi Master Plan layer...')
        
        # Create layer group
        self.layer_group, created = LayerGroup.objects.get_or_create(
            city=self.city,
            slug='kochi_master_plan',
            defaults={
                'name': 'Kochi Master Plan',
                'description': 'Comprehensive master plan data for Kochi including all land use zones',
                'category': self.categories['PLANNING'],
                'directory_path': 'data/tamil_nadu/kochi/kochi_master_plan/',
                'default_color': '#FFE4B5',
                'default_stroke': '#FF8C00',
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
            slug='kochi_master_plan',
            defaults={
                'name': 'Kochi Master Plan',
                'description': 'Kochi master plan data including analysis and planning data',
                'category': self.categories['PLANNING'],
                'layer_group': self.layer_group,
                'file_format': 'JSON',
                'is_directory': False,  # Not a directory, specific files
                'file_pattern': '',
                'file_path': 'data/tamil_nadu/kochi/kochi_master_plan/',
                'geometry_type': 'POLYGON',
                'categorization_method': 'FILENAME',
                'is_processed': False,
                'feature_count': 0,
                'is_true': True,  # Make it visible by default
                'tiles_generated': False,
                'data_source': 'Kochi Planning Authority',
                'source_files': [
                    'Kochi_Merged_Clipped_analysis.json'
                ]
            }
        )
        
        if created:
            self.stdout.write(f'  ✅ Created masterplan layer: {self.masterplan_layer.name}')
        else:
            self.stdout.write(f'  ✅ Found existing masterplan layer: {self.masterplan_layer.name}')

    def create_city_layer_styles(self):
        """Create city-specific layer styles for all categories"""
        self.stdout.write('Creating city-specific layer styles...')
        
        # Define specific colors for Kochi masterplan categories
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
            'PLANNING': {'fill_color': '#FFE4B5', 'pattern': 'SOLID'},
            'BOUNDARIES': {'fill_color': '#FFFFFF', 'pattern': 'DOTTED'},
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
        """Process specific Kochi masterplan files into the single layer"""
        self.stdout.write('Processing Kochi masterplan files...')
        
        # Define specific files to process (based on actual files in directory)
        masterplan_files = [
            'data/tamil_nadu/kochi/kochi_master_plan/Kochi_Merged_Clipped_analysis.json'
        ]
        
        # Also check for any other JSON/GeoJSON files in the directory
        masterplan_dir = Path('data/tamil_nadu/kochi/kochi_master_plan/')
        all_json_files = list(masterplan_dir.glob('*.json')) + list(masterplan_dir.glob('*.geojson'))
        
        # Check which specific files actually exist
        existing_files = []
        for file_path in masterplan_files:
            if Path(file_path).exists():
                existing_files.append(Path(file_path))
            else:
                self.stdout.write(f'  ⚠️  File not found: {file_path}')
        
        # Report file statistics
        self.stdout.write(f'📁 Directory contains {len(all_json_files)} total JSON/GeoJSON files')
        self.stdout.write(f'📋 Configured to process {len(masterplan_files)} specific files')
        self.stdout.write(f'✅ Found {len(existing_files)} files to process')
        
        if len(existing_files) == 0:
            self.stdout.write('⚠️  No JSON files found in Kochi data directory')
            self.stdout.write('ℹ️  Kochi currently has only raster data (TIFF files)')
            self.stdout.write('ℹ️  The infrastructure is ready for when JSON data becomes available')
            
            # Update layer statistics to reflect no data
            self.masterplan_layer.feature_count = 0
            self.masterplan_layer.is_processed = True
            self.masterplan_layer.save()
            
            # Update layer group statistics
            self.layer_group.save()
            
            self.stdout.write(f'\n📊 Processing Summary:')
            self.stdout.write(f'  📁 Total JSON/GeoJSON files in directory: {len(all_json_files)}')
            self.stdout.write(f'  📋 Files configured for processing: {len(masterplan_files)}')
            self.stdout.write(f'  ✅ Infrastructure created and ready')
            self.stdout.write(f'  ⚠️  No JSON files found (expected for Kochi)')
            self.stdout.write(f'  📈 Total features added: 0')
            self.stdout.write(f'  ℹ️  Layer is ready for future JSON data')
            return
        
        total_features = 0
        processed_files = 0
        error_files = []
        
        for json_file in existing_files:
            try:
                self.stdout.write(f'  Processing: {json_file.name}')
                features_added = self.process_masterplan_file(json_file)
                total_features += features_added
                processed_files += 1
                self.stdout.write(f'    ✅ Added {features_added} features')
                
            except Exception as e:
                error_files.append((json_file.name, str(e)))
                self.stdout.write(f'    ❌ Error processing {json_file.name}: {str(e)}')
        
        # Update layer statistics and geometry type
        self.masterplan_layer.feature_count = total_features
        self.masterplan_layer.is_processed = True
        
        # Update geometry type based on actual processed data
        if total_features > 0:
            # Get a sample feature to determine geometry type
            sample_feature = GeoFeature.objects.filter(layer=self.masterplan_layer).first()
            if sample_feature:
                geom_type = sample_feature.geometry.geom_type.upper()
                if geom_type in ['POLYGON', 'MULTIPOLYGON', 'POINT', 'LINESTRING', 'MULTILINESTRING']:
                    self.masterplan_layer.geometry_type = geom_type
        
        self.masterplan_layer.save()
        
        # Update layer group statistics
        self.layer_group.save()
        
        self.stdout.write(f'\n📊 Processing Summary:')
        self.stdout.write(f'  📁 Total JSON/GeoJSON files in directory: {len(all_json_files)}')
        self.stdout.write(f'  📋 Files configured for processing: {len(masterplan_files)}')
        self.stdout.write(f'  ✅ Successfully processed: {processed_files} files')
        self.stdout.write(f'  ❌ Errors: {len(error_files)} files')
        self.stdout.write(f'  📈 Total features added: {total_features:,}')
        
        if error_files:
            self.stdout.write(f'\n❌ Files with errors:')
            for filename, error in error_files:
                self.stdout.write(f'  - {filename}: {error}')

    def process_masterplan_file(self, json_file):
        """Process a single masterplan JSON file"""
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        features = data.get('features', [])
        if not features:
            return 0
        
        # Determine category based on filename
        category_code = self.get_category_from_filename(json_file.stem)
        category = self.categories.get(category_code, self.categories['UNCLASSIFIED'])
        
        features_added = 0
        
        for feature_data in features:
            try:
                # Extract geometry
                geometry_data = feature_data.get('geometry')
                if not geometry_data:
                    continue
                
                # Handle GeoJSON geometry (already in correct format)
                if geometry_data.get('type') in ['Polygon', 'MultiPolygon', 'LineString', 'MultiLineString', 'Point', 'MultiPoint']:
                    # Already in GeoJSON format
                    geojson_geometry = geometry_data
                else:
                    # Convert ESRI geometry to GeoJSON format
                    geojson_geometry = self.convert_esri_to_geojson(geometry_data)
                    if not geojson_geometry:
                        continue
                
                # Convert to GEOS geometry
                geometry = GEOSGeometry(json.dumps(geojson_geometry))
                
                # Flatten 3D geometry to 2D (remove Z dimension)
                if geometry.hasz:
                    geom_dict = json.loads(geometry.geojson)
                    
                    def remove_z_from_coords(coords):
                        """Recursively remove Z coordinates from coordinate arrays"""
                        if isinstance(coords[0], (int, float)):
                            return coords[:2]
                        else:
                            return [remove_z_from_coords(coord) for coord in coords]
                    
                    if 'coordinates' in geom_dict:
                        geom_dict['coordinates'] = remove_z_from_coords(geom_dict['coordinates'])
                    
                    geometry = GEOSGeometry(json.dumps(geom_dict))
                
                # Validate and fix geometry
                if not geometry.valid:
                    try:
                        geometry = geometry.buffer(0)
                        if not geometry.valid:
                            geometry = geometry.buffer(0.000001)
                            if not geometry.valid:
                                continue
                    except Exception:
                        continue
                
                # Extract attributes (GeoJSON uses 'properties', ESRI JSON uses 'attributes')
                attributes = feature_data.get('properties', feature_data.get('attributes', {}))
                
                # Helper function to clean numeric fields
                def clean_numeric_field(value):
                    """Convert empty strings to None for numeric fields"""
                    if value == '' or value is None:
                        return None
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        return None
                
                # Create GeoFeature
                geo_feature = GeoFeature.objects.create(
                    layer=self.masterplan_layer,
                    geometry=geometry,
                    name=attributes.get('name', attributes.get('id', '')),
                    source_layer_name=json_file.stem,
                    zone_category=category.name,
                    zone_subcategory=attributes.get('zone_type', json_file.stem),
                    
                    # Kochi-specific fields
                    plu_primary_code=attributes.get('zone_code', ''),
                    plu_secondary_1=attributes.get('zone_name', ''),
                    plu_secondary_2=attributes.get('zone_type', ''),
                    plu_proposed_use=attributes.get('proposed_use', ''),
                    plu_development_code=clean_numeric_field(attributes.get('development_code')),
                    plu_authority=attributes.get('authority', 'Kochi Planning Authority'),
                    
                    # Common fields
                    area=attributes.get('area') or attributes.get('Shape_Area'),
                    shape_length=attributes.get('Shape_Length'),
                    shape_area=attributes.get('Shape_Area'),
                    objectid=clean_numeric_field(attributes.get('OBJECTID') or attributes.get('id')),
                    fid=clean_numeric_field(attributes.get('FID') or attributes.get('fid')),
                    
                    # Store all original properties
                    properties=attributes,
                    is_valid=True
                )
                
                features_added += 1
                
            except Exception as e:
                self.stdout.write(f'    ⚠️  Error processing feature in {json_file.name}: {str(e)}')
                continue
        
        return features_added

    def get_category_from_filename(self, filename):
        """Map filename to category code for Kochi masterplan files"""
        filename_lower = filename.lower()
        
        # Kochi-specific file mappings
        if 'kochi_merged_clipped_analysis' in filename_lower:
            return 'PLANNING'
        elif 'planning' in filename_lower or 'boundary' in filename_lower:
            return 'PLANNING'
        else:
            return 'UNCLASSIFIED'

    def convert_esri_to_geojson(self, esri_geometry):
        """Convert ESRI geometry format to GeoJSON format"""
        try:
            if 'rings' in esri_geometry:
                # ESRI Polygon format
                rings = esri_geometry['rings']
                if not rings:
                    return None
                
                # Convert rings to GeoJSON coordinates
                # First ring is exterior, rest are holes
                exterior_ring = rings[0]
                holes = rings[1:] if len(rings) > 1 else []
                
                # Ensure rings are closed (first and last coordinates are the same)
                if exterior_ring[0] != exterior_ring[-1]:
                    exterior_ring.append(exterior_ring[0])
                
                for hole in holes:
                    if hole[0] != hole[-1]:
                        hole.append(hole[0])
                
                coordinates = [exterior_ring] + holes
                
                return {
                    "type": "Polygon",
                    "coordinates": coordinates
                }
            
            elif 'paths' in esri_geometry:
                # ESRI Polyline format
                paths = esri_geometry['paths']
                if not paths:
                    return None
                
                if len(paths) == 1:
                    return {
                        "type": "LineString",
                        "coordinates": paths[0]
                    }
                else:
                    return {
                        "type": "MultiLineString",
                        "coordinates": paths
                    }
            
            elif 'x' in esri_geometry and 'y' in esri_geometry:
                # ESRI Point format
                return {
                    "type": "Point",
                    "coordinates": [esri_geometry['x'], esri_geometry['y']]
                }
            
            else:
                # Unknown format, try to return as-is
                return esri_geometry
                
        except Exception as e:
            self.stdout.write(f'    ⚠️  Error converting ESRI geometry: {str(e)}')
            return None