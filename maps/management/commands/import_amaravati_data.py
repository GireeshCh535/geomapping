# maps/management/commands/import_amaravati_data.py
"""
Management command to import Amaravati GeoJSON data with symbology-based categorization
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from maps.services import DataImportService
from maps.models import City, DataLayer, GeoFeature, LayerCategory
import os
import json
from pathlib import Path


class Command(BaseCommand):
    help = 'Import Amaravati GeoJSON files with symbology-based categorization'

    def add_arguments(self, parser):
        parser.add_argument(
            'data_directory',
            type=str,
            help='Path to directory containing Amaravati GeoJSON files'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reimport - delete existing Amaravati data first',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing',
        )
        parser.add_argument(
            '--files',
            nargs='+',
            help='Import only specific files (provide filenames)',
        )
        parser.add_argument(
            '--setup-city',
            action='store_true',
            help='Setup city and categories first',
        )
        parser.add_argument(
            '--analyze-symbology',
            action='store_true',
            help='Analyze symbology values in files without importing',
        )

    def handle(self, *args, **options):
        data_directory = options['data_directory']
        force = options['force']
        dry_run = options['dry_run']
        specific_files = options['files']
        setup_city = options['setup_city']
        analyze_symbology = options['analyze_symbology']

        # Validate data directory
        data_path = Path(data_directory)
        if not data_path.exists():
            raise CommandError(f"Directory does not exist: {data_directory}")

        if not data_path.is_dir():
            raise CommandError(f"Path is not a directory: {data_directory}")

        # Setup city and categories first if requested
        if setup_city:
            self.setup_amaravati_city()

        # Analyze symbology if requested
        if analyze_symbology:
            self.analyze_symbology_values(data_path, specific_files)
            return

        # Check for existing Amaravati data
        try:
            city = City.objects.get(slug='amaravati')
            existing_layers = DataLayer.objects.filter(city=city).count()
            existing_features = GeoFeature.objects.filter(layer__city=city).count()
            
            if existing_layers > 0 or existing_features > 0:
                if force:
                    self.stdout.write(
                        self.style.WARNING(f"🧹 Deleting existing Amaravati data: {existing_layers} layers, {existing_features} features")
                    )
                    if not dry_run:
                        GeoFeature.objects.filter(layer__city=city).delete()
                        DataLayer.objects.filter(city=city).delete()
                else:
                    self.stdout.write(
                        self.style.WARNING(f"⚠️  Existing Amaravati data found: {existing_layers} layers, {existing_features} features")
                    )
                    self.stdout.write("Use --force to delete existing data and reimport")
                    return
        except City.DoesNotExist:
            if not setup_city:
                raise CommandError("Amaravati city not found. Use --setup-city to create it first.")

        # Get list of GeoJSON files
        geojson_files = list(data_path.glob("*.geojson"))
        
        if not geojson_files:
            raise CommandError(f"No GeoJSON files found in: {data_directory}")

        # Filter specific files if requested
        if specific_files:
            filtered_files = []
            for filename in specific_files:
                file_path = data_path / filename
                if file_path.exists():
                    filtered_files.append(file_path)
                else:
                    self.stdout.write(
                        self.style.WARNING(f"⚠️  File not found: {filename}")
                    )
            geojson_files = filtered_files

        self.stdout.write(f"📁 Found {len(geojson_files)} GeoJSON files to import")
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS("🔍 DRY RUN - Files that would be imported:"))
            for file_path in geojson_files:
                # Quick analysis of file
                symbology_count = self.analyze_file_symbology(file_path)
                self.stdout.write(f"   • {file_path.name} ({symbology_count} unique symbology values)")
            return

        # Import data using bulk import
        try:
            self.stdout.write(f"🚀 Starting Amaravati data import from: {data_directory}")
            
            # Use enhanced import method
            result = self.bulk_import_amaravati_files(geojson_files)
            
            # Display results
            self.display_import_results(result)
            
        except Exception as e:
            raise CommandError(f"Import failed: {str(e)}")

    def setup_amaravati_city(self):
        """Setup Amaravati city and required categories"""
        self.stdout.write("🏙️  Setting up Amaravati city and categories...")
        
        from django.core.management import call_command
        from io import StringIO
        
        # Capture setup output
        out = StringIO()
        call_command('setup_cities', '--with-plu', stdout=out)
        
        self.stdout.write(self.style.SUCCESS("✅ City and categories setup completed"))

    def analyze_symbology_values(self, data_path, specific_files=None):
        """Analyze symbology values across all files"""
        
        self.stdout.write("🔍 Analyzing symbology values in all files...")
        
        geojson_files = list(data_path.glob("*.geojson"))
        if specific_files:
            geojson_files = [data_path / f for f in specific_files if (data_path / f).exists()]
        
        all_symbology = {}
        
        for file_path in geojson_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                features = data.get('features', [])
                file_symbology = {}
                
                for feature in features:
                    props = feature.get('properties', {})
                    symbology = props.get('symbology', 'Unknown')
                    
                    if symbology not in file_symbology:
                        file_symbology[symbology] = 0
                    file_symbology[symbology] += 1
                    
                    if symbology not in all_symbology:
                        all_symbology[symbology] = {'total': 0, 'files': set()}
                    all_symbology[symbology]['total'] += 1
                    all_symbology[symbology]['files'].add(file_path.name)
                
                self.stdout.write(f"\n📄 {file_path.name}:")
                for symbology, count in sorted(file_symbology.items()):
                    self.stdout.write(f"   • {symbology}: {count} features")
                    
            except Exception as e:
                self.stdout.write(f"   ❌ Error reading {file_path.name}: {e}")
        
        # Summary
        self.stdout.write(f"\n📊 OVERALL SYMBOLOGY SUMMARY:")
        self.stdout.write(f"   Total unique symbology values: {len(all_symbology)}")
        
        for symbology, info in sorted(all_symbology.items()):
            files_list = ', '.join(sorted(info['files']))
            self.stdout.write(f"   • '{symbology}': {info['total']} features across {len(info['files'])} files")
            if len(info['files']) <= 3:
                self.stdout.write(f"     Files: {files_list}")

    def analyze_file_symbology(self, file_path):
        """Quick analysis of symbology values in a single file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            features = data.get('features', [])
            symbology_values = set()
            
            for feature in features:
                props = feature.get('properties', {})
                symbology = props.get('symbology', 'Unknown')
                symbology_values.add(symbology)
            
            return len(symbology_values)
        except:
            return 0

    def bulk_import_amaravati_files(self, geojson_files):
        """Import multiple GeoJSON files for Amaravati with enhanced processing"""
        
        city = City.objects.get(slug='amaravati')
        results = []
        
        import_service = DataImportService()
        
        self.stdout.write(f"\n🏙️  Processing Amaravati data: {len(geojson_files)} files")
        
        for i, file_path in enumerate(geojson_files, 1):
            self.stdout.write(f"\n📂 [{i}/{len(geojson_files)}] Processing: {file_path.name}")
            
            try:
                # Determine category for this file
                # For Amaravati, we'll analyze the symbology values and use the most common one
                category = self.determine_file_category(file_path)
                
                if not category:
                    self.stdout.write(f"   ⚠️  Could not determine category for {file_path.name}, skipping")
                    results.append({
                        'filename': file_path.name,
                        'status': 'error',
                        'error': 'Could not determine category',
                        'features_imported': 0
                    })
                    continue
                
                self.stdout.write(f"   🎯 Using category: {category.name}")
                
                # Import file
                with open(file_path, 'rb') as f:
                    from django.core.files import File
                    django_file = File(f)
                    django_file.name = file_path.name
                    
                    result = import_service.import_file(django_file, city, category)
                    result['filename'] = file_path.name
                    result['category_code'] = category.code
                    
                    results.append(result)
                    
                    self.stdout.write(f"   ✅ Success: {result['features_imported']} features imported")
                    
            except Exception as e:
                error_result = {
                    'filename': file_path.name,
                    'status': 'error',
                    'error': str(e),
                    'features_imported': 0
                }
                results.append(error_result)
                self.stdout.write(f"   ❌ Error: {file_path.name} - {e}")
        
        total_features = sum(r.get('features_imported', 0) for r in results)
        successful_files = len([r for r in results if r.get('status') == 'success'])
        
        return {
            'city': 'amaravati',
            'total_files': len(geojson_files),
            'imported_files': successful_files,
            'total_features': total_features,
            'results': results
        }

    def determine_file_category(self, file_path):
        """Determine the primary category for a file based on symbology analysis"""
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Get configuration for Amaravati
            from maps.config import get_city_config
            config = get_city_config('amaravati')
            category_mappings = config.get('category_mappings', {})
            
            features = data.get('features', [])
            symbology_counts = {}
            
            # Count symbology occurrences
            for feature in features:
                props = feature.get('properties', {})
                symbology = props.get('symbology', 'Unknown')
                
                if symbology in symbology_counts:
                    symbology_counts[symbology] += 1
                else:
                    symbology_counts[symbology] = 1
            
            if not symbology_counts:
                return None
            
            # Find the most common symbology
            most_common_symbology = max(symbology_counts, key=symbology_counts.get)
            
            # Map to category
            if most_common_symbology in category_mappings:
                category_code = category_mappings[most_common_symbology]
                try:
                    return LayerCategory.objects.get(code=category_code)
                except LayerCategory.DoesNotExist:
                    self.stdout.write(f"   ⚠️  Category not found: {category_code}")
                    return None
            else:
                self.stdout.write(f"   ⚠️  Unknown symbology: {most_common_symbology}")
                return None
                
        except Exception as e:
            self.stdout.write(f"   ❌ Error analyzing file: {e}")
            return None

    def display_import_results(self, result):
        """Display formatted import results"""
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("📊 AMARAVATI IMPORT COMPLETED"))
        self.stdout.write("="*60)
        
        self.stdout.write(f"🏙️  City: {result['city']}")
        self.stdout.write(f"📁 Total files processed: {result['total_files']}")
        self.stdout.write(f"✅ Successfully imported: {result['imported_files']}")
        self.stdout.write(f"🗺️  Total features imported: {result['total_features']:,}")
        
        # Show detailed results
        self.stdout.write("\n📋 Detailed Results:")
        successful = 0
        failed = 0
        
        for file_result in result['results']:
            filename = file_result['filename']
            status = file_result.get('status', 'unknown')
            features = file_result.get('features_imported', 0)
            category = file_result.get('category_code', 'unknown')
            
            if status == 'success':
                successful += 1
                self.stdout.write(
                    f"   ✅ {filename:<40} → {category:<15} ({features:,} features)"
                )
            elif status == 'error':
                failed += 1
                error = file_result.get('error', 'Unknown error')
                self.stdout.write(
                    self.style.ERROR(f"   ❌ {filename:<40} → ERROR: {error}")
                )
        
        # Summary
        self.stdout.write(f"\n📈 Summary:")
        self.stdout.write(f"   • Successful imports: {successful}")
        self.stdout.write(f"   • Failed imports: {failed}")
        success_rate = (successful/(successful+failed)*100) if (successful+failed) > 0 else 0
        self.stdout.write(f"   • Success rate: {success_rate:.1f}%")
        
        if result['total_features'] > 0:
            self.stdout.write(self.style.SUCCESS(f"\n🎉 Amaravati data import completed successfully!"))
            self.stdout.write(f"📍 Next steps:")
            self.stdout.write(f"   1. Generate tiles: python manage.py generate_city_tiles --city=amaravati")
            self.stdout.write(f"   2. Validate data: python manage.py validate_import --city=amaravati")
            self.stdout.write(f"   3. Test API: curl http://localhost:8000/api/cities/amaravati/layers/")
        else:
            self.stdout.write(self.style.WARNING(f"\n⚠️  No features were imported"))