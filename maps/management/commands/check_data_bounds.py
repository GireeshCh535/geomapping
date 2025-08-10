# maps/management/commands/check_data_bounds.py
"""
Quick check of data bounds for Bengaluru
Command: python manage.py check_data_bounds --city bengaluru
"""

from django.core.management.base import BaseCommand
from django.contrib.gis.db.models import Extent
from maps.models import City, DataLayer, LayerGroup, GeoFeature
import mercantile

class Command(BaseCommand):
    help = 'Check data bounds and suggest appropriate zoom levels'
    
    def add_arguments(self, parser):
        parser.add_argument('--city', required=True, help='City slug')
        parser.add_argument('--layer-group', help='Specific layer group to check')
    
    def handle(self, *args, **options):
        city_slug = options['city']
        layer_group_slug = options.get('layer_group')
        
        try:
            city = City.objects.get(slug=city_slug)
            
            self.stdout.write(f"🗺️  CHECKING DATA BOUNDS FOR {city.name}")
            
            if layer_group_slug:
                # Check specific layer group
                layer_group = LayerGroup.objects.get(city=city, slug=layer_group_slug)
                layers = DataLayer.objects.filter(layer_group=layer_group)
                self._check_layer_group_bounds(layer_group, layers)
            else:
                # Check all layer groups
                layer_groups = LayerGroup.objects.filter(city=city).order_by('display_order')
                
                for group in layer_groups:
                    layers = DataLayer.objects.filter(layer_group=group)
                    self._check_layer_group_bounds(group, layers)
                    
        except Exception as e:
            self.stdout.write(f"❌ Error: {e}")
    
    def _check_layer_group_bounds(self, layer_group, layers):
        """Check bounds for a specific layer group"""
        
        self.stdout.write(f"\n📁 {layer_group.name} ({layer_group.slug}):")
        
        # Count features across all layers
        total_features = sum(layer.feature_count or 0 for layer in layers)
        self.stdout.write(f"   📊 Total features: {total_features:,}")
        
        if total_features == 0:
            self.stdout.write(f"   ❌ No features - cannot calculate bounds")
            return
        
        # Get all features for this layer group
        all_features = GeoFeature.objects.filter(layer__in=layers)
        
        if not all_features.exists():
            self.stdout.write(f"   ❌ No GeoFeature records found")
            return
        
        # Calculate extent
        extent = all_features.aggregate(extent=Extent('geometry'))['extent']
        
        if not extent:
            self.stdout.write(f"   ❌ Could not calculate extent")
            return
        
        west, south, east, north = extent
        
        self.stdout.write(f"   🗺️  Bounds:")
        self.stdout.write(f"      West: {west:.6f}")
        self.stdout.write(f"      South: {south:.6f}")
        self.stdout.write(f"      East: {east:.6f}")
        self.stdout.write(f"      North: {north:.6f}")
        
        # Calculate appropriate zoom levels
        self._suggest_zoom_levels(west, south, east, north)
        
        # Test tile coordinates at different zoom levels
        center_lng = (west + east) / 2
        center_lat = (south + north) / 2
        
        self.stdout.write(f"   🎯 Center point: ({center_lng:.6f}, {center_lat:.6f})")
        
        for zoom in [8, 10, 12, 14]:
            tile = mercantile.tile(center_lng, center_lat, zoom)
            self.stdout.write(f"   📐 Zoom {zoom}: Tile ({tile.x}, {tile.y})")
    
    def _suggest_zoom_levels(self, west, south, east, north):
        """Suggest appropriate zoom levels based on data extent"""
        
        # Calculate the span
        lng_span = east - west
        lat_span = north - south
        
        # Rough zoom level estimation
        if lng_span > 1.0 or lat_span > 1.0:
            suggested_min = 6
            suggested_max = 10
        elif lng_span > 0.1 or lat_span > 0.1:
            suggested_min = 8
            suggested_max = 12
        else:
            suggested_min = 10
            suggested_max = 14
        
        self.stdout.write(f"   💡 Suggested zoom range: {suggested_min}-{suggested_max}")
        self.stdout.write(f"      Data span: {lng_span:.4f}° lng × {lat_span:.4f}° lat")