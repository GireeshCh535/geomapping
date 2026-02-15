#!/usr/bin/env python3
"""
Django management command to delete the existing Dadra and Nagar Haveli and Daman and Diu state
and all associated data to allow for proper recreation with the correct structure
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.gis.geos import GEOSGeometry
from django.utils.text import slugify
from pathlib import Path
import json
import glob
import os

from maps.models import (
    State, City, LayerCategory, DataLayer, GeoFeature, 
    CityLayerStyle, LayerGroup, CityZoneMapping
)


class Command(BaseCommand):
    help = 'Delete existing Dadra and Nagar Haveli and Daman and Diu state and all associated data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion (required for safety)',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.ERROR('❌ This command will delete all Dadra and Nagar Haveli and Daman and Diu data!')
            )
            self.stdout.write(
                self.style.WARNING('Use --confirm flag to proceed with deletion')
            )
            return
        
        self.stdout.write(
            self.style.WARNING('🗑️ Starting deletion of Dadra and Nagar Haveli and Daman and Diu state and all associated data')
        )
        
        try:
            with transaction.atomic():
                # Find the state
                try:
                    state = State.objects.get(slug='dadra-nagar-haveli-daman-diu')
                    self.stdout.write(f'Found state: {state.name}')
                except State.DoesNotExist:
                    self.stdout.write('No existing state found with slug: dadra-nagar-haveli-daman-diu')
                    return
                
                # Get all cities in this state
                cities = City.objects.filter(state_ref=state)
                self.stdout.write(f'Found {cities.count()} cities in this state')
                
                total_deleted = 0
                
                # Delete all data for each city
                for city in cities:
                    self.stdout.write(f'\n🗑️ Deleting data for city: {city.name} ({city.slug})')
                    
                    # Delete GeoFeatures
                    features_count = GeoFeature.objects.filter(layer__city=city).count()
                    if features_count > 0:
                        GeoFeature.objects.filter(layer__city=city).delete()
                        self.stdout.write(f'  ✅ Deleted {features_count} GeoFeatures')
                        total_deleted += features_count
                    
                    # Delete DataLayers
                    layers_count = DataLayer.objects.filter(city=city).count()
                    if layers_count > 0:
                        DataLayer.objects.filter(city=city).delete()
                        self.stdout.write(f'  ✅ Deleted {layers_count} DataLayers')
                    
                    # Delete LayerGroups
                    groups_count = LayerGroup.objects.filter(city=city).count()
                    if groups_count > 0:
                        LayerGroup.objects.filter(city=city).delete()
                        self.stdout.write(f'  ✅ Deleted {groups_count} LayerGroups')
                    
                    # Delete CityLayerStyles
                    styles_count = CityLayerStyle.objects.filter(city=city).count()
                    if styles_count > 0:
                        CityLayerStyle.objects.filter(city=city).delete()
                        self.stdout.write(f'  ✅ Deleted {styles_count} CityLayerStyles')
                    
                    # Delete CityZoneMappings
                    mappings_count = CityZoneMapping.objects.filter(city=city).count()
                    if mappings_count > 0:
                        CityZoneMapping.objects.filter(city=city).delete()
                        self.stdout.write(f'  ✅ Deleted {mappings_count} CityZoneMappings')
                    
                    # Delete the city itself
                    city.delete()
                    self.stdout.write(f'  ✅ Deleted city: {city.name}')
                
                # Delete the state
                state.delete()
                self.stdout.write(f'\n✅ Deleted state: {state.name}')
                
                self.stdout.write(f'\n📊 DELETION SUMMARY:')
                self.stdout.write(f'  Total GeoFeatures deleted: {total_deleted}')
                self.stdout.write(f'  Cities deleted: {cities.count()}')
                self.stdout.write(f'  State deleted: 1')
                
                self.stdout.write(
                    self.style.SUCCESS('\n✅ Dadra and Nagar Haveli and Daman and Diu state and all associated data deleted successfully!')
                )
                self.stdout.write(
                    self.style.SUCCESS('You can now run the insert scripts to recreate with the correct structure.')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error during deletion: {str(e)}')
            )
            raise CommandError(f'Deletion failed: {str(e)}')
