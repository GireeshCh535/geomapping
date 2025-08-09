# maps/services.py - Complete enhanced service with layer-specific import functionality
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter
from django.contrib.gis.geos import GEOSGeometry
from django.core.files.storage import default_storage
from django.contrib.gis.db.models import Extent
from django.utils import timezone
from django.utils.text import slugify
import mercantile
import mapbox_vector_tile
from django.contrib.gis.geos import Polygon

from .models import (
    City, State, LayerCategory, DataLayer, GeoFeature, PLUCodeMapping, 
    CityLayerStyle, ImportJob, VectorTileLayer
)
from .config import (
    get_city_config, get_plu_mapping, map_plu_code_to_category,
    get_attribute_mapping, optimize_coordinates, detect_data_format,
    convert_esri_to_geojson_geometry, CITY_CONFIGS
)

class DataImportService:
    """
    Enhanced service for importing geographic data into the system.
    - Handles ESRI JSON, GeoJSON, and config-driven imports.
    - Supports PLU code mapping and statistics.
    - NEW: Layer-specific imports for hierarchical structure.
    - Used by management commands and API endpoints for bulk and single-file import.
    """
    def __init__(self):
        # Track the current import job and statistics
        self.import_job = None
        self.errors = []
        self.statistics = {
            'features_processed': 0,
            'features_imported': 0,
            'features_failed': 0,
            'features_skipped': 0,
            'geometry_conversions': 0,
            'coordinate_optimizations': 0,
            'plu_codes_found': Counter(),
            'categories_assigned': Counter(),
        }

    # ================================
    # EXISTING CONFIG-BASED IMPORT METHODS
    # ================================

    def import_file_with_config(self, file_path, city_slug):
        """
        Import a file using the city configuration for automatic category mapping.
        - Looks up the file in the config's file_mappings.
        - Creates the city and category if needed.
        - Calls import_file for the actual import.
        """
        config = get_city_config(city_slug)
        if not config:
            raise ValueError(f"No configuration found for city: {city_slug}")
        
        filename = os.path.basename(file_path)
        
        # Find category mapping from filename
        category_code = None
        for file_pattern, cat_code in config['file_mappings'].items():
            if filename == file_pattern:
                category_code = cat_code
                break
        
        if not category_code:
            raise ValueError(f"No category mapping found for file: {filename}")
        
        # Get or create city
        city, created = City.objects.get_or_create(
            slug=city_slug,
            defaults=config['city_info']
        )
        
        # Get category
        category = LayerCategory.objects.get(code=category_code)
        
        # Import the file
        with open(file_path, 'rb') as f:
            from django.core.files import File
            django_file = File(f)
            django_file.name = filename
            return self.import_file(django_file, city, category)

    def bulk_import_city(self, city_slug, data_directory):
        """
        Import all files for a city from a directory using the config's file_mappings.
        - Loops through all expected files and imports them.
        - Tracks results and statistics for each file.
        """
        config = get_city_config(city_slug)
        if not config:
            raise ValueError(f"No configuration found for city: {city_slug}")
        
        results = []
        data_path = Path(data_directory)
        
        if not data_path.exists():
            raise ValueError(f"Directory not found: {data_directory}")
        
        # Get or create city
        city, created = City.objects.get_or_create(
            slug=city_slug,
            defaults=config['city_info']
        )
        
        print(f"\n🏙️  Processing {city.name} data from {data_directory}")
        print(f"📁 Expected files: {len(config['file_mappings'])}")
        
        # Import each file based on mapping
        for filename, category_code in config['file_mappings'].items():
            file_path = data_path / filename
            
            if file_path.exists():
                try:
                    print(f"\n📂 Processing: {filename}")
                    print(f"🎯 Target category: {category_code}")
                    
                    # Get category
                    category = LayerCategory.objects.get(code=category_code)
                    
                    # Import file with enhanced processing
                    with open(file_path, 'rb') as f:
                        from django.core.files import File
                        django_file = File(f)
                        django_file.name = filename
                        
                        result = self.import_file(django_file, city, category)
                        result['filename'] = filename
                        result['category_code'] = category_code
                        
                        # Add processing statistics
                        if hasattr(self, 'statistics'):
                            result['statistics'] = self.statistics.copy()
                        
                        results.append(result)
                        
                        print(f"✅ Success: {result['features_imported']} features imported")
                        if result.get('plu_codes_detected'):
                            print(f"🏷️  PLU codes found: {result['plu_codes_detected']}")
                        
                except Exception as e:
                    error_result = {
                        'filename': filename,
                        'category_code': category_code,
                        'status': 'error',
                        'error': str(e),
                        'features_imported': 0
                    }
                    results.append(error_result)
                    print(f"   ❌ Error: {filename} - {e}")
            else:
                print(f"   ⚠️  File not found: {filename}")
                results.append({
                    'filename': filename,
                    'category_code': category_code,
                    'status': 'not_found',
                    'features_imported': 0
                })
        
        # Update city PLU mappings for Bangalore
        if city_slug == 'bangalore':
            self._update_plu_mappings(city, results)
        
        # Summary
        total_features = sum(r.get('features_imported', 0) for r in results)
        successful_files = len([r for r in results if r.get('status') == 'success'])
        
        print(f"\n📊 Import Summary:")
        print(f"   Total files configured: {len(config['file_mappings'])}")
        print(f"   Successfully imported: {successful_files}")
        print(f"   Total features imported: {total_features}")
        
        return {
            'city': city_slug,
            'total_files': len(config['file_mappings']),
            'imported_files': successful_files,
            'total_features': total_features,
            'results': results
        }

    def import_file(self, uploaded_file, city, category):
        """Enhanced import with ESRI support and PLU processing"""
        
        start_time = timezone.now()
        self.statistics = {
            'features_processed': 0,
            'features_imported': 0,
            'features_failed': 0,
            'features_skipped': 0,
            'geometry_conversions': 0,
            'coordinate_optimizations': 0,
            'plu_codes_found': Counter(),
            'categories_assigned': Counter(),
        }
        
        # Create import job
        self.import_job = ImportJob.objects.create(
            city=city,
            filename=uploaded_file.name,
            file_format=self._detect_format(uploaded_file.name),
            status='PROCESSING'
        )
        
        # Save uploaded file temporarily
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=uploaded_file.name)
        for chunk in uploaded_file.chunks():
            temp_file.write(chunk)
        temp_file.close()
        
        try:
            # Detect and validate format
            file_format = self._detect_format(uploaded_file.name)
            
            # Analyze file content to determine actual format
            with open(temp_file.name, 'r', encoding='utf-8') as f:
                data = json.load(f)
                detected_format = detect_data_format(data)
                
                if detected_format == 'ESRI_JSON':
                    file_format = 'ESRI_JSON'
                    print(f"🔍 Detected ESRI JSON format")
                elif detected_format == 'GEOJSON':
                    file_format = 'GEOJSON'
                    print(f"🔍 Detected standard GeoJSON format")
            
            # Create data layer
            layer = DataLayer.objects.create(
                city=city,
                category=category,
                name=self._generate_layer_name(uploaded_file.name),
                slug=self._generate_slug(Path(uploaded_file.name).stem, city),
                original_filename=uploaded_file.name,
                file_format=file_format,
                categorization_method=self._determine_categorization_method(city.slug, file_format)
            )
            
            # Import based on format
            if file_format == 'ESRI_JSON':
                features_count = self._import_esri_json(temp_file.name, layer)
            elif file_format == 'GEOJSON':
                features_count = self._import_geojson(temp_file.name, layer)
            elif file_format == 'JSON':
                # Try to handle as ESRI JSON first
                features_count = self._import_esri_json(temp_file.name, layer)
            else:
                raise ValueError(f"Unsupported format: {file_format}")
            
            # Update layer with results
            layer.feature_count = features_count
            layer.is_processed = True
            layer.primary_plu_codes = list(self.statistics['plu_codes_found'].keys())
            layer.processing_errors = "\n".join(self.errors) if self.errors else ""
            layer.save()
            
            # Calculate layer bounding box
            layer.calculate_bbox()
            
            # Update import job
            end_time = timezone.now()
            self.import_job.status = 'COMPLETED' if features_count > 0 else 'PARTIAL'
            self.import_job.features_imported = features_count
            self.import_job.features_failed = self.statistics['features_failed']
            self.import_job.completed_at = end_time
            self.import_job.processing_duration = end_time - start_time
            self.import_job.plu_codes_detected = list(self.statistics['plu_codes_found'].keys())
            self.import_job.geometry_conversions = self.statistics['geometry_conversions']
            self.import_job.coordinate_optimizations = self.statistics['coordinate_optimizations']
            self.import_job.save()
            
            return {
                'layer_id': layer.id,
                'layer_name': layer.name,
                'features_imported': features_count,
                'status': 'success',
                'file_format': file_format,
                'categorization_method': layer.categorization_method,
                'plu_codes_detected': list(self.statistics['plu_codes_found'].keys()),
                'processing_duration': str(end_time - start_time),
                'statistics': self.statistics
            }
            
        except Exception as e:
            # Update import job with error
            if self.import_job:
                self.import_job.status = 'FAILED'
                self.import_job.error_message = str(e)
                self.import_job.completed_at = timezone.now()
                self.import_job.save()
            
            raise e
        finally:
            os.unlink(temp_file.name)

    # ================================
    # NEW: LAYER-SPECIFIC IMPORT METHODS
    # ================================

    def import_geojson_to_layer(self, file_path, target_layer):
        """
        NEW: Import GeoJSON file directly to an existing DataLayer
        This is the key method for layer-specific imports
        
        Args:
            file_path (str): Path to the GeoJSON file
            target_layer (DataLayer): Existing DataLayer instance to import into
            
        Returns:
            dict: Import results with status, features_imported, etc.
        """
        try:
            print(f"🔧 Importing {file_path} to layer {target_layer.name}")
            
            # Reset statistics for this import
            self.statistics = {
                'features_processed': 0,
                'features_imported': 0,
                'features_failed': 0,
                'features_skipped': 0,
                'geometry_conversions': 0,
                'coordinate_optimizations': 0,
                'plu_codes_found': Counter(),
                'categories_assigned': Counter(),
            }
            self.errors = []
            
            # Create import job for tracking
            self.import_job = ImportJob.objects.create(
                city=target_layer.city,
                filename=os.path.basename(file_path),
                file_path=file_path,
                file_format='GEOJSON',
                category_mapped=target_layer.category.code,
                status='PROCESSING'
            )
            
            # Import the GeoJSON data
            features_count = self._import_geojson(file_path, target_layer)
            
            # Update target layer
            target_layer.feature_count += features_count  # Add to existing count
            target_layer.is_processed = True
            target_layer.save()
            
            # Update import job
            self.import_job.status = 'COMPLETED' if features_count > 0 else 'PARTIAL'
            self.import_job.features_imported = features_count
            self.import_job.features_failed = self.statistics['features_failed']
            self.import_job.completed_at = timezone.now()
            self.import_job.save()
            
            return {
                'status': 'success',
                'features_imported': features_count,
                'features_failed': self.statistics['features_failed'],
                'layer_id': target_layer.id,
                'layer_name': target_layer.name,
                'statistics': self.statistics
            }
            
        except Exception as e:
            # Update import job with error
            if self.import_job:
                self.import_job.status = 'FAILED'
                self.import_job.error_message = str(e)
                self.import_job.completed_at = timezone.now()
                self.import_job.save()
            
            return {
                'status': 'error',
                'error': str(e),
                'features_imported': 0
            }

    def import_layer_directory(self, city, layer_name, layer_dir_path, category_override=None):
        """
        NEW: Import all GeoJSON files from a layer directory into a single DataLayer
        
        Args:
            city (City): City instance
            layer_name (str): Name for the layer (e.g., "Master plan - HMDA")
            layer_dir_path (str): Path to directory containing GeoJSON files
            category_override (str): Optional category code override
            
        Returns:
            dict: Results with layer info and import statistics
        """
        layer_dir = Path(layer_dir_path)
        if not layer_dir.exists():
            raise FileNotFoundError(f"Layer directory not found: {layer_dir_path}")
        
        # Find all GeoJSON files
        geojson_files = list(layer_dir.glob('*.geojson')) + list(layer_dir.glob('*.json'))
        
        if not geojson_files:
            raise ValueError(f"No GeoJSON files found in {layer_dir_path}")
        
        print(f"📁 Found {len(geojson_files)} GeoJSON files for layer '{layer_name}'")
        
        # Determine category
        if category_override:
            try:
                category = LayerCategory.objects.get(code=category_override.upper())
            except LayerCategory.DoesNotExist:
                category = self._auto_detect_category(layer_name)
        else:
            category = self._auto_detect_category(layer_name)
        
        # Create or get DataLayer
        layer_slug = slugify(layer_name)
        layer, created = DataLayer.objects.get_or_create(
            city=city,
            slug=layer_slug,
            defaults={
                'name': layer_name,
                'category': category,
                'description': f"Combined layer for {layer_name}",
                'file_format': 'GEOJSON',
                'categorization_method': 'MANUAL',
                'is_processed': False,
                'file_path': str(layer_dir)
            }
        )
        
        if not created:
            print(f"📋 Using existing layer: {layer.name}")
            # Clear existing features if re-importing
            existing_count = layer.geofeature_set.count()
            if existing_count > 0:
                print(f"🗑️  Removing {existing_count} existing features")
                layer.geofeature_set.all().delete()
                layer.feature_count = 0
                layer.save()
        else:
            print(f"📋 Created new layer: {layer.name}")
        
        # Import all files into this layer
        total_features = 0
        successful_files = 0
        failed_files = []
        
        for file_path in geojson_files:
            try:
                print(f"📄 Importing: {file_path.name}")
                
                result = self.import_geojson_to_layer(str(file_path), layer)
                
                if result['status'] == 'success':
                    features_imported = result['features_imported']
                    total_features += features_imported
                    successful_files += 1
                    print(f"   ✅ Imported {features_imported} features")
                else:
                    failed_files.append({
                        'file': file_path.name,
                        'error': result.get('error', 'Unknown error')
                    })
                    print(f"   ❌ Failed: {result.get('error')}")
                    
            except Exception as e:
                failed_files.append({
                    'file': file_path.name,
                    'error': str(e)
                })
                print(f"   ❌ Error: {e}")
        
        # Calculate layer bounding box from all features
        layer.calculate_bbox()
        
        return {
            'status': 'completed' if successful_files > 0 else 'failed',
            'layer_id': layer.id,
            'layer_name': layer_name,
            'layer_slug': layer_slug,
            'category': category.name,
            'total_files': len(geojson_files),
            'successful_files': successful_files,
            'failed_files': failed_files,
            'total_features': total_features,
            'city': city.slug
        }

    def import_multiple_layers(self, city, base_data_dir, layer_mappings, force=False):
        """
        NEW: Import multiple layers for a city from the hierarchical directory structure
        
        Args:
            city (City): City instance
            base_data_dir (str): Base data directory path (e.g., "data/telangana/hyderabad")  
            layer_mappings (list): List of layer definitions from Excel
            force (bool): Force re-import existing layers
            
        Returns:
            dict: Overall import results
        """
        results = {
            'city': city.slug,
            'total_layers': len(layer_mappings),
            'successful_layers': 0,
            'failed_layers': 0,
            'total_features': 0,
            'layer_results': []
        }
        
        base_dir = Path(base_data_dir)
        if not base_dir.exists():
            raise FileNotFoundError(f"Base data directory not found: {base_data_dir}")
        
        print(f"🏙️  Importing {len(layer_mappings)} layers for {city.name}")
        
        for i, layer_info in enumerate(layer_mappings, 1):
            layer_name = layer_info['name']
            layer_slug = layer_info['slug']
            
            print(f"\n📋 [{i}/{len(layer_mappings)}] Processing layer: {layer_name}")
            
            # Expected layer directory path
            layer_dir_path = base_dir / layer_slug
            
            if not layer_dir_path.exists():
                print(f"   ⚠️  Layer directory not found: {layer_dir_path}")
                results['layer_results'].append({
                    'layer_name': layer_name,
                    'status': 'directory_not_found',
                    'features_imported': 0
                })
                results['failed_layers'] += 1
                continue
            
            try:
                # Import this layer
                layer_result = self.import_layer_directory(
                    city, layer_name, str(layer_dir_path)
                )
                
                if layer_result['status'] == 'completed':
                    results['successful_layers'] += 1
                    results['total_features'] += layer_result['total_features']
                    print(f"   ✅ Layer completed: {layer_result['total_features']} features")
                else:
                    results['failed_layers'] += 1
                    print(f"   ❌ Layer failed")
                
                results['layer_results'].append(layer_result)
                
            except Exception as e:
                print(f"   ❌ Error importing layer {layer_name}: {e}")
                results['failed_layers'] += 1
                results['layer_results'].append({
                    'layer_name': layer_name,
                    'status': 'error',
                    'error': str(e),
                    'features_imported': 0
                })
        
        return results

    # ================================
    # FORMAT-SPECIFIC IMPORT METHODS
    # ================================

    def _import_esri_json(self, file_path, layer):
        """Enhanced import ESRI JSON file with smart PLU categorization"""
        print(f"🔧 Processing ESRI JSON format with enhanced PLU mapping")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        features = []
        city_config = get_city_config(layer.city.slug)
        coordinate_precision = city_config.get('coordinate_precision', 8)
        
        # Process features
        feature_list = data.get('features', [])
        total_features = len(feature_list)
        print(f"📊 Processing {total_features} features")
        
        for i, feature_data in enumerate(feature_list):
            try:
                self.statistics['features_processed'] += 1
                
                # Progress indicator
                if i % 100 == 0:
                    print(f"   Progress: {i}/{total_features} ({i/total_features*100:.1f}%)")
                
                attrs = feature_data.get('attributes', {})
                esri_geometry = feature_data.get('geometry', {})
                
                # Convert ESRI geometry to GeoJSON
                geojson_geom = convert_esri_to_geojson_geometry(esri_geometry)
                if not geojson_geom:
                    self.statistics['features_skipped'] += 1
                    continue
                
                # Optimize coordinate precision
                if 'coordinates' in geojson_geom:
                    geojson_geom['coordinates'] = optimize_coordinates(
                        geojson_geom['coordinates'], 
                        coordinate_precision
                    )
                    self.statistics['coordinate_optimizations'] += 1
                
                self.statistics['geometry_conversions'] += 1
                geom = GEOSGeometry(json.dumps(geojson_geom))
                
                # Enhanced PLU processing for different cities
                if layer.city.slug == 'bengaluru':
                    processed_attrs = self._process_bangalore_plu_attributes(attrs, layer)
                elif layer.city.slug == 'warangal':
                    processed_attrs = self._process_warangal_attributes(attrs, layer)
                elif layer.city.slug == 'delhi':
                    processed_attrs = self._process_delhi_attributes(attrs, layer)
                elif layer.city.slug == 'gurgaon':
                    processed_attrs = self._process_gurgaon_attributes(attrs, layer)
                elif layer.city.slug == 'jaipur':
                    processed_attrs = self._process_jaipur_attributes(attrs, layer)
                else:
                    processed_attrs = self._process_standard_attributes(attrs, layer)
                
                # Create feature with ONLY valid model fields
                feature = GeoFeature(
                    layer=layer,
                    geometry=geom,
                    **processed_attrs
                )
                
                features.append(feature)
                self.statistics['features_imported'] += 1
                
            except Exception as e:
                self.statistics['features_failed'] += 1
                error_msg = f"Feature {i}: {str(e)}"
                self.errors.append(error_msg)
                print(f"   ⚠️  {error_msg}")
                continue
        
        # Bulk create features
        if features:
            print(f"💾 Saving {len(features)} features to database...")
            GeoFeature.objects.bulk_create(features, batch_size=1000)
        
        print(f"✅ ESRI Import completed: {len(features)} features saved")
        print(f"📊 Category distribution: {dict(self.statistics['categories_assigned'])}")
        
        return len(features)

    def _import_geojson(self, file_path, layer):
        """Import standard GeoJSON file (Vizag/Amaravati format) - ENHANCED"""
        print(f"🔧 Processing standard GeoJSON format for {layer.city.slug}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        features = []
        city_config = get_city_config(layer.city.slug)
        coordinate_precision = city_config.get('coordinate_precision', 8)
        
        feature_list = data.get('features', [])
        total_features = len(feature_list)
        print(f"📊 Processing {total_features} features")
        
        for i, feature_data in enumerate(feature_list):
            try:
                self.statistics['features_processed'] += 1
                
                if i % 100 == 0:
                    print(f"   Progress: {i}/{total_features} ({i/total_features*100:.1f}%)")
                
                properties = feature_data.get('properties', {})
                geometry_data = feature_data.get('geometry', {})
                
                # Optimize coordinate precision
                if 'coordinates' in geometry_data:
                    geometry_data['coordinates'] = optimize_coordinates(
                        geometry_data['coordinates'], 
                        coordinate_precision
                    )
                    self.statistics['coordinate_optimizations'] += 1
                
                geom = GEOSGeometry(json.dumps(geometry_data))
                
                # Process attributes with enhanced category mapping
                processed_attrs = self._process_standard_attributes(properties, layer)
                
                # Create feature with ONLY valid model fields
                feature = GeoFeature(
                    layer=layer,
                    geometry=geom,
                    **processed_attrs
                )
                
                features.append(feature)
                self.statistics['features_imported'] += 1
                
            except Exception as e:
                self.statistics['features_failed'] += 1
                error_msg = f"Feature {i}: {str(e)}"
                self.errors.append(error_msg)
                print(f"   ⚠️  {error_msg}")
                continue
        
        # Bulk create features
        if features:
            print(f"💾 Saving {len(features)} features to database...")
            GeoFeature.objects.bulk_create(features, batch_size=1000)
            
            # Update layer categorization method at the LAYER level (not individual features)
            if layer.city.slug == 'vizag':
                layer.categorization_method = 'ATTRIBUTE'  # Vizag uses Category field
            else:
                layer.categorization_method = 'FILENAME'   # Others use filename
            layer.save()
        
        print(f"✅ GeoJSON Import completed: {len(features)} features saved")
        print(f"📊 Category distribution: {dict(self.statistics['categories_assigned'])}")
        
        return len(features)

    # ================================
    # CITY-SPECIFIC ATTRIBUTE PROCESSING
    # ================================

    def _process_bangalore_plu_attributes(self, esri_attrs, layer):
        """Process Bangalore-specific ESRI attributes with enhanced PLU mapping"""
        
        # Extract PLU codes
        plu_primary = str(esri_attrs.get('PLU', '')).strip()
        plu_secondary_1 = str(esri_attrs.get('PLU_NAME', '')).strip()
        plu_secondary_2 = str(esri_attrs.get('PLU_prop_l', '')).strip()
        
        # Map PLU to category using enhanced mapping
        derived_category = map_plu_code_to_category(plu_primary, 'bangalore')
        
        # Track PLU codes
        if plu_primary:
            self.statistics['plu_codes_found'][plu_primary] += 1
        
        # Track category assignment
        self.statistics['categories_assigned'][derived_category] += 1
        
        result = {
            # Basic identification
            'name': esri_attrs.get('PLU_NAME', '').strip(),
            'description': esri_attrs.get('PLU_prop_l', '').strip(),
            'source_layer_name': layer.name,
            
            # PLU fields
            'plu_primary_code': plu_primary,
            'plu_secondary_1': plu_secondary_1,
            'plu_secondary_2': plu_secondary_2,
            'plu_proposed_use': esri_attrs.get('PLU_prop_l', '').strip(),
            'plu_development_code': esri_attrs.get('PLU_F_PD_C'),
            'plu_authority': esri_attrs.get('PLU_BDA', '').strip(),
            'plu_ktc_code': esri_attrs.get('PLU_Tp_KTC', '').strip(),
            'plu_survey_code': esri_attrs.get('PLU_Tp_sur', '').strip(),
            
            # Derived fields
            'land_use_code': str(esri_attrs.get('PLU_Cd', '')),
            'derived_category': derived_category,
            'land_use_type': derived_category,
            
            # Measurements
            'source_area_value': esri_attrs.get('SHAPE.STArea()'),
            'source_length_value': esri_attrs.get('Shape_Leng'),
            'source_perimeter_value': esri_attrs.get('SHAPE.STLength()'),
            
            # Store all original attributes
            'source_attributes': esri_attrs,
            
            # Processing metadata
            'original_precision': 15,
            'geometry_simplified': True,
        }
        
        return result

    def _process_standard_attributes(self, attrs, layer):
        """Process attributes for non-Bangalore cities (ENHANCED for Amaravati and Vizag)"""
        
        city_config = get_city_config(layer.city.slug)
        attribute_mapping = city_config.get('attribute_mappings', {}) if city_config else {}
        category_mappings = city_config.get('category_mappings', {}) if city_config else {}
        
        # Map attributes using configuration
        mapped_attrs = {}
        for source_field, target_field in attribute_mapping.items():
            if source_field in attrs:
                mapped_attrs[target_field] = attrs[source_field]
        
        # Determine category - ENHANCED FOR BOTH VIZAG AND AMARAVATI
        derived_category = layer.category.code  # Default fallback
        categorization_method = 'FILENAME'  # Default method
        
        # ✅ AMARAVATI: Use 'symbology' field for categorization
        if layer.city.slug == 'amaravati' and 'symbology' in attrs:
            symbology_value = attrs['symbology']
            if symbology_value in category_mappings:
                derived_category = category_mappings[symbology_value]
                categorization_method = 'ATTRIBUTE'
                print(f"   ✅ Amaravati: Mapped symbology '{symbology_value}' → {derived_category}")
                
                # Track category mapping for statistics
                self.statistics['categories_assigned'][derived_category] += 1
            else:
                print(f"   ⚠️  Amaravati: Unknown symbology '{symbology_value}', using filename category")
        
        # ✅ VIZAG: Use 'Category' field for categorization (existing logic)
        elif layer.city.slug == 'vizag' and 'Category' in attrs:
            category_value = attrs['Category']
            if category_value in category_mappings:
                derived_category = category_mappings[category_value]
                categorization_method = 'ATTRIBUTE'
                print(f"   ✅ Vizag: Mapped category '{category_value}' → {derived_category}")
                
                # Track category mapping for statistics
                self.statistics['categories_assigned'][derived_category] += 1
            else:
                print(f"   ⚠️  Vizag: Unknown category '{category_value}', using filename category")
        
        # Build standardized result
        processed = {
            # Basic identification
            'name': attrs.get('Name', attrs.get('NAME', '')),
            'description': attrs.get('Description', ''),
            'source_layer_name': layer.name,
            
            # Land use fields
            'land_use_name': attrs.get('symbology', attrs.get('Category', '')),
            'land_use_type': derived_category,
            'derived_category': derived_category,
            
            # Area and geometry fields
            'area_value': attrs.get('AREA', attrs.get('Area', 0)),
            'area_unit': 'square_meters',
            'perimeter_value': attrs.get('PERIMETER', attrs.get('Perimeter', 0)),
            
            # Administrative fields
            'state': layer.city.state,
            'district': attrs.get('District', ''),
            'mandal': attrs.get('Mandal', ''),
            'village': attrs.get('Village', ''),
            'authority_name': '',
            
            # Source data fields
            'source_fid': attrs.get('fid', attrs.get('FID', attrs.get('OBJECTID'))),
            'source_object_id': attrs.get('OBJECTID', attrs.get('objectid')),
            'source_area_value': attrs.get('AREA', attrs.get('Area', 0)),
            'source_length_value': 0,
            'source_perimeter_value': attrs.get('PERIMETER', attrs.get('Perimeter', 0)),
            
            # Additional metadata
            'source_attributes': attrs,
        }
        
        # Add mapped attributes
        processed.update(mapped_attrs)
        
        return processed

    def _process_delhi_attributes(self, properties, layer):
        """Process Delhi GeoJSON attributes - Simple NAME field mapping"""
        
        # Extract NAME field  
        name_field = properties.get('NAME', '').strip()
        
        # Map to category using Delhi-specific logic
        from .config import map_name_to_category_delhi
        derived_category = map_name_to_category_delhi(name_field)
        
        # If mapping failed, use layer's default category
        if derived_category == 'UNCLASSIFIED' and layer.category:
            derived_category = layer.category.code
        
        # Process Delhi GeoJSON properties (very simple structure)
        processed = {
            # Basic identification
            'name': name_field,
            'description': '',
            'source_layer_name': layer.name,
            
            # Delhi-specific fields
            'land_use_name': name_field,
            'land_use_type': derived_category,
            'derived_category': derived_category,
            
            # Area and geometry fields
            'area_value': properties.get('AREA_SQMTR', 0),
            'area_unit': 'square_meters', 
            'perimeter_value': 0,
            
            # Administrative fields (empty for Delhi)
            'state': 'Delhi',
            'district': '',
            'mandal': '',
            'village': '',
            'authority_name': '',
            
            # PLU fields (empty for Delhi as it doesn't use PLU codes)
            'plu_primary_code': '',
            'plu_secondary_1': '',
            'plu_secondary_2': '',
            'plu_authority': '',
            'land_use_code': name_field,
            
            # Source data fields
            'source_fid': properties.get('fid'),
            'source_object_id': properties.get('fid'),
            'source_area_value': properties.get('AREA_SQMTR', 0),
            'source_length_value': 0,
            'source_perimeter_value': 0,
            
            # Delhi-specific fields
            'original_color': properties.get('COLOR', ''),
            
            # Additional metadata
            'source_attributes': properties,
        }
        
        return processed

    def _process_warangal_attributes(self, attrs, layer):
        """Process Warangal-specific attributes"""
        
        # Get PLU field - Warangal uses 'PLU' field
        plu_field = attrs.get('PLU', '').strip()
        
        # Map PLU to category
        derived_category = map_plu_code_to_category(plu_field, 'warangal')
        
        if plu_field:
            self.statistics['plu_codes_found'][plu_field] += 1
        
        self.statistics['categories_assigned'][derived_category] += 1
        
        return {
            'name': attrs.get('PLU_NAME', '').strip(),
            'description': '',
            'source_layer_name': layer.name,
            'plu_primary_code': plu_field,
            'land_use_type': derived_category,
            'derived_category': derived_category,
            'source_area_value': attrs.get('Shape_Leng'),
            'source_attributes': attrs,
        }

    def _process_gurgaon_attributes(self, attrs, layer):
        """Process Gurgaon-specific attributes"""
        
        # Gurgaon uses 'classtext' field
        classtext = attrs.get('classtext', '').strip()
        
        # Extract category from classtext (e.g., "100 Residential" -> "RESIDENTIAL")
        derived_category = 'UNCLASSIFIED'
        if 'residential' in classtext.lower():
            derived_category = 'RESIDENTIAL'
        elif 'commercial' in classtext.lower():
            derived_category = 'COMMERCIAL'
        elif 'industrial' in classtext.lower():
            derived_category = 'INDUSTRIAL'
        # Add more mappings as needed
        
        self.statistics['categories_assigned'][derived_category] += 1
        
        return {
            'name': classtext,
            'description': '',
            'source_layer_name': layer.name,
            'land_use_type': derived_category,
            'derived_category': derived_category,
            'land_use_code': classtext,
            'source_attributes': attrs,
        }

    def _process_jaipur_attributes(self, attrs, layer):
        """Process Jaipur-specific attributes"""
        
        # Use layer category as default
        derived_category = layer.category.code
        
        return {
            'name': attrs.get('Name', '').strip(),
            'description': '',
            'source_layer_name': layer.name,
            'land_use_type': derived_category,
            'derived_category': derived_category,
            'source_attributes': attrs,
        }

    # ================================
    # UTILITY METHODS
    # ================================

    def _auto_detect_category(self, layer_name):
        """Auto-detect LayerCategory based on layer name"""
        layer_lower = layer_name.lower()
        
        category_mappings = {
            'master plan': 'MIXED_USE',
            'road': 'TRANSPORT', 
            'roads': 'TRANSPORT',
            'lake': 'WATER_BODIES',
            'lakes': 'WATER_BODIES',
            'parks': 'PARKS_GREEN',
            'green': 'PARKS_GREEN',
            'residential': 'RESIDENTIAL',
            'commercial': 'COMMERCIAL',
            'industrial': 'INDUSTRIAL',
            'railway': 'TRANSPORT',
            'mmts': 'TRANSPORT',
            'metro': 'TRANSPORT',
            'utilities': 'UTILITIES',
            'government': 'GOVERNMENT',
            'public': 'PUBLIC',
            'agriculture': 'AGRICULTURAL',
            'forest': 'PROTECTED',
            'boundary': 'SPECIAL',
            'survey': 'SPECIAL',
            'rrr': 'SPECIAL',
            'workspace': 'COMMERCIAL',
            'future': 'SPECIAL'
        }
        
        for keyword, category_code in category_mappings.items():
            if keyword in layer_lower:
                try:
                    return LayerCategory.objects.get(code=category_code)
                except LayerCategory.DoesNotExist:
                    continue
        
        # Create unclassified category if not exists
        category, created = LayerCategory.objects.get_or_create(
            code='UNCLASSIFIED',
            defaults={
                'name': 'Unclassified',
                'description': 'Unclassified layers'
            }
        )
        return category

    def _update_plu_mappings(self, city, import_results):
        """Update PLU code mappings based on import results"""
        print(f"\n🏷️  Updating PLU mappings for {city.name}")
        
        plu_mapping = get_plu_mapping(city.slug)
        
        for result in import_results:
            if result.get('status') == 'success' and result.get('plu_codes_detected'):
                for plu_code in result['plu_codes_detected']:
                    if plu_code in plu_mapping:
                        plu_info = plu_mapping[plu_code]
                        category = LayerCategory.objects.get(code=plu_info['category'])
                        
                        mapping, created = PLUCodeMapping.objects.get_or_create(
                            city=city,
                            plu_code=plu_code,
                            defaults={
                                'mapped_category': category,
                                'plu_description': plu_info['description'],
                                'secondary_codes': plu_info.get('secondary_codes', []),
                                'feature_count': 0
                            }
                        )
                        
                        # Update feature count
                        feature_count = GeoFeature.objects.filter(
                            layer__city=city,
                            plu_primary_code=plu_code
                        ).count()
                        
                        mapping.feature_count = feature_count
                        mapping.last_used = timezone.now()
                        mapping.save()

    def _generate_layer_name(self, filename):
        """Generate a human-readable layer name from filename"""
        name = Path(filename).stem
        name = name.replace('_', ' ').replace('-', ' ')
        return name.title()

    def _generate_slug(self, filename_stem, city):
        """Generate unique slug for layer"""
        base_slug = slugify(filename_stem)
        slug = base_slug
        counter = 1
        
        while DataLayer.objects.filter(city=city, slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug

    def _detect_format(self, filename):
        """Detect file format from filename"""
        ext = Path(filename).suffix.lower()
        
        if ext in ['.geojson']:
            return 'GEOJSON'
        elif ext in ['.json']:
            return 'JSON'
        elif ext in ['.shp']:
            return 'SHP'
        else:
            return 'JSON'  # Default

    def _determine_categorization_method(self, city_slug, file_format):
        """Determine categorization method based on city and format"""
        if city_slug in ['bangalore']:
            return 'PLU_CODE'
        elif city_slug in ['vizag', 'amaravati']:
            return 'ATTRIBUTE'
        else:
            return 'FILENAME'

class VectorTileService:
    """CORRECTED - Vector tile generation service"""
    
    def generate_tile(self, layer, z, x, y):
        """Generate MVT tile for a single layer - FIXED VERSION"""
        
        # Get tile bounds
        tile_bounds = self._get_tile_bounds(z, x, y)
        
        # Query features in tile with optimized geometry
        features = GeoFeature.objects.filter(
            layer=layer,
            geometry__intersects=tile_bounds,
            is_valid=True
        ).select_related('layer', 'layer__category')
        
        if not features.exists():
            print(f"🗺️  No features found for tile {z}/{x}/{y}")
            return None
        
        print(f"🗺️  Generating tile {z}/{x}/{y} with {features.count()} features for layer {layer.slug}")
        
        # CRITICAL FIX: Use layer.slug as the layer name in MVT
        return self._features_to_mvt(features, layer.slug, z, x, y)
    
    def generate_combined_tile(self, layers, z, x, y):
        """Generate MVT tile with multiple layers - FIXED VERSION"""
        
        tile_bounds = self._get_tile_bounds(z, x, y)
        
        # Collect features from all layers
        layer_data = {}
        total_features = 0
        
        for layer in layers:
            features = GeoFeature.objects.filter(
                layer=layer,
                geometry__intersects=tile_bounds,
                is_valid=True
            ).select_related('layer', 'layer__category')
            
            if features.exists():
                layer_data[layer.slug] = features  # Use layer.slug as key
                total_features += features.count()
        
        if not layer_data:
            return None
        
        print(f"🗺️  Generating combined tile {z}/{x}/{y} with {total_features} features from {len(layer_data)} layers")
        
        return self._layers_to_mvt(layer_data, z, x, y)
    
    def _get_tile_bounds(self, z, x, y):
        """Get tile bounding box as Polygon"""
        bounds = mercantile.bounds(x, y, z)
        return Polygon.from_bbox([
            bounds.west, bounds.south, 
            bounds.east, bounds.north
        ])
    
    def _features_to_mvt(self, features, layer_name, z, x, y):
        """
        Convert features to MVT format with proper coordinate transformation
        """
        
        if not features:
            return None
            
        try:
            mvt_features = []
            
            for feature in features:
                try:
                    # Simplify geometry based on zoom level
                    simplified_geom = feature.geometry
                    
                    # Convert to GeoJSON dict
                    geom_dict = json.loads(simplified_geom.geojson)
                    
                    # Prepare properties
                    properties = {
                        'name': feature.name or '',
                        'category': feature.layer.category.name if feature.layer.category else 'Unknown',
                        'land_use': feature.land_use_type or '',
                        'plu_code': feature.plu_primary_code or '',
                        'area': float(feature.calculated_area) if feature.calculated_area else 0.0,
                        'id': feature.id
                    }
                    
                    mvt_feature = {
                        'geometry': geom_dict,
                        'properties': properties
                    }
                    
                    mvt_features.append(mvt_feature)
                    
                except Exception as e:
                    print(f"Skipping feature {feature.id} due to processing error: {e}")
                    continue
            
            if not mvt_features:
                return None
            
            # Format for mapbox-vector-tile==2.0.1
            layer_data = [{
                'name': layer_name,
                'features': mvt_features,
                'version': 2,
                'extent': 4096
            }]
            
            # Get tile bounds for coordinate transformation
            import mercantile
            bounds = mercantile.bounds(x, y, z)
            
            # Transform coordinates from WGS84 to tile coordinates (0-4096)
            transformed_features = []
            for feature in mvt_features:
                transformed_feature = feature.copy()
                geom = feature['geometry']
                
                if geom['type'] == 'Polygon' and 'coordinates' in geom:
                    transformed_coords = []
                    for ring in geom['coordinates']:
                        transformed_ring = []
                        for coord in ring:
                            # Transform from WGS84 to tile coordinates
                            tile_x = int((coord[0] - bounds.west) / (bounds.east - bounds.west) * 4096)
                            tile_y = int((bounds.north - coord[1]) / (bounds.north - bounds.south) * 4096)
                            transformed_ring.append([tile_x, tile_y])
                        transformed_coords.append(transformed_ring)
                    
                    transformed_feature['geometry']['coordinates'] = transformed_coords
                
                transformed_features.append(transformed_feature)
            
            # Update layer data with transformed features
            layer_data[0]['features'] = transformed_features
            
            # Encode the MVT
            mvt_tile = mapbox_vector_tile.encode(layer_data)
            
            print(f"✅ MVT encoded successfully: {len(mvt_features)} features, {len(mvt_tile)} bytes, layer_name='{layer_name}'")
            return mvt_tile
            
        except Exception as e:
            print(f"❌ MVT encoding failed for {layer_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _layers_to_mvt(self, layer_data, z, x, y):
        """
        CORRECTED - Convert multiple layers of features to a single MVT
        """
        if not layer_data:
            return None
            
        try:
            # Prepare list of layer dictionaries for encoding
            layers_list = []
            
            first_layer = True
            for layer_slug, features in layer_data.items():
                mvt_features = []
                try:
                    for i, feature in enumerate(features):
                        try:
                            simplified_geom = feature.geometry.simplify(
                                tolerance=self._get_simplify_tolerance(z), 
                                preserve_topology=True
                            )
                            geom_dict = json.loads(simplified_geom.geojson)
                            import mercantile
                            bounds = mercantile.bounds(x, y, z)
                            if first_layer and i == 0:
                                try:
                                    print(f"[DEBUG] TILE BOUNDS for {layer_slug} at z={z}, x={x}, y={y}: west={bounds.west}, south={bounds.south}, east={bounds.east}, north={bounds.north}")
                                    if geom_dict['type'] == 'Polygon' and geom_dict['coordinates']:
                                        sample_pt = geom_dict['coordinates'][0][0]
                                        print(f"[DEBUG] Sample input WGS84 coordinate: {sample_pt}")
                                        tile_pt = self._wgs84_to_tile_coords(sample_pt, bounds)
                                        print(f"[DEBUG] Sample output tile coordinate: {tile_pt}")
                                except Exception as e:
                                    print(f"[DEBUG] Exception during debug print: {e}")
                            transformed_geom = self._transform_geometry_to_tile(geom_dict, bounds)
                            if first_layer and i == 0:
                                print(f"[DEBUG] COMBINED TILE: First feature transformed geometry for {layer_slug}: {json.dumps(transformed_geom)[:500]}")
                            properties = {
                                'name': feature.name or '',
                                'category': feature.layer.category.name if feature.layer.category else 'Unknown',
                                'land_use': feature.land_use_type or '',
                                'plu_code': feature.plu_primary_code or '',
                                'area': float(feature.calculated_area) if feature.calculated_area else 0.0,
                                'id': feature.id,
                                'layer': layer_slug
                            }
                            mvt_features.append({
                                'geometry': transformed_geom,
                                'properties': properties
                            })
                        except Exception as e:
                            print(f"[DEBUG] ❌ Skipping feature {feature.id}: {e}")
                            continue
                    first_layer = False
                    if mvt_features:
                        layers_list.append({
                            'name': layer_slug,
                            'features': mvt_features
                        })
                except Exception as e:
                    print(f"[DEBUG] Exception in layer {layer_slug}: {e}")
                    continue
            
            if not layers_list:
                return None
            
            # Encode the list of layers
            mvt_tile = mapbox_vector_tile.encode(layers_list)
            
            total_features = sum(len(layer['features']) for layer in layers_list)
            layer_names = [layer['name'] for layer in layers_list]
            print(f"✅ Combined MVT encoded: {len(layers_list)} layers ({layer_names}), {total_features} features, {len(mvt_tile)} bytes")
            return mvt_tile
            
        except Exception as e:
            print(f"❌ Combined MVT encoding failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_simplify_tolerance(self, zoom):
        """Get simplify tolerance based on zoom level"""
        if zoom <= 8:
            return 0.001   # Low zoom - more simplification
        elif zoom <= 12:
            return 0.0005  # Medium zoom
        else:
            return 0.0001  # High zoom - less simplification
    
    def _get_layer_bounds(self, layer):
        """Get bounding box for layer"""
        if all([layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax]):
            return {
                'west': layer.bbox_xmin,
                'south': layer.bbox_ymin,
                'east': layer.bbox_xmax,
                'north': layer.bbox_ymax
            }
        
        # Calculate bounds from features if not cached
        extent = GeoFeature.objects.filter(
            layer=layer, 
            is_valid=True
        ).aggregate(extent=Extent('geometry'))['extent']
        
        if extent:
            return {
                'west': extent[0],
                'south': extent[1], 
                'east': extent[2],
                'north': extent[3]
            }
        
        return None
    
    def generate_layer_tiles(self, layer, min_zoom=6, max_zoom=14):
        """Generate all tiles for a layer within zoom range"""
        
        bounds = self._get_layer_bounds(layer)
        if not bounds:
            return {'error': 'No bounds available for layer'}
        
        total_tiles = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            # Get tiles that intersect with layer bounds
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'],
                zoom
            ))
            
            print(f"Generating {len(tiles)} tiles for zoom {zoom}")
            
            for tile in tiles:
                mvt_data = self.generate_tile(layer, tile.z, tile.x, tile.y)
                if mvt_data:
                    total_tiles += 1
        
        print(f"Generated {total_tiles} tiles for layer {layer.slug}")
        
        return {
            'layer_id': layer.id,
            'tiles_generated': total_tiles,
            'status': 'success',
            'zoom_range': {'min': min_zoom, 'max': max_zoom},
            'bounds': bounds
        }   

    def _wgs84_to_tile_coords(self, coords, bounds):
        # Helper to convert [lng, lat] to tile coordinates (0-4096) with correct Y inversion
        lng, lat = coords[0], coords[1]
        tile_x = int((lng - bounds.west) / (bounds.east - bounds.west) * 4096)
        tile_y = int((bounds.north - lat) / (bounds.north - bounds.south) * 4096)
        return [tile_x, tile_y]

    def _transform_geometry_to_tile(self, geom_dict, bounds):
        """
        Helper to transform a single geometry (GeoJSON dict) from WGS84 to tile coordinates.
        This is needed because the coordinate transformation for MVT is different from
        the standard GeoJSON to tile transformation.
        """
        if geom_dict['type'] == 'Polygon' and 'coordinates' in geom_dict:
            transformed_coords = []
            for ring in geom_dict['coordinates']:
                transformed_ring = []
                for coord in ring:
                    # Transform from WGS84 to tile coordinates
                    tile_x = int((coord[0] - bounds.west) / (bounds.east - bounds.west) * 4096)
                    tile_y = int((bounds.north - coord[1]) / (bounds.north - bounds.south) * 4096)
                    transformed_ring.append([tile_x, tile_y])
                transformed_coords.append(transformed_ring)
            geom_dict['coordinates'] = transformed_coords
        elif geom_dict['type'] == 'MultiPolygon' and 'coordinates' in geom_dict:
            transformed_coords = []
            for polygon in geom_dict['coordinates']:
                transformed_polygon = []
                for ring in polygon:
                    transformed_ring = []
                    for coord in ring:
                        tile_x = int((coord[0] - bounds.west) / (bounds.east - bounds.west) * 4096)
                        tile_y = int((bounds.north - coord[1]) / (bounds.north - bounds.south) * 4096)
                        transformed_ring.append([tile_x, tile_y])
                    transformed_polygon.append(transformed_ring)
                transformed_coords.append(transformed_polygon)
            geom_dict['coordinates'] = transformed_coords
        return geom_dict 