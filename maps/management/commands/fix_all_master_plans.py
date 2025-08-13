# maps/management/commands/fix_all_master_plans.py
"""
Batch command to fix master plan consolidation for all cities.
Properly consolidates zone layers into master plans based on city data structure.
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from maps.models import City, DataLayer
from django.db.models import Count

class Command(BaseCommand):
    help = 'Fix master plan consolidation for all cities'
    
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
        parser.add_argument('--cities', nargs='*', help='Specific cities to process')
        parser.add_argument('--verbose', action='store_true', help='Show detailed progress')
        
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🔧 FIXING MASTER PLANS FOR ALL CITIES'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Define consolidation rules for each city
        city_configs = {
            # Cities where ALL layers should be in master plan
            'visakhapatnam': {
                'consolidate': True,
                'exclude': [],  # All layers go into master plan
                'description': 'All zone layers → Master Plan'
            },
            'amaravati': {
                'consolidate': True,
                'exclude': [],  # All layers go into master plan
                'description': 'All zone layers → Master Plan'
            },
            'warangal': {
                'consolidate': True,
                'exclude': ['master_plan_roads', 'master-plan-roads'],
                'description': 'All zone layers → Master Plan (except roads)'
            },
            
            # Bengaluru needs different treatment
            'bengaluru': {
                'consolidate': False,  # Use cleanup_layers command instead
                'description': 'Needs special consolidation (multiple layer groups)'
            },
            
            # Hyderabad has multiple layer groups
            'hyderabad': {
                'consolidate': False,
                'exclude': ['highways', 'metro', 'rrr', 'lakes', 'railway'],
                'description': 'Has separate infrastructure layers'
            }
        }
        
        # Get cities to process
        if options.get('cities'):
            cities = City.objects.filter(slug__in=options['cities'])
        else:
            # Get cities with multiple layers that might need consolidation
            cities = City.objects.annotate(
                layer_count=Count('layers')
            ).filter(layer_count__gt=5).order_by('name')
        
        if not cities.exists():
            self.stdout.write("No cities found to process")
            return
        
        # Summary of what will be done
        self.stdout.write(f"\n📊 Found {cities.count()} cities to process:\n")
        
        for city in cities:
            layer_count = DataLayer.objects.filter(city=city).count()
            config = city_configs.get(city.slug, {})
            
            self.stdout.write(f"  • {city.name} ({city.slug}): {layer_count} layers")
            if config:
                self.stdout.write(f"    → {config.get('description', 'Custom configuration')}")
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("\n🔍 DRY RUN MODE - No changes will be made"))
        
        # Process each city
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("PROCESSING CITIES")
        self.stdout.write("=" * 70)
        
        results = {
            'success': [],
            'skipped': [],
            'failed': []
        }
        
        for city in cities:
            self.stdout.write(f"\n📍 Processing: {city.name}")
            self.stdout.write("-" * 50)
            
            config = city_configs.get(city.slug, {})
            
            try:
                if city.slug == 'bengaluru':
                    # Special handling for Bengaluru
                    self._process_bengaluru(city, options)
                    results['success'].append(city.name)
                    
                elif config.get('consolidate', True):
                    # Cities that need full consolidation
                    self._consolidate_city(city, config.get('exclude', []), options)
                    results['success'].append(city.name)
                    
                else:
                    # Cities that don't need consolidation
                    self.stdout.write(f"  ℹ️  Skipping {city.name} - has separate layer groups")
                    results['skipped'].append(city.name)
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ Failed: {str(e)}"))
                results['failed'].append(city.name)
        
        # Print summary
        self._print_summary(results)
    
    def _consolidate_city(self, city, exclude_patterns, options):
        """Consolidate a city's layers into master plan"""
        
        # Check current state
        layers = DataLayer.objects.filter(city=city)
        master_plan = layers.filter(slug__icontains='master_plan').first()
        
        if master_plan and master_plan.feature_count > 0:
            # Check if already consolidated
            other_layers = layers.exclude(id=master_plan.id)
            if exclude_patterns:
                for pattern in exclude_patterns:
                    other_layers = other_layers.exclude(slug__icontains=pattern)
            
            if other_layers.count() == 0:
                self.stdout.write(f"  ✅ Already consolidated")
                return
        
        # Run consolidation
        cmd_args = ['consolidate_master_plan', '--city', city.slug]
        
        if exclude_patterns:
            cmd_args.extend(['--exclude'] + exclude_patterns)
        
        if options.get('dry_run'):
            cmd_args.append('--dry-run')
        
        if options.get('verbose'):
            cmd_args.append('--verbose')
        
        call_command(*cmd_args)
    
    def _process_bengaluru(self, city, options):
        """Special processing for Bengaluru with multiple layer groups"""
        
        self.stdout.write("  ℹ️  Bengaluru needs special consolidation")
        
        # Run the cleanup_layers command for Bengaluru
        cmd_args = ['cleanup_layers', '--city', 'bengaluru']
        
        if options.get('dry_run'):
            cmd_args.append('--dry-run')
        
        if options.get('verbose'):
            cmd_args.append('--verbose')
        
        call_command(*cmd_args)
    
    def _print_summary(self, results):
        """Print processing summary"""
        
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("📊 PROCESSING SUMMARY")
        self.stdout.write("=" * 70)
        
        if results['success']:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Successfully processed: {len(results['success'])} cities"))
            for city in results['success']:
                self.stdout.write(f"  • {city}")
        
        if results['skipped']:
            self.stdout.write(self.style.WARNING(f"\n⏭️  Skipped: {len(results['skipped'])} cities"))
            for city in results['skipped']:
                self.stdout.write(f"  • {city}")
        
        if results['failed']:
            self.stdout.write(self.style.ERROR(f"\n❌ Failed: {len(results['failed'])} cities"))
            for city in results['failed']:
                self.stdout.write(f"  • {city}")
        
        # Show final status
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("FINAL STATUS")
        self.stdout.write("=" * 70)
        
        # Check key cities
        key_cities = ['visakhapatnam', 'amaravati', 'warangal', 'bengaluru']
        
        for city_slug in key_cities:
            try:
                city = City.objects.get(slug=city_slug)
                layers = DataLayer.objects.filter(city=city)
                master_plan = layers.filter(name__icontains='master plan').first()
                
                self.stdout.write(f"\n{city.name}:")
                self.stdout.write(f"  • Total layers: {layers.count()}")
                if master_plan:
                    self.stdout.write(f"  • Master Plan features: {master_plan.feature_count:,}")
                
            except City.DoesNotExist:
                continue