# maps/management/commands/complete_pipeline.py
# Complete pipeline from Excel hierarchy to S3 tiles with pattern support

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import transaction
import json
import os
import time
from datetime import datetime
import logging

from maps.models import City, DataLayer
from maps.services.s3_direct_tile_service import S3DirectTileGenerationService

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Complete pipeline: Setup hierarchy from Excel → Import data → Generate tiles → Upload to S3'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--excel-file',
            type=str,
            default='Untitled spreadsheet.xlsx',
            help='Path to Excel file with hierarchy'
        )
        
        parser.add_argument(
            '--data-path',
            type=str,
            default='data/',
            help='Base path containing all city data folders'
        )
        
        parser.add_argument(
            '--cities',
            nargs='+',
            help='Specific cities to process (e.g., bengaluru hyderabad warangal)'
        )
        
        parser.add_argument(
            '--min-zoom',
            type=int,
            default=8,
            help='Minimum zoom level for tiles'
        )
        
        parser.add_argument(
            '--max-zoom',
            type=int,
            default=14,
            help='Maximum zoom level for tiles'
        )
        
        parser.add_argument(
            '--skip-setup',
            action='store_true',
            help='Skip hierarchy setup (if already done)'
        )
        
        parser.add_argument(
            '--skip-import',
            action='store_true',
            help='Skip data import (if already done)'
        )
        
        parser.add_argument(
            '--skip-tiles',
            action='store_true',
            help='Skip tile generation'
        )
        
        parser.add_argument(
            '--fix-structure',
            action='store_true',
            help='Fix layer structure before processing'
        )
    
    def handle(self, *args, **options):
        """Execute complete pipeline"""
        
        start_time = datetime.now()
        self.stdout.write("=" * 60)
        self.stdout.write("🚀 STARTING COMPLETE PIPELINE")
        self.stdout.write("=" * 60)
        
        cities_to_process = options.get('cities', [])
        
        try:
            # Step 1: Setup hierarchy from Excel
            if not options['skip_setup']:
                self.setup_hierarchy(options['excel_file'], options['data_path'])
            
            # Step 2: Fix structure if needed
            if options['fix_structure']:
                self.fix_layer_structure(cities_to_process)
            
            # Step 3: Import data
            if not options['skip_import']:
                self.import_data(options['data_path'], cities_to_process)
            
            # Step 4: Setup styles (always run to ensure patterns are configured)
            self.setup_styles(cities_to_process)
            
            # Step 5: Generate and upload tiles to S3
            if not options['skip_tiles']:
                self.generate_tiles_to_s3(
                    cities_to_process,
                    options['min_zoom'],
                    options['max_zoom']
                )
            
            # Final report
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            self.stdout.write("=" * 60)
            self.stdout.write(self.style.SUCCESS("✅ PIPELINE COMPLETE"))
            self.stdout.write(f"⏱️  Total time: {duration:.2f} seconds")
            self.stdout.write("=" * 60)
            
            # Show summary
            self.show_summary(cities_to_process)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Pipeline failed: {str(e)}"))
            raise CommandError(str(e))
    
    def setup_hierarchy(self, excel_file: str, data_path: str):
        """Step 1: Setup hierarchy from Excel"""
        
        self.stdout.write("\n" + "="*40)
        self.stdout.write("📋 STEP 1: SETUP HIERARCHY FROM EXCEL")
        self.stdout.write("="*40)
        
        # Call the setup command
        call_command(
            'setup_hierarchy_from_excel',
            excel_file=excel_file,
            data_path=data_path,
            skip_import=True  # We'll import separately
        )
        
        self.stdout.write(self.style.SUCCESS("✅ Hierarchy setup complete"))
    
    def fix_layer_structure(self, cities: list):
        """Step 2: Fix layer structure"""
        
        self.stdout.write("\n" + "="*40)
        self.stdout.write("🔧 STEP 2: FIX LAYER STRUCTURE")
        self.stdout.write("="*40)
        
        cities_to_fix = cities if cities else ['bengaluru', 'hyderabad', 'warangal']
        
        for city_slug in cities_to_fix:
            try:
                self.stdout.write(f"\n🔧 Fixing {city_slug}...")
                call_command('fix_layer_structure', 'consolidate', city=city_slug)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"⚠️  Could not fix {city_slug}: {e}"))
        
        self.stdout.write(self.style.SUCCESS("✅ Structure fix complete"))
    
    def import_data(self, data_path: str, cities: list):
        """Step 3: Import data for all cities"""
        
        self.stdout.write("\n" + "="*40)
        self.stdout.write("📥 STEP 3: IMPORT DATA")
        self.stdout.write("="*40)
        
        # Import data for each city
        cities_to_import = cities if cities else [
            'bengaluru', 'hyderabad', 'warangal', 
            'visakhapatnam', 'amaravati'
        ]
        
        for city_slug in cities_to_import:
            self.import_city_data(city_slug, data_path)
    
    def import_city_data(self, city_slug: str, data_path: str):
        """Import data for a specific city"""
        
        self.stdout.write(f"\n📍 Importing data for {city_slug}...")
        
        try:
            city = City.objects.get(slug=city_slug)
            
            # Find data files for this city
            city_data_paths = [
                os.path.join(data_path, city_slug),
                os.path.join(data_path, city.state_ref.slug if city.state_ref else '', city_slug),
                os.path.join(data_path, f"{city_slug}_data")
            ]
            
            city_data_path = None
            for path in city_data_paths:
                if os.path.exists(path):
                    city_data_path = path
                    break
            
            if not city_data_path:
                self.stdout.write(self.style.WARNING(f"  ⚠️ No data folder found for {city_slug}"))
                return
            
            # Import based on city type
            if city_slug == 'bengaluru':
                self.import_bengaluru_data(city, city_data_path)
            else:
                self.import_standard_geojson(city, city_data_path)
            
        except City.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"  ⚠️ City {city_slug} not found"))
    
    @transaction.atomic
    def import_bengaluru_data(self, city: City, data_path: str):
        """Import Bengaluru ESRI JSON data"""
        
        self.stdout.write("  📂 Processing Bengaluru ESRI JSON data...")
        
        # Bengaluru specific file structure
        layer_groups = {
            'master_plan': {
                'files': [
                    'Agricultural_Land.json',
                    'Commercial_Business_.json',
                    'Commercial_Central_.json',
                    'Defense.json',
                    'Drains.json',
                    'HighTech.json',
                    'Industrial.json',
                    'Lake_Tank.json',
                    'Parks_GreenSpaces_Sports_Playgrounds_Cemetery_BurialGrounds.json',
                    'Power_Water_GarbageFacility_TreatmentPlant.json',
                    'Public_SemiPublic.json',
                    'Residential_Main_.json',
                    'Residential_Mixed_.json',
                    'Road_Rail_Airport_Transport.json',
                    'StateForest_Valley_ProtectedLand_.json',
                    'Unclassified_Use.json'
                ],
                'category': 'MIXED_USE'
            },
            'highways': {
                'files': [
                    'BellaryRoad_NH44.geojson',
                    'BengaluruChennaiExpressway_NE7.geojson',
                    'BengaluruMysuruRoad_NH275.geojson',
                    'HosurRoad_NH48.geojson',
                    'KanakpuraRoad_NH948.geojson',
                    'MadrasRoad_NH75.geojson',
                    'NICE_Road.geojson',
                    'STRR.geojson',
                    'TumakuruRoad_NH48.geojson'
                ],
                'category': 'TRANSPORT'
            },
            'metro': {
                'files': [
                    'Bangalore Metro Phases 1,2,2A&2B.geojson'
                ],
                'category': 'TRANSPORT'
            },
            'workspace': {
                'files': [
                    'Blr_Industrial_Area_processed.geojson'
                ],
                'category': 'INDUSTRIAL'
            }
        }
        
        # Import each layer group
        for layer_group, config in layer_groups.items():
            layer = self.get_or_create_layer(city, layer_group, config['category'])
            
            total_features = 0
            for file_name in config['files']:
                # Try different paths
                file_paths = [
                    os.path.join(data_path, layer_group, file_name),
                    os.path.join(data_path, file_name),
                    os.path.join(data_path, 'master_plan', file_name)
                ]
                
                for file_path in file_paths:
                    if os.path.exists(file_path):
                        features = self.import_esri_json_file(layer, file_path, file_name)
                        total_features += features
                        if features > 0:
                            self.stdout.write(f"    ✅ {file_name}: {features} features")
                        break
            
            # Update layer statistics
            layer.feature_count = total_features
            layer.is_processed = total_features > 0
            layer.save()
            
            self.stdout.write(f"  📁 {layer_group}: {total_features} total features")
    
    def import_esri_json_file(self, layer: DataLayer, file_path: str, source_name: str) -> int:
        """Import ESRI JSON file"""
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            from django.contrib.gis.geos import GEOSGeometry
            from maps.models import GeoFeature
            
            imported = 0
            
            # Handle ESRI format
            if 'features' in data and 'geometryType' in data:
                for feature in data['features']:
                    try:
                        # Get geometry
                        geom = feature.get('geometry', {})
                        
                        # Convert ESRI geometry to GeoJSON
                        if 'rings' in geom:
                            geojson_geom = {
                                'type': 'Polygon',
                                'coordinates': geom['rings']
                            }
                        elif 'paths' in geom:
                            geojson_geom = {
                                'type': 'LineString',
                                'coordinates': geom['paths'][0] if geom['paths'] else []
                            }
                        elif 'x' in geom and 'y' in geom:
                            geojson_geom = {
                                'type': 'Point',
                                'coordinates': [geom['x'], geom['y']]
                            }
                        else:
                            continue
                        
                        geometry = GEOSGeometry(json.dumps(geojson_geom))
                        
                        # Get properties
                        props = feature.get('attributes', {})
                        
                        # Create GeoFeature
                        GeoFeature.objects.create(
                            layer=layer,
                            geometry=geometry,
                            source_layer_name=source_name.replace('.json', ''),
                            
                            # Bengaluru PLU fields
                            plu_primary_code=str(props.get('PLU_Cd', '')),
                            plu_secondary_1=props.get('PLU_prop_l', ''),
                            plu_proposed_use=props.get('PLU_prop_l', ''),
                            plu_development_code=props.get('PLU_F_PD_C'),
                            plu_authority=props.get('PLU_BDA', ''),
                            
                            properties=props,
                            is_valid=True
                        )
                        
                        imported += 1
                        
                    except Exception as e:
                        logger.error(f"Error importing feature: {e}")
                        continue
            
            # Handle standard GeoJSON
            elif data.get('type') == 'FeatureCollection':
                return self.import_geojson_features(layer, data.get('features', []), source_name)
            
            return imported
            
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return 0
    
    def import_standard_geojson(self, city: City, data_path: str):
        """Import standard GeoJSON data"""
        
        import glob
        
        # Find all GeoJSON files
        patterns = [
            os.path.join(data_path, '**/*.geojson'),
            os.path.join(data_path, '**/*.json')
        ]
        
        files = []
        for pattern in patterns:
            files.extend(glob.glob(pattern, recursive=True))
        
        if not files:
            self.stdout.write(f"  ⚠️ No data files found in {data_path}")
            return
        
        self.stdout.write(f"  📂 Found {len(files)} files to import")
        
        # Group files by layer
        # Implementation depends on your folder structure
        # ... (similar to import_bengaluru_data but for standard GeoJSON)
    
    def import_geojson_features(self, layer: DataLayer, features: list, source_name: str) -> int:
        """Import GeoJSON features"""
        
        from django.contrib.gis.geos import GEOSGeometry
        from maps.models import GeoFeature
        
        imported = 0
        
        for feature in features:
            try:
                geometry = GEOSGeometry(json.dumps(feature['geometry']))
                props = feature.get('properties', {})
                
                GeoFeature.objects.create(
                    layer=layer,
                    geometry=geometry,
                    source_layer_name=source_name.replace('.geojson', '').replace('.json', ''),
                    properties=props,
                    is_valid=True
                )
                
                imported += 1
                
            except Exception as e:
                logger.error(f"Error importing feature: {e}")
                continue
        
        return imported
    
    def get_or_create_layer(self, city: City, layer_name: str, category_code: str) -> DataLayer:
        """Get or create a layer"""
        
        from maps.models import LayerCategory, DataLayer
        
        category, _ = LayerCategory.objects.get_or_create(
            code=category_code,
            defaults={'name': category_code.replace('_', ' ').title()}
        )
        
        layer, _ = DataLayer.objects.get_or_create(
            city=city,
            slug=layer_name,
            defaults={
                'name': layer_name.replace('_', ' ').title(),
                'category': category,
                'is_directory': True,
                'categorization_method': 'FILENAME',
                'is_processed': False
            }
        )
        
        return layer
    
    def setup_styles(self, cities: list):
        """Step 4: Setup city styles including patterns"""
        
        self.stdout.write("\n" + "="*40)
        self.stdout.write("🎨 STEP 4: SETUP STYLES")
        self.stdout.write("="*40)
        
        # Import style configurations
        call_command('import_city_styles')
        
        self.stdout.write(self.style.SUCCESS("✅ Styles setup complete"))
    
    def generate_tiles_to_s3(self, cities: list, min_zoom: int, max_zoom: int):
        """Step 5: Generate tiles and upload to S3"""
        
        self.stdout.write("\n" + "="*40)
        self.stdout.write("☁️  STEP 5: GENERATE TILES TO S3")
        self.stdout.write("="*40)
        
        s3_service = S3DirectTileGenerationService()
        
        # Test S3 connection first
        self.stdout.write("\n🔌 Testing S3 connection...")
        connection_test = s3_service.test_connection()
        
        if not connection_test['success']:
            raise CommandError(f"S3 connection failed: {connection_test['error']}")
        
        self.stdout.write(self.style.SUCCESS("✅ S3 connection successful"))
        
        # Generate tiles for each city
        cities_to_process = cities if cities else [
            'bengaluru', 'hyderabad', 'warangal',
            'visakhapatnam', 'amaravati'
        ]
        
        for city_slug in cities_to_process:
            try:
                city = City.objects.get(slug=city_slug)
                
                # Check if city has data
                if not DataLayer.objects.filter(city=city, is_processed=True).exists():
                    self.stdout.write(self.style.WARNING(
                        f"\n⚠️  Skipping {city_slug} - no processed layers"
                    ))
                    continue
                
                self.stdout.write(f"\n🏙️  Generating tiles for {city_slug}...")
                
                # Determine if city has patterns
                use_patterns = city_slug in ['visakhapatnam', 'amaravati']
                
                # Generate tiles
                result = s3_service.generate_and_upload_city_tiles(
                    city_slug=city_slug,
                    min_zoom=min_zoom,
                    max_zoom=max_zoom,
                    tile_types=['png', 'mvt'],
                    use_patterns=use_patterns
                )
                
                if result['success']:
                    stats = result.get('results', {})
                    self.stdout.write(self.style.SUCCESS(
                        f"  ✅ {city_slug}: {stats['generated_tiles']} tiles, "
                        f"{stats['total_size_mb']:.2f} MB"
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f"  ❌ {city_slug}: {result.get('error', 'Unknown error')}"
                    ))
                    
            except City.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  ⚠️ City {city_slug} not found"))
                continue
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ Error processing {city_slug}: {e}"))
                continue
    
    def show_summary(self, cities: list):
        """Show final summary"""
        
        self.stdout.write("\n" + "="*40)
        self.stdout.write("📊 SUMMARY")
        self.stdout.write("="*40)
        
        cities_to_check = cities if cities else City.objects.filter(is_active=True).values_list('slug', flat=True)
        
        for city_slug in cities_to_check:
            try:
                city = City.objects.get(slug=city_slug)
                layers = DataLayer.objects.filter(city=city)
                features = GeoFeature.objects.filter(layer__city=city).count()
                
                self.stdout.write(f"\n{city.name}:")
                self.stdout.write(f"  Layers: {layers.count()}")
                self.stdout.write(f"  Processed: {layers.filter(is_processed=True).count()}")
                self.stdout.write(f"  Features: {features}")
                
            except:
                continue