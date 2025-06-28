# maps/management/commands/import_vizag.py

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from maps.services import DataImportService
from maps.models import City, DataLayer, GeoFeature
import os
from pathlib import Path


class Command(BaseCommand):
    help = 'Import all Vizag GeoJSON files from a directory'

    def add_arguments(self, parser):
        parser.add_argument(
            'data_directory',
            type=str,
            help='Path to directory containing Vizag GeoJSON files'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reimport - delete existing Vizag data first',
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

    def handle(self, *args, **options):
        data_directory = options['data_directory']
        force = options['force']
        dry_run = options['dry_run']
        specific_files = options['files']
        setup_city = options['setup_city']

        # Validate data directory
        data_path = Path(data_directory)
        if not data_path.exists():
            raise CommandError(f"Directory does not exist: {data_directory}")

        if not data_path.is_dir():
            raise CommandError(f"Path is not a directory: {data_directory}")

        # Setup city and categories first if requested
        if setup_city:
            self.setup_vizag_city()

        # Check for existing Vizag data
        try:
            city = City.objects.get(slug='vizag')
            existing_layers = DataLayer.objects.filter(city=city).count()
            existing_features = GeoFeature.objects.filter(layer__city=city).count()
            
            if existing_layers > 0 or existing_features > 0:
                if force:
                    self.stdout.write(
                        self.style.WARNING(f"🧹 Deleting existing Vizag data: {existing_layers} layers, {existing_features} features")
                    )
                    if not dry_run:
                        GeoFeature.objects.filter(layer__city=city).delete()
                        DataLayer.objects.filter(city=city).delete()
                else:
                    self.stdout.write(
                        self.style.WARNING(f"⚠️  Existing Vizag data found: {existing_layers} layers, {existing_features} features")
                    )
                    self.stdout.write("Use --force to delete existing data and reimport")
                    return
        except City.DoesNotExist:
            if not setup_city:
                raise CommandError("Vizag city not found. Use --setup-city to create it first.")

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
                self.stdout.write(f"   • {file_path.name}")
            return

        # Import data
        try:
            self.stdout.write(f"🚀 Starting Vizag data import from: {data_directory}")
            
            # Use the existing bulk import service
            service = DataImportService()
            
            with transaction.atomic():
                result = service.bulk_import_city('vizag', str(data_directory))
            
            # Display results
            self.display_import_results(result)
            
        except Exception as e:
            raise CommandError(f"Import failed: {str(e)}")

    def setup_vizag_city(self):
        """Setup Vizag city and required categories"""
        self.stdout.write("🏙️  Setting up Vizag city and categories...")
        
        from django.core.management import call_command
        from io import StringIO
        
        # Capture setup output
        out = StringIO()
        call_command('setup_cities', '--with-plu', stdout=out)
        
        self.stdout.write(self.style.SUCCESS("✅ City and categories setup completed"))

    def display_import_results(self, result):
        """Display formatted import results"""
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("📊 VIZAG IMPORT COMPLETED"))
        self.stdout.write("="*60)
        
        self.stdout.write(f"🏙️  City: {result['city']}")
        self.stdout.write(f"📁 Total files configured: {result['total_files']}")
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
            elif status == 'not_found':
                failed += 1
                self.stdout.write(
                    self.style.WARNING(f"   ⚠️  {filename:<40} → FILE NOT FOUND")
                )
        
        # Summary
        self.stdout.write(f"\n📈 Summary:")
        self.stdout.write(f"   • Successful imports: {successful}")
        self.stdout.write(f"   • Failed imports: {failed}")
        self.stdout.write(f"   • Success rate: {(successful/(successful+failed)*100):.1f}%" if (successful+failed) > 0 else "   • Success rate: N/A")
        
        if result['total_features'] > 0:
            self.stdout.write(self.style.SUCCESS(f"\n🎉 Vizag data import completed successfully!"))
            self.stdout.write(f"📍 Visit your map to view the imported data")
        else:
            self.stdout.write(self.style.WARNING(f"\n⚠️  No features were imported"))

    def handle_error(self, error_msg):
        """Handle and display errors consistently"""
        self.stdout.write(self.style.ERROR(f"❌ Error: {error_msg}"))
        raise CommandError(error_msg)