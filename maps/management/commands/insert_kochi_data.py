"""
Django management command to insert Kochi master plan data
Creates ONE layer (kochi_master_plan) with all masterplan files as features
Following the hierarchy: State (Kerala) -> City (Kochi) -> DataLayer -> GeoFeatures from all files
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
    help = 'Insert Kochi master plan data into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Delete existing Kochi masterplan data before inserting new data',
        )
        parser.add_argument(
            '--data-dir',
            type=str,
            default='data/kerala/kochi/kochi_master_plan/',
            help='Directory containing the master plan data files',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting Kochi Master Plan Data Insertion')
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
                    self.delete_existing_kochi_masterplan_data()
                
                # Create ONE master plan layer and process all files into it
                self.create_and_populate_master_plan_layer()
                
                # Create city-specific styles
                self.create_city_layer_styles()
                
                # Create zone mappings for better categorization
                self.create_zone_mappings()
                
                # Print summary
                self.print_summary()
                
                self.stdout.write(
                    self.style.SUCCESS('✅ Kochi Master Plan Data Insertion Completed Successfully!')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error during data insertion: {str(e)}')
            )
            raise CommandError(f'Data insertion failed: {str(e)}')

    def setup_state_and_city(self):
        """Setup Kerala state and Kochi city"""
        self.stdout.write('Setting up Kerala state and Kochi city...')
        
        # Create or get Kerala state
        self.state, created = State.objects.get_or_create(
            code='KL',
            defaults={
                'name': 'Kerala',
                'slug': 'kerala',
                'center_lat': 10.8505,
                'center_lng': 76.2711,
                'default_zoom': 7,
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(f'  ✅ Created state: {self.state.name}')
        else:
            self.stdout.write(f'  ✅ Found existing state: {self.state.name}')
        
        # Create or get Kochi city
        self.city, created = City.objects.get_or_create(
            slug='kochi',
            defaults={
                'name': 'Kochi',
                'state': 'Kerala',
                'state_ref': self.state,
                'center_lat': 9.9312,
                'center_lng': 76.2673,
                'min_zoom': 6,
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
        """Setup layer categories for Kochi masterplan"""
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
                    'default_stroke_width': 1,
                    'default_opacity': 0.7,
                    'is_active': True
                }
            )
            
            self.categories[code] = category
            
            if created:
                self.stdout.write(f'  ✅ Created category: {name}')
            else:
                self.stdout.write(f'  ✅ Found existing category: {name}')

    def delete_existing_kochi_masterplan_data(self):
        """Delete existing Kochi masterplan data"""
        self.stdout.write('Deleting existing Kochi masterplan data...')
        
        # Delete existing data layers for Kochi masterplan
        deleted_layers = DataLayer.objects.filter(
            city=self.city,
            slug__icontains='master_plan'
        ).delete()
        
        if deleted_layers[0] > 0:
            self.stdout.write(f'  ✅ Deleted {deleted_layers[0]} existing data layers')
        
        # Delete existing geo features
        deleted_features = GeoFeature.objects.filter(
            layer__city=self.city,
            layer__slug__icontains='master_plan'
        ).delete()
        
        if deleted_features[0] > 0:
            self.stdout.write(f'  ✅ Deleted {deleted_features[0]} existing geo features')

    def create_and_populate_master_plan_layer(self):
        """Create ONE master plan layer and populate it with features from all files"""
        self.stdout.write('\nCreating and populating Kochi master plan layer...')
        
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
                slug='kochi-master-plan',
                defaults={
                    'name': 'Kochi Master Plan',
                    'description': 'Kochi Planning Authority master plan data',
                    'category': self.categories['PLANNING'],
                    'directory_path': str(self.data_dir),
                    'default_color': '#FFE4B5',
                    'default_stroke': '#FF8C00',
                    'default_opacity': 0.7,
                    'display_order': 0,
                    'is_visible': True,
                    'min_zoom': 6,
                    'max_zoom': 18
                }
            )
            
            self.master_plan_layer, created = DataLayer.objects.get_or_create(
                city=self.city,
                slug='kochi-master-plan',
                defaults={
                    'name': 'Kochi Master Plan',
                    'description': 'Comprehensive Kochi master plan including all boundaries and land use zones',
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
                    'data_source': 'Kochi Planning Authority',
                }
            )
            
            if created:
                self.stdout.write(f'  ✅ Created empty master plan layer: {self.master_plan_layer.name}')
            else:
                self.stdout.write(f'  ✅ Found existing master plan layer: {self.master_plan_layer.name}')
            
            return
        
        self.stdout.write(f'  📁 Found {len(all_files)} files to process:')
        for f in all_files:
            relative_path = f.relative_to(self.data_dir) if self.data_dir in f.parents else f.name
            self.stdout.write(f'  - {relative_path}')
        
        # Create a layer group for organization
        layer_group, created = LayerGroup.objects.get_or_create(
            city=self.city,
            slug='kochi-master-plan',
            defaults={
                'name': 'Kochi Master Plan',
                'description': 'Kochi Planning Authority master plan data',
                'category': self.categories['PLANNING'],
                'directory_path': str(self.data_dir),
                'default_color': '#FFE4B5',
                'default_stroke': '#FF8C00',
                'default_opacity': 0.7,
                'display_order': 0,
                'is_visible': True,
                'min_zoom': 6,
                'max_zoom': 18
            }
        )
        
        # Collect source file names for the layer
        source_file_names = [f.name for f in all_files]
        
        # Create or update THE SINGLE master plan layer
        self.master_plan_layer, created = DataLayer.objects.get_or_create(
            city=self.city,
            slug='kochi-master-plan',
            defaults={
                'name': 'Kochi Master Plan',
                'description': 'Comprehensive Kochi master plan including all boundaries and land use zones',
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
                'data_source': 'Kochi Planning Authority',
            }
        )
        
        if created:
            self.stdout.write(f'  ✅ Created master plan layer: {self.master_plan_layer.name}')
        else:
            self.stdout.write(f'  ✅ Found existing master plan layer: {self.master_plan_layer.name}')
        
        # Process all files and create features
        self.process_all_files(all_files)

    def process_all_files(self, all_files):
        """Process all files and create features"""
        self.stdout.write('\nProcessing all files...')
        
        total_features = 0
        geometry_types = set()
        
        for file_path in all_files:
            self.stdout.write(f'  📄 Processing: {file_path.name}')
            
            try:
                features_added, geom_type = self.process_single_file(file_path)
                total_features += features_added
                if geom_type:
                    geometry_types.add(geom_type)
                    
            except Exception as e:
                self.stdout.write(f'    ❌ Error processing {file_path.name}: {str(e)}')
                continue
        
        # Update the layer with final statistics
        if self.master_plan_layer:
            self.master_plan_layer.feature_count = total_features
            self.master_plan_layer.is_processed = True
            if geometry_types:
                # Use the most common geometry type
                most_common_type = max(geometry_types, key=list(geometry_types).count)
                self.master_plan_layer.geometry_type = most_common_type
            self.master_plan_layer.save()
        
        self.stdout.write(f'\n  ✅ Total features created: {total_features}')
        if geometry_types:
            self.stdout.write(f'  📐 Geometry types found: {", ".join(geometry_types)}')

    def process_single_file(self, file_path):
        """Process a single GeoJSON/JSON file and return (features_added, geometry_type)"""
        features_added = 0
        first_geom_type = None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different GeoJSON structures
            if data.get('type') == 'FeatureCollection':
                features = data.get('features', [])
            elif data.get('type') == 'Feature':
                features = [data]
            else:
                self.stdout.write(f'    ⚠️ Unsupported GeoJSON type: {data.get("type")}')
                return 0, None
            
            # Determine category based on filename
            category = self.determine_category_from_filename(file_path.stem)
            
            for idx, feature_data in enumerate(features):
                try:
                    # Extract geometry
                    geometry_data = feature_data.get('geometry')
                    if not geometry_data:
                        continue
                    
                    # Create GEOS geometry
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
                    
                    # Track geometry type
                    if not first_geom_type:
                        first_geom_type = self.get_geometry_type(feature_data)
                    
                except Exception as e:
                    self.stdout.write(f'    ⚠️ Error processing feature {idx}: {str(e)}')
                    continue
            
            self.stdout.write(f'    ✅ Added {features_added} features from {file_path.name}')
            return features_added, first_geom_type
            
        except Exception as e:
            self.stdout.write(f'    ❌ Error reading file {file_path.name}: {str(e)}')
            return 0, None



    def create_city_layer_styles(self):
        """Create city-specific layer styles for Kochi"""
        self.stdout.write('Creating city-specific layer styles...')
        
        # Define styles for different feature types
        styles = [
            {
                'category': self.categories['BOUNDARIES'],
                'fill_color': '#800080',
                'stroke_color': '#4B0082',
                'stroke_width': 2,
                'opacity': 0.8,
                'fill_pattern': 'SOLID'
            },
            {
                'category': self.categories['PLANNING'],
                'fill_color': '#FFE4B5',
                'stroke_color': '#DAA520',
                'stroke_width': 1,
                'opacity': 0.7,
                'fill_pattern': 'SOLID'
            },
            {
                'category': self.categories['RESIDENTIAL'],
                'fill_color': '#FFB6C1',
                'stroke_color': '#FF69B4',
                'stroke_width': 1,
                'opacity': 0.7,
                'fill_pattern': 'SOLID'
            },
            {
                'category': self.categories['COMMERCIAL'],
                'fill_color': '#FFD700',
                'stroke_color': '#B8860B',
                'stroke_width': 1,
                'opacity': 0.7,
                'fill_pattern': 'SOLID'
            },
            {
                'category': self.categories['INDUSTRIAL'],
                'fill_color': '#D2691E',
                'stroke_color': '#A0522D',
                'stroke_width': 1,
                'opacity': 0.7,
                'fill_pattern': 'SOLID'
            },
            {
                'category': self.categories['MIXED_USE'],
                'fill_color': '#9370DB',
                'stroke_color': '#663399',
                'stroke_width': 1,
                'opacity': 0.7,
                'fill_pattern': 'SOLID'
            },
            {
                'category': self.categories['UNCLASSIFIED'],
                'fill_color': '#CCCCCC',
                'stroke_color': '#999999',
                'stroke_width': 1,
                'opacity': 0.6,
                'fill_pattern': 'SOLID'
            }
        ]
        
        for style_data in styles:
            style, created = CityLayerStyle.objects.get_or_create(
                city=self.city,
                category=style_data['category'],
                defaults=style_data
            )
            
            if created:
                self.stdout.write(f'  ✅ Created style for {style_data["category"].name}')
            else:
                self.stdout.write(f'  ✅ Found existing style for {style_data["category"].name}')

    def create_zone_mappings(self):
        """Create zone mappings for Kochi"""
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
                self.stdout.write(f'  ✅ Created zone mapping for {source_layer}')
            else:
                self.stdout.write(f'  ✅ Updated zone mapping for {source_layer}')

    def print_summary(self):
        """Print summary of inserted data"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('📊 KOCHI MASTER PLAN DATA SUMMARY'))
        self.stdout.write('='*60)
        
        # Count features by type
        feature_counts = {}
        total_features = 0
        
        for feature_type in self.categories.keys():
            count = GeoFeature.objects.filter(
                layer=self.master_plan_layer,
                zone_category=feature_type
            ).count()
            
            if count > 0:
                feature_counts[feature_type] = count
                total_features += count
        
        self.stdout.write(f'🏙️  City: {self.city.name}, {self.state.name}')
        self.stdout.write(f'📁 Data Layer: {self.master_plan_layer.name}')
        self.stdout.write(f'📊 Total Features: {total_features}')
        self.stdout.write(f'📂 Source Directory: {self.data_dir}')
        
        self.stdout.write('\n📋 Features by Type:')
        for feature_type, count in feature_counts.items():
            category_name = self.categories[feature_type].name
            self.stdout.write(f'  • {category_name}: {count} features')
        
        self.stdout.write('\n🎨 Layer Styles:')
        styles = CityLayerStyle.objects.filter(
            city=self.city
        )
        
        for style in styles:
            self.stdout.write(f'  • {style.category.name}: {style.fill_color} (opacity: {style.opacity})')
        
        self.stdout.write('\n🌐 Access URLs:')
        self.stdout.write(f'  • API: /api/tiles/{self.state.slug}/{self.city.slug}/{self.master_plan_layer.slug}/')
        self.stdout.write(f'  • Map: /maps/{self.state.slug}/{self.city.slug}/')
        
        self.stdout.write('='*60)

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

    def safe_float(self, value):
        """Safely convert value to float"""
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def safe_int(self, value):
        """Safely convert value to int"""
        if value is None or value == '':
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
                
    def extract_feature_name(self, properties, source_name, index):
        """Extract a meaningful name for the feature"""
        # Try various common name fields
        name_fields = ['Name', 'name', 'NAME', 'City_Name', 'Zone_Name', 
                      'PLU_NAME', 'PLU_prop_l', 'zone_name', 'ZONE_NAME']
        
        for field in name_fields:
            if field in properties and properties[field]:
                return str(properties[field])
        
        # Try ID fields
        id_fields = ['OBJECTID', 'FID', 'id', 'ID', 'Id']
        for field in id_fields:
            if field in properties and properties[field]:
                return f"{source_name} - {field} {properties[field]}"
        
        # Fallback to source name and index
        return f"{source_name} - Feature {index + 1}"

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