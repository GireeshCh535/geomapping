# /app/maps/management/commands/show_hierarchy.py - FIXED VERSION

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from maps.models import State, City, DataLayer, LayerCategory, GeoFeature
from collections import defaultdict
from django.utils.text import slugify

class Command(BaseCommand):
    help = 'Display current State → City → Layer hierarchy with statistics'
    
    def add_arguments(self, parser):
        parser.add_argument('--state', help='Show specific state only')
        parser.add_argument('--city', help='Show specific city only')
        parser.add_argument('--with-stats', action='store_true', help='Include detailed statistics')
        parser.add_argument('--show-data-paths', action='store_true', help='Show expected data paths')
        parser.add_argument('--export-csv', help='Export hierarchy to CSV file')
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🏗️  CURRENT HIERARCHY STRUCTURE"))
        
        if options['city']:
            self._show_city_details(options['city'], options)
        elif options['state']:
            self._show_state_details(options['state'], options)
        else:
            self._show_complete_hierarchy(options)
        
        if options['export_csv']:
            self._export_to_csv(options['export_csv'])
    
    def _show_complete_hierarchy(self, options):
        """Show complete State → City → Layer hierarchy"""
        
        # ✅ FIXED: Changed 'geofeature' to 'geofeature_set'
        states = State.objects.prefetch_related('cities__layers').annotate(
            city_count=Count('cities'),
            total_layers=Count('cities__layers'),
            total_features=Count('cities__layers__geofeature_set')  # Fixed relationship name
        ).order_by('name')
        
        if not states.exists():
            self.stdout.write("❌ No states found. Run setup_hierarchy_from_excel first.")
            return
        
        self.stdout.write(f"\n📊 OVERVIEW:")
        self.stdout.write(f"   Total States: {states.count()}")
        self.stdout.write(f"   Total Cities: {sum(s.city_count for s in states)}")
        self.stdout.write(f"   Total Layers: {sum(s.total_layers for s in states)}")
        self.stdout.write(f"   Total Features: {sum(s.total_features for s in states)}")
        
        # Show hierarchy
        for state in states:
            self.stdout.write(f"\n🏛️  {state.name} ({state.slug}) [{state.code}]")
            self.stdout.write(f"   Cities: {state.city_count} | Layers: {state.total_layers} | Features: {state.total_features}")
            
            if options['show_data_paths']:
                self.stdout.write(f"   📁 Expected data path: data/{state.slug}/")
            
            # ✅ FIXED: Changed 'geofeature' to 'geofeature_set'
            cities = state.cities.annotate(
                layer_count=Count('layers'),
                feature_count=Count('layers__geofeature_set'),  # Fixed relationship name
                processed_layers=Count('layers', filter=Q(layers__is_processed=True)),
                layers_with_tiles=Count('layers', filter=Q(layers__tiles_generated=True))
            ).order_by('name')
            
            for city in cities:
                status_icon = "✅" if city.processed_layers > 0 else "⚪"
                tiles_icon = "🎯" if city.layers_with_tiles > 0 else "⚫"
                
                self.stdout.write(f"   {status_icon} {tiles_icon} {city.name} ({city.slug})")
                self.stdout.write(f"      Layers: {city.layer_count} | Features: {city.feature_count}")
                self.stdout.write(f"      Processed: {city.processed_layers}/{city.layer_count} | With tiles: {city.layers_with_tiles}/{city.layer_count}")
                
                if options['show_data_paths']:
                    self.stdout.write(f"      📁 Expected data path: data/{state.slug}/{city.slug}/")
                
                if options['with_stats']:
                    self._show_city_layer_details(city)
    
    def _show_state_details(self, state_slug, options):
        """Show detailed view of specific state"""
        try:
            state = State.objects.get(slug=state_slug)
            
            self.stdout.write(f"\n🏛️  STATE DETAILS: {state.name}")
            self.stdout.write(f"   Slug: {state.slug}")
            self.stdout.write(f"   Code: {state.code}")
            self.stdout.write(f"   Active: {state.is_active}")
            
            # ✅ FIXED: Changed 'geofeature' to 'geofeature_set'
            cities = state.cities.annotate(
                layer_count=Count('layers'),
                feature_count=Count('layers__geofeature_set')  # Fixed relationship name
            ).order_by('name')
            
            self.stdout.write(f"\n🏙️  CITIES IN {state.name} ({cities.count()}):")
            
            for city in cities:
                self.stdout.write(f"\n   📍 {city.name} ({city.slug})")
                self.stdout.write(f"      Layers: {city.layer_count} | Features: {city.feature_count}")
                
                if options['with_stats']:
                    self._show_city_layer_details(city)
                
                if options['show_data_paths']:
                    self.stdout.write(f"      📁 Data path: data/{state.slug}/{city.slug}/")
                    
                    # Show expected layer directories
                    layers = city.layers.all()
                    if layers:
                        self.stdout.write(f"      📂 Layer directories:")
                        for layer in layers:
                            self.stdout.write(f"         - {layer.slug}/")
        
        except State.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ State not found: {state_slug}"))
            self._show_available_states()
    
    def _show_city_details(self, city_slug, options):
        """Show detailed view of specific city"""
        try:
            city = City.objects.select_related('state_ref').get(slug=city_slug)
            
            self.stdout.write(f"\n🏙️  CITY DETAILS: {city.name}")
            self.stdout.write(f"   Slug: {city.slug}")
            self.stdout.write(f"   State: {city.state_ref.name if city.state_ref else city.state}")
            self.stdout.write(f"   Center: ({city.center_lat}, {city.center_lng})")
            self.stdout.write(f"   Active: {city.is_active}")
            
            if options['show_data_paths']:
                state_slug = city.state_ref.slug if city.state_ref else slugify(city.state)
                self.stdout.write(f"   📁 Data path: data/{state_slug}/{city.slug}/")
            
            self._show_city_layer_details(city, detailed=True)
            
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            self._show_available_cities()
    
    def _show_city_layer_details(self, city, detailed=False):
        """Show layers for a specific city"""
        # ❌ BROKEN: .annotate(feature_count=Count('geofeature'))
        # ✅ FIXED: Use existing feature_count field or different annotation name
        layers = city.layers.select_related('category')
        
        if not layers:
            self.stdout.write(f"      📄 No layers found")
            return
        
        # Group by category
        by_category = defaultdict(list)
        for layer in layers:
            by_category[layer.category.name].append(layer)
        
        if detailed:
            self.stdout.write(f"\n📋 LAYERS ({layers.count()}):")
            
            for category_name, category_layers in by_category.items():
                self.stdout.write(f"\n   📂 {category_name} ({len(category_layers)} layers):")
                
                for layer in category_layers:
                    status_icon = "✅" if layer.is_processed else "⚪"
                    tiles_icon = "🎯" if layer.tiles_generated else "⚫"
                    
                    # Use existing feature_count field
                    feature_count = layer.feature_count or 0
                    
                    self.stdout.write(f"      {status_icon} {tiles_icon} {layer.name} ({layer.slug})")
                    self.stdout.write(f"         Features: {feature_count:,} | Format: {layer.file_format}")
                    
                    if layer.file_path:
                        self.stdout.write(f"         Path: {layer.file_path}")
        else:
            # Compact view
            for category_name, category_layers in by_category.items():
                processed = sum(1 for l in category_layers if l.is_processed)
                # Use existing feature_count field
                total_features = sum(l.feature_count or 0 for l in category_layers)
                self.stdout.write(f"         📂 {category_name}: {len(category_layers)} layers, {processed} processed, {total_features:,} features")
    
    def _show_available_states(self):
        """Show available states for reference"""
        states = State.objects.filter(is_active=True).order_by('name')
        if states:
            self.stdout.write(f"\n📋 Available states:")
            for state in states:
                self.stdout.write(f"   • {state.name} ({state.slug})")
        else:
            self.stdout.write(f"   No states available")
    
    def _show_available_cities(self):
        """Show available cities for reference"""
        cities = City.objects.filter(is_active=True).order_by('name')
        if cities:
            self.stdout.write(f"\n📋 Available cities:")
            for city in cities[:10]:  # Show first 10
                self.stdout.write(f"   • {city.name} ({city.slug})")
            if cities.count() > 10:
                self.stdout.write(f"   ... and {cities.count() - 10} more")
        else:
            self.stdout.write(f"   No cities available")
    
    def _export_to_csv(self, filename):
        """Export hierarchy to CSV file"""
        import csv
        
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['State', 'State Code', 'City', 'Layer', 'Category', 'Processed', 'Features'])
            
            # ✅ FIXED: Changed 'geofeature' to 'geofeature_set'
            states = State.objects.prefetch_related('cities__layers__category')
            
            for state in states:
                for city in state.cities.all():
                    for layer in city.layers.all():
                        # Use existing feature_count field
                        feature_count = layer.feature_count or 0
                        
                        writer.writerow([
                            state.name,
                            state.code,
                            city.name,
                            layer.name,
                            layer.category.name,
                            'Yes' if layer.is_processed else 'No',
                            feature_count
                        ])
        
        self.stdout.write(f"✅ Exported hierarchy to {filename}")