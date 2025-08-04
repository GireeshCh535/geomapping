# Create this file: maps/management/commands/setup_delhi_ncr.py

from django.core.management.base import BaseCommand
from django.db import transaction
from maps.models import State, City
import time

class Command(BaseCommand):
    help = 'Setup Delhi NCR region with all cities and states'
    
    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Force recreation of existing data')
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🏛️  DELHI NCR SETUP"))
        self.stdout.write("Setting up Delhi National Capital Region with all cities...")
        
        start_time = time.time()
        
        with transaction.atomic():
            # Setup states first
            states = self._setup_states(options['force'])
            
            # Setup cities
            cities = self._setup_cities(states, options['force'])
            
        total_time = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(f"\n🎉 Delhi NCR setup completed in {total_time:.1f} seconds!"))
        
        # Show summary
        self.stdout.write(f"\n📊 Summary:")
        self.stdout.write(f"   States: {len(states)}")
        self.stdout.write(f"   Cities: {len(cities)}")
        
        # Show next steps
        self.stdout.write(f"\n📋 NEXT STEPS:")
        self.stdout.write(f"1. Import data for each city using: python manage.py import_city_data --city CITY_SLUG")
        self.stdout.write(f"2. Available cities: {', '.join([city.slug for city in cities])}")
        
    def _setup_states(self, force):
        """Setup all states in Delhi NCR"""
        self.stdout.write(f"\n🏛️  Setting up states...")
        
        states_data = [
            {
                'name': 'Delhi',
                'slug': 'delhi',
                'code': 'DL',
                'center_lat': 28.6139,
                'center_lng': 77.2090,
            },
            {
                'name': 'Haryana',
                'slug': 'haryana',
                'code': 'HR',
                'center_lat': 29.0588,
                'center_lng': 76.0856,
            },
            {
                'name': 'Uttar Pradesh',
                'slug': 'uttar-pradesh',
                'code': 'UP',
                'center_lat': 26.8467,
                'center_lng': 80.9462,
            },
            {
                'name': 'Rajasthan',
                'slug': 'rajasthan',
                'code': 'RJ',
                'center_lat': 27.0238,
                'center_lng': 74.2179,
            }
        ]
        
        states = []
        for state_info in states_data:
            if force:
                State.objects.filter(slug=state_info['slug']).delete()
            
            state, created = State.objects.get_or_create(
                slug=state_info['slug'],
                defaults=state_info
            )
            
            states.append(state)
            
            if created:
                self.stdout.write(f"   ✅ Created state: {state.name}")
            else:
                self.stdout.write(f"   📍 Using existing state: {state.name}")
        
        return states
    
    def _setup_cities(self, states, force):
        """Setup all cities in Delhi NCR"""
        self.stdout.write(f"\n🏙️  Setting up cities...")
        
        # Create state lookup
        state_lookup = {state.slug: state for state in states}
        
        # Delhi NCR cities data based on your list
        cities_data = [
            # Delhi (National Capital Territory)
            {
                'name': 'Delhi',
                'slug': 'delhi',
                'state': 'Delhi',
                'state_ref': state_lookup['delhi'],
                'center_lat': 28.6139,
                'center_lng': 77.2090,
                'is_active': True,
            },
            
            # Haryana cities
            {
                'name': 'Gurgaon',
                'slug': 'gurgaon',
                'state': 'Haryana',
                'state_ref': state_lookup['haryana'],
                'center_lat': 28.4595,
                'center_lng': 77.0266,
                'is_active': True,
            },
            {
                'name': 'Faridabad',
                'slug': 'faridabad',
                'state': 'Haryana',
                'state_ref': state_lookup['haryana'],
                'center_lat': 28.4089,
                'center_lng': 77.3178,
                'is_active': True,
            },
            {
                'name': 'Sonipat',
                'slug': 'sonipat',
                'state': 'Haryana',
                'state_ref': state_lookup['haryana'],
                'center_lat': 28.9931,
                'center_lng': 77.0151,
                'is_active': True,
            },
            {
                'name': 'Kharkhauda',
                'slug': 'kharkhauda',
                'state': 'Haryana',
                'state_ref': state_lookup['haryana'],
                'center_lat': 28.8629,
                'center_lng': 76.9109,
                'is_active': True,
            },
            {
                'name': 'Bahadurgarh',
                'slug': 'bahadurgarh',
                'state': 'Haryana',
                'state_ref': state_lookup['haryana'],
                'center_lat': 28.6930,
                'center_lng': 76.9380,
                'is_active': True,
            },
            {
                'name': 'Sampla',
                'slug': 'sampla',
                'state': 'Haryana',
                'state_ref': state_lookup['haryana'],
                'center_lat': 28.7607,
                'center_lng': 76.7788,
                'is_active': True,
            },
            {
                'name': 'Badli',
                'slug': 'badli',
                'state': 'Haryana',
                'state_ref': state_lookup['haryana'],
                'center_lat': 28.7041,
                'center_lng': 77.1025,
                'is_active': True,
            },
            {
                'name': 'Badsa',
                'slug': 'badsa',
                'state': 'Haryana',
                'state_ref': state_lookup['haryana'],
                'center_lat': 28.6167,
                'center_lng': 76.7833,
                'is_active': True,
            },
            {
                'name': 'Farukhnagar',
                'slug': 'farukhnagar',
                'state': 'Haryana',
                'state_ref': state_lookup['haryana'],
                'center_lat': 28.4495,
                'center_lng': 76.8245,
                'is_active': True,
            },
            {
                'name': 'Pataudi',
                'slug': 'pataudi',
                'state': 'Haryana',
                'state_ref': state_lookup['haryana'],
                'center_lat': 28.3257,
                'center_lng': 76.7814,
                'is_active': True,
            },
            {
                'name': 'Dharuhera',
                'slug': 'dharuhera',
                'state': 'Haryana',
                'state_ref': state_lookup['haryana'],
                'center_lat': 28.2048,
                'center_lng': 76.7950,
                'is_active': True,
            },
            {
                'name': 'Gwal Pahari',
                'slug': 'gwal-pahari',
                'state': 'Haryana',
                'state_ref': state_lookup['haryana'],
                'center_lat': 28.4167,
                'center_lng': 77.1333,
                'is_active': True,
            },
            {
                'name': 'Sohna',
                'slug': 'sohna',
                'state': 'Haryana',
                'state_ref': state_lookup['haryana'],
                'center_lat': 28.2450,
                'center_lng': 77.0650,
                'is_active': True,
            },
            {
                'name': 'Pirthala',
                'slug': 'pirthala',
                'state': 'Haryana',
                'state_ref': state_lookup['haryana'],
                'center_lat': 28.7000,
                'center_lng': 76.9500,
                'is_active': True,
            },
            {
                'name': 'Palwal',
                'slug': 'palwal',
                'state': 'Haryana',
                'state_ref': state_lookup['haryana'],
                'center_lat': 28.1441,
                'center_lng': 77.3260,
                'is_active': True,
            },
            
            # Uttar Pradesh cities
            {
                'name': 'Noida',
                'slug': 'noida',
                'state': 'Uttar Pradesh',
                'state_ref': state_lookup['uttar-pradesh'],
                'center_lat': 28.5355,
                'center_lng': 77.3910,
                'is_active': True,
            },
            {
                'name': 'YEIDA',
                'slug': 'yeida',
                'state': 'Uttar Pradesh',
                'state_ref': state_lookup['uttar-pradesh'],
                'center_lat': 28.4833,
                'center_lng': 77.5000,
                'is_active': True,
            },
            {
                'name': 'Greater Noida',
                'slug': 'greater-noida',
                'state': 'Uttar Pradesh',
                'state_ref': state_lookup['uttar-pradesh'],
                'center_lat': 28.4744,
                'center_lng': 77.5040,
                'is_active': True,
            },
            {
                'name': 'Ghaziabad',
                'slug': 'ghaziabad',
                'state': 'Uttar Pradesh',
                'state_ref': state_lookup['uttar-pradesh'],
                'center_lat': 28.6692,
                'center_lng': 77.4538,
                'is_active': True,
            },
            {
                'name': 'Loni',
                'slug': 'loni',
                'state': 'Uttar Pradesh',
                'state_ref': state_lookup['uttar-pradesh'],
                'center_lat': 28.7333,
                'center_lng': 77.2833,
                'is_active': True,
            },
            {
                'name': 'Bhagpat - Baraut - Khekra',
                'slug': 'bhagpat-baraut-khekra',
                'state': 'Uttar Pradesh',
                'state_ref': state_lookup['uttar-pradesh'],
                'center_lat': 28.9500,
                'center_lng': 77.2167,
                'is_active': True,
            },
            {
                'name': 'Modinagar',
                'slug': 'modinagar',
                'state': 'Uttar Pradesh',
                'state_ref': state_lookup['uttar-pradesh'],
                'center_lat': 28.8329,
                'center_lng': 77.6197,
                'is_active': True,
            },
            
            # Rajasthan cities
            {
                'name': 'Bhiwadi',
                'slug': 'bhiwadi',
                'state': 'Rajasthan',
                'state_ref': state_lookup['rajasthan'],
                'center_lat': 28.2098,
                'center_lng': 76.8606,
                'is_active': True,
            },
        ]
        
        cities = []
        for city_info in cities_data:
            if force:
                City.objects.filter(slug=city_info['slug']).delete()
            
            city, created = City.objects.get_or_create(
                slug=city_info['slug'],
                defaults=city_info
            )
            
            cities.append(city)
            
            if created:
                self.stdout.write(f"   ✅ Created city: {city.name} ({city.state})")
            else:
                self.stdout.write(f"   📍 Using existing city: {city.name} ({city.state})")
        
        return cities