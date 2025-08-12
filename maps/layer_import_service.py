# maps/services/layer_import_service.py
# Service to properly import layers with correct hierarchy

import os
import json
import glob
from pathlib import Path
from django.db import transaction
from django.contrib.gis.geos import GEOSGeometry
from maps.models import State, City, DataLayer, GeoFeature, LayerCategory
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class LayerImportService:
    """
    Service to import GeoJSON data with proper hierarchical structure:
    State → City → Layer (folder) → Files → Features
    """
    
    def __init__(self):
        self.import_stats = {
            'layers_created': 0,
            'files_processed': 0,
            'features_imported': 0,
            'errors': []
        }
    
    @transaction.atomic
    def import_city_data(self, state_slug: str, city_slug: str, base_path: str):
        """
        Import all layers for a city with proper hierarchy
        
        Args:
            state_slug: State identifier (e.g., 'karnataka')
            city_slug: City identifier (e.g., 'bengaluru')
            base_path: Base path to city data folder
        """
        try:
            # Get or create state and city
            state = State.objects.get(slug=state_slug)
            city = City.objects.get(slug=city_slug, state_ref=state)
            
            logger.info(f"Importing data for {city.name}, {state.name}")
            
            # Get city data path
            city_path = os.path.join(base_path, state_slug, city_slug)
            
            if not os.path.exists(city_path):
                raise ValueError(f"City data path not found: {city_path}")
            
            # Process each layer folder
            layer_folders = [d for d in os.listdir(city_path) 
                           if os.path.isdir(os.path.join(city_path, d))]
            
            for layer_folder in layer_folders:
                self._import_layer(city, layer_folder, os.path.join(city_path, layer_folder))
            
            logger.info(f"Import complete: {self.import_stats}")
            return self.import_stats
            
        except Exception as e:
            logger.error(f"Error importing city data: {e}")
            self.import_stats['errors'].append(str(e))
            raise
    
    def _import_layer(self, city: City, layer_name: str, layer_path: str):
        """
        Import a single layer (folder) containing multiple files
        
        Args:
            city: City object
            layer_name: Name of the layer (folder name)
            layer_path: Path to layer folder
        """
        try:
            logger.info(f"Processing layer: {layer_name}")
            
            # Determine category based on layer name
            category = self._get_category_for_layer(layer_name)
            
            # Create or update the layer (ONE layer for the entire folder)
            layer, created = DataLayer.objects.update_or_create(
                city=city,
                slug=layer_name.lower().replace(' ', '_').replace('-', '_'),
                defaults={
                    'name': layer_name.replace('_', ' ').title(),
                    'category': category,
                    'description': f"{layer_name} layer for {city.name}",
                    'is_directory': True,  # This is a directory-based layer
                    'file_path': layer_path,
                    'file_pattern': '*.json,*.geojson',  # Pattern to match files
                    'categorization_method': 'FILENAME',
                    'is_processed': False  # Will set to True after processing files
                }
            )
            
            if created:
                logger.info(f"Created new layer: {layer.name}")
                self.import_stats['layers_created'] += 1
            else:
                logger.info(f"Updated existing layer: {layer.name}")
            
            # Now process all files within this layer
            file_patterns = ['*.json', '*.geojson']
            files_to_process = []
            
            for pattern in file_patterns:
                files_to_process.extend(glob.glob(os.path.join(layer_path, pattern)))
            
            if not files_to_process:
                logger.warning(f"No files found in layer: {layer_name}")
                return
            
            logger.info(f"Found {len(files_to_process)} files in {layer_name}")
            
            # Process each file as part of this single layer
            total_features = 0
            for file_path in files_to_process:
                feature_count = self._import_file_to_layer(layer, file_path)
                total_features += feature_count
                self.import_stats['files_processed'] += 1
            
            # Update layer statistics
            layer.feature_count = total_features
            layer.is_processed = True
            layer.save()
            
            logger.info(f"Layer {layer_name} processed: {total_features} features from {len(files_to_process)} files")
            
        except Exception as e:
            logger.error(f"Error importing layer {layer_name}: {e}")
            self.import_stats['errors'].append(f"Layer {layer_name}: {str(e)}")
    
    def _import_file_to_layer(self, layer: DataLayer, file_path: str) -> int:
        """
        Import a single file's features into the layer
        
        Args:
            layer: DataLayer object
            file_path: Path to the GeoJSON file
            
        Returns:
            Number of features imported
        """
        try:
            filename = os.path.basename(file_path)
            logger.info(f"Processing file: {filename} for layer: {layer.name}")
            
            # Read GeoJSON file
            with open(file_path, 'r') as f:
                geojson_data = json.load(f)
            
            if geojson_data.get('type') != 'FeatureCollection':
                logger.warning(f"File {filename} is not a FeatureCollection")
                return 0
            
            features = geojson_data.get('features', [])
            imported_count = 0
            
            for idx, feature in enumerate(features):
                try:
                    # Create GeoFeature for this layer
                    geometry = GEOSGeometry(json.dumps(feature['geometry']))
                    properties = feature.get('properties', {})
                    
                    # Extract zone/category info based on city
                    zone_info = self._extract_zone_info(layer.city.slug, properties)
                    
                    geo_feature = GeoFeature.objects.create(
                        layer=layer,
                        geometry=geometry,
                        source_layer_name=filename.replace('.json', '').replace('.geojson', ''),
                        name=properties.get('name', ''),
                        description=properties.get('description', ''),
                        
                        # Zone/category fields
                        zone_category=zone_info.get('category', ''),
                        zone_subcategory=zone_info.get('subcategory', ''),
                        
                        # PLU fields for Bangalore/Warangal
                        plu_primary_code=properties.get('PLU', ''),
                        plu_secondary_1=properties.get('PLU_NAME', ''),
                        
                        # Amaravati fields
                        plot_category=properties.get('plot_categ', ''),
                        symbology=properties.get('symbology', ''),
                        
                        # Store all properties as JSON
                        properties=properties,
                        is_valid=True
                    )
                    
                    imported_count += 1
                    self.import_stats['features_imported'] += 1
                    
                except Exception as e:
                    logger.error(f"Error importing feature {idx} from {filename}: {e}")
                    continue
            
            logger.info(f"Imported {imported_count} features from {filename}")
            return imported_count
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            self.import_stats['errors'].append(f"File {file_path}: {str(e)}")
            return 0
    
    def _get_category_for_layer(self, layer_name: str) -> LayerCategory:
        """
        Determine the category for a layer based on its name
        
        Args:
            layer_name: Name of the layer folder
            
        Returns:
            LayerCategory object
        """
        layer_lower = layer_name.lower()
        
        # Map layer names to categories
        category_mapping = {
            'master_plan': 'MIXED_USE',
            'highways': 'TRANSPORT',
            'metro': 'TRANSPORT',
            'metro_lines': 'TRANSPORT',
            'strr': 'TRANSPORT',
            'workspace': 'INDUSTRIAL',
            'workspaces': 'INDUSTRIAL',
            'future_city': 'BOUNDARIES',
            'railway': 'TRANSPORT',
            'roads': 'TRANSPORT',
            'master_plan_roads': 'TRANSPORT',
            'rrr': 'TRANSPORT',
            'sez': 'INDUSTRIAL',
        }
        
        # Find matching category
        category_code = 'UNCLASSIFIED'
        for key, value in category_mapping.items():
            if key in layer_lower:
                category_code = value
                break
        
        # Get or create category
        category, _ = LayerCategory.objects.get_or_create(
            code=category_code,
            defaults={
                'name': category_code.replace('_', ' ').title(),
                'description': f"{category_code} category"
            }
        )
        
        return category
    
    def _extract_zone_info(self, city_slug: str, properties: Dict) -> Dict:
        """
        Extract zone/category information based on city
        
        Args:
            city_slug: City identifier
            properties: Feature properties
            
        Returns:
            Dictionary with zone information
        """
        zone_info = {}
        
        if city_slug == 'warangal':
            zone_info['category'] = properties.get('PLU_NAME', '')
            zone_info['subcategory'] = properties.get('PLU', '')
        elif city_slug == 'visakhapatnam':
            zone_info['category'] = properties.get('Category', '')
            zone_info['subcategory'] = properties.get('Sub_Category', '')
        elif city_slug == 'amaravati':
            zone_info['category'] = properties.get('symbology', '')
            zone_info['subcategory'] = properties.get('plot_categ', '')
        elif city_slug == 'bengaluru':
            zone_info['category'] = properties.get('PLU_NAME', '')
            zone_info['subcategory'] = properties.get('PLU', '')
        
        return zone_info


