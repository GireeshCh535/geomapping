from ._imports import *

# ================================
# API VIEWS
# ================================

@extend_schema_view(
    get=extend_schema(
        summary="Search for data at specific coordinates",
        description="""
        Enhanced coordinate search API that finds which state, city, layer, and feature a coordinate belongs to.
        
        **Features:**
        - Search within a specific city or across all cities
        - Find exact matches (features containing the point)
        - Find nearby features within a specified radius
        - Get administrative boundary information
        - Comprehensive feature details including area, category, and styling
        
        **Use Cases:**
        - Interactive map click queries
        - Address validation and geocoding
        - Land use analysis at specific locations
        - Administrative boundary queries
        """,
        parameters=[
            OpenApiParameter(
                name='lat',
                location=OpenApiParameter.QUERY,
                description='Latitude coordinate (required)',
                required=True,
                type=float,
                examples=[
                    OpenApiExample(
                        'Bengaluru Example',
                        value=12.9716,
                        description='Bengaluru city center'
                    ),
                    OpenApiExample(
                        'Hyderabad Example',
                        value=17.3850,
                        description='Hyderabad city center'
                    )
                ]
            ),
            OpenApiParameter(
                name='lng',
                location=OpenApiParameter.QUERY,
                description='Longitude coordinate (required)',
                required=True,
                type=float,
                examples=[
                    OpenApiExample(
                        'Bengaluru Example',
                        value=77.5946,
                        description='Bengaluru city center'
                    ),
                    OpenApiExample(
                        'Hyderabad Example',
                        value=78.4867,
                        description='Hyderabad city center'
                    )
                ]
            ),
            OpenApiParameter(
                name='radius',
                location=OpenApiParameter.QUERY,
                description='Search radius in meters for nearby features (optional)',
                required=False,
                type=float,
                default=100,
                examples=[
                    OpenApiExample(
                        'Small radius',
                        value=50,
                        description='50 meters - very local search'
                    ),
                    OpenApiExample(
                        'Medium radius',
                        value=200,
                        description='200 meters - neighborhood search'
                    ),
                    OpenApiExample(
                        'Large radius',
                        value=1000,
                        description='1 kilometer - city-wide search'
                    )
                ]
            )
        ],
        responses={
            200: extend_schema(
                description="Successful search with data found",
                examples=[
                    OpenApiExample(
                        'Exact Match Found',
                        value={
                            "search_point": {
                                "latitude": 12.9716,
                                "longitude": 77.5946,
                                "coordinates": [77.5946, 12.9716],
                                "wkt": "POINT(77.5946 12.9716)"
                            },
                            "found": True,
                            "state": {
                                "slug": "karnataka",
                                "name": "Karnataka",
                                "code": "KA"
                            },
                            "city": {
                                "slug": "bengaluru",
                                "name": "Bengaluru",
                                "center_lat": 12.9716,
                                "center_lng": 77.5946,
                                "min_zoom": 8,
                                "max_zoom": 18
                            },
                            "features": [
                                {
                                    "feature_id": 123,
                                    "feature_name": "Commercial Zone A",
                                    "layer_slug": "bengaluru_commercial",
                                    "layer_name": "Commercial Zones",
                                    "color": "#FF0000",
                                    "area": {
                                        "square_meters": 5000.0,
                                        "square_kilometers": 0.005,
                                        "acres": 1.24
                                    },
                                    "zone_category": "Commercial",
                                    "plu_code": "C1",
                                    "plu_name": "General Commercial"
                                }
                            ],
                            "nearby_features": [],
                            "administrative_boundaries": {
                                "city_boundary": {
                                    "has_boundary": True,
                                    "area_sq_km": 741.0
                                }
                            },
                            "summary": "Location is within Commercial Zones: Commercial Zone A (Commercial)",
                            "search_scope": "city_specific",
                            "search_radius_meters": 100,
                            "status": "success",
                            "metadata": {
                                "search_timestamp": "2024-01-15T10:30:00Z",
                                "search_radius_meters": 100,
                                "total_features_found": 1,
                                "total_nearby_features": 0,
                                "api_version": "2.0"
                            }
                        }
                    ),
                    OpenApiExample(
                        'No Exact Match - Nearby Features Found',
                        value={
                            "search_point": {
                                "latitude": 12.9716,
                                "longitude": 77.5946,
                                "coordinates": [77.5946, 12.9716],
                                "wkt": "POINT(77.5946 12.9716)"
                            },
                            "found": False,
                            "state": {
                                "slug": "karnataka",
                                "name": "Karnataka",
                                "code": "KA"
                            },
                            "city": {
                                "slug": "bengaluru",
                                "name": "Bengaluru",
                                "center_lat": 12.9716,
                                "center_lng": 77.5946,
                                "min_zoom": 8,
                                "max_zoom": 18
                            },
                            "features": [],
                            "nearby_features": [
                                {
                                    "feature_id": 124,
                                    "feature_name": "Residential Zone B",
                                    "layer_slug": "bengaluru_residential",
                                    "layer_name": "Residential Zones",
                                    "color": "#00FF00",
                                    "area": {
                                        "square_meters": 3000.0,
                                        "square_kilometers": 0.003,
                                        "acres": 0.74
                                    },
                                    "distance_meters": 45.2
                                }
                            ],
                            "administrative_boundaries": {},
                            "summary": "No exact match. Nearest feature is Residential Zones (45.2m away)",
                            "search_scope": "city_specific",
                            "search_radius_meters": 100,
                            "status": "no_data_found",
                            "metadata": {
                                "search_timestamp": "2024-01-15T10:30:00Z",
                                "search_radius_meters": 100,
                                "total_features_found": 0,
                                "total_nearby_features": 1,
                                "api_version": "2.0"
                            }
                        }
                    )
                ]
            ),
            400: extend_schema(
                description="Bad request - missing or invalid parameters",
                examples=[
                    OpenApiExample(
                        'Missing Coordinates',
                        value={
                            "error": "Missing coordinates",
                            "message": "Please provide lat and lng parameters",
                            "example": "/api/cities/bengaluru/search-coords-test/?lat=12.9716&lng=77.5946&radius=200",
                            "parameters": {
                                "lat": "Latitude (required)",
                                "lng": "Longitude (required)",
                                "radius": "Search radius in meters (optional, default: 100)"
                            }
                        }
                    ),
                    OpenApiExample(
                        'Invalid Coordinates',
                        value={
                            "error": "Invalid coordinates",
                            "message": "Latitude must be between -90 and 90, longitude between -180 and 180"
                        }
                    )
                ]
            ),
            404: extend_schema(
                description="No data found at coordinates",
                examples=[
                    OpenApiExample(
                        'City Not Found',
                        value={
                            "error": "City not found: invalid_city",
                            "city": "invalid_city",
                            "timestamp": "2024-01-15T10:30:00Z"
                        }
                    )
                ]
            ),
            500: extend_schema(
                description="Internal server error",
                examples=[
                    OpenApiExample(
                        'Server Error',
                        value={
                            "error": "Failed to search coordinates",
                            "message": "Database connection error",
                            "timestamp": "2024-01-15T10:30:00Z"
                        }
                    )
                ]
            )
        },
        tags=['coordinate-search']
    )
)
class CoordinateSearchTestView(APIView):
    """
    Enhanced coordinate search that finds which state, city, layer, and feature a coordinate belongs to.
    
    URL: /api/cities/{city_slug}/search-coords-test/?lat={latitude}&lng={longitude}
    
    If city_slug is provided, searches only within that city.
    If no city_slug is provided, searches across all states and cities.
    
    Returns detailed information about the feature including:
    - State and city information
    - Layer details
    - Feature information (name, category, land use, etc.)
    - Geographic properties (area, color, etc.)
    - Administrative boundaries
    - Nearby features
    
    Optimized with:
    - Redis caching for repeated queries
    - Optimized spatial queries
    - Reduced database round trips
    """
    permission_classes = [AllowAny]
    
    # Cache settings
    CACHE_TTL = 300  # 5 minutes for successful results
    CACHE_TTL_EMPTY = 60  # 1 minute for empty results
    COORDINATE_PRECISION = 5  # Decimal places for cache key (roughly 1.1m precision)
    
    def _generate_cache_key(self, slug, lat, lng, radius):
        """Generate cache key with coordinate precision rounding"""
        # Round coordinates to reduce cache misses for nearby points
        rounded_lat = round(lat, self.COORDINATE_PRECISION)
        rounded_lng = round(lng, self.COORDINATE_PRECISION)
        rounded_radius = int(radius)
        
        key_string = f"coord_search:{slug or 'global'}:{rounded_lat}:{rounded_lng}:{rounded_radius}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, request, city_slug=None):
        try:
            # Get coordinates from query parameters
            lat = request.GET.get('lat')
            lng = request.GET.get('lng')
            radius = request.GET.get('radius', '0')  # Default 0m radius for exact point search
            
            if not lat or not lng:
                return Response({
                    'error': 'Missing coordinates',
                    'message': 'Please provide lat and lng parameters',
                    'example': f'/api/cities/{city_slug or "any"}/search-coords-test/?lat=12.9716&lng=77.5946&radius=0',
                    'parameters': {
                        'lat': 'Latitude (required)',
                        'lng': 'Longitude (required)',
                        'radius': 'Search radius in meters (optional, default: 0)'
                    }
                }, status=400)
            
            try:
                latitude = float(lat)
                longitude = float(lng)
                radius_meters = float(radius)
            except ValueError:
                return Response({
                    'error': 'Invalid parameter format',
                    'message': 'Coordinates and radius must be valid numbers'
                }, status=400)
            
            # Validate coordinate ranges
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                return Response({
                    'error': 'Invalid coordinates',
                    'message': 'Latitude must be between -90 and 90, longitude between -180 and 180'
                }, status=400)
            
            # Validate radius
            if radius_meters < 0 or radius_meters > 10000:
                return Response({
                    'error': 'Invalid radius',
                    'message': 'Radius must be between 0 and 10,000 meters'
                }, status=400)
            
            # Generate cache key
            cache_key = self._generate_cache_key(city_slug, latitude, longitude, radius_meters)
            
            # Try cache first
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                cached_result['metadata']['from_cache'] = True
                return Response(cached_result)
            
            # Create point geometry
            search_point = Point(longitude, latitude, srid=4326)
            
            # Search for features
            if city_slug:
                # Check if city_slug is actually a layer slug
                try:
                    city = City.objects.get(slug=city_slug)
                    # It's a valid city, do city-specific search
                    result = self._search_in_city(city_slug, search_point, latitude, longitude, radius_meters)
                except City.DoesNotExist:
                    # Not a city, try as a layer slug
                    try:
                        layer = DataLayer.objects.select_related('city', 'city__state_ref').get(slug=city_slug)
                        # It's a valid layer, do layer-specific search
                        result = self._search_in_layer(layer, search_point, latitude, longitude, radius_meters)
                    except DataLayer.DoesNotExist:
                        return Response({
                            'error': f'No city or layer found with slug: {city_slug}',
                            'city_slug': city_slug,
                            'timestamp': timezone.now().isoformat()
                        }, status=404)
            else:
                # Search across all states and cities
                result = self._search_across_all_cities(search_point, latitude, longitude, radius_meters)
            
            # When returning simple format (data + fill_color), strip default color from features and all_layer_data so client never sees it
            if isinstance(result, dict) and 'fill_color' in result:
                for feat_list_key in ('features', 'all_layer_data'):
                    for f in result.get(feat_list_key) or []:
                        if isinstance(f, dict):
                            f.pop('color', None)
                            dc = f.get('detailed_category') or {}
                            if isinstance(dc, dict) and 'layer_category' in dc and isinstance(dc.get('layer_category'), dict):
                                dc['layer_category'].pop('default_color', None)
            
            # Add metadata to response (simple format has 'data' + 'fill_color' but no 'features' list)
            total_found = len(result.get('features', []))
            if total_found == 0 and result.get('data') is not None and 'fill_color' in result:
                total_found = 1
            result['metadata'] = {
                'search_timestamp': timezone.now().isoformat(),
                'search_radius_meters': radius_meters,
                'total_features_found': total_found,
                'total_nearby_features': len(result.get('nearby_features', [])),
                'api_version': '2.0',
                'from_cache': False
            }
            
            # Cache the result
            # Use shorter TTL for empty results, longer for successful results
            ttl = self.CACHE_TTL_EMPTY if not result.get('found') and not result.get('features') else self.CACHE_TTL
            try:
                cache.set(cache_key, result, ttl)
            except Exception as e:
                logger.warning(f"Failed to cache result: {e}")
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error in CoordinateSearchTestView: {e}")
            return Response({
                'error': 'Failed to search coordinates',
                'message': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=500)
    
    def _search_in_city(self, city_slug, search_point, latitude, longitude, radius_meters):
        """Search for features within a specific city"""
        try:
            city = get_object_or_404(City, slug=city_slug, is_active=True)
            
            # Find containing features
            containing_features = self._find_containing_features(city, search_point)
            
            # Find nearby features if radius > 0
            nearby_features = []
            if radius_meters > 0:
                nearby_features = self._find_nearby_features(city, search_point, radius_meters)
            
            # Get administrative boundaries
            admin_boundaries = self._get_administrative_boundaries(city, search_point)
            
            # Build response
            response_data = {
                'search_point': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'coordinates': [longitude, latitude],
                    'wkt': f'POINT({longitude} {latitude})'
                },
                'found': len(containing_features) > 0,
                'state': {
                    'slug': city.state_ref.slug,
                    'name': city.state_ref.name,
                    'code': city.state_ref.code
                },
                'city': {
                    'slug': city_slug,
                    'name': city.name,
                    'center_lat': city.center_lat,
                    'center_lng': city.center_lng,
                    'min_zoom': city.min_zoom,
                    'max_zoom': city.max_zoom
                },
                'features': containing_features,
                'nearby_features': nearby_features[:10] if nearby_features else [],
                'administrative_boundaries': admin_boundaries,
                'summary': self._create_search_summary(containing_features, nearby_features),
                'search_scope': 'city_specific',
                'search_radius_meters': radius_meters
            }
            
            if not containing_features and not nearby_features:
                response_data['status'] = 'no_data_found'
                return response_data
            
            response_data['status'] = 'success'
            return response_data
            
        except City.DoesNotExist:
            return {
                'error': f'City not found: {city_slug}',
                'city': city_slug,
                'timestamp': timezone.now().isoformat(),
                'status': 'city_not_found'
            }
    
    def _search_across_all_cities(self, search_point, latitude, longitude, radius_meters):
        """Search for features across all states and cities"""
        try:
            # Find all features that contain the point
            # Optimized with field limiting and result cap
            features = GeoFeature.objects.filter(
                layer__city__is_active=True,
                layer__city__state_ref__is_active=True,
                layer__is_processed=True,
                is_valid=True,
                geometry__contains=search_point
            ).select_related(
                'layer',
                'layer__city',
                'layer__city__state_ref'
            ).only(
                'id', 'name', 'zone_category', 'zone_subcategory',
                'plu_primary_code', 'plu_secondary_1', 'plot_category',
                'symbology', 'area', 'properties', 'geometry',
                'layer__id', 'layer__slug', 'layer__name', 'layer__description',
                'layer__city__slug', 'layer__city__name',
                'layer__city__state_ref__slug', 'layer__city__state_ref__name', 'layer__city__state_ref__code'
            ).order_by('-area')[:20]  # Limit to top 20 features
            
            if not features.exists():
                # Try nearby search across all cities if radius > 0
                nearby_features = []
                if radius_meters > 0:
                    nearby_features = self._find_nearby_across_all_cities(search_point, radius_meters)
                
                return {
                    'search_point': {
                        'latitude': latitude,
                        'longitude': longitude,
                        'coordinates': [longitude, latitude],
                        'wkt': f'POINT({longitude} {latitude})'
                    },
                    'found': False,
                    'features': [],
                    'nearby_features': nearby_features[:15],
                    'summary': 'No features found at this location',
                    'search_scope': 'global',
                    'search_radius_meters': radius_meters,
                    'status': 'no_exact_match'
                }
            
            # Get the primary feature (largest by area)
            primary_feature = features.first()
            city = primary_feature.layer.city
            state = city.state_ref
            
            # Process all containing features
            containing_features = []
            for feature in features:
                feature_data = self._process_feature_data(feature)
                containing_features.append(feature_data)
            
            # Get administrative boundaries
            admin_boundaries = self._get_administrative_boundaries(city, search_point)
            
            return {
                'search_point': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'coordinates': [longitude, latitude],
                    'wkt': f'POINT({longitude} {latitude})'
                },
                'found': True,
                'state': {
                    'slug': state.slug,
                    'name': state.name,
                    'code': state.code
                },
                'city': {
                    'slug': city.slug,
                    'name': city.name,
                    'center_lat': city.center_lat,
                    'center_lng': city.center_lng,
                    'min_zoom': city.min_zoom,
                    'max_zoom': city.max_zoom
                },
                'features': containing_features,
                'nearby_features': [],
                'administrative_boundaries': admin_boundaries,
                'summary': self._create_search_summary(containing_features, []),
                'search_scope': 'global',
                'search_radius_meters': radius_meters,
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Error in global search: {e}")
            return Response({
                'error': 'Failed to search across all cities',
                'message': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=500)
    
    def _get_administrative_boundaries(self, city, search_point):
        """Get administrative boundary information for the search point"""
        try:
            admin_info = {}
            
            # Get city boundaries if available
            if hasattr(city, 'boundary') and city.boundary:
                admin_info['city_boundary'] = {
                    'has_boundary': True,
                    'area_sq_km': round(city.boundary.area * 111 * 111, 2) if city.boundary.area else None
                }
            
            # Get state boundaries if available
            if hasattr(city.state_ref, 'boundary') and city.state_ref.boundary:
                admin_info['state_boundary'] = {
                    'has_boundary': True,
                    'area_sq_km': round(city.state_ref.boundary.area * 111 * 111, 2) if city.state_ref.boundary.area else None
                }
            
            # Get nearby administrative features
            nearby_admin_features = GeoFeature.objects.filter(
                layer__city=city,
                layer__is_processed=True,
                is_valid=True,
                zone_category__icontains='boundary'
            ).filter(
                geometry__intersects=search_point.buffer(0.001)  # ~100m buffer
            )[:5]
            
            if nearby_admin_features.exists():
                admin_info['nearby_boundaries'] = []
                for feature in nearby_admin_features:
                    admin_info['nearby_boundaries'].append({
                        'name': feature.name or feature.zone_category,
                        'layer': feature.layer.name,
                        'distance_meters': round(search_point.distance(feature.geometry.centroid) * 111000, 1)
                    })
            
            return admin_info
            
        except Exception as e:
            logger.error(f"Error getting administrative boundaries: {e}")
            return {'error': str(e)}
    
    def _find_containing_features(self, city, point):
        """Find all features that contain or intersect with the search point (exact point, no buffer)"""
        containing_features = []
        
        # Query features that intersect with the exact point
        # Optimized with field limiting and result cap
        features = GeoFeature.objects.filter(
            layer__city=city,
            layer__is_processed=True,
            is_valid=True,
            geometry__intersects=point
        ).select_related(
            'layer', 'layer__city', 'layer__city__state_ref'
        ).only(
            'id', 'name', 'zone_category', 'zone_subcategory',
            'plu_primary_code', 'plu_secondary_1', 'plot_category',
            'symbology', 'area', 'properties', 'geometry',
            'layer__id', 'layer__slug', 'layer__name', 'layer__description',
            'layer__city__slug', 'layer__city__name',
            'layer__city__state_ref__slug', 'layer__city__state_ref__name'
        ).order_by('-area')[:20]  # Limit to top 20 features
        
        for feature in features:
            feature_data = self._process_feature_data(feature)
            containing_features.append(feature_data)
        
        return containing_features
    
    def _find_nearby_across_all_cities(self, point, radius_meters):
        """Find features near the search point across all cities"""
        nearby_features = []
        
        # Create a buffer around the point for nearby search
        buffer_point = point.transform(3857, clone=True)  # Web Mercator for distance
        buffered_area = buffer_point.buffer(radius_meters)
        buffered_area.transform(4326)  # Back to WGS84
        
        # Find features that intersect with the buffer across all cities
        features = GeoFeature.objects.filter(
            layer__city__is_active=True,
            layer__city__state_ref__is_active=True,
            layer__is_processed=True,
            is_valid=True,
            geometry__intersects=buffered_area
        ).select_related('layer', 'layer__city', 'layer__city__state_ref')
        
        for feature in features:
            try:
                # Calculate approximate distance
                feature_centroid = feature.geometry.centroid
                distance = point.distance(feature_centroid) * 111000  # Rough conversion to meters
                
                feature_data = self._process_feature_data(feature)
                feature_data['distance_meters'] = round(distance, 1)
                
                nearby_features.append(feature_data)
                
            except Exception as e:
                logger.error(f"Error processing nearby feature {feature.id}: {e}")
                continue
        
        # Sort by distance
        nearby_features.sort(key=lambda x: x.get('distance_meters', float('inf')))
        
        return nearby_features
    
    def _find_nearby_features(self, city, point, radius_meters=100):
        """Find features near the search point within a city"""
        nearby_features = []
        
        # Create a buffer around the point for nearby search
        buffer_point = point.transform(3857, clone=True)  # Web Mercator for distance
        buffered_area = buffer_point.buffer(radius_meters)
        buffered_area.transform(4326)  # Back to WGS84
        
        # Find features that intersect with the buffer
        # Optimized with field limiting and result cap
        features = GeoFeature.objects.filter(
            layer__city=city,
            layer__is_processed=True,
            is_valid=True,
            geometry__intersects=buffered_area
        ).select_related(
            'layer', 'layer__city', 'layer__city__state_ref'
        ).only(
            'id', 'name', 'zone_category', 'zone_subcategory',
            'plu_primary_code', 'plu_secondary_1', 'plot_category',
            'symbology', 'area', 'properties', 'geometry',
            'layer__id', 'layer__slug', 'layer__name',
            'layer__city__slug', 'layer__city__name',
            'layer__city__state_ref__slug', 'layer__city__state_ref__name'
        )[:10]  # Limit to 10 nearby features
        
        for feature in features:
            try:
                # Calculate approximate distance
                feature_centroid = feature.geometry.centroid
                distance = point.distance(feature_centroid) * 111000  # Rough conversion to meters
                
                feature_data = self._process_feature_data(feature)
                feature_data['distance_meters'] = round(distance, 1)
                
                nearby_features.append(feature_data)
                
            except Exception as e:
                logger.error(f"Error processing nearby feature {feature.id}: {e}")
                continue
        
        # Sort by distance
        nearby_features.sort(key=lambda x: x['distance_meters'])
        
        return nearby_features
    
    def _find_nearby_across_all_cities(self, point, radius_meters=1000):
        """Find nearby features across all cities"""
        nearby_features = []
        
        # Create a buffer around the point for nearby search
        buffer_point = point.transform(3857, clone=True)
        buffered_area = buffer_point.buffer(radius_meters)
        buffered_area.transform(4326)
        
        # Find features that intersect with the buffer
        features = GeoFeature.objects.filter(
            layer__city__is_active=True,
            layer__city__state_ref__is_active=True,
            layer__is_processed=True,
            is_valid=True,
            geometry__intersects=buffered_area
        ).select_related(
            'layer',
            'layer__city',
            'layer__city__state_ref'
        )
        
        for feature in features:
            try:
                # Calculate approximate distance
                feature_centroid = feature.geometry.centroid
                distance = point.distance(feature_centroid) * 111000
                
                feature_data = self._process_feature_data(feature)
                feature_data['distance_meters'] = round(distance, 1)
                feature_data['state'] = {
                    'slug': feature.layer.city.state_ref.slug,
                    'name': feature.layer.city.state_ref.name,
                    'code': feature.layer.city.state_ref.code
                }
                feature_data['city'] = {
                    'slug': feature.layer.city.slug,
                    'name': feature.layer.city.name,
                    'center_lat': feature.layer.city.center_lat,
                    'center_lng': feature.layer.city.center_lng
                }
                
                nearby_features.append(feature_data)
                
            except Exception as e:
                logger.error(f"Error processing global nearby feature {feature.id}: {e}")
                continue
        
        # Sort by distance
        nearby_features.sort(key=lambda x: x['distance_meters'])
        
        return nearby_features
    
    def _process_feature_data(self, feature):
        """Process feature data into a standardized format"""
        try:
            # Prefer per-feature color from properties (e.g. HEX in CRZ/tile data) so API matches tile generation
            props = getattr(feature, 'properties', None) or {}
            if isinstance(props, dict):
                hex_color = (
                    props.get('HEX') or props.get('fill_color') or props.get('fillColor') or
                    props.get('FillColor') or props.get('color') or props.get('stroke')
                )
                if hex_color and isinstance(hex_color, str) and hex_color.strip().startswith('#'):
                    layer_color = hex_color.strip()
                else:
                    layer_color = self._get_feature_color_from_config(feature, feature.layer.city.slug)
            else:
                layer_color = self._get_feature_color_from_config(feature, feature.layer.city.slug)
            
            # Get detailed category information
            category_info = self._get_detailed_category_info(feature)
            
            # Calculate area in different units
            area_sq_m = float(feature.area) if feature.area else 0.0
            area_sq_km = round(area_sq_m * 111 * 111, 6) if area_sq_m else 0.0
            area_acres = round(area_sq_m * 0.000247105, 4) if area_sq_m else 0.0
            
            feature_data = {
                'feature_id': feature.id,
                'feature_name': feature.name or 'Unnamed',
                'layer_slug': feature.layer.slug,
                'layer_name': feature.layer.name,
                'layer_description': feature.layer.description or '',
                'color': layer_color,
                'area': {
                    'square_meters': area_sq_m,
                    'square_kilometers': area_sq_km,
                    'acres': area_acres
                },
                'zone_category': feature.zone_category or '',
                'zone_subcategory': feature.zone_subcategory or '',
                'plu_code': feature.plu_primary_code or '',
                'plu_name': feature.plu_secondary_1 or '',
                'plot_category': feature.plot_category or '',
                'symbology': feature.symbology or '',
                'detailed_category': category_info,
                'geometry_type': feature.geometry.geom_type if feature.geometry else None,
                'is_valid': feature.is_valid,
                'created_at': feature.created_at.isoformat() if feature.created_at else None,
                'updated_at': feature.updated_at.isoformat() if feature.updated_at else None
            }
            
            return feature_data
            
        except Exception as e:
            logger.error(f"Error processing feature {feature.id}: {e}")
            return {
                'feature_id': feature.id,
                'feature_name': 'Error processing feature',
                'layer_slug': feature.layer.slug if feature.layer else 'unknown',
                'layer_name': feature.layer.name if feature.layer else 'Unknown',
                'color': '#FF0000',
                'area': {'square_meters': 0.0, 'square_kilometers': 0.0, 'acres': 0.0},
                'error': str(e)
            }
    
    def _get_detailed_category_info(self, feature):
        """Get detailed category information for a feature"""
        category_info = {}
        
        # Zone information
        if feature.zone_category:
            category_info['zone'] = {
                'category': feature.zone_category,
                'subcategory': feature.zone_subcategory or ''
            }
        
        # PLU (Primary Land Use) information
        if feature.plu_primary_code:
            category_info['plu'] = {
                'primary_code': feature.plu_primary_code,
                'secondary_1': feature.plu_secondary_1 or '',
                'secondary_2': feature.plu_secondary_2 or '',
                'proposed_use': feature.plu_proposed_use or ''
            }
        
        # Amaravati specific fields
        if feature.plot_category:
            category_info['plot_category'] = feature.plot_category
        
        if feature.symbology:
            category_info['symbology'] = feature.symbology
        
        # Get zone name using the model method
        category_info['zone_name'] = feature.get_zone_name()
        
        # Properties (if available)
        if hasattr(feature, 'properties') and feature.properties:
            category_info['properties'] = feature.properties
        
        return category_info
    
    def _get_feature_color_from_config(self, feature, city_slug):
        """Get feature color from configuration using existing system"""
        try:
            # Use the existing config system from your codebase
            from ..config import get_city_config
            
            category_code = feature.zone_category
            
            # Get city-specific color from config
            state_slug = feature.layer.city.state_ref.slug if feature.layer.city.state_ref else None
            city_config = get_city_config(state_slug, city_slug) if state_slug else None
            if city_config and 'colors' in city_config:
                color = city_config['colors'].get(category_code)
                if color:
                    return color
            
            # Fallback to layer style
            try:
                style = feature.layer.get_style()
                if isinstance(style, dict):
                    return style.get('fill_color', '') or ''
                elif hasattr(style, 'fill_color'):
                    return style.fill_color or ''
            except:
                pass
            
            if feature.layer.category:
                return feature.layer.category.default_color or ''
            
            return ''
            
        except Exception as e:
            logger.error(f"Error getting feature color: {e}")
            return ''
    
    def _create_search_summary(self, containing_features, nearby_features):
        """Create a human-readable summary of the search results"""
        
        if containing_features:
            if len(containing_features) == 1:
                feature = containing_features[0]
                label = (feature.get('zone_category') or '').strip() or feature['feature_name']
                return f"Location is within {feature['layer_name']}: {feature['feature_name']} ({label})"
            else:
                primary = containing_features[0]  # Largest by area
                label = (primary.get('zone_category') or '').strip() or primary['feature_name']
                return f"Location is within {primary['layer_name']}: {primary['feature_name']} ({label}). Also overlaps with {len(containing_features) - 1} other features."
            
        elif nearby_features:
            nearest = nearby_features[0]
            return f"No exact match. Nearest feature is {nearest['layer_name']} ({nearest['distance_meters']}m away)"
            
        else:
            return "No features found at this location"
    
    def _search_in_layer(self, layer, search_point, latitude, longitude, radius_meters):
        """Search for features within a specific layer"""
        try:
            # Check if this is a master plan layer (by checking if slug contains 'masterplan' or 'master_plan')
            is_masterplan = 'masterplan' in layer.slug.lower() or 'master_plan' in layer.slug.lower()
            
            # Check if this is a roads/linear layer
            is_road_layer = any(keyword in layer.slug.lower() for keyword in [
                'road', 'highway', 'metro', 'railway', 'rail', 'line',
                'expressway', 'corridor', 'bridge', 'sea_link'
            ])
            
            # No buffer for road layers, CRZ, or master plan - exact point containment only
            # Other layers use a small buffer to handle boundary tolerance
            is_crz = layer.slug in CRZ_SEARCH_LAYER_SLUGS
            if is_road_layer or is_crz or is_masterplan:
                search_geometry = search_point
            else:
                search_geometry = search_point.buffer(0.0001)  # ~10m buffer
            
            # Search for features in the specific layer that intersect with the point
            # Optimized query with field limiting and result cap
            # CRZ layer: order by area ascending (smallest first) so overlapping zones return the most specific (e.g. CRZ 1A not CRZ 4A sea)
            features_qs = GeoFeature.objects.filter(
                layer=layer,
                is_valid=True,
                geometry__intersects=search_geometry
            ).select_related(
                'layer', 'layer__city', 'layer__city__state_ref'
            ).only(
                'id', 'name', 'zone_category', 'zone_subcategory',
                'plu_primary_code', 'plu_secondary_1', 'plot_category',
                'symbology', 'area', 'properties', 'geometry',
                'layer__id', 'layer__slug', 'layer__name', 'layer__description',
                'layer__city__slug', 'layer__city__name',
                'layer__city__state_ref__slug', 'layer__city__state_ref__name'
            )
            if layer.slug in CRZ_SEARCH_LAYER_SLUGS:
                features = features_qs.order_by('area')[:20]  # Smallest containing polygon = most specific zone
            else:
                features = features_qs.order_by('-area')[:20]  # Largest first (default)
            
            if not features.exists():
                # Skip nearby search for layers that should only return exact matches
                # For polygon-based master plan layers, heritage sites, and CRZ layer - only exact coordinate match
                # But for road layers, we already used a buffer above, so if no results, truly nothing nearby
                is_polygon_masterplan = is_masterplan and not is_road_layer
                is_heritage_site = layer.slug in ['hyderabad_heritage_sites', 'bengaluru_heritage_sites']
                is_crz_layer = layer.slug in CRZ_SEARCH_LAYER_SLUGS
                
                if is_polygon_masterplan or is_heritage_site or is_crz_layer:
                    return {
                        'search_point': {
                            'latitude': latitude,
                            'longitude': longitude,
                            'coordinates': [longitude, latitude],
                            'wkt': f'POINT({longitude} {latitude})'
                        },
                        'found': False,
                        'layer': {
                            'slug': layer.slug,
                            'name': layer.name,
                            'city': layer.city.slug,
                            'city_name': layer.city.name,
                            'state': layer.city.state_ref.slug if layer.city.state_ref else '',
                            'state_name': layer.city.state_ref.name if layer.city.state_ref else ''
                        },
                        'features': [],
                        'nearby_features': [],
                        'administrative_boundaries': {},
                        'summary': 'No features found in the specified layer',
                        'search_scope': 'layer_specific',
                        'search_radius_meters': 0 if is_masterplan else radius_meters,
                        'status': 'no_data_found',
                        'all_layer_data': [],
                    }
                
                # If no exact intersection found, search for nearby features within 100m buffer
                # Skip this for all master plan layers and heritage sites - they should never reach here due to check above
                buffer_100m = search_point.buffer(0.0009)  # ~100m buffer (0.0009 degrees ≈ 100m)
                
                nearby_features = GeoFeature.objects.filter(
                    layer=layer,
                    is_valid=True,
                    geometry__intersects=buffer_100m
                ).select_related(
                    'layer', 'layer__city', 'layer__city__state_ref'
                ).only(
                    'id', 'name', 'zone_category', 'zone_subcategory',
                    'plu_primary_code', 'plu_secondary_1', 'plot_category',
                    'symbology', 'area', 'properties', 'geometry',
                    'layer__id', 'layer__slug', 'layer__name',
                    'layer__city__slug', 'layer__city__name',
                    'layer__city__state_ref__slug', 'layer__city__state_ref__name'
                ).annotate(
                    distance=Distance('geometry', search_point)
                ).order_by('distance')[:10]  # Limit to closest 10
                
                if nearby_features.exists():
                    # Found nearby features within 100m, return the closest one
                    closest_feature = nearby_features.first()
                    feature_data = self._process_feature_data(closest_feature)
                    
                    # Calculate distance in meters
                    # Use the distance method directly on the geometry
                    distance_degrees = closest_feature.geometry.distance(search_point)
                    distance_meters = distance_degrees * 111000  # Approximate conversion
                    
                    # Check if this is one of the special layers that need custom response
                    if layer.slug == 'bengaluru_strr':
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {})
                        
                        notation = properties.get('Notation', '')
                        current_status = properties.get('Current_St', '')
                        
                        # Return as comma-separated string
                        data_string = f"{notation}, Status: {current_status}"
                        fill_color = (
                            properties.get('fill_color') or properties.get('fillColor') or
                            properties.get('FillColor') or properties.get('color')
                        ) or ''
                        return {
                            'data': data_string,
                            'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
                            'all_layer_data': [feature_data],
                        }
                    
                    elif layer.slug == 'bengaluru_metro':
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {})
                        
                        linecolour = properties.get('linecolour', '')
                        name = properties.get('Name ', '') or properties.get('Name', '')
                        remarks = properties.get('remarks', '')
                        
                        # Format: "linecolour" + Line, name, Status: remarks
                        line_name = f"{linecolour} Line" if linecolour else "Line"
                        data_string = f"{line_name}, {name}, Status: {remarks}"
                        fill_color = (
                            properties.get('fill_color') or properties.get('fillColor') or
                            properties.get('FillColor') or properties.get('color')
                        ) or ''
                        return {
                            'data': data_string,
                            'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
                            'all_layer_data': [feature_data],
                        }
                    
                    elif layer.slug == 'hyderabad_metro':
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {})

                        name = properties.get('name', '')
                        status = properties.get('Status', '')
                        linecolour = properties.get('linecolour', '')
                        from_junct = properties.get('from_junct', '')
                        to_junct = properties.get('to_junct', '')

                        route_parts = []
                        if from_junct:
                            route_parts.append(from_junct)
                        if to_junct:
                            if route_parts:
                                route_parts.append('to')
                            route_parts.append(to_junct)
                        route = ' '.join(route_parts)

                        parts = []
                        if name:
                            parts.append(name)
                        if status:
                            parts.append(f"Status: {status}")
                        if linecolour:
                            parts.append(linecolour)
                        if route:
                            parts.append(route)
                        data_string = ', '.join(parts)
                        fill_color = (
                            properties.get('fill_color') or properties.get('fillColor') or
                            properties.get('FillColor') or properties.get('color')
                        ) or ''
                        return {
                            'data': data_string,
                            'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
                            'all_layer_data': [feature_data],
                        }
                    
                    elif layer.slug == 'bengaluru_highways':
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {})
                        
                        name = properties.get('Name', '')
                        notation = properties.get('Notation', '')
                        
                        # Format: "Name, Notation"
                        data_string = f"{name}, {notation}"
                        fill_color = (
                            properties.get('fill_color') or properties.get('fillColor') or
                            properties.get('FillColor') or properties.get('color')
                        ) or ''
                        return {
                            'data': data_string,
                            'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
                            'all_layer_data': [feature_data],
                        }
                    
                    elif layer.slug == 'hyderabad_highways':
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {})
                        
                        name = properties.get('Name', '')
                        notation = properties.get('Notation', '')
                        
                        # Format: "Name, Notation"
                        data_string = f"{name}, {notation}"
                        fill_color = (
                            properties.get('fill_color') or properties.get('fillColor') or
                            properties.get('FillColor') or properties.get('color')
                        ) or ''
                        return {
                            'data': data_string,
                            'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
                            'all_layer_data': [feature_data],
                        }
                    
                    elif layer.slug == 'bengaluru_masterplan_roads':
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {}) or {}
                        name = str(properties.get('Name', '')) if properties.get('Name') else ''
                        road_width_feet = properties.get('Road Width (in feet)')
                        road_width_meters = properties.get('Road Width (in meters)')
                        data_parts = []
                        if name:
                            data_parts.append(name)
                        if road_width_feet:
                            data_parts.append(f"Width : {str(road_width_feet)}ft")
                        elif road_width_meters:
                            data_parts.append(f"Width : {str(road_width_meters)}m")
                        data_string = ', '.join(data_parts) if data_parts else 'Masterplan Road'
                        fill_color = (
                            properties.get('fill_color') or properties.get('fillColor') or
                            properties.get('FillColor') or properties.get('color')
                        ) or ''
                        return {
                            'data': data_string,
                            'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
                            'all_layer_data': [feature_data],
                        }
                    
                    elif layer.slug == 'hyderabad_rrr':
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {})
                        
                        notation = properties.get('Notation', '')
                        alignment = properties.get('Alignment', '')
                        
                        # Format: "Proposed, Status: Alignment"
                        proposed_notation = f"Proposed {notation}" if notation else "Proposed"
                        data_string = f"{proposed_notation}, Status: {alignment}"
                        fill_color = (
                            properties.get('fill_color') or properties.get('fillColor') or
                            properties.get('FillColor') or properties.get('color')
                        ) or ''
                        return {
                            'data': data_string,
                            'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
                            'all_layer_data': [feature_data],
                        }
                    
                    elif layer.slug == 'hyderabad_ratan_tata_road':
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {})
                        
                        name = properties.get('Name', '')
                        
                        # Format: "Name"
                        data_string = name
                        fill_color = (
                            properties.get('fill_color') or properties.get('fillColor') or
                            properties.get('FillColor') or properties.get('color')
                        ) or ''
                        return {
                            'data': data_string,
                            'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
                            'all_layer_data': [feature_data],
                        }
                    
                    elif layer.slug == 'hyderabad_future_city':
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {})
                        
                        name = properties.get('Name', '')
                        
                        # Format: "Name"
                        if name:
                            data_string = name
                        else:
                            data_string = "Unknown"
                        fill_color = (
                            properties.get('fill_color') or properties.get('fillColor') or
                            properties.get('FillColor') or properties.get('color')
                        ) or ''
                        return {
                            'data': data_string,
                            'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
                            'all_layer_data': [feature_data],
                        }
                    
                    elif layer.slug == 'hyderabad_master_plan_roads':
                        detailed_category = feature_data.get('detailed_category', {}) or {}
                        properties = detailed_category.get('properties', {}) or {}
                        fill_color = '#2B2B2B'
                        detailed_category['properties'] = {
                            'Name': properties.get('Name'),
                            'Width_in_Metres': properties.get('Width_in_Metres'),
                        }
                        name = str(properties.get('Name', '')) if properties.get('Name') else ''
                        width_m = properties.get('Width_in_Metres')
                        data_parts = []
                        if name:
                            data_parts.append(name)
                        if width_m is not None:
                            data_parts.append(f"Width: {width_m}m")
                        data_string = ', '.join(data_parts) if data_parts else 'Master Plan Road'
                        return {
                            'data': data_string,
                            'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
                            'all_layer_data': [feature_data],
                        }
                    
                    # All CRZ layers (CRZ_SEARCH_LAYER_SLUGS): Name, Regulation Type, HEX; trim properties
                    elif layer.slug in CRZ_SEARCH_LAYER_SLUGS:
                        filter_crz_geojson_properties(feature_data)
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {}) or {}
                        name = properties.get('Name', '')
                        regulation_type = properties.get('Regulation Type', '')
                        data_string = f"{name}, {regulation_type}".strip(', ')
                        fill_color = properties.get('HEX', '') or ''
                        return {
                            'data': data_string,
                            'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
                            'all_layer_data': [feature_data],
                        }

                    # Vijayawada Metro LRT: compact `data` only (Name, Connecting Points, Status, Length)
                    elif layer.slug == 'vijayawada_metro_lrt':
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {}) or {}
                        data_string = vijayawada_metro_lrt_coordinate_search_popup_text(properties)
                        fill_color = (
                            properties.get('fill_color') or properties.get('fillColor') or
                            properties.get('FillColor') or properties.get('color') or
                            properties.get('stroke')
                        ) or ''
                        return {
                            'data': data_string,
                            'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
                            'all_layer_data': [feature_data],
                        }

                    # Proposed metro/LRT routes (GeoJSON: phase, length_km, stations, …) — before highway-only legend
                    elif is_transit_route_proposed_geojson(
                        (feature_data.get('detailed_category') or {}).get('properties') or {}
                    ):
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {}) or {}
                        data_string = transit_route_proposed_geojson_popup_text(properties)
                        fill_color = (
                            properties.get('fill_color') or properties.get('fillColor') or
                            properties.get('FillColor') or properties.get('color') or
                            properties.get('stroke')
                        ) or ''
                        return {
                            'data': data_string,
                            'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
                            'all_layer_data': [feature_data],
                        }

                    # Highways / corridors / coastal infra: legend popup (Name, ROW, lanes, connects)
                    elif layer.slug in HIGHWAY_INFRASTRUCTURE_POPUP_SLUGS:
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {}) or {}
                        data_string = highway_infra_legend_popup_text(properties)
                        return {
                            'data': data_string,
                            'fill_color': masterplan_fill_color_svg_data_uri('#000000'),
                            'found': True,
                            'features': [feature_data],
                            'all_layer_data': [feature_data],
                        }
                    
                    # Special handling for all air funnel zones layers (nearby features)
                    elif layer.slug in [
                        'bhubaneswar_air_funnel_zones'
                        'bengaluru_air_funnel_zones',
                        'hyderabad_air_funnel_zones',
                        'kozhikode_air_funnel_zones',
                        'ayodhya_air_funnel_zones',
                        'raipur_air_funnel_zones',
                        'ahmedabad_air_funnel_zones',
                        'warangal_air_funnel_zones',
                        'nagpur_air_funnel_zones',
                        'bhubaneshwar_air_funnel_zones',
                        'chennai_air_funnel_zones',
                        'delhi_air_funnel_zones',
                        'diu_air_funnel_zones',
                        'dholera_air_funnel_zones',
                        'guwahati_air_funnel_zones',
                        'jaipur_air_funnel_zones',
                        'tirupati_air_funnel_zones',
                        'kochi_air_funnel_zones',
                        'lucknow_air_funnel_zones',
                        'mumbai_air_funnel_zones',
                        'noida_air_funnel_zones',
                        'patna_air_funnel_zones',
                        'raigarh_air_funnel_zones'
                    ]:
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {}) or {}
                        height_value = properties.get('Pemissible Height', '') or properties.get('Permissible Height', '')
                        data_str = f"Permissible Height : {height_value}" if height_value else "Permissible Height : "
                        fill_color = (
                            properties.get('fill_color') or properties.get('fillColor') or
                            properties.get('FillColor') or properties.get('color')
                        ) or ''
                        return {
                            'data': data_str,
                            'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                            'all_layer_data': [feature_data],
                        }
                    
                    elif layer.slug in ['bengaluru_anekal_masterplan', 'bengaluru_chikkaballapura_masterplan', 'bengaluru_hosakote_masterplan', 'bengaluru_nelamangala_masterplan',
            'coimbatore_master_plan', 'hosur_master_plan', 'kochi_master_plan', 'chennai_master_plan',
            'tirupati_masterplan', 'cuttack_masterplan', 'vgtm_masterplan', 'kakinada_masterplan',
            'mandideep_masterplan', 'ajmer_masterplan', 'pithampur_masterplan', 'bhopal_masterplan',
            'varanasi_masterplan', 'ahmedabad_masterplan', 'vadodara_masterplan', 'gift_city_masterplan',
            'mohali_sas_nagar_masterplan', 'daman_and_diu_masterplan', 'patna_masterplan', 'ayodhya_masterplan',
            'lucknow_masterplan', 'srinagar_masterplan', 'guwahati_masterplan','dadra_and_nagar_haveli_masterplan',
            "kannur_masterplan", 'kollam_masterplan', 'kozhikode_masterplan', "derabassi_masterplan", 'banur_masterplan', 'mullanpur_masterplan', 'kharar_masterplan',
            'sonipat_kundli_masterplan', 'arogya_dham_badsa_masterplan', 'palwal_masterplan', 'prithla_masterplan', 'loni_masterplan', 'baghpat_baraut_khekra_masterplan', 'modinagar_masterplan', 'kharkhauda_masterplan', 'ghaziabad_masterplan',
            'pinjore_kalka_masterplan', 'panchkula_extension_1_masterplan', 'panchkula_masterplan', 'dharuhera_masterplan', 'zirakpur_masterplan', 'sonipat_masterplan', 'new_raipur_masterplan',
            'biaapa_masterplan', 'port_blair_masterplan', 'itanagar_masterplan', 'thiruvananthapuram_masterplan', 'thrissur_masterplan',
            'nuh_masterplan', 'jhajjar_masterplan', 'meerut_masterplan', 'hodal_masterplan', 'rewari_masterplan',
            'gohana_masterplan', 'bhiwadi_masterplan', 'alwar_masterplan',
            'mumbai_masterplan', 'pune_city_pmc_masterplan', 'pimpri_chinchwad_masterplan', 'pmrda-masterplan-pmrda_masterplan', 'nagpur_masterplan']:
                        # Return just the layer name as plain string
                        return {
                            'data': layer.slug,
                            'features': [],
                            'nearby_features': [],
                            'all_layer_data': [],
                        }
                    
                    elif layer.slug == 'bengaluru_master_plan_2015':
                        # Return just the feature name (Layer Name from properties)
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {})
                        layer_name = properties.get('Layer Name', '')
                        return {
                            'data': layer_name,
                            'all_layer_data': [feature_data],
                        }
                    
                    # Any layer: non-empty GeoJSON properties → labeled lines (new keys need no slug branch)
                    detailed_category = feature_data.get('detailed_category', {}) or {}
                    properties = detailed_category.get('properties', {}) or {}
                    data_string = generic_geojson_properties_popup_text(properties)
                    if data_string:
                        fill_color = (
                            properties.get('fill_color') or properties.get('fillColor') or
                            properties.get('FillColor') or properties.get('color') or
                            properties.get('stroke')
                        ) or ''
                        return {
                            'data': data_string,
                            'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
                            'all_layer_data': [feature_data],
                        }
                    
                    # For other layers, return the full feature data with distance info
                    return {
                        'search_point': {
                            'latitude': latitude,
                            'longitude': longitude,
                            'coordinates': [longitude, latitude],
                            'wkt': f'POINT({longitude} {latitude})'
                        },
                        'found': True,
                        'layer': {
                            'slug': layer.slug,
                            'name': layer.name,
                            'city': layer.city.slug,
                            'city_name': layer.city.name,
                            'state': layer.city.state_ref.slug if layer.city.state_ref else '',
                            'state_name': layer.city.state_ref.name if layer.city.state_ref else ''
                        },
                        'features': [feature_data],
                        'nearby_features': [],
                        'administrative_boundaries': {},
                        'summary': f'Found nearby feature within {round(distance_meters, 2)}m',
                        'search_scope': 'layer_specific',
                        'search_radius_meters': round(distance_meters, 2),
                        'status': 'success',
                        'all_layer_data': [feature_data],
                    }
                
                # No features found even within 100m buffer
                return {
                    'search_point': {
                        'latitude': latitude,
                        'longitude': longitude,
                        'coordinates': [longitude, latitude],
                        'wkt': f'POINT({longitude} {latitude})'
                    },
                    'found': False,
                    'layer': {
                        'slug': layer.slug,
                        'name': layer.name,
                        'city': layer.city.slug,
                        'city_name': layer.city.name,
                        'state': layer.city.state_ref.slug if layer.city.state_ref else '',
                        'state_name': layer.city.state_ref.name if layer.city.state_ref else ''
                    },
                    'features': [],
                    'nearby_features': [],
                    'administrative_boundaries': {},
                    'summary': 'No features found in the specified layer',
                    'search_scope': 'layer_specific',
                    'search_radius_meters': radius_meters,
                    'status': 'no_data_found',
                    'all_layer_data': [],
                }
            
            # Process found features
            containing_features = []
            for feature in features:
                feature_data = self._process_feature_data(feature)
                containing_features.append(feature_data)
            
            # Special handling for jagdalpur_masterplan - select correct feature when multiple overlap
            if layer.slug == 'jagdalpur_masterplan' and containing_features:
                # For jagdalpur, when multiple features overlap, use properties.Name as source of truth
                # All features should have consistent Name, PLU_2021, and zone_subcategory
                # When multiple features overlap, prioritize by data consistency and area
                # Roads are infrastructure that typically cover larger areas and should be prioritized
                # when they overlap with smaller land-use zones
                best_feature = None
                best_score = -1
                
                for feature_data in containing_features:
                    detailed_category = feature_data.get('detailed_category', {})
                    properties = detailed_category.get('properties', {}) or {}
                    zone_subcategory = feature_data.get('zone_subcategory', '')
                    plu_2021 = properties.get('PLU_2021', '')
                    name = properties.get('Name', '')
                    area = feature_data.get('area', {}).get('square_meters', 0)
                    
                    score = 0
                    
                    # Check data consistency - all three should match
                    if name and plu_2021 and zone_subcategory:
                        if name == plu_2021 == zone_subcategory:
                            score += 20  # Perfect consistency - highest priority
                        elif name == plu_2021:
                            score += 15  # Name and PLU match
                        elif name == zone_subcategory:
                            score += 15  # Name and filename match
                        elif plu_2021 == zone_subcategory:
                            score += 15  # PLU and filename match
                    
                    # For jagdalpur: Roads are infrastructure features that should be prioritized
                    # when they overlap with smaller land-use zones (Commercial, Residential)
                    # Roads typically have larger areas (> 50 sq meters)
                    if name == 'Existing Roads' or plu_2021 == 'Existing Roads':
                        score += 10  # Prioritize Roads when they overlap with other features
                    
                    # Prefer features with complete Name property
                    if name:
                        score += 1
                    
                    if score > best_score:
                        best_score = score
                        best_feature = feature_data
                
                # Reorder so the best feature is first
                if best_feature and best_feature != containing_features[0]:
                    containing_features.remove(best_feature)
                    containing_features.insert(0, best_feature)
            
            # Special handling for bengaluru_strr layer
            if layer.slug == 'bengaluru_strr' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                
                notation = properties.get('Notation', '')
                current_status = properties.get('Current_St', '')
                data_string = f"{notation}, Status: {current_status}"
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': data_string,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
                    'all_layer_data': containing_features,
                }
            
            # Special handling for bengaluru_metro layer
            if layer.slug == 'bengaluru_metro' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                
                linecolour = properties.get('linecolour', '')
                name = properties.get('Name ', '') or properties.get('Name', '')
                remarks = properties.get('remarks', '')
                line_name = f"{linecolour} Line" if linecolour else "Line"
                data_string = f"{line_name}, {name}, Status: {remarks}"
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': data_string,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
                    'all_layer_data': containing_features,
                }
            
            # Special handling for bengaluru_masterplan_roads
            if layer.slug == 'bengaluru_masterplan_roads' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}

                name = str(properties.get('Name', '')) if properties.get('Name') else ''
                road_width_feet = properties.get('Road Width (in feet)')
                road_width_meters = properties.get('Road Width (in meters)')
                data_parts = []
                if name:
                    data_parts.append(name)
                if road_width_feet:
                    data_parts.append(f"Width : {str(road_width_feet)}ft")
                elif road_width_meters:
                    data_parts.append(f"Width : {str(road_width_meters)}m")
                data_string = ', '.join(data_parts) if data_parts else 'Masterplan Road'
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                        'data': data_string,
                        'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                        'found': True,
                        'features': containing_features[:1],
                        'all_layer_data': containing_features,
                    }
            
            # Special handling for hyderabad_master_plan_roads - only Name and Width_in_Metres in properties, constant fill #2B2B2B
            if layer.slug == 'hyderabad_master_plan_roads' and containing_features:
                primary_feature = containing_features[0]
                fill_color = '#2B2B2B'
                for feat in containing_features:
                    dc = feat.get('detailed_category', {}) or {}
                    props = dc.get('properties', {}) or {}
                    dc['properties'] = {
                        'Name': props.get('Name'),
                        'Width_in_Metres': props.get('Width_in_Metres'),
                    }
                properties = (primary_feature.get('detailed_category') or {}).get('properties') or {}
                name = str(properties.get('Name', '')) if properties.get('Name') else ''
                width_m = properties.get('Width_in_Metres')
                data_parts = []
                if name:
                    data_parts.append(name)
                if width_m is not None:
                    data_parts.append(f"Width: {width_m}m")
                data_string = ', '.join(data_parts) if data_parts else 'Master Plan Road'
                return {
                    'data': data_string,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
                    'all_layer_data': containing_features,
                }
            
            if layer.slug == 'hyderabad_metro' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {})

                name = properties.get('name', '')
                status = properties.get('Status', '')
                linecolour = properties.get('linecolour', '')
                from_junct = properties.get('from_junct', '')
                to_junct = properties.get('to_junct', '')

                route_parts = []
                if from_junct:
                    route_parts.append(from_junct)
                if to_junct:
                    if route_parts:
                        route_parts.append('to')
                    route_parts.append(to_junct)
                route = ' '.join(route_parts)

                parts = []
                if name:
                    parts.append(name)
                if status:
                    parts.append(f"Status: {status}")
                if linecolour:
                    parts.append(linecolour)
                if route:
                    parts.append(route)
                data_string = ', '.join(parts)

                return {
                    'data': data_string,
                    'all_layer_data': containing_features,
                }

            # Special handling for bengaluru_highways layer
            if layer.slug == 'bengaluru_highways' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                
                name = properties.get('Name', '')
                notation = properties.get('Notation', '')
                data_string = f"{name}, {notation}"
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': data_string,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
                    'all_layer_data': containing_features,
                }
            
            # Special handling for hyderabad_highways layer
            if layer.slug == 'hyderabad_highways' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {})
                
                name = properties.get('Name', '')
                notation = properties.get('Notation', '')
                
                # Format: "Name, Notation"
                data_string = f"{name}, {notation}"
                
                return {
                    'data': data_string,
                    'all_layer_data': containing_features,
                }
            
            # Special handling for hyderabad_rrr layer
            if layer.slug == 'hyderabad_rrr' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {})
                
                notation = properties.get('Notation', '')
                alignment = properties.get('Alignment', '')
                
                # Format: "Proposed, Status: Alignment"
                proposed_notation = f"Proposed {notation}" if notation else "Proposed"
                data_string = f"{proposed_notation}, Status: {alignment}"
                
                return {
                    'data': data_string,
                    'all_layer_data': containing_features,
                }
            
            # Special handling for hyderabad_ratan_tata_road layer
            if layer.slug == 'hyderabad_ratan_tata_road' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {})
                
                name = properties.get('Name', '')
                
                # Format: "Name"
                data_string = name
                
                return {
                    'data': data_string,
                    'all_layer_data': containing_features,
                }
            
            # Special handling for hyderabad_future_city layer
            if layer.slug == 'hyderabad_hmda_extended_area':
                return {
                    'data': layer.name,
                    'all_layer_data': containing_features if containing_features else [],
                }

            # Special handling for hyderabad_masterplan - return data (name) and fill_color as SVG
            if layer.slug == 'hyderabad_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                name = properties.get('Name', '')
                fill_color = properties.get('fill_color', '') or properties.get('fillColor', '') or properties.get('FillColor', '') or properties.get('color', '')
                return {
                    'data': name,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }

            # Special handling for amaravati_master_plan - return data (plot_category/feature_name) and fill_color as SVG
            if layer.slug == 'amaravati_master_plan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                feature_name = (
                    primary_feature.get('feature_name') or
                    detailed_category.get('plot_category') or
                    properties.get('symbology') or properties.get('plot_categ') or
                    properties.get('Name') or properties.get('name', '') or
                    'Unknown'
                )
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': feature_name,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }

            if layer.slug == 'hyderabad_future_city' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                name = properties.get('Name', '') or 'Unknown'
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': name,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for all air funnel zones layers
            air_funnel_zones_layers = [
                'bhubaneswar_air_funnel_zones',
                'bengaluru_air_funnel_zones',
                'hyderabad_air_funnel_zones',
                'kozhikode_air_funnel_zones',
                'ayodhya_air_funnel_zones',
                'raipur_air_funnel_zones',
                'ahmedabad_air_funnel_zones',
                'warangal_air_funnel_zones',
                'nagpur_air_funnel_zones',
                'bhubaneshwar_air_funnel_zones',
                'chennai_air_funnel_zones',
                'delhi_air_funnel_zones',
                'diu_air_funnel_zones',
                'dholera_air_funnel_zones',
                'guwahati_air_funnel_zones',
                'jaipur_air_funnel_zones',
                'tirupati_air_funnel_zones',
                'kochi_air_funnel_zones',
                'lucknow_air_funnel_zones',
                'mumbai_air_funnel_zones',
                'noida_air_funnel_zones',
                'patna_air_funnel_zones',
                'raigarh_air_funnel_zones'
            ]
            
            if layer.slug in air_funnel_zones_layers and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                height_value = properties.get('Pemissible Height', '') or properties.get('Permissible Height', '')
                data_str = f"Permissible Height : {height_value}" if height_value else "Permissible Height : "
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': data_str,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }

            # Special handling for heritage site layers
            if layer.slug in ['hyderabad_heritage_sites', 'bengaluru_heritage_sites'] and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                mon_name = properties.get('mon_name', '')
                boundary_type = properties.get('boundary_type', '')
                data_string = f"{mon_name}, {boundary_type}".strip()
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': data_string,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for BMRDA boundary layers
            if layer.slug in ['bengaluru_anekal_masterplan', 'bengaluru_chikkaballapura_masterplan', 'bengaluru_hosakote_masterplan', 'bengaluru_nelamangala_masterplan',
            'coimbatore_master_plan', 'hosur_master_plan', 'kochi_master_plan', 'chennai_master_plan',
            'tirupati_masterplan', 'cuttack_masterplan', 'vgtm_masterplan', 'kakinada_masterplan',
            'mandideep_masterplan', 'ajmer_masterplan', 'pithampur_masterplan', 'bhopal_masterplan',
            'varanasi_masterplan', 'ahmedabad_masterplan', 'vadodara_masterplan', 'gift_city_masterplan',
            'mohali_sas_nagar_masterplan', 'daman_and_diu_masterplan', 'patna_masterplan', 'ayodhya_masterplan',
            'lucknow_masterplan', 'srinagar_masterplan', 'guwahati_masterplan','dadra_and_nagar_haveli_masterplan',
            "kannur_masterplan", 'kollam_masterplan', 'kozhikode_masterplan', "derabassi_masterplan", 'banur_masterplan', 'mullanpur_masterplan', 'kharar_masterplan',
            'sonipat_kundli_masterplan', 'arogya_dham_badsa_masterplan', 'palwal_masterplan', 'prithla_masterplan', 'loni_masterplan', 'baghpat_baraut_khekra_masterplan', 'modinagar_masterplan', 'kharkhauda_masterplan', 'ghaziabad_masterplan',
            'pinjore_kalka_masterplan', 'panchkula_extension_1_masterplan', 'panchkula_masterplan', 'dharuhera_masterplan', 'zirakpur_masterplan', 'panchkula_extension_1_masterplan', 'sonipat_masterplan', 'new_raipur_masterplan',
            'biaapa_masterplan', 'port_blair_masterplan', 'itanagar_masterplan', 'thiruvananthapuram_masterplan', 'thrissur_masterplan',
            'nuh_masterplan', 'jhajjar_masterplan', 'meerut_masterplan', 'hodal_masterplan', 'rewari_masterplan',
            'gohana_masterplan', 'bhiwadi_masterplan', 'alwar_masterplan',
            'mumbai_masterplan', 'pune_city_pmc_masterplan', 'pimpri_chinchwad_masterplan', 'pmrda_masterplan', 'nagpur_masterplan'] and containing_features:
                # Return just the layer name as plain string
                return {
                    'data': layer.slug,
                    'features': [],
                    'nearby_features': [],
                    'all_layer_data': containing_features,
                }
            
            # Special handling for bengaluru_master_plan_2015
            if layer.slug == 'bengaluru_master_plan_2015' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                layer_name = properties.get('Layer Name', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': layer_name,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
                    'all_layer_data': containing_features,
                }

            # Special handling for warangal_master_plan
            # Warangal: zone name in properties.PLU_NAME/PLU, fill_color in properties (from legend script)
            if layer.slug == 'warangal_master_plan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                layer_name = properties.get('PLU_NAME', '') or properties.get('PLU', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': layer_name,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for gurugram_masterplan
            if layer.slug == 'gurugram_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {})
                layer_value = properties.get('LAYER', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': layer_value,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for delhi_masterplan
            if layer.slug == 'delhi_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) 
                name = properties.get('NAME', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': name,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for noida_masterplan
            if layer.slug == 'noida_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {})
                ppt_full = properties.get('ppt_full', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': ppt_full,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for greater_noida_masterplan
            if layer.slug == 'greater_noida_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {})
                ppt_full = properties.get('ppt_full', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': ppt_full,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for yamuna_expressway_masterplan
            if layer.slug == 'yamuna_expressway_masterplan' and containing_features:
                layer_value = ''
                primary_feature = containing_features[0]
                for feature in containing_features:
                    detailed_category = feature.get('detailed_category', {})
                    properties = detailed_category.get('properties', {}) 
                    layer_val = properties.get('layer', '')
                    if layer_val:
                        layer_value = layer_val
                        primary_feature = feature
                        break
                properties = primary_feature.get('detailed_category', {}).get('properties', {}) or {}
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': layer_value,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for faridabad_masterplan
            if layer.slug == 'faridabad_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                layer_value = properties.get('LAYER', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': layer_value,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for amaravati_masterplan
            if layer.slug == 'amaravati_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                symbology = properties.get('symbology', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': symbology,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for bhubaneswar_masterplan
            if layer.slug == 'bhubaneswar_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                landuse = properties.get('LANDUSE', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': landuse,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for puducherry_masterplan
            if layer.slug == 'puducherry_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                landuse = properties.get('Landuse', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': landuse,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for chandigarh_masterplan (Chandigarh GeoJSON has no Name; use zone_subcategory from file name e.g. Residential, Commercial)
            if layer.slug == 'chandigarh_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                name = (
                    properties.get('Name') or
                    primary_feature.get('zone_subcategory') or
                    primary_feature.get('feature_name') or
                    primary_feature.get('zone_category') or
                    ''
                )
                if isinstance(name, str):
                    name = name.strip()
                else:
                    name = str(name).strip() if name else ''
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': name,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features,
                    'all_layer_data': containing_features,
                }
            
            # Special handling for rajnandgaon_masterplan
            if layer.slug == 'rajnandgaon_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                proposed_t = properties.get('PROPOSED_T', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': proposed_t,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for durg_bihlai_masterplan
            if layer.slug == 'durg_bihlai_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                zone_subcategory = primary_feature.get('zone_subcategory', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': zone_subcategory,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for jagdalpur_masterplan
            if layer.slug == 'jagdalpur_masterplan' and containing_features:
                # Return properties.Name as the primary source of truth
                # The feature selection logic above ensures we have the correct feature first
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                
                # Use properties.Name as primary source (most accurate)
                name = properties.get('Name', '')
                
                # Fallback to PLU_2021 if Name is missing
                if not name:
                    name = properties.get('PLU_2021', '')
                
                # Final fallback to zone_subcategory (filename)
                if not name:
                    name = primary_feature.get('zone_subcategory', '')
                
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': name,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for arang_masterplan
            if layer.slug == 'arang_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                elu_plu_up = properties.get('ELU_PLU_UP', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': elu_plu_up,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for mahasamund_masterplan
            if layer.slug == 'mahasamund_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                pro_lulc = properties.get('PRO_LULC', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': pro_lulc,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for balodabazaar_masterplan
            if layer.slug == 'balodabazaar_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                proposed_t = properties.get('PROPOSED_T', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': proposed_t,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for bhatapara_masterplan
            if layer.slug == 'bhatapara_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                proposed_t = properties.get('PROPOSED_T', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': proposed_t,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for raigarh_masterplan
            if layer.slug == 'raigarh_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                old_dp_plu = properties.get('OLD_DP_PLU', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': old_dp_plu,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for udaipur_masterplan
            # Udaipur: zone name in properties.LANDUSE_CA, fill_color in properties (from legend script)
            if layer.slug == 'udaipur_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                landuse_ca = properties.get('LANDUSE_CA', '') or properties.get('LANDUSE_CATEGORY', '')
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': landuse_ca,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'all_layer_data': containing_features,
                }
            
            # Special handling for jodhpur_masterplan
            # Jodhpur: zone name from LANDUSE_CATEGORY or Name (skip generic "Placemark"), fill_color from properties
            if layer.slug == 'jodhpur_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                name = (properties.get('Name', '') or properties.get('name', '') or '').strip()
                if not name or str(name).upper() == 'PLACEMARK':
                    name = (
                        properties.get('LANDUSE_CATEGORY', '') or properties.get('LANDUSE_SUBCAT_LEVEL_1', '') or
                        properties.get('LANDUSE_CA', '') or primary_feature.get('feature_name', '') or ''
                    ) or name
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': name or 'Placemark',
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
                    'all_layer_data': containing_features,
                }
            
            # Special handling for jaipur_masterplan
            # Jaipur: zone name in properties.LANDUSE_CATEGORY (or Name), fill_color in properties (from legend script)
            if layer.slug == 'jaipur_masterplan' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                landuse_category = (
                    properties.get('LANDUSE_CATEGORY', '') or properties.get('LANDUSE_SUBCAT_LEVEL_1', '') or
                    properties.get('LANDUSE_CA', '') or properties.get('Name', '') or properties.get('name', '')
                )
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': landuse_category or primary_feature.get('feature_name', ''),
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
                    'all_layer_data': containing_features,
                }

            # Special handling for visakhapatnam_master_plan / visakhapatnam_masterplan
            # fill_color comes from geojson_add_fill_color_from_legend.py (key: fill_color only)
            if layer.slug in ('visakhapatnam_master_plan', 'visakhapatnam_masterplan') and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                category = properties.get('Category', '')
                fill_color = (properties.get('fill_color') or '').strip() or ''
                return {
                    'data': category,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
                    'all_layer_data': containing_features,
                }
            
            # All CRZ layers: Name, Regulation Type, HEX; trim properties on each feature
            if layer.slug in CRZ_SEARCH_LAYER_SLUGS and containing_features:
                for fd in containing_features:
                    filter_crz_geojson_properties(fd)
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                name = properties.get('Name', '')
                regulation_type = properties.get('Regulation Type', '')
                data_string = f"{name}, {regulation_type}".strip(', ')
                fill_color = properties.get('HEX', '') or ''
                return {
                    'data': data_string,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
                    'all_layer_data': containing_features,
                }

            if layer.slug == 'vijayawada_metro_lrt' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                data_string = vijayawada_metro_lrt_coordinate_search_popup_text(properties)
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color') or properties.get('stroke')
                ) or ''
                return {
                    'data': data_string,
                    'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
                    'all_layer_data': containing_features,
                }

            if containing_features:
                primary_feature = containing_features[0]
                _props = (primary_feature.get('detailed_category') or {}).get('properties') or {}
                if is_transit_route_proposed_geojson(_props):
                    data_string = transit_route_proposed_geojson_popup_text(_props)
                    fill_color = (
                        _props.get('fill_color') or _props.get('fillColor') or
                        _props.get('FillColor') or _props.get('color') or _props.get('stroke')
                    ) or ''
                    return {
                        'data': data_string,
                        'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                        'found': True,
                        'features': containing_features[:1],
                        'all_layer_data': containing_features,
                    }

            if layer.slug in HIGHWAY_INFRASTRUCTURE_POPUP_SLUGS and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {}) or {}
                data_string = highway_infra_legend_popup_text(properties)
                return {
                    'data': data_string,
                    'fill_color': masterplan_fill_color_svg_data_uri('#000000'),
                    'found': True,
                    'features': containing_features[:1],
                    'all_layer_data': containing_features,
                }
            
            # Any layer: non-empty GeoJSON properties → labeled lines (new keys need no slug branch)
            if containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {}) or {}
                properties = detailed_category.get('properties', {}) or {}
                data_string = generic_geojson_properties_popup_text(properties)
                if data_string:
                    fill_color = (
                        properties.get('fill_color') or properties.get('fillColor') or
                        properties.get('FillColor') or properties.get('color') or
                        properties.get('stroke')
                    ) or ''
                    return {
                        'data': data_string,
                        'fill_color': masterplan_fill_color_svg_data_uri(fill_color),
                        'found': True,
                        'features': containing_features[:1],
                        'all_layer_data': containing_features,
                    }
            
            # Generate summary
            if containing_features:
                primary_feature = containing_features[0]
                label = (primary_feature.get('zone_category') or '').strip() or primary_feature['feature_name']
                summary = f"Location is within {layer.name}: {primary_feature['feature_name']} ({label})"
                if len(containing_features) > 1:
                    summary += f". Also overlaps with {len(containing_features) - 1} other features."
            else:
                summary = "No features found in the specified layer"
            
            return {
                'search_point': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'coordinates': [longitude, latitude],
                    'wkt': f'POINT({longitude} {latitude})'
                },
                'found': True,
                'layer': {
                    'slug': layer.slug,
                    'name': layer.name,
                    'city': layer.city.slug,
                    'city_name': layer.city.name,
                    'state': layer.city.state_ref.slug if layer.city.state_ref else '',
                    'state_name': layer.city.state_ref.name if layer.city.state_ref else ''
                },
                'features': containing_features,
                'nearby_features': [],
                'administrative_boundaries': {},
                'summary': summary,
                'search_scope': 'layer_specific',
                'search_radius_meters': radius_meters,
                'status': 'success',
                'all_layer_data': containing_features,
            }
            
        except Exception as e:
            logger.error(f"Error in _search_in_layer: {e}")
            return {
                'search_point': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'coordinates': [longitude, latitude],
                    'wkt': f'POINT({longitude} {latitude})'
                },
                'found': False,
                'error': f'Error searching layer: {str(e)}',
                'layer': {
                    'slug': layer.slug,
                    'name': layer.name,
                    'city': layer.city.slug,
                    'city_name': layer.city.name,
                    'state': layer.city.state_ref.slug if layer.city.state_ref else '',
                    'state_name': layer.city.state_ref.name if layer.city.state_ref else ''
                },
                'features': [],
                'nearby_features': [],
                'administrative_boundaries': {},
                'summary': f'Error searching layer: {str(e)}',
                'search_scope': 'layer_specific',
                'search_radius_meters': radius_meters,
                'status': 'error',
                'all_layer_data': [],
            }
        
