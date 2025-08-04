# Create this file: maps/management/commands/setup_gurgaon.py

from django.core.management.base import BaseCommand
from maps.models import City, LayerCategory, CityLayerStyle, State
from maps.config import GURGAON_CONFIG
import time

class Command(BaseCommand):
    help = 'Setup Gurgaon city and categories in the database'
    
    def add_arguments(self, parser):
        parser.add_argument('--with-styles', action='store_true', help='Also create city-specific styles')
        parser.add_argument('--force', action='store_true', help='Force recreation of existing data')
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🏛️  GURGAON CITY SETUP"))
        self.stdout.write("📍 Gurgaon, Haryana - Millennium City")
        
        start_time = time.time()
        
        # Setup city
        city = self._setup_city(options['force'])
        
        # Setup categories
        categories = self._setup_categories(options['force'])
        
        # Setup styles if requested
        if options['with_styles']:
            self._setup_styles(city, categories, options['force'])
        
        total_time = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(f"\n🎉 Gurgaon setup completed in {total_time:.1f} seconds!"))
        
        # Show next steps
        self.stdout.write(f"\n📋 NEXT STEPS:")
        self.stdout.write(f"1. Copy your Gurgaon GeoJSON files to a directory")
        self.stdout.write(f"2. Run: python manage.py import_gurgaon_data --data-dir /path/to/gurgaon/files")
        self.stdout.write(f"3. Generate tiles: python manage.py generate_direct_s3_tiles --city gurgaon")
    
    def _setup_city(self, force):
        """Setup Gurgaon city"""
        config = GURGAON_CONFIG
        city_info = config['city_info']
        
        self.stdout.write(f"\n🏙️  Setting up city: {city_info['name']}")
        
        if force:
            # Delete existing city if force is True
            existing_city = City.objects.filter(slug=city_info['slug']).first()
            if existing_city:
                self.stdout.write(f"   🗑️  Deleting existing city data...")
                existing_city.delete()
        
        # Get or create Haryana state
        haryana_state, _ = State.objects.get_or_create(
            slug='haryana',
            defaults={
                'name': 'Haryana',
                'code': 'HR',
                'center_lat': 29.0588,
                'center_lng': 76.0856,
                'is_active': True,
            }
        )
        
        city, created = City.objects.get_or_create(
            slug=city_info['slug'],
            defaults={
                'name': city_info['name'],
                'state': city_info['state'],
                'state_ref': haryana_state,
                'center_lat': city_info['center_lat'],
                'center_lng': city_info['center_lng'],
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f"   ✅ Created city: {city.name}"))
        else:
            self.stdout.write(f"   📍 Using existing city: {city.name}")
            
        self.stdout.write(f"   📍 Location: {city.center_lat}, {city.center_lng}")
        self.stdout.write(f"   🏛️  State: {city.state}")
        
        return city
    
    def _setup_categories(self, force):
        """Setup all required layer categories"""
        config = GURGAON_CONFIG
        file_mappings = config['file_mappings']
        
        self.stdout.write(f"\n📂 Setting up layer categories...")
        
        # Get unique categories from file mappings
        unique_categories = set(file_mappings.values())
        
        categories = {}
        created_count = 0
        
        for category_code in unique_categories:
            category, created = LayerCategory.objects.get_or_create(
                code=category_code,
                defaults={
                    'name': category_code.replace('_', ' ').title(),
                    'description': f'{category_code} land use category for Gurgaon'
                }
            )
            
            categories[category_code] = category
            
            if created:
                created_count += 1
                self.stdout.write(f"   ✅ Created: {category.name}")
            else:
                self.stdout.write(f"   📋 Exists: {category.name}")
        
        self.stdout.write(f"   📊 Total categories: {len(unique_categories)} ({created_count} new)")
        self.stdout.write(f"   📄 Total files configured: {len(file_mappings)}")
        
        return categories
    
    def _setup_styles(self, city, categories, force):
        """Setup Gurgaon-specific styling"""
        config = GURGAON_CONFIG
        colors = config['colors']
        
        self.stdout.write(f"\n🎨 Setting up city styles...")
        
        created_count = 0
        updated_count = 0
        
        for category_code, color in colors.items():
            if category_code in categories:
                category = categories[category_code]
                
                # Check if style already exists
                existing_style = CityLayerStyle.objects.filter(
                    city=city,
                    category=category
                ).first()
                
                if existing_style and not force:
                    self.stdout.write(f"   🎯 Style exists: {category.name}")
                    continue
                
                # Create or update style
                style, created = CityLayerStyle.objects.update_or_create(
                    city=city,
                    category=category,
                    defaults={
                        'fill_color': color if color.startswith('#') else f'#{color}',
                        'stroke_color': self._darken_color(color),
                        'opacity': 0.7,
                        'stroke_width': 1,
                        'is_visible': True,
                        'min_zoom': 8,
                        'max_zoom': 18,
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f"   ✅ Created style: {category.name} -> {color}")
                else:
                    updated_count += 1
                    self.stdout.write(f"   🔄 Updated style: {category.name} -> {color}")
        
        self.stdout.write(f"   📊 Styles: {created_count} created, {updated_count} updated")
        
        # Show color summary
        self.stdout.write(f"\n🌈 Gurgaon Color Scheme:")
        main_categories = ['RESIDENTIAL', 'COMMERCIAL', 'INDUSTRIAL', 'TRANSPORT', 'UTILITIES', 'PUBLIC', 'PARKS_GREEN', 'AGRICULTURAL']
        for cat in main_categories:
            if cat in categories:
                color = colors.get(cat, '#CCCCCC')
                cat_name = categories[cat].name
                self.stdout.write(f"   {color} {cat_name}")
    
    def _darken_color(self, hex_color):
        """Darken a hex color for stroke"""
        if not hex_color.startswith('#'):
            hex_color = '#' + hex_color
        
        try:
            # Convert hex to RGB
            hex_color = hex_color.lstrip('#')
            if len(hex_color) != 6:
                return '#333333'
                
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            
            # Darken by 20%
            darkened_rgb = tuple(max(0, int(c * 0.8)) for c in rgb)
            
            # Convert back to hex
            return '#' + ''.join(f'{c:02x}' for c in darkened_rgb)
        except:
            return '#333333'  # Fallback dark color