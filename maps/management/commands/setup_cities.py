# management/commands/setup_cities.py - Enhanced with PLU support

from django.core.management.base import BaseCommand
from maps.models import City, LayerCategory, CityLayerStyle, PLUCodeMapping
from maps.config import CITY_CONFIGS, get_plu_mapping

class Command(BaseCommand):
    help = 'Setup cities, categories, and PLU mappings from configuration'
    
    def add_arguments(self, parser):
        parser.add_argument('--city', help='Setup specific city only')
        parser.add_argument('--with-plu', action='store_true', help='Setup PLU code mappings')
        parser.add_argument('--reset', action='store_true', help='Reset existing data')
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Setting up cities and categories..."))
        
        if options['reset']:
            self.stdout.write("⚠️  Resetting existing data...")
            if options['city']:
                City.objects.filter(slug=options['city']).delete()
            else:
                City.objects.all().delete()
                LayerCategory.objects.all().delete()
        
        # Create all categories first
        categories_created = self._create_categories()
        
        # Setup cities
        if options['city']:
            cities_data = {options['city']: CITY_CONFIGS[options['city']]}
        else:
            cities_data = CITY_CONFIGS
        
        cities_created = 0
        styles_created = 0
        plu_mappings_created = 0
        
        for city_slug, config in cities_data.items():
            self.stdout.write(f"\n🏙️  Setting up {config['city_info']['name']}...")
            
            # Create city
            city, created = City.objects.get_or_create(
                slug=city_slug,
                defaults=config['city_info']
            )
            
            if created:
                cities_created += 1
                self.stdout.write(f"   ✅ Created city: {city.name}")
            else:
                self.stdout.write(f"   ℹ️  City already exists: {city.name}")
            
            # Setup city-specific styles
            city_styles = self._setup_city_styles(city, config)
            styles_created += city_styles
            
            # Setup PLU mappings if requested and available
            if options['with_plu'] and 'plu_mapping' in config:
                plu_created = self._setup_plu_mappings(city, config)
                plu_mappings_created += plu_created
        
        # Summary
        self.stdout.write(f"\n📊 Setup Summary:")
        self.stdout.write(f"   Categories created: {categories_created}")
        self.stdout.write(f"   Cities created: {cities_created}")
        self.stdout.write(f"   Styles created: {styles_created}")
        if options['with_plu']:
            self.stdout.write(f"   PLU mappings created: {plu_mappings_created}")
        
        self.stdout.write(self.style.SUCCESS("\n✅ Setup completed successfully!"))
    
    def _create_categories(self):
        """Create all layer categories"""
        self.stdout.write("📋 Creating layer categories...")
        
        categories_data = [
            ('Residential', 'RESIDENTIAL'),
            ('Commercial', 'COMMERCIAL'),
            ('Mixed Use', 'MIXED_USE'),
            ('Industrial', 'INDUSTRIAL'),
            ('High Tech', 'HIGH_TECH'),
            ('Government', 'GOVERNMENT'),
            ('Public/Semi-Public', 'PUBLIC'),
            ('Education', 'EDUCATION'),
            ('Healthcare', 'HEALTHCARE'),
            ('Cultural', 'CULTURAL'),
            ('Defense', 'DEFENSE'),
            ('Transportation', 'TRANSPORT'),
            ('Utilities/Infrastructure', 'UTILITIES'),
            ('Protected/Forest', 'PROTECTED'),
            ('Parks/Green Spaces', 'PARKS_GREEN'),
            ('Water Bodies', 'WATER_BODIES'),
            ('Agricultural', 'AGRICULTURAL'),
            ('Cemetery', 'CEMETERY'),
            ('Drains', 'DRAINS'),
            ('Hills/Topographic', 'HILLS'),
            ('Special Use', 'SPECIAL'),
            ('Unclassified', 'UNCLASSIFIED'),
        ]
        
        created_count = 0
        for name, code in categories_data:
            category, created = LayerCategory.objects.get_or_create(
                code=code,
                defaults={'name': name}
            )
            if created:
                created_count += 1
                self.stdout.write(f"   ✅ Created category: {name}")
        
        return created_count
    
    def _setup_city_styles(self, city, config):
        """Setup city-specific styles"""
        self.stdout.write(f"   🎨 Setting up styles for {city.name}...")
        
        styles_created = 0
        for category_code, color in config['colors'].items():
            try:
                category = LayerCategory.objects.get(code=category_code)
                style, created = CityLayerStyle.objects.get_or_create(
                    city=city,
                    category=category,
                    defaults={
                        'fill_color': color,
                        'stroke_color': '#333333',
                        'opacity': 0.7,
                        'stroke_width': 1,
                        'is_visible': True
                    }
                )
                
                if created:
                    styles_created += 1
                    self.stdout.write(f"      ✅ Style: {category.name} → {color}")
                else:
                    # Update existing style color
                    if style.fill_color != color:
                        style.fill_color = color
                        style.save()
                        self.stdout.write(f"      🔄 Updated: {category.name} → {color}")
                
            except LayerCategory.DoesNotExist:
                self.stdout.write(f"      ⚠️  Category not found: {category_code}")
        
        return styles_created
    
    def _setup_plu_mappings(self, city, config):
        """Setup PLU code mappings for a city - fixed for enhanced structure"""
        self.stdout.write(f"   🏷️  Setting up PLU mappings for {city.name}...")
        
        plu_mapping = config.get('plu_mapping', {})
        if not plu_mapping:
            self.stdout.write(f"      ℹ️  No PLU mappings configured for {city.name}")
            return 0
        
        mappings_created = 0
        for plu_code, plu_info in plu_mapping.items():
            try:
                # Skip if no category defined (shouldn't happen with fixed config)
                if 'category' not in plu_info:
                    self.stdout.write(f"      ⚠️  No category defined for PLU code: {plu_code}")
                    continue
                    
                category_code = plu_info['category']
                
                # Get the category object
                try:
                    category = LayerCategory.objects.get(code=category_code)
                except LayerCategory.DoesNotExist:
                    self.stdout.write(f"      ⚠️  Category not found: {category_code} for PLU {plu_code}")
                    continue
                
                mapping, created = PLUCodeMapping.objects.get_or_create(
                    city=city,
                    plu_code=plu_code,
                    defaults={
                        'mapped_category': category,
                        'plu_description': plu_info.get('description', ''),
                        'secondary_codes': plu_info.get('secondary_codes', []),
                        'notes': f"Examples: {', '.join(plu_info.get('examples', []))}"
                    }
                )
                
                if created:
                    mappings_created += 1
                    self.stdout.write(f"      ✅ PLU: {plu_code} → {category.name}")
                else:
                    # Update existing mapping
                    mapping.plu_description = plu_info.get('description', '')
                    mapping.secondary_codes = plu_info.get('secondary_codes', [])
                    mapping.notes = f"Examples: {', '.join(plu_info.get('examples', []))}"
                    mapping.save()
                    self.stdout.write(f"      🔄 Updated: {plu_code} → {category.name}")
                    
            except Exception as e:
                self.stdout.write(f"      ❌ Error creating PLU mapping for {plu_code}: {str(e)}")
                continue
        
        return mappings_created