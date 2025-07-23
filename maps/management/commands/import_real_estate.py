# Create: maps/management/commands/import_real_estate.py

import json
import re
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from maps.models import Plot, Land

class Command(BaseCommand):
    help = 'Import plots and lands data from GeoJSON files'

    def add_arguments(self, parser):
        parser.add_argument('--plots', type=str, help='Path to plots-data.geojson')
        parser.add_argument('--lands', type=str, help='Path to lands-data.geojson')
        parser.add_argument('--clear', action='store_true', help='Clear existing data first')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🏡 Starting Real Estate Data Import'))
        
        if options['clear']:
            self.stdout.write('🗑️  Clearing existing data...')
            Plot.objects.all().delete()
            Land.objects.all().delete()
            self.stdout.write('✅ Existing data cleared')
        
        if options['plots']:
            self.import_plots(options['plots'])
        
        if options['lands']:
            self.import_lands(options['lands'])

    def import_plots(self, file_path):
        """Import plots data"""
        self.stdout.write(f'\n📍 Importing plots from: {file_path}')
        
        try:
            with open(file_path, 'r') as f:
                geojson_data = json.load(f)
            
            imported_count = 0
            
            for feature in geojson_data['features']:
                props = feature['properties']
                coords = feature['geometry']['coordinates']
                
                # Extract area and price from marker_title
                area_sq_yards, price_per_sq_yard = self.parse_plot_pricing(props['marker_title'])
                
                plot, created = Plot.objects.update_or_create(
                    plot_id=props['plot_id'],
                    defaults={
                        'location': Point(coords[0], coords[1]),
                        'area_sq_yards': area_sq_yards,
                        'price_per_sq_yard': price_per_sq_yard,
                        'total_price': area_sq_yards * price_per_sq_yard if area_sq_yards and price_per_sq_yard else None,
                        'marker_title': props['marker_title'],
                        'marker_id': props['marker_id'],
                    }
                )
                
                if created:
                    imported_count += 1
                    self.stdout.write(f'  ✅ Plot {plot.plot_id}: {plot.marker_title}')
            
            self.stdout.write(self.style.SUCCESS(f'📊 Imported {imported_count} plots'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error importing plots: {e}'))

    def import_lands(self, file_path):
        """Import lands data"""
        self.stdout.write(f'\n🌾 Importing lands from: {file_path}')
        
        try:
            with open(file_path, 'r') as f:
                geojson_data = json.load(f)
            
            imported_count = 0
            
            for feature in geojson_data['features']:
                props = feature['properties']
                coords = feature['geometry']['coordinates']
                
                # Extract area and price text from marker_title
                area_text, price_text = self.parse_land_pricing(props['marker_title'])
                
                land, created = Land.objects.update_or_create(
                    land_id=props['land_id'],
                    defaults={
                        'location': Point(coords[0], coords[1]),
                        'area_text': area_text,
                        'price_text': price_text,
                        'marker_title': props['marker_title'],
                        'marker_id': props['marker_id'],
                    }
                )
                
                if created:
                    imported_count += 1
                    self.stdout.write(f'  ✅ Land {land.land_id}: {land.marker_title}')
            
            self.stdout.write(self.style.SUCCESS(f'📊 Imported {imported_count} lands'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error importing lands: {e}'))

    def parse_plot_pricing(self, marker_title):
        """Parse '320 Sq Yards - ₹ 18000 /Sq Yard' into components"""
        try:
            # Extract area (number before 'Sq Yards')
            area_match = re.search(r'(\d+)\s*Sq Yards', marker_title)
            area_sq_yards = int(area_match.group(1)) if area_match else None
            
            # Extract price (number after ₹)
            price_match = re.search(r'₹\s*(\d+)\s*/Sq Yard', marker_title)
            price_per_sq_yard = int(price_match.group(1)) if price_match else None
            
            return area_sq_yards, price_per_sq_yard
        except:
            return None, None

    def parse_land_pricing(self, marker_title):
        """Parse '12 Acres - ₹80 Lakhs/Acre' into components"""
        try:
            # Split by ' - '
            parts = marker_title.split(' - ')
            if len(parts) == 2:
                return parts[0].strip(), parts[1].strip()
        except:
            pass
        return marker_title, ""