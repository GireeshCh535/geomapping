# management/commands/import_city_data.py - Import city data from directory

from django.core.management.base import BaseCommand
from django.utils import timezone
from maps.services import DataImportService
from maps.models import City, ImportJob
from pathlib import Path
import os

class Command(BaseCommand):
    help = 'Import geographic data for a city from directory'
    
    def add_arguments(self, parser):
        parser.add_argument('--city', required=True, help='City slug (bangalore, vizag, amaravati)')
        parser.add_argument('--data-dir', required=True, help='Directory containing data files')
        parser.add_argument('--file', help='Import specific file only')
        parser.add_argument('--force', action='store_true', help='Force re-import existing layers')
        parser.add_argument('--validate-only', action='store_true', help='Only validate files, don\'t import')
        parser.add_argument('--setup-styles', action='store_true', help='Setup city styles after import')
    
    def handle(self, *args, **options):
        city_slug = options['city']
        data_dir = options['data_dir']
        specific_file = options.get('file')
        
        # Validate inputs
        if not os.path.exists(data_dir):
            self.stdout.write(self.style.ERROR(f"❌ Directory not found: {data_dir}"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"🚀 Starting import for {city_slug.upper()}"))
        self.stdout.write(f"📂 Data directory: {data_dir}")
        
        # Initialize import service
        import_service = DataImportService()
        
        try:
            if specific_file:
                # Import single file
                result = self._import_single_file(
                    import_service, city_slug, data_dir, specific_file, options
                )
                self._display_single_result(result)
            else:
                # Bulk import all files
                if options['validate_only']:
                    self._validate_files_only(city_slug, data_dir)
                else:
                    result = import_service.bulk_import_city(city_slug, data_dir)
                    self._display_bulk_results(result)
                    
                    # Setup styles if requested
                    if options['setup_styles']:
                        self._setup_styles(import_service, city_slug)
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Import failed: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())
    
    def _import_single_file(self, import_service, city_slug, data_dir, filename, options):
        """Import a single file"""
        file_path = Path(data_dir) / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        self.stdout.write(f"📄 Importing single file: {filename}")
        
        # Check if already imported (unless force)
        if not options['force']:
            try:
                city = City.objects.get(slug=city_slug)
                existing = city.layers.filter(original_filename=filename).first()
                if existing:
                    self.stdout.write(f"⚠️  File already imported: {filename}")
                    self.stdout.write("   Use --force to re-import")
                    return {'status': 'skipped', 'filename': filename}
            except City.DoesNotExist:
                pass
        
        # Import the file
        return import_service.import_file_with_config(str(file_path), city_slug)
    
    def _validate_files_only(self, city_slug, data_dir):
        """Validate files without importing"""
        from maps.config import get_city_config
        
        config = get_city_config(city_slug)
        if not config:
            self.stdout.write(self.style.ERROR(f"❌ No configuration for city: {city_slug}"))
            return
        
        self.stdout.write(f"🔍 Validating files for {city_slug}...")
        
        data_path = Path(data_dir)
        found_files = []
        missing_files = []
        
        for filename, category in config['file_mappings'].items():
            file_path = data_path / filename
            if file_path.exists():
                file_size = file_path.stat().st_size
                found_files.append({
                    'filename': filename,
                    'category': category,
                    'size_mb': round(file_size / (1024 * 1024), 2),
                    'color': config['colors'].get(category, '#666666')
                })
            else:
                missing_files.append({'filename': filename, 'category': category})
        
        # Display results
        self.stdout.write(f"\n✅ Found Files ({len(found_files)}):")
        for file_info in found_files:
            self.stdout.write(
                f"   📄 {file_info['filename']} "
                f"({file_info['size_mb']} MB) → {file_info['category']} "
                f"{file_info['color']}"
            )
        
        if missing_files:
            self.stdout.write(f"\n❌ Missing Files ({len(missing_files)}):")
            for file_info in missing_files:
                self.stdout.write(f"   📄 {file_info['filename']} → {file_info['category']}")
        
        self.stdout.write(f"\n📊 Summary:")
        self.stdout.write(f"   Total configured: {len(config['file_mappings'])}")
        self.stdout.write(f"   Found: {len(found_files)}")
        self.stdout.write(f"   Missing: {len(missing_files)}")
        
        if len(found_files) > 0:
            total_size = sum(f['size_mb'] for f in found_files)
            self.stdout.write(f"   Total size: {total_size:.1f} MB")
            self.stdout.write(f"\n🚀 Ready to import! Remove --validate-only to proceed")
    
    def _setup_styles(self, import_service, city_slug):
        """Setup city styles after import"""
        self.stdout.write(f"\n🎨 Setting up styles for {city_slug}...")
        try:
            import_service.setup_city_styles(city_slug)
            self.stdout.write("✅ Styles setup completed")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠️  Style setup failed: {e}"))
    
    def _display_single_result(self, result):
        """Display single file import result"""
        if result.get('status') == 'success':
            self.stdout.write(f"✅ Import successful!")
            self.stdout.write(f"   Layer: {result.get('layer_name')}")
            self.stdout.write(f"   Features: {result.get('features_imported', 0):,}")
            self.stdout.write(f"   Format: {result.get('file_format')}")
            self.stdout.write(f"   Method: {result.get('categorization_method')}")
            
            if result.get('plu_codes_detected'):
                codes = ', '.join(result['plu_codes_detected'][:5])
                self.stdout.write(f"   PLU codes: {codes}")
        else:
            self.stdout.write(self.style.ERROR(f"❌ Import failed"))
    
    def _display_bulk_results(self, result):
        """Display bulk import results"""
        self.stdout.write(f"\n📊 Bulk Import Results for {result['city'].upper()}:")
        self.stdout.write(f"   Total files configured: {result['total_files']}")
        self.stdout.write(f"   Successfully imported: {result['imported_files']}")
        self.stdout.write(f"   Total features: {result['total_features']:,}")
        
        # Show detailed results
        successful = [r for r in result['results'] if r.get('status') == 'success']
        failed = [r for r in result['results'] if r.get('status') == 'error']
        not_found = [r for r in result['results'] if r.get('status') == 'not_found']
        
        if successful:
            self.stdout.write(f"\n✅ Successful Imports ({len(successful)}):")
            for r in successful:
                features = r.get('features_imported', 0)
                self.stdout.write(f"   📄 {r['filename']}: {features:,} features")
                
                # Show PLU codes if detected
                if r.get('plu_codes_detected'):
                    codes = ', '.join(r['plu_codes_detected'][:3])
                    self.stdout.write(f"      🏷️  PLU: {codes}")
        
        if failed:
            self.stdout.write(f"\n❌ Failed Imports ({len(failed)}):")
            for r in failed:
                self.stdout.write(f"   📄 {r['filename']}: {r.get('error', 'Unknown error')}")
        
        if not_found:
            self.stdout.write(f"\n⚠️  Files Not Found ({len(not_found)}):")
            for r in not_found:
                self.stdout.write(f"   📄 {r['filename']}")
        
        # Show next steps
        if successful:
            city_slug = result['city']
            self.stdout.write(f"\n🎯 Next Steps:")
            self.stdout.write(f"   1. Validate: python manage.py validate_import --city={city_slug}")
            self.stdout.write(f"   2. Generate tiles: python manage.py generate_city_tiles --city={city_slug}")
            self.stdout.write(f"   3. Check PLU: python manage.py show_plu_mappings --city={city_slug}")
            self.stdout.write(f"   4. Test API: curl http://localhost:8000/api/cities/{city_slug}/layers/")
        
        # Show import job IDs for tracking
        recent_jobs = ImportJob.objects.filter(
            city__slug=result['city']
        ).order_by('-started_at')[:3]
        
        if recent_jobs.exists():
            self.stdout.write(f"\n📋 Recent Import Jobs:")
            for job in recent_jobs:
                status_icon = "✅" if job.status == 'COMPLETED' else "❌"
                self.stdout.write(f"   {status_icon} {job.filename}: {job.features_imported:,} features")