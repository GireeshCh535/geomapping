# maps/services/s3_direct_tile_service.py
"""
Direct S3 Tile Generation Service
Generates tiles (PNG/MVT) directly to S3 without local storage
"""

import boto3
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
from maps.tile_rendering_service import TileRenderingService
from maps.models import DataLayer, City, Plot, Land, GeoFeature

logger = logging.getLogger(__name__)

class S3DirectTileGenerationService:
    """
    Service for generating and uploading tiles directly to S3
    Eliminates local storage entirely
    """
    
    def __init__(self):
        self.bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'gis-portal')
        self.region = getattr(settings, 'AWS_S3_REGION_NAME', 'ap-south-1')
        self.cloudfront_domain = getattr(settings, 'CLOUDFRONT_DOMAIN', None)
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            region_name=self.region,
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        )
        
        # Initialize tile services
        self.vector_service = VectorTileService()
        self.render_service = TileRenderingService()
    
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
            cache_control = 'max-age=31536000'  # 1 year for PNG
            if content_type == 'application/vnd.mapbox-vector-tile':
                cache_control = 'max-age=86400'  # 1 day for MVT
            
            # FIXED: Remove ContentLength from extra_args
            extra_args = {
                'ContentType': content_type,
                'CacheControl': cache_control,
                # REMOVED: 'ContentLength': len(data_bytes)  # This causes the error!
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
            
            # Generate URLs
            s3_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            cloudfront_url = None
            if self.cloudfront_domain:
                cloudfront_url = f"https://{self.cloudfront_domain}/{s3_key}"
            
            return {
                'success': True,
                's3_key': s3_key,
                'size': len(data_bytes),
                's3_url': s3_url,
                'cloudfront_url': cloudfront_url
            }
            
        except ClientError as e:
            logger.error(f"Failed to upload {s3_key}: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected error uploading {s3_key}: {e}")
            return {'success': False, 'error': str(e)}

    def generate_and_upload_city_tiles(self, city_slug: str, min_zoom: int = 8, max_zoom: int = 14, 
                                     tile_types: List[str] = ['png', 'mvt']) -> Dict[str, Any]:
        """
        Generate and upload all tiles for a city directly to S3
        
        Args:
            city_slug: City identifier
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            tile_types: List of tile types ('png', 'mvt')
        
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
            
            logger.info(f"🚀 Starting direct S3 generation for {city_slug} with {layers.count()} layers")
            
            # Calculate tile bounds for the city
            city_bounds = self._get_city_bounds(layers)
            if not city_bounds:
                return {
                    'success': False,
                    'error': f'Could not determine bounds for city: {city_slug}'
                }
            
            # Generate tile list
            tiles_to_generate = []
            for zoom in range(min_zoom, max_zoom + 1):
                tiles = list(mercantile.tiles(
                    city_bounds['west'], city_bounds['south'],
                    city_bounds['east'], city_bounds['north'],
                    zoom
                ))
                tiles_to_generate.extend([(tile.z, tile.x, tile.y) for tile in tiles])
            
            logger.info(f"📊 Will generate {len(tiles_to_generate)} tiles across zoom levels {min_zoom}-{max_zoom}")
            
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
            
            # Use ThreadPoolExecutor for concurrent generation
            max_workers = min(10, len(tiles_to_generate))  # Limit concurrent uploads
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                
                for z, x, y in tiles_to_generate:
                    future = executor.submit(
                        self._generate_and_upload_single_tile_optimized,
                        city_slug, layers, z, x, y, tile_types
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
                'cloudfront_base_url': f"https://{self.cloudfront_domain}" if self.cloudfront_domain else None
            }
            
        except Exception as e:
            logger.error(f"Error in generate_and_upload_real_estate_tiles: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_and_upload_single_tile(self, city_slug: str, layers, z: int, x: int, y: int, 
                                       tile_types: List[str]) -> Dict[str, Any]:
        """Generate and upload a single city tile"""
        try:
            result = {'success': False}
            
            # Generate MVT data
            mvt_data = self.vector_service.generate_combined_tile(layers, z, x, y)
            
            if not mvt_data:
                # Upload empty tiles
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
                png_data = self.render_service.combined_mvt_to_png(mvt_data, layers, z, x, y)
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
            return result
            
        except Exception as e:
            logger.error(f"Error generating tile {city_slug}/{z}/{x}/{y}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _generate_and_upload_real_estate_tile(self, data_type: str, z: int, x: int, y: int, 
                                            tile_types: List[str]) -> Dict[str, Any]:
        """Generate and upload a single real estate tile"""
        try:
            result = {'success': False}
            
            # Generate MVT data based on data type
            if data_type == 'plots':
                mvt_data = self._generate_plots_mvt(z, x, y)
            elif data_type == 'lands':
                mvt_data = self._generate_lands_mvt(z, x, y)
            else:  # combined
                mvt_data = self._generate_combined_real_estate_mvt(z, x, y)
            
            if not mvt_data:
                # Upload empty tiles
                if 'mvt' in tile_types:
                    mvt_key = f"real_estate/{data_type}/{z}_{x}_{y}.mvt"
                    mvt_result = self.upload_bytes_to_s3(b'', mvt_key, 'application/vnd.mapbox-vector-tile')
                    if mvt_result['success']:
                        result['mvt_size'] = 0
                
                if 'png' in tile_types:
                    empty_png = self.render_service.create_empty_tile()
                    png_key = f"real_estate/{data_type}/{z}_{x}_{y}.png"
                    png_result = self.upload_bytes_to_s3(empty_png, png_key, 'image/png')
                    if png_result['success']:
                        result['png_size'] = len(empty_png)
                
                result['success'] = True
                return result
            
            # Upload MVT if requested
            if 'mvt' in tile_types:
                mvt_key = f"real_estate/{data_type}/{z}_{x}_{y}.mvt"
                mvt_result = self.upload_bytes_to_s3(mvt_data, mvt_key, 'application/vnd.mapbox-vector-tile')
                if mvt_result['success']:
                    result['mvt_size'] = len(mvt_data)
                else:
                    return {'success': False, 'error': f"MVT upload failed: {mvt_result.get('error')}"}
            
            # Generate and upload PNG if requested
            if 'png' in tile_types:
                png_data = self._convert_real_estate_mvt_to_png(mvt_data, data_type, z, x, y)
                if png_data:
                    png_key = f"real_estate/{data_type}/{z}_{x}_{y}.png"
                    png_result = self.upload_bytes_to_s3(png_data, png_key, 'image/png')
                    if png_result['success']:
                        result['png_size'] = len(png_data)
                    else:
                        return {'success': False, 'error': f"PNG upload failed: {png_result.get('error')}"}
                else:
                    return {'success': False, 'error': 'PNG generation failed'}
            
            result['success'] = True
            return result
            
        except Exception as e:
            logger.error(f"Error generating real estate tile {data_type}/{z}/{x}/{y}: {e}")
            return {'success': False, 'error': str(e)}
        
    def _generate_and_upload_single_tile_optimized(self, city_slug: str, layers, z: int, x: int, y: int, 
                                                   tile_types: List[str]) -> Dict[str, Any]:
        """
        MEMORY-OPTIMIZED: Generate and upload a single city tile
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
                    geometry__intersects=tile_bounds,  # SPATIAL FILTER - KEY OPTIMIZATION
                    is_valid=True
                ).select_related('layer', 'layer__category')[:1000]  # Limit per layer for memory
                
                layer_feature_count = layer_features.count()
                if layer_feature_count > 0:
                    tile_features.extend(list(layer_features))
                    total_features_in_tile += layer_feature_count
            
            print(f"🎯 Tile {z}/{x}/{y}: Processing {total_features_in_tile} features (filtered from {sum(layer.features.count() for layer in layers)})")
            
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
            mvt_data = self._features_to_mvt_optimized(tile_features, z, x, y)
            
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
                # Use memory-optimized PNG generation
                png_data = self._mvt_to_png_optimized(mvt_data, layers, z, x, y)
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
        
    def _features_to_mvt_optimized(self, features, z, x, y):
        """Generate MVT from filtered features with memory optimization"""
        try:
            import mapbox_vector_tile
            from collections import defaultdict
            
            # Group features by layer for organized MVT structure
            layer_data = defaultdict(list)
            
            for feature in features:
                layer_name = feature.layer.slug
                
                # Create feature properties
                properties = {
                    'id': feature.id,
                    'category': feature.layer.category.code if feature.layer.category else 'unknown',
                    'layer': layer_name
                }
                
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
                if layer_features:  # Only include layers with features
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
            logger.error(f"Error generating optimized MVT: {e}")
            return None

    def _mvt_to_png_optimized(self, mvt_data, layers, z, x, y):
        """Memory-optimized PNG generation"""
        try:
            from PIL import Image, ImageDraw
            import mapbox_vector_tile
            
            # Decode MVT
            decoded_data = mapbox_vector_tile.decode(mvt_data)
            if not decoded_data:
                return self.render_service.create_empty_tile()
            
            # Create image
            img = Image.new('RGBA', (256, 256), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            
            # Layer colors (you can customize these)
            layer_colors = {
                'residential': (255, 255, 0, 180),      # Yellow
                'commercial': (0, 77, 168, 180),        # Blue  
                'industrial': (170, 102, 178, 180),     # Purple
                'public': (230, 0, 0, 180),             # Red
                'parks': (152, 230, 0, 180),            # Green
                'transport': (128, 128, 128, 180),      # Gray
                'water': (30, 144, 255, 180),           # Dodger Blue
            }
            
            features_drawn = 0
            
            # Draw each layer
            for layer_name, layer_data in decoded_data.items():
                features = layer_data.get('features', [])
                
                # Get color for layer
                color = layer_colors.get(layer_name.lower(), (128, 128, 128, 180))
                
                for feature in features:
                    if self._draw_mvt_feature_optimized(draw, feature, color):
                        features_drawn += 1
                    
                    # Memory protection: limit features per tile
                    if features_drawn > 5000:
                        logger.warning(f"Tile {z}/{x}/{y}: Limited to 5000 features for memory")
                        break
            
            # Use enhanced compression
            return self.render_service._save_compressed_png(img, optimize_level=2)
            
        except Exception as e:
            logger.error(f"Error in optimized PNG generation: {e}")
            return self.render_service.create_empty_tile()

    
    def _get_city_bounds(self, layers) -> Optional[Dict[str, float]]:
        """Get bounding box for city layers"""
        try:
            from django.contrib.gis.db.models import Extent
            from maps.models import GeoFeature
            
            # Get extent from all features in the layers
            extent = GeoFeature.objects.filter(
                layer__in=layers,
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
            
        except Exception as e:
            logger.error(f"Error getting city bounds: {e}")
            return None
        
    def _draw_mvt_feature_optimized(self, draw, feature, color):
        """Draw a single MVT feature with memory optimization"""
        try:
            geometry = feature.get('geometry', {})
            geom_type = geometry.get('type', '')
            coordinates = geometry.get('coordinates', [])
            
            if geom_type == 'Polygon':
                for ring in coordinates[:1]:  # Only draw outer ring for memory efficiency
                    if len(ring) >= 3:
                        # Simplify coordinates for memory efficiency
                        simplified_ring = ring[::2] if len(ring) > 100 else ring  # Skip every other point if too many
                        pixels = [(int(coord[0] * 256 / 4096), int(coord[1] * 256 / 4096)) for coord in simplified_ring]
                        if len(pixels) >= 3:
                            draw.polygon(pixels, fill=color, outline=color)
                            return True
            
            elif geom_type == 'Point':
                if coordinates:
                    x, y = coordinates[0] * 256 / 4096, coordinates[1] * 256 / 4096
                    draw.ellipse([x-1, y-1, x+1, y+1], fill=color, outline=color)
                    return True
            
            elif geom_type == 'LineString':
                if len(coordinates) >= 2:
                    pixels = [(int(coord[0] * 256 / 4096), int(coord[1] * 256 / 4096)) for coord in coordinates]
                    for i in range(len(pixels) - 1):
                        draw.line([pixels[i], pixels[i+1]], fill=color, width=1)
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Error drawing optimized MVT feature: {e}")
            return False
    
    def _get_real_estate_bounds(self, data_type: str) -> Optional[Dict[str, float]]:
        """Get bounding box for real estate data"""
        try:
            from django.contrib.gis.db.models import Extent
            
            if data_type == 'plots':
                extent = Plot.objects.filter(is_active=True).aggregate(extent=Extent('location'))['extent']
            elif data_type == 'lands':
                extent = Land.objects.filter(is_active=True).aggregate(extent=Extent('location'))['extent']
            else:  # combined
                plot_extent = Plot.objects.filter(is_active=True).aggregate(extent=Extent('location'))['extent']
                land_extent = Land.objects.filter(is_active=True).aggregate(extent=Extent('location'))['extent']
                
                if plot_extent and land_extent:
                    extent = [
                        min(plot_extent[0], land_extent[0]),
                        min(plot_extent[1], land_extent[1]),
                        max(plot_extent[2], land_extent[2]),
                        max(plot_extent[3], land_extent[3])
                    ]
                else:
                    extent = plot_extent or land_extent
            
            if extent:
                return {
                    'west': extent[0],
                    'south': extent[1],
                    'east': extent[2], 
                    'north': extent[3]
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting real estate bounds: {e}")
            return None
    
    def _generate_plots_mvt(self, z: int, x: int, y: int) -> Optional[bytes]:
        """Generate MVT for plots"""
        try:
            import mapbox_vector_tile
            from django.contrib.gis.geos import Polygon
            
            tile_bounds = self._get_tile_bounds(z, x, y)
            if not tile_bounds:
                return None
            
            plots = Plot.objects.filter(
                location__intersects=tile_bounds,
                is_active=True
            )[:500]  # Limit features
            
            if not plots.exists():
                return None
            
            features = []
            for plot in plots:
                properties = {
                    'id': plot.id,
                    'survey_number': plot.survey_number or '',
                    'plot_area': float(plot.plot_area) if plot.plot_area else 0,
                    'type': 'plot'
                }
                
                features.append({
                    'geometry': plot.location.__geo_interface__,
                    'properties': properties
                })
            
            mvt_data = mapbox_vector_tile.encode({
                'plots': {
                    'features': features,
                    'version': 2,
                    'extent': 4096
                }
            })
            
            return mvt_data
            
        except Exception as e:
            logger.error(f"Error generating plots MVT: {e}")
            return None
    
    def _generate_lands_mvt(self, z: int, x: int, y: int) -> Optional[bytes]:
        """Generate MVT for lands"""
        try:
            import mapbox_vector_tile
            
            tile_bounds = self._get_tile_bounds(z, x, y)
            if not tile_bounds:
                return None
            
            lands = Land.objects.filter(
                location__intersects=tile_bounds,
                is_active=True
            )[:500]  # Limit features
            
            if not lands.exists():
                return None
            
            features = []
            for land in lands:
                properties = {
                    'id': land.id,
                    'survey_number': land.survey_number or '',
                    'land_area': float(land.land_area) if land.land_area else 0,
                    'type': 'land'
                }
                
                features.append({
                    'geometry': land.location.__geo_interface__,
                    'properties': properties
                })
            
            mvt_data = mapbox_vector_tile.encode({
                'lands': {
                    'features': features,
                    'version': 2,
                    'extent': 4096
                }
            })
            
            return mvt_data
            
        except Exception as e:
            logger.error(f"Error generating lands MVT: {e}")
            return None
    
    def _generate_combined_real_estate_mvt(self, z: int, x: int, y: int) -> Optional[bytes]:
        """Generate combined MVT for plots and lands"""
        try:
            import mapbox_vector_tile
            
            tile_bounds = self._get_tile_bounds(z, x, y)
            if not tile_bounds:
                return None
            
            # Get plots
            plots = Plot.objects.filter(
                location__intersects=tile_bounds,
                is_active=True
            )[:250]  # Limit features per type
            
            # Get lands
            lands = Land.objects.filter(
                location__intersects=tile_bounds,
                is_active=True
            )[:250]  # Limit features per type
            
            if not plots.exists() and not lands.exists():
                return None
            
            layers = {}
            
            # Add plots layer
            if plots.exists():
                plot_features = []
                for plot in plots:
                    properties = {
                        'id': plot.id,
                        'survey_number': plot.survey_number or '',
                        'plot_area': float(plot.plot_area) if plot.plot_area else 0,
                        'type': 'plot'
                    }
                    
                    plot_features.append({
                        'geometry': plot.location.__geo_interface__,
                        'properties': properties
                    })
                
                layers['plots'] = {
                    'features': plot_features,
                    'version': 2,
                    'extent': 4096
                }
            
            # Add lands layer
            if lands.exists():
                land_features = []
                for land in lands:
                    properties = {
                        'id': land.id,
                        'survey_number': land.survey_number or '',
                        'land_area': float(land.land_area) if land.land_area else 0,
                        'type': 'land'
                    }
                    
                    land_features.append({
                        'geometry': land.location.__geo_interface__,
                        'properties': properties
                    })
                
                layers['lands'] = {
                    'features': land_features,
                    'version': 2,
                    'extent': 4096
                }
            
            mvt_data = mapbox_vector_tile.encode(layers)
            return mvt_data
            
        except Exception as e:
            logger.error(f"Error generating combined real estate MVT: {e}")
            return None
    
    def _convert_real_estate_mvt_to_png(self, mvt_data: bytes, data_type: str, z: int, x: int, y: int) -> Optional[bytes]:
        """Convert real estate MVT to PNG"""
        try:
            from PIL import Image, ImageDraw
            import mapbox_vector_tile
            
            # Decode MVT
            decoded_data = mapbox_vector_tile.decode(mvt_data)
            if not decoded_data:
                return self.render_service.create_empty_tile()
            
            # Create image
            img = Image.new('RGBA', (256, 256), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            
            # Define colors for different types
            colors = {
                'plot': (255, 196, 0, 200),    # Yellow with transparency
                'land': (0, 77, 168, 200),     # Blue with transparency
                'plots': (255, 196, 0, 200),   # For layer name
                'lands': (0, 77, 168, 200)     # For layer name
            }
            
            # Draw features
            for layer_name, layer_data in decoded_data.items():
                features = layer_data.get('features', [])
                layer_color = colors.get(layer_name, (128, 128, 128, 200))
                
                for feature in features:
                    feature_type = feature.get('properties', {}).get('type', layer_name)
                    color = colors.get(feature_type, layer_color)
                    self._draw_mvt_feature(draw, feature, color)
            
            # Save as PNG
            return self.render_service._save_compressed_png(img, optimize_level=2)
            
        except Exception as e:
            logger.error(f"Error converting real estate MVT to PNG: {e}")
            return self.render_service.create_empty_tile()
    
    def _draw_mvt_feature(self, draw, feature, color):
        """Draw a single MVT feature on the image"""
        try:
            geometry = feature.get('geometry', {})
            geom_type = geometry.get('type', '')
            coordinates = geometry.get('coordinates', [])
            
            if geom_type == 'Polygon':
                for ring in coordinates:
                    if len(ring) >= 3:
                        # Convert coordinates to pixel coordinates (simplified)
                        pixels = [(int(coord[0] * 256 / 4096), int(coord[1] * 256 / 4096)) for coord in ring]
                        if len(pixels) >= 3:
                            draw.polygon(pixels, fill=color, outline=color)
            
            elif geom_type == 'Point':
                x, y = coordinates[0] * 256 / 4096, coordinates[1] * 256 / 4096
                draw.ellipse([x-2, y-2, x+2, y+2], fill=color, outline=color)
                
        except Exception as e:
            logger.error(f"Error drawing MVT feature: {e}")
    
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
        """Generate sample URLs for testing"""
        if not self.cloudfront_domain:
            return {}
        
        base_url = f"https://{self.cloudfront_domain}"
        mid_zoom = (min_zoom + max_zoom) // 2
        
        return {
            'city_tile_example': f"{base_url}/{city_slug}/combined/{mid_zoom}_2048_2048.png",
            'city_mvt_example': f"{base_url}/{city_slug}/combined/{mid_zoom}_2048_2048.mvt",
            'template_png': f"{base_url}/{city_slug}/combined/{{z}}_{{x}}_{{y}}.png",
            'template_mvt': f"{base_url}/{city_slug}/combined/{{z}}_{{x}}_{{y}}.mvt"
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test S3 connection and bucket access"""
        try:
            # Try to list objects in bucket
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                MaxKeys=1
            )
            
            return {
                'success': True,
                'bucket': self.bucket_name,
                'region': self.region,
                'cloudfront_domain': self.cloudfront_domain,
                'object_count': response.get('KeyCount', 0)
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                return {'success': False, 'error': f"Bucket '{self.bucket_name}' does not exist"}
            elif error_code == 'AccessDenied':
                return {'success': False, 'error': "Access denied - check AWS credentials"}
            else:
                return {'success': False, 'error': f"AWS Error: {error_code}"}
                
        except NoCredentialsError:
            return {'success': False, 'error': "AWS credentials not found"}
        except Exception as e:
            return {'success': False, 'error': str(e)}