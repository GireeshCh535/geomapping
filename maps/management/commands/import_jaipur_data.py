# Create this file: maps/management/commands/import_jaipur_data.py

from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Import Jaipur GeoJSON data from directory'
    
    def add_arguments(self, parser):
        parser.add_argument('--data-dir', required=True, help='Directory containing Jaipur GeoJSON files')
        parser.add_argument('--file', help='Import only specific file')
        parser.add_argument('--force', action='store_true', help='Force re-import existing layers')
        parser.add_argument('--validate-only', action='store_true', help='Only validate files')
        parser.add_argument('--setup-styles', action='store_true', help='Setup city styles')
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🏛️  JAIPUR DATA IMPORT"))
        self.stdout.write("👑 Pink City - Rajasthan")
        
        # Build arguments for the existing command
        cmd_args = [
            '--city', 'jaipur',
            '--data-dir', options['data_dir']
        ]
        
        if options.get('file'):
            cmd_args.extend(['--file', options['file']])
        if options.get('force'):
            cmd_args.append('--force')
        if options.get('validate_only'):
            cmd_args.append('--validate-only')
        if options.get('setup_styles'):
            cmd_args.append('--setup-styles')
        
        # Call the existing command
        try:
            call_command('import_city_data', *cmd_args)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Import failed: {str(e)}"))
            self.stdout.write("\n" + "="*50)
            self.stdout.write("JAIPUR DATA STRUCTURE:")
            self.stdout.write("="*50)
            self.stdout.write("Expected files (28 total):")
            files = [
                'Agriculture_Land.geojson',
                'Commercial.geojson',
                'Communication.geojson',
                'Eco_Sensitive__Zone.geojson',
                'Educational.geojson',
                'G1.geojson',
                'G2.geojson', 
                'G3.geojson',
                'Govt_and_Semi_Governmernt.geojson',
                'Green_Areas.geojson',
                'Health_Services.geojson',
                'Heritage.geojson',
                'Industrial.geojson',
                'Mixed.geojson',
                'Others.geojson',
                'Public___Semi_Public.geojson',
                'Public_Utilities.geojson',
                'Recreational.geojson',
                'Religious.geojson',
                'Residential.geojson',
                'Rural.geojson',
                'Specific_Land_Use.geojson',
                'Transportation.geojson',
                'U1_2025.geojson',
                'U2_HIZ.geojson',
                'U2_LIZ.geojson',
                'U3_HIZ.geojson',
                'U3_LIZ.geojson',
                'Vacant_Land.geojson',
                'Water_Bodies.geojson'
            ]
            for f in files:
                self.stdout.write(f"   - {f}")
            self.stdout.write("\nData should have 'LANDUSE_CATEGORY' field with values like:")
            categories = [
                'Agriculture Land',
                'Commercial',
                'Communication',
                'Eco-Sensitive Zone',
                'Educational',
                'G1', 'G2', 'G3',
                'Govt and Semi Governmernt',
                'Green Areas',
                'Health Services',
                'Heritage',
                'Industrial',
                'Mixed',
                'Others',
                'Public & Semi Public',
                'Public Utilities',
                'Recreational',
                'Religious',
                'Residential',
                'Rural',
                'Speccific Land Use',
                'Transportation',
                'U1_2025',
                'U2 HIZ',
                'U2 LIZ',
                'U3 HIZ',
                'U3 LIZ',
                'Vacant Land',
                'Water Bodies'
            ]
            for cat in categories:
                self.stdout.write(f"   '{cat}'")
            self.stdout.write("\nKey attributes expected:")
            self.stdout.write("   - LANDUSE_CATEGORY: Main land use type")
            self.stdout.write("   - LANDUSE_SUBCAT_LEVEL_1: Sub-category level 1")
            self.stdout.write("   - DISTRICT: Should be 'Jaipur'")
            self.stdout.write("   - ADMIN_ZONE: Administrative zone")
            self.stdout.write("   - SHAPE.AREA: Area value")
            self.stdout.write("   - SHAPE.LEN: Perimeter/length value")