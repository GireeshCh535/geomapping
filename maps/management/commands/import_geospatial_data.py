# maps/management/commands/import_geospatial_data.py
"""
Import command that combines multiple files into single layers
Each layer group (master_plan, highways, etc.) becomes ONE layer with ALL features combined

Example:
- master_plan (16 files) → bengaluru_master_plan_2015 (1 layer with all features)
- highways (8 files) → bengaluru_highways (1 layer with all features)
- metro (lines + stations) → hyderabad_metro (1 layer with all features)
- future-city (FCDA Boundary) → hyderabad_future_city (1 layer with styling)
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.gis.geos import Polygon, MultiPolygon, LineString, MultiLineString, Point
from django.utils.text import slugify
from django.utils import timezone
from maps.models import (
    State, City, LayerCategory, DataLayer, 
    GeoFeature, LayerGroup, CityLayerStyle
)
from maps.config import DATA_IMPORT_CONFIG, LAYER_CATEGORIES, detect_data_format
import json
import os
from pathlib import Path
import traceback

class Command(BaseCommand):
    help = 'Import geospatial data - combines multiple files into single layers with custom styling'
    
    def add_arguments(self, parser):
        parser.add_argument('--data-dir', required=True, help='Base data directory')
        parser.add_argument('--state', help='State slug (e.g., karnataka)')
        parser.add_argument('--city', help='City slug (e.g., bengaluru)')
        parser.add_argument('--layer-group', help='Specific layer group (e.g., master-plan, highways)')
        parser.add_argument('--force', action='store_true', help='Force re-import')
        parser.add_argument('--dry-run', action='store_true', help='Test without saving')
        parser.add_argument('--verbose', action='store_true', help='Verbose output')
        
    def handle(self, *args, **options):
        data_dir = Path(options['data_dir'])
        
        if not data_dir.exists():
            self.stdout.write(self.style.ERROR(f"❌ Data directory not found: {data_dir}"))
            return
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🚀 GEOSPATIAL DATA IMPORT (COMBINED LAYERS)'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        self.stats = {
            'states': 0,
            'cities': 0,
            'layers': 0,
            'features': 0,
            'files_processed': 0,
            'errors': []
        }
        
        try:
            with transaction.atomic():
                self._process_import(data_dir, options)
                
                if options['dry_run']:
                    self.stdout.write(self.style.WARNING("\n🔄 DRY RUN - Rolling back"))
                    raise Exception("Dry run complete")
                
                self._print_summary()
                
        except Exception as e:
            if "Dry run complete" not in str(e):
                self.stdout.write(self.style.ERROR(f"\n❌ Import failed: {e}"))
                if options['verbose']:
                    self.stdout.write(traceback.format_exc())
            else:
                self._print_summary()
    
    def _process_import(self, data_dir, options):
        """Main import process"""
        
        states_config = DATA_IMPORT_CONFIG.get('states', {})
        
        if options['state']:
            if options['state'] not in states_config:
                raise ValueError(f"State '{options['state']}' not in configuration")
            states_to_process = {options['state']: states_config[options['state']]}
        else:
            states_to_process = states_config
        
        for state_slug, state_config in states_to_process.items():
            self._process_state(state_slug, state_config, data_dir, options)
    
    def _process_state(self, state_slug, state_config, data_dir, options):
        """Process a single state"""
        
        self.stdout.write(f"\n📦 State: {state_config['name']} ({state_slug})")
        
        # Get or create state
        state, created = State.objects.get_or_create(
            slug=state_slug,
            defaults={
                'name': state_config['name'],
                'code': state_config['code'],
                'is_active': True
            }
        )
        
        if created:
            self.stats['states'] += 1
            self.stdout.write(f"  ✅ Created state: {state.name}")
        else:
            self.stdout.write(f"  ✓ Using existing state: {state.name}")
        
        # Process cities
        cities_config = state_config.get('cities', {})
        
        if options['city']:
            city_slug = options['city']
            # Handle aliases
            city_aliases = {'vizag': 'visakhapatnam', 'bangalore': 'bengaluru'}
            if city_slug in city_aliases:
                city_slug = city_aliases[city_slug]
            
            if city_slug not in cities_config:
                self.stdout.write(self.style.ERROR(f"  ❌ City '{city_slug}' not found"))
                return
            cities_to_process = {city_slug: cities_config[city_slug]}
        else:
            cities_to_process = cities_config
        
        for city_slug, city_config in cities_to_process.items():
            self._process_city(state, city_slug, city_config, data_dir, options)
    
    def _process_city(self, state, city_slug, city_config, data_dir, options):
        """Process a single city"""
        
        self.stdout.write(f"\n  🏙️  City: {city_config['name']} ({city_slug})")
        
        # Get or create city
        city, created = City.objects.get_or_create(
            slug=city_slug,
            defaults={
                'name': city_config['name'],
                'state': city_config['name'],  # Legacy field
                'state_ref': state,
                'center_lat': city_config.get('center_lat', 0),
                'center_lng': city_config.get('center_lng', 0),
                'min_zoom': 8,
                'max_zoom': 18,
                'is_active': True
            }
        )
        
        if created:
            self.stats['cities'] += 1
            self.stdout.write(f"    ✅ Created city: {city.name}")
        else:
            self.stdout.write(f"    ✓ Using existing city: {city.name}")
        
        # Process layer groups
        layer_groups = city_config.get('layer_groups', {})
        
        if options.get('layer_group'):
            group_slug = options['layer_group']
            if group_slug in layer_groups:
                group_config = layer_groups[group_slug]
                self._process_layer_group_combined(city, group_slug, group_config, data_dir, city_config, options)
            else:
                self.stdout.write(self.style.ERROR(f"    ❌ Layer group '{group_slug}' not found"))
                self.stdout.write(f"      Available: {', '.join(layer_groups.keys())}")
        else:
            for group_slug, group_config in layer_groups.items():
                self._process_layer_group_combined(city, group_slug, group_config, data_dir, city_config, options)
    
    def _process_layer_group_combined(self, city, group_slug, group_config, data_dir, city_config, options):
        """Process a layer group - combines ALL files into ONE layer with custom styling"""
        
        self.stdout.write(f"\n    📂 Processing Layer Group: {group_config['name']}")
        
        # Get data path
        files_path = data_dir / group_config['path']
        if not files_path.exists():
            self.stdout.write(self.style.ERROR(f"      ❌ Path not found: {files_path}"))
            return
        
        # Generate layer slug based on group and city
        layer_slugs = {
            'master-plan': f"{city.slug}_master_plan_2015" if city.slug == 'bengaluru' else f"{city.slug}_master_plan",
            'highways': f"{city.slug}_highways",
            'metro': f"{city.slug}_metro",
            'strr': f"{city.slug}_strr",
            'workspace': f"{city.slug}_workspaces",
            'future-city': f"{city.slug}_future_city"
        }
        
        layer_slug = layer_slugs.get(group_slug, f"{city.slug}_{group_slug.replace('-', '_')}")
        layer_name = group_config['name']
        
        # Check if layer exists
        existing_layer = DataLayer.objects.filter(city=city, slug=layer_slug).first()
        
        if existing_layer and not options['force']:
            self.stdout.write(f"      ✓ Layer already exists: {layer_name} ({existing_layer.feature_count} features)")
            return
        
        if existing_layer and options['force']:
            # Delete existing layer and its features
            GeoFeature.objects.filter(layer=existing_layer).delete()
            existing_layer.delete()
            self.stdout.write(f"      🗑️  Deleted existing layer: {layer_name}")
        
        # Determine category based on group
        category_map = {
            'master-plan': 'MIXED_USE',
            'highways': 'TRANSPORT',
            'metro': 'TRANSPORT',
            'strr': 'UNCLASSIFIED',
            'workspace': 'UNCLASSIFIED',
            'future-city': 'PLANNING'
        }
        category_code = category_map.get(group_slug, 'MIXED_USE')
        category = self._get_or_create_category(category_code)
        
        # Create the single combined layer
        layer = DataLayer.objects.create(
            city=city,
            category=category,
            name=layer_name,
            slug=layer_slug,
            description=group_config.get('description', ''),
            original_filename=f"combined_{group_slug}",
            file_format='GEOJSON',
            categorization_method='MANUAL',
            feature_count=0,
            is_processed=False
        )
        
        self.stdout.write(f"      ✅ Created layer: {layer_name} (slug: {layer_slug})")
        
        # Process all files and collect features
        all_features = []
        files = group_config.get('files', {})
        files_processed = 0
        
        for filename, file_config in files.items():
            file_path = files_path / filename
            
            if not file_path.exists():
                self.stdout.write(self.style.WARNING(f"        ⚠️  File not found: {filename}"))
                continue
            
            try:
                # Read file
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract features from this file with custom styling
                file_features = self._extract_features_with_custom_styling(
                    data, 
                    layer,
                    city_config, 
                    group_config,
                    file_config,
                    city.slug,
                    group_slug,
                    options
                )
                
                if file_features:
                    all_features.extend(file_features)
                    files_processed += 1
                    self.stdout.write(f"        ✅ {filename}: {len(file_features)} features")
                else:
                    self.stdout.write(f"        ⚠️  {filename}: No features extracted")
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"        ❌ {filename}: {e}"))
                if options['verbose']:
                    self.stdout.write(traceback.format_exc())
        
        # Bulk create all features for this layer
        if all_features:
            GeoFeature.objects.bulk_create(all_features, batch_size=500)
            layer.feature_count = len(all_features)
            layer.is_processed = True
            layer.last_processed = timezone.now()
            layer.save()
            
            self.stats['layers'] += 1
            self.stats['features'] += len(all_features)
            self.stats['files_processed'] += files_processed
            
            self.stdout.write(self.style.SUCCESS(
                f"      ✅ Combined {files_processed} files into 1 layer with {len(all_features)} total features"
            ))
        else:
            self.stdout.write(self.style.WARNING(f"      ⚠️  No features found in any files"))
            layer.delete()  # Remove empty layer
    
    def _extract_features_with_custom_styling(self, data, layer, city_config, group_config, file_config, city_slug, group_slug, options):
        """Extract features from a single file with custom styling logic"""
        
        features = []
        plu_field = city_config.get('plu_field', 'PLU')
        
        # Determine data format
        detected_format = detect_data_format(data)
        
        if detected_format == 'ESRI_JSON' and 'features' in data:
            # ESRI JSON format (Bengaluru master plan)
            for feature in data['features']:
                if not feature:
                    continue
                
                geom = feature.get('geometry')
                props = feature.get('attributes', {})
                
                if not geom or 'rings' not in geom:
                    continue
                
                try:
                    rings = geom['rings']
                    if rings and len(rings[0]) > 3:
                        polygon = Polygon(rings[0])
                        
                        # Add metadata
                        if props and plu_field in props:
                            props['_plu_code'] = str(props[plu_field])[:50]
                        props['_source_file'] = file_config.get('name', '')
                        
                        features.append(GeoFeature(
                            layer=layer,
                            geometry=polygon,
                            source_layer_name=file_config.get('name', ''),
                            zone_category=file_config.get('name', ''),
                            properties=props or {}
                        ))
                except Exception as e:
                    if options.get('verbose'):
                        self.stdout.write(f"          Error: {e}")
        
        elif detected_format == 'GEOJSON' and 'features' in data:
            # Standard GeoJSON format with custom styling
            for feature in data['features']:
                if not feature:
                    continue
                
                geom = feature.get('geometry')
                props = feature.get('properties', {})
                
                if not geom:
                    continue
                
                try:
                    geom_type = geom.get('type')
                    coords = geom.get('coordinates')
                    geometry_obj = None
                    
                    # Helper function to convert 3D coordinates to 2D
                    def convert_to_2d(coordinate_list):
                        """Convert 3D coordinates to 2D by dropping Z dimension"""
                        if not coordinate_list:
                            return coordinate_list
                        if isinstance(coordinate_list[0], (list, tuple)):
                            return [convert_to_2d(coord) for coord in coordinate_list]
                        else:
                            # Single coordinate - take only x, y
                            return coordinate_list[:2]
                    
                    if geom_type == 'Polygon' and coords:
                        try:
                            if len(coords) > 0 and len(coords[0]) > 3:
                                # Convert to 2D coordinates
                                coords_2d = convert_to_2d(coords)
                                geometry_obj = Polygon(coords_2d[0])
                        except Exception as e:
                            if options.get('verbose'):
                                self.stdout.write(f"          ⚠️  Polygon creation failed: {e}")
                    
                    elif geom_type == 'MultiPolygon' and coords:
                        try:
                            polygons = []
                            for poly_coords in coords:
                                if poly_coords and len(poly_coords) > 0 and len(poly_coords[0]) > 3:
                                    # Convert to 2D coordinates
                                    poly_coords_2d = convert_to_2d(poly_coords)
                                    polygons.append(Polygon(poly_coords_2d[0]))
                            if polygons:
                                geometry_obj = MultiPolygon(polygons)
                        except Exception as e:
                            if options.get('verbose'):
                                self.stdout.write(f"          ⚠️  MultiPolygon creation failed: {e}")
                    
                    elif geom_type == 'LineString' and coords:
                        try:
                            if len(coords) >= 2:
                                # Convert to 2D coordinates
                                coords_2d = convert_to_2d(coords)
                                geometry_obj = LineString(coords_2d)
                        except Exception as e:
                            if options.get('verbose'):
                                self.stdout.write(f"          ⚠️  LineString creation failed: {e}")
                    
                    elif geom_type == 'MultiLineString' and coords:
                        try:
                            lines = []
                            for line_coords in coords:
                                if len(line_coords) >= 2:
                                    # Convert to 2D coordinates
                                    line_coords_2d = convert_to_2d(line_coords)
                                    lines.append(LineString(line_coords_2d))
                            if lines:
                                geometry_obj = MultiLineString(lines)
                        except Exception as e:
                            if options.get('verbose'):
                                self.stdout.write(f"          ⚠️  MultiLineString creation failed: {e}")
                    
                    elif geom_type == 'Point' and coords:
                        try:
                            if len(coords) >= 2:
                                # Convert to 2D coordinates
                                coords_2d = convert_to_2d(coords)
                                geometry_obj = Point(coords_2d)
                        except Exception as e:
                            if options.get('verbose'):
                                self.stdout.write(f"          ⚠️  Point creation failed: {e}")
                    
                    if geometry_obj:
                        # Check if coordinates need transformation (Web Mercator to Geographic)
                        try:
                            # Safely extract sample coordinates for checking
                            coords_sample = None
                            if geom_type == 'Polygon' and coords and len(coords) > 0 and len(coords[0]) > 0:
                                coords_sample = coords[0][0]
                            elif geom_type == 'MultiPolygon' and coords and len(coords) > 0 and len(coords[0]) > 0 and len(coords[0][0]) > 0:
                                coords_sample = coords[0][0][0]
                            elif geom_type == 'LineString' and coords and len(coords) > 0:
                                coords_sample = coords[0]
                            elif geom_type == 'MultiLineString' and coords and len(coords) > 0 and len(coords[0]) > 0:
                                coords_sample = coords[0][0]
                            elif geom_type == 'Point' and coords and len(coords) >= 2:
                                coords_sample = coords
                            
                            # Check if coordinates are in Web Mercator (EPSG:3857) range
                            # Web Mercator X: -20037508 to 20037508, Y: -20037508 to 20037508
                            # Geographic X: -180 to 180, Y: -90 to 90
                            if coords_sample and len(coords_sample) >= 2:
                                x, y = coords_sample[0], coords_sample[1]
                                
                                # Ensure x and y are numbers, not lists
                                if isinstance(x, (list, tuple)):
                                    x = x[0] if x else 0
                                if isinstance(y, (list, tuple)):
                                    y = y[0] if y else 0
                                
                                # If coordinates are in Web Mercator range, transform to geographic
                                if abs(float(x)) > 180 or abs(float(y)) > 90:
                                    from django.contrib.gis.gdal import SpatialReference, CoordTransform
                                    from django.contrib.gis.geos import GEOSGeometry
                                    
                                    # Create coordinate transformation from Web Mercator to WGS84
                                    web_mercator = SpatialReference('EPSG:3857')
                                    wgs84 = SpatialReference('EPSG:4326')
                                    transform = CoordTransform(web_mercator, wgs84)
                                    
                                    # Transform the geometry
                                    geometry_obj.transform(transform)
                                    
                                    if options.get('verbose'):
                                        self.stdout.write(f"          🔄 Transformed coordinates from Web Mercator to WGS84")
                        except Exception as transform_error:
                            if options.get('verbose'):
                                self.stdout.write(f"          ⚠️  Coordinate transformation failed: {transform_error}")
                        
                        # Apply custom styling based on city and group
                        styled_props = self._apply_custom_styling(
                            props, file_config, city_slug, group_slug, options
                        )
                        
                        # Add metadata
                        if props and plu_field in props:
                            styled_props['_plu_code'] = str(props[plu_field])[:50]
                        styled_props['_source_file'] = file_config.get('name', '')
                        
                        features.append(GeoFeature(
                            layer=layer,
                            geometry=geometry_obj,
                            source_layer_name=file_config.get('name', ''),
                            zone_category=file_config.get('name', ''),
                            properties=styled_props or {}
                        ))
                        
                except Exception as e:
                    if options.get('verbose'):
                        self.stdout.write(f"          Error: {e}")
        
        return features
    
    def _apply_custom_styling(self, props, file_config, city_slug, group_slug, options):
        """Apply custom styling properties based on city and group"""
        
        styled_props = props.copy() if props else {}
        
        # Hyderabad Metro styling
        if city_slug == 'hyderabad' and group_slug == 'metro':
            # Check if this is a metro line feature (has linecolour field)
            if props.get('linecolour'):
                line_name = props.get('name', '').strip()
                line_color = props.get('linecolour', '').strip()
                
                # Map line colors
                metro_colors = {
                    'Green Line': '#00933D',
                    'Blue Line': '#2D6BA1',
                    'Red Line': '#E40D17',
                    'Purple Line': '#8C06ED',
                    'Orange Line': '#EF6908'
                }
                
                color_hex = metro_colors.get(line_color, '#00933D')
                
                styled_props.update({
                    'feature_type': 'metro_line',
                    'line_color': line_color,
                    'color_hex': color_hex,
                    'line_name': line_name,
                    'phase': props.get('Status', ''),
                    'station_count': props.get('noofstatio', 0),
                    'length_km': props.get('length_km', 0)
                })
                
            # Check if this is a metro station feature (has station-specific fields)
            elif props.get('Station_Name') or props.get('station_name'):
                station_name = props.get('Station_Name', props.get('station_name', props.get('name', ''))).strip()
                station_type = props.get('StationType', props.get('stationtype', '')).strip()
                
                styled_props.update({
                    'feature_type': 'metro_station',
                    'station_name': station_name,
                    'station_type': station_type or 'General Station',
                    'color_hex': '#00933D',  # Default station color
                    'line_name': props.get('Line_Name', props.get('line_name', '')),
                    'phase': props.get('Phase', props.get('Status', ''))
                })
        
        # Hyderabad Future City styling
        elif city_slug == 'hyderabad' and group_slug == 'future-city':
            # Apply Future City styling to all features in this group
            styled_props.update({
                'name': props.get('Name', 'FCDA'),
                'object_id': props.get('OBJECTID', 1),
                'shape_length': props.get('Shape_Leng', 0),
                'shape_area': props.get('Shape_Area', 0),
                'fill_color': file_config.get('color', '#7D7D7D'),
                'border_color': file_config.get('border_color', '#C3C3C3'),
                'opacity': file_config.get('opacity', 0.5),
                'type': file_config.get('type', 'boundary'),
                'original_properties': props
            })
        
        return styled_props
    
    def _get_or_create_category(self, category_code):
        """Get or create category"""
        category_info = LAYER_CATEGORIES.get(category_code, {})
        category, _ = LayerCategory.objects.get_or_create(
            code=category_code,
            defaults={
                'name': category_info.get('name', category_code),
                'description': category_info.get('description', ''),
                'default_color': category_info.get('default_color', '#CCCCCC'),
                'default_opacity': category_info.get('default_opacity', 0.8)
            }
        )
        return category
    
    def _print_summary(self):
        """Print import summary"""
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("📊 IMPORT SUMMARY"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"✅ States created: {self.stats['states']}")
        self.stdout.write(f"✅ Cities created: {self.stats['cities']}")
        self.stdout.write(f"✅ Layers created: {self.stats['layers']}")
        self.stdout.write(f"✅ Files processed: {self.stats['files_processed']}")
        self.stdout.write(f"✅ Total features imported: {self.stats['features']:,}")
        
        if self.stats['errors']:
            self.stdout.write(f"\n⚠️  Errors: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:5]:
                self.stdout.write(f"  - {error}")
        
        # Show database status
        self.stdout.write("\n📦 Database Status:")
        try:
            from maps.models import DataLayer, GeoFeature
            
            # Show specific city if processed
            if 'bengaluru' in str(self.stats):
                bengaluru_layers = DataLayer.objects.filter(city__slug='bengaluru')
                if bengaluru_layers.exists():
                    self.stdout.write(f"\n  Bengaluru Layers:")
                    for layer in bengaluru_layers:
                        self.stdout.write(f"    - {layer.name} ({layer.slug}): {layer.feature_count} features")
            
            total_layers = DataLayer.objects.count()
            total_features = GeoFeature.objects.count()
            self.stdout.write(f"\n  Total Layers in DB: {total_layers}")
            self.stdout.write(f"  Total Features in DB: {total_features:,}")
            
        except Exception as e:
            self.stdout.write(f"  Error getting stats: {e}")