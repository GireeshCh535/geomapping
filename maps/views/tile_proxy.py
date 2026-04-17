from ._imports import *

@extend_schema(
    summary="Serve map tiles",
    description="Serve map tiles (PNG or MVT) via Django proxy: fetches from S3 (optional CloudFront if USE_CLOUDFRONT and path whitelist).",
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
            'description': 'Tile bytes (PNG or MVT) proxied from S3',
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
    Tile serving API: proxy only (S3 by default; optional CloudFront; server-side cache).
    Requires API key (X-API-Key) when any active ApiKey exists; same as other API endpoints except webhooks.

    Serves tiles with hierarchical URL structure; client never sees backend URL:
    GET /api/tiles/<state_slug>/<city_slug>/<layer_slug>/<z>/<x>/<y>.png
    GET /api/tiles/<state_slug>/<city_slug>/<layer_slug>/<z>/<x>/<y>.mvt

    Examples:
    - /api/tiles/karnataka/bengaluru/bengaluru_master_plan_2015/12/2926/1899.png
    - /api/tiles/andhra-pradesh/visakhapatnam/master_plan/12/2048/2048.png
    - /api/tiles/telangana/hyderabad/rrr/12/2048/2048.mvt
    
    Backend is S3 by default; tile body is cached (TILE_PROXY_CACHE_TTL).
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
        """Serve tiles via proxy (path-based CloudFront or S3; server-side cache). No redirects."""
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
                else:
                    logger.debug(f"❌ Layer not found (suppressed): {layer_key}")
                return self._return_error_tile(f"Layer not found: {state_slug}/{city_slug}/{layer_slug}")

            s3_key = self.tile_path_service.generate_s3_key(
                state_slug, city_slug, layer_slug, z, x, y, format_type
            )
            if s3_key.startswith("__invalid__/"):
                return self._return_error_tile("Invalid tile path")
            cache_key = f"tile_proxy:{s3_key}"
            ttl = getattr(settings, 'TILE_PROXY_CACHE_TTL', 3600)
            if ttl > 0:
                cached = cache.get(cache_key)
                if cached is not None:
                    return self._build_tile_response(cached, format_type)
            # Whitelisted keys: CloudFront then S3 (per TILE_SERVING_FALLBACK_ORDER). Others: S3 only.
            use_cf = self.tile_path_service.use_cloudfront_for_path(s3_key)
            candidates = []
            if use_cf:
                fallback_order = getattr(
                    settings, 'TILE_SERVING_FALLBACK_ORDER', ['cloudfront', 's3_direct']
                ) or ['cloudfront', 's3_direct']
                for source in fallback_order:
                    if source == 'cloudfront':
                        candidates.append(('CloudFront', self.tile_path_service.generate_cloudfront_url(
                            state_slug, city_slug, layer_slug, z, x, y, format_type
                        )))
                    elif source == 's3_direct':
                        candidates.append(('S3', self.tile_path_service.generate_s3_url(
                            state_slug, city_slug, layer_slug, z, x, y, format_type
                        )))
            else:
                candidates.append(('S3', self.tile_path_service.generate_s3_url(
                    state_slug, city_slug, layer_slug, z, x, y, format_type
                )))

            tile_data = None
            for backend_label, backend_url in candidates:
                # print(f"[tile_proxy] Serving from {backend_label}: {backend_url}")
                tile_data = self._fetch_url(backend_url)
                if tile_data:
                    break
            if tile_data:
                if ttl > 0:
                    try:
                        cache.set(cache_key, tile_data, ttl)
                    except Exception:
                        pass
                return self._build_tile_response(tile_data, format_type)
            # print(f"[tile_proxy] fetch FAIL ({backend_label}): {s3_key}")
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
        """
        CloudFront first only for CLOUDFRONT_PATH_PREFIXES keys; then S3; optional on-demand.
        """
        
        s3_key = self.tile_path_service.generate_s3_key(
            state_slug, city_slug, layer_slug, z, x, y, format_type
        )
        if s3_key.startswith("__invalid__/"):
            return None
        if self.tile_path_service.use_cloudfront_for_path(s3_key):
            cloudfront_url = self.tile_path_service.generate_cloudfront_url(
                state_slug, city_slug, layer_slug, z, x, y, format_type
            )
            logger.debug(f"🔍 Trying CloudFront: {cloudfront_url}")
            tile_data = self._fetch_url(cloudfront_url)
            if tile_data:
                logger.debug(f"✅ Served from CloudFront: {cloudfront_url}")
                return tile_data

        s3_url = self.tile_path_service.generate_s3_url(
            state_slug, city_slug, layer_slug, z, x, y, format_type
        )
        logger.debug(f"🔍 Trying S3 Direct: {s3_url}")
        tile_data = self._fetch_url(s3_url)
        if tile_data:
            logger.debug(f"✅ Served from S3: {s3_url}")
            return tile_data
        
        # 3. Generate on-demand (optional - can be disabled for performance)
        if getattr(settings, 'ENABLE_ON_DEMAND_TILE_GENERATION', False):
            logger.debug(f"🔍 Trying on-demand generation for {z}/{x}/{y}.{format_type}")
            tile_data = self._generate_tile_on_demand(layer, z, x, y, format_type)
            if tile_data:
                logger.debug(f"✅ Generated on-demand: {z}/{x}/{y}.{format_type}")
                return tile_data
        
        logger.debug(f"❌ Tile not found from any source: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
        return None
    
    def _fetch_url(self, url, timeout=5):
        """Fetch data from URL with timeout"""
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                return response.content
            else:
                logger.debug(f"Failed to fetch {url}: HTTP {response.status_code}")
        except Exception as e:
            logger.debug(f"Failed to fetch {url}: {e}")
        return None
    
    def _read_local_file(self, file_path):
        """Read tile from local file system (disabled - S3/CloudFront only)"""
        # Local file reading disabled - using S3/CloudFront only
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
            if "Tile not found" in error_message or "Layer not found" in error_message:
                # Already logged at appropriate level above, don't log again here
                logger.debug(f"Returning 404 for: {error_message[:100]}")
            elif "Invalid tile coordinates" in error_message:
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
    S3 Direct Tile Serving API.
    Requires API key (X-API-Key) when any active ApiKey exists; same as other API endpoints except webhooks.

    Serves tiles directly from S3 with hierarchical URL structure:
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
        self.s3_client = boto3.client(
            's3',
            region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'ap-south-1'),
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        )
        self.bucket_name = 'gis-portal-layers'

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
        """Serve tiles directly from S3"""
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
                else:
                    # Log at debug level for subsequent requests
                    logger.debug(f"❌ Layer not found (suppressed): {layer_key}")
                
                return self._return_error_tile(f"Layer not found: {state_slug}/{city_slug}/{layer_slug}")
            
            logger.debug(f"🔍 Serving S3 direct tile: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
            
            # Get tile directly from S3
            tile_data = self._get_tile_from_s3(state_slug, city_slug, layer_slug, z, x, y, format_type)
            
            if tile_data:
                # Return the tile data with appropriate headers
                headers = self.tile_path_service.get_tile_cache_headers(format_type)
                response = HttpResponse(tile_data, content_type=headers['ContentType'])
                # response['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'
                response['Access-Control-Allow-Origin'] = '*'
                logger.debug(f"✅ Successfully served S3 direct tile: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
                return response
            else:
                logger.debug(f"❌ Tile not found in S3: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
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
    
    def _get_tile_from_s3(self, state_slug, city_slug, layer_slug, z, x, y, format_type):
        """
        Get tile directly from S3 bucket
        """
        try:
            s3_key = self.tile_path_service.generate_s3_key(
                state_slug, city_slug, layer_slug, z, x, y, format_type
            )
            if s3_key.startswith("__invalid__/"):
                return None
            
            logger.debug(f"🔍 Fetching from S3: s3://{self.bucket_name}/{s3_key}")
            
            # Get object from S3
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            # Read the tile data
            tile_data = response['Body'].read()
            
            if tile_data:
                logger.debug(f"✅ Successfully fetched from S3: s3://{self.bucket_name}/{s3_key}")
                return tile_data
            else:
                logger.debug(f"❌ Empty tile data from S3: s3://{self.bucket_name}/{s3_key}")
                return None
                
        except self.s3_client.exceptions.NoSuchKey:
            logger.debug(f"❌ Tile not found in S3: s3://{self.bucket_name}/{s3_key}")
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching from S3: s3://{self.bucket_name}/{s3_key} - {str(e)}")
            return None
    
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
            if "Tile not found" in error_message or "Layer not found" in error_message:
                # Already logged at appropriate level above, don't log again here
                logger.debug(f"Returning 404 for: {error_message[:100]}")
            elif "Invalid tile coordinates" in error_message:
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
