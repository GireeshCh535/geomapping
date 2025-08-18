# maps/geotiff_service.py
"""
GeoTIFF processing service for converting raster data to vector format
and integrating with the existing geospatial data management system.
"""

import os
import json
import tempfile
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from django.conf import settings
from django.utils.text import slugify
from django.contrib.gis.geos import GEOSGeometry
from django.db import transaction

from .models import City, LayerCategory, DataLayer, GeoFeature
from .services import DataImportService

logger = logging.getLogger(__name__)

class GeoTIFFService:
    """
    Service for processing GeoTIFF files and converting them to GeoJSON
    for integration with the existing geospatial data system.
    """
    
    def __init__(self):
        self.import_service = DataImportService()
        self.temp_dir = Path(tempfile.gettempdir()) / 'geotiff_conversion'
        self.temp_dir.mkdir(exist_ok=True)
    
    def process_geotiff_file(self, 
                           input_path: str, 
                           city_slug: str, 
                           category_code: str,
                           layer_name: Optional[str] = None,
                           simplify_tolerance: float = 0.0001,
                           optimize_coordinates: bool = True) -> Dict[str, Any]:
        """
        Process a single GeoTIFF file and convert it to GeoJSON.
        
        Args:
            input_path: Path to the GeoTIFF file
            city_slug: City slug for the target city
            category_code: Layer category code (e.g., 'RESIDENTIAL')
            layer_name: Custom layer name (optional)
            simplify_tolerance: Geometry simplification tolerance
            optimize_coordinates: Whether to optimize coordinate precision
            
        Returns:
            Dict with processing results and metadata
        """
        
        result = {
            'success': False,
            'input_file': input_path,
            'output_file': None,
            'layer_created': None,
            'features_imported': 0,
            'errors': [],
            'warnings': [],
            'processing_time': 0
        }
        
        try:
            import time
            start_time = time.time()
            
            # Validate inputs
            if not self._validate_inputs(input_path, city_slug, category_code):
                result['errors'].append("Input validation failed")
                return result
            
            # Convert GeoTIFF to GeoJSON
            geojson_path = self._convert_geotiff_to_geojson(
                input_path, simplify_tolerance, optimize_coordinates
            )
            
            if not geojson_path:
                result['errors'].append("GeoTIFF conversion failed")
                return result
            
            result['output_file'] = str(geojson_path)
            
            # Generate layer name if not provided
            if not layer_name:
                layer_name = Path(input_path).stem
            
            # Import into the system
            layer_result = self._import_geojson_layer(
                geojson_path, city_slug, category_code, layer_name
            )
            
            if layer_result['success']:
                result['success'] = True
                result['layer_created'] = layer_result['layer']
                result['features_imported'] = layer_result['features_count']
            else:
                result['errors'].extend(layer_result['errors'])
            
            result['processing_time'] = time.time() - start_time
            
        except Exception as e:
            result['errors'].append(f"Processing error: {str(e)}")
            logger.error(f"GeoTIFF processing error: {e}", exc_info=True)
        
        return result
    
    def process_geotiff_directory(self, 
                                input_dir: str, 
                                city_slug: str, 
                                category_code: str,
                                file_pattern: str = "*.tif",
                                **kwargs) -> List[Dict[str, Any]]:
        """
        Process all GeoTIFF files in a directory.
        
        Args:
            input_dir: Directory containing GeoTIFF files
            city_slug: City slug for the target city
            category_code: Layer category code
            file_pattern: File pattern to match (default: "*.tif")
            **kwargs: Additional arguments for process_geotiff_file
            
        Returns:
            List of processing results for each file
        """
        
        input_path = Path(input_dir)
        if not input_path.exists() or not input_path.is_dir():
            return [{'success': False, 'errors': [f"Directory not found: {input_dir}"]}]
        
        # Find all matching files
        tif_files = list(input_path.glob(file_pattern)) + list(input_path.glob("*.tiff"))
        
        if not tif_files:
            return [{'success': False, 'errors': [f"No GeoTIFF files found in: {input_dir}"]}]
        
        results = []
        for tif_file in tif_files:
            logger.info(f"Processing GeoTIFF file: {tif_file}")
            result = self.process_geotiff_file(
                str(tif_file), city_slug, category_code, **kwargs
            )
            results.append(result)
        
        return results
    
    def _validate_inputs(self, input_path: str, city_slug: str, category_code: str) -> bool:
        """Validate input parameters"""
        
        # Check input file
        if not os.path.exists(input_path):
            logger.error(f"Input file not found: {input_path}")
            return False
        
        if not input_path.lower().endswith(('.tif', '.tiff')):
            logger.error(f"Input file is not a GeoTIFF: {input_path}")
            return False
        
        # Check city
        try:
            city = City.objects.get(slug=city_slug, is_active=True)
        except City.DoesNotExist:
            logger.error(f"City not found: {city_slug}")
            return False
        
        # Check category
        try:
            category = LayerCategory.objects.get(code=category_code, is_active=True)
        except LayerCategory.DoesNotExist:
            logger.error(f"Category not found: {category_code}")
            return False
        
        return True
    
    def _convert_geotiff_to_geojson(self, 
                                  input_path: str, 
                                  simplify_tolerance: float = 0.0001,
                                  optimize_coordinates: bool = True) -> Optional[Path]:
        """
        Convert GeoTIFF to GeoJSON using GDAL.
        
        Args:
            input_path: Path to GeoTIFF file
            simplify_tolerance: Geometry simplification tolerance
            optimize_coordinates: Whether to optimize coordinate precision
            
        Returns:
            Path to the converted GeoJSON file or None if conversion failed
        """
        
        try:
            # Create temporary output file
            input_file = Path(input_path)
            temp_output = self.temp_dir / f"{input_file.stem}_converted.geojson"
            
            # Build GDAL command
            cmd = [
                'gdal_polygonize.py',
                str(input_path),
                '-f', 'GeoJSON',
                str(temp_output)
            ]
            
            logger.info(f"Running GDAL command: {' '.join(cmd)}")
            
            # Run conversion
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            if not temp_output.exists():
                logger.error("GDAL conversion failed - output file not created")
                return None
            
            # Apply simplification if requested
            if simplify_tolerance > 0:
                simplified_output = self._simplify_geojson(temp_output, simplify_tolerance)
                if simplified_output:
                    temp_output.unlink()  # Remove original
                    temp_output = simplified_output
            
            # Optimize coordinates if requested
            if optimize_coordinates:
                self._optimize_geojson_coordinates(temp_output)
            
            return temp_output
            
        except subprocess.CalledProcessError as e:
            logger.error(f"GDAL conversion error: {e.stderr}")
            return None
        except Exception as e:
            logger.error(f"Conversion error: {e}", exc_info=True)
            return None
    
    def _simplify_geojson(self, geojson_path: Path, tolerance: float) -> Optional[Path]:
        """Simplify GeoJSON geometry to reduce file size"""
        
        try:
            import geopandas as gpd
            
            # Read GeoJSON
            gdf = gpd.read_file(geojson_path)
            
            if gdf.empty:
                logger.warning("Empty GeoJSON file - no simplification needed")
                return geojson_path
            
            # Simplify geometries
            gdf['geometry'] = gdf['geometry'].simplify(tolerance, preserve_topology=True)
            
            # Save simplified version
            simplified_path = geojson_path.with_suffix('.simplified.geojson')
            gdf.to_file(simplified_path, driver='GeoJSON')
            
            logger.info(f"Simplified geometry with tolerance: {tolerance}")
            return simplified_path
            
        except ImportError:
            logger.warning("geopandas not available - skipping simplification")
            return geojson_path
        except Exception as e:
            logger.warning(f"Simplification failed: {e}")
            return geojson_path
    
    def _optimize_geojson_coordinates(self, geojson_path: Path, precision: int = 6):
        """Optimize coordinate precision in GeoJSON"""
        
        try:
            with open(geojson_path, 'r') as f:
                data = json.load(f)
            
            # Optimize coordinates
            if 'features' in data:
                for feature in data['features']:
                    if 'geometry' in feature and 'coordinates' in feature['geometry']:
                        feature['geometry']['coordinates'] = self._optimize_coordinates(
                            feature['geometry']['coordinates'], precision
                        )
            
            # Write optimized version
            with open(geojson_path, 'w') as f:
                json.dump(data, f, separators=(',', ':'))
            
            logger.info(f"Optimized coordinates with precision: {precision}")
            
        except Exception as e:
            logger.warning(f"Coordinate optimization failed: {e}")
    
    def _optimize_coordinates(self, coords: Any, precision: int = 6) -> Any:
        """Recursively optimize coordinate precision"""
        if isinstance(coords, list):
            return [self._optimize_coordinates(coord, precision) for coord in coords]
        elif isinstance(coords, (int, float)):
            return round(float(coords), precision)
        return coords
    
    def _import_geojson_layer(self, 
                            geojson_path: Path, 
                            city_slug: str, 
                            category_code: str,
                            layer_name: str) -> Dict[str, Any]:
        """
        Import the converted GeoJSON into the existing system.
        
        Args:
            geojson_path: Path to the GeoJSON file
            city_slug: City slug
            category_code: Layer category code
            layer_name: Layer name
            
        Returns:
            Dict with import results
        """
        
        result = {
            'success': False,
            'layer': None,
            'features_count': 0,
            'errors': []
        }
        
        try:
            with transaction.atomic():
                # Get city and category
                city = City.objects.get(slug=city_slug, is_active=True)
                category = LayerCategory.objects.get(code=category_code, is_active=True)
                
                # Create layer slug
                layer_slug = slugify(layer_name)
                
                # Check if layer already exists
                existing_layer = DataLayer.objects.filter(
                    city=city, slug=layer_slug
                ).first()
                
                if existing_layer:
                    logger.info(f"Layer already exists: {existing_layer.name}")
                    result['layer'] = existing_layer
                    result['features_count'] = existing_layer.feature_count
                    result['success'] = True
                    return result
                
                # Create new layer
                layer = DataLayer.objects.create(
                    city=city,
                    category=category,
                    name=layer_name,
                    slug=layer_slug,
                    description=f"Converted from GeoTIFF: {geojson_path.name}",
                    file_path=str(geojson_path),
                    file_format='GEOJSON',
                    geometry_type='POLYGON',  # GeoTIFF typically converts to polygons
                    is_processed=False
                )
                
                # Import features
                features_count = self._import_geojson_features(geojson_path, layer)
                
                # Update layer
                layer.feature_count = features_count
                layer.is_processed = True
                layer.calculate_bbox()  # Calculate bounding box
                layer.save()
                
                result['success'] = True
                result['layer'] = layer
                result['features_count'] = features_count
                
                logger.info(f"Successfully imported layer: {layer.name} with {features_count} features")
                
        except Exception as e:
            result['errors'].append(f"Import error: {str(e)}")
            logger.error(f"Import error: {e}", exc_info=True)
        
        return result
    
    def _import_geojson_features(self, geojson_path: Path, layer: DataLayer) -> int:
        """
        Import features from GeoJSON file into the database.
        
        Args:
            geojson_path: Path to GeoJSON file
            layer: DataLayer instance
            
        Returns:
            Number of features imported
        """
        
        try:
            with open(geojson_path, 'r') as f:
                data = json.load(f)
            
            features = data.get('features', [])
            imported_count = 0
            
            # Process features in batches
            batch_size = 1000
            for i in range(0, len(features), batch_size):
                batch = features[i:i + batch_size]
                batch_features = []
                
                for feature in batch:
                    try:
                        # Extract geometry
                        geometry_data = feature.get('geometry', {})
                        if not geometry_data or 'coordinates' not in geometry_data:
                            continue
                        
                        # Convert to GEOS geometry
                        geos_geometry = GEOSGeometry(json.dumps(geometry_data))
                        
                        # Extract properties
                        properties = feature.get('properties', {})
                        
                        # Create GeoFeature
                        geo_feature = GeoFeature(
                            layer=layer,
                            geometry=geos_geometry,
                            source_layer_name=geojson_path.stem,
                            zone_category=layer.category.name,
                            properties=properties,
                            is_valid=True
                        )
                        
                        batch_features.append(geo_feature)
                        
                    except Exception as e:
                        logger.warning(f"Error processing feature: {e}")
                        continue
                
                # Bulk create features
                if batch_features:
                    GeoFeature.objects.bulk_create(batch_features, batch_size=100)
                    imported_count += len(batch_features)
                
                logger.info(f"Imported batch {i//batch_size + 1}: {len(batch_features)} features")
            
            return imported_count
            
        except Exception as e:
            logger.error(f"Feature import error: {e}", exc_info=True)
            return 0
    
    def get_conversion_stats(self, geojson_path: Path) -> Dict[str, Any]:
        """
        Get statistics about a converted GeoJSON file.
        
        Args:
            geojson_path: Path to GeoJSON file
            
        Returns:
            Dict with file statistics
        """
        
        stats = {
            'file_size_mb': 0,
            'feature_count': 0,
            'bounds': None,
            'geometry_types': []
        }
        
        try:
            # File size
            stats['file_size_mb'] = geojson_path.stat().st_size / (1024 * 1024)
            
            # Read GeoJSON
            with open(geojson_path, 'r') as f:
                data = json.load(f)
            
            features = data.get('features', [])
            stats['feature_count'] = len(features)
            
            # Extract bounds
            if 'bbox' in data:
                stats['bounds'] = data['bbox']
            
            # Analyze geometry types
            geometry_types = set()
            for feature in features:
                geom_type = feature.get('geometry', {}).get('type')
                if geom_type:
                    geometry_types.add(geom_type)
            
            stats['geometry_types'] = list(geometry_types)
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
        
        return stats
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        try:
            import shutil
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info("Cleaned up temporary files")
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
