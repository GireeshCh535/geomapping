# maps/management/commands/show_layer_groups.py
"""
Display hierarchy by Layer Groups (master_plan, highways, metro, workspace)
Command: python manage.py show_layer_groups --city bengaluru
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from maps.models import State, City, DataLayer, LayerGroup, GeoFeature
from collections import defaultdict

class Command(BaseCommand):
    help = 'Display State → City → Layer Groups hierarchy (not categories)'
    
    def add_arguments(self, parser):
        parser.add_argument('--state', help='Show specific state only')
        parser.add_argument('--city', help='Show specific city only')
        parser.add_argument('--with-stats', action='store_true', help='Include detailed statistics')
        parser.add_argument('--compact', action='store_true', help='Compact view without individual layers')
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🏗️  LAYER GROUPS HIERARCHY"))
        
        if options['city']:
            self._show_city_layer_groups(options['city'], options)
        elif options['state']:
            self._show_state_layer_groups(options['state'], options)
        else:
            self._show_complete_layer_groups_hierarchy(options)
    
    def _show_complete_layer_groups_hierarchy(self, options):
        """Show complete State → City → Layer Groups hierarchy"""
        
        states = State.objects.prefetch_related(
            'cities__layer_groups__layers'
        ).annotate(
            city_count=Count('cities'),
            total_layer_groups=Count('cities__layer_groups'),
            total_layers=Count('cities__layer_groups__layers')
        ).filter(is_active=True).order_by('name')
        
        if not states.exists():
            self.stdout.write("❌ No states found. Run setup_hierarchy_from_excel first.")
            return
        
        for state in states:
            total_features = sum(
                city.layers.aggregate(
                    total=Sum('feature_count')
                )['total'] or 0 
                for city in state.cities.all()
            )
            
            self.stdout.write(f"\n🏛️  STATE: {state.name}")
            self.stdout.write(f"   Cities: {state.city_count} | Layer Groups: {state.total_layer_groups} | Total Features: {total_features:,}")
            
            # Show cities and their layer groups
            cities = state.cities.filter(is_active=True).prefetch_related('layer_groups__layers')
            
            for city in cities:
                self._show_city_layer_groups_inline(city, options)
    
    def _show_city_layer_groups(self, city_slug, options):
        """Show layer groups for a specific city"""
        
        try:
            city = City.objects.prefetch_related(
                'layer_groups__layers'
            ).get(slug=city_slug)
            
            self.stdout.write(f"\n🏙️  CITY: {city.name} ({city.get_state_name()})")
            self._show_city_layer_groups_detailed(city, options)
            
        except City.DoesNotExist:
            self.stdout.write(f"❌ City not found: {city_slug}")
            available_cities = City.objects.values_list('slug', 'name')
            self.stdout.write("   Available cities:")
            for slug, name in available_cities:
                self.stdout.write(f"   - {slug} ({name})")
    
    def _show_city_layer_groups_inline(self, city, options):
        """Show city layer groups in compact format"""
        
        layer_groups = city.layer_groups.annotate(
            layer_count=Count('layers'),
            total_features=Sum('layers__feature_count')
        ).order_by('display_order', 'name')
        
        if not layer_groups.exists():
            self.stdout.write(f"   🏙️  {city.name}: No layer groups")
            return
        
        self.stdout.write(f"\n   🏙️  {city.name}:")
        
        for group in layer_groups:
            total_features = group.total_features or 0
            status_icon = "✅" if total_features > 0 else "⚪"
            
            self.stdout.write(f"      {status_icon} 📁 {group.name} ({group.slug})")
            self.stdout.write(f"         Layers: {group.layer_count} | Features: {total_features:,}")
    
    def _show_city_layer_groups_detailed(self, city, options):
        """Show detailed layer groups for a city"""
        
        layer_groups = city.layer_groups.annotate(
            layer_count=Count('layers'),
            total_features=Sum('layers__feature_count')
        ).order_by('display_order', 'name')
        
        if not layer_groups.exists():
            self.stdout.write("   ❌ No layer groups found")
            return
        
        city_total_features = sum(group.total_features or 0 for group in layer_groups)
        
        self.stdout.write(f"   Slug: {city.slug}")
        self.stdout.write(f"   State: {city.get_state_name()}")
        self.stdout.write(f"   Layer Groups: {layer_groups.count()}")
        self.stdout.write(f"   Total Features: {city_total_features:,}")
        
        # Show each layer group
        self.stdout.write(f"\n📁 LAYER GROUPS ({layer_groups.count()}):")
        
        for group in layer_groups:
            total_features = group.total_features or 0
            status_icon = "✅" if total_features > 0 else "⚪"
            
            self.stdout.write(f"\n   {status_icon} 📁 {group.name} ({group.slug})")
            self.stdout.write(f"      Category: {group.category.name}")
            self.stdout.write(f"      Description: {group.description}")
            self.stdout.write(f"      Layers: {group.layer_count}")
            self.stdout.write(f"      Total Features: {total_features:,}")
            self.stdout.write(f"      Directory: {group.directory_path}")
            
            # Show individual layers if not compact
            if not options.get('compact', False):
                layers = group.layers.all().order_by('name')
                
                if layers.exists():
                    self.stdout.write(f"      📋 Individual Layers ({layers.count()}):")
                    
                    for layer in layers:
                        layer_status = "✅" if layer.is_processed else "⚪"
                        feature_count = layer.feature_count or 0
                        
                        self.stdout.write(f"         {layer_status} {layer.name}")
                        self.stdout.write(f"            Features: {feature_count:,} | Format: {layer.file_format}")
                        
                        if feature_count == 0 and layer.file_format == 'JSON':
                            self.stdout.write(f"            ⚠️  Zero features - may need re-import")
        
        # Show summary
        self.stdout.write(f"\n📊 SUMMARY:")
        
        successful_groups = sum(1 for group in layer_groups if (group.total_features or 0) > 0)
        self.stdout.write(f"   ✅ Groups with data: {successful_groups}/{layer_groups.count()}")
        self.stdout.write(f"   📊 Total features across all groups: {city_total_features:,}")
        
        # Show next steps
        if successful_groups > 0:
            group_names = [group.slug for group in layer_groups if (group.total_features or 0) > 0]
            self.stdout.write(f"\n🚀 Ready for tile generation:")
            self.stdout.write(f"   python manage.py generate_direct_s3_tiles \\")
            self.stdout.write(f"       --city {city.slug} \\")
            self.stdout.write(f"       --layer-groups \"{','.join(group_names)}\" \\")
            self.stdout.write(f"       --type png \\")
            self.stdout.write(f"       --min-zoom 8 \\")
            self.stdout.write(f"       --max-zoom 14")
        else:
            self.stdout.write(f"\n⚠️  No layer groups have data - import data first")
    
    def _show_state_layer_groups(self, state_slug, options):
        """Show layer groups for all cities in a state"""
        
        try:
            state = State.objects.prefetch_related(
                'cities__layer_groups__layers'
            ).get(slug=state_slug)
            
            self.stdout.write(f"\n🏛️  STATE: {state.name}")
            
            cities = state.cities.filter(is_active=True)
            for city in cities:
                self._show_city_layer_groups_inline(city, options)
                
        except State.DoesNotExist:
            self.stdout.write(f"❌ State not found: {state_slug}")
            available_states = State.objects.values_list('slug', 'name')
            self.stdout.write("   Available states:")
            for slug, name in available_states:
                self.stdout.write(f"   - {slug} ({name})")