# maps/caching.py - Advanced GIS Data Caching System
"""
High-performance caching system for large GIS datasets
Supports Redis, Database, and File-based caching with smart invalidation
"""

import json
import hashlib
import time
import gzip
from typing import Optional, Dict, Any, List
from django.core.cache import cache
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class GISCacheManager:
    """
    Advanced caching manager for GIS data with multiple backends and smart invalidation
    """
    
    def __init__(self):
        self.default_timeout = getattr(settings, 'GIS_CACHE_TIMEOUT', 3600 * 24)  # 24 hours
        self.compression_enabled = getattr(settings, 'GIS_CACHE_COMPRESSION', True)
        self.cache_prefix = 'gis_cache'
        
    def _generate_cache_key(self, cache_type: str, city_slug: str, **params) -> str:
        """Generate unique cache key based on parameters"""
        # Create deterministic hash from parameters
        param_string = json.dumps(params, sort_keys=True)
        param_hash = hashlib.md5(param_string.encode()).hexdigest()[:8]
        
        return f"{self.cache_prefix}:{cache_type}:{city_slug}:{param_hash}"
    
    def _compress_data(self, data: Any) -> bytes:
        """Compress data using gzip if enabled"""
        json_str = json.dumps(data, separators=(',', ':'))
        
        if self.compression_enabled:
            return gzip.compress(json_str.encode('utf-8'))
        return json_str.encode('utf-8')
    
    def _decompress_data(self, compressed_data: bytes) -> Any:
        """Decompress data"""
        if self.compression_enabled:
            try:
                json_str = gzip.decompress(compressed_data).decode('utf-8')
            except:
                # Fallback for uncompressed data
                json_str = compressed_data.decode('utf-8')
        else:
            json_str = compressed_data.decode('utf-8')
            
        return json.loads(json_str)
    
    def cache_city_complete(self, city_slug: str, data: Dict, **params) -> bool:
        """Cache complete city data with compression"""
        cache_key = self._generate_cache_key('city_complete', city_slug, **params)
        
        try:
            # Add metadata
            cache_data = {
                'data': data,
                'cached_at': timezone.now().isoformat(),
                'cache_version': '1.0',
                'feature_count': len(data.get('features', [])),
                'size_mb': len(json.dumps(data)) / (1024 * 1024)
            }
            
            compressed_data = self._compress_data(cache_data)
            
            # Store in cache
            success = cache.set(cache_key, compressed_data, timeout=self.default_timeout)
            
            if success:
                logger.info(f"✅ Cached city data: {city_slug} ({cache_data['feature_count']} features, "
                           f"{cache_data['size_mb']:.1f}MB)")
                
                # Store cache metadata for management
                self._store_cache_metadata(cache_key, city_slug, cache_data)
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Failed to cache city data for {city_slug}: {e}")
            return False
    
    def get_city_complete(self, city_slug: str, **params) -> Optional[Dict]:
        """Retrieve cached complete city data"""
        cache_key = self._generate_cache_key('city_complete', city_slug, **params)
        
        try:
            compressed_data = cache.get(cache_key)
            if compressed_data is None:
                return None
            
            cache_data = self._decompress_data(compressed_data)
            
            logger.info(f"🚀 Cache HIT for {city_slug} ({cache_data['feature_count']} features)")
            
            # Update access metadata
            self._update_cache_access(cache_key)
            
            return cache_data['data']
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve cached data for {city_slug}: {e}")
            return None
    
    def cache_progressive_chunk(self, city_slug: str, chunk_index: int, data: Dict, **params) -> bool:
        """Cache progressive loading chunks"""
        cache_key = self._generate_cache_key('progressive', city_slug, 
                                           chunk_index=chunk_index, **params)
        
        try:
            cache_data = {
                'data': data,
                'chunk_index': chunk_index,
                'cached_at': timezone.now().isoformat()
            }
            
            compressed_data = self._compress_data(cache_data)
            
            # Progressive chunks can have shorter TTL
            timeout = self.default_timeout // 2
            success = cache.set(cache_key, compressed_data, timeout=timeout)
            
            if success:
                feature_count = len(data.get('features', []))
                logger.info(f"✅ Cached progressive chunk {chunk_index} for {city_slug} ({feature_count} features)")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Failed to cache progressive chunk for {city_slug}: {e}")
            return False
    
    def get_progressive_chunk(self, city_slug: str, chunk_index: int, **params) -> Optional[Dict]:
        """Retrieve cached progressive chunk"""
        cache_key = self._generate_cache_key('progressive', city_slug, 
                                           chunk_index=chunk_index, **params)
        
        try:
            compressed_data = cache.get(cache_key)
            if compressed_data is None:
                return None
            
            cache_data = self._decompress_data(compressed_data)
            
            logger.info(f"🚀 Cache HIT for progressive chunk {chunk_index} of {city_slug}")
            
            return cache_data['data']
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve progressive chunk for {city_slug}: {e}")
            return None
    
    def cache_layer_features(self, city_slug: str, layer_slug: str, data: Dict, **params) -> bool:
        """Cache individual layer features"""
        cache_key = self._generate_cache_key('layer_features', city_slug, 
                                           layer_slug=layer_slug, **params)
        
        try:
            cache_data = {
                'data': data,
                'layer_slug': layer_slug,
                'cached_at': timezone.now().isoformat()
            }
            
            compressed_data = self._compress_data(cache_data)
            success = cache.set(cache_key, compressed_data, timeout=self.default_timeout)
            
            if success:
                feature_count = len(data.get('features', {}).get('features', []))
                logger.info(f"✅ Cached layer features: {layer_slug} ({feature_count} features)")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Failed to cache layer features for {layer_slug}: {e}")
            return False
    
    def get_layer_features(self, city_slug: str, layer_slug: str, **params) -> Optional[Dict]:
        """Retrieve cached layer features"""
        cache_key = self._generate_cache_key('layer_features', city_slug, 
                                           layer_slug=layer_slug, **params)
        
        try:
            compressed_data = cache.get(cache_key)
            if compressed_data is None:
                return None
            
            cache_data = self._decompress_data(compressed_data)
            
            logger.info(f"🚀 Cache HIT for layer {layer_slug} of {city_slug}")
            
            return cache_data['data']
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve cached layer for {layer_slug}: {e}")
            return None
    
    def invalidate_city_cache(self, city_slug: str) -> int:
        """Invalidate all cache entries for a city"""
        try:
            # Get all cache keys for this city
            pattern = f"{self.cache_prefix}:*:{city_slug}:*"
            
            # Note: This requires Redis backend for pattern-based deletion
            # For other backends, we'll need to track keys differently
            deleted_count = 0
            
            if hasattr(cache, 'delete_pattern'):
                # Redis backend with pattern support
                deleted_count = cache.delete_pattern(pattern)
            else:
                # Fallback: use metadata to track keys
                deleted_count = self._invalidate_by_metadata(city_slug)
            
            logger.info(f"🧹 Invalidated {deleted_count} cache entries for {city_slug}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ Failed to invalidate cache for {city_slug}: {e}")
            return 0
    
    def _store_cache_metadata(self, cache_key: str, city_slug: str, cache_data: Dict):
        """Store cache metadata for management"""
        metadata_key = f"{self.cache_prefix}:metadata:{city_slug}"
        
        try:
            # Get existing metadata
            metadata = cache.get(metadata_key, {})
            
            # Update metadata
            metadata[cache_key] = {
                'cached_at': cache_data['cached_at'],
                'feature_count': cache_data.get('feature_count', 0),
                'size_mb': cache_data.get('size_mb', 0),
                'access_count': 0,
                'last_accessed': None
            }
            
            # Store updated metadata (longer TTL)
            cache.set(metadata_key, metadata, timeout=self.default_timeout * 2)
            
        except Exception as e:
            logger.error(f"Failed to store cache metadata: {e}")
    
    def _update_cache_access(self, cache_key: str):
        """Update cache access statistics"""
        # Extract city from cache key
        parts = cache_key.split(':')
        if len(parts) >= 3:
            city_slug = parts[2]
            metadata_key = f"{self.cache_prefix}:metadata:{city_slug}"
            
            try:
                metadata = cache.get(metadata_key, {})
                if cache_key in metadata:
                    metadata[cache_key]['access_count'] = metadata[cache_key].get('access_count', 0) + 1
                    metadata[cache_key]['last_accessed'] = timezone.now().isoformat()
                    cache.set(metadata_key, metadata, timeout=self.default_timeout * 2)
            except Exception as e:
                logger.error(f"Failed to update cache access: {e}")
    
    def _invalidate_by_metadata(self, city_slug: str) -> int:
        """Invalidate cache using stored metadata"""
        metadata_key = f"{self.cache_prefix}:metadata:{city_slug}"
        
        try:
            metadata = cache.get(metadata_key, {})
            deleted_count = 0
            
            for cache_key in metadata.keys():
                if cache.delete(cache_key):
                    deleted_count += 1
            
            # Remove metadata
            cache.delete(metadata_key)
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to invalidate by metadata: {e}")
            return 0
    
    def get_cache_stats(self, city_slug: str) -> Dict:
        """Get cache statistics for a city"""
        metadata_key = f"{self.cache_prefix}:metadata:{city_slug}"
        
        try:
            metadata = cache.get(metadata_key, {})
            
            total_entries = len(metadata)
            total_features = sum(entry.get('feature_count', 0) for entry in metadata.values())
            total_size_mb = sum(entry.get('size_mb', 0) for entry in metadata.values())
            total_access_count = sum(entry.get('access_count', 0) for entry in metadata.values())
            
            return {
                'city': city_slug,
                'total_entries': total_entries,
                'total_features_cached': total_features,
                'total_size_mb': round(total_size_mb, 2),
                'total_access_count': total_access_count,
                'cache_entries': metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {'city': city_slug, 'error': str(e)}
    
    def warm_cache(self, city_slug: str, force: bool = False) -> Dict:
        """Pre-warm cache for a city"""
        from maps.views import CityCompleteView
        from maps.models import City
        
        try:
            city = City.objects.get(slug=city_slug, is_active=True)
            
            # Check if already cached
            if not force:
                cached_data = self.get_city_complete(city_slug)
                if cached_data:
                    return {
                        'status': 'already_cached',
                        'city': city_slug,
                        'feature_count': len(cached_data.get('features', []))
                    }
            
            # Create a mock request to get complete data
            view = CityCompleteView()
            
            # Generate complete data (this might take time for large datasets)
            logger.info(f"🔥 Warming cache for {city_slug}...")
            start_time = time.time()
            
            # Get all layers and generate complete response
            # This calls the existing _get_complete_geojson_response method
            from django.http import HttpRequest
            request = HttpRequest()
            request.GET = {'no_limits': 'true'}  # Force complete load
            
            response_data = view._get_complete_geojson_response(
                city, 
                city.layers.filter(is_processed=True), 
                sum(layer.feature_count or 0 for layer in city.layers.all()),
                request
            )
            
            # Cache the response
            if hasattr(response_data, 'data'):
                data = response_data.data
            else:
                data = response_data
            
            success = self.cache_city_complete(city_slug, data)
            
            end_time = time.time()
            duration = end_time - start_time
            
            return {
                'status': 'success' if success else 'failed',
                'city': city_slug,
                'feature_count': len(data.get('features', [])),
                'cache_duration_seconds': round(duration, 2),
                'size_mb': len(json.dumps(data)) / (1024 * 1024)
            }
            
        except Exception as e:
            logger.error(f"Failed to warm cache for {city_slug}: {e}")
            return {
                'status': 'error',
                'city': city_slug,
                'error': str(e)
            }

# Global cache manager instance
gis_cache = GISCacheManager()

# Decorator for automatic caching
def cache_gis_response(cache_type: str, timeout: Optional[int] = None):
    """Decorator to automatically cache GIS responses"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract parameters for cache key
            if len(args) > 1 and hasattr(args[1], 'path'):
                # This is a view method with request
                view_instance = args[0]
                request = args[1]
                
                # Extract city_slug from URL or kwargs
                city_slug = kwargs.get('city_slug') or getattr(view_instance, 'kwargs', {}).get('city_slug')
                
                if city_slug:
                    # Generate cache parameters from request
                    cache_params = dict(request.GET.items())
                    
                    # Try to get from cache first
                    if cache_type == 'city_complete':
                        cached_data = gis_cache.get_city_complete(city_slug, **cache_params)
                    elif cache_type == 'progressive':
                        chunk_index = cache_params.get('chunk', 0)
                        cached_data = gis_cache.get_progressive_chunk(city_slug, int(chunk_index), **cache_params)
                    else:
                        cached_data = None
                    
                    if cached_data:
                        # Return cached response
                        from rest_framework.response import Response
                        return Response(cached_data)
            
            # Cache miss - execute original function
            response = func(*args, **kwargs)
            
            # Cache the response if successful
            if hasattr(response, 'data') and hasattr(response, 'status_code') and response.status_code == 200:
                if city_slug:
                    if cache_type == 'city_complete':
                        gis_cache.cache_city_complete(city_slug, response.data, **cache_params)
                    elif cache_type == 'progressive':
                        chunk_index = cache_params.get('chunk', 0)
                        gis_cache.cache_progressive_chunk(city_slug, int(chunk_index), response.data, **cache_params)
            
            return response
        
        return wrapper
    return decorator