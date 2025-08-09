# maps/management/commands/setup_hierarchy_from_excel.py
"""
Setup complete State → City → Layer hierarchy from Excel data
Command: python manage.py setup_hierarchy_from_excel --excel-file "path/to/excel"
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from maps.models import State, City, LayerCategory, DataLayer
import pandas as pd
import openpyxl
from pathlib import Path

class Command(BaseCommand):
    help = 'Setup complete hierarchy (States → Cities → Layers) from Excel data'
    
    def add_arguments(self, parser):
        parser.add_argument('--excel-file', help='Path to Excel file with hierarchy data')
        parser.add_argument('--use-default', action='store_true', help='Use uploaded Excel file from project')
        parser.add_argument('--force', action='store_true', help='Force recreation of existing data')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be created without creating')
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🏗️  SETTING UP HIERARCHY FROM EXCEL"))
        
        # Determine Excel file path
        if options['use_default']:
            excel_file = 'Untitled spreadsheet.xlsx'  # Use uploaded file
        elif options['excel_file']:
            excel_file = options['excel_file']
        else:
            self.stdout.write(self.style.ERROR("❌ Specify --excel-file or --use-default"))
            return
        
        try:
            # Read Excel data
            hierarchy_data = self._read_excel_data(excel_file)
            
            if options['dry_run']:
                self._show_dry_run(hierarchy_data)
                return
            
            # Setup hierarchy
            with transaction.atomic():
                results = self._setup_complete_hierarchy(hierarchy_data, options['force'])
            
            self._display_setup_results(results)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Setup failed: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())
    
    def _read_excel_data(self, excel_file):
        """Read and parse Excel data into hierarchy structure"""
        self.stdout.write(f"📊 Reading Excel data from: {excel_file}")
        
        # Try to read with pandas first, fallback to openpyxl
        try:
            df = pd.read_excel(excel_file, header=None)
            
            # Parse the data structure
            hierarchy = {}
            current_state = None
            current_city = None
            
            for index, row in df.iterrows():
                state = row[0] if pd.notna(row[0]) else current_state
                city = row[1] if pd.notna(row[1]) else current_city
                layer_name = row[2] if pd.notna(row[2]) else None
                description = row[3] if pd.notna(row[3]) else None
                status = row[4] if pd.notna(row[4]) else None
                docs_url = row[5] if pd.notna(row[5]) else None
                live_status = row[6] if pd.notna(row[6]) else None
                data_format = row[7] if pd.notna(row[7]) else 'GeoJson'
                pricing = row[8] if pd.notna(row[8]) else 'Free'
                
                # Skip if no layer name
                if not layer_name:
                    continue
                
                # Update current state/city
                if state:
                    current_state = state.strip()
                if city:
                    current_city = city.strip()
                
                # Initialize hierarchy structure
                if current_state not in hierarchy:
                    hierarchy[current_state] = {}
                if current_city not in hierarchy[current_state]:
                    hierarchy[current_state][current_city] = []
                
                # Add layer data
                hierarchy[current_state][current_city].append({
                    'name': layer_name.strip(),
                    'slug': slugify(layer_name.strip()),
                    'description': description.strip() if description else '',
                    'status': status.strip() if status else 'Unknown',
                    'docs_url': docs_url.strip() if docs_url else '',
                    'live_status': live_status.strip() if live_status else '',
                    'format': data_format.strip() if data_format else 'GeoJson',
                    'pricing': pricing.strip() if pricing else 'Free'
                })
            
            return hierarchy
            
        except Exception as e:
            self.stdout.write(f"❌ Error reading Excel: {e}")
            raise
    
    def _show_dry_run(self, hierarchy_data):
        """Show what would be created without actually creating"""
        self.stdout.write("\n🔍 DRY RUN - What would be created:")
        
        total_states = len(hierarchy_data)
        total_cities = sum(len(cities) for cities in hierarchy_data.values())
        total_layers = sum(
            len(layers) 
            for cities in hierarchy_data.values() 
            for layers in cities.values()
        )
        
        self.stdout.write(f"\n📊 Summary:")
        self.stdout.write(f"   States: {total_states}")
        self.stdout.write(f"   Cities: {total_cities}")
        self.stdout.write(f"   Layers: {total_layers}")
        
        self.stdout.write(f"\n📋 Detailed breakdown:")
        for state_name, cities in hierarchy_data.items():
            self.stdout.write(f"\n🏛️  State: {state_name} ({slugify(state_name)})")
            for city_name, layers in cities.items():
                self.stdout.write(f"   🏙️  City: {city_name} ({slugify(city_name)}) - {len(layers)} layers")
                for layer in layers[:3]:  # Show first 3 layers
                    self.stdout.write(f"      📄 {layer['name']} ({layer['format']}, {layer['status']})")
                if len(layers) > 3:
                    self.stdout.write(f"      ... and {len(layers) - 3} more layers")
    
    def _setup_complete_hierarchy(self, hierarchy_data, force=False):
        """Setup the complete hierarchy in database"""
        results = {
            'states_created': 0,
            'cities_created': 0,
            'layers_created': 0,
            'states_updated': 0,
            'cities_updated': 0,
            'errors': []
        }
        
        for state_name, cities in hierarchy_data.items():
            try:
                # Create/update state
                state_slug = slugify(state_name)
                state_code = self._generate_state_code(state_name)
                
                state, state_created = State.objects.get_or_create(
                    slug=state_slug,
                    defaults={
                        'name': state_name,
                        'code': state_code,
                        'is_active': True
                    }
                )
                
                if state_created:
                    results['states_created'] += 1
                    self.stdout.write(f"🏛️  Created state: {state_name}")
                else:
                    if force:
                        state.name = state_name
                        state.code = state_code
                        state.save()
                        results['states_updated'] += 1
                    self.stdout.write(f"ℹ️  State exists: {state_name}")
                
                # Create/update cities in this state
                for city_name, layers in cities.items():
                    try:
                        city_slug = slugify(city_name)
                        
                        city, city_created = City.objects.get_or_create(
                            slug=city_slug,
                            defaults={
                                'name': city_name,
                                'state': state_name,  # Legacy field
                                'state_ref': state,   # New FK field
                                'center_lat': 0.0,    # Will be updated later
                                'center_lng': 0.0,    # Will be updated later
                                'is_active': True
                            }
                        )
                        
                        if city_created:
                            results['cities_created'] += 1
                            self.stdout.write(f"   🏙️  Created city: {city_name}")
                        else:
                            if force:
                                city.state_ref = state
                                city.save()
                                results['cities_updated'] += 1
                            self.stdout.write(f"   ℹ️  City exists: {city_name}")
                        
                        # Create layer definitions (not importing data yet)
                        for layer_data in layers:
                            try:
                                layer_slug = layer_data['slug']
                                category = self._get_or_create_category(layer_data['name'])
                                
                                layer, layer_created = DataLayer.objects.get_or_create(
                                    city=city,
                                    slug=layer_slug,
                                    defaults={
                                        'name': layer_data['name'],
                                        'category': category,
                                        'description': layer_data['description'],
                                        'file_format': self._normalize_format(layer_data['format']),
                                        'categorization_method': 'MANUAL',
                                        'is_processed': False
                                    }
                                )
                                
                                if layer_created:
                                    results['layers_created'] += 1
                                    self.stdout.write(f"      📄 Created layer: {layer_data['name']}")
                                else:
                                    self.stdout.write(f"      ℹ️  Layer exists: {layer_data['name']}")
                                    
                            except Exception as e:
                                error_msg = f"Error creating layer {layer_data['name']}: {e}"
                                results['errors'].append(error_msg)
                                self.stdout.write(f"      ❌ {error_msg}")
                                
                    except Exception as e:
                        error_msg = f"Error creating city {city_name}: {e}"
                        results['errors'].append(error_msg)
                        self.stdout.write(f"   ❌ {error_msg}")
                        
            except Exception as e:
                error_msg = f"Error creating state {state_name}: {e}"
                results['errors'].append(error_msg)
                self.stdout.write(f"❌ {error_msg}")
        
        return results
    
    def _generate_state_code(self, state_name):
        """Generate 2-letter state code"""
        code_mappings = {
            'Telangana': 'TS',
            'Andhra Pradesh': 'AP', 
            'Karnataka': 'KA',
            'Tamil Nadu': 'TN',
            'Kerala': 'KL',
            'Maharashtra': 'MH',
            'Gujarat': 'GJ',
            'Rajasthan': 'RJ',
            'Madhya Pradesh': 'MP',
            'Delhi NCR': 'DL',
            'Punjab': 'PB',
            'Odisha': 'OD'
        }
        
        return code_mappings.get(state_name, state_name[:2].upper())
    
    def _normalize_format(self, format_str):
        """Normalize file format from Excel to model choices"""
        if not format_str:
            return 'GEOJSON'
        
        format_lower = format_str.lower().strip()
        
        format_mappings = {
            'geojson': 'GEOJSON',
            'json': 'JSON',
            'geotiff': 'SHP',  # Map to closest available
            'api': 'JSON',
            'shapefile': 'SHP'
        }
        
        return format_mappings.get(format_lower, 'GEOJSON')
    
    def _get_or_create_category(self, layer_name):
        """Get or create appropriate category for layer"""
        layer_lower = layer_name.lower()
        
        # Category detection logic (same as in import_layer_data)
        category_mappings = {
            'master plan': 'MIXED_USE',
            'road': 'TRANSPORT', 
            'roads': 'TRANSPORT',
            'lake': 'WATER_BODIES',
            'lakes': 'WATER_BODIES',
            'parks': 'PARKS_GREEN',
            'residential': 'RESIDENTIAL',
            'commercial': 'COMMERCIAL',
            'industrial': 'INDUSTRIAL',
            'railway': 'TRANSPORT',
            'utilities': 'UTILITIES',
            'government': 'GOVERNMENT',
            'public': 'PUBLIC',
            'agriculture': 'AGRICULTURAL',
            'forest': 'PROTECTED'
        }
        
        for keyword, category_code in category_mappings.items():
            if keyword in layer_lower:
                category, created = LayerCategory.objects.get_or_create(
                    code=category_code,
                    defaults={
                        'name': category_code.replace('_', ' ').title(),
                        'description': f'{category_code.replace("_", " ").title()} related layers'
                    }
                )
                return category
        
        # Default category
        category, created = LayerCategory.objects.get_or_create(
            code='UNCLASSIFIED',
            defaults={
                'name': 'Unclassified',
                'description': 'Unclassified layers'
            }
        )
        return category
    
    def _display_setup_results(self, results):
        """Display setup results summary"""
        self.stdout.write(f"\n📊 HIERARCHY SETUP RESULTS:")
        self.stdout.write(f"   States created: {results['states_created']}")
        self.stdout.write(f"   States updated: {results['states_updated']}")
        self.stdout.write(f"   Cities created: {results['cities_created']}")
        self.stdout.write(f"   Cities updated: {results['cities_updated']}")
        self.stdout.write(f"   Layers created: {results['layers_created']}")
        
        if results['errors']:
            self.stdout.write(f"\n❌ Errors ({len(results['errors'])}):")
            for error in results['errors'][:5]:  # Show first 5 errors
                self.stdout.write(f"   - {error}")
            if len(results['errors']) > 5:
                self.stdout.write(f"   ... and {len(results['errors']) - 5} more errors")
        
        self.stdout.write(f"\n🎯 Next Steps:")
        self.stdout.write(f"1. Import data: python manage.py import_layer_data --city CITY_SLUG --layer LAYER_NAME --data-dir PATH")
        self.stdout.write(f"2. Generate tiles: python manage.py generate_direct_s3_tiles --city CITY_SLUG")
        self.stdout.write(f"3. View hierarchy: python manage.py show_hierarchy")