# Replace your import_warangal_data.py with this simpler version that uses existing methods

from django.core.management.base import BaseCommand
from django.utils import timezone
from maps.services import DataImportService
from maps.models import City, LayerCategory, DataLayer, ImportJob
from maps.config import WARANGAL_CONFIG
from pathlib import Path
import os
import time

class Command(BaseCommand):
    help = 'Import Warangal GeoJSON data from directory'
    
    def add_arguments(self, parser):
        parser.add_argument('--data-dir', required=True, help='Directory containing Warangal GeoJSON files')
        parser.add_argument('--file', help='Import only specific file (e.g., Agriculture.geojson)')
        parser.add_argument('--force', action='store_true', help='Force re-import existing layers')
        parser.add_argument('--validate-only', action='store_true', help='Only validate files, don\'t import')
        parser.add_argument('--setup-styles', action='store_true', help='Setup city styles after import')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be imported without importing')
    
    def handle(self, *args, **options):
        data_dir = options['data_dir']
        specific_file = options.get('file')
        
        # Validate data directory
        if not os.path.exists(data_dir):
            self.stdout.write(self.style.ERROR(f"❌ Directory not found: {data_dir}"))
            return
        
        self.stdout.write(self.style.SUCCESS("🏛️  WARANGAL DATA IMPORT"))
        self.stdout.write(f"📂 Data directory: {data_dir}")
        
        start_time = time.time()
        
        # Initialize import service
        import_service = DataImportService()
        
        try:
            if specific_file:
                self._import_single_file(import_service, data_dir, specific_file, options)
            else:
                # Use the existing bulk_import_city method
                self.stdout.write(f"🚀 Starting bulk import for Warangal...")
                result = import_service.bulk_import_city('warangal', data_dir)
                self._display_bulk_results(result)
            
            # Setup styles if requested
            if options['setup_styles'] and not options['validate_only'] and not options['dry_run']:
                self._setup_warangal_styles()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Import failed: {str(e)}"))
            import traceback
            self.stdout.write(traceback.format_exc())
            return
        
        total_time = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(f"\n🎉 Import completed in {total_time:.1f} seconds!"))
    
    def _import_single_file(self, import_service, data_dir, filename, options):
        """Import a single file"""
        file_path = os.path.join(data_dir, filename)
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"❌ File not found: {filename}"))
            return
        
        # Get category from config
        config = WARANGAL_CONFIG
        if filename not in config['file_mappings']:
            self.stdout.write(self.style.WARNING(f"⚠️  File not in configuration: {filename}"))
            return
        
        if options['dry_run']:
            category_code = config['file_mappings'][filename]
            self.stdout.write(f"🔍 Would import: {filename} -> {category_code}")
            return
        
        if options['validate_only']:
            self._validate_file(file_path, filename)
            return
        
        # Import the file using existing method
        self.stdout.write(f"\n📄 Importing: {filename}")
        try:
            result = import_service.import_file_with_config(file_path, 'warangal')
            features_imported = result.get('features_imported', 0)
            self.stdout.write(self.style.SUCCESS(f"   ✅ Imported {features_imported} features"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Error importing {filename}: {str(e)}"))
    
    def _display_bulk_results(self, result):
        """Display results from bulk import"""
        if not result:
            self.stdout.write(self.style.ERROR("❌ No results returned from import"))
            return
        
        self.stdout.write(f"\n📊 Import Summary:")
        self.stdout.write(f"   City: {result.get('city', 'Unknown')}")
        self.stdout.write(f"   Total files configured: {result.get('total_files', 0)}")
        self.stdout.write(f"   Successfully imported: {result.get('imported_files', 0)}")
        self.stdout.write(f"   Total features imported: {result.get('total_features', 0)}")
        
        # Show detailed results if available
        if 'results' in result:
            self.stdout.write(f"\n📄 File Details:")
            for file_result in result['results']:
                filename = file_result.get('filename', 'Unknown')
                status = file_result.get('status', 'unknown')
                features = file_result.get('features_imported', 0)
                
                if status == 'success':
                    self.stdout.write(f"   ✅ {filename}: {features} features")
                elif status == 'error':
                    error = file_result.get('error', 'Unknown error')
                    self.stdout.write(f"   ❌ {filename}: {error}")
                elif status == 'not_found':
                    self.stdout.write(f"   ⚠️  {filename}: File not found")
                else:
                    self.stdout.write(f"   ❓ {filename}: {status}")
    
    def _validate_file(self, file_path, filename):
        """Validate a GeoJSON file"""
        try:
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Basic validation
            if 'type' not in data or data['type'] != 'FeatureCollection':
                self.stdout.write(f"   ❌ {filename}: Not a valid FeatureCollection")
                return
            
            features = data.get('features', [])
            if not features:
                self.stdout.write(f"   ⚠️  {filename}: No features found")
                return
            
            # Check first feature structure
            first_feature = features[0]
            if 'geometry' not in first_feature or 'properties' not in first_feature:
                self.stdout.write(f"   ❌ {filename}: Invalid feature structure")
                return
            
            # Check for PLU fields
            props = first_feature['properties']
            plu_fields = ['PLU', 'PLU_NAME']
            missing_plu = [field for field in plu_fields if field not in props]
            
            if missing_plu:
                self.stdout.write(f"   ⚠️  {filename}: Missing PLU fields: {missing_plu}")
            
            self.stdout.write(f"   ✅ {filename}: Valid ({len(features)} features)")
            
        except json.JSONDecodeError as e:
            self.stdout.write(f"   ❌ {filename}: Invalid JSON - {str(e)}")
        except Exception as e:
            self.stdout.write(f"   ❌ {filename}: Validation error - {str(e)}")
    
    def _setup_warangal_styles(self):
        """Setup Warangal-specific styling"""
        self.stdout.write(f"\n🎨 Setting up Warangal styles...")
        
        try:
            from maps.models import CityLayerStyle
            config = WARANGAL_CONFIG
            
            city = City.objects.get(slug='warangal')
            
            # Create styles for each category
            for category_code, color in config['colors'].items():
                try:
                    category = LayerCategory.objects.get(code=category_code)
                    
                    style, created = CityLayerStyle.objects.get_or_create(
                        city=city,
                        category=category,
                        defaults={
                            'fill_color': color,
                            'stroke_color': self._darken_color(color),
                            'fill_opacity': 0.7,
                            'stroke_opacity': 1.0,
                            'stroke_width': 1,
                        }
                    )
                    
                    if created:
                        self.stdout.write(f"   🎯 Created style for {category.name}: {color}")
                    
                except LayerCategory.DoesNotExist:
                    self.stdout.write(f"   ⚠️  Category not found: {category_code}")
            
            self.stdout.write(self.style.SUCCESS(f"✅ Warangal styles setup complete"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error setting up styles: {str(e)}"))
    
    def _darken_color(self, hex_color):
        """Darken a hex color for stroke"""
        if not hex_color.startswith('#'):
            hex_color = '#' + hex_color
        
        try:
            # Convert hex to RGB
            hex_color = hex_color.lstrip('#')
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            
            # Darken by 20%
            darkened_rgb = tuple(max(0, int(c * 0.8)) for c in rgb)
            
            # Convert back to hex
            return '#' + ''.join(f'{c:02x}' for c in darkened_rgb)
        except:
            return '#333333'  # Fallback dark color