#!/usr/bin/env python3
"""
Django management command to insert Chennai Master Plan data
Inserts boundary data for Chennai City and CMA (Chennai Metropolitan Area)
"""

import os
import sys
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.db.models import Q
from django.db import transaction
import geopandas as gpd
import pandas as pd
import json

# Add the project root to the Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent.parent  # maps/management/commands -> maps -> . -> project_root
sys.path.insert(0, str(project_root))

from maps.models import State, City, DataLayer, GeoFeature, LayerCategory


class Command(BaseCommand):
    help = 'Insert Chennai Master Plan data (City and CMA boundaries)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force regeneration even if data already exists',
        )

    def handle(self, *args, **options):
        force = options['force']
        
        # Data paths
        data_dir = project_root / "data" / "tamil_nadu" / "chennai" / "chennai_master_plan"
        
        # GeoJSON files to process
        geojson_files = [
            {
                'file': 'ChennaiCityBoundary.geojson',
                'name': 'Chennai City Boundary',
                'description': 'Administrative boundary of Chennai City Corporation'
            },
            {
                'file': 'CMA_Boundary.geojson', 
                'name': 'Chennai Metropolitan Area Boundary',
                'description': 'Administrative boundary of Chennai Metropolitan Area'
            }
        ]
        
        try:
            with transaction.atomic():
                # Get or create Tamil Nadu state
                state, created = State.objects.get_or_create(
                    name='Tamil Nadu',
                    defaults={'slug': 'tamil_nadu'}
                )
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f'Created state: {state.name}')
                    )
                else:
                    self.stdout.write(f'Using existing state: {state.name}')

                # Get or create Chennai city
                city, created = City.objects.get_or_create(
                    name='Chennai',
                    state=state,
                    defaults={'slug': 'chennai'}
                )
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f'Created city: {city.name}')
                    )
                else:
                    self.stdout.write(f'Using existing city: {city.name}')

                # Get or create BOUNDARIES category
                category, created = LayerCategory.objects.get_or_create(
                    code='BOUNDARIES',
                    defaults={
                        'name': 'Administrative Boundaries',
                        'description': 'Administrative boundaries and jurisdictional areas',
                        'default_color': '#FF6B6B',
                        'default_stroke': '#D63031',
                        'default_opacity': 0.8
                    }
                )
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f'Created category: {category.name}')
                    )
                else:
                    self.stdout.write(f'Using existing category: {category.name}')

                # Get or create Chennai Master Plan layer
                layer, created = DataLayer.objects.get_or_create(
                    city=city,
                    slug='chennai_master_plan',
                    defaults={
                        'name': 'Chennai Master Plan',
                        'category': category,
                        'description': 'Chennai Master Plan boundaries and land use data',
                        'geometry_type': 'POLYGON',
                        'is_processed': False  # Will be set to True after processing
                    }
                )
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f'Created layer: {layer.name}')
                    )
                else:
                    self.stdout.write(f'Using existing layer: {layer.name}')

                # Track total features processed
                features_processed = 0
                
                # Process each GeoJSON file
                for file_info in geojson_files:
                    file_path = data_dir / file_info['file']
                    
                    if not file_path.exists():
                        self.stdout.write(
                            self.style.WARNING(f'File not found: {file_path}')
                        )
                        continue

                    self.stdout.write(f'Processing: {file_info["file"]}')
                    
                    # Read GeoJSON file
                    try:
                        gdf = gpd.read_file(file_path)
                        self.stdout.write(f'Loaded {len(gdf)} features from {file_info["file"]}')
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'Error reading {file_info["file"]}: {e}')
                        )
                        continue

                    # Process each feature
                    for idx, row in gdf.iterrows():
                        try:
                            # Get geometry
                            geometry = row.geometry
                            if geometry is None or geometry.is_empty:
                                self.stdout.write(
                                    self.style.WARNING(f'Skipping empty geometry in {file_info["file"]} at index {idx}')
                                )
                                continue

                            # Convert to GEOS geometry
                            geos_geometry = GEOSGeometry(geometry.wkt)
                            
                            # Create feature name
                            feature_name = file_info['name']
                            if 'City_Name' in row and pd.notna(row['City_Name']):
                                feature_name = f"{file_info['name']} - {row['City_Name']}"
                            elif 'id' in row and pd.notna(row['id']):
                                feature_name = f"{file_info['name']} - ID {row['id']}"

                            # Check if feature already exists
                            existing_feature = GeoFeature.objects.filter(
                                layer=layer,
                                name=feature_name
                            ).first()

                            if existing_feature and not force:
                                self.stdout.write(f'Skipping existing feature: {feature_name}')
                                continue

                            # Prepare properties
                            properties = {}
                            for col in gdf.columns:
                                if col != 'geometry' and pd.notna(row[col]):
                                    properties[col] = str(row[col])

                            # Create or update feature
                            if existing_feature and force:
                                existing_feature.geometry = geos_geometry
                                existing_feature.properties = properties
                                existing_feature.save()
                                self.stdout.write(
                                    self.style.SUCCESS(f'Updated feature: {feature_name}')
                                )
                                features_processed += 1
                            else:
                                GeoFeature.objects.create(
                                    layer=layer,
                                    name=feature_name,
                                    geometry=geos_geometry,
                                    properties=properties,
                                    description=file_info['description']
                                )
                                self.stdout.write(
                                    self.style.SUCCESS(f'Created feature: {feature_name}')
                                )
                                features_processed += 1

                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f'Error processing feature {idx} in {file_info["file"]}: {e}')
                            )
                            continue

                # Update layer metadata
                total_features = GeoFeature.objects.filter(layer=layer).count()
                layer.is_processed = True
                layer.feature_count = total_features
                layer.save()
                
                # Summary
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nSuccessfully processed Chennai Master Plan data!\n'
                        f'Features processed in this run: {features_processed}\n'
                        f'Total features in layer: {total_features}\n'
                        f'Layer marked as processed: {layer.is_processed}'
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error processing Chennai Master Plan data: {e}')
            )
            raise
