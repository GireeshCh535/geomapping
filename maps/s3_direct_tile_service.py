# maps/services/s3_direct_tile_service.py
"""
Enhanced S3 Direct Tile Generation Service with Pattern Support
Generates tiles (PNG/MVT) directly to S3 with hatched, dotted, and striped patterns
"""

import io
import mercantile
import logging
from pathlib import Path
from django.conf import settings
from botocore.exceptions import ClientError, NoCredentialsError
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple
import mimetypes
import time

from maps.services import VectorTileService
from maps.tile_rendering_service import TileRenderingService  # Enhanced version with patterns
from maps.tile_path_service import TilePathService
from maps.tile_storage import (
    get_tile_object_storage_bucket_name,
    get_tile_object_storage_s3_client,
    public_https_url_for_object_key,
)
from maps.models import DataLayer, City, GeoFeature, CityLayerStyle, CityZoneMapping
from maps.config import get_city_style_config, get_visakhapatnam_styles, get_amaravati_styles

logger = logging.getLogger(__name__)

class S3DirectTileGenerationService:
    """
    Enhanced service for generating and uploading tiles directly to S3
    Now supports pattern fills (hatched, dotted, striped) for different zones
    """
    
    def __init__(self):
        self.bucket_name = get_tile_object_storage_bucket_name()
        self.region = getattr(settings, 'AWS_S3_REGION_NAME', 'ap-south-1')
        self.s3_tile_domain = (
            (getattr(settings, 'AWS_S3_TILE_DOMAIN', None) or '').strip()
            or (getattr(settings, 'PUBLIC_TILE_CDN_HOST', None) or '').strip()
        )
        self.cloudfront_domain = getattr(settings, 'CLOUDFRONT_DOMAIN', None)
        self.s3_client = get_tile_object_storage_s3_client()
        
        # Initialize tile services
        self.vector_service = VectorTileService()
        self.render_service = TileRenderingService()  # Enhanced version with pattern support
    
    def upload_bytes_to_s3(self, data_bytes: bytes, s3_key: str, content_type: str) -> Dict[str, Any]:
        """
        Upload bytes data directly to S3
        
        Args:
            data_bytes: The tile data as bytes
            s3_key: S3 object key (path)
            content_type: MIME type
        
        Returns:
            Dict with success status and details
        """
        try:
            # Set cache headers based on content type
            # cache_control = 'max-age=31536000'  # 1 year for PNG
            # if content_type == 'application/vnd.mapbox-vector-tile':
            #     cache_control = 'max-age=86400'  # 1 day for MVT
            
            # Fixed: Removed ContentLength from extra_args
            extra_args = {
                'ContentType': content_type,
                # 'CacheControl': cache_control,
            }
            
            # Upload using put_object with BytesIO
            file_obj = io.BytesIO(data_bytes)
            
            # upload_fileobj automatically handles content length
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                s3_key,
                ExtraArgs=extra_args
            )
            
            public_url = public_https_url_for_object_key(s3_key)
            cloudfront_url = None
            if self.cloudfront_domain and not (getattr(settings, 'PUBLIC_TILE_CDN_HOST', None) or '').strip():
                cloudfront_url = f"https://{self.cloudfront_domain}/{s3_key}"

            return {
                'success': True,
                's3_key': s3_key,
                'size': len(data_bytes),
                's3_url': public_url,
                'cloudfront_url': cloudfront_url,
            }
            
        except ClientError as e:
            logger.error(f"Failed to upload {s3_key}: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected error uploading {s3_key}: {e}")
            return {'success': False, 'error': str(e)}

    def generate_and_upload_city_tiles(self, city_slug: str, min_zoom: int = 8, max_zoom: int = 14, 
                                     tile_types: List[str] = ['png', 'mvt'],
                                     use_patterns: bool = True, target_coordinates: tuple = None) -> Dict[str, Any]:
        """
        Generate and upload all tiles for a city directly to S3 with pattern support
        
        Args:
            city_slug: City identifier
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            tile_types: List of tile types ('png', 'mvt')
            use_patterns: Whether to use pattern fills for supported cities
            target_coordinates: Optional (lng, lat) tuple to ensure tiles are generated for specific area
        
        Returns:
            Dictionary with generation results
        """
        try:
            # Get city and layers
            city = City.objects.get(slug=city_slug, is_active=True)
            layers = DataLayer.objects.filter(
                city=city,
                is_processed=True
            ).select_related('category', 'city')
            
            if not layers.exists():
                return {
                    'success': False,
                    'error': f'No processed layers found for city: {city_slug}'
                }
            
            # Check if this city has pattern styles configured
            has_patterns = CityLayerStyle.objects.filter(
                city=city,
                fill_pattern__in=['HATCHED', 'DOTTED', 'STRIPED', 'CROSS_HATCHED']
            ).exists()
            
            if has_patterns and use_patterns:
                logger.info(f"🎨 City {city_slug} has pattern styles configured")
            
            logger.info(f"🚀 Starting direct S3 generation for {city_slug} with {layers.count()} layers")
            
            # Calculate tile bounds for the city
            city_bounds = self._get_city_bounds(layers)
            if not city_bounds:
                return {
                    'success': False,
                    'error': f'Could not determine bounds for city: {city_slug}'
                }
            
            # ENHANCED: If target coordinates provided, expand bounds to include them
            if target_coordinates:
                target_lng, target_lat = target_coordinates
                # Expand bounds to include target coordinates if they're outside current bounds
                city_bounds['west'] = min(city_bounds['west'], target_lng - 0.01)  # Add buffer
                city_bounds['east'] = max(city_bounds['east'], target_lng + 0.01)  # Add buffer
                city_bounds['south'] = min(city_bounds['south'], target_lat - 0.01)  # Add buffer
                city_bounds['north'] = max(city_bounds['north'], target_lat + 0.01)  # Add buffer
                logger.info(f"🔧 Expanded city bounds to include target coordinates: {city_bounds}")
            
            # Generate tile list
            tiles_to_generate = []
            for zoom in range(min_zoom, max_zoom + 1):
                tiles = list(mercantile.tiles(
                    city_bounds['west'], city_bounds['south'],
                    city_bounds['east'], city_bounds['north'],
                    zoom
                ))
                tiles_to_generate.extend([(tile.z, tile.x, tile.y) for tile in tiles])
                
                # ENHANCED: If target coordinates provided, ensure that specific tile is included
                if target_coordinates:
                    target_lng, target_lat = target_coordinates
                    target_tile = mercantile.tile(target_lng, target_lat, zoom)
                    target_tile_tuple = (target_tile.z, target_tile.x, target_tile.y)
                    
                    # Check if target tile is in the list
                    target_tile_in_list = any(t == target_tile_tuple for t in tiles_to_generate)
                    
                    if not target_tile_in_list:
                        logger.info(f"🔧 Adding target tile {target_tile.z}/{target_tile.x}/{target_tile.y} for zoom {zoom}")
                        tiles_to_generate.append(target_tile_tuple)
            
            logger.info(f"📊 Will generate {len(tiles_to_generate)} tiles across zoom levels {min_zoom}-{max_zoom}")
            
            # Generate tiles with concurrent processing
            results = {
                'total_tiles': len(tiles_to_generate),
                'generated_tiles': 0,
                'failed_tiles': 0,
                'png_uploads': 0,
                'mvt_uploads': 0,
                'total_size_mb': 0,
                'errors': [],
                'has_patterns': has_patterns and use_patterns
            }
            
            # Use ThreadPoolExecutor for concurrent generation
            max_workers = min(10, len(tiles_to_generate))
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                
                for z, x, y in tiles_to_generate:
                    future = executor.submit(
                        self._generate_and_upload_single_tile_with_patterns,
                        city_slug, layers, z, x, y, tile_types, use_patterns
                    )
                    futures.append(future)
                
                # Process completed futures
                for i, future in enumerate(as_completed(futures)):
                    try:
                        tile_result = future.result()
                        if tile_result['success']:
                            results['generated_tiles'] += 1
                            if 'png_size' in tile_result:
                                results['png_uploads'] += 1
                                results['total_size_mb'] += tile_result['png_size'] / (1024 * 1024)
                            if 'mvt_size' in tile_result:
                                results['mvt_uploads'] += 1
                                results['total_size_mb'] += tile_result['mvt_size'] / (1024 * 1024)
                        else:
                            results['failed_tiles'] += 1
                            results['errors'].append(tile_result.get('error', 'Unknown error'))
                        
                        # Progress logging
                        if (i + 1) % 50 == 0:
                            logger.info(f"📈 Progress: {i + 1}/{len(futures)} tiles processed")
                            
                    except Exception as e:
                        results['failed_tiles'] += 1
                        results['errors'].append(str(e))
                        logger.error(f"Error processing tile future: {e}")
            
            # Calculate success rate
            success_rate = (results['generated_tiles'] / results['total_tiles']) * 100 if results['total_tiles'] > 0 else 0
            
            return {
                'success': results['failed_tiles'] == 0,
                'city': city_slug,
                'results': results,
                'success_rate': f"{success_rate:.1f}%",
                'cloudfront_base_url': f"https://{self.cloudfront_domain}" if self.cloudfront_domain else None,
                'sample_urls': self._generate_sample_urls(city_slug, min_zoom, max_zoom)
            }
            
        except Exception as e:
            logger.error(f"Error in generate_and_upload_city_tiles: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_and_upload_single_tile_with_patterns(self, city_slug: str, layers, z: int, x: int, y: int, 
                                                      tile_types: List[str], use_patterns: bool = True) -> Dict[str, Any]:
        """
        Enhanced: Generate and upload a single tile with pattern support
        
        Args:
            city_slug: City identifier
            layers: QuerySet of DataLayer objects
            z, x, y: Tile coordinates
            tile_types: List of tile types ('png', 'mvt')
            use_patterns: Whether to use pattern fills
        
        Returns:
            Dictionary with upload results
        """
        try:
            result = {'success': False}
            
            # Generate MVT data using VectorTileService
            mvt_data = self.vector_service.generate_combined_tile(layers, z, x, y)
            
            # Check if we have valid MVT data
            if not mvt_data or len(mvt_data) == 0:
                logger.debug(f"No MVT data for tile {city_slug}/{z}/{x}/{y}, generating empty tiles")
                
                # Generate empty tiles for areas with no data
                if 'mvt' in tile_types:
                    mvt_key = f"{city_slug}/combined/{z}_{x}_{y}.mvt"
                    mvt_result = self.upload_bytes_to_s3(b'', mvt_key, 'application/vnd.mapbox-vector-tile')
                    if mvt_result['success']:
                        result['mvt_size'] = 0
                
                if 'png' in tile_types:
                    empty_png = self.render_service.create_empty_tile()
                    png_key = f"{city_slug}/combined/{z}_{x}_{y}.png"
                    png_result = self.upload_bytes_to_s3(empty_png, png_key, 'image/png')
                    if png_result['success']:
                        result['png_size'] = len(empty_png)
                
                result['success'] = True
                return result
            
            # Upload MVT if requested
            if 'mvt' in tile_types:
                mvt_key = f"{city_slug}/combined/{z}_{x}_{y}.mvt"
                mvt_result = self.upload_bytes_to_s3(mvt_data, mvt_key, 'application/vnd.mapbox-vector-tile')
                if mvt_result['success']:
                    result['mvt_size'] = len(mvt_data)
                else:
                    return {'success': False, 'error': f"MVT upload failed: {mvt_result.get('error')}"}
            
            # Generate and upload PNG if requested
            if 'png' in tile_types:
                logger.debug(f"Generating PNG for tile {city_slug}/{z}/{x}/{y} with patterns={use_patterns}")
                
                # Use enhanced rendering with pattern support
                if use_patterns and city_slug in ['visakhapatnam', 'amaravati']:
                    # Use pattern-aware rendering for cities with pattern configurations
                    png_data = self.render_service.render_mvt_to_png_with_patterns(
                        mvt_data, layers, z, x, y, city_slug
                    )
                else:
                    # Use standard rendering for other cities
                    png_data = self.render_service.combined_mvt_to_png(mvt_data, layers, z, x, y)
                
                if png_data and len(png_data) > 0:
                    png_key = f"{city_slug}/combined/{z}_{x}_{y}.png"
                    png_result = self.upload_bytes_to_s3(png_data, png_key, 'image/png')
                    if png_result['success']:
                        result['png_size'] = len(png_data)
                        logger.debug(f"Successfully uploaded PNG for {city_slug}/{z}/{x}/{y}, size: {len(png_data)} bytes")
                    else:
                        return {'success': False, 'error': f"PNG upload failed: {png_result.get('error')}"}
                else:
                    # Fallback to empty tile if PNG generation fails
                    logger.warning(f"PNG generation failed for {city_slug}/{z}/{x}/{y}, using empty tile")
                    empty_png = self.render_service.create_empty_tile()
                    png_key = f"{city_slug}/combined/{z}_{x}_{y}.png"
                    png_result = self.upload_bytes_to_s3(empty_png, png_key, 'image/png')
                    if png_result['success']:
                        result['png_size'] = len(empty_png)
                    else:
                        return {'success': False, 'error': f"Empty PNG upload failed: {png_result.get('error')}"}
            
            result['success'] = True
            return result
            
        except Exception as e:
            logger.error(f"Error generating tile {city_slug}/{z}/{x}/{y}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _generate_and_upload_single_tile_optimized(self, city_slug: str, layers, z: int, x: int, y: int, 
                                                   tile_types: List[str], use_patterns: bool = True) -> Dict[str, Any]:
        """
        MEMORY-OPTIMIZED with PATTERN SUPPORT: Generate and upload a single city tile
        Only processes features that actually intersect with the tile bounds
        """
        try:
            result = {'success': False}
            
            # Get tile bounds as a polygon for spatial filtering
            tile_bounds = self._get_tile_bounds(z, x, y)
            if not tile_bounds:
                return {'success': False, 'error': 'Could not calculate tile bounds'}
            
            # OPTIMIZATION: Only get features that intersect with THIS tile
            tile_features = []
            total_features_in_tile = 0
            
            # Process layers individually to manage memory
            for layer in layers:
                layer_features = GeoFeature.objects.filter(
                    layer=layer,
                    geometry__intersects=tile_bounds,  # SPATIAL FILTER
                    is_valid=True
                ).select_related('layer', 'layer__category')[:1000]  # Limit per layer
                
                layer_feature_count = layer_features.count()
                if layer_feature_count > 0:
                    tile_features.extend(list(layer_features))
                    total_features_in_tile += layer_feature_count
            
            logger.debug(f"🎯 Tile {z}/{x}/{y}: Processing {total_features_in_tile} features")
            
            # If no features in this tile, create empty tile
            if not tile_features:
                if 'mvt' in tile_types:
                    mvt_key = f"{city_slug}/combined/{z}_{x}_{y}.mvt"
                    mvt_result = self.upload_bytes_to_s3(b'', mvt_key, 'application/vnd.mapbox-vector-tile')
                    if mvt_result['success']:
                        result['mvt_size'] = 0
                
                if 'png' in tile_types:
                    empty_png = self.render_service.create_empty_tile()
                    png_key = f"{city_slug}/combined/{z}_{x}_{y}.png"
                    png_result = self.upload_bytes_to_s3(empty_png, png_key, 'image/png')
                    if png_result['success']:
                        result['png_size'] = len(empty_png)
                
                result['success'] = True
                result['features_processed'] = 0
                return result
            
            # Generate MVT using only filtered features
            mvt_data = self._features_to_mvt_with_zone_data(tile_features, z, x, y, city_slug)
            
            if not mvt_data:
                # Still create empty tiles even if MVT generation fails
                if 'mvt' in tile_types:
                    mvt_key = f"{city_slug}/combined/{z}_{x}_{y}.mvt"
                    mvt_result = self.upload_bytes_to_s3(b'', mvt_key, 'application/vnd.mapbox-vector-tile')
                    if mvt_result['success']:
                        result['mvt_size'] = 0
                
                if 'png' in tile_types:
                    empty_png = self.render_service.create_empty_tile()
                    png_key = f"{city_slug}/combined/{z}_{x}_{y}.png"
                    png_result = self.upload_bytes_to_s3(empty_png, png_key, 'image/png')
                    if png_result['success']:
                        result['png_size'] = len(empty_png)
                
                result['success'] = True
                result['features_processed'] = total_features_in_tile
                return result
            
            # Upload MVT if requested
            if 'mvt' in tile_types:
                mvt_key = f"{city_slug}/combined/{z}_{x}_{y}.mvt"
                mvt_result = self.upload_bytes_to_s3(mvt_data, mvt_key, 'application/vnd.mapbox-vector-tile')
                if mvt_result['success']:
                    result['mvt_size'] = len(mvt_data)
                else:
                    return {'success': False, 'error': f"MVT upload failed: {mvt_result.get('error')}"}
            
            # Generate and upload PNG if requested
            if 'png' in tile_types:
                # Get layers for style information
                layer_ids = list(set([f.layer_id for f in tile_features]))
                tile_layers = DataLayer.objects.filter(id__in=layer_ids).select_related('category', 'city')
                
                # Use pattern-aware rendering if applicable
                if use_patterns and city_slug in ['visakhapatnam', 'amaravati']:
                    png_data = self.render_service.render_mvt_to_png_with_patterns(
                        mvt_data, tile_layers, z, x, y, city_slug
                    )
                else:
                    png_data = self.render_service.combined_mvt_to_png(mvt_data, tile_layers, z, x, y)
                
                if png_data:
                    png_key = f"{city_slug}/combined/{z}_{x}_{y}.png"
                    png_result = self.upload_bytes_to_s3(png_data, png_key, 'image/png')
                    if png_result['success']:
                        result['png_size'] = len(png_data)
                    else:
                        return {'success': False, 'error': f"PNG upload failed: {png_result.get('error')}"}
                else:
                    return {'success': False, 'error': 'PNG generation failed'}
            
            result['success'] = True
            result['features_processed'] = total_features_in_tile
            return result
            
        except Exception as e:
            logger.error(f"Error generating optimized tile {city_slug}/{z}/{x}/{y}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _features_to_mvt_with_zone_data(self, features, z, x, y, city_slug):
        """
        Enhanced: Generate MVT from filtered features with zone/category data for pattern support
        """
        try:
            import mapbox_vector_tile
            from collections import defaultdict
            
            # Group features by layer for organized MVT structure
            layer_data = defaultdict(list)
            
            for feature in features:
                layer_name = feature.layer.slug
                
                # Create feature properties with zone information
                properties = {
                    'id': feature.id,
                    'layer': layer_name
                }
                
                # Add zone/category information based on city
                if city_slug == 'warangal':
                    properties['plu'] = getattr(feature, 'plu_primary_code', '')
                    properties['plu_name'] = getattr(feature, 'plu_secondary_1', '')
                elif city_slug == 'visakhapatnam':
                    properties['category_name'] = getattr(feature, 'zone_category', '')
                elif city_slug == 'amaravati':
                    properties['symbology'] = getattr(feature, 'zone_category', '')
                    properties['plot_categ'] = getattr(feature, 'zone_subcategory', '')
                
                # Add custom properties if available
                if hasattr(feature, 'properties') and feature.properties:
                    properties.update(feature.properties)
                
                # Add geometry
                try:
                    geom_dict = {
                        'geometry': feature.geometry.__geo_interface__,
                        'properties': properties
                    }
                    layer_data[layer_name].append(geom_dict)
                except Exception as e:
                    logger.warning(f"Skipping invalid geometry for feature {feature.id}: {e}")
                    continue
            
            # Build MVT layers
            mvt_layers = {}
            for layer_name, layer_features in layer_data.items():
                if layer_features:
                    mvt_layers[layer_name] = {
                        'features': layer_features,
                        'version': 2,
                        'extent': 4096
                    }
            
            if not mvt_layers:
                return None
            
            # Generate MVT
            mvt_data = mapbox_vector_tile.encode(mvt_layers)
            return mvt_data
            
        except Exception as e:
            logger.error(f"Error generating MVT with zone data: {e}")
            return None
    
    def generate_and_upload_real_estate_tiles(self, data_type: str = 'combined', 
                                            min_zoom: int = 8, max_zoom: int = 16,
                                            tile_types: List[str] = ['png', 'mvt']) -> Dict[str, Any]:
        """
        Generate and upload real estate tiles directly to S3
        
        Args:
            data_type: 'plots', 'lands', or 'combined'
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            tile_types: List of tile types ('png', 'mvt')
        
        Returns:
            Dictionary with generation results
        """
        try:
            logger.info(f"🏡 Starting real estate tile generation for {data_type}")
            
            # Get data bounds
            bounds = self._get_real_estate_bounds(data_type)
            if not bounds:
                return {
                    'success': False,
                    'error': f'No data found for real estate type: {data_type}'
                }
            
            # Generate tile list
            tiles_to_generate = []
            for zoom in range(min_zoom, max_zoom + 1):
                tiles = list(mercantile.tiles(
                    bounds['west'], bounds['south'],
                    bounds['east'], bounds['north'],
                    zoom
                ))
                tiles_to_generate.extend([(tile.z, tile.x, tile.y) for tile in tiles])
            
            logger.info(f"📊 Will generate {len(tiles_to_generate)} real estate tiles")
            
            # Generate tiles with concurrent processing
            results = {
                'total_tiles': len(tiles_to_generate),
                'generated_tiles': 0,
                'failed_tiles': 0,
                'png_uploads': 0,
                'mvt_uploads': 0,
                'total_size_mb': 0,
                'errors': []
            }
            
            max_workers = min(8, len(tiles_to_generate))
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                
                for z, x, y in tiles_to_generate:
                    future = executor.submit(
                        self._generate_and_upload_real_estate_tile,
                        data_type, z, x, y, tile_types
                    )
                    futures.append(future)
                
                # Process completed futures
                for i, future in enumerate(as_completed(futures)):
                    try:
                        tile_result = future.result()
                        if tile_result['success']:
                            results['generated_tiles'] += 1
                            if 'png_size' in tile_result:
                                results['png_uploads'] += 1
                                results['total_size_mb'] += tile_result['png_size'] / (1024 * 1024)
                            if 'mvt_size' in tile_result:
                                results['mvt_uploads'] += 1
                                results['total_size_mb'] += tile_result['mvt_size'] / (1024 * 1024)
                        else:
                            results['failed_tiles'] += 1
                            results['errors'].append(tile_result.get('error', 'Unknown error'))
                        
                        if (i + 1) % 100 == 0:
                            logger.info(f"📈 Real estate progress: {i + 1}/{len(futures)} tiles processed")
                            
                    except Exception as e:
                        results['failed_tiles'] += 1
                        results['errors'].append(str(e))
            
            success_rate = (results['generated_tiles'] / results['total_tiles']) * 100 if results['total_tiles'] > 0 else 0
            
            return {
                'success': results['failed_tiles'] == 0,
                'data_type': data_type,
                'results': results,
                'success_rate': f"{success_rate:.1f}%",
                'cloudfront_base_url': f"https://{self.cloudfront_domain}" if self.cloudfront_domain else None,
            }
            
        except Exception as e:
            logger.error(f"Error in generate_and_upload_real_estate_tiles: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # Keep all the existing helper methods unchanged
    def _get_city_bounds(self, layers) -> Optional[Dict[str, float]]:
        """Calculate bounds from all layers in a city"""
        bounds = None
        
        for layer in layers:
            layer_bounds = self.vector_service._get_layer_bounds(layer)
            if layer_bounds:
                if not bounds:
                    bounds = layer_bounds.copy()
                else:
                    bounds['west'] = min(bounds['west'], layer_bounds['west'])
                    bounds['south'] = min(bounds['south'], layer_bounds['south'])
                    bounds['east'] = max(bounds['east'], layer_bounds['east'])
                    bounds['north'] = max(bounds['north'], layer_bounds['north'])
        
        return bounds
    
    
    
    def _get_tile_bounds(self, z: int, x: int, y: int):
        """Get geographic bounds for a tile"""
        try:
            from django.contrib.gis.geos import Polygon
            import mercantile
            
            tile = mercantile.Tile(x, y, z)
            west, south, east, north = mercantile.bounds(tile)
            
            # Create polygon for spatial queries
            bounds_polygon = Polygon.from_bbox((west, south, east, north))
            bounds_polygon.srid = 4326
            
            return bounds_polygon
            
        except Exception as e:
            logger.error(f"Error getting tile bounds: {e}")
            return None
    
    def _generate_sample_urls(self, city_slug: str, min_zoom: int, max_zoom: int) -> Dict[str, str]:
        """Generate sample URLs using the same CloudFront vs S3 rules as tile_path_service."""
        tps = TilePathService()
        sample_key = f"{city_slug}/combined/0_0_0.png"
        if tps.use_public_cdn_for_tile_origin():
            base_url = f"https://{tps.public_tile_cdn_host}"
            if tps.public_tile_cdn_path_prefix:
                base_url = f"{base_url}/{tps.public_tile_cdn_path_prefix}"
        else:
            host = tps.cloudfront_domain if tps.use_cloudfront_for_path(sample_key) else tps.s3_tile_domain
            base_url = f"https://{host}"
        mid_zoom = (min_zoom + max_zoom) // 2
        
        return {
            'city_tile_example': f"{base_url}/{city_slug}/combined/{mid_zoom}_2048_2048.png",
            'city_mvt_example': f"{base_url}/{city_slug}/combined/{mid_zoom}_2048_2048.mvt",
            'template_png': f"{base_url}/{city_slug}/combined/{{z}}_{{x}}_{{y}}.png",
            'template_mvt': f"{base_url}/{city_slug}/combined/{{z}}_{{x}}_{{y}}.mvt"
        }
    
    def _draw_mvt_feature(self, draw, feature, color):
        """Draw a single MVT feature on the image"""
        try:
            geometry = feature.get('geometry', {})
            geom_type = geometry.get('type', '')
            coordinates = geometry.get('coordinates', [])
            
            if geom_type == 'Polygon':
                for ring in coordinates:
                    if len(ring) >= 3:
                        # Convert coordinates to pixel coordinates
                        pixels = [(int(coord[0] * 256 / 4096), int(coord[1] * 256 / 4096)) for coord in ring]
                        if len(pixels) >= 3:
                            draw.polygon(pixels, fill=color, outline=color)
            
            elif geom_type == 'Point':
                x, y = coordinates[0] * 256 / 4096, coordinates[1] * 256 / 4096
                draw.ellipse([x-2, y-2, x+2, y+2], fill=color, outline=color)
                
        except Exception as e:
            logger.error(f"Error drawing MVT feature: {e}")
    
    def test_connection(self) -> Dict[str, Any]:
        """Test S3 connection and bucket access"""
        try:
            # Try to head bucket (checks if bucket exists and we have access)
            response = self.s3_client.head_bucket(Bucket=self.bucket_name)
            
            return {
                'success': True,
                'bucket': self.bucket_name,
                'region': self.region,
                's3_tile_domain': self.s3_tile_domain,
                'cloudfront_domain': self.cloudfront_domain,
                'message': 'S3 connection successful'
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                error_msg = f"Bucket '{self.bucket_name}' not found"
            elif error_code == '403':
                error_msg = f"Access denied to bucket '{self.bucket_name}'"
            else:
                error_msg = f"S3 error: {e.response['Error']['Message']}"
            
            return {
                'success': False,
                'error': error_msg,
                'bucket': self.bucket_name,
                'region': self.region
            }
            
        except NoCredentialsError:
            return {
                'success': False,
                'error': 'AWS credentials not found or invalid',
                'bucket': self.bucket_name,
                'region': self.region
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Connection test failed: {str(e)}',
                'bucket': self.bucket_name,
                'region': self.region
            }