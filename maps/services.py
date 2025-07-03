# services.py - Enhanced with ESRI support and PLU processing
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
import mercantile
import mapbox_vector_tile
from django.contrib.gis.geos import Polygon
from .models import GeoFeature, VectorTileLayer

from .models import (
    City, LayerCategory, DataLayer, GeoFeature, PLUCodeMapping, 
    CityLayerStyle, ImportJob
)
from .config import (
    get_city_config, get_plu_mapping, map_plu_code_to_category,
    get_attribute_mapping, optimize_coordinates, detect_data_format,
    convert_esri_to_geojson_geometry, CITY_CONFIGS
)


class DataImportService:
    """Enhanced service for importing geographic data with ESRI and PLU support"""
    
    def __init__(self):
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
    
    def import_file_with_config(self, file_path, city_slug):
        """Import file using city configuration for automatic mapping"""
        
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
        """Import all files for a city from a directory with enhanced processing"""
        
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
                    print(f"❌ Error: {filename} - {e}")
            else:
                print(f"⚠️  File not found: {filename}")
                results.append({
                    'filename': filename,
                    'category_code': category_code,
                    'status': 'not_found',
                    'features_imported': 0
                })
        
        # Update city PLU mappings
        if city_slug == 'bangalore':
            self._update_plu_mappings(city, results)
        
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
                
                # Enhanced PLU processing for Bangalore
                if layer.city.slug == 'bangalore':
                    processed_attrs = self._process_bangalore_plu_attributes(attrs, layer)
                else:
                    processed_attrs = self._process_standard_attributes(attrs, layer)
                
                # Track PLU codes
                if processed_attrs['plu_primary_code']:
                    self.statistics['plu_codes_found'][processed_attrs['plu_primary_code']] += 1
                
                self.statistics['categories_assigned'][processed_attrs['derived_category']] += 1
                
                # Create feature with enhanced data
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
            
            # Update layer categorization method
            layer.categorization_method = 'PLU_CODE' if layer.city.slug == 'bangalore' else 'FILENAME'
            layer.save()
        
        print(f"✅ Import completed: {len(features)} features saved")
        return len(features)
    
    def _process_bangalore_plu_attributes(self, esri_attrs, layer):
        """Process Bangalore ESRI attributes with enhanced PLU logic"""
        
        # Extract all PLU fields
        plu_primary = esri_attrs.get('PLU_Tp_pro', '').strip()
        plu_secondary_1 = esri_attrs.get('PLU_Tp_p_1', '').strip()
        plu_secondary_2 = esri_attrs.get('PLU_Tp_p_2', '').strip()
        plu_bda = esri_attrs.get('PLU_BDA', '').strip()
        
        # Enhanced categorization logic - priority order
        derived_category = layer.category.code  # Default fallback
        categorization_method = 'FILENAME'
        
        # Priority 1: Use PLU_BDA for specific authority mappings
        if plu_bda:
            if plu_bda == 'Eaa':
                derived_category = 'PROTECTED'
                categorization_method = 'PLU_CODE'
            elif plu_bda == 'Eac':
                derived_category = 'WATER_BODIES'
                categorization_method = 'PLU_CODE'
            elif plu_bda == 'Ef':
                derived_category = 'AGRICULTURAL'
                categorization_method = 'PLU_CODE'
            elif plu_bda == 'Ca':
                derived_category = 'RESIDENTIAL'
                categorization_method = 'PLU_CODE'
            elif plu_bda == 'Cb':
                derived_category = 'RESIDENTIAL'
                categorization_method = 'PLU_CODE'
            elif plu_bda == 'Ba':
                derived_category = 'COMMERCIAL'
                categorization_method = 'PLU_CODE'
            elif plu_bda == 'Bb':
                derived_category = 'COMMERCIAL'
                categorization_method = 'PLU_CODE'
            elif plu_bda == 'Da':
                derived_category = 'INDUSTRIAL'
                categorization_method = 'PLU_CODE'
            elif plu_bda == 'Db':
                derived_category = 'HIGH_TECH'
                categorization_method = 'PLU_CODE'
            elif plu_bda == 'Dc':
                derived_category = 'TRANSPORT'
                categorization_method = 'PLU_CODE'
            elif plu_bda == 'Ta':
                derived_category = 'TRANSPORT'
                categorization_method = 'PLU_CODE'
            elif plu_bda == 'K':
                derived_category = 'PUBLIC'
                categorization_method = 'PLU_CODE'
            elif plu_bda == 'Q':
                derived_category = 'UTILITIES'
                categorization_method = 'PLU_CODE'
            elif plu_bda == 'U':
                derived_category = 'DEFENSE'
                categorization_method = 'PLU_CODE'
            elif plu_bda == 'Eab':
                derived_category = 'DRAINS'
                categorization_method = 'PLU_CODE'
            elif plu_bda == 'F':
                derived_category = 'PARKS_GREEN'
                categorization_method = 'PLU_CODE'
        
        # Priority 2: If no specific PLU_BDA match, use primary + secondary logic
        if categorization_method == 'FILENAME' and plu_primary:
            if plu_primary == 'E':
                # E code - most complex, needs secondary analysis
                if plu_secondary_1 == 'Ea':
                    if plu_secondary_2 == 'Eaa':
                        derived_category = 'PROTECTED'
                    elif plu_secondary_2 == 'Eac':
                        derived_category = 'WATER_BODIES'
                    else:
                        derived_category = 'PROTECTED'  # Default for Ea
                elif plu_secondary_1 == 'Eb':
                    derived_category = 'AGRICULTURAL'
                elif plu_secondary_1 == 'Ke':
                    derived_category = 'PUBLIC'
                else:
                    derived_category = 'AGRICULTURAL'  # Default for E
                categorization_method = 'PLU_CODE'
            
            elif plu_primary == 'B':
                # B code - Commercial
                if plu_secondary_1 == 'Ba':
                    derived_category = 'COMMERCIAL'  # Central
                elif plu_secondary_1 == 'Bb':
                    derived_category = 'COMMERCIAL'  # Business
                else:
                    derived_category = 'COMMERCIAL'
                categorization_method = 'PLU_CODE'
            
            elif plu_primary == 'D':
                # D code - Development/Industrial/Transport
                if plu_secondary_1 == 'Da':
                    derived_category = 'INDUSTRIAL'
                elif plu_secondary_1 == 'Db':
                    derived_category = 'HIGH_TECH'
                elif plu_secondary_1 == 'Dc':
                    derived_category = 'TRANSPORT'
                else:
                    derived_category = 'INDUSTRIAL'  # Default for D
                categorization_method = 'PLU_CODE'
            
            elif plu_primary == 'C':
                # C code - Residential
                if plu_secondary_1 == 'Ca':
                    derived_category = 'RESIDENTIAL'  # Mixed
                elif plu_secondary_1 == 'Cb':
                    derived_category = 'RESIDENTIAL'  # Main
                else:
                    derived_category = 'RESIDENTIAL'
                categorization_method = 'PLU_CODE'
            
            elif plu_primary == 'M':
                # M code - Utilities
                derived_category = 'UTILITIES'
                categorization_method = 'PLU_CODE'
            
            elif plu_primary == 'F':
                # F code - Parks/Green
                derived_category = 'PARKS_GREEN'
                categorization_method = 'PLU_CODE'
            
            elif plu_primary == 'N':
                # N code - Defense
                derived_category = 'DEFENSE'
                categorization_method = 'PLU_CODE'
            
            elif plu_primary == 'S':
                # S code - Unclassified
                derived_category = 'UNCLASSIFIED'
                categorization_method = 'PLU_CODE'
            
            elif plu_primary == 'K':
                # K code - Public
                derived_category = 'PUBLIC'
                categorization_method = 'PLU_CODE'
            
            elif plu_primary == 'Q':
                # Q code - Utilities
                derived_category = 'UTILITIES'
                categorization_method = 'PLU_CODE'
            
            # Add missing codes
            elif plu_primary == 'R':
                derived_category = 'RESIDENTIAL'
                categorization_method = 'PLU_CODE'
            elif plu_primary == 'J':
                derived_category = 'UTILITIES'
                categorization_method = 'PLU_CODE'
            elif plu_primary == 'P':
                derived_category = 'PUBLIC'
                categorization_method = 'PLU_CODE'
            elif plu_primary == 'H':
                derived_category = 'TRANSPORT'
                categorization_method = 'PLU_CODE'
            elif plu_primary == 'O':
                derived_category = 'COMMERCIAL'
                categorization_method = 'PLU_CODE'
            elif plu_primary == 'G':
                derived_category = 'PARKS_GREEN'
                categorization_method = 'PLU_CODE'
            elif plu_primary == 'T':
                derived_category = 'TRANSPORT'
                categorization_method = 'PLU_CODE'
            elif plu_primary == 'I':
                derived_category = 'INDUSTRIAL'
                categorization_method = 'PLU_CODE'
        
        # Debug output
        if categorization_method == 'PLU_CODE':
            print(f"   PLU: {plu_primary}/{plu_secondary_1}/{plu_secondary_2} (BDA:{plu_bda}) → {derived_category}")
        
        # Build comprehensive attributes
        return {
            'source_fid': esri_attrs.get('fid'),
            'source_object_id': esri_attrs.get('OBJECTID'),
            
            # PLU-specific fields
            'plu_primary_code': plu_primary,
            'plu_secondary_1': plu_secondary_1,
            'plu_secondary_2': plu_secondary_2,
            'plu_proposed_use': esri_attrs.get('PLU_prop_l', '').strip(),
            'plu_development_code': esri_attrs.get('PLU_F_PD_C'),
            'plu_authority': plu_bda,
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
                print(f"   ✅ Vizag: Mapped Category '{category_value}' → {derived_category}")
                
                # Track category mapping for statistics
                self.statistics['categories_assigned'][derived_category] += 1
            else:
                print(f"   ⚠️  Vizag: Unknown category '{category_value}', using filename category")
        
        # Store city-specific fields in source_attributes
        enhanced_source_attrs = attrs.copy()
        
        # ✅ AMARAVATI-specific field handling
        if layer.city.slug == 'amaravati':
            if 'plot_code' in attrs:
                enhanced_source_attrs['plot_code'] = attrs['plot_code']
            if 'symbology' in attrs:
                enhanced_source_attrs['symbology'] = attrs['symbology']
            if 'plot_categ' in attrs:
                enhanced_source_attrs['plot_category'] = attrs['plot_categ']
            if 'township' in attrs:
                enhanced_source_attrs['township'] = attrs['township']
            if 'sector' in attrs:
                enhanced_source_attrs['sector'] = attrs['sector']
            if 'colony' in attrs:
                enhanced_source_attrs['colony'] = attrs['colony']
        
        # ✅ VIZAG-specific field handling (existing)
        elif layer.city.slug == 'vizag':
            if 'RuleID' in attrs:
                enhanced_source_attrs['rule_id'] = attrs['RuleID']
            if 'Override' in attrs:
                enhanced_source_attrs['override_value'] = attrs['Override']
        
        # Return only fields that exist in the GeoFeature model
        return {
            'source_fid': mapped_attrs.get('source_fid', attrs.get('FID')),
            'source_object_id': mapped_attrs.get('source_object_id', attrs.get('OBJECTID')),
            'name': mapped_attrs.get('name', attrs.get('plot_code', '')),  # Use plot_code as name for Amaravati
            'category_name': attrs.get('symbology', attrs.get('Category', '')),  # symbology for Amaravati, Category for Vizag
            'derived_category': derived_category,
            'land_use_type': attrs.get('symbology', attrs.get('Category', derived_category)),
            'zoning': mapped_attrs.get('zoning', ''),
            
            # Administrative info
            'district': attrs.get('DISTRICT', '').strip(),
            'mandal': attrs.get('MANDAL', '').strip(),
            'village': attrs.get('Village', attrs.get('lpsvillage', '')).strip(),
            
            # Amaravati-specific fields
            'state': 'Andhra Pradesh' if layer.city.slug in ['amaravati', 'vizag'] else '',
            
            # Measurements
            'source_area_value': mapped_attrs.get('source_area_value', attrs.get('Shape_Area', attrs.get('alloted_ex'))),
            'source_length_value': mapped_attrs.get('source_length_value', attrs.get('Shape_Length')),
            
            # Store ALL original attributes including city-specific fields
            'source_attributes': enhanced_source_attrs,
            'geometry_simplified': True,
        }
        
    def _import_geojson(self, file_path, layer):
        """Import standard GeoJSON file (Vizag/Amaravati format) - FIXED"""
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
        
        print(f"✅ Import completed: {len(features)} features saved")
        print(f"📊 Category distribution: {dict(self.statistics['categories_assigned'])}")
        
        return len(features)
    
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
                        
                        if created:
                            print(f"   ✅ Created PLU mapping: {plu_code} → {category.name}")
    
    def setup_city_styles(self, city_slug):
        """Setup city-specific styles based on configuration"""
        
        config = get_city_config(city_slug)
        if not config:
            raise ValueError(f"No configuration found for city: {city_slug}")
        
        try:
            city = City.objects.get(slug=city_slug)
        except City.DoesNotExist:
            raise ValueError(f"City not found: {city_slug}")
        
        print(f"🎨 Setting up styles for {city.name}")
        
        # Create city-specific styles
        for category_code, color in config['colors'].items():
            try:
                category = LayerCategory.objects.get(code=category_code)
                
                style, created = CityLayerStyle.objects.get_or_create(
                    city=city,
                    category=category,
                    defaults={
                        'fill_color': color,
                        'stroke_color': '#333333',
                        'opacity': 0.7,
                        'stroke_width': 1,
                        'is_visible': True
                    }
                )
                
                if not created:
                    # Update existing style
                    style.fill_color = color
                    style.save()
                    print(f"   ✅ Updated style: {category.name} → {color}")
                else:
                    print(f"   ✅ Created style: {category.name} → {color}")
                    
            except LayerCategory.DoesNotExist:
                print(f"   ⚠️  Category not found: {category_code}")
        
        print(f"✅ Style setup completed for {city_slug}")
    
    def _determine_categorization_method(self, city_slug, file_format):
        """Determine the best categorization method for a city/format"""
        if city_slug == 'bangalore' and file_format == 'ESRI_JSON':
            return 'PLU_CODE'
        return 'FILENAME'
    
    def _generate_layer_name(self, filename):
        """Generate human-readable layer name from filename"""
        name = Path(filename).stem
        # Convert underscores to spaces and title case
        name = name.replace('_', ' ').replace('.', ' ')
        return ' '.join(word.capitalize() for word in name.split())
    
    def _detect_format(self, filename):
        """Detect file format from extension"""
        ext = Path(filename).suffix.lower()
        if ext == '.json':
            return 'JSON'  # Will be refined during processing
        elif ext == '.geojson':
            return 'GEOJSON'
        else:
            raise ValueError(f"Unsupported file extension: {ext}")
    
    def _generate_slug(self, name, city):
        """Generate unique slug for layer"""
        base_slug = name.lower().replace(' ', '_').replace('-', '_')
        slug = base_slug
        counter = 1
        
        while DataLayer.objects.filter(city=city, slug=slug).exists():
            slug = f"{base_slug}_{counter}"
            counter += 1
        
        return slug

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
        CORRECTED - Convert features to MVT format
        This is the critical fix for mapbox-vector-tile==2.0.1
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
                    
                    mvt_features.append({
                        'geometry': geom_dict,
                        'properties': properties
                    })
                    
                except Exception as e:
                    print(f"Skipping feature {feature.id} due to processing error: {e}")
                    continue
            
            if not mvt_features:
                return None
            
            # CRITICAL FIX: Format for mapbox-vector-tile==2.0.1
            # It expects a LIST of layer dictionaries
            layer_data = [{
                'name': layer_name,  # This must match the source-layer in frontend
                'features': mvt_features
            }]
            
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
            
            for layer_slug, features in layer_data.items():
                mvt_features = []
                
                for feature in features:
                    try:
                        # Simplify geometry based on zoom
                        simplified_geom = feature.geometry.simplify(
                            tolerance=self._get_simplify_tolerance(z), 
                            preserve_topology=True
                        )
                        
                        # Convert to GeoJSON
                        geom_dict = json.loads(simplified_geom.geojson)
                        
                        # Prepare properties
                        properties = {
                            'name': feature.name or '',
                            'category': feature.layer.category.name if feature.layer.category else 'Unknown',
                            'land_use': feature.land_use_type or '',
                            'plu_code': feature.plu_primary_code or '',
                            'area': float(feature.calculated_area) if feature.calculated_area else 0.0,
                            'id': feature.id,
                            'layer': layer_slug  # Add layer identifier
                        }
                        
                        mvt_features.append({
                            'geometry': geom_dict,
                            'properties': properties
                        })
                        
                    except Exception as e:
                        print(f"Skipping feature {feature.id}: {e}")
                        continue
                
                if mvt_features:
                    # CRITICAL: Use layer_slug as the name
                    layers_list.append({
                        'name': layer_slug,  # This must match frontend source-layer
                        'features': mvt_features
                    })
            
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