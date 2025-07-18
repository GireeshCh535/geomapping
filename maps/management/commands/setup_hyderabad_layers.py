from django.core.management.base import BaseCommand
from django.db import transaction
from maps.models import City, LayerCategory, LayerGroup, DataLayer
from maps.config import HYDERABAD_CONFIG
import os

class Command(BaseCommand):
    help = 'Setup layer groups and layers for Hyderabad'

    def handle(self, *args, **options):
        self.stdout.write('Setting up Hyderabad layer groups...')
        
        try:
            with transaction.atomic():
                # Get or create Hyderabad city
                city_info = HYDERABAD_CONFIG['city_info']
                city, created = City.objects.get_or_create(
                    slug='hyderabad',
                    defaults=city_info
                )
                if created:
                    self.stdout.write(f'Created city: {city.name}')
                
                # Process each layer group
                for group_slug, group_config in HYDERABAD_CONFIG['layer_groups'].items():
                    # Get category
                    category = LayerCategory.objects.get(code=group_config['category'])
                    
                    # Create layer group
                    group, created = LayerGroup.objects.get_or_create(
                        city=city,
                        slug=group_slug,
                        defaults={
                            'name': group_config['name'],
                            'description': group_config['description'],
                            'category': category,
                            'directory_path': group_config['directory_path'],
                            'default_color': group_config['default_color'],
                        }
                    )
                    
                    if created:
                        self.stdout.write(f'Created layer group: {group.name}')
                    
                    # Create layers in this group
                    for layer_slug, layer_config in group_config['layers'].items():
                        layer, created = DataLayer.objects.get_or_create(
                            city=city,
                            slug=f"{group_slug}_{layer_slug}",
                            defaults={
                                'name': layer_config['name'],
                                'category': category,
                                'layer_group': group,
                                'file_path': os.path.join(
                                    group_config['directory_path'],
                                    layer_config['file']
                                ),
                                'file_format': 'GEOJSON' if layer_config['file'].endswith('.geojson') else 'SHP',
                            }
                        )
                        
                        if created:
                            self.stdout.write(f'Created layer: {layer.name}')
                
                self.stdout.write(self.style.SUCCESS('Successfully set up Hyderabad layers'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}')) 