#!/usr/bin/env python3
"""
Django management command to insert Delhi Master Plan data.
Creates ONE layer (delhi_masterplan) under city delhi-ncr with all GeoJSON files from data/delhi_ncr/master_plan.
Features have properties: fid, NAME, AREA_SQMTR, COLOR, fill_color (fill_color from run_fill_color_delhi_masterplan.sh).
API uses properties.NAME and properties.fill_color.

Usage:
    # 1. Add fill_color to GeoJSONs (from project root):
    #    bash scripts/run_fill_color_delhi_masterplan.sh
    # 2. Insert into DB:
    python manage.py insert_delhi_masterplan_data --delete-existing
    python manage.py insert_delhi_masterplan_data --data-dir data/delhi_ncr/master_plan
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.gis.geos import GEOSGeometry
from pathlib import Path
import json

from maps.models import (
    State, City, LayerCategory, DataLayer, GeoFeature,
    CityLayerStyle, LayerGroup, CityZoneMapping
)


class Command(BaseCommand):
    help = 'Insert Delhi master plan data (layer: delhi_masterplan, city: delhi-ncr)'

    def add_arguments(self, parser):
        parser.add_argument('--delete-existing', action='store_true', help='Delete existing delhi_masterplan layer first')
        parser.add_argument(
            '--data-dir',
            type=str,
            default='data/delhi_ncr/master_plan',
            help='Directory containing master plan GeoJSON files and legend.csv',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting Delhi Master Plan Data Insertion'))
        self.data_dir = Path(options['data_dir'])
        if not self.data_dir.exists():
            raise CommandError(f'Data directory does not exist: {self.data_dir}')
        try:
            with transaction.atomic():
                self.setup_state_and_city()
                self.setup_layer_categories()
                if options['delete_existing']:
                    self.delete_existing_delhi_masterplan()
                self.create_and_populate_layer()
                self.create_city_layer_styles()
                self.create_zone_mappings()
                self.print_summary()
                self.stdout.write(self.style.SUCCESS('✅ Delhi Master Plan Data Insertion Completed Successfully!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
            raise CommandError(f'Data insertion failed: {str(e)}')

    def setup_state_and_city(self):
        self.stdout.write('Setting up state and city (Delhi NCR)...')
        self.state, _ = State.objects.get_or_create(
            code='DL',
            defaults={
                'name': 'Delhi',
                'slug': 'delhi',
                'center_lat': 28.6139,
                'center_lng': 77.2090,
                'default_zoom': 7,
                'is_active': True,
            }
        )
        self.city, created = City.objects.get_or_create(
            slug='delhi-ncr',
            defaults={
                'name': 'Delhi NCR',
                'state': 'Delhi',
                'state_ref': self.state,
                'center_lat': 28.6139,
                'center_lng': 77.2090,
                'min_zoom': 8,
                'max_zoom': 18,
                'is_active': True,
            }
        )
        if not self.city.state_ref:
            self.city.state_ref = self.state
            self.city.save()
        self.stdout.write(f'  ✅ City: {self.city.name}')

    def setup_layer_categories(self):
        self.stdout.write('Setting up layer categories...')
        categories = [
            ('BOUNDARIES', 'Administrative Boundaries', 'City and administrative boundaries', '#800080'),
            ('PLANNING', 'Planning Areas', 'Urban planning and development areas', '#FFE4B5'),
            ('RESIDENTIAL', 'Residential', 'Residential zones', '#FFB6C1'),
            ('COMMERCIAL', 'Commercial', 'Commercial zones', '#FFD700'),
            ('INDUSTRIAL', 'Industrial', 'Industrial zones', '#D2691E'),
            ('MIXED_USE', 'Mixed Use', 'Mixed-use zones', '#9370DB'),
            ('UNCLASSIFIED', 'Unclassified', 'Unclassified areas', '#CCCCCC'),
        ]
        self.categories = {}
        for code, name, desc, color in categories:
            cat, _ = LayerCategory.objects.get_or_create(
                code=code,
                defaults={'name': name, 'description': desc, 'default_color': color,
                          'default_stroke': '#333333', 'default_opacity': 0.7, 'display_order': 0, 'is_active': True}
            )
            self.categories[code] = cat

    def delete_existing_delhi_masterplan(self):
        self.stdout.write('Deleting existing delhi_masterplan layer...')
        try:
            layer = DataLayer.objects.get(city=self.city, slug='delhi_masterplan')
            n = layer.geofeature_set.count()
            layer.delete()
            self.stdout.write(f'  ✅ Deleted layer with {n} features')
        except DataLayer.DoesNotExist:
            self.stdout.write('  ℹ️ No existing layer')
        LayerGroup.objects.filter(city=self.city, slug='delhi_masterplan').delete()

    def create_and_populate_layer(self):
        self.stdout.write('\nCreating and populating Delhi master plan layer...')
        files = sorted(self.data_dir.glob('*.geojson'))
        if not files:
            self.stdout.write('  ⚠️ No GeoJSON files found')
            self._create_empty_layer()
            return
        self.stdout.write(f'📁 Found {len(files)} files')
        group, _ = LayerGroup.objects.get_or_create(
            city=self.city, slug='delhi_masterplan',
            defaults={
                'name': 'Delhi Master Plan', 'description': 'Delhi Development Authority master plan',
                'category': self.categories['PLANNING'], 'directory_path': str(self.data_dir),
                'default_color': '#FFE4B5', 'default_stroke': '#FF8C00', 'default_opacity': 0.7,
                'display_order': 0, 'is_visible': True, 'min_zoom': 8, 'max_zoom': 18,
            }
        )
        source_names = [f.name for f in files]
        self.layer, created = DataLayer.objects.get_or_create(
            city=self.city, slug='delhi_masterplan',
            defaults={
                'name': 'Delhi Master Plan', 'description': 'Delhi Development Authority master plan',
                'category': self.categories['PLANNING'], 'layer_group': group,
                'file_format': 'GEOJSON', 'file_path': str(self.data_dir), 'is_directory': True,
                'file_pattern': '*.geojson', 'source_files': source_names, 'geometry_type': 'POLYGON',
                'categorization_method': 'FILENAME', 'is_processed': False, 'feature_count': 0,
                'is_true': True, 'data_source': 'Delhi Development Authority',
            }
        )
        if not created:
            self.layer.source_files = source_names
            self.layer.save()
            self.layer.geofeature_set.all().delete()
        self.processed_files = []
        self.total_features = 0
        geom_types = set()
        for path in files:
            try:
                count, gtype = self.process_file(path)
                if gtype:
                    geom_types.add(gtype)
                self.processed_files.append((path.name, count))
                self.total_features += count
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ {path.name}: {e}'))
        self.layer.feature_count = self.total_features
        self.layer.is_processed = True
        if geom_types:
            self.layer.geometry_type = 'MULTIPOLYGON' if 'MULTIPOLYGON' in geom_types else 'POLYGON'
        self.calculate_layer_bbox(self.layer)
        self.layer.save()
        self.stdout.write(f'\n✅ Populated {self.total_features:,} features from {len(self.processed_files)} files')

    def _create_empty_layer(self):
        group, _ = LayerGroup.objects.get_or_create(
            city=self.city, slug='delhi_masterplan',
            defaults={'name': 'Delhi Master Plan', 'description': 'DDA master plan', 'category': self.categories['PLANNING'],
                      'directory_path': str(self.data_dir), 'default_color': '#FFE4B5', 'default_stroke': '#FF8C00',
                      'default_opacity': 0.7, 'display_order': 0, 'is_visible': True, 'min_zoom': 8, 'max_zoom': 18}
        )
        self.layer, _ = DataLayer.objects.get_or_create(
            city=self.city, slug='delhi_masterplan',
            defaults={'name': 'Delhi Master Plan', 'description': 'DDA master plan', 'category': self.categories['PLANNING'],
                      'layer_group': group, 'file_format': 'GEOJSON', 'file_path': str(self.data_dir), 'is_directory': True,
                      'file_pattern': '*.geojson', 'source_files': [], 'geometry_type': 'POLYGON',
                      'categorization_method': 'FILENAME', 'is_processed': True, 'feature_count': 0,
                      'is_true': True, 'data_source': 'Delhi Development Authority'}
        )
        self.processed_files = []
        self.total_features = 0

    def process_file(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        features = data.get('features', [])
        if not features:
            return 0, None
        category = self.determine_category(file_path.stem)
        gtype = self.geom_type(features[0])
        added = 0
        for idx, feat in enumerate(features, 1):
            try:
                geom_data = feat.get('geometry')
                if not geom_data:
                    continue
                geom = GEOSGeometry(json.dumps(geom_data))
                if geom.hasz:
                    geom = self.flatten(geom)
                if not geom.valid:
                    geom = geom.buffer(0)
                    if not geom.valid:
                        continue
                props = feat.get('properties', {})
                name = props.get('NAME') or props.get('Name') or props.get('name') or f"{file_path.stem} - {idx}"
                if not isinstance(name, str):
                    name = str(name)
                area_val = self.safe_float(props.get('AREA_SQMTR') or props.get('Shape_Area') or props.get('Area'))
                GeoFeature.objects.create(
                    layer=self.layer,
                    geometry=geom,
                    name=name.strip(),
                    source_layer_name=file_path.stem,
                    zone_category=category.name,
                    zone_subcategory=file_path.stem,
                    area=area_val,
                    shape_length=self.safe_float(props.get('Shape_Length') or props.get('shape_leng')),
                    shape_area=area_val,
                    objectid=self.safe_int(props.get('OBJECTID') or props.get('objectid', idx)),
                    fid=self.safe_int(props.get('FID') or props.get('fid', idx)),
                    properties=props,
                    is_valid=True,
                )
                added += 1
            except Exception as e:
                self.stdout.write(f'    ⚠️ Feature {idx}: {e}')
        self.stdout.write(f'  ✅ {file_path.name}: {added} features')
        return added, gtype

    def determine_category(self, stem):
        s = stem.lower()
        if 'boundary' in s:
            return self.categories['BOUNDARIES']
        if 'residential' in s or 'housing' in s:
            return self.categories.get('RESIDENTIAL', self.categories['PLANNING'])
        if 'commercial' in s:
            return self.categories.get('COMMERCIAL', self.categories['PLANNING'])
        if 'industrial' in s or 'industry' in s:
            return self.categories.get('INDUSTRIAL', self.categories['PLANNING'])
        if 'mixed' in s:
            return self.categories.get('MIXED_USE', self.categories['PLANNING'])
        return self.categories['PLANNING']

    def geom_type(self, feature):
        t = feature.get('geometry', {}).get('type', '').upper()
        return {'POLYGON': 'POLYGON', 'MULTIPOLYGON': 'MULTIPOLYGON'}.get(t, 'POLYGON')

    def flatten(self, geom):
        d = json.loads(geom.geojson)
        def noz(c):
            return c[:2] if isinstance(c[0], (int, float)) else [noz(x) for x in c]
        if 'coordinates' in d:
            d['coordinates'] = noz(d['coordinates'])
        return GEOSGeometry(json.dumps(d))

    def safe_float(self, v):
        if v is None or v == '':
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    def safe_int(self, v):
        if v is None or v == '':
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    def calculate_layer_bbox(self, layer):
        try:
            from django.contrib.gis.db.models import Extent
            ext = layer.geofeature_set.aggregate(extent=Extent('geometry'))['extent']
            if ext:
                layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax = ext
                layer.save(update_fields=['bbox_xmin', 'bbox_ymin', 'bbox_xmax', 'bbox_ymax'])
        except Exception:
            pass

    def create_city_layer_styles(self):
        self.stdout.write('\nEnsuring city layer styles...')
        configs = {
            'BOUNDARIES': {'fill_color': '#800080', 'stroke_color': '#4B0082', 'opacity': 0.3, 'stroke_width': 2, 'fill_pattern': 'SOLID'},
            'PLANNING': {'fill_color': '#FFE4B5', 'stroke_color': '#FF8C00', 'opacity': 0.5, 'stroke_width': 1, 'fill_pattern': 'SOLID'},
            'RESIDENTIAL': {'fill_color': '#FFB6C1', 'stroke_color': '#FF69B4', 'opacity': 0.6, 'stroke_width': 1, 'fill_pattern': 'SOLID'},
            'COMMERCIAL': {'fill_color': '#FFD700', 'stroke_color': '#FFA500', 'opacity': 0.6, 'stroke_width': 1, 'fill_pattern': 'HATCHED'},
            'INDUSTRIAL': {'fill_color': '#D2691E', 'stroke_color': '#8B4513', 'opacity': 0.6, 'stroke_width': 1, 'fill_pattern': 'CROSS_HATCHED'},
            'MIXED_USE': {'fill_color': '#9370DB', 'stroke_color': '#6B46C1', 'opacity': 0.6, 'stroke_width': 1, 'fill_pattern': 'STRIPED'},
            'UNCLASSIFIED': {'fill_color': '#CCCCCC', 'stroke_color': '#666666', 'opacity': 0.5, 'stroke_width': 1, 'fill_pattern': 'SOLID'},
        }
        for code, cfg in configs.items():
            if code in self.categories:
                CityLayerStyle.objects.update_or_create(
                    city=self.city, category=self.categories[code],
                    defaults={**cfg, 'is_visible': True, 'min_zoom': 8, 'max_zoom': 18}
                )
        self.stdout.write('  ✅ Styles updated')

    def create_zone_mappings(self):
        self.stdout.write('\nCreating zone mappings...')
        if not getattr(self, 'layer', None):
            return
        for source in self.layer.geofeature_set.values_list('source_layer_name', flat=True).distinct():
            if not source:
                continue
            cat = self.determine_category(source)
            try:
                style = CityLayerStyle.objects.get(city=self.city, category=cat)
            except CityLayerStyle.DoesNotExist:
                style = CityLayerStyle.objects.create(city=self.city, category=cat, fill_color=cat.default_color,
                      stroke_color=cat.default_stroke, opacity=cat.default_opacity)
            cnt = self.layer.geofeature_set.filter(source_layer_name=source).count()
            CityZoneMapping.objects.update_or_create(
                city=self.city, zone_name=source,
                defaults={'category': cat, 'style': style, 'feature_count': cnt, 'is_active': True}
            )
            self.stdout.write(f'  ✅ {source}: {cnt} features')

    def print_summary(self):
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('📊 Delhi Master Plan – Import Summary'))
        self.stdout.write('='*60)
        self.stdout.write(f'  City: {self.city.name} (delhi-ncr)')
        self.stdout.write(f'  Layer: delhi_masterplan')
        if hasattr(self, 'processed_files'):
            self.stdout.write(f'  Files: {len(self.processed_files)}')
            self.stdout.write(f'  Total features: {getattr(self, "total_features", 0):,}')
        self.stdout.write('='*60)
