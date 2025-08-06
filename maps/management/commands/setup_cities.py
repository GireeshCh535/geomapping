# Enhanced setup_cities.py command - Fixed for Amaravati PLU-specific styling

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
            
            # Setup city-specific styles (ENHANCED FOR AMARAVATI)
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
        """Setup city-specific styles - FIXED FOR AMARAVATI PLU CODES"""
        self.stdout.write(f"   🎨 Setting up styles for {city.name}...")
        
        styles_created = 0
        colors = config.get('colors', {})
        
        # SPECIAL HANDLING FOR AMARAVATI - Map PLU codes to categories
        if city.slug == 'amaravati': ##e1e1e1
            
            # PLU to Category mapping for Amaravati
            plu_to_category = {
                'Burial Ground': 'CEMETERY',
                'C1 -Mixed use zone': 'MIXED_USE',
                'C2- General commercial zone': 'COMMERCIAL',
                'C3-Neighbourhood centre zone': 'COMMERCIAL',
                'C4-Town centre zone': 'COMMERCIAL',
                'C5-Regional centre zone': 'COMMERCIAL',
                'C6-Central business district zone': 'COMMERCIAL',
                'Commercial Vacant': 'COMMERCIAL',
                'I1-Business park zone': 'INDUSTRIAL',
                'I2-Logistics zone': 'INDUSTRIAL',
                'I3-Non polluting industry zone': 'INDUSTRIAL',
                'P1-Passive zone': 'PROTECTED',
                'P2-Active zone': 'PARKS_GREEN',
                'P3-Protected zone': 'PROTECTED',
                'P3-Protected zone Hills': 'HILLS',
                'PGN-G': 'PARKS_GREEN',
                'PGN-V': 'PARKS_GREEN',
                'R1-Village planning zone': 'RESIDENTIAL',
                'R3-Medium to high density zone': 'RESIDENTIAL',
                'R4-High density zone': 'RESIDENTIAL',
                'RAA': 'RESIDENTIAL',
                'Residential Vacant': 'RESIDENTIAL',
                'S2-Education zone': 'EDUCATION',
                'S3-Special zone': 'SPECIAL',
                'SC1a-Mixed Use': 'MIXED_USE',
                'SC1b-Mixed Use': 'MIXED_USE',
                'SP1-Passive Zone': 'PROTECTED',
                'SP2-Active Zone': 'PARKS_GREEN',
                'SP3-Protected Zone': 'PROTECTED',
                'SR2-Low Density Housing': 'RESIDENTIAL',
                'SR4-High Density Private': 'RESIDENTIAL',
                'SS1-Government Zone': 'GOVERNMENT',
                'SS2a-Education Zone': 'EDUCATION',
                'SS2b-Cultural Zone': 'CULTURAL',
                'SS2c-Health Zone': 'HEALTHCARE',
                'SS3-Special Zone': 'SPECIAL',
                'SU1-Reserve Zone': 'UTILITIES',
                'SU2-Road Network': 'TRANSPORT',
                'U1-Reserve zone': 'UTILITIES',
                'U2-Road reserve zone': 'TRANSPORT',
            }
            
            # Track which categories we've created styles for
            created_categories = set()
            
            # Process PLU codes and create styles by category
            for plu_code, color in colors.items():
                if plu_code in plu_to_category:
                    category_code = plu_to_category[plu_code]
                    
                    # Skip if we already created a style for this category
                    if category_code in created_categories:
                        continue
                        
                    try:
                        category = LayerCategory.objects.get(code=category_code)
                        
                        # Special stroke handling
                        stroke_color = '#333333'  # default
                        if plu_code in ['R1-Village planning zone', 'C2- General commercial zone', 'SU2-Road Network']:
                            stroke_color = '#000000'  # Black outline
                        
                        style, created = CityLayerStyle.objects.get_or_create(
                            city=city,
                            category=category,
                            defaults={
                                'fill_color': color,
                                'stroke_color': stroke_color,
                                'opacity': 0.7,
                                'stroke_width': 1,
                                'is_visible': True
                            }
                        )
                        
                        if not created:
                            # Update existing style
                            style.fill_color = color
                            style.stroke_color = stroke_color
                            style.save()
                            self.stdout.write(f"   🔄 Updated: {category.name} → {color}")
                        else:
                            self.stdout.write(f"   ✅ Created: {category.name} → {color}")
                            styles_created += 1
                        
                        created_categories.add(category_code)
                            
                    except LayerCategory.DoesNotExist:
                        self.stdout.write(f"   ⚠️  Category not found: {category_code}")
                else:
                    # Try to find standard category codes in colors
                    try:
                        category = LayerCategory.objects.get(code=plu_code)
                        
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
                        
                        if not created:
                            style.fill_color = color
                            style.save()
                            self.stdout.write(f"   🔄 Updated: {category.name} → {color}")
                        else:
                            self.stdout.write(f"   ✅ Created: {category.name} → {color}")
                            styles_created += 1
                            
                    except LayerCategory.DoesNotExist:
                        # This is expected for PLU codes that don't match category codes
                        pass
            
            return styles_created
        
        # Regular processing for other cities (unchanged)
        for category_code, color in colors.items():
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
                
                if not created:
                    # Update existing style
                    style.fill_color = color
                    style.save()
                    self.stdout.write(f"   🔄 Updated: {category.name} → {color}")
                else:
                    self.stdout.write(f"   ✅ Created: {category.name} → {color}")
                    styles_created += 1
                    
            except LayerCategory.DoesNotExist:
                self.stdout.write(f"   ⚠️  Category not found: {category_code}")
        
        return styles_created

    def _setup_amaravati_plu_styles(self, city, plu_colors):
        """Setup Amaravati PLU-specific styles with proper category mapping"""
        
        # Updated PLU color mapping with your exact specifications
        amaravati_plu_colors = {
            'Burial Ground': '#E39E00',                          # Cemetery
            'C1 -Mixed use zone': '#73B2FF',                     # Mixed Use  
            'C2- General commercial zone': '#00C5FF',            # Commercial
            'C3-Neighbourhood centre zone': '#00C5FF',           # Commercial
            'C4-Town centre zone': '#00A9E6',                    # Commercial
            'C5-Regional centre zone': '#0070FF',                # Commercial
            'C6-Central business district zone': '#005CE6',      # Commercial
            'Commercial Vacant': '#C5E2FF',                      # Commercial
            'I1-Business park zone': '#FFEBE8',                  # Industrial
            'I2-Logistics zone': '#FF73DF',                      # Industrial
            'I3-Non polluting industry zone': '#A900E6',         # Industrial
            'P1-Passive zone': '#267300',                        # Protected
            'P2-Active zone': '#38A800',                         # Parks/Green
            'P3-Protected zone': '#BEE8FF',                      # Protected
            'P3-Protected zone Hills': '#4C7300',                # Hills
            'PGN-G': '#4C7300',                                  # Parks/Green
            'PGN-V': '#897044',                                  # Parks/Green
            'R1-Village planning zone': '#FFFFFF',               # Residential (Hatched)
            'R3-Medium to high density zone': '#F5CA7A',         # Residential
            'R4-High density zone': '#E69800',                  # Residential
            'RAA': '#FFAA00',                                    # Residential
            'Residential Vacant': '#FFD37F',                     # Residential
            'S2-Education zone': '#FF7F7F',                      # Education
            'S3-Special zone': '#D7B09E',                        # Special
            'SC1a-Mixed Use': '#0070FF',                         # Mixed Use
            'SC1b-Mixed Use': '#73B2FF',                         # Mixed Use
            'SP1-Passive Zone': '#267300',                       # Protected
            'SP2-Active Zone': '#38A800',                        # Parks/Green
            'SP3-Protected Zone': '#00C5FF',                     # Protected
            'SR2-Low Density Housing': '#FFFFBE',               # Residential
            'SR4-High Density Private': '#FFAA00',              # Residential
            'SS1-Government Zone': '#E60000',                    # Government
            'SS2a-Education Zone': '#FF7F7F',                    # Education
            'SS2b-Cultural Zone': '#C500FF',                     # Cultural
            'SS2c-Health Zone': '#D3FFBE',                       # Healthcare
            'SS3-Special Zone': '#A83800',                       # Special
            'SU1-Reserve Zone': '#e38f8f',                       # Utilities
            'SU2-Road Network': '#FFFFFF',                       # Transport
            'U1-Reserve zone': '#CCCCCC',                        # Utilities
            'U2-Road reserve zone': '#000000',                   # Transport
        }
        
        # PLU to Category mapping for Amaravati
        plu_to_category_mapping = {
            'Burial Ground': 'CEMETERY',
            'C1 -Mixed use zone': 'MIXED_USE',
            'C2- General commercial zone': 'COMMERCIAL',
            'C3-Neighbourhood centre zone': 'COMMERCIAL',
            'C4-Town centre zone': 'COMMERCIAL',
            'C5-Regional centre zone': 'COMMERCIAL',
            'C6-Central business district zone': 'COMMERCIAL',
            'Commercial Vacant': 'COMMERCIAL',
            'I1-Business park zone': 'INDUSTRIAL',
            'I2-Logistics zone': 'INDUSTRIAL',
            'I3-Non polluting industry zone': 'INDUSTRIAL',
            'P1-Passive zone': 'PROTECTED',
            'P2-Active zone': 'PARKS_GREEN',
            'P3-Protected zone': 'PROTECTED',
            'P3-Protected zone Hills': 'HILLS',
            'PGN-G': 'PARKS_GREEN',
            'PGN-V': 'PARKS_GREEN',
            'R1-Village planning zone': 'RESIDENTIAL',
            'R3-Medium to high density zone': 'RESIDENTIAL',
            'R4-High density zone': 'RESIDENTIAL',
            'RAA': 'RESIDENTIAL',
            'Residential Vacant': 'RESIDENTIAL',
            'S2-Education zone': 'EDUCATION',
            'S3-Special zone': 'SPECIAL',
            'SC1a-Mixed Use': 'MIXED_USE',
            'SC1b-Mixed Use': 'MIXED_USE',
            'SP1-Passive Zone': 'PROTECTED',
            'SP2-Active Zone': 'PARKS_GREEN',
            'SP3-Protected Zone': 'PROTECTED',
            'SR2-Low Density Housing': 'RESIDENTIAL',
            'SR4-High Density Private': 'RESIDENTIAL',
            'SS1-Government Zone': 'GOVERNMENT',
            'SS2a-Education Zone': 'EDUCATION',
            'SS2b-Cultural Zone': 'CULTURAL',
            'SS2c-Health Zone': 'HEALTHCARE',
            'SS3-Special Zone': 'SPECIAL',
            'SU1-Reserve Zone': 'UTILITIES',
            'SU2-Road Network': 'TRANSPORT',
            'U1-Reserve zone': 'UTILITIES',
            'U2-Road reserve zone': 'TRANSPORT',
        }
        
        styles_created = 0
        
        # Create separate CityLayerStyle for each PLU code by category
        category_styles = {}  # Track one style per category
        
        for plu_code, color in amaravati_plu_colors.items():
            category_code = plu_to_category_mapping.get(plu_code)
            
            if not category_code:
                self.stdout.write(f"   ⚠️  No category mapping for PLU: {plu_code}")
                continue
                
            try:
                category = LayerCategory.objects.get(code=category_code)
                
                # Store PLU-specific information in the style
                # For now, create one style per category (can be enhanced later for PLU-specific styles)
                if category_code not in category_styles:
                    
                    # Special stroke handling for specific PLU codes
                    stroke_color = '#333333'  # default
                    stroke_width = 1
                    fill_pattern = 'solid'  # default
                    
                    # Special styling based on your specifications
                    if plu_code == 'R1-Village planning zone':
                        stroke_color = '#000000'  # Black outline + hatched
                        fill_pattern = 'hatched'
                    elif plu_code == 'C2- General commercial zone':
                        stroke_color = '#000000'  # Black outline
                    elif plu_code == 'SU2-Road Network':
                        stroke_color = '#000000'  # Black outline
                    elif plu_code == 'Burial Ground':
                        fill_pattern = 'dotted'  # Dotted pattern
                    
                    style, created = CityLayerStyle.objects.get_or_create(
                        city=city,
                        category=category,
                        defaults={
                            'fill_color': color,
                            'stroke_color': stroke_color,
                            'opacity': 0.7,
                            'stroke_width': stroke_width,
                            'is_visible': True,
                            # Store PLU-specific metadata (if your model supports it)
                            # 'plu_pattern': fill_pattern,  # Add this field to model if needed
                        }
                    )
                    
                    if not created:
                        # Update existing style
                        style.fill_color = color
                        style.stroke_color = stroke_color
                        style.save()
                        self.stdout.write(f"   🔄 Updated: {category.name} → {color}")
                    else:
                        self.stdout.write(f"   ✅ Created: {category.name} → {color}")
                        styles_created += 1
                        
                    category_styles[category_code] = style
                else:
                    # Category already has a style, just log the PLU mapping
                    self.stdout.write(f"   📍 PLU Mapped: {plu_code} → {category.name} ({color})")
                    
            except LayerCategory.DoesNotExist:
                self.stdout.write(f"   ⚠️  Category not found for PLU: {plu_code} → {category_code}")
        
        return styles_created

    def _setup_plu_mappings(self, city, config):
        """Setup PLU code mappings for a city"""
        plu_mapping = config.get('plu_mapping', {})
        if not plu_mapping:
            return 0
        
        self.stdout.write(f"   🗺️  Setting up PLU mappings for {city.name}...")
        
        mappings_created = 0
        for plu_code, plu_info in plu_mapping.items():
            try:
                category = LayerCategory.objects.get(code=plu_info['category'])
                
                mapping, created = PLUCodeMapping.objects.get_or_create(
                    city=city,
                    plu_code=plu_code,
                    defaults={
                        'category': category,
                        'description': plu_info.get('description', ''),
                        'is_active': True
                    }
                )
                
                if created:
                    mappings_created += 1
                    self.stdout.write(f"   ✅ Created PLU mapping: {plu_code} → {category.name}")
                else:
                    self.stdout.write(f"   📋 PLU mapping exists: {plu_code} → {category.name}")
                    
            except LayerCategory.DoesNotExist:
                self.stdout.write(f"   ⚠️  Category not found for PLU: {plu_code} → {plu_info.get('category')}")
        
        return mappings_created