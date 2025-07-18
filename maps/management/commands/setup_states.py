from django.core.management.base import BaseCommand
from django.db import transaction
from maps.models import City, State

class Command(BaseCommand):
    help = 'Setup states for existing cities'

    def handle(self, *args, **options):
        self.stdout.write('Setting up states...')
        
        with transaction.atomic():
            # Get unique states from existing cities
            existing_states = City.objects.values_list('state', flat=True).distinct()
            
            state_mapping = {}
            for state_name in existing_states:
                if not state_name:
                    continue
                    
                # Create slug from name
                slug = state_name.lower().replace(' ', '-')
                # Create 2-letter code
                code = ''.join(word[0] for word in state_name.split())[:2].upper()
                
                state, created = State.objects.get_or_create(
                    name=state_name,
                    defaults={
                        'slug': slug,
                        'code': code,
                        'is_active': True
                    }
                )
                
                if created:
                    self.stdout.write(f'Created state: {state_name}')
                else:
                    self.stdout.write(f'State already exists: {state_name}')
                
                state_mapping[state_name] = state
            
            # Update cities to link to states
            for city in City.objects.all():
                if city.state and city.state in state_mapping:
                    city.state_ref = state_mapping[city.state]
                    city.save()
                    self.stdout.write(f'Updated city: {city.name} -> {city.state}')
        
        self.stdout.write(self.style.SUCCESS('States setup completed!')) 