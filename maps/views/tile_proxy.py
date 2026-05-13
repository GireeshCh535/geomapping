from ._imports import *

from maps.tile_debug import tile_debug, tile_route


def _fetch_tile_bytes(url, timeout=5):
    """HTTP GET tile body; used by tile proxy views (CDN or legacy origins)."""
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            n = len(response.content)
            tile_debug(f"fetch OK bytes={n} url={url[:200]}")
            return response.content
        tile_debug(f"fetch HTTP {response.status_code} url={url[:200]}")
    except Exception as e:
        tile_debug(f"fetch ERR url={url[:160]} err={e}")
    return None


@extend_schema(
    summary="Serve map tiles",
    description="Serve map tiles (PNG or MVT) via Django proxy: same URL for clients always; origin fetches tile bytes from the configured CDN/R2 host server-side (no redirect to CDN).",
    tags=['tiles'],
    parameters=[
        OpenApiParameter(
            name='state_slug',
            location=OpenApiParameter.PATH,
            description='State slug (e.g., karnataka)',
            required=True,
            type=str
        ),
        OpenApiParameter(
            name='city_slug',
            location=OpenApiParameter.PATH,
            description='City slug (e.g., bengaluru)',
            required=True,
            type=str
        ),
        OpenApiParameter(
            name='layer_slug',
            location=OpenApiParameter.PATH,
            description='Layer slug (e.g., master_plan_2015)',
            required=True,
            type=str
        ),
        OpenApiParameter(
            name='z',
            location=OpenApiParameter.PATH,
            description='Zoom level (0-22)',
            required=True,
            type=int
        ),
        OpenApiParameter(
            name='x',
            location=OpenApiParameter.PATH,
            description='Tile X coordinate',
            required=True,
            type=int
        ),
        OpenApiParameter(
            name='y',
            location=OpenApiParameter.PATH,
            description='Tile Y coordinate',
            required=True,
            type=int
        ),
    ],
    responses={
        200: {
            'description': 'Tile bytes (PNG or MVT) proxied from tile origin (CDN or S3)',
        },
        404: {
            'description': 'Tile or layer not found',
            'content': {
                'application/json': {
                    'example': {
                        'error': 'Layer not found: karnataka/bengaluru/master_plan',
                        'status': 'error'
                    }
                }
            }
        }
    },
    examples=[
        OpenApiExample(
            'PNG Tile',
            value='PNG tile image',
            description='Example: /api/tiles/karnataka/bengaluru/master_plan_2015/12/2048/2048.png'
        ),
        OpenApiExample(
            'MVT Tile',
            value='MVT tile data',
            description='Example: /api/tiles/karnataka/bengaluru/master_plan_2015/12/2048/2048.mvt'
        )
    ]
)
class CloudFrontTileView(APIView):
    """
    Tile serving API: proxy only; clients use this path on the app domain. Backend fetches bytes from PUBLIC_TILE_CDN_HOST internally.
    Requires API key (X-API-Key) when any active ApiKey exists; same as other API endpoints except webhooks.

    Serves tiles with hierarchical URL structure; client never sees backend URL:
    GET /api/tiles/<state_slug>/<city_slug>/<layer_slug>/<z>/<x>/<y>.png
    GET /api/tiles/<state_slug>/<city_slug>/<layer_slug>/<z>/<x>/<y>.mvt

    Examples:
    - /api/tiles/karnataka/bengaluru/bengaluru_master_plan_2015/12/2926/1899.png
    - /api/tiles/andhra-pradesh/visakhapatnam/master_plan/12/2048/2048.png
    - /api/tiles/telangana/hyderabad/rrr/12/2048/2048.mvt
    
    Backend URL comes from TilePathService (CDN or S3/CloudFront); tile body is cached (TILE_PROXY_CACHE_TTL).
    Layer existence is cached (5 min) to avoid DB hit per tile request.
    """
    
    # Class-level cache to track recently logged layer warnings (to reduce log spam)
    _layer_warning_cache = {}
    _layer_warning_cache_timeout = 300  # Log same layer warning at most once per 5 minutes
    # Cache TTL for "layer exists" / "layer missing" to avoid DB hit on every tile request
    _layer_cache_ttl = 300  # 5 minutes

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tile_path_service = TilePathService()

    def _layer_exists_cached(self, state_slug, city_slug, layer_slug):
        """Return True if layer exists, False otherwise. Uses Django cache to avoid DB hit per tile."""
        cache_key = f"tile_layer:v1:{state_slug}:{city_slug}:{layer_slug}"
        cached = cache.get(cache_key)
        if cached is not None:
            return bool(cached)
        layer = self._get_layer_by_hierarchy(state_slug, city_slug, layer_slug)
        exists = layer is not None
        cache.set(cache_key, "1" if exists else "0", self._layer_cache_ttl)
        return exists

    def _should_use_debug_proxy(self, request):
        """
        Reserved for optional ?proxy=1 debug behavior (ENABLE_TILE_PROXY_DEBUG).
        Normal traffic is always served via this view as a backend proxy.
        """
        proxy_requested = str(request.GET.get('proxy', '')).lower() in {'1', 'true', 'yes'}
        proxy_enabled = getattr(settings, 'ENABLE_TILE_PROXY_DEBUG', settings.DEBUG)
        return proxy_requested and proxy_enabled

    def _build_tile_response(self, tile_data, format_type):
        """Return tile bytes with headers (proxy response; backend not exposed)."""
        headers = self.tile_path_service.get_tile_cache_headers(format_type)
        response = HttpResponse(tile_data, content_type=headers['ContentType'])
        response['Cache-Control'] = headers['CacheControl']
        response['Pragma'] = headers['Pragma']
        response['Expires'] = headers['Expires']
        response['Access-Control-Allow-Origin'] = '*'
        return response

    def get(self, request, state_slug, city_slug, layer_slug, z, x, y):
        """Serve tiles via proxy (server-side fetch from tile CDN; no redirect to CDN)."""
        try:
            z, x, y = int(z), int(x), int(y)

            # Validate tile coordinates
            if not self.tile_path_service.validate_tile_coordinates(z, x, y):
                logger.warning(f"❌ Invalid tile coordinates: {z}/{x}/{y}")
                return self._return_error_tile("Invalid tile coordinates")

            # Determine format from URL
            format_type = 'png' if request.path.endswith('.png') else 'mvt'

            # Cached layer check (avoids DB hit per tile; cache TTL 5 min). Developer rasters skip DataLayer.
            if is_developer_data_tile_request(state_slug):
                if not developer_raster_path_valid(city_slug, layer_slug):
                    return self._return_error_tile("Invalid tile path")
            elif not self._layer_exists_cached(state_slug, city_slug, layer_slug):
                layer_key = f"{state_slug}/{city_slug}/{layer_slug}"
                import time
                current_time = time.time()
                last_logged = self._layer_warning_cache.get(layer_key, 0)
                if current_time - last_logged > self._layer_warning_cache_timeout:
                    logger.warning(f"❌ Layer not found: {layer_key} (will suppress similar warnings for 5 minutes)")
                    self._layer_warning_cache[layer_key] = current_time
                    if len(self._layer_warning_cache) > 1000:
                        cutoff_time = current_time - 3600
                        self._layer_warning_cache = {
                            k: v for k, v in self._layer_warning_cache.items()
                            if v > cutoff_time
                        }
                return self._return_error_tile(f"Layer not found: {state_slug}/{city_slug}/{layer_slug}")

            s3_key = self.tile_path_service.generate_s3_key(
                state_slug, city_slug, layer_slug, z, x, y, format_type
            )
            if s3_key.startswith("__invalid__/"):
                return self._return_error_tile("Invalid tile path")
            upstream = self.tile_path_service.generate_public_cdn_url(s3_key)
            cache_key = f"tile_proxy:{s3_key}"
            ttl = getattr(settings, 'TILE_PROXY_CACHE_TTL', 3600)
            if ttl > 0:
                cached = cache.get(cache_key)
                if cached is not None:
                    tile_route(
                        self.tile_path_service.format_tile_api_routing_for_log(
                            request.path, s3_key, upstream
                        )
                        + " | this_request=Django_tile_response_cache_HIT (no HTTP to CDN)"
                    )
                    tile_debug(
                        f"proxy HIT cache_key={cache_key[:120]} fmt={format_type} "
                        f"path={state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}"
                    )
                    return self._build_tile_response(cached, format_type)
            backend_url = self.tile_path_service.get_backend_url_for_tile(
                state_slug, city_slug, layer_slug, z, x, y, format_type
            )
            tile_route(
                self.tile_path_service.format_tile_api_routing_for_log(
                    request.path, s3_key, backend_url
                )
                + " | this_request=Django_HTTP_GET_to_tile_CDN (R2 objects behind CDN)"
            )
            tile_debug(
                f"proxy MISS fetch layer={state_slug}/{city_slug}/{layer_slug} "
                f"z={z} x={x} y={y} fmt={format_type} origin={backend_url[:200]}"
            )
            tile_data = self._fetch_url(backend_url)
            if tile_data:
                if ttl > 0:
                    try:
                        cache.set(cache_key, tile_data, ttl)
                    except Exception:
                        pass
                tile_debug(f"proxy OK bytes={len(tile_data)} s3_key={s3_key[:160]}")
                return self._build_tile_response(tile_data, format_type)
            tile_debug(f"proxy MISS bytes layer={state_slug}/{city_slug}/{layer_slug} key={s3_key[:160]}")
            return self._return_error_tile(
                f"Tile not found: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}"
            )
            
        except (OperationalError, DatabaseError) as e:
            error_msg = str(e)
            if "too many clients" in error_msg.lower():
                logger.error(f"❌ Database connection pool exhausted: {error_msg}")
                # Try to close old connections
                close_old_connections()
                return self._return_error_tile("Service temporarily unavailable. Please try again.")
            else:
                logger.error(f"❌ Database error serving tile: {error_msg}")
                return self._return_error_tile(f"Database error: {error_msg}")
        except Exception as e:
            logger.error(f"Error serving tile: {str(e)}")
            return self._return_error_tile(f"Error serving tile: {str(e)}")

    def _get_tile_with_fallback(self, state_slug, city_slug, layer_slug, z, x, y, format_type, layer):
        """Fetch tile from the public CDN; optional on-demand generation if enabled."""
        s3_key = self.tile_path_service.generate_s3_key(
            state_slug, city_slug, layer_slug, z, x, y, format_type
        )
        if s3_key.startswith("__invalid__/"):
            return None
        url = self.tile_path_service.get_backend_url_for_tile(
            state_slug, city_slug, layer_slug, z, x, y, format_type
        )
        tile_data = self._fetch_url(url)
        if tile_data:
            return tile_data
        if getattr(settings, 'ENABLE_ON_DEMAND_TILE_GENERATION', False):
            tile_data = self._generate_tile_on_demand(layer, z, x, y, format_type)
            if tile_data:
                return tile_data
        return None
    
    def _fetch_url(self, url, timeout=5):
        """Fetch data from URL with timeout"""
        return _fetch_tile_bytes(url, timeout=timeout)
    
    def _read_local_file(self, file_path):
        """Read tile from local file system (disabled)."""
        return None
    
    def _generate_tile_on_demand(self, layer, z, x, y, format_type):
        """Generate tile on-demand (optional feature)"""
        try:
            # This would integrate with your existing tile generation services
            # For now, return None to disable on-demand generation
            return None
        except Exception as e:
            logger.error(f"On-demand tile generation failed: {e}")
            return None
    
    def _get_layer_by_hierarchy(self, state_slug, city_slug, layer_slug):
        """Get layer by hierarchical path"""
        try:
            return DataLayer.objects.select_related('city', 'city__state_ref', 'category').get(
                city__slug=city_slug,
                city__state_ref__slug=state_slug,
                slug=layer_slug,
                city__is_active=True,
                city__state_ref__is_active=True
            )
        except DataLayer.DoesNotExist:
            return None
    
    def _return_error_tile(self, error_message):
        """Return an error response"""
        try:
            # Suppress logging for routine missing tile/layer errors to reduce log spam
            # These are normal in tile serving - not every tile coordinate has data
            if "Tile not found" not in error_message and "Layer not found" not in error_message:
                if "Invalid tile coordinates" in error_message:
                    # Invalid coordinates are worth logging but not as warning
                    logger.info(f"Invalid tile coordinates requested")
                else:
                    # Only log actual errors as warnings
                    logger.warning(f"❌ Returning error tile: {error_message}")
            
            return Response({
                'error': error_message,
                'status': 'error'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"❌ Error returning error tile: {str(e)}")
            return Response({
                'error': f'Error returning error tile: {str(e)}',
                'status': 'error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class S3DirectTileView(APIView):
    """
    Same proxy pattern as CloudFrontTileView: HTTP GET to the internal tile origin (CDN), not exposed as a redirect to the client.
    Requires API key (X-API-Key) when any active ApiKey exists; same as other API endpoints except webhooks.

    Hierarchical URL structure:
    GET /api/s3-tiles/<state_slug>/<city_slug>/<layer_slug>/<z>/<x>/<y>.png
    GET /api/s3-tiles/<state_slug>/<city_slug>/<layer_slug>/<z>/<x>/<y>.mvt
    
    Examples:
    - /api/s3-tiles/karnataka/bengaluru/bengaluru_master_plan_2015/12/2926/1899.png
    - /api/s3-tiles/andhra-pradesh/visakhapatnam/visakhapatnam_master_plan/12/2048/2048.png
    - /api/s3-tiles/telangana/hyderabad/rrr/12/2048/2048.mvt
    
    Layer existence is cached (5 min) to avoid DB hit per tile request.
    """
    
    _layer_warning_cache = {}
    _layer_warning_cache_timeout = 300
    _layer_cache_ttl = 300  # Same key/TTL as CloudFrontTileView for layer existence

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tile_path_service = TilePathService()

    def _layer_exists_cached(self, state_slug, city_slug, layer_slug):
        """Return True if layer exists, False otherwise. Uses same cache key as CloudFrontTileView."""
        cache_key = f"tile_layer:v1:{state_slug}:{city_slug}:{layer_slug}"
        cached = cache.get(cache_key)
        if cached is not None:
            return bool(cached)
        layer = self._get_layer_by_hierarchy(state_slug, city_slug, layer_slug)
        exists = layer is not None
        cache.set(cache_key, "1" if exists else "0", self._layer_cache_ttl)
        return exists

    def get(self, request, state_slug, city_slug, layer_slug, z, x, y):
        """Serve tile bytes from the public tile CDN (HTTP)."""
        try:
            z, x, y = int(z), int(x), int(y)
            
            if not self.tile_path_service.validate_tile_coordinates(z, x, y):
                logger.warning(f"❌ Invalid tile coordinates: {z}/{x}/{y}")
                return self._return_error_tile("Invalid tile coordinates")
            
            format_type = 'png' if request.path.endswith('.png') else 'mvt'
            
            if is_developer_data_tile_request(state_slug):
                if not developer_raster_path_valid(city_slug, layer_slug):
                    return self._return_error_tile("Invalid tile path")
            elif not self._layer_exists_cached(state_slug, city_slug, layer_slug):
                # Only log layer not found warnings occasionally to reduce log spam
                layer_key = f"{state_slug}/{city_slug}/{layer_slug}"
                import time
                current_time = time.time()
                
                # Check if we've logged this layer recently
                last_logged = self._layer_warning_cache.get(layer_key, 0)
                if current_time - last_logged > self._layer_warning_cache_timeout:
                    logger.warning(f"❌ Layer not found: {layer_key} (will suppress similar warnings for 5 minutes)")
                    self._layer_warning_cache[layer_key] = current_time
                    # Clean up old entries periodically (keep cache size manageable)
                    if len(self._layer_warning_cache) > 1000:
                        # Remove entries older than 1 hour
                        cutoff_time = current_time - 3600
                        self._layer_warning_cache = {
                            k: v for k, v in self._layer_warning_cache.items()
                            if v > cutoff_time
                        }
                
                return self._return_error_tile(f"Layer not found: {state_slug}/{city_slug}/{layer_slug}")
            
            url = self.tile_path_service.get_backend_url_for_tile(
                state_slug, city_slug, layer_slug, z, x, y, format_type
            )
            sk = self.tile_path_service.generate_s3_key(
                state_slug, city_slug, layer_slug, z, x, y, format_type
            )
            tile_route(
                self.tile_path_service.format_tile_api_routing_for_log(request.path, sk, url)
                + " | this_request=Django_HTTP_GET_to_tile_CDN_each_request (R2 via CDN)"
            )
            tile_debug(
                f"s3-direct fetch layer={state_slug}/{city_slug}/{layer_slug} "
                f"z={z} x={x} y={y} fmt={format_type} origin={url[:200]}"
            )
            tile_data = _fetch_tile_bytes(url)
            
            if tile_data:
                # Return the tile data with appropriate headers
                headers = self.tile_path_service.get_tile_cache_headers(format_type)
                response = HttpResponse(tile_data, content_type=headers['ContentType'])
                # response['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'
                response['Access-Control-Allow-Origin'] = '*'
                tile_debug(f"s3-direct OK bytes={len(tile_data)}")
                return response
            else:
                tile_debug(f"s3-direct MISS origin={state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
                return self._return_error_tile(f"Tile not found: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
            
        except (OperationalError, DatabaseError) as e:
            error_msg = str(e)
            if "too many clients" in error_msg.lower():
                logger.error(f"❌ Database connection pool exhausted: {error_msg}")
                # Try to close old connections
                close_old_connections()
                return self._return_error_tile("Service temporarily unavailable. Please try again.")
            else:
                logger.error(f"❌ Database error serving S3 direct tile: {error_msg}")
                return self._return_error_tile(f"Database error: {error_msg}")
        except Exception as e:
            logger.error(f"Error serving S3 direct tile: {str(e)}")
            return self._return_error_tile(f"Error serving tile: {str(e)}")
    
    def _get_layer_by_hierarchy(self, state_slug, city_slug, layer_slug):
        """Get layer by hierarchical path with connection error handling"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Close old connections before retry
                if retry_count > 0:
                    close_old_connections()
                
                return DataLayer.objects.select_related('city', 'city__state_ref', 'category').get(
                    city__slug=city_slug,
                    city__state_ref__slug=state_slug,
                    slug=layer_slug,
                    city__is_active=True,
                    city__state_ref__is_active=True
                )
            except DataLayer.DoesNotExist:
                return None
            except (OperationalError, DatabaseError) as e:
                retry_count += 1
                error_msg = str(e)
                
                # Check if it's a "too many clients" error
                if "too many clients" in error_msg.lower():
                    logger.warning(f"⚠️ Database connection pool exhausted (attempt {retry_count}/{max_retries}). Retrying...")
                    if retry_count >= max_retries:
                        logger.error(f"❌ Max retries reached for database connection. Error: {error_msg}")
                        raise
                    # Wait a bit before retrying
                    import time
                    time.sleep(0.1 * retry_count)  # Exponential backoff
                else:
                    # Other database errors - don't retry
                    logger.error(f"❌ Database error: {error_msg}")
                    raise
            except Exception as e:
                    logger.error(f"❌ Unexpected error in _get_layer_by_hierarchy: {str(e)}")
                    raise
        
        return None
    
    def _return_error_tile(self, error_message):
        """Return an error response"""
        try:
            # Suppress logging for routine missing tile/layer errors to reduce log spam
            # These are normal in tile serving - not every tile coordinate has data
            if "Tile not found" not in error_message and "Layer not found" not in error_message:
                if "Invalid tile coordinates" in error_message:
                    # Invalid coordinates are worth logging but not as warning
                    logger.info(f"Invalid tile coordinates requested")
                else:
                    # Only log actual errors as warnings
                    logger.warning(f"❌ Returning error tile: {error_message}")
            
            return Response({
                'error': error_message,
                'status': 'error'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"❌ Error returning error tile: {str(e)}")
            return Response({
                'error': f'Error returning error tile: {str(e)}',
                'status': 'error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
