# maps/management/commands/import_city_styles.py
# Django management command to import city-specific styles with pattern support

from django.core.management.base import BaseCommand
from django.db import transaction
from maps.models import City, LayerCategory, CityLayerStyle, CityZoneMapping
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Import city-specific layer styles with pattern support'
    
    def handle(self, *args, **options):
        """Import styles for all cities"""
        self.import_warangal_styles()
        self.import_visakhapatnam_styles()
        self.import_amaravati_styles()
        self.import_bengaluru_styles()
        
        self.stdout.write(self.style.SUCCESS('Successfully imported all city styles'))
    
    @transaction.atomic
    def import_warangal_styles(self):
        """Import Warangal styles - all solid colors"""
        try:
            city = City.objects.get(slug='warangal')
            
            # Warangal uses PLU and PLU_NAME fields
            # Colors from config.py
            warangal_styles = {
                'AGRICULTURAL': {'color': '#9DC1CB', 'pattern': 'SOLID'},
                'TRANSPORT': {'color': '#FFB6C1', 'pattern': 'SOLID'},  # AirStrip
                'COMMERCIAL': {'color': '#73B2FF', 'pattern': 'SOLID'},
                'PROTECTED': {'color': '#228B22', 'pattern': 'SOLID'},  # Forest
                'MIXED_USE': {'color': '#FF8C00', 'pattern': 'SOLID'},  # Growth Corridor
                'INDUSTRIAL': {'color': '#AA66B2', 'pattern': 'SOLID'},
            }
            
            for category_code, style_data in warangal_styles.items():
                category, _ = LayerCategory.objects.get_or_create(
                    code=category_code,
                    defaults={'name': category_code.replace('_', ' ').title()}
                )
                
                CityLayerStyle.objects.update_or_create(
                    city=city,
                    category=category,
                    defaults={
                        'fill_color': style_data['color'],
                        'fill_pattern': style_data['pattern'],
                        'stroke_width': 0,  # No borders as requested
                        'opacity': 0.8
                    }
                )
            
            self.stdout.write(f"✓ Imported Warangal styles")
            
        except City.DoesNotExist:
            self.stdout.write(self.style.WARNING('Warangal city not found'))
    
    @transaction.atomic
    def import_visakhapatnam_styles(self):
        """Import Visakhapatnam styles with patterns"""
        try:
            city = City.objects.get(slug='visakhapatnam')
            
            # Complex styles with patterns
            vizag_styles = [
                # Solid fills
                {'zone': 'Agricultural Use Zone', 'color': '#D3FFBE', 'pattern': 'SOLID'},
                {'zone': 'Blue Zone Water Bodies', 'color': '#73FFDF', 'pattern': 'SOLID'},
                {'zone': 'Brown Zone Hills', 'color': '#A87000', 'pattern': 'SOLID'},
                {'zone': 'Commercial Use Zone', 'color': '#004DA8', 'pattern': 'SOLID'},
                
                # Hatched patterns
                {'zone': 'Existing Crematorium / Burial Ground / Graveyard',
                 'pattern': 'HATCHED', 'pattern_color': '#FF0000', 'secondary_fill': '#FFFFFF'},
                {'zone': 'Existing Educational Facilities',
                 'pattern': 'HATCHED', 'pattern_color': '#000000', 'secondary_fill': '#FF0000'},
                {'zone': 'Proposed Industrial Use Zone',
                 'pattern': 'HATCHED', 'pattern_color': '#FFFFFF', 'secondary_fill': '#C500FF'},
                {'zone': 'Existing Public Utilities',
                 'pattern': 'HATCHED', 'pattern_color': '#E60000', 'secondary_fill': '#FF7F7F'},
                {'zone': 'Existing Religious Facilities',
                 'pattern': 'HATCHED', 'pattern_color': '#55FF00', 'secondary_fill': '#FF0000'},
                {'zone': 'Existing Road / Railway Line Area',
                 'pattern': 'HATCHED', 'pattern_color': '#828282', 'secondary_fill': '#FFFFFF'},
                {'zone': 'Proposed PSP Use Zone',
                 'pattern': 'HATCHED', 'pattern_color': '#FF0000', 'secondary_fill': '#FFFFFF'},
                {'zone': 'Proposed Public Utilities Use Zone',
                 'pattern': 'HATCHED', 'pattern_color': '#FFFFFF', 'secondary_fill': '#F57A7A'},
                {'zone': 'Proposed Transportation Facility Use Zone',
                 'pattern': 'HATCHED', 'pattern_color': '#FFFFFF', 'secondary_fill': '#343434'},
                {'zone': 'Special Area Use Zone',
                 'pattern': 'HATCHED', 'pattern_color': '#002673', 'secondary_fill': '#FFFFFF'},
                
                # Dotted patterns
                {'zone': 'Existing Health Facilities',
                 'pattern': 'DOTTED', 'pattern_color': '#CCCCCC', 'secondary_fill': '#FF0000'},
                {'zone': 'Mixed Use Zone 3',
                 'pattern': 'HATCHED', 'pattern_color': '#E1E1E1', 'secondary_fill': '#E69800'},
                {'zone': 'Mixed Use Zone 4',
                 'pattern': 'DOTTED', 'pattern_color': '#000000', 'secondary_fill': '#FFAA00'},
                {'zone': 'Sea / River / Accreted Land',
                 'pattern': 'DOTTED', 'pattern_color': '#E39E00', 'secondary_fill': '#D7C29E'},
                {'zone': 'Water Body Buffer',
                 'pattern': 'DOTTED', 'pattern_color': '#267300', 'secondary_fill': '#4CE600'},
                
                # More solid fills
                {'zone': 'Existing Industrial Area', 'color': '#C500FF', 'pattern': 'SOLID'},
                {'zone': 'Existing Government / Semi Government Facilities', 'color': '#FF0000', 'pattern': 'SOLID'},
                {'zone': 'Existing Recreational / Playgrounds / Parks / Layout Open Space', 'color': '#55FF00', 'pattern': 'SOLID'},
                {'zone': 'Existing Transportation Facility', 'color': '#686868', 'pattern': 'SOLID'},
                {'zone': 'Green Zone Forest', 'color': '#00734C', 'pattern': 'SOLID'},
                {'zone': 'Kambalakonda Eco Sensitive Zone / NAOB Buffer / Zoological Park', 'color': '#D7C29E', 'pattern': 'SOLID'},
                {'zone': 'Kambalakonda WildLife Sanctuary / Biodiversity Area', 'color': '#38A800', 'pattern': 'SOLID'},
                {'zone': 'Mixed Use Zone 1', 'color': '#FFAA00', 'pattern': 'SOLID'},
                {'zone': 'Mixed Use Zone 2', 'color': '#FFD37F', 'pattern': 'SOLID'},
                {'zone': 'Proposed Recreational Use Zone', 'color': '#4C7300', 'pattern': 'SOLID'},
                {'zone': 'Proposed Road Network', 'color': '#000000', 'pattern': 'SOLID'},
                {'zone': 'Residential Use Zone', 'color': '#FFFF73', 'pattern': 'SOLID'},
            ]
            
            for style_data in vizag_styles:
                # Determine category based on zone name
                category_code = self._determine_category(style_data['zone'])
                category, _ = LayerCategory.objects.get_or_create(
                    code=category_code,
                    defaults={'name': category_code.replace('_', ' ').title()}
                )
                
                # Create style
                style_obj, _ = CityLayerStyle.objects.update_or_create(
                    city=city,
                    category=category,
                    defaults={
                        'fill_color': style_data.get('color', style_data.get('secondary_fill', '#FFFFFF')),
                        'fill_pattern': style_data.get('pattern', 'SOLID'),
                        'pattern_color': style_data.get('pattern_color', ''),
                        'secondary_fill_color': style_data.get('secondary_fill', ''),
                        'pattern_spacing': 12 if style_data.get('pattern') == 'HATCHED' else 15,
                        'pattern_size': 3 if style_data.get('pattern') == 'DOTTED' else 2,
                        'stroke_width': 0,  # No borders
                        'opacity': 0.8
                    }
                )
                
                # Create zone mapping
                CityZoneMapping.objects.update_or_create(
                    city=city,
                    zone_name=style_data['zone'],
                    defaults={
                        'category': category,
                        'style': style_obj,
                        'is_active': True
                    }
                )
            
            self.stdout.write(f"✓ Imported Visakhapatnam styles with patterns")
            
        except City.DoesNotExist:
            self.stdout.write(self.style.WARNING('Visakhapatnam city not found'))
    
    @transaction.atomic
    def import_amaravati_styles(self):
        """Import Amaravati styles with patterns"""
        try:
            city = City.objects.get(slug='amaravati')
            
            amaravati_styles = [
                # Dotted pattern
                {'zone': 'Burial Ground', 'pattern': 'DOTTED', 
                 'pattern_color': '#E39E00', 'secondary_fill': '#FFFFFF'},
                
                # Solid fills with outlines
                {'zone': 'C1 - Mixed Use Zone', 'color': '#73B2FF', 'pattern': 'SOLID'},
                {'zone': 'C2 - General Commercial Zone', 'color': '#00C5FF', 
                 'pattern': 'SOLID', 'outline': '#000000'},
                {'zone': 'C3 - Neighbourhood Centre Zone', 'color': '#00C5FF', 'pattern': 'SOLID'},
                {'zone': 'C4 - Town Centre Zone', 'color': '#00A9E6', 'pattern': 'SOLID'},
                {'zone': 'C5 - Regional Centre Zone', 'color': '#0070FF', 'pattern': 'SOLID'},
                {'zone': 'C6 - Central Business District Zone', 'color': '#005CE6', 'pattern': 'SOLID'},
                {'zone': 'Commercial Vacant', 'color': '#C5E2FF', 'pattern': 'SOLID'},
                
                # Industrial zones
                {'zone': 'I1 - Business Park Zone', 'color': '#FFBEE8', 'pattern': 'SOLID'},
                {'zone': 'I2 - Logistics Zone', 'color': '#FF73DF', 'pattern': 'SOLID'},
                {'zone': 'I3 - Non Polluting Industry Zone', 'color': '#A900E6', 'pattern': 'SOLID'},
                
                # Parks and protected zones
                {'zone': 'P1 - Passive Zone', 'color': '#267300', 'pattern': 'SOLID'},
                {'zone': 'P2 - Active Zone', 'color': '#38A800', 'pattern': 'SOLID'},
                {'zone': 'P3 - Protected Zone', 'color': '#BEE8FF', 'pattern': 'SOLID'},
                {'zone': 'P3 - Protected Zone Hills', 'color': '#4C7300', 'pattern': 'SOLID'},
                {'zone': 'PGN-G', 'color': '#4C7300', 'pattern': 'SOLID'},
                {'zone': 'PGN-V', 'color': '#897044', 'pattern': 'SOLID'},
                
                # Residential with hatched pattern
                {'zone': 'R1 - Village Planning Zone', 'pattern': 'HATCHED',
                 'pattern_color': '#000000', 'secondary_fill': '#FFFFFF'},
                {'zone': 'R3 - Medium to High Density Zone', 'color': '#F5CA7A', 'pattern': 'SOLID'},
                {'zone': 'R4 - High Density Zone', 'color': '#E69800', 'pattern': 'SOLID'},
                {'zone': 'RAA', 'color': '#FFAA00', 'pattern': 'SOLID'},
                {'zone': 'Residential Vacant', 'color': '#FFD37F', 'pattern': 'SOLID'},
                
                # Special zones
                {'zone': 'S2 - Education Zone', 'color': '#FF7F7F', 'pattern': 'SOLID'},
                {'zone': 'S3 - Special Zone', 'color': '#D7B09E', 'pattern': 'SOLID'},
                {'zone': 'SC1a - Mixed Use', 'color': '#0070FF', 'pattern': 'SOLID'},
                {'zone': 'SC1b - Mixed Use', 'color': '#73B2FF', 'pattern': 'SOLID'},
                {'zone': 'SP1 - Passive Zone', 'color': '#267300', 'pattern': 'SOLID'},
                {'zone': 'SP2 - Active Zone', 'color': '#38A800', 'pattern': 'SOLID'},
                {'zone': 'SP3 - Protected Zone', 'color': '#00C5FF', 'pattern': 'SOLID'},
                {'zone': 'SR2 - Low Density Housing', 'color': '#FFFFBE', 'pattern': 'SOLID'},
                {'zone': 'SR4 - High Density Private', 'color': '#FFAA00', 'pattern': 'SOLID'},
                {'zone': 'SS1 - Government Zone', 'color': '#E60000', 'pattern': 'SOLID'},
                {'zone': 'SS2a - Education Zone', 'color': '#FF7F7F', 'pattern': 'SOLID'},
                {'zone': 'SS2b - Cultural Zone', 'color': '#C500FF', 'pattern': 'SOLID'},
                {'zone': 'SS2c - Health Zone', 'color': '#D3FFBE', 'pattern': 'SOLID'},
                {'zone': 'SS3 - Special Zone', 'color': '#A83800', 'pattern': 'SOLID'},
                {'zone': 'SU1 - Reserve Zone', 'color': '#E1E1E1', 'pattern': 'SOLID'},
                {'zone': 'SU2 - Road Network', 'color': '#FFFFFF', 
                 'pattern': 'SOLID', 'outline': '#000000'},
                {'zone': 'U1 - Reserve Zone', 'color': '#CCCCCC', 'pattern': 'SOLID'},
                {'zone': 'U2 - Road Reserve Zone', 'color': '#000000', 'pattern': 'SOLID'},
            ]
            
            for style_data in amaravati_styles:
                category_code = self._determine_category(style_data['zone'])
                category, _ = LayerCategory.objects.get_or_create(
                    code=category_code,
                    defaults={'name': category_code.replace('_', ' ').title()}
                )
                
                style_obj, _ = CityLayerStyle.objects.update_or_create(
                    city=city,
                    category=category,
                    defaults={
                        'fill_color': style_data.get('color', style_data.get('secondary_fill', '#FFFFFF')),
                        'fill_pattern': style_data.get('pattern', 'SOLID'),
                        'pattern_color': style_data.get('pattern_color', ''),
                        'secondary_fill_color': style_data.get('secondary_fill', ''),
                        'stroke_color': style_data.get('outline', '#333333'),
                        'stroke_width': 1 if style_data.get('outline') else 0,
                        'opacity': 0.8
                    }
                )
                
                CityZoneMapping.objects.update_or_create(
                    city=city,
                    zone_name=style_data['zone'],
                    defaults={
                        'category': category,
                        'style': style_obj,
                        'is_active': True
                    }
                )
            
            self.stdout.write(f"✓ Imported Amaravati styles with patterns")
            
        except City.DoesNotExist:
            self.stdout.write(self.style.WARNING('Amaravati city not found'))
    
    @transaction.atomic
    def import_bengaluru_styles(self):
        """Import Bengaluru master plan styles - all solid colors"""
        try:
            city = City.objects.get(slug='bengaluru')
            
            bengaluru_styles = [
                {'zone': 'Residential (Mixed)', 'color': '#FFC400', 'category': 'RESIDENTIAL'},
                {'zone': 'Residential (Main)', 'color': '#FFEBAF', 'category': 'RESIDENTIAL'},
                {'zone': 'Commercial (Central)', 'color': '#004DA8', 'category': 'COMMERCIAL'},
                {'zone': 'Commercial (Business)', 'color': '#73B2FF', 'category': 'COMMERCIAL'},
                {'zone': 'Industrial', 'color': '#AA66B2', 'category': 'INDUSTRIAL'},
                {'zone': 'High Tech', 'color': '#C29ED7', 'category': 'HIGH_TECH'},
                {'zone': 'Public/ Semi Public', 'color': '#E60000', 'category': 'PUBLIC'},
                {'zone': 'Defense', 'color': '#E0B8FC', 'category': 'DEFENSE'},
                {'zone': 'State Forest/Valley (Protected Land)', 'color': '#70A800', 'category': 'PROTECTED'},
                {'zone': 'Parks and Green Spaces, Sport/Playgrounds, Cemeteries/Burial Grounds', 
                 'color': '#98E600', 'category': 'PARKS_GREEN'},
                {'zone': 'Lake/Tank (Protected Land)', 'color': '#BEE8FF', 'category': 'WATER_BODIES'},
                {'zone': 'Road/Rail/Airport Transport', 'color': '#828282', 'category': 'TRANSPORT'},
                {'zone': 'Power/Water/Garbage Facility/Treatment Plant', 
                 'color': '#D79E9E', 'category': 'UTILITIES'},
                {'zone': 'Agricultural Land', 'color': '#9DC1CB', 'category': 'AGRICULTURAL'},
                {'zone': 'Unclassified Use', 'color': '#E1E1E1', 'category': 'UNCLASSIFIED'},
                {'zone': 'Drains', 'color': '#267300', 'category': 'WATER_BODIES'},
            ]
            
            for style_data in bengaluru_styles:
                category, _ = LayerCategory.objects.get_or_create(
                    code=style_data['category'],
                    defaults={'name': style_data['category'].replace('_', ' ').title()}
                )
                
                style_obj, _ = CityLayerStyle.objects.update_or_create(
                    city=city,
                    category=category,
                    defaults={
                        'fill_color': style_data['color'],
                        'fill_pattern': 'SOLID',
                        'stroke_width': 0,  # No borders
                        'opacity': 0.8
                    }
                )
                
                CityZoneMapping.objects.update_or_create(
                    city=city,
                    zone_name=style_data['zone'],
                    defaults={
                        'category': category,
                        'style': style_obj,
                        'is_active': True
                    }
                )
            
            self.stdout.write(f"✓ Imported Bengaluru master plan styles")
            
        except City.DoesNotExist:
            self.stdout.write(self.style.WARNING('Bengaluru city not found'))
    
    def _determine_category(self, zone_name: str) -> str:
        """Determine category code based on zone name"""
        zone_lower = zone_name.lower()
        
        if any(word in zone_lower for word in ['residential', 'housing', 'density']):
            return 'RESIDENTIAL'
        elif any(word in zone_lower for word in ['commercial', 'business', 'cbd', 'centre']):
            return 'COMMERCIAL'
        elif any(word in zone_lower for word in ['industrial', 'logistics']):
            return 'INDUSTRIAL'
        elif any(word in zone_lower for word in ['mixed use']):
            return 'MIXED_USE'
        elif any(word in zone_lower for word in ['government', 'public', 'semi']):
            return 'GOVERNMENT'
        elif any(word in zone_lower for word in ['education', 'school']):
            return 'EDUCATION'
        elif any(word in zone_lower for word in ['health', 'hospital', 'medical']):
            return 'HEALTH'
        elif any(word in zone_lower for word in ['park', 'green', 'recreational', 'playground']):
            return 'PARKS_GREEN'
        elif any(word in zone_lower for word in ['water', 'lake', 'river', 'sea', 'tank']):
            return 'WATER_BODIES'
        elif any(word in zone_lower for word in ['transport', 'road', 'railway', 'airport']):
            return 'TRANSPORT'
        elif any(word in zone_lower for word in ['utilities', 'power', 'garbage', 'treatment']):
            return 'UTILITIES'
        elif any(word in zone_lower for word in ['agricultural', 'farming']):
            return 'AGRICULTURAL'
        elif any(word in zone_lower for word in ['forest', 'protected', 'sanctuary', 'wildlife']):
            return 'PROTECTED'
        elif any(word in zone_lower for word in ['burial', 'cemetery', 'crematorium']):
            return 'BURIAL'
        elif any(word in zone_lower for word in ['religious', 'temple', 'church', 'mosque']):
            return 'RELIGIOUS'
        elif any(word in zone_lower for word in ['cultural', 'heritage']):
            return 'CULTURAL'
        elif any(word in zone_lower for word in ['defense', 'military']):
            return 'DEFENSE'
        else:
            return 'UNCLASSIFIED'