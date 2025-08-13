# maps/management/commands/import_geo_layers.py
"""
Fresh import command that correctly handles GeoJSON files
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.gis.geos import Polygon, MultiPolygon, LineString, MultiLineString
from django.utils.text import slugify
from django.utils import timezone
from maps.models import State, City, LayerCategory, DataLayer, GeoFeature, LayerGroup, CityLayerStyle
from maps.config import DATA_IMPORT_CONFIG, LAYER_CATEGORIES
import json
from pathlib import Path

class Command(BaseCommand):
    help = 'Import geographic layers with correct format detection'
    
    def add_arguments(self, parser):
        parser.add_argument('--data-dir', required=True, help='Base data directory')
        parser.add_argument('--city', required=True, help='City slug')
        parser.add_argument('--layer-group', required=True, help='Layer group slug')
        parser.add_argument('--force', action='store_true', help='Force re-import')
        
    def handle(self, *args, **options):
        data_dir = Path(options['data_dir'])
        city_slug = options['city']
        group_slug = options['layer_group']
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS(f'🚀 IMPORTING {group_slug.upper()} FOR {city_slug.upper()}'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        # Get city
        try:
            city = City.objects.get(slug=city_slug)
        except City.DoesNotExist:
            city = City.objects.get(name__iexact=city_slug.replace('-', ' '))
        
        self.stdout.write(f'✓ City: {city.name}')
        
        # Get config
        for state_slug, state_config in DATA_IMPORT_CONFIG['states'].items():
            if city_slug in state_config.get('cities', {}):
                city_config = state_config['cities'][city_slug]
                break
        else:
            self.stdout.write(self.style.ERROR(f'❌ No config for {city_slug}'))
            return
        
        # Get layer group config
        layer_groups = city_config.get('layer_groups', {})
        if group_slug not in layer_groups:
            self.stdout.write(self.style.ERROR(f'❌ No config for layer group {group_slug}'))
            return
        
        group_config = layer_groups[group_slug]
        
        # Process files
        files_path = data_dir / group_config['path']
        if not files_path.exists():
            self.stdout.write(self.style.ERROR(f'❌ Path not found: {files_path}'))
            return
        
        self.stdout.write(f'📂 Processing {len(group_config["files"])} files from {files_path}')
        
        with transaction.atomic():
            for filename, file_config in group_config['files'].items():
                file_path = files_path / filename
                
                if not file_path.exists():
                    self.stdout.write(self.style.WARNING(f'  ⚠️  {filename} not found'))
                    continue
                
                self._import_file(city, file_path, file_config, options)
    
    def _import_file(self, city, file_path, file_config, options):
        """Import a single file"""
        
        self.stdout.write(f'\n📄 {file_path.name}')
        
        # Create/get layer
        layer_slug = slugify(file_path.stem)
        
        if options['force']:
            DataLayer.objects.filter(city=city, slug=layer_slug).delete()
        
        category, _ = LayerCategory.objects.get_or_create(
            code=file_config.get('category', 'TRANSPORT'),
            defaults={'name': file_config.get('category', 'TRANSPORT')}
        )
        
        # DETERMINE FORMAT BY FILE EXTENSION
        if file_path.suffix.lower() == '.geojson':
            file_format = 'GEOJSON'
            data_format = 'geojson'
        else:  # .json
            file_format = 'ESRI_JSON'
            data_format = 'esri_json'
        
        self.stdout.write(f'  Format: {data_format}')
        
        layer = DataLayer.objects.create(
            city=city,
            category=category,
            name=file_config['name'],
            slug=layer_slug,
            original_filename=file_path.name,
            file_format=file_format,
            categorization_method='MANUAL',
            feature_count=0,
            is_processed=False
        )
        
        # Import features
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        features = []
        
        if 'features' in data:
            self.stdout.write(f'  Found {len(data["features"])} features')
            
            for idx, feature in enumerate(data['features'][:100]):  # Limit to 100 for testing
                if not feature or not feature.get('geometry'):
                    continue
                
                geom = feature['geometry']
                props = feature.get('properties', {})
                geom_type = geom.get('type')
                coords = geom.get('coordinates')
                
                if not coords:
                    continue
                
                try:
                    # Create geometry based on type
                    if geom_type == 'MultiLineString':
                        lines = []
                        for line_coords in coords:
                            if len(line_coords) >= 2:
                                lines.append(LineString(line_coords))
                        if lines:
                            geometry = MultiLineString(lines)
                            features.append(GeoFeature(
                                layer=layer,
                                geometry=geometry,
                                properties=props
                            ))
                    
                    elif geom_type == 'LineString':
                        if len(coords) >= 2:
                            geometry = LineString(coords)
                            features.append(GeoFeature(
                                layer=layer,
                                geometry=geometry,
                                properties=props
                            ))
                    
                    elif geom_type == 'MultiPolygon':
                        polygons = []
                        for poly_coords in coords:
                            if poly_coords and len(poly_coords[0]) > 3:
                                polygons.append(Polygon(poly_coords[0]))
                        if polygons:
                            geometry = MultiPolygon(polygons)
                            features.append(GeoFeature(
                                layer=layer,
                                geometry=geometry,
                                properties=props
                            ))
                    
                    elif geom_type == 'Polygon':
                        if coords and len(coords[0]) > 3:
                            geometry = Polygon(coords[0])
                            features.append(GeoFeature(
                                layer=layer,
                                geometry=geometry,
                                properties=props
                            ))
                    
                    if idx == 0 and features:
                        self.stdout.write(f'  First feature type: {geom_type} ✓')
                        
                except Exception as e:
                    if idx < 3:
                        self.stdout.write(f'  Error on feature {idx}: {e}')
        
        # Bulk create
        if features:
            GeoFeature.objects.bulk_create(features, batch_size=500)
            self.stdout.write(self.style.SUCCESS(f'  ✅ Imported {len(features)} features'))
            
            layer.feature_count = len(features)
            layer.is_processed = True
            layer.save()
        else:
            self.stdout.write(self.style.WARNING(f'  ⚠️  No features imported'))
        
        # Create style
        try:
            CityLayerStyle.objects.filter(city=city, category=category).delete()
            
            color = file_config.get('color', '#14e098')
            if isinstance(color, dict):
                fill_color = color.get('solid', '#14e098')
            else:
                fill_color = color
            
            CityLayerStyle.objects.create(
                city=city,
                category=category,
                fill_color=fill_color,
                stroke_color=fill_color,
                fill_pattern='SOLID',
                pattern_color=fill_color,
                stroke_width=2
            )
            self.stdout.write(f'  Style: {fill_color}')
        except Exception as e:
            self.stdout.write(f'  Style error: {e}')