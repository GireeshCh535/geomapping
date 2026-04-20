#!/usr/bin/env python3
"""
Django management command to insert a shapefile-based layer into an existing city.
Mirrors insert_masterplan_layer but reads .shp files via geopandas instead of GeoJSON/JSON.

Usage:
    python manage.py insert_shapefile_layer \
        --city-slug "daman" \
        --layer-name "Daman Boundary" \
        --layer-slug "daman_boundary" \
        --data-dir "data/daman/Boundary_File" \
        --authority "Daman Development Authority" \
        --delete-existing
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
    help = 'Insert a shapefile-based layer into an existing city'

    def add_arguments(self, parser):
        parser.add_argument(
            '--city-slug',
            type=str,
            required=True,
            help='Existing city slug (e.g., "daman")',
        )
        parser.add_argument(
            '--layer-name',
            type=str,
            required=True,
            help='Layer display name (e.g., "Daman Boundary")',
        )
        parser.add_argument(
            '--layer-slug',
            type=str,
            required=True,
            help='Layer slug for URL/database (e.g., "daman_boundary")',
        )
        parser.add_argument(
            '--data-dir',
            type=str,
            required=True,
            help='Directory containing the .shp file(s)',
        )
        parser.add_argument(
            '--authority',
            type=str,
            help='Development authority name (defaults to city name + "Development Authority")',
        )
        parser.add_argument(
            '--min-zoom',
            type=int,
            default=8,
            help='Minimum zoom level (default: 8)',
        )
        parser.add_argument(
            '--max-zoom',
            type=int,
            default=18,
            help='Maximum zoom level (default: 18)',
        )
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Delete existing layer data before inserting new data',
        )
        parser.add_argument(
            '--exclude',
            type=str,
            default='',
            help='Comma-separated substrings: exclude shapefiles whose name contains any of these',
        )

    def handle(self, *args, **options):
        self.city_slug = options['city_slug']
        self.layer_name = options['layer_name']
        self.layer_slug = options['layer_slug']
        self.data_dir = Path(options['data_dir'])
        self.authority = options.get('authority')
        self.min_zoom = options['min_zoom']
        self.max_zoom = options['max_zoom']
        exclude_str = (options.get('exclude') or '').strip()
        self.exclude_substrings = [s.strip() for s in exclude_str.split(',') if s.strip()]

        self.stdout.write(self.style.SUCCESS(f'Starting {self.layer_name} Shapefile Insertion'))

        if not self.data_dir.exists():
            raise CommandError(f'Data directory does not exist: {self.data_dir}')

        try:
            import geopandas as gpd
        except ImportError:
            raise CommandError('geopandas is required: pip install geopandas')

        self._gpd = gpd

        try:
            with transaction.atomic():
                self.get_city()
                self.setup_layer_categories()

                if options['delete_existing']:
                    self.delete_existing_layer()

                self.create_and_populate_layer()
                self.create_city_layer_styles()
                self.create_zone_mappings()
                self.print_summary()

                self.stdout.write(self.style.SUCCESS(f'✅ {self.layer_name} Insertion Completed Successfully!'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error during insertion: {str(e)}'))
            import traceback
            traceback.print_exc()
            raise CommandError(f'Insertion failed: {str(e)}')

    def get_city(self):
        self.stdout.write(f'Looking up city: {self.city_slug}...')
        try:
            self.city = City.objects.get(slug=self.city_slug)
            self.stdout.write(f'  ✅ Found city: {self.city.name}')

            if self.city.state_ref:
                self.state = self.city.state_ref
                self.stdout.write(f'  ✅ Found state: {self.state.name}')
            else:
                raise CommandError(f'City {self.city.name} does not have an associated state')

            if not self.authority:
                self.authority = f"{self.city.name} Development Authority"

        except City.DoesNotExist:
            raise CommandError(f'City with slug "{self.city_slug}" does not exist. Please create the city first.')

    def setup_layer_categories(self):
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
                    'is_active': True
                }
            )
            self.categories[code] = category
            if created:
                self.stdout.write(f'  ✅ Created category: {name}')

    def delete_existing_layer(self):
        self.stdout.write(f'Deleting existing {self.layer_name} data...')
        try:
            layer = DataLayer.objects.get(city=self.city, slug=self.layer_slug)
            feature_count = layer.geofeature_set.count()
            layer.delete()
            self.stdout.write(f'  ✅ Deleted layer with {feature_count} features')
        except DataLayer.DoesNotExist:
            self.stdout.write(f'  No existing {self.layer_name} layer found')

        LayerGroup.objects.filter(city=self.city, slug=self.layer_slug).delete()

    def create_and_populate_layer(self):
        self.stdout.write(f'\nCreating and populating {self.layer_name} layer...')

        all_files = list(self.data_dir.glob('*.shp')) + list(self.data_dir.rglob('*.shp'))
        # Deduplicate (rglob includes top-level)
        seen = set()
        unique_files = []
        for f in all_files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)
        all_files = unique_files

        if self.exclude_substrings:
            original_count = len(all_files)
            all_files = [f for f in all_files if not any(exc in f.name for exc in self.exclude_substrings)]
            excluded = original_count - len(all_files)
            if excluded:
                self.stdout.write(f'  Excluded {excluded} file(s) matching --exclude')

        layer_group, _ = LayerGroup.objects.get_or_create(
            city=self.city,
            slug=self.layer_slug,
            defaults={
                'name': self.layer_name,
                'description': f'{self.authority} data for {self.layer_name}',
                'category': self.categories['PLANNING'],
                'directory_path': str(self.data_dir),
                'default_color': '#FFE4B5',
                'default_stroke': '#FF8C00',
                'default_opacity': 0.7,
                'display_order': 0,
                'is_visible': True,
                'min_zoom': self.min_zoom,
                'max_zoom': self.max_zoom
            }
        )

        if not all_files:
            self.stdout.write(f'  ⚠️ No .shp files found in {self.data_dir}')
            self.layer, _ = DataLayer.objects.get_or_create(
                city=self.city,
                slug=self.layer_slug,
                defaults={
                    'name': self.layer_name,
                    'description': f'{self.layer_name} shapefile layer',
                    'category': self.categories['PLANNING'],
                    'layer_group': layer_group,
                    'file_format': 'SHP',
                    'file_path': str(self.data_dir),
                    'is_directory': True,
                    'file_pattern': '*.shp',
                    'source_files': [],
                    'geometry_type': 'POLYGON',
                    'categorization_method': 'FILENAME',
                    'is_processed': True,
                    'feature_count': 0,
                    'is_true': True,
                    'data_source': self.authority,
                }
            )
            self.processed_files = []
            self.failed_files = []
            self.total_features_imported = 0
            self.stdout.write('  ✅ Created empty layer structure')
            return

        self.stdout.write(f'📁 Found {len(all_files)} shapefile(s) to process:')
        for f in all_files:
            self.stdout.write(f'  - {f.name}')

        source_file_names = [f.name for f in all_files]

        self.layer, created = DataLayer.objects.get_or_create(
            city=self.city,
            slug=self.layer_slug,
            defaults={
                'name': self.layer_name,
                'description': f'{self.layer_name} including all boundaries and land use zones',
                'category': self.categories['PLANNING'],
                'layer_group': layer_group,
                'file_format': 'SHP',
                'file_path': str(self.data_dir),
                'is_directory': True,
                'file_pattern': '*.shp',
                'source_files': source_file_names,
                'geometry_type': 'POLYGON',
                'categorization_method': 'FILENAME',
                'is_processed': False,
                'feature_count': 0,
                'is_true': True,
                'data_source': self.authority,
            }
        )

        if created:
            self.stdout.write(f'  ✅ Created layer: {self.layer.name}')
        else:
            self.stdout.write(f'  ✅ Found existing layer: {self.layer.name}')
            self.layer.source_files = source_file_names
            self.layer.save()
            deleted_count = self.layer.geofeature_set.all().delete()[0]
            if deleted_count > 0:
                self.stdout.write(f'    Deleted {deleted_count} existing features')

        self.processed_files = []
        self.failed_files = []
        self.total_features_imported = 0
        geometry_types = set()

        for file_path in all_files:
            try:
                self.stdout.write(f'\n📄 Processing: {file_path.name}')
                features_count, geom_type = self.process_shapefile_into_layer(file_path)
                if geom_type:
                    geometry_types.add(geom_type)
                self.processed_files.append((file_path.name, features_count))
                self.total_features_imported += features_count
            except Exception as e:
                self.failed_files.append((file_path.name, str(e)))
                self.stdout.write(self.style.ERROR(f'  ❌ Error processing {file_path.name}: {str(e)}'))
                continue

        self.layer.feature_count = self.total_features_imported
        self.layer.is_processed = True

        if geometry_types:
            if 'MULTIPOLYGON' in geometry_types:
                self.layer.geometry_type = 'MULTIPOLYGON'
            elif 'POLYGON' in geometry_types:
                self.layer.geometry_type = 'POLYGON'
            else:
                self.layer.geometry_type = list(geometry_types)[0]

        bbox = self.calculate_layer_bbox(self.layer)
        if bbox:
            self.stdout.write(f'\n  📍 Layer bounding box: {bbox}')

        self.layer.save()

        try:
            from maps.listing_layer_enrichment_service import refresh_layer_point_count_cache
            refresh_layer_point_count_cache(layer_ids=[self.layer.id])
            self.stdout.write('  Refreshed layer point count cache')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Layer point count cache refresh failed: {e}'))

        self.stdout.write(f'\n✅ Layer populated with {self.total_features_imported:,} features from {len(self.processed_files)} file(s)')

    def process_shapefile_into_layer(self, file_path):
        """Read a shapefile with geopandas and insert its features into the layer."""
        gpd = self._gpd

        gdf = gpd.read_file(file_path)

        if gdf.empty:
            self.stdout.write(f'  ⚠️ No features found in {file_path.name}')
            return 0, None

        # Reproject to WGS84 if needed
        if gdf.crs is None:
            self.stdout.write(f'  ⚠️ No CRS found in {file_path.name}, assuming EPSG:4326')
            gdf = gdf.set_crs(epsg=4326)
        elif gdf.crs.to_epsg() != 4326:
            self.stdout.write(f'  🌐 Reprojecting from {gdf.crs} to EPSG:4326')
            gdf = gdf.to_crs(epsg=4326)

        category = self.determine_category_from_filename(file_path.stem)

        # Detect dominant geometry type from first valid row
        first_geom_type = None
        for geom in gdf.geometry:
            if geom is not None:
                first_geom_type = self._map_geom_type(geom.geom_type)
                break

        features_added = 0

        for idx, row in enumerate(gdf.itertuples(index=False), 1):
            try:
                raw_geom = row.geometry
                if raw_geom is None or raw_geom.is_empty:
                    continue

                # Convert shapely geometry → GEOSGeometry via GeoJSON
                geometry = GEOSGeometry(json.dumps(raw_geom.__geo_interface__), srid=4326)

                # Flatten 3D to 2D if needed
                if geometry.hasz:
                    geometry = self.flatten_geometry(geometry)

                if not geometry.valid:
                    geometry = geometry.buffer(0)
                    if not geometry.valid:
                        self.stdout.write(f'    ⚠️ Invalid geometry at feature {idx}, skipping')
                        continue

                # Build properties dict from all non-geometry fields, sanitizing NaN/Inf
                properties = self.sanitize_properties({
                    col: (val if not hasattr(val, 'item') else val.item())
                    for col, val in row._asdict().items()
                    if col != 'geometry'
                })

                area_value = None
                for key in ['Area', 'AREA', 'area', 'Shape_Area', 'SHAPE_AREA', 'shape_area']:
                    if key in properties:
                        area_value = self.safe_float(properties[key])
                        if area_value is not None:
                            break
                if area_value is None:
                    try:
                        area_value = geometry.area
                    except Exception:
                        area_value = None

                shape_length_value = None
                for key in ['Shape_Length', 'SHAPE_LENGTH', 'shape_length', 'Length', 'LENGTH']:
                    if key in properties:
                        shape_length_value = self.safe_float(properties[key])
                        if shape_length_value is not None:
                            break

                shape_area_value = None
                for key in ['Shape_Area', 'SHAPE_AREA', 'shape_area', 'Area', 'AREA']:
                    if key in properties:
                        shape_area_value = self.safe_float(properties[key])
                        if shape_area_value is not None:
                            break

                GeoFeature.objects.create(
                    layer=self.layer,
                    geometry=geometry,
                    name=self.extract_feature_name(properties, file_path.stem, idx),
                    source_layer_name=file_path.stem,
                    zone_category=category.name,
                    zone_subcategory=file_path.stem,
                    area=area_value,
                    shape_length=shape_length_value,
                    shape_area=shape_area_value,
                    objectid=self.safe_int(properties.get('OBJECTID', properties.get('objectid', idx))),
                    fid=self.safe_int(properties.get('FID', properties.get('fid', idx))),
                    properties=properties,
                    is_valid=True
                )

                features_added += 1

            except Exception as e:
                self.stdout.write(f'    ⚠️ Error processing feature {idx}: {str(e)}')
                continue

        self.stdout.write(f'  ✅ Added {features_added} features from {file_path.name}')
        return features_added, first_geom_type

    def _map_geom_type(self, shapely_type):
        mapping = {
            'Polygon': 'POLYGON',
            'MultiPolygon': 'MULTIPOLYGON',
            'Point': 'POINT',
            'MultiPoint': 'POINT',
            'LineString': 'LINESTRING',
            'MultiLineString': 'MULTILINESTRING',
        }
        return mapping.get(shapely_type, 'POLYGON')

    def determine_category_from_filename(self, filename):
        filename_lower = filename.lower()
        if any(term in filename_lower for term in ['boundary', 'boundaries', 'cma_boundary', 'city_boundary']):
            return self.categories['BOUNDARIES']
        elif any(term in filename_lower for term in ['residential', 'housing']):
            return self.categories.get('RESIDENTIAL', self.categories['PLANNING'])
        elif any(term in filename_lower for term in ['commercial', 'business']):
            return self.categories.get('COMMERCIAL', self.categories['PLANNING'])
        elif any(term in filename_lower for term in ['industrial']):
            return self.categories.get('INDUSTRIAL', self.categories['PLANNING'])
        elif any(term in filename_lower for term in ['mixed']):
            return self.categories.get('MIXED_USE', self.categories['PLANNING'])
        else:
            return self.categories['PLANNING']

    def flatten_geometry(self, geometry):
        geom_dict = json.loads(geometry.geojson)

        def remove_z(coords):
            if isinstance(coords[0], (int, float)):
                return coords[:2]
            return [remove_z(c) for c in coords]

        if 'coordinates' in geom_dict:
            geom_dict['coordinates'] = remove_z(geom_dict['coordinates'])
        return GEOSGeometry(json.dumps(geom_dict))

    def extract_feature_name(self, properties, source_name, index):
        name_fields = ['Name', 'name', 'NAME', 'City_Name', 'Zone_Name',
                       'Area_Name', 'Title', 'Label', 'Description']
        for field in name_fields:
            if field in properties and properties[field]:
                return str(properties[field])
        return f"{source_name} - Feature {index}"

    def sanitize_properties(self, props):
        """Replace NaN/Inf values (invalid JSON) with None."""
        import math
        clean = {}
        for k, v in props.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                clean[k] = None
            else:
                clean[k] = v
        return clean

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
            self.stdout.write(f'    ⚠️ Could not calculate bbox: {str(e)}')
        return None

    def create_city_layer_styles(self):
        self.stdout.write('\nEnsuring city-specific layer styles exist...')

        style_configs = {
            'BOUNDARIES': {'fill_color': '#800080', 'stroke_color': '#4B0082', 'opacity': 0.3, 'stroke_width': 2, 'fill_pattern': 'SOLID'},
            'PLANNING':   {'fill_color': '#FFE4B5', 'stroke_color': '#FF8C00', 'opacity': 0.5, 'stroke_width': 1, 'fill_pattern': 'SOLID'},
            'RESIDENTIAL':{'fill_color': '#FFB6C1', 'stroke_color': '#FF69B4', 'opacity': 0.6, 'stroke_width': 1, 'fill_pattern': 'SOLID'},
            'COMMERCIAL': {'fill_color': '#FFD700', 'stroke_color': '#FFA500', 'opacity': 0.6, 'stroke_width': 1, 'fill_pattern': 'HATCHED'},
            'INDUSTRIAL': {'fill_color': '#D2691E', 'stroke_color': '#8B4513', 'opacity': 0.6, 'stroke_width': 1, 'fill_pattern': 'CROSS_HATCHED'},
            'MIXED_USE':  {'fill_color': '#9370DB', 'stroke_color': '#6B46C1', 'opacity': 0.6, 'stroke_width': 1, 'fill_pattern': 'STRIPED'},
            'UNCLASSIFIED':{'fill_color': '#CCCCCC', 'stroke_color': '#666666', 'opacity': 0.5, 'stroke_width': 1, 'fill_pattern': 'SOLID'},
        }

        for category_code, config in style_configs.items():
            if category_code in self.categories:
                style, created = CityLayerStyle.objects.get_or_create(
                    city=self.city,
                    category=self.categories[category_code],
                    defaults={
                        'fill_color': config['fill_color'],
                        'stroke_color': config['stroke_color'],
                        'opacity': config['opacity'],
                        'stroke_width': config['stroke_width'],
                        'fill_pattern': config['fill_pattern'],
                        'is_visible': True,
                        'min_zoom': self.min_zoom,
                        'max_zoom': self.max_zoom
                    }
                )
                if created:
                    self.stdout.write(f'  ✅ Created style for {category_code}')

    def create_zone_mappings(self):
        self.stdout.write('\nCreating zone mappings...')

        if not hasattr(self, 'layer') or not self.layer:
            self.stdout.write('  No layer found, skipping zone mappings')
            return

        source_layers = self.layer.geofeature_set.values_list('source_layer_name', flat=True).distinct()

        if not source_layers:
            self.stdout.write('  No features found, skipping zone mappings')
            return

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
                    opacity=category.default_opacity
                )

            feature_count = self.layer.geofeature_set.filter(source_layer_name=source_layer).count()

            zone_mapping, created = CityZoneMapping.objects.update_or_create(
                city=self.city,
                zone_name=f"{self.layer_slug}_{source_layer}",
                defaults={
                    'category': category,
                    'style': style,
                    'feature_count': feature_count,
                    'is_active': True
                }
            )

            action = 'Created' if created else 'Updated'
            self.stdout.write(f'  ✅ {action} zone mapping for "{source_layer}" ({feature_count} features)')

    def print_summary(self):
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('📊 IMPORT SUMMARY'))
        self.stdout.write('=' * 60)

        self.stdout.write(f'\n📍 Location:')
        self.stdout.write(f'  State: {self.state.name} ({self.state.code})')
        self.stdout.write(f'  City: {self.city.name}')
        self.stdout.write(f'  Layer: {self.layer_name} ({self.layer_slug})')

        if hasattr(self, 'processed_files'):
            self.stdout.write(f'\n📁 Files Processed:')
            self.stdout.write(f'  Successfully processed: {len(self.processed_files)}')
            self.stdout.write(f'  Failed: {len(self.failed_files) if hasattr(self, "failed_files") else 0}')

            if self.processed_files:
                self.stdout.write(f'\n  Details:')
                for filename, features_count in self.processed_files:
                    self.stdout.write(f'    • {filename}: {features_count:,} features')

            if hasattr(self, 'failed_files') and self.failed_files:
                self.stdout.write(f'\n  Failed files:')
                for filename, error in self.failed_files:
                    self.stdout.write(f'    • {filename}: {error}')

        if hasattr(self, 'layer'):
            self.stdout.write(f'\n📂 Layer Info:')
            self.stdout.write(f'  Name: {self.layer.name}')
            self.stdout.write(f'  Total features: {self.layer.feature_count:,}')
            self.stdout.write(f'  Geometry type: {self.layer.geometry_type}')

            from django.db.models import Count
            source_stats = self.layer.geofeature_set.values('source_layer_name').annotate(
                count=Count('id')
            ).order_by('source_layer_name')

            if source_stats:
                self.stdout.write(f'\n🗺️ Features by Source File:')
                for stat in source_stats:
                    self.stdout.write(f'  • {stat["source_layer_name"]}: {stat["count"]:,} features')

        self.stdout.write('\n' + '=' * 60)
