# maps/management/commands/setup_hierarchy_from_excel.py
# FIXED VERSION - Handles Excel parsing correctly with proper data

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.core.management import call_command
import pandas as pd
import json
import os
from pathlib import Path
from typing import Dict, List, Any
import logging
from django.apps import apps

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Setup hierarchy from Excel with CORRECTED parsing'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--excel-file',
            type=str,
            default='Untitled spreadsheet.xlsx',
            help='Path to Excel file'
        )
        
        parser.add_argument(
            '--data-path',
            type=str,
            default='data/',
            help='Base path to GeoJSON data files'
        )
        
        parser.add_argument(
            '--skip-import',
            action='store_true',
            help='Only setup hierarchy, skip data import'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without creating it'
        )
    
    def handle(self, *args, **options):
        """Main handler with fixes"""
        
        self.stdout.write("=" * 60)
        self.stdout.write("🚀 FIXED HIERARCHY SETUP FROM EXCEL")
        self.stdout.write("=" * 60)
        
        try:
            # Step 1: Check database tables exist
            self.check_database_setup()
            
            # Step 2: Read and parse Excel CORRECTLY
            self.stdout.write("\n📋 STEP 1: READING EXCEL DATA (FIXED)")
            hierarchy = self.read_excel_correctly(options['excel_file'])
            
            # Step 3: Create database structure
            if not options['dry_run']:
                self.stdout.write("\n🏗️ STEP 2: CREATING DATABASE STRUCTURE")
                self.create_hierarchy_structure(hierarchy)
            else:
                self.stdout.write("\n🔍 DRY RUN - Would create:")
                self.show_what_would_be_created(hierarchy)
            
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write("✅ HIERARCHY SETUP COMPLETE")
            self.stdout.write("=" * 60)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Pipeline failed: {str(e)}"))
            raise CommandError(str(e))
    
    def check_database_setup(self):
        """Check if required models/tables exist"""
        try:
            # Import models to check if they exist
            from maps.models import State, City, LayerCategory, DataLayer
            
            # Try a simple query to check if tables exist
            State.objects.first()
            self.stdout.write("✅ Database tables exist")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR("❌ Database tables don't exist"))
            self.stdout.write("Run migrations first: python manage.py migrate")
            raise CommandError(f"Database not ready: {str(e)}")
    
    def read_excel_correctly(self, excel_file: str) -> Dict:
        """FIXED: Read Excel file correctly, skip headers, fix state mapping"""
        
        try:
            # Read Excel with proper headers
            df = pd.read_excel(excel_file, header=0)  # Use first row as headers
            
            self.stdout.write(f"📊 Excel shape: {df.shape}")
            self.stdout.write(f"📊 Columns: {list(df.columns)}")
            
            # CORRECT state code mapping
            state_mapping = {
                'Telangana': 'TS',
                'Karnataka': 'KA', 
                'Delhi': 'DL',
                'Haryana': 'HR',
                'Uttar Pradesh': 'UP',
                'Rajasthan': 'RJ',  # FIXED: was RA
                'Madhya Pradesh': 'MP',  # FIXED: was MA
                'Gujarat': 'GJ',  # FIXED: was GU
                'Maharashtra': 'MH',
                'Andhra Pradesh': 'AP',
                'Odisha': 'OR',  # FIXED: was OD
                'Punjab': 'PB',  # FIXED: was PU
                'Tamil Nadu': 'TN',  # FIXED: was TA
                'Kerala': 'KL'  # FIXED: was KE + spelling corrected
            }
            
            # CORRECT city to state mapping for Delhi NCR
            city_state_mapping = {
                'Delhi': 'DL',
                # Haryana cities
                'Gurgaon': 'HR', 'Faridabad': 'HR', 'Sonipat': 'HR', 'Kharkhauda': 'HR',
                'Bahadurgarh': 'HR', 'Sampla': 'HR', 'Badli': 'HR', 'Badsa': 'HR', 
                'Farukhnagar': 'HR', 'Pataudi': 'HR', 'Dharuhera': 'HR', 'Gwal Pahari': 'HR',
                'Sohna': 'HR', 'Pirthala': 'HR', 'Palwal': 'HR',
                # Uttar Pradesh cities  
                'Noida': 'UP', 'YEIDA': 'UP', 'Gr. Noida': 'UP', 'Ghaziabad': 'UP', 
                'Loni': 'UP', 'Bhagpat - Baraut - Khekra': 'UP', 'Modinagar': 'UP',
                # Rajasthan cities
                'Bhiwadi': 'RJ'
            }
            
            hierarchy = {
                'states': {},
                'cities': {},
                'layers': []
            }
            
            current_state = None
            current_city = None
            
            # Process each row (headers already handled)
            in_delhi_ncr_section = False
            current_state_for_layer = None
            
            for idx, row in df.iterrows():
                # Get values from proper column names
                state_val = str(row['State ']).strip() if pd.notna(row['State ']) else ''
                city_val = str(row['Urban Area ']).strip() if pd.notna(row['Urban Area ']) else ''
                layer_val = str(row['Layer name ']).strip() if pd.notna(row['Layer name ']) else ''
                
                # Handle state
                if state_val and state_val != 'nan':
                    if state_val == 'Delhi NCR':
                        # Mark that we're entering Delhi NCR section
                        in_delhi_ncr_section = True
                        current_state = None  # Reset state for Delhi NCR cities
                        self.stdout.write("  🔍 Entering Delhi NCR section - cities will be mapped to actual states")
                    else:
                        # Normal state
                        in_delhi_ncr_section = False
                        state_name = state_val
                        state_code = state_mapping.get(state_name, state_name[:2].upper())
                        
                        if state_code not in hierarchy['states']:
                            hierarchy['states'][state_code] = {
                                'name': state_name,
                                'code': state_code,
                                'cities': []
                            }
                        current_state = state_code
                        self.stdout.write(f"  🔍 Set current state: {state_name} ({state_code})")
                
                # Handle city
                if city_val and city_val != 'nan':
                    city_name = city_val
                    
                    # Special handling for Delhi NCR cities
                    if in_delhi_ncr_section or city_name in city_state_mapping:
                        # Map Delhi NCR cities to their actual states
                        actual_state_code = city_state_mapping.get(city_name, 'DL')  # Default to Delhi if not found
                        
                        # Debug output
                        self.stdout.write(f"    🔍 Mapping Delhi NCR city: {city_name} → {actual_state_code}")
                        
                        actual_state_name = [name for name, code in state_mapping.items() if code == actual_state_code][0]
                        
                        if actual_state_code not in hierarchy['states']:
                            hierarchy['states'][actual_state_code] = {
                                'name': actual_state_name,
                                'code': actual_state_code,
                                'cities': []
                            }
                        
                        # Set current_state to the actual state for this city
                        city_state = actual_state_code
                    else:
                        # Normal city, use current_state
                        city_state = current_state
                    
                    # Normalize city name
                    city_slug = self.normalize_city_name(city_name)
                    
                    if city_slug not in hierarchy['cities']:
                        hierarchy['cities'][city_slug] = {
                            'name': self.clean_city_name(city_name),
                            'state': city_state,
                            'layers': []
                        }
                        
                        if city_state and city_state in hierarchy['states']:
                            if city_slug not in hierarchy['states'][city_state]['cities']:
                                hierarchy['states'][city_state]['cities'].append(city_slug)
                    
                    current_city = city_slug
                    
                    # For layers, use the city's assigned state  
                    current_state_for_layer = city_state
                
                # Handle layer
                if layer_val and layer_val != 'nan' and current_city:
                    # Make sure we have a state for the layer
                    if current_state_for_layer is None:
                        # Use the city's state from hierarchy
                        if current_city in hierarchy['cities']:
                            current_state_for_layer = hierarchy['cities'][current_city]['state']
                    
                    if current_state_for_layer:
                        layer_name = layer_val
                        
                        layer_info = {
                            'name': layer_name,
                            'category': self._determine_category(layer_name),
                            'city': current_city,
                            'state': current_state_for_layer,
                            'status': str(row['Status ']).strip() if pd.notna(row['Status ']) else '',
                            'is_live': str(row['Live status ']).strip().lower() == 'live' if pd.notna(row['Live status ']) else False,
                            'data_type': str(row['Data type ']).strip() if pd.notna(row['Data type ']) else 'GeoJson',
                            'access': str(row['Access ']).strip() if pd.notna(row['Access ']) else 'Free'
                        }
                        
                        hierarchy['layers'].append(layer_info)
                        hierarchy['cities'][current_city]['layers'].append(layer_info)
            
            # Summary
            self.stdout.write(f"✅ CORRECTLY Parsed: {len(hierarchy['states'])} states, "
                            f"{len(hierarchy['cities'])} cities, "
                            f"{len(hierarchy['layers'])} layers")
            
            # Show what we found
            for state_code, state_info in hierarchy['states'].items():
                self.stdout.write(f"  State: {state_info['name']} ({state_code})")
                for city_slug in state_info['cities']:
                    city_info = hierarchy['cities'][city_slug]
                    self.stdout.write(f"    → {city_info['name']}: {len(city_info['layers'])} layers")
            
            return hierarchy
            
        except Exception as e:
            raise CommandError(f"Error reading Excel: {str(e)}")
    
    def normalize_city_name(self, city_name: str) -> str:
        """Normalize city name to slug"""
        # Handle special cases
        if 'BMRDA' in city_name:
            return 'bmrda'
        elif city_name.lower() == 'bangalore':
            return 'bengaluru'
        elif '(HR)' in city_name or '(UP)' in city_name or '(RJ)' in city_name:
            # Remove state suffix and normalize
            clean_name = city_name.split('(')[0].strip()
            return clean_name.lower().replace(' ', '_').replace('-', '_')
        else:
            return city_name.lower().replace(' ', '_').replace('-', '_')
    
    def clean_city_name(self, city_name: str) -> str:
        """Clean city name for display"""
        if 'BMRDA' in city_name:
            return 'BMRDA'
        elif '(HR)' in city_name or '(UP)' in city_name or '(RJ)' in city_name:
            # Remove state suffix 
            return city_name.split('(')[0].strip()
        else:
            return city_name
    
    def _determine_category(self, layer_name: str) -> str:
        """Determine category from layer name"""
        layer_lower = layer_name.lower()
        
        if 'master plan' in layer_lower:
            return 'MIXED_USE'
        elif any(word in layer_lower for word in ['rrr', 'road', 'highway', 'metro']):
            return 'TRANSPORT'
        elif any(word in layer_lower for word in ['survey', 'cadastral']):
            return 'BOUNDARIES'
        elif any(word in layer_lower for word in ['ward', 'constituency']):
            return 'BOUNDARIES'
        elif any(word in layer_lower for word in ['village', 'town']):
            return 'BOUNDARIES'
        elif any(word in layer_lower for word in ['lakes', 'water']):
            return 'WATER_BODIES'
        else:
            return 'UNCLASSIFIED'
    
    def show_what_would_be_created(self, hierarchy: Dict):
        """Show what would be created in dry run"""
        
        self.stdout.write("🔍 WOULD CREATE:")
        
        for state_code, state_info in hierarchy['states'].items():
            self.stdout.write(f"  📍 State: {state_info['name']} ({state_code})")
            
        for city_slug, city_info in hierarchy['cities'].items():
            self.stdout.write(f"  🏙️ City: {city_info['name']} → {city_info['state']}")
        
        categories = set(layer['category'] for layer in hierarchy['layers'])
        for category in categories:
            self.stdout.write(f"  📂 Category: {category}")
        
        self.stdout.write(f"  📄 Layers: {len(hierarchy['layers'])} total")
    
    @transaction.atomic
    def create_hierarchy_structure(self, hierarchy: Dict):
        """Create database structure"""
        
        from maps.models import State, City, LayerCategory, DataLayer
        
        # Create states
        for state_code, state_info in hierarchy['states'].items():
            state, created = State.objects.update_or_create(
                code=state_code,
                defaults={
                    'name': state_info['name'],
                    'slug': state_info['name'].lower().replace(' ', '_'),
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f"  ✅ Created state: {state.name}")
        
        # Create cities with proper coordinates
        city_coordinates = {
            'hyderabad': (17.385044, 78.486671),
            'warangal': (17.9784, 79.6000),
            'bengaluru': (12.9716, 77.5946),
            'bangalore': (12.9716, 77.5946),
            'bmrda': (12.8406, 77.6602),
            'delhi': (28.6139, 77.2090),
            'gurgaon': (28.4595, 77.0266),
            'noida': (28.5355, 77.3910),
            'yeida': (28.4844, 77.5662),
            'faridabad': (28.4089, 77.3178),
            'gr_noida': (28.4601, 77.5122),
            'ghaziabad': (28.6692, 77.4538),
            'sonipat': (28.9931, 77.0151),
            'kharkhauda': (28.8818, 76.9066),
            'bahadurgarh': (28.6928, 76.9378),
            'sampla': (28.7584, 76.7778),
            'badli': (28.7250, 77.0833),
            'badsa': (28.0167, 76.8833),
            'farukhnagar': (28.4333, 76.8167),
            'pataudi': (28.3256, 76.7878),
            'dharuhera': (28.2042, 76.7953),
            'gwal_pahari': (28.4457, 77.1367),
            'sohna': (28.2750, 77.0667),
            'pirthala': (28.8833, 76.6167),
            'palwal': (28.1441, 77.3263),
            'loni': (28.7485, 77.2849),
            'bhagpat_baraut_khekra': (28.9491, 77.2167),
            'modinagar': (28.9167, 77.5833),
            'bhiwadi': (28.2099, 76.8600),
            'jaipur': (26.9124, 75.7873),
            'jodhpur': (26.2389, 73.0243),
            'ajmer': (26.4499, 74.6399),
            'udaipur': (24.5854, 73.7125),
            'bhopal': (23.2599, 77.4126),
            'indore': (22.7196, 75.8577),
            'pithampur': (22.6022, 75.6854),
            'ahmedabad_gandhinagar': (23.0225, 72.5714),
            'mumbai': (19.0760, 72.8777),
            'amaravati': (16.5062, 80.6480),
            'tirupati': (13.6288, 79.4192),
            'vijaywada_guntur_tenali_mangalagiri': (16.5062, 80.6480),
            'kakinada': (16.9891, 82.2475),
            'vizag': (17.6868, 83.2185),
            'bhubaneshwar': (20.2961, 85.8245),
            'chandigarh': (30.7333, 76.7794),
            'chennai': (13.0827, 80.2707),
            'hosur': (12.7409, 77.8253),
            'coimbatore': (11.0168, 76.9558),
            'kochi': (9.9312, 76.2673)
        }
        
        for city_slug, city_info in hierarchy['cities'].items():
            if city_info['state']:
                try:
                    state = State.objects.get(code=city_info['state'])
                except State.DoesNotExist:
                    self.stdout.write(f"  ⚠️ State {city_info['state']} not found for city {city_info['name']}")
                    continue
            else:
                state = None
            
            # Get coordinates
            coords = city_coordinates.get(city_slug, (20.5937, 78.9629))  # Default to India center
            
            city, created = City.objects.update_or_create(
                slug=city_slug,
                defaults={
                    'name': city_info['name'],
                    'state': state.name if state else '',
                    'state_ref': state,
                    'center_lat': coords[0],
                    'center_lng': coords[1],
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f"  ✅ Created city: {city.name} in {state.name if state else 'Unknown'}")
        
        # Create categories
        categories = set(layer['category'] for layer in hierarchy['layers'])
        for category_code in categories:
            category, created = LayerCategory.objects.get_or_create(
                code=category_code,
                defaults={
                    'name': category_code.replace('_', ' ').title(),
                    'description': f'{category_code.replace("_", " ").title()} layers'
                }
            )
            if created:
                self.stdout.write(f"  ✅ Created category: {category.name}")
        
        # Create layers (basic structure)
        for layer_info in hierarchy['layers']:
            try:
                city = City.objects.get(slug=layer_info['city'])
                category = LayerCategory.objects.get(code=layer_info['category'])
                
                layer_slug = f"{layer_info['city']}_{layer_info['name'].lower().replace(' ', '_').replace('-', '_')}"
                
                layer, created = DataLayer.objects.update_or_create(
                    slug=layer_slug,
                    defaults={
                        'name': layer_info['name'],
                        'city': city,
                        'category': category,
                        'description': f"{layer_info['name']} layer for {city.name}"
                        # 'is_active': True,
                        # 'is_premium': layer_info.get('access', '').lower() == 'premium'
                    }
                )
                if created:
                    self.stdout.write(f"  ✅ Created layer: {layer.name} in {city.name}")
            except Exception as e:
                self.stdout.write(f"  ⚠️ Could not create layer {layer_info['name']}: {e}")