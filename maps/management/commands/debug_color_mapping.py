"""
Debug command to check color mapping and zone names
Usage: python manage.py debug_color_mapping --city bengaluru
"""

from django.core.management.base import BaseCommand
from maps.models import City, GeoFeature, CityZoneMapping, CityLayerStyle
from collections import Counter
import json

class Command(BaseCommand):
    help = 'Debug color mapping and zone names for a city'
    
    def add_arguments(self, parser):
        parser.add_argument('--city', type=str, required=True, help='City slug')
        parser.add_argument('--layer', type=str, help='Optional specific layer slug')
        parser.add_argument('--limit', type=int, default=100, help='Limit number of features to check')
    
    def handle(self, *args, **options):
        city_slug = options['city']
        layer_slug = options.get('layer')
        limit = options['limit']
        
        try:
            city = City.objects.get(slug=city_slug)
            
            self.stdout.write(f'🔍 Debugging color mapping for: {city.name}')
            
            # Check CityZoneMapping
            self.stdout.write('\n📊 CITY ZONE MAPPINGS:')
            zone_mappings = CityZoneMapping.objects.filter(city=city)
            for mapping in zone_mappings:
                self.stdout.write(f'   Zone: "{mapping.zone_name}" → Color: {mapping.style.fill_color}')
            
            # Check CityLayerStyle  
            self.stdout.write('\n🎨 CITY LAYER STYLES:')
            layer_styles = CityLayerStyle.objects.filter(city=city)
            for style in layer_styles:
                self.stdout.write(f'   Category: {style.category.code} → Color: {style.fill_color}')
            
            # Check actual feature data
            if layer_slug:
                features = GeoFeature.objects.filter(layer__city=city, layer__slug=layer_slug)[:limit]
            else:
                features = GeoFeature.objects.filter(layer__city=city)[:limit]
            
            self.stdout.write(f'\n📋 FEATURE DATA SAMPLE ({features.count()} features):')
            
            # Collect zone names
            zone_names = []
            plu_codes = []
            source_layers = []
            
            for feature in features:
                # Check zone_category
                if feature.zone_category:
                    zone_names.append(feature.zone_category)
                
                # Check PLU fields for Bengaluru
                if city_slug == 'bengaluru':
                    if feature.plu_secondary_1:
                        plu_codes.append(feature.plu_secondary_1)
                    if feature.source_layer_name:
                        source_layers.append(feature.source_layer_name)
                    
                    # Check original properties
                    if feature.properties:
                        props = feature.properties
                        if 'PLU_Tp_pro' in props:
                            zone_names.append(props['PLU_Tp_pro'])
                        if 'PLU_NAME' in props:
                            zone_names.append(props['PLU_NAME'])
            
            # Show most common values
            if zone_names:
                self.stdout.write('\n📊 Most common zone_category values:')
                for zone, count in Counter(zone_names).most_common(10):
                    self.stdout.write(f'   "{zone}": {count} features')
            
            if plu_codes and city_slug == 'bengaluru':
                self.stdout.write('\n📊 Most common plu_secondary_1 values:')
                for plu, count in Counter(plu_codes).most_common(10):
                    self.stdout.write(f'   "{plu}": {count} features')
            
            if source_layers and city_slug == 'bengaluru':
                self.stdout.write('\n📊 Most common source_layer_name values:')
                for source, count in Counter(source_layers).most_common(10):
                    self.stdout.write(f'   "{source}": {count} features')
            
            # Show sample feature properties
            if features.exists():
                sample_feature = features[0]
                self.stdout.write(f'\n🔍 SAMPLE FEATURE #{sample_feature.id}:')
                self.stdout.write(f'   Layer: {sample_feature.layer.slug}')
                self.stdout.write(f'   zone_category: "{sample_feature.zone_category}"')
                
                if city_slug == 'bengaluru':
                    self.stdout.write(f'   plu_primary_code: "{sample_feature.plu_primary_code}"')
                    self.stdout.write(f'   plu_secondary_1: "{sample_feature.plu_secondary_1}"')
                    self.stdout.write(f'   plu_proposed_use: "{sample_feature.plu_proposed_use}"')
                    self.stdout.write(f'   source_layer_name: "{sample_feature.source_layer_name}"')
                
                if sample_feature.properties:
                    self.stdout.write('   Original properties:')
                    for key, value in list(sample_feature.properties.items())[:10]:
                        self.stdout.write(f'     {key}: "{value}"')
            
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ City {city_slug} not found'))