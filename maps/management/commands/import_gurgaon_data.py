# Create this file: maps/management/commands/import_gurgaon_data.py

from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Import Gurgaon GeoJSON data from directory'
    
    def add_arguments(self, parser):
        parser.add_argument('--data-dir', required=True, help='Directory containing Gurgaon GeoJSON files')
        parser.add_argument('--file', help='Import only specific file')
        parser.add_argument('--force', action='store_true', help='Force re-import existing layers')
        parser.add_argument('--validate-only', action='store_true', help='Only validate files')
        parser.add_argument('--setup-styles', action='store_true', help='Setup city styles')
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🏛️  GURGAON DATA IMPORT"))
        self.stdout.write("📍 Millennium City - Haryana")
        
        # Build arguments for the existing command
        cmd_args = [
            '--city', 'gurgaon',
            '--data-dir', options['data_dir']  # Changed from 'data-dir' to 'data_dir'
        ]
        
        if options.get('file'):
            cmd_args.extend(['--file', options['file']])
        if options.get('force'):
            cmd_args.append('--force')
        if options.get('validate_only'):  # Changed from 'validate-only' to 'validate_only'
            cmd_args.append('--validate-only')
        if options.get('setup_styles'):  # Changed from 'setup-styles' to 'setup_styles'
            cmd_args.append('--setup-styles')
        
        # Call the existing command
        try:
            call_command('import_city_data', *cmd_args)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Import failed: {str(e)}"))
            self.stdout.write("\n" + "="*50)
            self.stdout.write("GURGAON DATA STRUCTURE:")
            self.stdout.write("="*50)
            self.stdout.write("Expected files:")
            files = [
                'Agriculture_Zone.geojson',
                'Commercial.geojson', 
                'Hubs.geojson',
                'Industrial.geojson',
                'Natural_Conservation_Zone_Hubs.geojson',
                'Open_Spaces.geojson',
                'Public_and_Semi_Public_Use.geojson',
                'Public_Utilities.geojson',
                'Residential_GroupHousing_Plotted.geojson',
                'Special_Zone.geojson',
                'Transport_and_Communication.geojson',
                'World_Trade_Hub.geojson'
            ]
            for f in files:
                self.stdout.write(f"   - {f}")
            self.stdout.write("\nData should have 'classtext' field with values like:")
            self.stdout.write("   '100 Residential (Group Housing/Plotted)'")
            self.stdout.write("   '200 Commercial'")
            self.stdout.write("   '800 Aggriculture Zone'")
            self.stdout.write("   etc.")