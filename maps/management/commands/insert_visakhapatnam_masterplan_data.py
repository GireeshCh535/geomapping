#!/usr/bin/env python3
"""
Django management command to insert Visakhapatnam Masterplan data
Creates ONE layer (visakhapatnam_master_plan) with all masterplan files as features.
Features have properties: FID, MANDAL, DISTRICT, Village, Category, Shape_Length, Shape_Area, RuleID, Override, fill_color.
fill_color is set by geojson_add_fill_color_from_legend.py; API reads fill_color from properties only.

Usage:
    python manage.py insert_visakhapatnam_masterplan_data
    python manage.py insert_visakhapatnam_masterplan_data --delete-existing
    python manage.py insert_visakhapatnam_masterplan_data --data-dir data/andhra_pradesh/visakhapatnam/master_plan
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
    help = 'Insert Visakhapatnam masterplan data into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Delete existing Visakhapatnam masterplan data before inserting',
        )
        parser.add_argument(
            '--data-dir',
            type=str,
            default='data/andhra_pradesh/visakhapatnam/master_plan',
            help='Directory containing the master plan GeoJSON files',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting Visakhapatnam Masterplan Data Insertion')
        )
        self.data_dir = Path(options['data_dir'])
        if not self.data_dir.exists():
            raise CommandError(f'Data directory does not exist: {self.data_dir}')
        try:
            with transaction.atomic():
                self.setup_state_and_city()
                self.setup_layer_categories()
                if options['delete_existing']:
                    self.delete_existing_visakhapatnam_masterplan_data()
                self.create_and_populate_master_plan_layer()
                self.create_city_layer_styles()
                self.create_zone_mappings()
                self.print_summary()
                self.stdout.write(
                    self.style.SUCCESS('✅ Visakhapatnam Masterplan Data Insertion Completed Successfully!')
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error during data insertion: {str(e)}'))
            raise CommandError(f'Data insertion failed: {str(e)}')

    def setup_state_and_city(self):
        """Setup Andhra Pradesh state and Visakhapatnam city."""
        self.stdout.write('Setting up Andhra Pradesh state and Visakhapatnam city...')
        self.state, created = State.objects.get_or_create(
            code='AP',
            defaults={
                'name': 'Andhra Pradesh',
                'slug': 'andhra-pradesh',
                'center_lat': 15.9129,
                'center_lng': 79.7400,
                'default_zoom': 7,
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(f'  ✅ Created state: {self.state.name}')
        else:
            self.stdout.write(f'  ✅ Found existing state: {self.state.name}')
        self.city, created = City.objects.get_or_create(
            slug='visakhapatnam',
            defaults={
                'name': 'Visakhapatnam',
                'state': 'Andhra Pradesh',
                'state_ref': self.state,
                'center_lat': 17.7396,
                'center_lng': 83.2247,
                'min_zoom': 8,
                'max_zoom': 18,
                'is_active': True,
            }
        )
        if not created and not self.city.state_ref:
            self.city.state_ref = self.state
            self.city.save()
        if created:
            self.stdout.write(f'  ✅ Created city: {self.city.name}')
        else:
            self.stdout.write(f'  ✅ Found existing city: {self.city.name}')

    def setup_layer_categories(self):
        """Setup layer categories for Visakhapatnam masterplan."""
        self.stdout.write('Setting up layer categories...')
        categories = [
            ('BOUNDARIES', 'Administrative Boundaries', 'City and administrative boundaries', '#800080'),
            ('PLANNING', 'Planning Areas', 'Urban planning and development areas', '#FFE4B5'),
            ('RESIDENTIAL', 'Residential', 'Residential zones and housing areas', '#FFB6C1'),
            ('COMMERCIAL', 'Commercial', 'Commercial and business zones', '#FFD700'),
            ('INDUSTRIAL', 'Industrial', 'Industrial zones and manufacturing areas', '#D2691E'),
            ('MIXED_USE', 'Mixed Use', 'Mixed-use development zones', '#9370DB'),
            ('UNCLASSIFIED', 'Unclassified', 'Unclassified or miscellaneous areas', '#CCCCCC'),
        ]
        self.categories = {}
        for code, name, description, color in categories:
            category, created = LayerCategory.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'description': description,
                    'default_color': color,
                    'default_stroke': '#333333',
                    'default_opacity': 0.7,
                    'display_order': 0,
                    'is_active': True,
                }
            )
            self.categories[code] = category
            if created:
                self.stdout.write(f'  ✅ Created category: {name}')
            else:
                self.stdout.write(f'  ✅ Found existing category: {name}')

    def delete_existing_visakhapatnam_masterplan_data(self):
        """Delete existing Visakhapatnam masterplan layer and its features."""
        self.stdout.write('Deleting existing Visakhapatnam masterplan data...')
        try:
            layer = DataLayer.objects.get(city=self.city, slug='visakhapatnam_master_plan')
            feature_count = layer.geofeature_set.count()
            layer.delete()
            self.stdout.write(f'  ✅ Deleted layer with {feature_count} features')
        except DataLayer.DoesNotExist:
            self.stdout.write('  ℹ️ No existing visakhapatnam_master_plan layer found')
        LayerGroup.objects.filter(city=self.city, slug='visakhapatnam_master_plan').delete()

    def create_and_populate_master_plan_layer(self):
        """Create ONE master plan layer and populate from all GeoJSON files."""
        self.stdout.write('\nCreating and populating Visakhapatnam master plan layer...')
        all_files = sorted(self.data_dir.glob('*.geojson'))
        if not all_files:
            self.stdout.write('  ⚠️ No GeoJSON files found')
            self._create_empty_layer()
            return
        self.stdout.write(f'📁 Found {len(all_files)} files to process:')
        for f in all_files:
            self.stdout.write(f'  - {f.name}')
        layer_group, _ = LayerGroup.objects.get_or_create(
            city=self.city,
            slug='visakhapatnam_master_plan',
            defaults={
                'name': 'Visakhapatnam Master Plan',
                'description': 'Greater Visakhapatnam Municipal Corporation master plan',
                'category': self.categories['PLANNING'],
                'directory_path': str(self.data_dir),
                'default_color': '#FFE4B5',
                'default_stroke': '#FF8C00',
                'default_opacity': 0.7,
                'display_order': 0,
                'is_visible': True,
                'min_zoom': 8,
                'max_zoom': 18,
            }
        )
        source_file_names = [f.name for f in all_files]
        self.master_plan_layer, created = DataLayer.objects.get_or_create(
            city=self.city,
            slug='visakhapatnam_master_plan',
            defaults={
                'name': 'Visakhapatnam Master Plan',
                'description': 'Visakhapatnam Master Plan - Land Use Categories',
                'category': self.categories['PLANNING'],
                'layer_group': layer_group,
                'file_format': 'GEOJSON',
                'file_path': str(self.data_dir),
                'is_directory': True,
                'file_pattern': '*.geojson',
                'source_files': source_file_names,
                'geometry_type': 'POLYGON',
                'categorization_method': 'FILENAME',
                'is_processed': False,
                'feature_count': 0,
                'is_true': True,
                'data_source': 'Greater Visakhapatnam Municipal Corporation',
            }
        )
        if created:
            self.stdout.write(f'  ✅ Created layer: {self.master_plan_layer.name}')
        else:
            self.stdout.write(f'  ✅ Found existing layer: {self.master_plan_layer.name}')
            self.master_plan_layer.source_files = source_file_names
            self.master_plan_layer.save()
            deleted = self.master_plan_layer.geofeature_set.all().delete()[0]
            if deleted:
                self.stdout.write(f'    Deleted {deleted} existing features')
        self.processed_files = []
        self.failed_files = []
        self.total_features_imported = 0
        geometry_types = set()
        for file_path in all_files:
            try:
                self.stdout.write(f'\n📄 Processing file: {file_path.name}')
                count, geom_type = self.process_file_into_layer(file_path)
                if geom_type:
                    geometry_types.add(geom_type)
                self.processed_files.append((file_path.name, count))
                self.total_features_imported += count
            except Exception as e:
                self.failed_files.append((file_path.name, str(e)))
                self.stdout.write(self.style.ERROR(f'  ❌ Error: {e}'))
        self.master_plan_layer.feature_count = self.total_features_imported
        self.master_plan_layer.is_processed = True
        if geometry_types:
            if 'MULTIPOLYGON' in geometry_types:
                self.master_plan_layer.geometry_type = 'MULTIPOLYGON'
            elif 'POLYGON' in geometry_types:
                self.master_plan_layer.geometry_type = 'POLYGON'
            else:
                self.master_plan_layer.geometry_type = list(geometry_types)[0]
        bbox = self.calculate_layer_bbox(self.master_plan_layer)
        if bbox:
            self.stdout.write(f'\n  📍 Layer bounding box: {bbox}')
        self.master_plan_layer.save()
        self.stdout.write(f'\n✅ Layer populated with {self.total_features_imported:,} features from {len(self.processed_files)} files')

    def _create_empty_layer(self):
        """Create empty layer structure when no files found."""
        layer_group, _ = LayerGroup.objects.get_or_create(
            city=self.city,
            slug='visakhapatnam_master_plan',
            defaults={
                'name': 'Visakhapatnam Master Plan',
                'description': 'Greater Visakhapatnam Municipal Corporation master plan',
                'category': self.categories['PLANNING'],
                'directory_path': str(self.data_dir),
                'default_color': '#FFE4B5',
                'default_stroke': '#FF8C00',
                'default_opacity': 0.7,
                'display_order': 0,
                'is_visible': True,
                'min_zoom': 8,
                'max_zoom': 18,
            }
        )
        self.master_plan_layer, _ = DataLayer.objects.get_or_create(
            city=self.city,
            slug='visakhapatnam_master_plan',
            defaults={
                'name': 'Visakhapatnam Master Plan',
                'description': 'Visakhapatnam Master Plan - Land Use Categories',
                'category': self.categories['PLANNING'],
                'layer_group': layer_group,
                'file_format': 'GEOJSON',
                'file_path': str(self.data_dir),
                'is_directory': True,
                'file_pattern': '*.geojson',
                'source_files': [],
                'geometry_type': 'POLYGON',
                'categorization_method': 'FILENAME',
                'is_processed': True,
                'feature_count': 0,
                'is_true': True,
                'data_source': 'Greater Visakhapatnam Municipal Corporation',
            }
        )
        self.processed_files = []
        self.failed_files = []
        self.total_features_imported = 0

    def process_file_into_layer(self, file_path):
        """Process one GeoJSON file and add features to the layer. Returns (count, geometry_type)."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            self.stdout.write(f'  ❌ Read error: {e}')
            return 0, None
        features = data.get('features', [])
        if not features:
            self.stdout.write('  ⚠️ No features in file')
            return 0, None
        category = self.determine_category_from_filename(file_path.stem)
        first_geom_type = self.get_geometry_type(features[0])
        features_added = 0
        for idx, feature_data in enumerate(features, 1):
            try:
                geometry_data = feature_data.get('geometry')
                if not geometry_data:
                    continue
                geometry = GEOSGeometry(json.dumps(geometry_data))
                if geometry.hasz:
                    geometry = self.flatten_geometry(geometry)
                if not geometry.valid:
                    geometry = geometry.buffer(0)
                    if not geometry.valid:
                        continue
                properties = feature_data.get('properties', {})
                name = self.extract_feature_name(properties, file_path.stem, idx)
                GeoFeature.objects.create(
                    layer=self.master_plan_layer,
                    geometry=geometry,
                    name=name,
                    source_layer_name=file_path.stem,
                    zone_category=category.name,
                    zone_subcategory=file_path.stem,
                    area=self.safe_float(properties.get('Shape_Area') or properties.get('Area')),
                    shape_length=self.safe_float(properties.get('Shape_Length')),
                    shape_area=self.safe_float(properties.get('Shape_Area')),
                    objectid=self.safe_int(properties.get('OBJECTID', properties.get('objectid', idx))),
                    fid=self.safe_int(properties.get('FID', properties.get('fid', idx))),
                    properties=properties,
                    is_valid=True,
                )
                features_added += 1
            except Exception as e:
                self.stdout.write(f'    ⚠️ Feature {idx}: {e}')
                continue
        self.stdout.write(f'  ✅ Added {features_added} features from {file_path.name}')
        return features_added, first_geom_type

    def determine_category_from_filename(self, filename):
        """Map filename stem to layer category."""
        lower = filename.lower()
        if any(t in lower for t in ['boundary', 'boundaries']):
            return self.categories['BOUNDARIES']
        if any(t in lower for t in ['residential', 'housing']):
            return self.categories.get('RESIDENTIAL', self.categories['PLANNING'])
        if any(t in lower for t in ['commercial']):
            return self.categories.get('COMMERCIAL', self.categories['PLANNING'])
        if any(t in lower for t in ['industrial']):
            return self.categories.get('INDUSTRIAL', self.categories['PLANNING'])
        if any(t in lower for t in ['mixed']):
            return self.categories.get('MIXED_USE', self.categories['PLANNING'])
        return self.categories['PLANNING']

    def get_geometry_type(self, feature):
        geom = feature.get('geometry', {})
        t = geom.get('type', '').upper()
        return {'POLYGON': 'POLYGON', 'MULTIPOLYGON': 'MULTIPOLYGON', 'POINT': 'POINT',
                'LINESTRING': 'LINESTRING', 'MULTILINESTRING': 'MULTILINESTRING'}.get(t, 'POLYGON')

    def flatten_geometry(self, geometry):
        geom_dict = json.loads(geometry.geojson)
        def drop_z(c):
            return c[:2] if isinstance(c[0], (int, float)) else [drop_z(x) for x in c]
        if 'coordinates' in geom_dict:
            geom_dict['coordinates'] = drop_z(geom_dict['coordinates'])
        return GEOSGeometry(json.dumps(geom_dict))

    def extract_feature_name(self, properties, source_name, index):
        """Visakhapatnam: prefer Category, then Name/name, then source + index."""
        if properties.get('Category'):
            return str(properties['Category']).strip()
        for key in ('Name', 'name', 'Zone_Name', 'Area_Name', 'Title', 'Label'):
            if properties.get(key):
                return str(properties[key]).strip()
        return f"{source_name} - Feature {index}"

    def safe_float(self, value):
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def safe_int(self, value):
        if value is None or value == '':
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def calculate_layer_bbox(self, layer):
        try:
            from django.contrib.gis.db.models import Extent
            extent = layer.geofeature_set.aggregate(extent=Extent('geometry'))['extent']
            if extent:
                layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax = extent
                layer.save(update_fields=['bbox_xmin', 'bbox_ymin', 'bbox_xmax', 'bbox_ymax'])
                return extent
        except Exception as e:
            self.stdout.write(f'    ⚠️ Bbox: {e}')
        return None

    def create_city_layer_styles(self):
        """Create city-specific layer styles."""
        self.stdout.write('\nEnsuring city-specific layer styles exist...')
        configs = {
            'BOUNDARIES': {'fill_color': '#800080', 'stroke_color': '#4B0082', 'opacity': 0.3, 'stroke_width': 2, 'fill_pattern': 'SOLID'},
            'PLANNING': {'fill_color': '#FFE4B5', 'stroke_color': '#FF8C00', 'opacity': 0.5, 'stroke_width': 1, 'fill_pattern': 'SOLID'},
            'RESIDENTIAL': {'fill_color': '#FFB6C1', 'stroke_color': '#FF69B4', 'opacity': 0.6, 'stroke_width': 1, 'fill_pattern': 'SOLID'},
            'COMMERCIAL': {'fill_color': '#FFD700', 'stroke_color': '#FFA500', 'opacity': 0.6, 'stroke_width': 1, 'fill_pattern': 'HATCHED'},
            'INDUSTRIAL': {'fill_color': '#D2691E', 'stroke_color': '#8B4513', 'opacity': 0.6, 'stroke_width': 1, 'fill_pattern': 'CROSS_HATCHED'},
            'MIXED_USE': {'fill_color': '#9370DB', 'stroke_color': '#6B46C1', 'opacity': 0.6, 'stroke_width': 1, 'fill_pattern': 'STRIPED'},
            'UNCLASSIFIED': {'fill_color': '#CCCCCC', 'stroke_color': '#666666', 'opacity': 0.5, 'stroke_width': 1, 'fill_pattern': 'SOLID'},
        }
        for code, config in configs.items():
            if code not in self.categories:
                continue
            CityLayerStyle.objects.update_or_create(
                city=self.city,
                category=self.categories[code],
                defaults={
                    'fill_color': config['fill_color'],
                    'stroke_color': config['stroke_color'],
                    'opacity': config['opacity'],
                    'stroke_width': config['stroke_width'],
                    'fill_pattern': config['fill_pattern'],
                    'is_visible': True,
                    'min_zoom': 8,
                    'max_zoom': 18,
                }
            )
        self.stdout.write('  ✅ Styles updated')

    def create_zone_mappings(self):
        """Create zone mappings from source_layer_name."""
        self.stdout.write('\nCreating zone mappings...')
        if not getattr(self, 'master_plan_layer', None):
            return
        source_layers = self.master_plan_layer.geofeature_set.values_list('source_layer_name', flat=True).distinct()
        for source_layer in source_layers:
            if not source_layer:
                continue
            category = self.determine_category_from_filename(source_layer)
            try:
                style = CityLayerStyle.objects.get(city=self.city, category=category)
            except CityLayerStyle.DoesNotExist:
                style = CityLayerStyle.objects.create(
                    city=self.city,
                    category=category,
                    fill_color=category.default_color,
                    stroke_color=category.default_stroke,
                    opacity=category.default_opacity,
                )
            count = self.master_plan_layer.geofeature_set.filter(source_layer_name=source_layer).count()
            CityZoneMapping.objects.update_or_create(
                city=self.city,
                zone_name=source_layer,
                defaults={'category': category, 'style': style, 'feature_count': count, 'is_active': True}
            )
            self.stdout.write(f'  ✅ Updated zone mapping for "{source_layer}" ({count} features)')

    def print_summary(self):
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('📊 IMPORT SUMMARY'))
        self.stdout.write('='*60)
        self.stdout.write(f'\n📍 Location:')
        self.stdout.write(f'  State: {self.state.name} ({self.state.code})')
        self.stdout.write(f'  City: {self.city.name}')
        self.stdout.write(f'  Layer: {getattr(self.master_plan_layer, "name", "N/A")} (visakhapatnam_master_plan)')
        if hasattr(self, 'processed_files'):
            self.stdout.write(f'\n📁 Files: {len(self.processed_files)} processed, {len(getattr(self, "failed_files", []))} failed')
            for name, count in self.processed_files:
                self.stdout.write(f'    • {name}: {count:,} features')
        if hasattr(self, 'master_plan_layer') and self.master_plan_layer:
            self.stdout.write(f'\n📂 Total features: {getattr(self.master_plan_layer, "feature_count", 0):,}')
        self.stdout.write('='*60)
