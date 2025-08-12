# maps/management/commands/fix_layer_structure.py
# Django management command to fix the layer hierarchy

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from maps.layer_import_service import LayerImportService, LayerStructureFixer
from maps.models import City, DataLayer
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fix layer structure to follow proper hierarchy: State → City → Layer → Files → Features'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            type=str,
            choices=['consolidate', 'import', 'list'],
            help='Action to perform'
        )
        
        parser.add_argument(
            '--city',
            type=str,
            required=True,
            help='City slug (e.g., bengaluru, hyderabad, warangal)'
        )
        
        parser.add_argument(
            '--state',
            type=str,
            help='State slug (required for import action)'
        )
        
        parser.add_argument(
            '--data-path',
            type=str,
            help='Base path to data folder (required for import action)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        
        action = options['action']
        city_slug = options['city']
        
        if action == 'list':
            self.list_current_structure(city_slug)
        
        elif action == 'consolidate':
            self.consolidate_layers(city_slug, options['dry_run'])
        
        elif action == 'import':
            if not options['state'] or not options['data_path']:
                raise CommandError('--state and --data-path are required for import action')
            
            self.import_with_proper_structure(
                options['state'],
                city_slug,
                options['data_path']
            )
    
    def list_current_structure(self, city_slug: str):
        """List current layer structure for a city"""
        try:
            city = City.objects.get(slug=city_slug)
            layers = DataLayer.objects.filter(city=city).order_by('category__name', 'name')
            
            self.stdout.write(f"\n📊 Current structure for {city.name}:")
            self.stdout.write("=" * 60)
            
            current_category = None
            for layer in layers:
                if layer.category != current_category:
                    current_category = layer.category
                    self.stdout.write(f"\n{current_category.name if current_category else 'Uncategorized'}:")
                
                status = "✅" if layer.is_processed else "⏳"
                features = layer.geofeature_set.count()
                is_dir = "📁" if layer.is_directory else "📄"
                
                self.stdout.write(
                    f"  {is_dir} {status} {layer.name} "
                    f"[{features} features] "
                    f"{'(Directory-based)' if layer.is_directory else '(File-based)'}"
                )
            
            # Show summary
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(f"Total layers: {layers.count()}")
            self.stdout.write(f"Directory-based layers: {layers.filter(is_directory=True).count()}")
            self.stdout.write(f"File-based layers: {layers.filter(is_directory=False).count()}")
            
        except City.DoesNotExist:
            raise CommandError(f"City '{city_slug}' not found")
    
    def consolidate_layers(self, city_slug: str, dry_run: bool):
        """Consolidate file-based layers into proper layer groups"""
        
        # Define consolidation rules for each city
        consolidation_rules = {
            'bengaluru': [
                {
                    'layer_name': 'master_plan',
                    'files': [
                        'Agricultural_Land',
                        'Commercial_Business',
                        'Commercial_Central',
                        'Defense',
                        'Drains',
                        'HighTech',
                        'Industrial',
                        'Lake_Tank',
                        'Parks_GreenSpaces_Sports_Playgrounds_Cemetery_BurialGrounds',
                        'Power_Water_GarbageFacility_TreatmentPlant',
                        'Public_SemiPublic',
                        'Residential_Main',
                        'Residential_Mixed',
                        'Road_Rail_Airport_Transport',
                        'StateForest_Valley_ProtectedLand',
                        'Unclassified_Use'
                    ]
                },
                {
                    'layer_name': 'highways',
                    'files': [
                        'BellaryRoad_NH44',
                        'BengaluruChennaiExpressway_NE7',
                        'BengaluruMysuruRoad_NH275',
                        'HosurRoad_NH48',
                        'KanakpuraRoad_NH948',
                        'MadrasRoad_NH75',
                        'NICE_Road',
                        'TumakuruRoad_NH48'
                    ]
                },
                {
                    'layer_name': 'metro',
                    'files': [
                        'Bangalore Metro Phases'
                    ]
                }
            ],
            'hyderabad': [
                {
                    'layer_name': 'future_city',
                    'files': [
                        'HMDA_Boundary',
                        'HMDA_Villages'
                    ]
                },
                {
                    'layer_name': 'highways',
                    'files': [
                        'Hyderabad Highways'
                    ]
                },
                {
                    'layer_name': 'metro_lines',
                    'files': [
                        'Hyderabad Metro Lines',
                        'Hyderabad Metro Stations'
                    ]
                },
                {
                    'layer_name': 'master_plan_roads',
                    'files': [
                        'HMDA Master Plan Roads'
                    ]
                },
                {
                    'layer_name': 'rrr',
                    'files': [
                        'Regional Ring Road'
                    ]
                },
                {
                    'layer_name': 'workspaces',
                    'files': [
                        'Special Economic Zones'
                    ]
                }
            ],
            'warangal': [
                {
                    'layer_name': 'master_plan',
                    'files': [
                        'Agriculture',
                        'AirStrip',
                        'Commercial',
                        'Forest',
                        'GrowthCorridor',
                        'GrowthCorridor2',
                        'Heritage',
                        'HillBuffer',
                        'Hillocks',
                        'Industrial',
                        'MixedUse',
                        'Public_and_SemiPublic',
                        'PublicUtilities',
                        'RailwayLand',
                        'Recreational',
                        'Residential',
                        'ResidentialExpansion',
                        'RoadBuffer',
                        'Transportation',
                        'Water_Bodies',
                        'WaterBodyBuffer',
                        'ZoologicalPark'
                    ]
                }
            ]
        }
        
        if city_slug not in consolidation_rules:
            self.stdout.write(self.style.WARNING(
                f"No consolidation rules defined for {city_slug}"
            ))
            return
        
        rules = consolidation_rules[city_slug]
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\n🔍 DRY RUN MODE - No changes will be made"))
        
        self.stdout.write(f"\n🔧 Consolidating layers for {city_slug}")
        
        fixer = LayerStructureFixer()
        
        for rule in rules:
            layer_name = rule['layer_name']
            files = rule['files']
            
            self.stdout.write(f"\n📁 Processing layer group: {layer_name}")
            self.stdout.write(f"   Files to consolidate: {len(files)}")
            
            if not dry_run:
                result = fixer.consolidate_file_layers_to_single_layer(
                    city_slug=city_slug,
                    layer_name=layer_name,
                    file_patterns=files
                )
                
                if result['success']:
                    self.stdout.write(self.style.SUCCESS(
                        f"   ✅ Consolidated {result['file_layers_removed']} file layers "
                        f"into {result['master_layer']} "
                        f"({result['features_consolidated']} features)"
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f"   ❌ Error: {result['error']}"
                    ))
            else:
                # In dry run, just show what would be done
                city = City.objects.get(slug=city_slug)
                file_layers = []
                for file_pattern in files:
                    matching = DataLayer.objects.filter(
                        city=city,
                        name__icontains=file_pattern
                    )
                    file_layers.extend(matching)
                
                if file_layers:
                    self.stdout.write(f"   Would consolidate {len(file_layers)} layers:")
                    for layer in file_layers[:5]:  # Show first 5
                        self.stdout.write(f"      - {layer.name}")
                    if len(file_layers) > 5:
                        self.stdout.write(f"      ... and {len(file_layers) - 5} more")
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS("\n✅ Consolidation complete"))
        else:
            self.stdout.write(self.style.WARNING("\n🔍 Dry run complete - no changes made"))
    
    def import_with_proper_structure(self, state_slug: str, city_slug: str, data_path: str):
        """Import data with proper hierarchical structure"""
        
        self.stdout.write(f"\n📥 Importing data for {city_slug}, {state_slug}")
        self.stdout.write(f"   Data path: {data_path}")
        
        importer = LayerImportService()
        
        try:
            stats = importer.import_city_data(
                state_slug=state_slug,
                city_slug=city_slug,
                base_path=data_path
            )
            
            self.stdout.write(self.style.SUCCESS("\n✅ Import complete"))
            self.stdout.write(f"   Layers created: {stats['layers_created']}")
            self.stdout.write(f"   Files processed: {stats['files_processed']}")
            self.stdout.write(f"   Features imported: {stats['features_imported']}")
            
            if stats['errors']:
                self.stdout.write(self.style.WARNING(f"\n⚠️  Errors encountered:"))
                for error in stats['errors'][:10]:
                    self.stdout.write(f"   - {error}")
                    
        except Exception as e:
            raise CommandError(f"Import failed: {str(e)}")