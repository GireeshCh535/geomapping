# maps/management/commands/verify_hierarchy.py
"""
Command to verify the correct hierarchical structure after import.
Shows State → City → Layer Groups (with combined features count)
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from maps.models import State, City, DataLayer, GeoFeature
from collections import defaultdict

class Command(BaseCommand):
    help = 'Verify and display the correct State → City → Layer hierarchy'
    
    def add_arguments(self, parser):
        parser.add_argument('--state', help='Filter by state slug')
        parser.add_argument('--city', help='Filter by city slug')
        parser.add_argument('--detailed', action='store_true', help='Show detailed feature breakdown')
        
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🗂️  GEOSPATIAL DATA HIERARCHY'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('\n📋 Structure: State → City → Layer (Combined Features)\n')
        
        # Get states with filters
        states_query = State.objects.all()
        if options.get('state'):
            states_query = states_query.filter(slug=options['state'])
        
        states = states_query.prefetch_related('cities__layers').order_by('name')
        
        if not states.exists():
            self.stdout.write(self.style.ERROR("❌ No states found in database"))
            return
        
        total_stats = {
            'states': 0,
            'cities': 0,
            'layers': 0,
            'features': 0
        }
        
        for state in states:
            total_stats['states'] += 1
            
            # Get cities for this state
            cities_query = state.cities.all()
            if options.get('city'):
                cities_query = cities_query.filter(slug=options['city'])
            
            cities = cities_query.order_by('name')
            
            if not cities.exists():
                continue
            
            self.stdout.write(f"\n📦 State: {state.name}")
            self.stdout.write(f"   Slug: {state.slug}")
            
            for city in cities:
                total_stats['cities'] += 1
                
                # Get layers for this city (these should be layer GROUPS now)
                layers = DataLayer.objects.filter(city=city).order_by('name')
                
                if not layers.exists():
                    self.stdout.write(f"\n  🏙️  City: {city.name} ({city.slug})")
                    self.stdout.write(f"      ⚠️  No layers found")
                    continue
                
                self.stdout.write(f"\n  🏙️  City: {city.name}")
                self.stdout.write(f"      Slug: {city.slug}")
                self.stdout.write(f"      Layers: {layers.count()}")
                
                # Group layers by category for better display
                layers_by_category = defaultdict(list)
                for layer in layers:
                    category = layer.category.name if layer.category else 'Uncategorized'
                    layers_by_category[category].append(layer)
                
                # Display layers grouped by category
                for category, cat_layers in sorted(layers_by_category.items()):
                    self.stdout.write(f"\n      📂 {category}:")
                    
                    for layer in cat_layers:
                        total_stats['layers'] += 1
                        
                        # Get actual feature count from database
                        feature_count = GeoFeature.objects.filter(layer=layer).count()
                        total_stats['features'] += feature_count
                        
                        # Compare with stored count
                        if layer.feature_count != feature_count:
                            count_display = f"{feature_count} (stored: {layer.feature_count} ⚠️)"
                        else:
                            count_display = f"{feature_count}"
                        
                        self.stdout.write(f"        • {layer.name}")
                        self.stdout.write(f"          Slug: {layer.slug}")
                        self.stdout.write(f"          Features: {count_display}")
                        
                        if options.get('detailed'):
                            self._show_feature_details(layer)
        
        # Print summary
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('📊 HIERARCHY SUMMARY')
        self.stdout.write('=' * 70)
        self.stdout.write(f"Total States: {total_stats['states']}")
        self.stdout.write(f"Total Cities: {total_stats['cities']}")
        self.stdout.write(f"Total Layer Groups: {total_stats['layers']}")
        self.stdout.write(f"Total Features: {total_stats['features']:,}")
        
        # Check for issues
        self._check_for_issues()
    
    def _show_feature_details(self, layer: DataLayer):
        """Show detailed breakdown of features in a layer"""
        
        # Get features grouped by source file
        features = GeoFeature.objects.filter(layer=layer).values('source_file').annotate(
            count=Count('id')
        ).order_by('source_file')
        
        if features:
            self.stdout.write("          Source files:")
            for feature_group in features:
                source = feature_group['source_file'] or 'unknown'
                count = feature_group['count']
                self.stdout.write(f"            - {source}: {count} features")
        
        # Get feature types
        feature_types = GeoFeature.objects.filter(layer=layer).values('feature_type').annotate(
            count=Count('id')
        ).order_by('feature_type')
        
        if feature_types:
            self.stdout.write("          Geometry types:")
            for ft in feature_types:
                self.stdout.write(f"            - {ft['feature_type']}: {ft['count']}")
    
    def _check_for_issues(self):
        """Check for common issues in the hierarchy"""
        
        issues = []
        
        # Check for duplicate layer files (should not exist anymore)
        duplicate_patterns = [
            'residential_mixed',
            'residential_main',
            'commercial_central',
            'commercial_business',
            'industrial',
            'hightech',
            'defense',
            'agricultural_land'
        ]
        
        for pattern in duplicate_patterns:
            duplicates = DataLayer.objects.filter(slug__icontains=pattern)
            if duplicates.count() > 1:
                issues.append(f"Multiple layers found for '{pattern}' - should be combined")
        
        # Check for empty layers
        empty_layers = DataLayer.objects.filter(feature_count=0)
        if empty_layers.exists():
            issues.append(f"{empty_layers.count()} empty layers found")
        
        # Check for layers without categories
        no_category = DataLayer.objects.filter(category__isnull=True)
        if no_category.exists():
            issues.append(f"{no_category.count()} layers without categories")
        
        if issues:
            self.stdout.write('\n' + self.style.WARNING('⚠️  POTENTIAL ISSUES:'))
            for issue in issues:
                self.stdout.write(f"  - {issue}")
        else:
            self.stdout.write('\n' + self.style.SUCCESS('✅ No hierarchy issues detected'))