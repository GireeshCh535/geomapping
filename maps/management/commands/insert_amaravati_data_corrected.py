"""
Django management command to insert Amaravati master plan data - CORRECTED VERSION
This creates ONE layer with all 40 files under it, not 40 separate layers
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
    help = 'Insert Amaravati master plan data into the database - CORRECTED VERSION'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Delete existing Amaravati data before inserting new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting Amaravati Master Plan Data Insertion - CORRECTED')
        )
        
        try:
            with transaction.atomic():
                # Setup basic entities
                self.setup_state_and_city()
                self.setup_layer_categories()
                
                # Delete existing data if requested
                if options['delete_existing']:
                    self.delete_existing_amaravati_data()
                
                # Create the SINGLE master plan layer
                self.create_master_plan_layer()
                
                # Create styles for all zone types
                self.create_city_layer_styles()
                
                # Process all files into the single layer
                self.process_all_files_into_single_layer()
                
                # Calculate bounds
                self.calculate_layer_bounds()
            
            self.stdout.write(
                self.style.SUCCESS('\n✅ AMARAVATI DATA INSERTION COMPLETED SUCCESSFULLY!')
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
            code='AP',
            defaults={
                'name': 'Andhra Pradesh',
                'slug': 'andhra-pradesh',
                'center_lat': 15.9129,
                'center_lng': 79.7400,
                'default_zoom': 7
            }
        )
        if created:
            self.stdout.write(f"  ✅ Created state: {self.state.name}")
        else:
            self.stdout.write(f"  📍 Found existing state: {self.state.name}")
        
        # Create/update City
        self.city, created = City.objects.get_or_create(
            slug='amaravati',
            defaults={
                'name': 'Amaravati',
                'state': 'Andhra Pradesh',
                'state_ref': self.state,
                'center_lat': 16.5740,
                'center_lng': 80.3586,
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
            ('RESIDENTIAL', 'Residential', 'Residential zones and housing areas'),
            ('COMMERCIAL', 'Commercial', 'Commercial and business zones'),
            ('MIXED_USE', 'Mixed Use', 'Mixed use development zones'),
            ('INDUSTRIAL', 'Industrial', 'Industrial and manufacturing zones'),
            ('GOVERNMENT', 'Government', 'Government and administrative zones'),
            ('EDUCATION', 'Education', 'Educational institutions and zones'),
            ('HEALTH', 'Health', 'Healthcare facilities and zones'),
            ('CULTURAL', 'Cultural', 'Cultural and heritage zones'),
            ('PARKS_GREEN', 'Parks & Green Spaces', 'Parks, gardens, and green areas'),
            ('PROTECTED', 'Protected/Forest', 'Protected areas and forests'),
            ('TRANSPORT', 'Transportation', 'Transportation infrastructure'),
            ('BURIAL', 'Burial/Cemetery', 'Burial grounds and cemeteries'),
            ('UNCLASSIFIED', 'Unclassified', 'Unclassified or special zones'),
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

    def delete_existing_amaravati_data(self):
        """Delete existing Amaravati data to start fresh"""
        self.stdout.write("🗑️ Deleting existing Amaravati data...")
        
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

    def create_master_plan_layer(self):
        """Create the single master plan layer"""
        self.stdout.write("📁 Creating master plan layer...")
        
        # Get the main category (we'll use MIXED_USE as default since it contains multiple zone types)
        main_category = LayerCategory.objects.get(code='MIXED_USE')
        
        # Get all GeoJSON files
        data_dir = Path("data/andhra_pradesh/amaravati/master_plan")
        geojson_files = list(data_dir.glob("*.geojson"))
        
        # Create the single layer
        self.master_plan_layer, created = DataLayer.objects.get_or_create(
            city=self.city,
            slug='amaravati_master_plan',
            defaults={
                'name': 'Amaravati Master Plan',
                'description': 'Complete master plan data for Amaravati city with all 40 zones',
                'category': main_category,
                'file_format': 'GEOJSON',
                'file_path': str(data_dir),
                'is_directory': True,
                'file_pattern': '*.geojson',
                'source_files': [str(f) for f in geojson_files],
                'categorization_method': 'FILENAME',
                'geometry_type': 'POLYGON',
                'is_processed': False,
                'feature_count': 0
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Created master plan layer: {self.master_plan_layer.name}")
            self.stdout.write(f"  📊 Layer contains {len(geojson_files)} source files")
        else:
            self.stdout.write(f"  📍 Found existing master plan layer: {self.master_plan_layer.name}")

    def create_city_layer_styles(self):
        """Create city-specific layer styles for all zone types"""
        self.stdout.write("🎨 Creating city layer styles...")
        
        # Zone to category mapping
        zone_category_mapping = {
            'C1__Mixed_use_zone': 'MIXED_USE',
            'C2__General_commercial_zone': 'COMMERCIAL',
            'C3_Neighbourhood_centre_zone': 'COMMERCIAL',
            'C4_Town_centre_zone': 'COMMERCIAL',
            'C5_Regional_centre_zone': 'COMMERCIAL',
            'C6_Central_business_district_zone': 'COMMERCIAL',
            'Commercial_Vacant': 'COMMERCIAL',
            'I1_Business_park_zone': 'INDUSTRIAL',
            'I2_Logistics_zone': 'INDUSTRIAL',
            'I3_Non_polluting_industry_zone': 'INDUSTRIAL',
            'P1_Passive_zone': 'PARKS_GREEN',
            'P2_Active_zone': 'PARKS_GREEN',
            'P3_Protected_zone': 'PROTECTED',
            'P3_Protected_zone_Hills': 'PROTECTED',
            'PGN_G': 'PARKS_GREEN',
            'PGN_V': 'PARKS_GREEN',
            'R1_Village_planning_zone': 'RESIDENTIAL',
            'R3_Medium_to_high_density_zone': 'RESIDENTIAL',
            'R4_High_density_zone': 'RESIDENTIAL',
            'RAA': 'RESIDENTIAL',
            'Residential_Vacant': 'RESIDENTIAL',
            'S2_Education_zone': 'EDUCATION',
            'S3_Special_zone': 'UNCLASSIFIED',
            'SC1a_Mixed_Use': 'MIXED_USE',
            'SC1b___Mixed_Use': 'MIXED_USE',
            'SP1__Passive_Zone': 'PARKS_GREEN',
            'SP2__Active_Zone': 'PARKS_GREEN',
            'SP3_Protected_Zone': 'PROTECTED',
            'SR2_Low_Density_Housing': 'RESIDENTIAL',
            'SR4___High_Density_Private': 'RESIDENTIAL',
            'SS1___Government_Zone': 'GOVERNMENT',
            'SS2a__Education_Zone': 'EDUCATION',
            'SS2b_Cultural_Zone': 'CULTURAL',
            'SS2c_Health_Zone': 'HEALTH',
            'SS3___Special_Zone': 'UNCLASSIFIED',
            'SU1_Reserve_Zone': 'UNCLASSIFIED',
            'SU2___Road_Network': 'TRANSPORT',
            'U1_Reserve_zone': 'UNCLASSIFIED',
            'U2__Road_reserve_zone': 'TRANSPORT',
            'Burial_Ground': 'BURIAL'
        }
        
        # Color mapping (from the tile generator)
        color_mapping = {
            'Burial_Ground': {'fill': '#FFFFFF', 'stroke': '#000000', 'pattern': 'DOTTED', 'pattern_color': '#E39E00'},
            'C1__Mixed_use_zone': {'fill': '#73B2FF', 'stroke': None, 'pattern': 'SOLID'},
            'C2__General_commercial_zone': {'fill': '#00C5FF', 'stroke': '#000000', 'pattern': 'SOLID'},
            'C3_Neighbourhood_centre_zone': {'fill': '#00C5FF', 'stroke': None, 'pattern': 'SOLID'},
            'C4_Town_centre_zone': {'fill': '#00A9E6', 'stroke': None, 'pattern': 'SOLID'},
            'C5_Regional_centre_zone': {'fill': '#0070FF', 'stroke': None, 'pattern': 'SOLID'},
            'C6_Central_business_district_zone': {'fill': '#005CE6', 'stroke': None, 'pattern': 'SOLID'},
            'Commercial_Vacant': {'fill': '#C5E2FF', 'stroke': None, 'pattern': 'SOLID'},
            'I1_Business_park_zone': {'fill': '#FFBEE8', 'stroke': None, 'pattern': 'SOLID'},
            'I2_Logistics_zone': {'fill': '#FF73DF', 'stroke': None, 'pattern': 'SOLID'},
            'I3_Non_polluting_industry_zone': {'fill': '#A900E6', 'stroke': None, 'pattern': 'SOLID'},
            'P1_Passive_zone': {'fill': '#267300', 'stroke': None, 'pattern': 'SOLID'},
            'P2_Active_zone': {'fill': '#38A800', 'stroke': None, 'pattern': 'SOLID'},
            'P3_Protected_zone': {'fill': '#BEE8FF', 'stroke': None, 'pattern': 'SOLID'},
            'P3_Protected_zone_Hills': {'fill': '#4C7300', 'stroke': None, 'pattern': 'SOLID'},
            'PGN_G': {'fill': '#4C7300', 'stroke': None, 'pattern': 'SOLID'},
            'PGN_V': {'fill': '#897044', 'stroke': None, 'pattern': 'SOLID'},
            'R1_Village_planning_zone': {'fill': '#FFFFFF', 'stroke': '#000000', 'pattern': 'HATCHED'},
            'R3_Medium_to_high_density_zone': {'fill': '#F5CA7A', 'stroke': None, 'pattern': 'SOLID'},
            'R4_High_density_zone': {'fill': '#E69800', 'stroke': None, 'pattern': 'SOLID'},
            'RAA': {'fill': '#FFAA00', 'stroke': None, 'pattern': 'SOLID'},
            'Residential_Vacant': {'fill': '#FFD37F', 'stroke': None, 'pattern': 'SOLID'},
            'S2_Education_zone': {'fill': '#FFF7F7', 'stroke': None, 'pattern': 'SOLID'},
            'S3_Special_zone': {'fill': '#D7B09E', 'stroke': None, 'pattern': 'SOLID'},
            'SC1a_Mixed_Use': {'fill': '#0070FF', 'stroke': None, 'pattern': 'SOLID'},
            'SC1b___Mixed_Use': {'fill': '#73B2FF', 'stroke': None, 'pattern': 'SOLID'},
            'SP1__Passive_Zone': {'fill': '#267300', 'stroke': None, 'pattern': 'SOLID'},
            'SP2__Active_Zone': {'fill': '#38A800', 'stroke': None, 'pattern': 'SOLID'},
            'SP3_Protected_Zone': {'fill': '#00C5FF', 'stroke': None, 'pattern': 'SOLID'},
            'SR2_Low_Density_Housing': {'fill': '#FFFFBE', 'stroke': None, 'pattern': 'SOLID'},
            'SR4___High_Density_Private': {'fill': '#FFAA00', 'stroke': None, 'pattern': 'SOLID'},
            'SS1___Government_Zone': {'fill': '#E60000', 'stroke': None, 'pattern': 'SOLID'},
            'SS2a__Education_Zone': {'fill': '#FFF7F7', 'stroke': None, 'pattern': 'SOLID'},
            'SS2b_Cultural_Zone': {'fill': '#C500FF', 'stroke': None, 'pattern': 'SOLID'},
            'SS2c_Health_Zone': {'fill': '#D3FFBE', 'stroke': None, 'pattern': 'SOLID'},
            'SS3___Special_Zone': {'fill': '#A83800', 'stroke': None, 'pattern': 'SOLID'},
            'SU1_Reserve_Zone': {'fill': '#E1E1E1', 'stroke': None, 'pattern': 'SOLID'},
            'SU2___Road_Network': {'fill': '#FFFFFF', 'stroke': '#000000', 'pattern': 'SOLID'},
            'U1_Reserve_zone': {'fill': '#CCCCCC', 'stroke': None, 'pattern': 'SOLID'},
            'U2__Road_reserve_zone': {'fill': '#000000', 'stroke': None, 'pattern': 'SOLID'}
        }
        
        created_count = 0
        for zone_name, category_code in zone_category_mapping.items():
            try:
                category = LayerCategory.objects.get(code=category_code)
                color_config = color_mapping.get(zone_name, {})
                
                # Create style
                style, created = CityLayerStyle.objects.get_or_create(
                    city=self.city,
                    category=category,
                    defaults={
                        'fill_color': color_config.get('fill', '#CCCCCC'),
                        'stroke_color': color_config.get('stroke') or '#333333',
                        'opacity': 0.7,
                        'stroke_width': 1 if color_config.get('stroke') else 0,
                        'fill_pattern': color_config.get('pattern', 'SOLID'),
                        'pattern_color': color_config.get('pattern_color', ''),
                        'pattern_spacing': 8 if color_config.get('pattern') == 'HATCHED' else 10,
                        'pattern_angle': 45,
                        'pattern_size': 3 if color_config.get('pattern') == 'DOTTED' else 1,
                        'secondary_fill_color': color_config.get('fill', '#FFFFFF') if color_config.get('pattern') in ['HATCHED', 'DOTTED'] else '',
                        'is_visible': True
                    }
                )
                if created:
                    created_count += 1
                    self.stdout.write(f"  ✅ Created style for {zone_name} → {category.name}")
            except LayerCategory.DoesNotExist:
                self.stdout.write(f"  ⚠️ Category not found for {zone_name}: {category_code}")
        
        self.stdout.write(f"  📊 Created {created_count} new layer styles")

    def process_all_files_into_single_layer(self):
        """Process all GeoJSON files into the single master plan layer"""
        self.stdout.write("📁 Processing all GeoJSON files into single layer...")
        
        data_dir = Path("data/andhra_pradesh/amaravati/master_plan")
        if not data_dir.exists():
            self.stdout.write(f"❌ Data directory not found: {data_dir}")
            return
        
        geojson_files = list(data_dir.glob("*.geojson"))
        self.stdout.write(f"  📊 Found {len(geojson_files)} GeoJSON files")
        
        total_features = 0
        for file_path in sorted(geojson_files):
            file_name = file_path.stem
            self.stdout.write(f"  📄 Processing {file_name}...")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    geojson_data = json.load(f)
                
                features = geojson_data.get('features', [])
                self.stdout.write(f"    📊 Processing {len(features)} features...")
                
                file_feature_count = 0
                for feature_data in features:
                    try:
                        # Create geometry
                        geometry = GEOSGeometry(json.dumps(feature_data['geometry']))
                        
                        # Extract properties
                        properties = feature_data.get('properties', {})
                        
                        # Create feature
                        feature = GeoFeature.objects.create(
                            layer=self.master_plan_layer,
                            geometry=geometry,
                            source_layer_name=file_name,  # This will be the zone name
                            name=properties.get('symbology', '') or properties.get('plot_categ', ''),
                            zone_category=properties.get('symbology', '') or properties.get('plot_categ', ''),
                            plot_category=properties.get('plot_categ', ''),
                            symbology=properties.get('symbology', ''),
                            township=properties.get('township'),
                            sector=properties.get('sector'),
                            colony=properties.get('colony'),
                            block=properties.get('block'),
                            area=properties.get('alloted_ex'),
                            shape_length=properties.get('Shape_Length'),
                            shape_area=properties.get('Shape_Area'),
                            objectid=properties.get('OBJECTID'),
                            properties=properties
                        )
                        file_feature_count += 1
                        total_features += 1
                        
                    except Exception as e:
                        self.stdout.write(f"    ⚠️ Error processing feature: {e}")
                        continue
                
                self.stdout.write(f"    ✅ Inserted {file_feature_count} features from {file_name}")
                
            except Exception as e:
                self.stdout.write(f"    ❌ Error processing file {file_name}: {e}")
                continue
        
        # Update layer statistics
        self.master_plan_layer.feature_count = total_features
        self.master_plan_layer.is_processed = True
        self.master_plan_layer.save()
        
        self.stdout.write(f"  ✅ Total features inserted: {total_features}")

    def calculate_layer_bounds(self):
        """Calculate bounding boxes for the layer"""
        self.stdout.write("📐 Calculating layer bounds...")
        
        try:
            self.master_plan_layer.calculate_bbox()
            self.stdout.write(f"  ✅ Calculated bounds for {self.master_plan_layer.name}")
        except Exception as e:
            self.stdout.write(f"  ⚠️ Error calculating bounds: {e}")
