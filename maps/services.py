import os
import sys
import json
import tempfile
import shutil
import logging
import traceback
import re
import time
import glob
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

from .models import *
from .config import *

class DataImportService:
    """
    Complete enhanced service for importing geographic data into the system.
    
    PRESERVED ORIGINAL FUNCTIONALITY:
    - Handles ESRI JSON, GeoJSON, and config-driven imports
    - Supports PLU code mapping and statistics
    - Used by management commands and API endpoints for bulk and single-file import
    - All existing methods maintained for backward compatibility
    
    NEW HIERARCHICAL FUNCTIONALITY:
    - Layer group organization (master_plan, highways, metro, workspace)
    - Hierarchical structure: State → City → Layer Groups → Individual Layers
    - Bulk layer group imports
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
            'layers_created': 0,
            'layers_updated': 0,
        }

    # ================================
    # ORIGINAL CONFIG-BASED IMPORT METHODS (PRESERVED)
    # ================================

    def import_file_with_config(self, file_path, city_slug):
        """
        ORIGINAL METHOD - Import a file using the city configuration for automatic category mapping.
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
        for file_pattern, cat_code in config.get('file_mappings', {}).items():
            if filename == file_pattern:
                category_code = cat_code
                break
        
        if not category_code:
            raise ValueError(f"No category mapping found for file: {filename}")
        
        # Get or create city
        city, created = City.objects.get_or_create(
            slug=city_slug,
            defaults=config.get('city_info', {'name': city_slug.title()})
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
        ORIGINAL METHOD - Import all files for a city from a directory using the config's file_mappings.
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
            defaults=config.get('city_info', {'name': city_slug.title()})
        )
        
        print(f"\n🏙️  Processing {city.name} data from {data_directory}")
        print(f"📁 Expected files: {len(config.get('file_mappings', {}))}")
        
        # Import each file based on mapping
        for filename, category_code in config.get('file_mappings', {}).items():
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
                        
                        print(f"✅ {filename}: {result.get('features_imported', 0)} features imported")
                        
                except Exception as e:
                    print(f"❌ {filename}: Error - {str(e)}")
                    results.append({
                        'filename': filename,
                        'success': False,
                        'error': str(e),
                        'category_code': category_code
                    })
            else:
                print(f"⚠️  {filename}: File not found")
                results.append({
                    'filename': filename,
                    'success': False,
                    'error': 'File not found',
                    'category_code': category_code
                })
        
        # Calculate summary statistics
        successful = len([r for r in results if r.get('success', False)])
        total_features = sum(r.get('features_imported', 0) for r in results)
        
        print(f"\n📊 Import Summary:")
        print(f"   Files processed: {len(results)}")
        print(f"   Successful: {successful}")
        print(f"   Total features: {total_features}")
        
        return {
            'success': successful > 0,
            'files_processed': len(results),
            'successful_files': successful,
            'total_features': total_features,
            'results': results
        }

    def import_file(self, uploaded_file, city, category):
        """
        ORIGINAL METHOD - Enhanced import with ESRI support and PLU processing
        """
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
                categorization_method=self._determine_categorization_method(city.slug, file_format),
                is_processed=False
            )
            
            print(f"📋 Created layer: {layer.name} ({layer.slug})")
            
            # Import data based on format
            if file_format == 'ESRI_JSON':
                features_imported = self._import_esri_json_data(layer, data, city.slug)
            elif file_format == 'GEOJSON':
                features_imported = self._import_geojson_data(layer, data, city.slug)
            else:
                features_imported = self._import_json_data(layer, data, city.slug)
            
            # Update layer metadata
            layer.feature_count = features_imported
            layer.is_processed = True
            layer.last_processed = timezone.now()
            
            # Calculate and store bounds
            extent = layer.geofeature_set.aggregate(extent=Extent('geometry'))['extent']
            if extent:
                layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax = extent
            
            layer.save()
            
            # Update import job
            self.import_job.status = 'COMPLETED'
            self.import_job.features_imported = features_imported
            self.import_job.completed_at = timezone.now()
            self.import_job.save()
            
            # Update PLU code mappings for Bangalore
            if city.slug == 'bengaluru':
                self._update_plu_mappings(city, self.statistics['plu_codes_found'])
            
            print(f"✅ Import completed: {features_imported} features")
            
            return {
                'success': True,
                'layer_id': layer.id,
                'layer_name': layer.name,
                'features_imported': features_imported,
                'statistics': self.statistics
            }
            
        except Exception as e:
            # Update import job with error
            if self.import_job:
                self.import_job.status = 'FAILED'
                self.import_job.error_message = str(e)
                self.import_job.save()
            
            print(f"❌ Import failed: {str(e)}")
            
            return {
                'success': False,
                'error': str(e),
                'statistics': self.statistics
            }
        
        finally:
            # Clean up temp file
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)

    # ================================
    # NEW HIERARCHICAL LAYER IMPORT METHODS
    # ================================

    def import_layer_group(self, city_slug, group_name, data_directory, force=False):
        """
        FIXED METHOD - Import all layers for a specific layer group with proper category mapping
        
        Args:
            city_slug: City slug (e.g., 'bengaluru')
            group_name: Layer group name (e.g., 'master_plan', 'highways')
            data_directory: Directory containing the layer group data
            force: Force re-import existing layers
            
        Returns:
            dict: Import results with statistics
        """
        print(f"📁 Importing layer group '{group_name}' for city '{city_slug}'")
        
        try:
            # Get city
            city = City.objects.get(slug=city_slug)
            
            # Get layer group configuration
            layer_groups_config = get_layer_groups_config(city_slug)
            if group_name not in layer_groups_config:
                raise ValueError(f"Unknown layer group: {group_name}")
            
            group_config = layer_groups_config[group_name]
            expected_layers = group_config.get('layers', {})
            
            # ✅ FIXED: Map layer group to appropriate category
            group_category_mapping = {
                'master_plan': 'MIXED_USE',      # Contains multiple land use types
                'highways': 'TRANSPORT',         # Transportation infrastructure  
                'metro': 'TRANSPORT',           # Metro/rail transport
                'strr': 'TRANSPORT',            # Ring road transport
                'workspace': 'INDUSTRIAL',       # Industrial workspaces
                'industrial': 'INDUSTRIAL',      # Alternative industrial naming
                'roads': 'TRANSPORT',           # Roads/transport
            }
            
            category_code = group_category_mapping.get(group_name, 'MIXED_USE')
            group_category = self._get_or_create_category(category_code)
            
            # ✅ FIXED: Create or get layer group with ALL required fields
            layer_group, created = LayerGroup.objects.get_or_create(
                city=city,  # ✅ REQUIRED FIELD
                slug=group_name,
                defaults={
                    'name': group_config.get('name', group_name.replace('_', ' ').title()),
                    'description': group_config.get('description', f'{group_name} layer group'),
                    'category': group_category,  # ✅ REQUIRED FIELD
                    'directory_path': data_directory,  # ✅ REQUIRED FIELD
                    'display_order': group_config.get('display_order', 1),
                    'default_color': group_config.get('color', '#666666'),
                    'default_stroke': '#333333',
                    'default_opacity': 0.7
                }
            )
            
            if created:
                print(f"📁 Created layer group: {layer_group.name} (Category: {group_category.name})")
            else:
                print(f"📁 Using existing layer group: {layer_group.name}")
            
            results = {
                'group_name': group_name,
                'city': city_slug,
                'total_expected_layers': len(expected_layers),
                'layers_processed': 0,
                'layers_imported': 0,
                'layers_failed': 0,
                'total_features': 0,
                'errors': [],
                'layer_results': []
            }
            
            # Process each expected layer
            for layer_slug, layer_config in expected_layers.items():
                print(f"  📋 Processing layer: {layer_slug}")
                
                try:
                    # Import this specific layer
                    layer_result = self.import_single_layer(
                        city=city,
                        layer_group=layer_group,
                        layer_slug=layer_slug,
                        layer_config=layer_config,
                        data_directory=data_directory,
                        force=force
                    )
                    
                    if layer_result['success']:
                        results['layers_imported'] += 1
                        results['total_features'] += layer_result.get('features_imported', 0)
                        print(f"    ✅ {layer_result['features_imported']} features imported")
                    else:
                        results['layers_failed'] += 1
                        results['errors'].append(f"{layer_slug}: {layer_result.get('error')}")
                        print(f"    ❌ {layer_result.get('error')}")
                    
                    results['layers_processed'] += 1
                    results['layer_results'].append(layer_result)
                    
                except Exception as e:
                    results['layers_failed'] += 1
                    error_msg = f"{layer_slug}: {str(e)}"
                    results['errors'].append(error_msg)
                    print(f"    ❌ Error: {e}")
            
            return results
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'group_name': group_name,
                'city': city_slug
            }

    def import_single_layer(self, city, layer_group, layer_slug, layer_config, data_directory, force=False):
        """
        Import a single layer from directory - FIXED VERSION
        
        Args:
            city: City object
            layer_group: LayerGroup object (can be None, we'll create it)
            layer_slug: Layer slug (e.g., 'Agricultural_Land')
            layer_config: Layer configuration from config.py
            data_directory: Directory containing layer data files
            force: Force re-import existing layer
            
        Returns:
            dict: Import result for this layer
        """
        try:
            # Check if layer already exists
            existing_layer = DataLayer.objects.filter(
                city=city,
                slug=layer_slug
            ).first()
            
            if existing_layer and not force:
                return {
                    'layer_slug': layer_slug,
                    'success': True,
                    'action': 'skipped',
                    'reason': 'Layer already exists',
                    'features_imported': existing_layer.feature_count
                }
            
            # Find data files for this layer
            file_pattern = layer_config.get('file_pattern', f'*{layer_slug}*.json')
            data_files = self._find_layer_files(data_directory, file_pattern, layer_slug)
            
            if not data_files:
                return {
                    'layer_slug': layer_slug,
                    'success': False,
                    'error': f'No data files found matching pattern: {file_pattern}'
                }
            
            # Get or create category for individual layer
            category_code = layer_config.get('category', 'UNCLASSIFIED')
            layer_category = self._get_or_create_category(category_code)
            
            # FIXED: Create or get layer group with ALL required fields
            if not layer_group:
                # Determine layer group name from data_directory
                group_name = os.path.basename(data_directory)
                
                # Get or create a default category for layer groups (use same as main category or create MIXED_USE)
                group_category = self._get_or_create_category('MIXED_USE')  # Layer groups can be MIXED_USE
                
                layer_group, created = LayerGroup.objects.get_or_create(
                    city=city,  # ✅ REQUIRED FIELD
                    slug=group_name,
                    defaults={
                        'name': layer_config.get('group_name', group_name.replace('_', ' ').title()),
                        'description': layer_config.get('group_description', f'{group_name} layer group'),
                        'category': group_category,  # ✅ REQUIRED FIELD  
                        'directory_path': data_directory,  # ✅ REQUIRED FIELD
                        'display_order': layer_config.get('display_order', 1),
                        'default_color': '#666666',
                        'default_stroke': '#333333',
                        'default_opacity': 0.7
                    }
                )
                
                if created:
                    print(f"📁 Created layer group: {layer_group.name}")
                else:
                    print(f"📁 Using existing layer group: {layer_group.name}")
            
            # Create or update layer
            if existing_layer:
                layer = existing_layer
                # Clear existing features if force re-import
                layer.geofeature_set.all().delete()
                action = 'updated'
                self.statistics['layers_updated'] += 1
            else:
                layer = DataLayer.objects.create(
                    city=city,
                    layer_group=layer_group,
                    slug=layer_slug,
                    name=layer_config.get('name', layer_slug.replace('_', ' ').title()),
                    category=layer_category,
                    description=layer_config.get('description', ''),
                    file_format='JSON',
                    original_filename=f'{layer_slug}.json',
                    categorization_method='MANUAL',
                    is_processed=False
                )
                action = 'created'
                self.statistics['layers_created'] += 1
            
            # Import data from all files for this layer
            total_features = 0
            for data_file in data_files:
                features_imported = self._import_layer_file(layer, data_file, city.slug)
                total_features += features_imported
            
            # Update layer metadata
            layer.feature_count = total_features
            layer.is_processed = True
            layer.last_processed = timezone.now()
            
            # Calculate bounds
            self._calculate_layer_bounds(layer)
            layer.save()
            
            # Create layer styling if configured
            self._create_layer_style(city, layer, layer_config)
            
            return {
                'layer_slug': layer_slug,
                'success': True,
                'action': action,
                'features_imported': total_features,
                'files_processed': len(data_files),
                'layer_id': layer.id
            }
            
        except Exception as e:
            return {
                'layer_slug': layer_slug,
                'success': False,
                'error': str(e)
            }

    # ================================
    # ORIGINAL CITY-SPECIFIC ATTRIBUTE PROCESSING (PRESERVED)
    # ================================

    def _process_bangalore_plu_attributes(self, esri_attrs, layer):
        """ORIGINAL METHOD - Process Bangalore-specific ESRI attributes with enhanced PLU mapping"""
        
        # Extract PLU codes
        plu_primary = str(esri_attrs.get('PLU', '')).strip()
        plu_secondary_1 = str(esri_attrs.get('PLU_NAME', '')).strip()
        plu_secondary_2 = str(esri_attrs.get('PLU_prop_l', '')).strip()
        
        # Map PLU to category using enhanced mapping
        derived_category = map_plu_code_to_category(plu_primary, 'bengaluru')
        
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

    def _process_vizag_attributes(self, attrs, layer):
        """ORIGINAL METHOD - Process Vizag-specific attributes"""
        
        # Vizag uses 'name_1' field
        name = attrs.get('name_1', '').strip()
        
        # Extract category from name (e.g., "100 Residential" -> "RESIDENTIAL")
        derived_category = 'UNCLASSIFIED'
        if 'residential' in name.lower():
            derived_category = 'RESIDENTIAL'
        elif 'commercial' in name.lower():
            derived_category = 'COMMERCIAL'
        elif 'industrial' in name.lower():
            derived_category = 'INDUSTRIAL'
        # Add more mappings as needed
        
        self.statistics['categories_assigned'][derived_category] += 1
        
        return {
            'name': name,
            'description': '',
            'source_layer_name': layer.name,
            'land_use_type': derived_category,
            'derived_category': derived_category,
            'land_use_code': name,
            'rule_id': attrs.get('RuleID'),
            'override_value': attrs.get('Override', '').strip(),
            'source_attributes': attrs,
        }

    def _process_hyderabad_attributes(self, attrs, layer):
        """ORIGINAL METHOD - Process Hyderabad-specific attributes"""
        
        # Hyderabad uses 'name' field
        name = attrs.get('name', '').strip()
        
        # Extract category from name if available
        derived_category = 'MIXED_USE'
        name_lower = name.lower()
        
        if 'residential' in name_lower:
            derived_category = 'RESIDENTIAL'
        elif 'commercial' in name_lower:
            derived_category = 'COMMERCIAL'
        elif 'industrial' in name_lower:
            derived_category = 'INDUSTRIAL'
        elif any(word in name_lower for word in ['road', 'transport']):
            derived_category = 'TRANSPORT'
        
        self.statistics['categories_assigned'][derived_category] += 1
        
        return {
            'name': name,
            'description': '',
            'source_layer_name': layer.name,
            'land_use_type': derived_category,
            'derived_category': derived_category,
            'source_attributes': attrs,
        }

    def _process_workspace_attributes(self, properties, layer):
        """ORIGINAL METHOD - Process workspace data attributes"""
        
        def safe_get(d, key, default=''):
            value = d.get(key, default)
            return str(value).strip() if value is not None else default
        
        # Extract basic info
        feature_name = safe_get(properties, 'Name', '')
        feature_type = safe_get(properties, 'Type', '')
        industry = safe_get(properties, 'Industry', '')
        
        # Build description from available fields
        description_parts = []
        if feature_type:
            description_parts.append(f"Type: {feature_type}")
        if industry:
            description_parts.append(f"Industry: {industry}")
        
        description = "; ".join(description_parts) if description_parts else ""
        
        # Map to appropriate category
        type_lower = safe_get(properties, 'Type', '').lower()
        industry_lower = safe_get(properties, 'Industry', '').lower()
        
        if 'industrial' in type_lower or 'manufacturing' in industry_lower:
            derived_category = 'INDUSTRIAL'
        elif 'commercial' in type_lower:
            derived_category = 'COMMERCIAL'  
        elif 'residential' in type_lower:
            derived_category = 'RESIDENTIAL'
        else:
            derived_category = 'INDUSTRIAL'  # Default for workspace data
        
        self.statistics['categories_assigned'][derived_category] += 1
        
        # Return ONLY the core fields that we know exist
        return {
            # Core identification fields
            'name': feature_name,                    # CharField(max_length=200, blank=True)
            'description': description,              # TextField(blank=True)
            'source_layer_name': layer.name,        # CharField(max_length=200, blank=True)
            
            # Derived category field
            'derived_category': derived_category,    # CharField(max_length=30, blank=True)
            'land_use_type': derived_category,       # CharField(max_length=100, blank=True)
            
            # Keep PLU fields empty for workspace data
            'plu_primary_code': '',                  # CharField(max_length=50, blank=True)
            'plu_secondary_1': '',                   # CharField(max_length=100, blank=True)
            'plu_secondary_2': '',                   # CharField(max_length=50, blank=True)
        }

    def _process_delhi_attributes(self, properties, layer):
        """ORIGINAL METHOD - Process Delhi GeoJSON attributes - Simple NAME field mapping"""
        
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
            
            # Land use classification
            'derived_category': derived_category,
            'land_use_type': derived_category,
            'land_use_name': name_field,
            
            # Store original data
            'source_attributes': properties,
        }
        
        # Track category assignment
        self.statistics['categories_assigned'][derived_category] += 1
        
        return processed

    def _process_gurgaon_attributes(self, attrs, layer):
        """ORIGINAL METHOD - Process Gurgaon-specific attributes"""
        
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
        """ORIGINAL METHOD - Process Jaipur-specific attributes"""
        
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
    # ORIGINAL DATA IMPORT METHODS (PRESERVED)
    # ================================

    def _import_esri_json_data(self, layer, data, city_slug):
        """ORIGINAL METHOD - Import ESRI JSON format data"""
        features_imported = 0
        features = data.get('features', [])
        
        print(f"📊 Processing {len(features)} ESRI features")
        
        for feature in features:
            try:
                # Extract geometry and attributes
                esri_geometry = feature.get('geometry', {})
                attributes = feature.get('attributes', {})
                
                if not esri_geometry:
                    continue
                
                # Convert ESRI geometry to GeoJSON
                geojson_geom = convert_esri_to_geojson_geometry(esri_geometry)
                if not geojson_geom:
                    self.statistics['geometry_conversions'] += 1
                    continue
                
                # Create Django geometry object
                geometry = GEOSGeometry(json.dumps(geojson_geom))
                
                # Optimize coordinates if needed
                if geometry:
                    geometry = optimize_coordinates(geometry)
                    self.statistics['coordinate_optimizations'] += 1
                
                # Process attributes based on city
                if city_slug == 'bengaluru':
                    processed_attrs = self._process_bangalore_plu_attributes(attributes, layer)
                elif city_slug == 'vizag':
                    processed_attrs = self._process_vizag_attributes(attributes, layer)
                elif city_slug == 'hyderabad':
                    processed_attrs = self._process_hyderabad_attributes(attributes, layer)
                elif city_slug == 'gurgaon':
                    processed_attrs = self._process_gurgaon_attributes(attributes, layer)
                elif city_slug == 'jaipur':
                    processed_attrs = self._process_jaipur_attributes(attributes, layer)
                else:
                    # Generic processing
                    processed_attrs = {
                        'name': str(attributes.get('name', '')).strip(),
                        'source_layer_name': layer.name,
                        'derived_category': layer.category.code,
                        'source_attributes': attributes,
                    }
                
                # Create GeoFeature
                geo_feature = GeoFeature.objects.create(
                    layer=layer,
                    geometry=geometry,
                    **processed_attrs
                )
                
                features_imported += 1
                self.statistics['features_imported'] += 1
                self.statistics['features_processed'] += 1
                
            except Exception as e:
                self.statistics['features_failed'] += 1
                self.errors.append(f"ESRI feature import failed: {str(e)}")
                continue
        
        return features_imported

    def _import_geojson_data(self, layer, data, city_slug):
        """ORIGINAL METHOD - Import GeoJSON format data"""
        features_imported = 0
        
        # Handle both FeatureCollection and single Feature
        if data.get('type') == 'FeatureCollection':
            features = data.get('features', [])
        elif data.get('type') == 'Feature':
            features = [data]
        else:
            return 0
        
        print(f"📊 Processing {len(features)} GeoJSON features")
        
        for feature in features:
            try:
                # Extract geometry and properties
                geom_data = feature.get('geometry', {})
                properties = feature.get('properties', {})
                
                if not geom_data:
                    continue
                
                # Create Django geometry object
                geometry = GEOSGeometry(json.dumps(geom_data))
                
                # Optimize coordinates if needed
                if geometry:
                    geometry = optimize_coordinates(geometry)
                    self.statistics['coordinate_optimizations'] += 1
                
                # Process properties based on city
                if city_slug == 'delhi':
                    processed_attrs = self._process_delhi_attributes(properties, layer)
                elif city_slug in ['workspace', 'industrial']:
                    processed_attrs = self._process_workspace_attributes(properties, layer)
                else:
                    # Generic processing
                    processed_attrs = {
                        'name': str(properties.get('name', '')).strip(),
                        'description': str(properties.get('description', '')).strip(),
                        'source_layer_name': layer.name,
                        'derived_category': layer.category.code,
                        'source_attributes': properties,
                    }
                
                # Create GeoFeature
                geo_feature = GeoFeature.objects.create(
                    layer=layer,
                    geometry=geometry,
                    **processed_attrs
                )
                
                features_imported += 1
                self.statistics['features_imported'] += 1
                self.statistics['features_processed'] += 1
                
            except Exception as e:
                self.statistics['features_failed'] += 1
                self.errors.append(f"GeoJSON feature import failed: {str(e)}")
                continue
        
        return features_imported

    def _import_json_data(self, layer, data, city_slug):
        """ORIGINAL METHOD - Import generic JSON data"""
        # Placeholder for custom JSON formats
        return 0

    # ================================
    # NEW UTILITY METHODS FOR HIERARCHICAL IMPORTS
    # ================================

    def _find_layer_files(self, data_directory, file_pattern, layer_slug):
        """NEW METHOD - Find data files for a layer using various patterns"""
        data_files = []
        
        # Try exact pattern first
        pattern_path = os.path.join(data_directory, file_pattern)
        matches = glob.glob(pattern_path)
        data_files.extend(matches)
        
        # Try case-insensitive patterns if no matches
        if not data_files:
            patterns_to_try = [
                f"*{layer_slug}*.json",
                f"{layer_slug}.json",
                f"{layer_slug}.geojson",
                f"*{layer_slug.lower()}*.json",
                f"*{layer_slug.upper()}*.json"
            ]
            
            for pattern in patterns_to_try:
                pattern_path = os.path.join(data_directory, pattern)
                matches = glob.glob(pattern_path)
                if matches:
                    data_files.extend(matches)
                    break
        
        return data_files

    def _import_layer_file(self, layer, file_path, city_slug):
        """
        FIXED METHOD - Import features from a single file into a layer
        
        Args:
            layer: DataLayer object
            file_path: Path to the data file
            city_slug: City slug for processing attributes
            
        Returns:
            int: Number of features imported
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # ✅ FIXED: Detect data format based on content structure
            data_format = detect_data_format(data)  # Now uses content, not file path
            
            print(f"    📄 File: {os.path.basename(file_path)}")
            print(f"    🎯 Detected format: {data_format}")
            
            if data_format == 'ESRI_JSON':
                features_imported = self._import_esri_features(layer, data, city_slug)
                print(f"    📊 ESRI JSON: {features_imported} features imported")
                return features_imported
            elif data_format == 'GEOJSON':
                features_imported = self._import_geojson_features(layer, data, city_slug)
                print(f"    📊 GeoJSON: {features_imported} features imported")
                return features_imported
            else:
                error_msg = f"Unknown data format in {file_path}: {data_format}"
                print(f"    ❌ {error_msg}")
                self.errors.append(error_msg)
                return 0
                
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in {file_path}: {str(e)}"
            print(f"    ❌ {error_msg}")
            self.errors.append(error_msg)
            return 0
        except Exception as e:
            error_msg = f"Error importing {file_path}: {str(e)}"
            print(f"    ❌ {error_msg}")
            self.errors.append(error_msg)
            return 0

    def _import_esri_features(self, layer, esri_data, city_slug):
        """
        FIXED METHOD - Import features from ESRI JSON format
        
        Args:
            layer: DataLayer object
            esri_data: ESRI JSON data dictionary
            city_slug: City slug for processing attributes
            
        Returns:
            int: Number of features imported
        """
        features_imported = 0
        
        # Get features from ESRI JSON
        features = esri_data.get('features', [])
        print(f"    📊 Processing {len(features)} ESRI features...")
        
        for i, feature_data in enumerate(features):
            try:
                # Extract geometry and attributes
                esri_geometry = feature_data.get('geometry', {})
                attributes = feature_data.get('attributes', {})
                
                if not esri_geometry:
                    self.statistics['features_skipped'] += 1
                    continue
                
                # Convert ESRI geometry to GeoJSON
                geojson_geom = convert_esri_to_geojson_geometry(esri_geometry)
                if not geojson_geom:
                    self.statistics['geometry_conversions'] += 1
                    self.statistics['features_failed'] += 1
                    continue
                
                # Create Django geometry object
                try:
                    geometry = GEOSGeometry(json.dumps(geojson_geom))
                    self.statistics['geometry_conversions'] += 1
                except Exception as geom_error:
                    print(f"    ❌ Geometry error on feature {i}: {geom_error}")
                    self.statistics['features_failed'] += 1
                    continue
                
                # ✅ FIXED: Process attributes with correct city slug mapping
                processed_attrs = self._process_city_attributes(attributes, layer, city_slug)
                
                # ✅ FIXED: Validate required fields before creating GeoFeature
                if not all(key in processed_attrs for key in ['name', 'source_layer_name']):
                    print(f"    ❌ Missing required attributes on feature {i}")
                    self.statistics['features_failed'] += 1
                    continue
                
                # Create GeoFeature
                try:
                    geo_feature = GeoFeature.objects.create(
                        layer=layer,
                        geometry=geometry,
                        **processed_attrs
                    )
                    
                    features_imported += 1
                    self.statistics['features_imported'] += 1
                    self.statistics['features_processed'] += 1
                    
                    # Progress indicator for large files
                    if features_imported % 500 == 0:
                        print(f"    📈 Progress: {features_imported}/{len(features)} features imported...")
                        
                except Exception as db_error:
                    print(f"    ❌ Database error on feature {i}: {db_error}")
                    self.statistics['features_failed'] += 1
                    continue
                    
            except Exception as e:
                print(f"    ❌ Feature {i} import failed: {str(e)}")
                self.statistics['features_failed'] += 1
                self.errors.append(f"Feature {i} import failed: {str(e)}")
                continue
        
        print(f"    ✅ ESRI import completed: {features_imported} features imported")
        return features_imported
    def _process_city_attributes(self, attributes, layer, city_slug):
        """
        FIXED METHOD - Process attributes with correct city slug mapping and error handling
        
        Args:
            attributes: ESRI attributes or GeoJSON properties
            layer: DataLayer object
            city_slug: City slug ('bengaluru', 'hyderabad', etc.)
            
        Returns:
            dict: Processed attributes for GeoFeature creation
        """
        
        def safe_get(d, key, default=''):
            """Safely get value from dict, handling None and converting to string"""
            value = d.get(key, default)
            if value is None:
                return default
            return str(value).strip()
        
        # ✅ FIXED: Correct city slug mapping (bengaluru = bangalore)
        if city_slug in ['bengaluru', 'bangalore']:
            return self._process_bangalore_plu_attributes_fixed(attributes, layer)
        elif city_slug in ['hyderabad', 'vizag']:
            return self._process_telangana_attributes(attributes, layer)
        elif city_slug == 'delhi':
            return self._process_delhi_attributes(attributes, layer)
        else:
            return self._process_generic_attributes_fixed(attributes, layer)


    def _process_bangalore_plu_attributes_fixed(self, esri_attrs, layer):
        """
        FIXED - Process Bangalore/Bengaluru ESRI attributes with enhanced error handling
        """
        
        def safe_get(d, key, default=''):
            """Safely get value from dict"""
            value = d.get(key, default)
            return str(value).strip() if value is not None else str(default)
        
        # Extract PLU codes with fallbacks
        plu_primary = safe_get(esri_attrs, 'PLU_Cd', '') or safe_get(esri_attrs, 'PLU', '')
        plu_tp_pro = safe_get(esri_attrs, 'PLU_Tp_pro', '')
        plu_tp_p_1 = safe_get(esri_attrs, 'PLU_Tp_p_1', '')
        plu_tp_p_2 = safe_get(esri_attrs, 'PLU_Tp_p_2', '')
        plu_prop_l = safe_get(esri_attrs, 'PLU_prop_l', '')
        
        # Generate name from available PLU fields
        name_parts = [plu_tp_pro, plu_tp_p_1, plu_tp_p_2, plu_prop_l]
        name = ' '.join([part for part in name_parts if part and part.strip()]).strip()
        
        # Fallback name if empty
        if not name:
            name = f"{layer.name} Feature"
        
        # Map PLU to category
        try:
            derived_category = map_plu_code_to_category(plu_primary, 'bangalore')
            if not derived_category or derived_category == 'UNCLASSIFIED':
                derived_category = self._derive_category_from_layer(layer.slug)
        except:
            derived_category = layer.category.code if layer.category else 'UNCLASSIFIED'
        
        # Track PLU codes and categories
        if plu_primary:
            self.statistics['plu_codes_found'][plu_primary] += 1
        self.statistics['categories_assigned'][derived_category] += 1
        
        # ✅ FIXED: Return all required fields for GeoFeature
        return {
            # Required fields
            'name': name[:200],  # Ensure field length limit
            'source_layer_name': layer.name,
            
            # PLU fields
            'plu_primary_code': plu_primary,
            'plu_secondary_1': plu_tp_p_1,
            'plu_secondary_2': plu_tp_p_2,
            'plu_proposed_use': plu_prop_l[:200] if plu_prop_l else '',
            'plu_development_code': esri_attrs.get('PLU_F_PD_C'),
            'plu_authority': safe_get(esri_attrs, 'PLU_BDA', ''),
            'plu_ktc_code': safe_get(esri_attrs, 'PLU_Tp_KTC', ''),
            'plu_survey_code': safe_get(esri_attrs, 'PLU_Tp_sur', ''),
            
            # Derived fields
            'land_use_code': plu_primary,
            'derived_category': derived_category,
            'land_use_type': derived_category,
            
            # Measurements
            'source_area_value': esri_attrs.get('SHAPE.STArea()'),
            'source_length_value': esri_attrs.get('Shape_Leng'),
            'source_perimeter_value': esri_attrs.get('SHAPE.STLength()'),
            
            # Store all original attributes (as JSON)
            'source_attributes': esri_attrs,
            
            # Processing metadata
            'original_precision': 15,
            'geometry_simplified': True,
        }


    def _process_generic_attributes_fixed(self, attrs, layer):
        """FIXED - Process generic attributes with proper error handling"""
        
        def safe_get(d, key, default=''):
            value = d.get(key, default)
            return str(value).strip() if value is not None else str(default)
        
        # Try common field names for name
        name = (safe_get(attrs, 'name') or 
                safe_get(attrs, 'Name') or 
                safe_get(attrs, 'NAME') or 
                safe_get(attrs, 'title') or
                safe_get(attrs, 'Title') or
                f"{layer.name} Feature")
        
        description = (safe_get(attrs, 'description') or 
                    safe_get(attrs, 'Description') or
                    safe_get(attrs, 'desc') or
                    '')
        
        derived_category = layer.category.code if layer.category else 'UNCLASSIFIED'
        self.statistics['categories_assigned'][derived_category] += 1
        
        return {
            'name': name[:200],  # Ensure field length limit
            'description': description[:500],  # Ensure field length limit
            'source_layer_name': layer.name,
            'derived_category': derived_category,
            'land_use_type': derived_category,
            'source_attributes': attrs,
        }

    def _import_geojson_features(self, layer, geojson_data, city_slug):
        """NEW METHOD - Import features from GeoJSON format"""
        features_imported = 0
        
        # Handle both FeatureCollection and single Feature
        if geojson_data.get('type') == 'FeatureCollection':
            features = geojson_data.get('features', [])
        elif geojson_data.get('type') == 'Feature':
            features = [geojson_data]
        else:
            return 0
        
        for feature_data in features:
            try:
                # Extract geometry and properties
                geom_data = feature_data.get('geometry', {})
                properties = feature_data.get('properties', {})
                
                if not geom_data:
                    continue
                
                # Create Django geometry object
                geometry = GEOSGeometry(json.dumps(geom_data))
                
                # Optimize coordinates
                if geometry:
                    geometry = optimize_coordinates(geometry)
                    self.statistics['coordinate_optimizations'] += 1
                
                # Process properties based on city
                processed_attrs = self._process_city_attributes(properties, layer, city_slug)
                
                # Create GeoFeature
                geo_feature = GeoFeature.objects.create(
                    layer=layer,
                    geometry=geometry,
                    **processed_attrs
                )
                
                features_imported += 1
                self.statistics['features_imported'] += 1
                self.statistics['features_processed'] += 1
                
            except Exception as e:
                self.statistics['features_failed'] += 1
                self.errors.append(f"Feature import failed: {str(e)}")
                continue
        
        return features_imported

    def _process_bangalore_attributes(self, attrs, layer):
        """NEW METHOD - Process Bangalore-specific attributes with PLU mapping"""
        
        def safe_get(d, key, default=''):
            """Safely get value from dict, handling None and converting to string"""
            value = d.get(key, default)
            return str(value).strip() if value is not None else default
        
        # Extract PLU codes
        plu_primary = safe_get(attrs, 'PLU', '')
        if not plu_primary:
            # Try alternative field names
            plu_primary = safe_get(attrs, 'PLU_Cd', '')
        
        plu_secondary_1 = safe_get(attrs, 'PLU_NAME', '')
        plu_secondary_2 = safe_get(attrs, 'PLU_prop_l', '')
        
        # Extract other PLU fields
        plu_tp_pro = safe_get(attrs, 'PLU_Tp_pro', '')
        plu_tp_p_1 = safe_get(attrs, 'PLU_Tp_p_1', '')
        plu_tp_p_2 = safe_get(attrs, 'PLU_Tp_p_2', '')
        
        # Generate name from available fields
        name_parts = [plu_secondary_1, plu_tp_pro, plu_tp_p_1, plu_tp_p_2]
        name = ' '.join([part for part in name_parts if part]).strip()
        
        # Map PLU to category
        derived_category = map_plu_code_to_category(plu_primary, 'bengaluru')
        if not derived_category or derived_category == 'UNCLASSIFIED':
            # Try to derive from layer name
            derived_category = self._derive_category_from_layer(layer.slug)
        
        # Track PLU codes and categories
        if plu_primary:
            self.statistics['plu_codes_found'][plu_primary] += 1
        self.statistics['categories_assigned'][derived_category] += 1
        
        return {
            # Basic identification
            'name': name,
            'description': plu_secondary_2,
            'source_layer_name': layer.name,
            
            # PLU fields
            'plu_primary_code': plu_primary,
            'plu_secondary_1': plu_secondary_1,
            'plu_secondary_2': plu_secondary_2,
            'plu_proposed_use': safe_get(attrs, 'PLU_prop_l', ''),
            'plu_development_code': attrs.get('PLU_F_PD_C'),
            'plu_authority': safe_get(attrs, 'PLU_BDA', ''),
            'plu_ktc_code': safe_get(attrs, 'PLU_Tp_KTC', ''),
            'plu_survey_code': safe_get(attrs, 'PLU_Tp_sur', ''),
            
            # Derived fields
            'land_use_code': str(attrs.get('PLU_Cd', '')),
            'derived_category': derived_category,
            'land_use_type': derived_category,
            
            # Measurements
            'source_area_value': attrs.get('SHAPE.STArea()'),
            'source_length_value': attrs.get('Shape_Leng'),
            'source_perimeter_value': attrs.get('SHAPE.STLength()'),
            
            # Store all original attributes
            'source_attributes': attrs,
            
            # Processing metadata
            'original_precision': 15,
            'geometry_simplified': True,
            'source_fid': attrs.get('fid'),
            'source_object_id': attrs.get('OBJECTID'),
        }

    def _process_telangana_attributes(self, attrs, layer):
        """NEW METHOD - Process Telangana (Hyderabad/Vizag) specific attributes"""
        
        def safe_get(d, key, default=''):
            value = d.get(key, default)
            return str(value).strip() if value is not None else default
        
        # Extract common fields
        name = safe_get(attrs, 'Name', '') or safe_get(attrs, 'NAME', '')
        description = safe_get(attrs, 'Description', '') or safe_get(attrs, 'DESCRIPTION', '')
        
        # Derive category from layer or attributes
        derived_category = self._derive_category_from_layer(layer.slug)
        
        # Check for specific Vizag fields
        rule_id = attrs.get('RuleID')
        override_value = safe_get(attrs, 'Override', '')
        
        self.statistics['categories_assigned'][derived_category] += 1
        
        return {
            'name': name,
            'description': description,
            'source_layer_name': layer.name,
            'derived_category': derived_category,
            'land_use_type': derived_category,
            'rule_id': rule_id,
            'override_value': override_value,
            'source_attributes': attrs,
        }

    def _process_generic_attributes(self, attrs, layer):
        """NEW METHOD - Process generic attributes for unknown cities"""
        
        # Try common field names
        name = attrs.get('name', '') or attrs.get('Name', '') or attrs.get('NAME', '')
        description = attrs.get('description', '') or attrs.get('Description', '')
        
        derived_category = self._derive_category_from_layer(layer.slug)
        
        self.statistics['categories_assigned'][derived_category] += 1
        
        return {
            'name': str(name).strip(),
            'description': str(description).strip(),
            'source_layer_name': layer.name,
            'derived_category': derived_category,
            'land_use_type': derived_category,
            'source_attributes': attrs,
        }

    def _derive_category_from_layer(self, layer_slug):
        """NEW METHOD - Derive category from layer slug"""
        layer_lower = layer_slug.lower()
        
        if any(word in layer_lower for word in ['agricultural', 'farm', 'crop']):
            return 'AGRICULTURAL'
        elif any(word in layer_lower for word in ['commercial', 'business', 'office']):
            return 'COMMERCIAL'
        elif any(word in layer_lower for word in ['industrial', 'manufacturing', 'factory']):
            return 'INDUSTRIAL'
        elif any(word in layer_lower for word in ['residential', 'housing', 'apartment']):
            return 'RESIDENTIAL'
        elif any(word in layer_lower for word in ['road', 'highway', 'transport', 'rail', 'metro']):
            return 'TRANSPORT'
        elif any(word in layer_lower for word in ['lake', 'tank', 'water', 'drain']):
            return 'WATER_BODIES'
        elif any(word in layer_lower for word in ['park', 'green', 'garden', 'playground']):
            return 'PARKS_GREEN'
        elif any(word in layer_lower for word in ['government', 'public', 'admin']):
            return 'GOVERNMENT'
        elif any(word in layer_lower for word in ['forest', 'protected', 'reserve']):
            return 'PROTECTED'
        elif any(word in layer_lower for word in ['utility', 'power', 'water', 'waste']):
            return 'UTILITIES'
        else:
            return 'UNCLASSIFIED'

    def _get_or_create_category(self, category_code):
        """NEW METHOD - Get or create LayerCategory"""
        category_configs = {
            'AGRICULTURAL': {'name': 'Agricultural', 'description': 'Agricultural and farming areas'},
            'COMMERCIAL': {'name': 'Commercial', 'description': 'Commercial and business areas'},
            'GOVERNMENT': {'name': 'Government', 'description': 'Government and public facilities'},
            'INDUSTRIAL': {'name': 'Industrial', 'description': 'Industrial and manufacturing areas'},
            'RESIDENTIAL': {'name': 'Residential', 'description': 'Residential areas'},
            'TRANSPORT': {'name': 'Transport', 'description': 'Transportation infrastructure'},
            'WATER_BODIES': {'name': 'Water Bodies', 'description': 'Lakes, tanks, and water features'},
            'PARKS_GREEN': {'name': 'Parks & Green Spaces', 'description': 'Parks and green spaces'},
            'UTILITIES': {'name': 'Utilities', 'description': 'Utility facilities'},
            'PROTECTED': {'name': 'Protected Areas', 'description': 'Protected areas'},
            'UNCLASSIFIED': {'name': 'Unclassified', 'description': 'Unclassified areas'},
        }
        
        config = category_configs.get(category_code, category_configs['UNCLASSIFIED'])
        
        category, created = LayerCategory.objects.get_or_create(
            code=category_code,
            defaults=config
        )
        
        return category

    def _calculate_layer_bounds(self, layer):
        """NEW METHOD - Calculate and store layer bounding box"""
        extent = layer.geofeature_set.aggregate(
            extent=Extent('geometry')
        )['extent']
        
        if extent:
            layer.bbox_xmin = extent[0]
            layer.bbox_ymin = extent[1]
            layer.bbox_xmax = extent[2]
            layer.bbox_ymax = extent[3]

    def _create_layer_style(self, city, layer, layer_config):
        """NEW METHOD - Create city-specific layer styling"""
        try:
            color = layer_config.get('color', '#666666')
            
            style, created = CityLayerStyle.objects.get_or_create(
                city=city,
                category=layer.category,
                defaults={
                    'fill_color': color,
                    'stroke_color': color,
                    'opacity': 0.7,
                    'stroke_width': 1
                }
            )
        except Exception as e:
            self.errors.append(f"Error creating style for {layer.slug}: {str(e)}")

    # ================================
    # ORIGINAL UTILITY METHODS (PRESERVED)
    # ================================

    def _auto_detect_category(self, layer_name):
        """ORIGINAL METHOD - Auto-detect LayerCategory based on layer name"""
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
            'utilities': 'UTILITIES',
            'government': 'GOVERNMENT',
            'public': 'PUBLIC',
            'agriculture': 'AGRICULTURAL',
            'forest': 'PROTECTED'
        }
        
        for keyword, category_code in category_mappings.items():
            if keyword in layer_lower:
                category, created = LayerCategory.objects.get_or_create(
                    code=category_code,
                    defaults={
                        'name': category_code.replace('_', ' ').title(),
                        'description': f'{category_code.replace("_", " ").title()} related layers'
                    }
                )
                return category
        
        # Default category
        category, created = LayerCategory.objects.get_or_create(
            code='UNCLASSIFIED',
            defaults={
                'name': 'Unclassified',
                'description': 'Unclassified layers'
            }
        )
        return category

    def _update_plu_mappings(self, city, plu_codes_found):
        """ORIGINAL METHOD - Update PLU code mappings for a city"""
        
        for plu_code, count in plu_codes_found.items():
            # Check if mapping exists
            existing_mapping = PLUCodeMapping.objects.filter(
                city=city, 
                plu_code=plu_code
            ).first()
            
            if existing_mapping:
                # Update usage statistics
                existing_mapping.feature_count = count
                existing_mapping.last_used = timezone.now()
                existing_mapping.save()
            else:
                # Create new mapping with auto-detected category
                mapped_category = map_plu_code_to_category(plu_code, city.slug)
                category = LayerCategory.objects.get(code=mapped_category)
                
                PLUCodeMapping.objects.create(
                    city=city,
                    plu_code=plu_code,
                    mapped_category=category,
                    feature_count=count,
                    last_used = timezone.now()
                )

    def _generate_layer_name(self, filename):
        """ORIGINAL METHOD - Generate a human-readable layer name from filename"""
        name = Path(filename).stem
        name = name.replace('_', ' ').replace('-', ' ')
        return name.title()

    def _generate_slug(self, filename_stem, city):
        """ORIGINAL METHOD - Generate unique slug for layer"""
        base_slug = slugify(filename_stem)
        slug = base_slug
        counter = 1
        
        while DataLayer.objects.filter(city=city, slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug

    def _detect_format(self, filename):
        """ORIGINAL METHOD - Detect file format from filename"""
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
        """ORIGINAL METHOD - Determine categorization method based on city and format"""
        if city_slug in ['bengaluru']:
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
    
    def generate_combined_mvt_for_layers(self, layers, z, x, y):
        """
        MISSING METHOD - Generate combined MVT for multiple layers (called by S3DirectTileGenerationService)
        This is just a wrapper around generate_combined_tile for backward compatibility
        """
        return self.generate_combined_tile(layers, z, x, y)
    
    def _generate_layer_group_mvt(self, layers, z, x, y):
        """
        MISSING METHOD - Generate MVT for a layer group (alternate interface)
        """
        try:
            # Get tile bounds
            tile_bounds = self._get_tile_bounds(z, x, y)
            
            # Collect features from all layers in the group
            all_features = []
            layers_with_data = []
            
            for layer in layers:
                features = GeoFeature.objects.filter(
                    layer=layer,
                    geometry__intersects=tile_bounds,
                    is_valid=True
                ).select_related('layer', 'layer__category')
                
                if features.exists():
                    all_features.extend(features)
                    layers_with_data.append(layer.slug)
            
            if not all_features:
                print(f"🗺️  No features found in tile {z}/{x}/{y} for any layer in group")
                return b''
            
            print(f"🗺️  Generating layer group MVT {z}/{x}/{y} with {len(all_features)} features from layers: {layers_with_data}")
            
            # Create layer data structure for MVT encoding
            layer_data = {}
            for layer in layers:
                layer_features = [f for f in all_features if f.layer == layer]
                if layer_features:
                    layer_data[layer.slug] = layer_features
            
            if layer_data:
                return self._layers_to_mvt(layer_data, z, x, y)
            else:
                return b''
                
        except Exception as e:
            print(f"❌ Layer group MVT generation failed: {e}")
            import traceback
            traceback.print_exc()
            return b''
    
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