class LayerStructureFixer:
    """
    Fix existing incorrect layer structure where files are treated as layers
    """
    
    @transaction.atomic
    def consolidate_file_layers_to_single_layer(self, city_slug: str, layer_name: str, 
                                               file_patterns: List[str]):
        """
        Consolidate multiple file-based layers into a single layer
        
        Args:
            city_slug: City identifier
            layer_name: Target layer name (e.g., 'master_plan')
            file_patterns: List of file patterns to consolidate
        """
        try:
            city = City.objects.get(slug=city_slug)
            
            # Create the consolidated layer
            category = self._get_category_for_layer(layer_name)
            
            master_layer, created = DataLayer.objects.get_or_create(
                city=city,
                slug=layer_name.lower().replace(' ', '_'),
                defaults={
                    'name': layer_name.replace('_', ' ').title(),
                    'category': category,
                    'description': f"Consolidated {layer_name} layer for {city.name}",
                    'is_directory': True,
                    'categorization_method': 'FILENAME',
                    'is_processed': False
                }
            )
            
            logger.info(f"{'Created' if created else 'Using existing'} master layer: {master_layer.name}")
            
            # Find all file-based layers to consolidate
            file_layers = []
            for pattern in file_patterns:
                # Remove .json extension for matching
                pattern_clean = pattern.replace('.json', '').replace('.geojson', '')
                matching_layers = DataLayer.objects.filter(
                    city=city,
                    name__icontains=pattern_clean
                ).exclude(id=master_layer.id)
                file_layers.extend(matching_layers)
            
            logger.info(f"Found {len(file_layers)} file-based layers to consolidate")
            
            # Move all features from file layers to master layer
            total_features_moved = 0
            for file_layer in file_layers:
                feature_count = file_layer.geofeature_set.count()
                
                # Update all features to point to master layer
                file_layer.geofeature_set.update(
                    layer=master_layer,
                    source_layer_name=file_layer.name  # Preserve original file name
                )
                
                total_features_moved += feature_count
                logger.info(f"Moved {feature_count} features from {file_layer.name} to {master_layer.name}")
                
                # Delete the file-based layer
                file_layer.delete()
            
            # Update master layer statistics
            master_layer.feature_count = master_layer.geofeature_set.count()
            master_layer.is_processed = True
            master_layer.save()
            
            logger.info(f"Consolidation complete: {total_features_moved} features in {master_layer.name}")
            
            return {
                'success': True,
                'master_layer': master_layer.name,
                'file_layers_removed': len(file_layers),
                'features_consolidated': total_features_moved
            }
            
        except Exception as e:
            logger.error(f"Error consolidating layers: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_category_for_layer(self, layer_name: str) -> LayerCategory:
        """Get or create category for layer"""
        layer_lower = layer_name.lower()
        
        # Determine category
        if 'master' in layer_lower:
            category_code = 'MIXED_USE'
        elif any(word in layer_lower for word in ['highway', 'road', 'metro', 'rail']):
            category_code = 'TRANSPORT'
        elif any(word in layer_lower for word in ['industrial', 'workspace', 'sez']):
            category_code = 'INDUSTRIAL'
        else:
            category_code = 'UNCLASSIFIED'
        
        category, _ = LayerCategory.objects.get_or_create(
            code=category_code,
            defaults={'name': category_code.replace('_', ' ').title()}
        )
        
        return category