# maps/management/commands/setup_required_categories.py
"""
Setup all required LayerCategory objects for the hierarchical structure
Command: python manage.py setup_required_categories
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from maps.models import LayerCategory

class Command(BaseCommand):
    help = 'Setup all required LayerCategory objects for layer groups'
    
    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Force recreation of existing categories')
        parser.add_argument('--show-existing', action='store_true', help='Show existing categories')
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🏗️  SETTING UP REQUIRED LAYER CATEGORIES"))
        
        if options['show_existing']:
            self._show_existing_categories()
            return
        
        # Define required categories for layer groups
        required_categories = {
            'MIXED_USE': {
                'name': 'Mixed Use',
                'description': 'Mixed land use areas including master plans',
                'default_color': '#9DC1CB',
                'display_order': 1
            },
            'TRANSPORT': {
                'name': 'Transportation',
                'description': 'Transportation infrastructure (roads, highways, metro)',
                'default_color': '#828282',
                'display_order': 2
            },
            'INDUSTRIAL': {
                'name': 'Industrial',
                'description': 'Industrial areas and workspaces',
                'default_color': '#AA66B2',
                'display_order': 3
            },
            'RESIDENTIAL': {
                'name': 'Residential',
                'description': 'Residential areas and housing',
                'default_color': '#FFEBAF',
                'display_order': 4
            },
            'COMMERCIAL': {
                'name': 'Commercial',
                'description': 'Commercial and business areas',
                'default_color': '#73B2FF',
                'display_order': 5
            },
            'GOVERNMENT': {
                'name': 'Government',
                'description': 'Government and public institutions',
                'default_color': '#E60000',
                'display_order': 6
            },
            'PUBLIC': {
                'name': 'Public/Semi-Public',
                'description': 'Public and semi-public facilities',
                'default_color': '#E60000',
                'display_order': 7
            },
            'WATER_BODIES': {
                'name': 'Water Bodies',
                'description': 'Lakes, tanks, and water features',
                'default_color': '#BEE8FF',
                'display_order': 8
            },
            'PARKS_GREEN': {
                'name': 'Parks & Green Spaces',
                'description': 'Parks, gardens, and green spaces',
                'default_color': '#98E600',
                'display_order': 9
            },
            'AGRICULTURAL': {
                'name': 'Agricultural',
                'description': 'Agricultural land',
                'default_color': '#9DC1CB',
                'display_order': 10
            },
            'UTILITIES': {
                'name': 'Utilities/Infrastructure',
                'description': 'Utility facilities and infrastructure',
                'default_color': '#D79E9E',
                'display_order': 11
            },
            'PROTECTED': {
                'name': 'Protected/Forest',
                'description': 'Protected areas and forest land',
                'default_color': '#70A800',
                'display_order': 12
            },
            'DEFENSE': {
                'name': 'Defense',
                'description': 'Defense and military areas',
                'default_color': '#E0B8FC',
                'display_order': 13
            },
            'HIGH_TECH': {
                'name': 'High Tech',
                'description': 'High tech and IT parks',
                'default_color': '#C29ED7',
                'display_order': 14
            },
            'DRAINS': {
                'name': 'Drains',
                'description': 'Drainage systems',
                'default_color': '#267300',
                'display_order': 15
            },
            'UNCLASSIFIED': {
                'name': 'Unclassified',
                'description': 'Unclassified land use',
                'default_color': '#E1E1E1',
                'display_order': 99
            }
        }
        
        with transaction.atomic():
            created_count = 0
            updated_count = 0
            
            for code, config in required_categories.items():
                category, created = LayerCategory.objects.get_or_create(
                    code=code,
                    defaults=config
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f"✅ Created category: {category.name} ({code})")
                else:
                    if options['force']:
                        # Update existing category
                        for key, value in config.items():
                            setattr(category, key, value)
                        category.save()
                        updated_count += 1
                        self.stdout.write(f"🔄 Updated category: {category.name} ({code})")
                    else:
                        self.stdout.write(f"📋 Existing category: {category.name} ({code})")
        
        self.stdout.write(f"\n📊 SETUP RESULTS:")
        self.stdout.write(f"   Categories created: {created_count}")
        self.stdout.write(f"   Categories updated: {updated_count}")
        self.stdout.write(f"   Total categories: {LayerCategory.objects.count()}")
        
        self.stdout.write(f"\n✅ Layer categories setup completed!")
        self.stdout.write(f"🚀 Now you can run: python manage.py import_city_layers --city bengaluru --data-dir 'data/karnataka/bengaluru' --layer-groups 'master_plan,highways,metro,workspace'")
    
    def _show_existing_categories(self):
        """Show all existing layer categories"""
        categories = LayerCategory.objects.all().order_by('display_order', 'name')
        
        self.stdout.write(f"\n📋 EXISTING LAYER CATEGORIES ({categories.count()} total):")
        
        for category in categories:
            self.stdout.write(f"   {category.code}: {category.name}")
            self.stdout.write(f"      Color: {category.default_color}")
            self.stdout.write(f"      Description: {category.description}")
            self.stdout.write(f"      Active: {category.is_active}")
            self.stdout.write("")