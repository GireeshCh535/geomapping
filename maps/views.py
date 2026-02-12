from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Prefetch
from django.db import connection, close_old_connections
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.conf import settings
from django.core.cache import cache
import hashlib
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.db.models.functions import Distance
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from .models import *
from .serializers import *
from .tile_path_service import TilePathService
import copy
import logging
import json
from urllib.parse import quote
import boto3
import requests
import psycopg2
from psycopg2 import OperationalError, DatabaseError

logger = logging.getLogger(__name__)

# SVG template for master plan fill color indicator (use {color} placeholder)
MASTERPLAN_FILL_COLOR_SVG = (
    '<svg width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">'
    '<rect x="0" y="0" width="16" height="16" rx="4" ry="4" fill="{color}"/>'
    '</svg>'
)


def _masterplan_fill_color_svg_data_uri(hex_color):
    """Return SVG as a data URI so frontend can use in <img src={fill_color} /> without JSON escaping issues."""
    if not hex_color:
        return ''
    svg_str = MASTERPLAN_FILL_COLOR_SVG.format(color=hex_color)
    return f"data:image/svg+xml,{quote(svg_str)}"

# ================================
# VIEWSETS (Router endpoints)
# ================================

@extend_schema_view(
    list=extend_schema(
        summary="List all states",
        description="Retrieve a list of all active states",
        tags=['states']
    ),
    retrieve=extend_schema(
        summary="Get state details",
        description="Retrieve detailed information about a specific state",
        tags=['states']
    )
)
class StateViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for states"""
    queryset = State.objects.filter(is_active=True)
    serializer_class = StateSerializer
    lookup_field = 'slug'

@extend_schema_view(
    list=extend_schema(
        summary="List all layer groups",
        description="Retrieve a list of all layer groups",
        tags=['layers']
    ),
    retrieve=extend_schema(
        summary="Get layer group details",
        description="Retrieve detailed information about a specific layer group",
        tags=['layers']
    )
)
class LayerGroupViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for layer groups"""
    queryset = LayerGroup.objects.all()
    serializer_class = LayerGroupSerializer
    lookup_field = 'slug'

@extend_schema_view(
    list=extend_schema(
        summary="List all cities",
        description="Retrieve a list of all active cities",
        tags=['cities']
    ),
    retrieve=extend_schema(
        summary="Get city details",
        description="Retrieve detailed information about a specific city",
        tags=['cities']
    )
)
class CityViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for cities"""
    queryset = City.objects.filter(is_active=True).select_related('state_ref')
    serializer_class = CitySerializer
    lookup_field = 'slug'

@extend_schema_view(
    list=extend_schema(
        summary="List all layer categories",
        description="Retrieve a list of all layer categories",
        tags=['categories']
    ),
    retrieve=extend_schema(
        summary="Get layer category details",
        description="Retrieve detailed information about a specific layer category",
        tags=['categories']
    )
)
class LayerCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for layer categories"""
    queryset = LayerCategory.objects.all()
    serializer_class = LayerCategorySerializer
    lookup_field = 'code'

@extend_schema_view(
    list=extend_schema(
        summary="List all data layers",
        description="Retrieve a list of all processed data layers",
        tags=['layers']
    ),
    retrieve=extend_schema(
        summary="Get data layer details",
        description="Retrieve detailed information about a specific data layer",
        tags=['layers']
    )
)
class DataLayerViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for data layers"""
    queryset = DataLayer.objects.filter(is_processed=True).select_related('city', 'category')
    serializer_class = DataLayerSerializer

@extend_schema_view(
    list=extend_schema(
        summary="List all geo features",
        description="Retrieve a list of all valid geo features",
        tags=['features']
    ),
    retrieve=extend_schema(
        summary="Get geo feature details",
        description="Retrieve detailed information about a specific geo feature",
        tags=['features']
    )
)
class GeoFeatureViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for geo features"""
    queryset = GeoFeature.objects.filter(is_valid=True).select_related('layer', 'layer__city')
    serializer_class = GeoFeatureSerializer

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
                                    "category": "COMMERCIAL",
                                    "category_name": "Commercial",
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
                                    "category": "RESIDENTIAL",
                                    "category_name": "Residential",
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
                logger.debug(f"Cache HIT for coordinate search: {cache_key}")
                return Response(cached_result)
            
            logger.debug(f"Cache MISS for coordinate search: {cache_key}")
            
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
            
            # When returning simple format (data + fill_color), strip default color from features so client never sees it
            if isinstance(result, dict) and 'fill_color' in result and result.get('features'):
                for f in result['features']:
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
                logger.debug(f"Cached result for {cache_key} with TTL {ttl}s")
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
                'layer__category', 
                'layer__city', 
                'layer__city__state_ref'
            ).only(
                'id', 'name', 'zone_category', 'zone_subcategory',
                'plu_primary_code', 'plu_secondary_1', 'plot_category',
                'symbology', 'area', 'properties', 'geometry',
                'layer__id', 'layer__slug', 'layer__name', 'layer__description',
                'layer__category__code', 'layer__category__name',
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
        """Find all features that contain or intersect with the search point"""
        containing_features = []
        
        # Use a small buffer around the point to handle LineStrings and other geometries
        search_buffer = point.buffer(0.0001)  # ~10m buffer
        
        # Query features that intersect with the buffered point
        # Optimized with field limiting and result cap
        features = GeoFeature.objects.filter(
            layer__city=city,
            layer__is_processed=True,
            is_valid=True,
            geometry__intersects=search_buffer
        ).select_related(
            'layer', 'layer__category', 'layer__city', 'layer__city__state_ref'
        ).only(
            'id', 'name', 'zone_category', 'zone_subcategory',
            'plu_primary_code', 'plu_secondary_1', 'plot_category',
            'symbology', 'area', 'properties', 'geometry',
            'layer__id', 'layer__slug', 'layer__name', 'layer__description',
            'layer__category__code', 'layer__category__name',
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
        ).select_related('layer', 'layer__category', 'layer__city', 'layer__city__state_ref')
        
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
            'layer', 'layer__category', 'layer__city', 'layer__city__state_ref'
        ).only(
            'id', 'name', 'zone_category', 'zone_subcategory',
            'plu_primary_code', 'plu_secondary_1', 'plot_category',
            'symbology', 'area', 'properties', 'geometry',
            'layer__id', 'layer__slug', 'layer__name',
            'layer__category__code', 'layer__category__name',
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
            'layer__category', 
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
            # Get layer color using existing config system
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
                'category': feature.layer.category.code if feature.layer.category else 'UNKNOWN',
                'category_name': feature.layer.category.name if feature.layer.category else 'Unknown',
                'category_description': feature.layer.category.description if feature.layer.category else '',
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
                'category': 'ERROR',
                'category_name': 'Error',
                'color': '#FF0000',
                'area': {'square_meters': 0.0, 'square_kilometers': 0.0, 'acres': 0.0},
                'error': str(e)
            }
    
    def _get_detailed_category_info(self, feature):
        """Get detailed category information for a feature"""
        category_info = {}
        
        # Basic category info
        if feature.layer.category:
            category_info['layer_category'] = {
                'code': feature.layer.category.code,
                'name': feature.layer.category.name,
                'description': feature.layer.category.description or '',
                'default_color': feature.layer.category.default_color or '',
                'default_opacity': feature.layer.category.default_opacity or 0.8
            }
        
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
            from .config import get_city_config
            
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
            
            # Fallback to category color; no default - keep "" if none
            if feature.layer.category:
                return feature.layer.category.color or ''
            
            return ''
            
        except Exception as e:
            logger.error(f"Error getting feature color: {e}")
            return ''
    
    def _create_search_summary(self, containing_features, nearby_features):
        """Create a human-readable summary of the search results"""
        
        if containing_features:
            if len(containing_features) == 1:
                feature = containing_features[0]
                return f"Location is within {feature['layer_name']}: {feature['feature_name']} ({feature['category_name']})"
            else:
                primary = containing_features[0]  # Largest by area
                return f"Location is within {primary['layer_name']}: {primary['feature_name']} ({primary['category_name']}). Also overlaps with {len(containing_features) - 1} other features."
            
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
            is_road_layer = any(keyword in layer.slug.lower() for keyword in ['road', 'highway', 'metro', 'railway', 'rail', 'line'])
            
            # For road/linear layers, always use a buffer for meaningful results
            # For polygon master plan layers, use exact point containment
            # For other layers, use a small buffer to handle various geometries
            if is_road_layer:
                # Roads are LineStrings - use a 10m buffer to find nearby roads
                search_geometry = search_point.buffer(0.00001)  # ~1m buffer
            elif is_masterplan:
                # Polygon-based master plans (land use zones) - exact point containment
                search_geometry = search_point
            else:
                # Other layers - use a small buffer
                search_geometry = search_point.buffer(0.0001)  # ~10m buffer
            
            # Search for features in the specific layer that intersect with the point
            # Optimized query with field limiting and result cap
            features = GeoFeature.objects.filter(
                layer=layer,
                is_valid=True,
                geometry__intersects=search_geometry
            ).select_related(
                'layer', 'layer__category', 'layer__city', 'layer__city__state_ref'
            ).only(
                'id', 'name', 'zone_category', 'zone_subcategory',
                'plu_primary_code', 'plu_secondary_1', 'plot_category',
                'symbology', 'area', 'properties', 'geometry',
                'layer__id', 'layer__slug', 'layer__name', 'layer__description',
                'layer__category__code', 'layer__category__name',
                'layer__city__slug', 'layer__city__name',
                'layer__city__state_ref__slug', 'layer__city__state_ref__name'
            ).order_by('-area')[:20]  # Limit to top 20 features
            
            if not features.exists():
                # Skip nearby search for layers that should only return exact matches
                # For polygon-based master plan layers and heritage sites, never search nearby - only exact coordinate match
                # But for road layers, we already used a buffer above, so if no results, truly nothing nearby
                is_polygon_masterplan = is_masterplan and not is_road_layer
                is_heritage_site = layer.slug in ['hyderabad_heritage_sites', 'bengaluru_heritage_sites']
                
                if is_polygon_masterplan or is_heritage_site:
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
                        'status': 'no_data_found'
                    }
                
                # If no exact intersection found, search for nearby features within 100m buffer
                # Skip this for all master plan layers and heritage sites - they should never reach here due to check above
                buffer_100m = search_point.buffer(0.0009)  # ~100m buffer (0.0009 degrees ≈ 100m)
                
                nearby_features = GeoFeature.objects.filter(
                    layer=layer,
                    is_valid=True,
                    geometry__intersects=buffer_100m
                ).select_related(
                    'layer', 'layer__category', 'layer__city', 'layer__city__state_ref'
                ).only(
                    'id', 'name', 'zone_category', 'zone_subcategory',
                    'plu_primary_code', 'plu_secondary_1', 'plot_category',
                    'symbology', 'area', 'properties', 'geometry',
                    'layer__id', 'layer__slug', 'layer__name',
                    'layer__category__code', 'layer__category__name',
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
                            'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
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
                            'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
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
                            'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
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
                            'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
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
                            'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
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
                            'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
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
                            'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
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
                            'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                            'found': True,
                            'features': [feature_data],
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
                            'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                        }
                    
                    elif layer.slug in ['bengaluru_anekal_masterplan', 'bengaluru_chikkaballapura_masterplan', 'bengaluru_hosakote_masterplan', 'bengaluru_nelamangala_masterplan',
            'coimbatore_master_plan', 'hosur_master_plan', 'kochi_master_plan', 'chennai_master_plan',
            'tirupati_masterplan', 'cuttack_masterplan', 'vgtm_masterplan', 'kakinada_masterplan',
            'mandideep_masterplan', 'ajmer_masterplan', 'pithampur_masterplan', 'bhopal_masterplan',
            'varanasi_masterplan', 'ahmedabad_masterplan', 'vadodara_masterplan', 'gift_city_masterplan',
            'mohali_sas_nagar_masterplan', 'daman_and_diu_masterplan', 'patna_masterplan', 'ayodhya_masterplan',
            'lucknow_masterplan', 'srinagar_masterplan', 'guwahati_masterplan','dadra_and_nagar_haveli_masterplan',
            "kannur_masterplan", 'kollam_masterplan', 'kozhikode_masterplan', "derabassi_masterplan", 'banur_masterplan', 'mullanpur_masterplan', 'kharar_masterplan',
            'sonipat_kundli_masterplan', 'arogya_dham_badsa_masterplan', 'palwal_masterplan', 'prithla_masterplan', 'loni_masterplan', 'bhagpat_baraut_khekra_masterplan', 'modinagar_masterplan', 'kharkhauda_masterplan', 'ghaziabad_masterplan',
            'pinjore_kalka_masterplan', 'panchkula_extension_1_masterplan', 'panchkula_masterplan', 'dharuhera_masterplan', 'zirakpur_masterplan', 'sonipat_masterplan', 'new_raipur_masterplan',
            'biappa_masterplan', 'port_blair_masterplan', 'itanagar_masterplan', 'thiruvananthapuram_masterplan', 'thrissur_masterplan',
            'nuh_masterplan', 'jhajjar_masterplan', 'meerut_masterplan', 'hodal_masterplan', 'rewari_masterplan',
            'gohana_masterplan', 'bhiwadi_masterplan', 'alwar_masterplan',
            'mumbai_masterplan', 'pune_city_pmc_masterplan', 'pimpri_chinchwad_masterplan', 'pmrda-masterplan-pmrda_masterplan', 'nagpur_masterplan']:
                        # Return just the layer name as plain string
                        return {
                            'data': layer.slug,
                            'features': [],
                            'nearby_features': []
                        }
                    
                    elif layer.slug == 'bengaluru_master_plan_2015':
                        # Return just the feature name (Layer Name from properties)
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {})
                        layer_name = properties.get('Layer Name', '')
                        return {
                            'data': layer_name
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
                        'status': 'success'
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
                    'status': 'no_data_found'
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
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
                    data_parts.append(f"Road Width (in feet) - {str(road_width_feet)}")
                elif road_width_meters:
                    data_parts.append(f"Road Width (in meters) - {str(road_width_meters)}")
                data_string = ', '.join(data_parts) if data_parts else 'Masterplan Road'
                fill_color = (
                    properties.get('fill_color') or properties.get('fillColor') or
                    properties.get('FillColor') or properties.get('color')
                ) or ''
                return {
                    'data': data_string,
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
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
                    'data': data_string
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
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
                    'data': data_string
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
                    'data': data_string
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
                    'data': data_string
                }
            
            # Special handling for hyderabad_future_city layer
            if layer.slug == 'hyderabad_hmda_extended_area':
                return {
                    'data': layer.name
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
            'sonipat_kundli_masterplan', 'arogya_dham_badsa_masterplan', 'palwal_masterplan', 'prithla_masterplan', 'loni_masterplan', 'bhagpat_baraut_khekra_masterplan', 'modinagar_masterplan', 'kharkhauda_masterplan', 'ghaziabad_masterplan',
            'pinjore_kalka_masterplan', 'panchkula_extension_1_masterplan', 'panchkula_masterplan', 'dharuhera_masterplan', 'zirakpur_masterplan', 'panchkula_extension_1_masterplan', 'sonipat_masterplan', 'new_raipur_masterplan',
            'biappa_masterplan', 'port_blair_masterplan', 'itanagar_masterplan', 'thiruvananthapuram_masterplan', 'thrissur_masterplan',
            'nuh_masterplan', 'jhajjar_masterplan', 'meerut_masterplan', 'hodal_masterplan', 'rewari_masterplan',
            'gohana_masterplan', 'bhiwadi_masterplan', 'alwar_masterplan',
            'mumbai_masterplan', 'pune_city_pmc_masterplan', 'pimpri_chinchwad_masterplan', 'pmrda-masterplan-pmrda_masterplan', 'nagpur_masterplan'] and containing_features:
                # Return just the layer name as plain string
                return {
                    'data': layer.slug,
                    'features': [],
                    'nearby_features': []
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features,
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
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
                    'fill_color': _masterplan_fill_color_svg_data_uri(fill_color),
                    'found': True,
                    'features': containing_features[:1],
                }
            
            # Generate summary
            if containing_features:
                primary_feature = containing_features[0]
                summary = f"Location is within {layer.name}: {primary_feature['feature_name']} ({primary_feature['category_name']})"
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
                'status': 'success'
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
                'status': 'error'
            }
        
class AvailableTilesView(APIView):
    """
    API to get available tile coordinates for a city and zoom level
    GET /api/cities/{city_slug}/tiles/available/?zoom={z}&bbox={west,south,east,north}
    """
    
    def __init__(self):
        super().__init__()
        # Initialize S3 client for checking tile existence
        self.s3_client = boto3.client(
            's3',
            region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'ap-south-1'),
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        )
        self.bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME')
        self.cloudfront_domain = getattr(settings, 'CLOUDFRONT_DOMAIN', None)
    
    def get(self, request, city_slug):
        """
        Get available tile coordinates for a city and zoom level
        """
        try:
            # Validate city exists
            try:
                city = City.objects.get(slug=city_slug, is_active=True)
            except City.DoesNotExist:
                return Response({
                    'error': 'City not found',
                    'city': city_slug
                }, status=404)
            
            # Get query parameters
            zoom = request.GET.get('zoom')
            bbox_param = request.GET.get('bbox')  # format: "west,south,east,north"
            limit = int(request.GET.get('limit', 1000))  # Max tiles to return
            
            # Validate zoom parameter
            if not zoom:
                return Response({
                    'error': 'zoom parameter is required',
                    'example': f'/api/cities/{city_slug}/tiles/available/?zoom=12'
                }, status=400)
            
            try:
                zoom = int(zoom)
                if zoom < 0 or zoom > 18:
                    raise ValueError("Zoom must be between 0 and 18")
            except ValueError as e:
                return Response({
                    'error': f'Invalid zoom level: {str(e)}',
                    'zoom': zoom
                }, status=400)
            
            # Parse bounding box or use city bounds
            if bbox_param:
                try:
                    bbox_coords = [float(x) for x in bbox_param.split(',')]
                    if len(bbox_coords) != 4:
                        raise ValueError("Bbox must have 4 coordinates")
                    west, south, east, north = bbox_coords
                except ValueError as e:
                    return Response({
                        'error': f'Invalid bbox format: {str(e)}',
                        'example': 'bbox=77.0,12.0,78.0,13.0'
                    }, status=400)
            else:
                # Use default bounds for the city (approximate)
                # You can customize these based on your city data
                if city.slug == 'bengaluru':
                    west, south, east, north = 77.4, 12.8, 77.8, 13.2
                elif city.slug == 'visakhapatnam':
                    west, south, east, north = 83.1, 17.6, 83.4, 17.8
                elif city.slug == 'amaravati':
                    west, south, east, north = 80.2, 16.4, 80.6, 16.8
                else:
                    # Default bounds for unknown cities
                    west, south, east, north = 77.0, 12.0, 78.0, 13.0
            
            # Get tiles for the bounding box and zoom level
            import mercantile
            tiles = list(mercantile.tiles(west, south, east, north, zoom))
            
            # Limit results
            if len(tiles) > limit:
                tiles = tiles[:limit]
            
            # Format response
            tile_coords = []
            for tile in tiles:
                bounds = mercantile.bounds(tile)
                tile_coords.append({
                    'z': tile.z,
                    'x': tile.x,
                    'y': tile.y,
                    'bounds': {
                        'west': bounds.west,
                        'south': bounds.south,
                        'east': bounds.east,
                        'north': bounds.north
                    }
                })
            
            return Response({
                'city': city_slug,
                'zoom': zoom,
                'bbox': {
                    'west': west,
                    'south': south,
                    'east': east,
                    'north': north
                },
                'total_tiles': len(tiles),
                'tiles': tile_coords
            })
            
        except Exception as e:
            logger.error(f"Error in AvailableTilesView: {e}")
            return Response({
                'error': 'Failed to get available tiles',
                'message': str(e)
            }, status=500)

class TileCoordinatesView(APIView):
    """
    API to get tile coordinates for a specific point or area
    GET /api/cities/{city_slug}/tiles/coordinates/?lat={lat}&lng={lng}&zoom={z}
    """
    
    def get(self, request, city_slug):
        """
        Get tile coordinates for a specific point or area
        """
        try:
            # Validate city exists
            try:
                city = City.objects.get(slug=city_slug, is_active=True)
            except City.DoesNotExist:
                return Response({
                    'error': 'City not found',
                    'city': city_slug
                }, status=404)
            
            # Get query parameters
            lat = request.GET.get('lat')
            lng = request.GET.get('lng')
            zoom = request.GET.get('zoom', '12')
            
            # Validate required parameters
            if not lat or not lng:
                return Response({
                    'error': 'lat and lng parameters are required',
                    'example': f'/api/cities/{city_slug}/tiles/coordinates/?lat=12.9716&lng=77.5946&zoom=12'
                }, status=400)
            
            try:
                latitude = float(lat)
                longitude = float(lng)
                zoom_level = int(zoom)
            except ValueError as e:
                return Response({
                    'error': f'Invalid parameter format: {str(e)}',
                    'example': 'lat=12.9716&lng=77.5946&zoom=12'
                }, status=400)
            
            # Validate coordinate ranges
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                    return Response({
                    'error': 'Invalid coordinates',
                    'message': 'Latitude must be between -90 and 90, longitude between -180 and 180'
                    }, status=400)
            
            # Validate zoom level
            if zoom_level < 0 or zoom_level > 18:
                    return Response({
                    'error': 'Invalid zoom level',
                    'message': 'Zoom must be between 0 and 18'
                    }, status=400)
            
            # Get tile coordinates
            import mercantile
            tile = mercantile.tile(longitude, latitude, zoom_level)
            bounds = mercantile.bounds(tile)
            
            # Get surrounding tiles (3x3 grid)
            surrounding_tiles = []
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    x, y = tile.x + dx, tile.y + dy
                    if 0 <= x < 2**zoom_level and 0 <= y < 2**zoom_level:
                        surrounding_tiles.append({
                            'z': zoom_level,
                            'x': x,
                            'y': y,
                            'is_center': dx == 0 and dy == 0
                })
            
            return Response({
                'city': city_slug,
                'point': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'coordinates': [longitude, latitude]
                },
                'zoom': zoom_level,
                'center_tile': {
                    'z': tile.z,
                    'x': tile.x,
                    'y': tile.y,
                    'bounds': {
                        'west': bounds.west,
                        'south': bounds.south,
                        'east': bounds.east,
                        'north': bounds.north
                    }
                },
                'surrounding_tiles': surrounding_tiles,
                'total_tiles': len(surrounding_tiles)
            })
            
        except Exception as e:
            logger.error(f"Error in TileCoordinatesView: {e}")
            return Response({
                'error': 'Failed to get tile coordinates',
                'message': str(e)
            }, status=500)

@extend_schema(
    summary="Get complete hierarchy",
    description="Retrieve the complete hierarchy of states, cities, and layers in a single API call. This endpoint provides a comprehensive view of the entire geospatial data structure including statistics and tile availability.",
    tags=['hierarchy'],
    responses={
        200: {
            'description': 'Complete hierarchy data',
            'content': {
                'application/json': {
                    'example': {
                        'states': [
                            {
                                'state': {
                                    'name': 'Karnataka',
                                    'slug': 'karnataka',
                                    'is_active': True
                                },
                                'cities': [
                                    {
                                        'name': 'Bengaluru',
                                        'slug': 'bengaluru',
                                        'center_lat': 12.9716,
                                        'center_lng': 77.5946,
                                        'is_active': True,
                                        'is_live': True,
                                        'statistics': {
                                            'total_layers': 5,
                                            'processed_layers': 5,
                                            'layers_with_tiles': 5,
                                            'total_features': 1250
                                        },
                                        'status': 'live',
                                        'layers': [
                                            {
                                                'name': 'Master Plan 2015',
                                                'slug': 'master_plan_2015',
                                                'status': 'live',
                                                'is_live': True,
                                                'tiles_generated': True,
                                                'feature_count': 250,
                                                'category': 'Master Plan',
                                                'bounds': {
                                                    'xmin': 77.4,
                                                    'ymin': 12.8,
                                                    'xmax': 77.8,
                                                    'ymax': 13.2
                                                },
                                                'tile_urls': {
                                                    'png': 'https://d17yosovmfjm4.cloudfront.net/tiles/karnataka/bengaluru/master_plan_2015/{z}/{x}/{y}.png',
                                                    'mvt': 'https://d17yosovmfjm4.cloudfront.net/tiles/karnataka/bengaluru/master_plan_2015/{z}/{x}/{y}.mvt'
                                                }
                                            }
                                        ]
                                    }
                                ],
                                'statistics': {
                                    'total_cities': 1,
                                    'total_layers': 5,
                                    'total_features': 1250
                                }
                            }
                        ],
                        'summary': {
                            'total_states': 1,
                            'total_cities': 1,
                            'total_layers': 5,
                            'total_features': 1250
                        }
                    }
                }
            }
        }
    }
)
@extend_schema(
    summary="Get complete system hierarchy",
    description="""
    Returns the complete hierarchy of states, cities, layer groups, layers, and features in a single API call.
    This provides comprehensive data about the entire system structure including:
    
    - All states with their metadata and map settings
    - All cities within each state with map centers and statistics
    - All layer groups within each city with styling information
    - All data layers within each layer group with detailed information
    - Feature counts and processing status
    - Tile generation status and URLs
    - Bounding boxes and geometry information
    - Category and styling information
    - Global statistics and category definitions
    """,
    tags=['hierarchy'],
    responses={
        200: {
            'description': 'Complete hierarchy data',
            'content': {
                'application/json': {
                    'example': {
                        'status': 'success',
                        'timestamp': '2024-01-01T12:00:00Z',
                        'global_statistics': {
                            'total_states': 3,
                            'total_cities': 8,
                            'total_layers': 25,
                            'total_features': 150000,
                            'total_categories': 15
                        },
                        'categories': {
                            'RESIDENTIAL': {
                                'name': 'Residential',
                                'description': 'Residential areas',
                                'default_color': '#FFFF73',
                                'default_stroke': '#333333',
                                'default_opacity': 0.8,
                                'display_order': 1
                            }
                        },
                        'hierarchy': [
                            {
                                'id': 1,
                                'name': 'Karnataka',
                                'slug': 'karnataka',
                                'code': 'KA',
                                'map_settings': {
                                    'center_lat': 12.9716,
                                    'center_lng': 77.5946,
                                    'default_zoom': 7
                                },
                                'status': {'is_active': True},
                                'statistics': {
                                    'total_cities': 2,
                                    'total_layers': 10,
                                    'total_features': 75000
                                },
                                'cities': [
                                    {
                                        'id': 1,
                                        'name': 'Bengaluru',
                                        'slug': 'bengaluru',
                                        'state': {
                                            'name': 'Karnataka',
                                            'slug': 'karnataka',
                                            'code': 'KA'
                                        },
                                        'map_settings': {
                                            'center_lat': 12.9716,
                                            'center_lng': 77.5946,
                                            'min_zoom': 8,
                                            'max_zoom': 18
                                        },
                                        'status': {
                                            'is_active': True,
                                            'is_live': True,
                                            'status': 'live'
                                        },
                                        'statistics': {
                                            'total_layer_groups': 3,
                                            'total_layers': 8,
                                            'layers_with_tiles': 8,
                                            'total_features': 50000,
                                            'standalone_layers': 2
                                        },
                                        'styling': {
                                            'RESIDENTIAL': {
                                                'fill_color': '#FFFF73',
                                                'stroke_color': '#333333',
                                                'opacity': 0.8,
                                                'stroke_width': 1,
                                                'pattern_config': {
                                                    'pattern_type': 'SOLID',
                                                    'pattern_color': '#FFFF73',
                                                    'pattern_spacing': 10,
                                                    'pattern_angle': 45,
                                                    'pattern_size': 3,
                                                    'secondary_fill': None
                                                },
                                                'visibility': {
                                                    'is_visible': True,
                                                    'min_zoom': 8,
                                                    'max_zoom': 18
                                                }
                                            }
                                        },
                                        'layer_groups': [
                                            {
                                                'id': 1,
                                                'name': 'Master Plan',
                                                'slug': 'master-plan',
                                                'description': 'Bengaluru Master Plan 2015',
                                                'directory_path': '/data/karnataka/bengaluru/master_plan/',
                                                'category': {
                                                    'code': 'RESIDENTIAL',
                                                    'name': 'Residential'
                                                },
                                                'styling': {
                                                    'default_color': '#FFFF73',
                                                    'default_stroke': '#333333',
                                                    'default_opacity': 0.8
                                                },
                                                'display_settings': {
                                                    'display_order': 1,
                                                    'is_visible': True,
                                                    'min_zoom': 8,
                                                    'max_zoom': 18
                                                },
                                                'statistics': {
                                                    'total_layers': 3,
                                                    'total_features': 25000
                                                },
                                                'layers': [
                                                    {
                                                        'id': 1,
                                                        'name': 'Bengaluru Master Plan 2015',
                                                        'slug': 'bengaluru_master_plan_2015',
                                                        'description': 'Complete master plan data',
                                                        'file_info': {
                                                            'original_filename': 'bengaluru_master_plan_2015.geojson',
                                                            'file_format': 'GEOJSON',
                                                            'file_path': '/data/karnataka/bengaluru/master_plan/bengaluru_master_plan_2015.geojson',
                                                            'is_directory': False,
                                                            'file_pattern': None,
                                                            'source_files_count': 0
                                                        },
                                                        'category': {
                                                            'code': 'RESIDENTIAL',
                                                            'name': 'Residential'
                                                        },
                                                        'geometry_info': {
                                                            'geometry_type': 'POLYGON',
                                                            'has_valid_bbox': True,
                                                            'bounds': {
                                                                'xmin': 77.4567,
                                                                'ymin': 12.8234,
                                                                'xmax': 77.7234,
                                                                'ymax': 13.1234
                                                            },
                                                            'center_point': [12.9734, 77.5901]
                                                        },
                                                        'processing_status': {
                                                            'is_processed': True,
                                                            'tiles_generated': True,
                                                            'feature_count': 15000,
                                                            'processing_errors': None
                                                        },
                                                        'tile_info': {
                                                            'tiles_generated': True,
                                                            'tile_cache_size': 52428800,
                                                            'tile_urls': {
                                                                'png_template': 'https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/bengaluru_master_plan_2015/{z}/{x}/{y}.png',
                                                                'mvt_template': 'https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/bengaluru_master_plan_2015/{z}/{x}/{y}.mvt',
                                                                'api_png_template': '/api/tiles/karnataka/bengaluru/bengaluru_master_plan_2015/{z}/{x}/{y}.png',
                                                                'api_mvt_template': '/api/tiles/karnataka/bengaluru/bengaluru_master_plan_2015/{z}/{x}/{y}.mvt',
                                                                'cloudfront_base': 'https://d17yosovmfjm4.cloudfront.net/karnataka/bengaluru/bengaluru_master_plan_2015/',
                                                                'api_base': '/api/tiles/karnataka/bengaluru/bengaluru_master_plan_2015/'
                                                            }
                                                        },
                                                        'metadata': {
                                                            'data_source': 'Bengaluru Development Authority',
                                                            'last_updated': '2024-01-01T12:00:00Z',
                                                            'created_at': '2024-01-01T12:00:00Z',
                                                            'updated_at': '2024-01-01T12:00:00Z'
                                                        },
                                                        'statistics': {
                                                            'feature_count': 15000,
                                                            'file_breakdown': None
                                                        }
                                                    }
                                                ]
                                            }
                                        ],
                                        'standalone_layers': [],
                                        'created_at': '2024-01-01T12:00:00Z'
                                    }
                                ],
                                'created_at': '2024-01-01T12:00:00Z'
                            }
                        ]
                    }
                }
            }
        },
        500: {
            'description': 'Server error',
            'content': {
                'application/json': {
                    'example': {
                        'error': 'Failed to load hierarchy',
                        'message': 'Database connection error'
                    }
                }
            }
        }
    }
)
class CompleteHierarchyAPIView(APIView):
    """
    Complete Hierarchy API - Enhanced Version
    
    Returns the complete hierarchy of states, cities, layer groups, layers, and features in a single API call.
    This provides comprehensive data about the entire system structure.
    
    GET /api/hierarchy/
    
    Response includes:
    - All states with their metadata
    - All cities within each state with map centers and statistics
    - All layer groups within each city
    - All data layers within each layer group with detailed information
    - Feature counts and processing status
    - Tile generation status and URLs
    - Bounding boxes and geometry information
    - Category and styling information
    """
    
    def get(self, request):
        """Get complete hierarchy with comprehensive statistics and metadata"""
        try:
            # Get all active states with their cities, layer groups, and layers
            states = State.objects.filter(is_active=True).prefetch_related(
                Prefetch(
                    'cities',
                    queryset=City.objects.filter(is_active=True).prefetch_related(
                        Prefetch(
                            'layer_groups',
                            queryset=LayerGroup.objects.all().select_related('category')
                        ),
                        Prefetch(
                            'layers',
                            queryset=DataLayer.objects.all().select_related('category', 'layer_group')
                        ),
                        Prefetch(
                            'layer_styles',
                            queryset=CityLayerStyle.objects.all().select_related('category')
                        )
                    )
                )
            )
            
            # Get all categories for reference
            categories = LayerCategory.objects.all()
            category_data = {
                cat.code: {
                    'name': cat.name,
                    'description': cat.description,
                    'default_color': cat.default_color,
                    'default_stroke': cat.default_stroke,
                    'default_opacity': cat.default_opacity,
                    'display_order': cat.display_order
                } for cat in categories
            }
            
            hierarchy_data = []
            total_states = 0
            total_cities = 0
            total_layers = 0
            total_features = 0
            
            for state in states:
                state_cities = []
                state_total_features = 0
                state_total_layers = 0
                
                for city in state.cities.all():
                    city_layer_groups = []
                    city_layers = []
                    city_total_features = 0
                    city_total_layers = 0
                    layers_with_tiles = 0
                    
                    # Process layer groups
                    for layer_group in city.layer_groups.all():
                        group_layers = []
                        group_feature_count = 0
                        
                        for layer in city.layers.all():
                            if layer.layer_group == layer_group:
                                layer_data = self._get_layer_data(layer, state.slug, city.slug)
                                group_layers.append(layer_data)
                                group_feature_count += layer_data['statistics']['feature_count']
                                city_total_features += layer_data['statistics']['feature_count']
                                city_total_layers += 1
                                
                                if layer.tiles_generated:
                                    layers_with_tiles += 1
                        
                        layer_group_data = {
                            'id': layer_group.id,
                            'name': layer_group.name,
                            'slug': layer_group.slug,
                            'description': layer_group.description,
                            'directory_path': layer_group.directory_path,
                            'category': {
                                'code': layer_group.category.code,
                                'name': layer_group.category.name
                            },
                            'styling': {
                                'default_color': layer_group.default_color,
                                'default_stroke': layer_group.default_stroke,
                                'default_opacity': layer_group.default_opacity
                            },
                            'display_settings': {
                                'display_order': layer_group.display_order,
                                'is_visible': layer_group.is_visible,
                                'min_zoom': layer_group.min_zoom,
                                'max_zoom': layer_group.max_zoom
                            },
                            'statistics': {
                                'total_layers': len(group_layers),
                                'total_features': group_feature_count
                            },
                            'layers': group_layers
                        }
                        
                        city_layer_groups.append(layer_group_data)
                    
                    # Process layers not in groups (standalone layers)
                    standalone_layers = []
                    for layer in city.layers.all():
                        if not layer.layer_group:
                            layer_data = self._get_layer_data(layer, state.slug, city.slug)
                            standalone_layers.append(layer_data)
                            city_total_features += layer_data['statistics']['feature_count']
                            city_total_layers += 1
                            
                            if layer.tiles_generated:
                                layers_with_tiles += 1
                    
                    # Get city styling information
                    city_styles = {}
                    for style in city.layer_styles.all():
                        city_styles[style.category.code] = {
                            'fill_color': style.fill_color,
                            'stroke_color': style.stroke_color,
                            'opacity': style.opacity,
                            'stroke_width': style.stroke_width,
                            'pattern_config': style.get_pattern_config(),
                            'visibility': {
                                'is_visible': style.is_visible,
                                'min_zoom': style.min_zoom,
                                'max_zoom': style.max_zoom
                            }
                        }
                    
                    # City status summary
                    city_status = 'live' if layers_with_tiles > 0 else 'pending'
                    is_live = layers_with_tiles > 0
                    
                    city_data = {
                        'id': city.id,
                        'name': city.name,
                        'slug': city.slug,
                        'state': {
                            'name': state.name,
                            'slug': state.slug,
                            'code': state.code
                        },
                        'map_settings': {
                            'center_lat': city.center_lat,
                            'center_lng': city.center_lng,
                            'min_zoom': city.min_zoom,
                            'max_zoom': city.max_zoom
                        },
                        'status': {
                            'is_active': city.is_active,
                            'is_live': is_live,
                            'status': city_status
                        },
                        'statistics': {
                            'total_layer_groups': len(city_layer_groups),
                            'total_layers': city_total_layers,
                            'layers_with_tiles': layers_with_tiles,
                            'total_features': city_total_features,
                            'standalone_layers': len(standalone_layers)
                        },
                        'styling': city_styles,
                        'layer_groups': city_layer_groups,
                        'standalone_layers': standalone_layers,
                        'created_at': city.created_at.isoformat() if city.created_at else None
                    }
                    
                    state_cities.append(city_data)
                    state_total_features += city_total_features
                    state_total_layers += city_total_layers
                    total_cities += 1
                
                # State statistics
                state_data = {
                    'id': state.id,
                    'name': state.name,
                    'slug': state.slug,
                    'code': state.code,
                    'map_settings': {
                        'center_lat': state.center_lat,
                        'center_lng': state.center_lng,
                        'default_zoom': state.default_zoom
                    },
                    'status': {
                        'is_active': state.is_active
                    },
                    'statistics': {
                        'total_cities': len(state_cities),
                        'total_layers': state_total_layers,
                        'total_features': state_total_features
                    },
                    'cities': state_cities,
                    'created_at': state.created_at.isoformat() if state.created_at else None
                }
                
                hierarchy_data.append(state_data)
                total_states += 1
                total_layers += state_total_layers
                total_features += state_total_features
            
            # Global statistics
            global_stats = {
                'total_states': total_states,
                'total_cities': total_cities,
                'total_layers': total_layers,
                'total_features': total_features,
                'total_categories': len(categories)
            }
            
            return Response({
                'status': 'success',
                'timestamp': timezone.now().isoformat(),
                'global_statistics': global_stats,
                'categories': category_data,
                'hierarchy': hierarchy_data
            })
            
        except Exception as e:
            logger.error(f"Error in CompleteHierarchyAPIView: {e}")
            return Response({
                'error': 'Failed to load hierarchy',
                'message': str(e)
            }, status=500)
    
    def _get_layer_data(self, layer, state_slug, city_slug):
        """Get comprehensive layer data"""
        layer_feature_count = GeoFeature.objects.filter(layer=layer, is_valid=True).count()
        
        # Get tile URLs if tiles are generated
        tile_urls = None
        if layer.tiles_generated:
            tile_urls = self._get_layer_tile_urls(state_slug, city_slug, layer.slug, True)
        
        # Get feature breakdown by source file if it's a directory layer
        file_breakdown = None
        if layer.is_directory:
            try:
                file_breakdown = layer.get_file_features_breakdown()
            except:
                file_breakdown = None
        
        return {
            'id': layer.id,
            'name': layer.name,
            'slug': layer.slug,
            'description': layer.description,
            'is_true': layer.is_true,  # Layer visibility control
            'file_info': {
                'original_filename': layer.original_filename,
                'file_format': layer.file_format,
                'file_path': layer.file_path,
                'is_directory': layer.is_directory,
                'file_pattern': layer.file_pattern,
                'source_files_count': len(layer.source_files) if layer.source_files else 0
            },
            'category': {
                'code': layer.category.code if layer.category else None,
                'name': layer.category.name if layer.category else 'Unknown'
            },
            'geometry_info': {
                'geometry_type': layer.geometry_type,
                'has_valid_bbox': layer.has_valid_bbox(),
                'bounds': {
                    'xmin': layer.bbox_xmin,
                    'ymin': layer.bbox_ymin,
                    'xmax': layer.bbox_xmax,
                    'ymax': layer.bbox_ymax
                } if layer.has_valid_bbox() else None,
                'center_point': layer.get_center_point()
            },
            'processing_status': {
                'is_processed': layer.is_processed,
                'tiles_generated': layer.tiles_generated,
                'feature_count': layer_feature_count,
                'processing_errors': layer.processing_errors
            },
            'tile_info': {
                'tiles_generated': layer.tiles_generated,
                'tile_cache_size': layer.tile_cache_size,
                'tile_urls': tile_urls
            },
            'metadata': {
                'data_source': layer.data_source,
                'last_updated': layer.last_updated.isoformat() if layer.last_updated else None,
                'created_at': layer.created_at.isoformat(),
                'updated_at': layer.updated_at.isoformat()
            },
            'statistics': {
                'feature_count': layer_feature_count,
                'file_breakdown': file_breakdown
            }
        }
    
    def _get_layer_tile_urls(self, state_slug, city_slug, layer_slug, include_cloudfront=True):
        """Get tile URLs for a layer"""
        base_url = getattr(settings, 'CLOUDFRONT_DOMAIN', 'd17yosovmfjm4.cloudfront.net')
        
        return {
            'png_template': f"https://{base_url}/{state_slug}/{city_slug}/{layer_slug}/{{z}}/{{x}}/{{y}}.png",
            'mvt_template': f"https://{base_url}/{state_slug}/{city_slug}/{layer_slug}/{{z}}/{{x}}/{{y}}.mvt",
            'api_png_template': f"/api/tiles/{state_slug}/{city_slug}/{layer_slug}/{{z}}/{{x}}/{{y}}.png",
            'api_mvt_template': f"/api/tiles/{state_slug}/{city_slug}/{layer_slug}/{{z}}/{{x}}/{{y}}.mvt",
            'cloudfront_base': f"https://{base_url}/{state_slug}/{city_slug}/{layer_slug}/",
            'api_base': f"/api/tiles/{state_slug}/{city_slug}/{layer_slug}/"
        }

@extend_schema(
    summary="Serve map tiles",
    description="Serve map tiles (PNG or MVT format) from CloudFront CDN with hierarchical URL structure. This endpoint redirects to CloudFront URLs for optimal performance.",
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
        302: {
            'description': 'Redirect to CloudFront tile URL',
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
    Enhanced CloudFront Tile Serving API with Fallback
    
    Serves tiles from CloudFront CDN with hierarchical URL structure:
    GET /api/tiles/<state_slug>/<city_slug>/<layer_slug>/<z>/<x>/<y>.png
    GET /api/tiles/<state_slug>/<city_slug>/<layer_slug>/<z>/<x>/<y>.mvt
    
    Examples:
    - /api/tiles/karnataka/bengaluru/bengaluru_master_plan_2015/12/2926/1899.png
    - /api/tiles/andhra-pradesh/visakhapatnam/master_plan/12/2048/2048.png
    - /api/tiles/telangana/hyderabad/rrr/12/2048/2048.mvt
    
    This API tries CloudFront first, then S3 direct, then local generation as fallback.
    """
    
    # Class-level cache to track recently logged layer warnings (to reduce log spam)
    _layer_warning_cache = {}
    _layer_warning_cache_timeout = 300  # Log same layer warning at most once per 5 minutes
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tile_path_service = TilePathService()
    
    def get(self, request, state_slug, city_slug, layer_slug, z, x, y):
        """Serve tiles with multiple fallback options"""
        try:
            z, x, y = int(z), int(x), int(y)
            
            # Validate tile coordinates
            if not self.tile_path_service.validate_tile_coordinates(z, x, y):
                logger.warning(f"❌ Invalid tile coordinates: {z}/{x}/{y}")
                return self._return_error_tile("Invalid tile coordinates")
            
            # Determine format from URL
            format_type = 'png' if request.path.endswith('.png') else 'mvt'
            
            # Get layer information
            layer = self._get_layer_by_hierarchy(state_slug, city_slug, layer_slug)
            if not layer:
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
            
            logger.debug(f"🔍 Serving tile: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
            
            # Try multiple sources in order of preference
            tile_data = self._get_tile_with_fallback(state_slug, city_slug, layer_slug, z, x, y, format_type, layer)
            
            if tile_data:
                # Return the tile data with no-cache headers
                headers = self.tile_path_service.get_tile_cache_headers(format_type)
                response = HttpResponse(tile_data, content_type=headers['ContentType'])
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'
                logger.debug(f"✅ Successfully served tile: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
                return response
            else:
                logger.debug(f"❌ Tile not found: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
                return self._return_error_tile(f"Tile not found: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
            
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
        Try to get tile from multiple sources in order:
        1. CloudFront CDN (primary)
        2. S3 Direct (fallback)
        3. Generate on-demand (if enabled)
        """
        
        # 1. Try CloudFront first (primary source)
        cloudfront_url = self.tile_path_service.generate_cloudfront_url(
            state_slug, city_slug, layer_slug, z, x, y, format_type
        )
        
        logger.debug(f"🔍 Trying CloudFront: {cloudfront_url}")
        tile_data = self._fetch_url(cloudfront_url)
        if tile_data:
            logger.debug(f"✅ Served from CloudFront: {cloudfront_url}")
            return tile_data
        
        # 2. Try S3 Direct (fallback)
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
    S3 Direct Tile Serving API
    
    Serves tiles directly from S3 with hierarchical URL structure.
    Similar to CloudFrontTileView but uses S3 direct access.
    """
    
    # Class-level cache to track recently logged layer warnings (to reduce log spam)
    _layer_warning_cache = {}
    _layer_warning_cache_timeout = 300  # Log same layer warning at most once per 5 minutes
    """
    S3 Direct Tile Serving API
    
    Serves tiles directly from S3 with hierarchical URL structure:
    GET /api/s3-tiles/<state_slug>/<city_slug>/<layer_slug>/<z>/<x>/<y>.png
    GET /api/s3-tiles/<state_slug>/<city_slug>/<layer_slug>/<z>/<x>/<y>.mvt
    
    Examples:
    - /api/s3-tiles/karnataka/bengaluru/bengaluru_master_plan_2015/12/2926/1899.png
    - /api/s3-tiles/andhra-pradesh/visakhapatnam/visakhapatnam_master_plan/12/2048/2048.png
    - /api/s3-tiles/telangana/hyderabad/rrr/12/2048/2048.mvt
    
    This API serves tiles directly from S3 without CloudFront CDN.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tile_path_service = TilePathService()
        # Initialize S3 client for direct access
        self.s3_client = boto3.client(
            's3',
            region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'ap-south-1'),
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        )
        self.bucket_name = 'testing-gis-layers'
    
    def get(self, request, state_slug, city_slug, layer_slug, z, x, y):
        """Serve tiles directly from S3"""
        try:
            z, x, y = int(z), int(x), int(y)
            
            # Validate tile coordinates
            if not self.tile_path_service.validate_tile_coordinates(z, x, y):
                logger.warning(f"❌ Invalid tile coordinates: {z}/{x}/{y}")
                return self._return_error_tile("Invalid tile coordinates")
            
            # Determine format from URL
            format_type = 'png' if request.path.endswith('.png') else 'mvt'
            
            # Get layer information
            layer = self._get_layer_by_hierarchy(state_slug, city_slug, layer_slug)
            if not layer:
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
            # Generate S3 key for the tile
            s3_key = f"{state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}"
            
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

@extend_schema_view(
    get=extend_schema(
        summary="Find layers near coordinates or bounds",
        description="Find all layers that have features within 50km of given coordinates or bounding box. Returns layer information including state, city, category, and feature counts.",
        tags=['layers', 'search'],
        parameters=[
            OpenApiParameter(
                name='lat',
                location=OpenApiParameter.QUERY,
                required=False,
                type=float,
                description='Latitude coordinate (required if bounds not provided)'
            ),
            OpenApiParameter(
                name='lng',
                location=OpenApiParameter.QUERY,
                required=False,
                type=float,
                description='Longitude coordinate (required if bounds not provided)'
            ),
            OpenApiParameter(
                name='bounds',
                location=OpenApiParameter.QUERY,
                required=False,
                type=str,
                description='Bounding box as "west,south,east,north" (required if lat/lng not provided)'
            ),
            OpenApiParameter(
                name='radius_km',
                location=OpenApiParameter.QUERY,
                required=False,
                type=float,
                description='Search radius in kilometers (default: 50)'
            ),
        ],
        responses={
            200: {
                'description': 'Layers found successfully',
                'examples': [
                    {
                        'application/json': {
                            'success': True,
                            'search_area': {
                                'type': 'point',
                                'center': {
                                    'lat': 17.3850,
                                    'lng': 78.4867
                                },
                                'radius_km': 50
                            },
                            'total_layers_found': 5,
                            'layers': [
                                {
                                    'layer_id': 123,
                                    'layer_slug': 'hyderabad_metro',
                                    'layer_name': 'Hyderabad Metro',
                                    'state': {
                                        'slug': 'telangana',
                                        'name': 'Telangana'
                                    },
                                    'city': {
                                        'slug': 'hyderabad',
                                        'name': 'Hyderabad'
                                    },
                                    'category': {
                                        'code': 'INFRASTRUCTURE',
                                        'name': 'Infrastructure'
                                    },
                                    'feature_count': 150,
                                    'distance_km': 2.5,
                                    'bounds': {
                                        'west': 78.2673,
                                        'south': 17.2345,
                                        'east': 78.5678,
                                        'north': 17.4567
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
            400: {
                'description': 'Invalid request parameters',
                'examples': [
                    {
                        'application/json': {
                            'success': False,
                            'error': 'Please provide either lat/lng coordinates or bounds parameter'
                        }
                    }
                ]
            }
        }
    )
)
class NearbyLayersAPIView(APIView):
    """
    API endpoint to find all layers within 50km of given coordinates or bounds.
    
    URL: /api/layers/nearby/?lat={latitude}&lng={longitude}
    URL: /api/layers/nearby/?bounds={west,south,east,north}
    
    Returns all layers that have features within the specified radius (default 50km)
    of the given point or bounding box.
    
    Examples:
    - /api/layers/nearby/?lat=17.3850&lng=78.4867
    - /api/layers/nearby/?lat=17.3850&lng=78.4867&radius_km=25
    - /api/layers/nearby/?bounds=78.0,17.0,79.0,18.0
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        try:
            # Get query parameters
            lat = request.GET.get('lat')
            lng = request.GET.get('lng')
            bounds_param = request.GET.get('bounds')
            # For point searches, radius_km is ignored (only exact containment)
            # For bounds searches, radius_km is still used
            radius_km = float(request.GET.get('radius_km', 50)) if bounds_param else None
            
            # Validate radius only for bounds-based searches
            if bounds_param and radius_km and (radius_km <= 0 or radius_km > 500):
                return Response({
                    'success': False,
                    'error': 'radius_km must be between 0 and 500'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Determine search area - either from point or bounds
            search_area = None
            search_type = None
            
            if lat and lng:
                # Point-based search
                try:
                    latitude = float(lat)
                    longitude = float(lng)
                except ValueError:
                    return Response({
                        'success': False,
                        'error': 'Invalid coordinate format: lat and lng must be valid numbers'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Validate coordinate ranges
                if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                    return Response({
                        'success': False,
                        'error': 'Invalid coordinates: lat must be between -90 and 90, lng between -180 and 180'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Create point - no buffer, only check if point is inside features
                search_point = Point(longitude, latitude, srid=4326)
                
                # Use the point directly (no buffer) - only find layers where point is inside features
                search_area = search_point
                
                search_type = 'point'
                search_center = {'lat': latitude, 'lng': longitude}
                
                logger.info(f"Search point: ({latitude}, {longitude}) - checking for exact containment (no radius)")
                
            elif bounds_param:
                # Bounds-based search
                try:
                    bounds_coords = [float(x.strip()) for x in bounds_param.split(',')]
                    if len(bounds_coords) != 4:
                        raise ValueError("Bounds must have 4 coordinates")
                    west, south, east, north = bounds_coords
                except (ValueError, IndexError) as e:
                    return Response({
                        'success': False,
                        'error': f'Invalid bounds format: {str(e)}. Expected format: west,south,east,north'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Validate bounds
                if not (-90 <= south <= 90) or not (-90 <= north <= 90) or \
                   not (-180 <= west <= 180) or not (-180 <= east <= 180):
                    return Response({
                        'success': False,
                        'error': 'Invalid bounds: coordinates out of valid range'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if west >= east or south >= north:
                    return Response({
                        'success': False,
                        'error': 'Invalid bounds: west must be < east, south must be < north'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Expand bounds by radius_km (if provided, otherwise use default 50km)
                search_radius_km = radius_km if radius_km else 50
                # Convert km to degrees (approximate: 1 degree ≈ 111 km)
                radius_degrees = search_radius_km / 111.0
                expanded_west = west - radius_degrees
                expanded_south = south - radius_degrees
                expanded_east = east + radius_degrees
                expanded_north = north + radius_degrees
                
                # Create polygon from expanded bounds
                search_area = Polygon.from_bbox((
                    expanded_west, expanded_south, expanded_east, expanded_north
                ))
                search_area.srid = 4326
                search_type = 'bounds'
                search_center = {
                    'lat': (south + north) / 2,
                    'lng': (west + east) / 2
                }
                original_bounds = {
                    'west': west,
                    'south': south,
                    'east': east,
                    'north': north
                }
                # Store search_radius_km for use in response
                bounds_search_radius_km = search_radius_km
            else:
                return Response({
                    'success': False,
                    'error': 'Please provide either lat/lng coordinates or bounds parameter'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate search_area before using it
            if not search_area:
                return Response({
                    'success': False,
                    'error': 'Failed to create search area geometry'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Ensure search_area has proper SRID
            if not hasattr(search_area, 'srid') or search_area.srid != 4326:
                try:
                    if hasattr(search_area, 'srid') and search_area.srid:
                        search_area.transform(4326)
                    else:
                        search_area.srid = 4326
                except Exception as e:
                    logger.warning(f"Could not set SRID on search_area: {e}")
            
            # Find all layers that have features containing the point (exact match, no buffer)
            # Use geometry__contains for polygons and geometry__intersects for all geometry types
            # This ensures we find features where the point is actually inside/on the feature
            logger.info(f"Searching for layers with features containing the point (exact match, no radius)...")
            logger.info(f"Search point: ({search_center.get('lat')}, {search_center.get('lng')})")
            
            # Use contains for polygons (most accurate) and intersects for lines/points
            # This finds features where the point is actually inside or on the feature
            layers_with_features = GeoFeature.objects.filter(
                geometry__intersects=search_area,  # Works for all geometry types
                is_valid=True,
                layer__is_processed=True,
                layer__city__is_active=True,
                layer__city__state_ref__is_active=True
            ).select_related(
                'layer',
                'layer__category',
                'layer__city',
                'layer__city__state_ref'
            ).values(
                'layer_id',
                'layer__slug',
                'layer__name',
                'layer__description',
                'layer__category__code',
                'layer__category__name',
                'layer__city__slug',
                'layer__city__name',
                'layer__city__state_ref__slug',
                'layer__city__state_ref__name',
                'layer__bbox_xmin',
                'layer__bbox_ymin',
                'layer__bbox_xmax',
                'layer__bbox_ymax'
            ).distinct()
            
            logger.info(f"Found {layers_with_features.count()} unique layers with features containing the point")
            
            # Process results
            layers_list = []
            for layer_data in layers_with_features:
                layer_id = layer_data['layer_id']
                
                # Get feature count for this layer within search area
                feature_count = GeoFeature.objects.filter(
                    layer_id=layer_id,
                    geometry__intersects=search_area,
                    is_valid=True
                ).count()
                
                # Calculate distance from search center to layer center
                if layer_data['layer__bbox_xmin'] and layer_data['layer__bbox_ymin'] and \
                   layer_data['layer__bbox_xmax'] and layer_data['layer__bbox_ymax']:
                    layer_center_lng = (layer_data['layer__bbox_xmin'] + layer_data['layer__bbox_xmax']) / 2
                    layer_center_lat = (layer_data['layer__bbox_ymin'] + layer_data['layer__bbox_ymax']) / 2
                    
                    # Calculate distance in km (Haversine formula approximation)
                    from math import radians, cos, sin, asin, sqrt
                    lat1, lon1 = radians(search_center['lat']), radians(search_center['lng'])
                    lat2, lon2 = radians(layer_center_lat), radians(layer_center_lng)
                    dlat = lat2 - lat1
                    dlon = lon2 - lon1
                    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                    c = 2 * asin(sqrt(a))
                    distance_km = 6371 * c  # Earth radius in km
                else:
                    distance_km = None
                    layer_center_lat = None
                    layer_center_lng = None
                
                # Prepare layer bounds
                layer_bounds = None
                if layer_data['layer__bbox_xmin'] and layer_data['layer__bbox_ymin'] and \
                   layer_data['layer__bbox_xmax'] and layer_data['layer__bbox_ymax']:
                    layer_bounds = {
                        'west': layer_data['layer__bbox_xmin'],
                        'south': layer_data['layer__bbox_ymin'],
                        'east': layer_data['layer__bbox_xmax'],
                        'north': layer_data['layer__bbox_ymax']
                    }
                
                layer_info = {
                    'layer_id': layer_id,
                    'layer_slug': layer_data['layer__slug'],
                    'layer_name': layer_data['layer__name'],
                    'layer_description': layer_data['layer__description'] or '',
                    'meaning': (
                        'Your point falls inside this layer (inside ' + str(feature_count) + ' feature(s)).'
                    ),
                    'state': {
                        'slug': layer_data['layer__city__state_ref__slug'],
                        'name': layer_data['layer__city__state_ref__name']
                    },
                    'city': {
                        'slug': layer_data['layer__city__slug'],
                        'name': layer_data['layer__city__name']
                    },
                    'category': {
                        'code': layer_data['layer__category__code'],
                        'name': layer_data['layer__category__name']
                    } if layer_data['layer__category__code'] else None,
                    'feature_count': feature_count,
                    'feature_count_description': f'Number of polygons/features in this layer that contain your point.',
                    'distance_km': round(distance_km, 2) if distance_km is not None else None,
                    'bounds': layer_bounds,
                    'center': {
                        'lat': layer_center_lat,
                        'lng': layer_center_lng
                    } if layer_center_lat and layer_center_lng else None
                }
                
                layers_list.append(layer_info)
            
            # Sort by distance (closest first)
            layers_list.sort(key=lambda x: x['distance_km'] if x['distance_km'] is not None else float('inf'))
            
            # Build a self-explanatory response
            total = len(layers_list)
            if search_type == 'point':
                summary_message = (
                    f"Found {total} layer(s) that contain your point. "
                    "Your coordinates fall inside at least one polygon/feature in each of these layers."
                )
                if total == 0:
                    summary_message = (
                        "No layers found. Your point does not fall inside any layer's geometry. "
                        "Try a point inside a city/masterplan area or use bounds search with ?bounds=west,south,east,north"
                    )
            else:
                summary_message = (
                    f"Found {total} layer(s) within the given bounds (radius {bounds_search_radius_km} km)."
                )
            
            response_data = {
                'success': True,
                'summary': {
                    'message': summary_message,
                    'total_layers_found': total,
                    'search_type': search_type,
                },
                'request': {
                    'description': (
                        'Point search: layers whose geometry contains this exact point (no radius).'
                        if search_type == 'point'
                        else f'Bounds search: layers that intersect the area (radius {bounds_search_radius_km} km).'
                    ),
                    'coordinates': {
                        'lat': search_center.get('lat'),
                        'lng': search_center.get('lng'),
                        'lat_description': 'Latitude (degrees, -90 to 90)',
                        'lng_description': 'Longitude (degrees, -180 to 180)',
                    },
                },
                'search_area': {
                    'type': search_type,
                    'center': search_center,
                },
            }
            
            if search_type == 'point':
                response_data['search_area']['search_type'] = 'exact_containment'
                response_data['search_area']['note'] = (
                    'Only layers where your point is inside a feature are returned (no distance radius).'
                )
            else:
                response_data['search_area']['radius_km'] = bounds_search_radius_km
                response_data['search_area']['original_bounds'] = original_bounds
                response_data['search_area']['expanded_bounds'] = {
                    'west': expanded_west,
                    'south': expanded_south,
                    'east': expanded_east,
                    'north': expanded_north,
                }
            
            response_data['layers'] = layers_list
            response_data['response_guide'] = {
                'summary': 'Quick human-readable result and what was searched.',
                'request': 'Echo of your query and what it means.',
                'layers': (
                    'Each layer listed has at least one polygon/line that contains (or intersects) your point. '
                    'Ordered by distance from your point to the layer center (closest first).'
                ),
                'layer_fields': {
                    'layer_id': 'Database ID of the layer.',
                    'layer_slug': 'URL-safe identifier (use in APIs: state/city/layer_slug).',
                    'layer_name': 'Human-readable layer name.',
                    'layer_description': 'Optional description of the layer.',
                    'state': 'State this layer belongs to (slug and name).',
                    'city': 'City this layer belongs to (slug and name).',
                    'category': 'Layer type/category (e.g. PLANNING, TRANSPORT).',
                    'feature_count': 'Number of polygons/features in this layer that contain your point.',
                    'distance_km': 'Distance from your point to the layer center in km (0 = point inside layer).',
                    'bounds': 'Layer extent: west, south, east, north (degrees). Use to zoom map to layer.',
                    'center': 'Approximate center of the layer (lat, lng).',
                },
            }
            
            logger.info(f"Returning {len(layers_list)} layers near coordinates ({search_center.get('lat')}, {search_center.get('lng')})")
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Error finding nearby layers: {str(e)}")
            return Response({
                'success': False,
                'error': f'Error finding nearby layers: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema_view(
    get=extend_schema(
        summary="Get layer bounds",
        description="Retrieve the geographic bounds for a specific layer based on actual data",
        tags=['layers'],
        parameters=[
            OpenApiParameter(name='state_slug', location=OpenApiParameter.PATH, required=True, type=str, description='State slug'),
            OpenApiParameter(name='city_slug', location=OpenApiParameter.PATH, required=True, type=str, description='City slug'),
            OpenApiParameter(name='layer_slug', location=OpenApiParameter.PATH, required=True, type=str, description='Layer slug'),
        ],
        responses={
            200: {
                'description': 'Layer bounds retrieved successfully',
                'examples': [
                    {
                        'application/json': {
                            'state': 'telangana',
                            'state_name': 'Telangana',
                            'city': 'hyderabad',
                            'city_name': 'Hyderabad',
                            'layer': 'hyderabad_highways',
                            'layer_name': 'Hyderabad Highways',
                            'bounds': {
                                'west': 78.2673,
                                'south': 17.2345,
                                'east': 78.5678,
                                'north': 17.4567
                            },
                            'center': {
                                'lat': 17.3456,
                                'lng': 78.4175
                            },
                            'dimensions': {
                                'width': 0.3005,
                                'height': 0.2222
                            },
                            'feature_count': 1234,
                            'data_source': 'calculated_from_features'
                        }
                    }
                ]
            },
            404: {
                'description': 'State, city, or layer not found',
                'examples': [
                    {
                        'application/json': {
                            'error': 'Layer not found: hyderabad_highways in city: hyderabad',
                            'state': 'telangana',
                            'city': 'hyderabad',
                            'layer': 'hyderabad_highways'
                        }
                    }
                ]
            }
        }
    )
)
class LayerBoundsAPIView(APIView):
    """
    API endpoint to get the geographic bounds for a specific layer based on actual data.
    
    URL: /api/layers/{state_slug}/{city_slug}/{layer_slug}/bounds/
    
    Returns the bounding box coordinates (west, south, east, north) for the layer,
    calculated from the actual feature geometries in the database.
    
    Optimized for performance with:
    - Single optimized query with select_related
    - Caching for bounds calculation
    - Reduced database hits
    """
    permission_classes = [AllowAny]
    
    def get(self, request, state_slug, city_slug, layer_slug):
        try:
            # Create cache key for this layer bounds
            cache_key = f"layer_bounds_{state_slug}_{city_slug}_{layer_slug}"
            
            # Try to get from cache first
            cached_result = cache.get(cache_key)
            if cached_result:
                return Response(cached_result)
            
            # Single optimized query to get layer with all related data
            layer = DataLayer.objects.select_related(
                'city__state_ref', 
                'category'
            ).get(
                slug=layer_slug,
                city__slug=city_slug,
                city__state_ref__slug=state_slug,
                city__is_active=True,
                city__state_ref__is_active=True,
                is_processed=True
            )
            
            # Check if layer has stored bounds (fastest path)
            if all([layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax]):
                bounds = {
                    'west': layer.bbox_xmin,
                    'south': layer.bbox_ymin,
                    'east': layer.bbox_xmax,
                    'north': layer.bbox_ymax
                }
                data_source = 'stored_bounds'
                feature_count = layer.feature_count  # Use stored count
            else:
                # Calculate bounds from actual features (optimized query)
                from django.contrib.gis.db.models import Extent
                
                # Single query to get both extent and count
                result = GeoFeature.objects.filter(
                    layer=layer,
                    is_valid=True
                ).aggregate(
                    extent=Extent('geometry'),
                    count=Count('id')
                )
                
                extent = result['extent']
                feature_count = result['count']
                
                if not extent:
                    return Response({
                        'error': f'No valid features found for layer: {layer_slug}',
                        'state': state_slug,
                        'city': city_slug,
                        'layer': layer_slug
                    }, status=status.HTTP_404_NOT_FOUND)
                
                bounds = {
                    'west': extent[0],
                    'south': extent[1],
                    'east': extent[2],
                    'north': extent[3]
                }
                data_source = 'calculated_from_features'
            
            # Calculate center coordinates
            center_lng = (bounds['west'] + bounds['east']) / 2
            center_lat = (bounds['south'] + bounds['north']) / 2
            
            # Calculate dimensions
            width = bounds['east'] - bounds['west']
            height = bounds['north'] - bounds['south']
            
            response_data = {
                'state': state_slug,
                'state_name': layer.city.state_ref.name,
                'city': city_slug,
                'city_name': layer.city.name,
                'layer': layer_slug,
                'layer_name': layer.name,
                'bounds': bounds,
                'center': {
                    'lat': center_lat,
                    'lng': center_lng
                },
                'dimensions': {
                    'width': width,
                    'height': height
                },
                'feature_count': feature_count,
                'data_source': data_source,
                'layer_info': {
                    'category': layer.category.code if layer.category else None,
                    'category_name': layer.category.name if layer.category else None,
                    'feature_count': layer.feature_count,
                    'is_processed': layer.is_processed,
                    'created_at': layer.created_at.isoformat() if layer.created_at else None
                }
            }
            
            # Cache the result for 1 hour (3600 seconds)
            cache.set(cache_key, response_data, 3600)
            
            return Response(response_data)
            
        except DataLayer.DoesNotExist:
            return Response({
                'error': f'Layer not found: {layer_slug} in city: {city_slug}',
                'state': state_slug,
                'city': city_slug,
                'layer': layer_slug
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error getting layer bounds: {str(e)}")
            return Response({
                'error': f'Error calculating layer bounds: {str(e)}',
                'state': state_slug,
                'city': city_slug,
                'layer': layer_slug
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    summary="Search coordinates in specific layer",
    description="Search for features at given coordinates within a specific layer identified by slug",
    parameters=[
        OpenApiParameter(
            name='lat',
            type=float,
            location=OpenApiParameter.QUERY,
            required=True,
            description='Latitude of the point to check'
        ),
        OpenApiParameter(
            name='lng',
            type=float,
            location=OpenApiParameter.QUERY,
            required=True,
            description='Longitude of the point to check'
        ),
        OpenApiParameter(
            name='slug',
            type=str,
            location=OpenApiParameter.QUERY,
            required=True,
            description='Slug of the layer to search in'
        )
    ],
    responses={
        200: extend_schema(
            description="Feature found in the specified layer",
            examples=[
                OpenApiExample(
                    'Feature Found',
                    value={
                        "feature": {
                            "id": 12345,
                            "name": "C1 Mixed Use Zone",
                            "zone_category": "C1__Mixed_use_zone",
                            "plot_category": "Mixed Use",
                            "symbology": "C1",
                            "township": "Amaravati",
                            "sector": "Sector 1",
                            "colony": "Colony A",
                            "block": "Block 1",
                            "area": 1500.5,
                            "shape_length": 200.3,
                            "shape_area": 1500.5,
                            "objectid": 123,
                            "properties": {
                                "symbology": "C1",
                                "plot_categ": "Mixed Use",
                                "township": "Amaravati"
                            }
                        },
                        "layer": {
                            "slug": "amaravati_master_plan",
                            "name": "Amaravati Master Plan",
                            "city": "amaravati",
                            "city_name": "Amaravati",
                            "state": "andhra-pradesh",
                            "state_name": "Andhra Pradesh"
                        },
                        "search_point": {
                            "latitude": 16.5740,
                            "longitude": 80.3586,
                            "coordinates": [80.3586, 16.5740]
                        }
                    }
                )
            ]
        ),
        400: extend_schema(
            description="Invalid request parameters",
            examples=[
                OpenApiExample(
                    'Invalid Layer Slug',
                    value={
                        "detail": "Invalid layer slug"
                    }
                ),
                OpenApiExample(
                    'Missing Parameters',
                    value={
                        "detail": "Missing required parameters: lat, lng, slug"
                    }
                ),
                OpenApiExample(
                    'Invalid Coordinates',
                    value={
                        "detail": "Invalid coordinates: lat must be between -90 and 90, lng between -180 and 180"
                    }
                )
            ]
        ),
        404: extend_schema(
            description="No feature found in the specified layer",
            examples=[
                OpenApiExample(
                    'No Feature Found',
                    value={
                        "detail": "No feature found in the specified layer"
                    }
                )
            ]
        )
    },
    tags=['search']
)
class LayerCoordinateSearchView(APIView):
    """
    Coordinate-based search restricted to a single layer identified by its slug.
    
    URL: /api/search-coords-by-layer/?lat=<latitude>&lng=<longitude>&slug=<layer_slug>
    URL: /api/cities/<layer_slug>/search-coords-test/?lat=<latitude>&lng=<longitude>
    
    This API searches only within the layer identified by the given slug.
    Returns feature details if coordinates fall inside a feature of that layer.
    """
    permission_classes = [AllowAny]
    
    def get(self, request, layer_slug=None):
        try:
            # Get parameters from query string or URL path
            lat = request.GET.get('lat')
            lng = request.GET.get('lng')
            slug = layer_slug or request.GET.get('slug')
            
            # Validate required parameters
            if not lat or not lng or not slug:
                return Response({
                    'detail': 'Missing required parameters: lat, lng, and layer slug'
                }, status=400)
            
            # If this is a URL path parameter (layer_slug), check if it's actually a layer slug
            if layer_slug:
                # First check if it's a valid city slug - if so, this should be handled by city search
                from maps.models import City
                try:
                    City.objects.get(slug=layer_slug)
                    # It's a valid city slug, so this should be handled by the city search view
                    # We'll let it fall through to the city search by returning a 404
                    return Response({
                        'detail': 'Invalid layer slug'
                    }, status=400)
                except City.DoesNotExist:
                    # Not a city slug, proceed with layer search
                    pass
            
            # Validate and convert coordinates
            try:
                latitude = float(lat)
                longitude = float(lng)
            except ValueError:
                return Response({
                    'detail': 'Invalid coordinate format: lat and lng must be valid numbers'
                }, status=400)
            
            # Validate coordinate ranges
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                return Response({
                    'detail': 'Invalid coordinates: lat must be between -90 and 90, lng between -180 and 180'
                }, status=400)
            
            # Check if layer exists
            try:
                layer = DataLayer.objects.select_related('city', 'city__state_ref').get(slug=slug)
            except DataLayer.DoesNotExist:
                return Response({
                    'detail': 'Invalid layer slug'
                }, status=400)
            
            # Create point geometry for search
            search_point = Point(longitude, latitude, srid=4326)
            
            # Search for features in the specific layer that intersect with the point
            # Use a small buffer around the point to handle LineStrings and other geometries
            search_buffer = search_point.buffer(0.0001)  # ~10m buffer
            
            features = GeoFeature.objects.filter(
                layer=layer,
                is_valid=True,
                geometry__intersects=search_buffer
            ).order_by('-area')  # Order by area (largest first)
            
            if not features.exists():
                return Response({
                    'detail': 'No feature found in the specified layer'
                }, status=404)
            
            # Get the primary feature (largest by area if multiple)
            feature = features.first()
            
            # Build response
            response_data = {
                'feature': {
                    'id': feature.id,
                    'name': feature.name or '',
                    'zone_category': feature.zone_category or '',
                    'plot_category': feature.plot_category or '',
                    'symbology': feature.symbology or '',
                    'township': feature.township or '',
                    'sector': feature.sector or '',
                    'colony': feature.colony or '',
                    'block': feature.block or '',
                    'area': float(feature.area) if feature.area else None,
                    'shape_length': float(feature.shape_length) if feature.shape_length else None,
                    'shape_area': float(feature.shape_area) if feature.shape_area else None,
                    'objectid': feature.objectid,
                    'properties': feature.properties or {}
                },
                'layer': {
                    'slug': layer.slug,
                    'name': layer.name,
                    'city': layer.city.slug,
                    'city_name': layer.city.name,
                    'state': layer.city.state_ref.slug,
                    'state_name': layer.city.state_ref.name
                },
                'search_point': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'coordinates': [longitude, latitude]
                }
            }
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Error in LayerCoordinateSearchView: {e}")
            return Response({
                'detail': f'Internal server error: {str(e)}'
            }, status=500)

@extend_schema_view(
    get=extend_schema(
        summary="Get layer bounds and zoom levels",
        description="Provides bounds and optimal zoom levels for layers based on actual data in the database. Supports single or multiple layers - if multiple layers are called, returns combined bounds.",
        parameters=[
            OpenApiParameter(
                name='state_slug',
                location=OpenApiParameter.PATH,
                description='State slug (e.g., karnataka, telangana)',
                required=True,
                type=str
            ),
            OpenApiParameter(
                name='city_slug',
                location=OpenApiParameter.PATH,
                description='City slug (e.g., bengaluru, hyderabad)',
                required=True,
                type=str
            ),
            OpenApiParameter(
                name='layer_slugs',
                location=OpenApiParameter.PATH,
                description='Layer slug(s) - comma-separated for multiple layers (e.g., bengaluru_master_plan_2015 or highways,metro_combined)',
                required=True,
                type=str
            )
        ],
        responses={
            200: extend_schema(
                description="Successfully retrieved bounds and zoom levels",
                examples=[
                    OpenApiExample(
                        'Single Layer Response',
                        value={
                            "success": True,
                            "state": {
                                "slug": "karnataka",
                                "name": "Karnataka"
                            },
                            "city": {
                                "slug": "bengaluru",
                                "name": "Bengaluru",
                                "center_lat": 12.9716,
                                "center_lng": 77.5946,
                                "min_zoom": 8,
                                "max_zoom": 18
                            },
                            "layers": [
                                {
                                    "slug": "bengaluru_master_plan_2015",
                                    "name": "Bengaluru Master Plan 2015",
                                    "category": "Mixed Use",
                                    "feature_count": 1250,
                                    "geometry_type": "POLYGON",
                                    "is_processed": True,
                                    "tiles_generated": True
                                }
                            ],
                            "bounds": {
                                "west": 77.1234,
                                "south": 12.5678,
                                "east": 78.1234,
                                "north": 13.5678,
                                "center_lat": 13.0678,
                                "center_lng": 77.6234
                            },
                            "zoom": {
                                "optimal": 12,
                                "min_zoom": 8,
                                "max_zoom": 18,
                                "recommended_range": {
                                    "min": 10,
                                    "max": 14
                                }
                            },
                            "statistics": {
                                "total_layers": 1,
                                "total_features": 1250,
                                "bounds_width_degrees": 1.0,
                                "bounds_height_degrees": 1.0
                            },
                            "message": "Bounds calculated from 1250 features across 1 layer(s)"
                        }
                    )
                ]
            ),
            404: extend_schema(
                description="City or layers not found",
                examples=[
                    OpenApiExample(
                        'City Not Found',
                        value={
                            "error": "City \"invalid_city\" not found in state \"karnataka\""
                        }
                    ),
                    OpenApiExample(
                        'Layers Not Found',
                        value={
                            "error": "No processed layers found with slugs: ['invalid_layer']"
                        }
                    )
                ]
            )
        },
        tags=['layers', 'bounds']
    )
)

class LayerBoundsZoomAPIView(APIView):
    """
    Layer Bounds and Zoom Level API
    
    Provides bounds and optimal zoom levels for layers based on actual data in the database.
    Supports single or multiple layers - if multiple layers are called, returns combined bounds.
    
    GET /api/layers/<state_slug>/<city_slug>/<layer_slug>/bounds-zoom/
    GET /api/layers/<state_slug>/<city_slug>/<layer_slug1>,<layer_slug2>,<layer_slug3>/bounds-zoom/
    
    Examples:
    - /api/layers/karnataka/bengaluru/bengaluru_master_plan_2015/bounds-zoom/
    - /api/layers/telangana/hyderabad/highways,metro_combined/bounds-zoom/
    
    Returns:
    - Bounds calculated from actual GeoFeature geometries
    - Optimal zoom level to fit all bounds in view
    - Center point for map positioning
    - Feature count and layer information
    """
    permission_classes = [AllowAny]
    
    def get(self, request, state_slug, city_slug, layer_slugs):
        """Get bounds and zoom levels for specified layers"""
        try:
            # Parse layer slugs (comma-separated for multiple layers)
            layer_slug_list = [slug.strip() for slug in layer_slugs.split(',')]
            
            # Get city
            try:
                city = City.objects.select_related('state_ref').get(
                    slug=city_slug,
                    state_ref__slug=state_slug,
                    is_active=True
                )
            except City.DoesNotExist:
                return Response({
                    'error': f'City "{city_slug}" not found in state "{state_slug}"'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get layers
            layers = DataLayer.objects.filter(
                city=city,
                slug__in=layer_slug_list,
                is_processed=True
            ).select_related('category')
            
            if not layers.exists():
                return Response({
                    'error': f'No processed layers found with slugs: {layer_slug_list}'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Check if all requested layers were found
            found_slugs = [layer.slug for layer in layers]
            missing_slugs = [slug for slug in layer_slug_list if slug not in found_slugs]
            if missing_slugs:
                return Response({
                    'error': f'Layers not found: {missing_slugs}',
                    'found_layers': found_slugs
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Calculate combined bounds from all features in all layers
            combined_bounds = self._calculate_combined_bounds(layers)
            
            if not combined_bounds:
                return Response({
                    'error': 'No features found in the specified layers',
                    'layers': [{'slug': layer.slug, 'name': layer.name, 'feature_count': layer.feature_count} for layer in layers]
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Calculate optimal zoom level
            optimal_zoom = self._calculate_optimal_zoom(combined_bounds)
            
            # Calculate center point
            center_lat = (combined_bounds['south'] + combined_bounds['north']) / 2
            center_lng = (combined_bounds['west'] + combined_bounds['east']) / 2
            
            # Prepare layer information
            layer_info = []
            total_features = 0
            for layer in layers:
                layer_info.append({
                    'slug': layer.slug,
                    'name': layer.name,
                    'category': layer.category.name,
                    'feature_count': layer.feature_count,
                    'geometry_type': layer.geometry_type,
                    'is_processed': layer.is_processed,
                    'tiles_generated': layer.tiles_generated
                })
                total_features += layer.feature_count
            
            # Prepare response
            response_data = {
                'success': True,
                'state': {
                    'slug': state_slug,
                    'name': city.state_ref.name if city.state_ref else state_slug
                },
                'city': {
                    'slug': city_slug,
                    'name': city.name,
                    'center_lat': city.center_lat,
                    'center_lng': city.center_lng,
                    'min_zoom': city.min_zoom,
                    'max_zoom': city.max_zoom
                },
                'layers': layer_info,
                'bounds': {
                    'west': round(combined_bounds['west'], 6),
                    'south': round(combined_bounds['south'], 6),
                    'east': round(combined_bounds['east'], 6),
                    'north': round(combined_bounds['north'], 6),
                    'center_lat': round(center_lat, 6),
                    'center_lng': round(center_lng, 6)
                },
                'zoom': {
                    'optimal': optimal_zoom,
                    'min_zoom': city.min_zoom,
                    'max_zoom': city.max_zoom,
                    'recommended_range': {
                        'min': max(optimal_zoom - 2, city.min_zoom),
                        'max': min(optimal_zoom + 2, city.max_zoom)
                    }
                },
                'statistics': {
                    'total_layers': len(layers),
                    'total_features': total_features,
                    'bounds_width_degrees': round(combined_bounds['east'] - combined_bounds['west'], 6),
                    'bounds_height_degrees': round(combined_bounds['north'] - combined_bounds['south'], 6)
                },
                'message': f'Bounds calculated from {total_features} features across {len(layers)} layer(s)'
            }
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Error in layer bounds zoom API: {str(e)}")
            return Response({
                'error': f'Internal server error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _calculate_combined_bounds(self, layers):
        """Calculate combined bounds from all features in the specified layers"""
        from django.contrib.gis.db.models import Extent
        from django.contrib.gis.geos import GEOSGeometry, Polygon
        
        # Get all features from all layers
        features = GeoFeature.objects.filter(
            layer__in=layers,
            is_valid=True
        )
        
        if not features.exists():
            return None
        
        # Calculate extent of all features
        extent = features.aggregate(extent=Extent('geometry'))['extent']
        
        if not extent:
            return None
        
        # extent is (xmin, ymin, xmax, ymax)
        xmin, ymin, xmax, ymax = extent
        
        # Check if coordinates are in Web Mercator (EPSG:3857) instead of WGS84 (EPSG:4326)
        # Web Mercator coordinates are in meters and much larger than degree values
        # If longitude > 180 or < -180, it's likely Web Mercator
        if abs(xmin) > 180 or abs(xmax) > 180 or abs(ymin) > 90 or abs(ymax) > 90:
            # Coordinates appear to be in Web Mercator (EPSG:3857)
            # Create a polygon from the extent and transform it to WGS84
            bbox = Polygon.from_bbox((xmin, ymin, xmax, ymax))
            bbox.srid = 3857  # Set as Web Mercator
            bbox.transform(4326)  # Transform to WGS84
            
            # Get the new extent in WGS84
            extent_wgs84 = bbox.extent
            return {
                'west': extent_wgs84[0],   # xmin (longitude)
                'south': extent_wgs84[1],  # ymin (latitude)
                'east': extent_wgs84[2],   # xmax (longitude)
                'north': extent_wgs84[3]   # ymax (latitude)
            }
        
        # Coordinates are already in WGS84
        return {
            'west': xmin,   # xmin (longitude)
            'south': ymin,  # ymin (latitude)
            'east': xmax,   # xmax (longitude)
            'north': ymax   # ymax (latitude)
        }
    
    def _calculate_optimal_zoom(self, bounds):
        """Calculate optimal zoom level to fit the bounds in view"""
        import math
        
        # Calculate the span of the bounds
        lat_span = bounds['north'] - bounds['south']
        lng_span = bounds['east'] - bounds['west']
        
        # Use the larger span to determine zoom level
        max_span = max(lat_span, lng_span)
        
        # Calculate zoom level based on span
        # This is a simplified calculation - you might want to fine-tune this
        if max_span > 180:
            zoom = 1
        elif max_span > 90:
            zoom = 2
        elif max_span > 45:
            zoom = 3
        elif max_span > 22.5:
            zoom = 4
        elif max_span > 11.25:
            zoom = 5
        elif max_span > 5.625:
            zoom = 6
        elif max_span > 2.813:
            zoom = 7
        elif max_span > 1.406:
            zoom = 8
        elif max_span > 0.703:
            zoom = 9
        elif max_span > 0.352:
            zoom = 10
        elif max_span > 0.176:
            zoom = 11
        elif max_span > 0.088:
            zoom = 12
        elif max_span > 0.044:
            zoom = 13
        elif max_span > 0.022:
            zoom = 14
        elif max_span > 0.011:
            zoom = 15
        elif max_span > 0.0055:
            zoom = 16
        elif max_span > 0.00275:
            zoom = 17
        else:
            zoom = 18
        
        return zoom


def _webhook_payload_snapshot(data):
    """
    Return a deep copy of webhook payload so we store everything exactly as received.
    Handles QueryDict and nested structures; result is JSON-serializable.
    """
    if data is None:
        return {}
    if hasattr(data, 'dict'):
        data = data.dict()
    elif hasattr(data, 'items') and not isinstance(data, dict):
        data = dict(data)
    try:
        return copy.deepcopy(data)
    except Exception:
        return json.loads(json.dumps(data, default=str))


def _print_webhook_response(webhook_name, data):
    """
    Print the entire webhook request body as clear, readable JSON to console and log.
    Use for all webhook endpoints so incoming payload is visible for debugging.
    """
    try:
        if data is None:
            payload = {}
        elif hasattr(data, 'dict'):
            payload = data.dict()
        elif hasattr(data, 'items') and not isinstance(data, dict):
            payload = dict(data)
        else:
            payload = data
        json_str = json.dumps(payload, indent=2, default=str, ensure_ascii=False)
    except Exception as e:
        json_str = f"(could not serialize: {e})"
    sep = "=" * 80
    banner = f"\n{sep}\n  WEBHOOK REQUEST BODY: {webhook_name}\n{sep}"
    print(banner)
    print(json_str)
    print(sep + "\n")
    logger.info("%s\n%s", banner, json_str)


class DeveloperListingMediaWebhookView(APIView):
    """
    Webhook endpoint to receive notifications when developer listing media files
    are uploaded and need tile generation.
    
    Supports: Developer Land and Developer Plot (listing_type: developerland, developerplot).
    
    We store everything from the webhook:
    - WebhookEvent.payload: full request body (every key/value sent by backend)
    - DeveloperListing.listing_data: full listing object (unchanged)
    - DeveloperListingMedia.media_data: full media object per item (unchanged)
    
    This endpoint receives POST requests when:
    - DeveloperLand or DeveloperPlot is created/updated
    - TIF files are uploaded/updated
    
    The service will:
    1. Save full webhook data to database (no fields dropped)
    2. Download TIF files from CloudFront URLs
    3. Generate map tiles from TIF files
    4. Upload tiles to S3 at the specified path
    5. Store TIF metadata and bounds
    """
    permission_classes = [AllowAny]  # Public endpoint (webhook)
    authentication_classes = []  # No authentication required
    http_method_names = ['post']  # Only allow POST requests
    
    def post(self, request):
        """Process webhook and generate tiles for TIF files"""
        from .models import (
            DeveloperListing, DeveloperListingMedia, WebhookEvent
        )
        from django.utils import timezone
        
        logger.info(f"[WEBHOOK_RECEIVE] ===== Webhook POST request received =====")
        logger.info(f"[WEBHOOK_RECEIVE] Request method: {request.method}")
        logger.info(f"[WEBHOOK_RECEIVE] Content-Type: {request.content_type}")
        logger.info(f"[WEBHOOK_RECEIVE] Headers: {dict(request.headers)}")
        
        webhook_event = None
        try:
            # Read body once (stream can only be read once); use it for both parsing and raw storage
            raw_body_full = ''
            try:
                raw_body_full = request.body.decode('utf-8', errors='replace')
            except Exception:
                pass
            import json
            data = {}
            if raw_body_full:
                try:
                    data = json.loads(raw_body_full)
                except Exception:
                    pass
            raw_body_str = raw_body_full[:50000] if len(raw_body_full) > 50000 else raw_body_full
            # Snapshot full payload so we store everything (no keys dropped)
            payload_snapshot = _webhook_payload_snapshot(data)
            # Print entire webhook JSON clearly for debugging
            _print_webhook_response("developer-listing-media", data)
            
            # Validate required fields
            event_type = data.get('event_type')
            listing_type = data.get('listing_type')
            listing_id = data.get('listing_id')
            tif_files = data.get('tif_files', [])
            listing_data = data.get('listing_data', {}) or {}
            media_items = data.get('media_items', []) or []
            action = data.get('action', '')
            
            if not all([event_type, listing_type, listing_id]):
                logger.warning(f"Webhook received with missing required fields: {data}")
                return Response(
                    {"error": "Missing required fields: event_type, listing_type, listing_id"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate event type
            valid_event_types = [
                'developer_listing_created',
                'developer_listing_updated',
                'developer_listing_media_uploaded',
                'developer_listing_media_deleted',
                'developer_listing_listing_deleted'
            ]
            
            if event_type not in valid_event_types:
                logger.warning(f"Webhook received with unknown event_type: {event_type}")
                return Response(
                    {"error": f"Unknown event_type: {event_type}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Save webhook event first – store everything: full payload + raw body (already read above)
            webhook_event = WebhookEvent.objects.create(
                event_type=event_type,
                action=action,
                listing_type=listing_type,
                listing_id=listing_id,
                payload=payload_snapshot,
                raw_body=raw_body_str,
                request_headers=dict(request.headers),
                request_ip=self._get_client_ip(request)
            )
            
            # Handle deletion events (listing/media); we already stored the payload above
            if action == 'listing_deleted':
                logger.info(f"[WEBHOOK_RECEIVE] 🗑️  Listing deletion event received")
                return self._handle_listing_deletion(webhook_event, listing_type, listing_id, data)
            
            if action == 'media_deleted':
                logger.info(f"[WEBHOOK_RECEIVE] 🗑️  Media deletion event received")
                return self._handle_media_deletion(webhook_event, listing_type, listing_id, data, media_items)
            
            logger.info(f"[WEBHOOK_RECEIVE] ===== Webhook received =====")
            logger.info(f"[WEBHOOK_RECEIVE] 📥 Event: {event_type}")
            logger.info(f"[WEBHOOK_RECEIVE] 📥 Action: {action}")
            logger.info(f"[WEBHOOK_RECEIVE] 📥 Listing: {listing_type} ID={listing_id}")
            logger.info(f"[WEBHOOK_RECEIVE] 📥 Media items: {len(media_items)}")
            logger.info(f"[WEBHOOK_RECEIVE] 📥 TIF files: {len(tif_files)}")
            logger.info(f"[WEBHOOK_RECEIVE] 📥 Webhook Event ID: {webhook_event.id}")
            
            # Save/update listing data
            logger.info(f"[WEBHOOK_RECEIVE] 💾 Saving/updating DeveloperListing in database...")
            
            # Extract city from division list if available
            city_name = ''
            if listing_data.get('city'):
                city_name = listing_data.get('city', '')
            elif listing_data.get('division'):
                # division is a list, get first item's name if exists
                division = listing_data.get('division', [])
                if isinstance(division, list) and len(division) > 0:
                    city_name = division[0].get('name', '') if isinstance(division[0], dict) else ''
                elif isinstance(division, dict):
                    city_name = division.get('name', '')
            
            # Store full listing_data (every field from backend; we only extract a few for querying)
            listing_data_stored = _webhook_payload_snapshot(listing_data)
            listing, created = DeveloperListing.objects.update_or_create(
                listing_type=listing_type,
                backend_listing_id=listing_id,
                defaults={
                    'listing_data': listing_data_stored,
                    'name': listing_data.get('name', '') or listing_data.get('title', ''),
                    'description': listing_data.get('description', ''),
                    'location': listing_data.get('location', ''),
                    'city': city_name,
                    'state': listing_data.get('state', ''),
                    'last_webhook_event': event_type,
                    'backend_created_at': self._parse_datetime(listing_data.get('created_at')),
                    'backend_updated_at': self._parse_datetime(listing_data.get('updated_at')),
                }
            )
            # Sync location_point from listing_data for layer enrichment
            point = listing.get_listing_point()
            if point is not None and (listing.location_point is None or listing.location_point.wkt != point.wkt):
                listing.location_point = point
                listing.save(update_fields=['location_point'])
            logger.info(f"[WEBHOOK_RECEIVE] ✅ DeveloperListing {'created' if created else 'updated'}: ID={listing.id}, Name={listing.name}")

            # Sync into SyncedDeveloperLand / SyncedDeveloperPlot so the 4 Synced* tables stay in sync
            from .models import SyncedDeveloperLand, SyncedDeveloperPlot
            from .sync_utils import defaults_for_developer_land, defaults_for_developer_plot
            listing_data_for_sync = dict(listing_data_stored) if listing_data_stored else {}
            listing_data_for_sync['id'] = listing_id
            if listing_type == 'developerland':
                defaults = defaults_for_developer_land(listing_data_for_sync)
                SyncedDeveloperLand.objects.update_or_create(
                    backend_id=listing_id,
                    defaults=defaults,
                )
                logger.info(f"[WEBHOOK_RECEIVE] Synced SyncedDeveloperLand backend_id={listing_id}")
            elif listing_type == 'developerplot':
                defaults = defaults_for_developer_plot(listing_data_for_sync)
                SyncedDeveloperPlot.objects.update_or_create(
                    backend_id=listing_id,
                    defaults=defaults,
                )
                logger.info(f"[WEBHOOK_RECEIVE] Synced SyncedDeveloperPlot backend_id={listing_id}")

            # Run enrichment (state-filtered); no coords or no nearby layers -> enriched_layers=[], enriched_at=None or now
            try:
                from maps.listing_layer_enrichment_service import enrich_listing
                if enrich_listing(listing, update_location_point=True):
                    logger.info(f"[WEBHOOK_RECEIVE] Enriched DeveloperListing {listing_type} {listing_id}")
                else:
                    logger.info(f"[WEBHOOK_RECEIVE] Enrichment skipped/cleared (no coords or no layers) for {listing_type} {listing_id}")
            except Exception as enr_err:
                logger.warning(f"[WEBHOOK_RECEIVE] Enrichment failed for {listing_type} {listing_id}: {enr_err}", exc_info=True)

            # Save/update media files
            logger.info(f"[WEBHOOK_RECEIVE] 💾 Saving/updating {len(media_items)} media files...")
            
            # Track media IDs from webhook payload
            webhook_media_ids = set()
            
            # Import tile service for cleanup (only if needed)
            tile_service_for_cleanup = None
            
            for idx, media_item in enumerate(media_items, 1):
                media_id = media_item.get('id')
                if not media_id:
                    logger.warning(f"[WEBHOOK_RECEIVE] ⚠️  Media item {idx}: No ID found, skipping")
                    continue
                
                webhook_media_ids.add(media_id)
                
                is_tif = media_item.get('is_tif', False)
                file_name = media_item.get('file_name', 'unknown')
                new_s3_tile_path = media_item.get('s3_tile_path', '')
                
                logger.info(f"[WEBHOOK_RECEIVE] 📄 Media {idx}/{len(media_items)}: ID={media_id}, File={file_name}, TIF={is_tif}")
                
                # Check if media already exists and has a different tile path
                # This handles the case where a media is deleted and recreated with same ID but different file/path
                old_media = None
                old_s3_tile_path = None
                try:
                    old_media = DeveloperListingMedia.objects.get(
                        listing=listing,
                        backend_media_id=media_id
                    )
                    old_s3_tile_path = old_media.s3_tile_path
                    
                    # If it's a TIF file, delete old tiles before updating
                    # This handles both cases:
                    # 1. File updated with same name (same path) - need to delete old tiles before generating new ones
                    # 2. File updated with different name (different path) - delete old path, generate to new path
                    if is_tif and old_s3_tile_path:
                        if old_s3_tile_path == new_s3_tile_path:
                            logger.info(f"[WEBHOOK_RECEIVE] 🔄 Media file updated with same name/path: {old_s3_tile_path}")
                            logger.info(f"[WEBHOOK_RECEIVE] 🗑️  Deleting old tiles before generating new ones (same path)...")
                        else:
                            logger.info(f"[WEBHOOK_RECEIVE] 🔄 Media tile path changed: {old_s3_tile_path} → {new_s3_tile_path}")
                            logger.info(f"[WEBHOOK_RECEIVE] 🗑️  Deleting old tiles from old path before updating...")
                        
                        logger.info(f"[WEBHOOK_RECEIVE]    ⚠️  Will ONLY delete tiles for this specific media (ID={media_id}), not other listings/media")
                        
                        if not tile_service_for_cleanup:
                            from .developer_listing_tile_service import DeveloperListingTileService
                            tile_service_for_cleanup = DeveloperListingTileService()
                        
                        # Always delete old tiles, even if path is the same (file replaced with same name)
                        deleted_tiles = tile_service_for_cleanup._delete_s3_tiles(old_s3_tile_path)
                        logger.info(f"[WEBHOOK_RECEIVE] ✅ Deleted {deleted_tiles} old tiles from {old_s3_tile_path} (ONLY for media ID={media_id}, listing #{listing_id})")
                        logger.info(f"[WEBHOOK_RECEIVE] 🆕 New tiles will be generated after this update")
                        
                except DeveloperListingMedia.DoesNotExist:
                    # New media, no cleanup needed
                    pass
                
                # Store full media item (every field from backend)
                media_data_stored = _webhook_payload_snapshot(media_item)
                media_obj, created = DeveloperListingMedia.objects.update_or_create(
                    listing=listing,
                    backend_media_id=media_id,
                    defaults={
                        'media_type': media_item.get('media_type', 'file'),
                        'category': media_item.get('category', ''),
                        'file_name': file_name,
                        'file_url': media_item.get('url', ''),
                        's3_path': media_item.get('s3_path', ''),
                        'is_tif': is_tif,
                        's3_tile_path': new_s3_tile_path,
                        'media_data': media_data_stored,
                    }
                )
                logger.info(f"[WEBHOOK_RECEIVE] ✅ Media {'created' if created else 'updated'}: ID={media_obj.id}")
            
            # Handle deleted media: if action is 'updated', delete media records (and their tiles) 
            # that exist in DB but are not in the webhook payload
            if action in ['updated', 'media_uploaded'] and webhook_media_ids:
                existing_media = DeveloperListingMedia.objects.filter(listing=listing)
                deleted_count = 0
                
                for existing_media_obj in existing_media:
                    if existing_media_obj.backend_media_id not in webhook_media_ids:
                        # This media was deleted from the backend
                        logger.info(f"[WEBHOOK_RECEIVE] 🗑️  Media deleted: ID={existing_media_obj.backend_media_id}, File={existing_media_obj.file_name}")
                        
                        # Delete tiles from S3 if it's a TIF file (ONLY for this specific deleted media)
                        if existing_media_obj.is_tif and existing_media_obj.s3_tile_path:
                            logger.info(f"[WEBHOOK_RECEIVE]    ⚠️  Will ONLY delete tiles for this specific media (ID={existing_media_obj.backend_media_id}), not other files")
                            from .developer_listing_tile_service import DeveloperListingTileService
                            tile_service = DeveloperListingTileService()
                            deleted_tiles = tile_service._delete_s3_tiles(existing_media_obj.s3_tile_path)
                            logger.info(f"[WEBHOOK_RECEIVE] 🗑️  Deleted {deleted_tiles} tiles from S3 for deleted media (ONLY for media ID={existing_media_obj.backend_media_id}, listing #{listing_id})")
                        
                        # Delete the media record
                        existing_media_obj.delete()
                        deleted_count += 1
                
                if deleted_count > 0:
                    logger.info(f"[WEBHOOK_RECEIVE] ✅ Cleaned up {deleted_count} deleted media records and their tiles")
            
            logger.info(f"[WEBHOOK_RECEIVE] ✅ All media files saved")
            
            # Process TIF files if any
            if tif_files:
                logger.info(f"[WEBHOOK_RECEIVE] 🗺️  Processing {len(tif_files)} TIF files for tile generation...")
                from .developer_listing_tile_service import DeveloperListingTileService
                tile_service = DeveloperListingTileService()
                
                logger.info(f"[WEBHOOK_RECEIVE] 🚀 Starting tile generation service...")
                # Process webhook asynchronously (in background)
                # For now, process synchronously - can be moved to Celery/background task later
                result = tile_service.process_webhook(data, listing=listing, webhook_event=webhook_event)
                logger.info(f"[WEBHOOK_RECEIVE] ✅ Tile generation completed: {result.get('total_tiles_generated', 0)} tiles")
                
                # Update webhook event with results
                webhook_event.processed = True
                webhook_event.processed_at = timezone.now()
                webhook_event.tiles_generated = result.get('total_tiles_generated', 0)
                webhook_event.tif_files_processed = result.get('tif_files_processed', 0)
                webhook_event.processing_result = result
                webhook_event.save()
                
                if result.get('success'):
                    logger.info(
                        f"Successfully processed webhook: "
                        f"{result.get('total_tiles_generated', 0)} tiles generated"
                    )
                    return Response(
                        {
                            "status": "success",
                            "message": f"Webhook processed for {listing_type} {listing_id}",
                            "tiles_generated": result.get('total_tiles_generated', 0),
                            "tif_files_processed": result.get('tif_files_processed', 0),
                            "details": result
                        },
                        status=status.HTTP_200_OK
                    )
                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.error(f"[WEBHOOK_RECEIVE] ❌ Error processing tiles: {error_msg}")
                    webhook_event.processing_error = error_msg
                    webhook_event.save()
                    logger.error(f"[WEBHOOK_RECEIVE] ===== Webhook processing failed =====")
                    return Response(
                        {
                            "status": "error",
                            "message": f"Error processing tiles: {result.get('error')}",
                            "details": result
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            else:
                # No TIF files to process - mark as processed
                logger.info(f"[WEBHOOK_RECEIVE] ⚠️  No TIF files to process for {listing_type} {listing_id}")
                logger.info(f"[WEBHOOK_RECEIVE] 💾 Marking webhook event as processed...")
                webhook_event.processed = True
                webhook_event.processed_at = timezone.now()
                webhook_event.save()
                logger.info(f"[WEBHOOK_RECEIVE] ✅ Webhook event marked as processed")
                logger.info(f"[WEBHOOK_RECEIVE] ===== Webhook processing completed (no TIF files) =====")
                return Response(
                    {
                        "status": "success",
                        "message": f"Webhook received for {listing_type} {listing_id}",
                        "tiles_generated": 0,
                        "note": "No TIF files found in webhook payload"
                    },
                    status=status.HTTP_200_OK
                )
                
        except Exception as e:
            logger.error(f"[WEBHOOK_RECEIVE] ❌ Exception processing developer listing webhook: {e}", exc_info=True)
            if webhook_event:
                logger.error(f"[WEBHOOK_RECEIVE] 💾 Saving error to webhook event...")
                webhook_event.processing_error = str(e)
                webhook_event.save()
                logger.error(f"[WEBHOOK_RECEIVE] ✅ Error saved")
            logger.error(f"[WEBHOOK_RECEIVE] ===== Webhook processing failed with exception =====")
            return Response(
                {
                    "error": "Internal server error processing webhook",
                    "details": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _handle_listing_deletion(self, webhook_event, listing_type, listing_id, data):
        """
        Handle listing deletion webhook
        Deletes all tiles and removes listing from database
        """
        from django.utils import timezone
        from .models import DeveloperListing, DeveloperListingMedia
        from .developer_listing_tile_service import DeveloperListingTileService
        
        logger.info(f"[WEBHOOK_DELETE] ===== Processing listing deletion =====")
        logger.info(f"[WEBHOOK_DELETE] Listing: {listing_type} ID={listing_id}")
        
        try:
            # Find the listing
            try:
                listing = DeveloperListing.objects.get(
                    listing_type=listing_type,
                    backend_listing_id=listing_id
                )
            except DeveloperListing.DoesNotExist:
                logger.warning(f"[WEBHOOK_DELETE] ⚠️  Listing not found: {listing_type} {listing_id}")
                # Mark as processed even if not found (might have been deleted already)
                webhook_event.processed = True
                webhook_event.processed_at = timezone.now()
                webhook_event.processing_result = {'note': 'Listing not found in database'}
                webhook_event.save()
                return Response(
                    {
                        "status": "success",
                        "message": f"Listing {listing_type} {listing_id} not found (may have been deleted already)",
                        "tiles_deleted": 0
                    },
                    status=status.HTTP_200_OK
                )
            
            # Get all media for this SPECIFIC listing only (e.g., listing ID 70)
            # This ensures we only delete tiles for this listing, not all listings
            all_media = DeveloperListingMedia.objects.filter(listing=listing)
            total_tiles_deleted = 0
            
            logger.info(f"[WEBHOOK_DELETE] 📋 Found {all_media.count()} media files for listing {listing_type} #{listing_id}")
            
            # Delete tiles for each TIF media file (ONLY for this specific listing)
            tile_service = DeveloperListingTileService()
            for media in all_media:
                if media.is_tif and media.s3_tile_path:
                    logger.info(f"[WEBHOOK_DELETE] 🗑️  Deleting tiles for media: {media.file_name} (path: {media.s3_tile_path})")
                    logger.info(f"[WEBHOOK_DELETE]    ⚠️  This will ONLY delete tiles for this specific media file, not other listings")
                    deleted_count = tile_service._delete_s3_tiles(media.s3_tile_path)
                    total_tiles_deleted += deleted_count
                    logger.info(f"[WEBHOOK_DELETE] ✅ Deleted {deleted_count} tiles for {media.file_name} (ONLY for listing #{listing_id})")
            
            # Delete all media records (CASCADE will handle this, but we do it explicitly for logging)
            media_count = all_media.count()
            all_media.delete()
            logger.info(f"[WEBHOOK_DELETE] ✅ Deleted {media_count} media records")

            # Delete the listing record
            listing.delete()
            logger.info(f"[WEBHOOK_DELETE] ✅ Deleted listing record")

            # Keep SyncedDeveloperLand / SyncedDeveloperPlot in sync
            from .models import SyncedDeveloperLand, SyncedDeveloperPlot
            if listing_type == 'developerland':
                SyncedDeveloperLand.objects.filter(backend_id=listing_id).delete()
                logger.info(f"[WEBHOOK_DELETE] Deleted SyncedDeveloperLand backend_id={listing_id}")
            elif listing_type == 'developerplot':
                SyncedDeveloperPlot.objects.filter(backend_id=listing_id).delete()
                logger.info(f"[WEBHOOK_DELETE] Deleted SyncedDeveloperPlot backend_id={listing_id}")
            
            # Mark webhook as processed
            webhook_event.processed = True
            webhook_event.processed_at = timezone.now()
            webhook_event.tiles_generated = 0  # No tiles generated, but we track deletions
            webhook_event.processing_result = {
                'tiles_deleted': total_tiles_deleted,
                'media_records_deleted': media_count,
                'listing_deleted': True
            }
            webhook_event.save()
            
            logger.info(f"[WEBHOOK_DELETE] ✅ Listing deletion completed")
            logger.info(f"[WEBHOOK_DELETE]    - Tiles deleted: {total_tiles_deleted}")
            logger.info(f"[WEBHOOK_DELETE]    - Media records deleted: {media_count}")
            logger.info(f"[WEBHOOK_DELETE] ===== Listing deletion processing completed =====")
            
            return Response(
                {
                    "status": "success",
                    "message": f"Listing {listing_type} {listing_id} deleted successfully",
                    "tiles_deleted": total_tiles_deleted,
                    "media_records_deleted": media_count
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"[WEBHOOK_DELETE] ❌ Error processing listing deletion: {e}", exc_info=True)
            webhook_event.processing_error = str(e)
            webhook_event.save()
            return Response(
                {
                    "status": "error",
                    "message": f"Error processing listing deletion: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _handle_media_deletion(self, webhook_event, listing_type, listing_id, data, media_items):
        """
        Handle media deletion webhook
        Deletes tiles for deleted media and removes media records from database
        """
        from django.utils import timezone
        from .models import DeveloperListing, DeveloperListingMedia
        from .developer_listing_tile_service import DeveloperListingTileService
        
        logger.info(f"[WEBHOOK_DELETE] ===== Processing media deletion =====")
        logger.info(f"[WEBHOOK_DELETE] Listing: {listing_type} ID={listing_id}")
        logger.info(f"[WEBHOOK_DELETE] Media items in payload: {len(media_items)}")
        
        try:
            # Find the listing
            try:
                listing = DeveloperListing.objects.get(
                    listing_type=listing_type,
                    backend_listing_id=listing_id
                )
            except DeveloperListing.DoesNotExist:
                logger.warning(f"[WEBHOOK_DELETE] ⚠️  Listing not found: {listing_type} {listing_id}")
                webhook_event.processed = True
                webhook_event.processed_at = timezone.now()
                webhook_event.processing_result = {'note': 'Listing not found in database'}
                webhook_event.save()
                return Response(
                    {
                        "status": "success",
                        "message": f"Listing {listing_type} {listing_id} not found",
                        "tiles_deleted": 0
                    },
                    status=status.HTTP_200_OK
                )
            
            # Find deleted media items (those marked with 'deleted': true)
            # This ensures we ONLY delete tiles for the specific deleted media files, not all media
            deleted_media_items = [m for m in media_items if m.get('deleted', False)]
            logger.info(f"[WEBHOOK_DELETE] Found {len(deleted_media_items)} deleted media items (will ONLY delete tiles for these specific files)")
            
            total_tiles_deleted = 0
            deleted_media_count = 0
            
            tile_service = DeveloperListingTileService()
            
            # Process each deleted media item (ONLY these specific files)
            for deleted_media in deleted_media_items:
                media_id = deleted_media.get('id')
                file_name = deleted_media.get('file_name', 'unknown')
                s3_tile_path = deleted_media.get('s3_tile_path', '')
                is_tif = deleted_media.get('is_tif', False)
                
                logger.info(f"[WEBHOOK_DELETE] 🗑️  Processing deleted media: ID={media_id}, File={file_name}, TIF={is_tif}")
                logger.info(f"[WEBHOOK_DELETE]    ⚠️  Will ONLY delete tiles for this specific media file (ID={media_id}), not other files")
                
                # Delete tiles from S3 if it's a TIF file (ONLY for this specific media)
                if is_tif and s3_tile_path:
                    logger.info(f"[WEBHOOK_DELETE] 🗑️  Deleting tiles from S3 path: {s3_tile_path}")
                    logger.info(f"[WEBHOOK_DELETE]    ⚠️  This will ONLY delete tiles matching this path prefix, not other listings/media")
                    deleted_count = tile_service._delete_s3_tiles(s3_tile_path)
                    total_tiles_deleted += deleted_count
                    logger.info(f"[WEBHOOK_DELETE] ✅ Deleted {deleted_count} tiles for {file_name} (ONLY for media ID={media_id}, listing #{listing_id})")
                elif is_tif:
                    logger.warning(f"[WEBHOOK_DELETE] ⚠️  TIF file {file_name} has no s3_tile_path, skipping tile deletion")
                
                # Delete the media record from database
                try:
                    media_obj = DeveloperListingMedia.objects.get(
                        listing=listing,
                        backend_media_id=media_id
                    )
                    media_obj.delete()
                    deleted_media_count += 1
                    logger.info(f"[WEBHOOK_DELETE] ✅ Deleted media record: ID={media_id}")
                except DeveloperListingMedia.DoesNotExist:
                    logger.warning(f"[WEBHOOK_DELETE] ⚠️  Media record not found: ID={media_id} (may have been deleted already)")
            
            # Update remaining media items (those not deleted)
            remaining_media_items = [m for m in media_items if not m.get('deleted', False)]
            logger.info(f"[WEBHOOK_DELETE] Updating {len(remaining_media_items)} remaining media items...")
            
            for media_item in remaining_media_items:
                media_id = media_item.get('id')
                if not media_id:
                    continue
                
                DeveloperListingMedia.objects.update_or_create(
                    listing=listing,
                    backend_media_id=media_id,
                    defaults={
                        'media_type': media_item.get('media_type', 'file'),
                        'category': media_item.get('category', ''),
                        'file_name': media_item.get('file_name', ''),
                        'file_url': media_item.get('url', ''),
                        's3_path': media_item.get('s3_path', ''),
                        'is_tif': media_item.get('is_tif', False),
                        's3_tile_path': media_item.get('s3_tile_path', ''),
                        'media_data': media_item,
                    }
                )
            
            logger.info(f"[WEBHOOK_DELETE] ✅ Updated remaining media items")
            
            # Mark webhook as processed
            webhook_event.processed = True
            webhook_event.processed_at = timezone.now()
            webhook_event.tiles_generated = 0
            webhook_event.processing_result = {
                'tiles_deleted': total_tiles_deleted,
                'media_records_deleted': deleted_media_count,
                'remaining_media_count': len(remaining_media_items)
            }
            webhook_event.save()
            
            logger.info(f"[WEBHOOK_DELETE] ✅ Media deletion completed")
            logger.info(f"[WEBHOOK_DELETE]    - Tiles deleted: {total_tiles_deleted}")
            logger.info(f"[WEBHOOK_DELETE]    - Media records deleted: {deleted_media_count}")
            logger.info(f"[WEBHOOK_DELETE]    - Remaining media: {len(remaining_media_items)}")
            logger.info(f"[WEBHOOK_DELETE] ===== Media deletion processing completed =====")
            
            return Response(
                {
                    "status": "success",
                    "message": f"Media deletion processed for {listing_type} {listing_id}",
                    "tiles_deleted": total_tiles_deleted,
                    "media_records_deleted": deleted_media_count,
                    "remaining_media_count": len(remaining_media_items)
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"[WEBHOOK_DELETE] ❌ Error processing media deletion: {e}", exc_info=True)
            webhook_event.processing_error = str(e)
            webhook_event.save()
            return Response(
                {
                    "status": "error",
                    "message": f"Error processing media deletion: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _parse_datetime(self, dt_string):
        """Parse datetime string from backend"""
        if not dt_string:
            return None
        from django.utils.dateparse import parse_datetime
        return parse_datetime(dt_string)


class LandPlotWebhookView(APIView):
    """
    Webhook endpoint for Land and Plot (regular listings) from 1acre-be.
    Receives create/update/delete events with full listing_data.
    Same pattern as DeveloperListingMediaWebhookView.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ['post']

    def post(self, request):
        from .models import LandPlotWebhookEvent, SyncedLand, SyncedPlot
        from .sync_utils import defaults_for_land, defaults_for_plot

        logger.info("[LAND_PLOT_WEBHOOK] ===== Land/Plot webhook POST received =====")
        try:
            # Read raw body first (only one read allowed; request.data would consume the stream)
            raw_body = ''
            try:
                _req = getattr(request, '_request', request)
                raw_body = (_req.body.decode('utf-8', errors='replace')
                            if getattr(_req, 'body', None) else '')
            except Exception:
                pass
            # Parse JSON from raw body so we never touch request.body again
            data = {}
            if raw_body and raw_body.strip():
                try:
                    data = json.loads(raw_body)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"[LAND_PLOT_WEBHOOK] Could not parse JSON body: {e}")
                    return Response(
                        {"error": "Invalid JSON body"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            if not isinstance(data, dict):
                data = {}
            # Snapshot full payload so we save everything (same pattern as developer listing webhook)
            payload_snapshot = _webhook_payload_snapshot(data)
            # Print entire webhook JSON clearly for debugging
            _print_webhook_response("land-plot", data)
            # Truncate raw_body for storage if needed (already have full string above)
            if len(raw_body) > 50000:
                raw_body = raw_body[:50000]

            event_type = data.get('event_type')
            action = data.get('action')
            listing_type = data.get('listing_type')
            listing_id = data.get('listing_id')
            listing_data = data.get('listing_data', {})

            if not all([event_type, action, listing_type, listing_id is not None]):
                return Response(
                    {"error": "Missing required fields: event_type, action, listing_type, listing_id"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if event_type not in ('listing_created', 'listing_updated', 'listing_deleted'):
                return Response(
                    {"error": f"Unknown event_type: {event_type}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if listing_type not in ('land', 'plot'):
                return Response(
                    {"error": f"Unknown listing_type: {listing_type}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            ip = self._get_client_ip(request)
            LandPlotWebhookEvent.objects.create(
                event_type=event_type,
                action=action,
                listing_type=listing_type,
                listing_id=listing_id,
                payload=payload_snapshot,
                raw_body=raw_body,
                request_headers=dict(request.headers),
                request_ip=ip,
            )
            logger.info(f"[LAND_PLOT_WEBHOOK] Saved: {action} {listing_type} {listing_id}")

            # Sync into SyncedLand / SyncedPlot so DB stays in sync with 1acre-be
            if action in ('created', 'updated'):
                item = dict(listing_data) if listing_data else {}
                item['id'] = listing_id  # ensure id present for payload
                if listing_type == 'land':
                    defaults = defaults_for_land(item)
                    record, _ = SyncedLand.objects.update_or_create(
                        backend_id=listing_id,
                        defaults=defaults,
                    )
                    logger.info(f"[LAND_PLOT_WEBHOOK] Synced SyncedLand backend_id={listing_id}")
                else:
                    defaults = defaults_for_plot(item)
                    record, _ = SyncedPlot.objects.update_or_create(
                        backend_id=listing_id,
                        defaults=defaults,
                    )
                    logger.info(f"[LAND_PLOT_WEBHOOK] Synced SyncedPlot backend_id={listing_id}")
                # Run enrichment (state-filtered); no coords or no nearby layers -> enriched_layers=[], enriched_at=None or now
                try:
                    from maps.listing_layer_enrichment_service import enrich_synced_record
                    if enrich_synced_record(record, update_location_point=True):
                        logger.info(f"[LAND_PLOT_WEBHOOK] Enriched {listing_type} {listing_id}")
                    else:
                        logger.info(f"[LAND_PLOT_WEBHOOK] Enrichment skipped/cleared (no coords or no layers) for {listing_type} {listing_id}")
                except Exception as enr_err:
                    logger.warning(f"[LAND_PLOT_WEBHOOK] Enrichment failed for {listing_type} {listing_id}: {enr_err}", exc_info=True)
            elif action == 'deleted':
                if listing_type == 'land':
                    deleted, _ = SyncedLand.objects.filter(backend_id=listing_id).delete()
                    if deleted:
                        logger.info(f"[LAND_PLOT_WEBHOOK] Deleted SyncedLand backend_id={listing_id}")
                else:
                    deleted, _ = SyncedPlot.objects.filter(backend_id=listing_id).delete()
                    if deleted:
                        logger.info(f"[LAND_PLOT_WEBHOOK] Deleted SyncedPlot backend_id={listing_id}")

            return Response(
                {"status": "success", "event_type": event_type, "listing_type": listing_type, "listing_id": listing_id},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"[LAND_PLOT_WEBHOOK] Error: {e}", exc_info=True)
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class DeveloperListingDetailAPIView(APIView):
    """
    API endpoint to retrieve complete developer listing details
    including media files, TIF metadata, and webhook events.
    
    GET /api/developer-listings/{listing_type}/{listing_id}/
    
    Returns:
    - Complete listing data
    - All media files with TIF metadata
    - Tile generation status
    - Recent webhook events
    - Media and tile summaries
    """
    permission_classes = [AllowAny]  # Make public or add authentication as needed
    
    def get(self, request, listing_type, listing_id):
        """Get complete details for a developer listing"""
        from .models import DeveloperListing
        from .serializers import DeveloperListingDetailSerializer
        
        try:
            # Validate listing_type
            if listing_type not in ['developerland', 'developerplot']:
                return Response(
                    {'error': f'Invalid listing_type. Must be "developerland" or "developerplot"'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get listing
            try:
                listing = DeveloperListing.objects.prefetch_related(
                    'media_files',
                    'media_files__tif_metadata'
                ).get(
                    listing_type=listing_type,
                    backend_listing_id=listing_id
                )
            except DeveloperListing.DoesNotExist:
                return Response(
                    {
                        'error': f'Listing not found',
                        'listing_type': listing_type,
                        'listing_id': listing_id
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Serialize and return
            serializer = DeveloperListingDetailSerializer(listing)
            
            return Response(
                {
                    'success': True,
                    'listing': serializer.data
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error retrieving developer listing details: {e}", exc_info=True)
            return Response(
                {
                    'error': 'Internal server error',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeveloperListingListAPIView(APIView):
    """
    API endpoint to list all developer listings with filtering
    
    GET /api/developer-listings/
    
    Query parameters:
    - listing_type: Filter by type (developerland, developerplot)
    - city: Filter by city name
    - state: Filter by state name
    - is_active: Filter by active status (true/false)
    - has_tiles: Filter listings with TIF tiles (true/false)
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """List developer listings with filtering"""
        from .models import DeveloperListing
        from .serializers import DeveloperListingSerializer
        
        try:
            # Get query parameters
            listing_type = request.query_params.get('listing_type')
            city = request.query_params.get('city')
            state = request.query_params.get('state')
            is_active = request.query_params.get('is_active')
            has_tiles = request.query_params.get('has_tiles')
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
            
            # Build queryset
            queryset = DeveloperListing.objects.prefetch_related('media_files').all()
            
            # Apply filters
            if listing_type:
                if listing_type not in ['developerland', 'developerplot']:
                    return Response(
                        {'error': 'Invalid listing_type. Must be "developerland" or "developerplot"'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                queryset = queryset.filter(listing_type=listing_type)
            
            if city:
                queryset = queryset.filter(city__icontains=city)
            
            if state:
                queryset = queryset.filter(state__icontains=state)
            
            if is_active is not None:
                is_active_bool = is_active.lower() == 'true'
                queryset = queryset.filter(is_active=is_active_bool)
            
            if has_tiles is not None:
                has_tiles_bool = has_tiles.lower() == 'true'
                if has_tiles_bool:
                    # Filter listings that have at least one TIF with generated tiles
                    queryset = queryset.filter(
                        media_files__is_tif=True,
                        media_files__tiles_generated=True
                    ).distinct()
                else:
                    # Filter listings without any generated TIF tiles
                    from django.db.models import Q
                    queryset = queryset.exclude(
                        media_files__is_tif=True,
                        media_files__tiles_generated=True
                    ).distinct()
            
            # Order by most recent
            queryset = queryset.order_by('-created_at')
            
            # Pagination
            total_count = queryset.count()
            start = (page - 1) * page_size
            end = start + page_size
            listings = queryset[start:end]
            
            # Serialize
            serializer = DeveloperListingSerializer(listings, many=True)
            
            return Response(
                {
                    'success': True,
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total_count': total_count,
                        'total_pages': (total_count + page_size - 1) // page_size,
                        'has_next': end < total_count,
                        'has_previous': page > 1
                    },
                    'filters': {
                        'listing_type': listing_type,
                        'city': city,
                        'state': state,
                        'is_active': is_active,
                        'has_tiles': has_tiles
                    },
                    'listings': serializer.data
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error listing developer listings: {e}", exc_info=True)
            return Response(
                {
                    'error': 'Internal server error',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EnrichmentLookupAPIView(APIView):
    """
    POST API: return enrichment and full record data for land/plot/developer_land/developer_plot by IDs.

    POST /api/enrichment-lookup/
    Body: { "listing_type": "land"|"plot"|"developer_land"|"developer_plot", "ids": [1, 2, 3] }
    ids can be either Django primary keys (id) or backend_id (1acre-be API id); both are matched.

    Returns: { "results": [ {...}, ... ], "count": N } with enrichment (enriched_layers, enriched_at, location_point)
    and all other model fields + payload.
    """
    permission_classes = [AllowAny]

    # Map listing_type -> (Model, backend_id field name)
    _MODEL_MAP = None

    @classmethod
    def _get_model_map(cls):
        if cls._MODEL_MAP is None:
            from .models import SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot
            cls._MODEL_MAP = {
                'land': SyncedLand,
                'plot': SyncedPlot,
                'developer_land': SyncedDeveloperLand,
                'developer_plot': SyncedDeveloperPlot,
            }
        return cls._MODEL_MAP

    @staticmethod
    def _serialize_point(point):
        if point is None:
            return None
        try:
            return {'type': 'Point', 'coordinates': [point.x, point.y]}
        except Exception:
            return None

    def _record_to_dict(self, obj):
        """Build a dict with all fields + enrichment for one synced record."""
        from django.forms.models import model_to_dict
        d = model_to_dict(obj, exclude=['location_point'])
        d['id'] = obj.pk
        d['backend_id'] = getattr(obj, 'backend_id', None)
        raw_layers = getattr(obj, 'enriched_layers', []) or []
        d['enriched_layers'] = [dict(entry) for entry in raw_layers]
        d['enriched_at'] = obj.enriched_at.isoformat() if getattr(obj, 'enriched_at', None) else None
        d['location_point'] = self._serialize_point(getattr(obj, 'location_point', None))
        if hasattr(obj, 'lat') and obj.lat is not None:
            d['lat'] = obj.lat
        if hasattr(obj, 'long') and obj.long is not None:
            d['long'] = obj.long
        d['payload'] = getattr(obj, 'payload', {}) or {}
        d['synced_at'] = obj.synced_at.isoformat() if getattr(obj, 'synced_at', None) else None
        # True when no coordinates -> enrichment not run or cleared; client can treat as null/false
        has_point = getattr(obj, 'location_point', None) is not None
        if not has_point and hasattr(obj, 'lat') and hasattr(obj, 'long'):
            has_point = obj.lat is not None and obj.long is not None
        if not has_point and hasattr(obj, 'payload') and obj.payload:
            p = obj.payload
            has_point = (p.get('lat') or p.get('latitude')) is not None and (p.get('long') or p.get('lng') or p.get('longitude')) is not None
        d['enrichment_skipped'] = not has_point
        return d

    def post(self, request):
        from .models import SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot

        try:
            data = request.data if getattr(request, 'data', None) is not None else {}
            if not isinstance(data, dict):
                return Response(
                    {'error': 'Request body must be JSON with listing_type and ids'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            listing_type = (data.get('listing_type') or '').strip().lower()
            ids = data.get('ids')
            if not listing_type:
                return Response(
                    {'error': 'Missing listing_type. Use one of: land, plot, developer_land, developer_plot'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            model_map = self._get_model_map()
            if listing_type not in model_map:
                return Response(
                    {'error': f'Invalid listing_type "{listing_type}". Use one of: land, plot, developer_land, developer_plot'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if ids is None:
                ids = []
            if not isinstance(ids, list):
                ids = [ids] if ids is not None else []
            ids = [int(x) for x in ids if x is not None and str(x).strip() != '']
            ids = list(dict.fromkeys(ids))

            model = model_map[listing_type]
            if ids:
                qs = model.objects.filter(
                    Q(backend_id__in=ids) | Q(pk__in=ids)
                ).distinct()
            else:
                qs = model.objects.none()
            records = list(qs)
            results = [self._record_to_dict(r) for r in records]

            # Resolve "place" (specific feature) for each enriched layer, like CoordinateSearchTestView
            from .listing_layer_enrichment_service import get_place_for_point_in_layer
            from django.contrib.gis.geos import Point
            for record, result in zip(records, results):
                point = getattr(record, 'location_point', None)
                if point is None and getattr(record, 'long', None) is not None and getattr(record, 'lat', None) is not None:
                    try:
                        point = Point(float(record.long), float(record.lat), srid=4326)
                    except (TypeError, ValueError):
                        point = None
                if point is None:
                    continue
                enriched = result.get('enriched_layers') or []
                for layer_entry in enriched:
                    layer_id = layer_entry.get('layer_id')
                    distance_km = layer_entry.get('distance_km', 0)
                    if layer_id is not None:
                        place = get_place_for_point_in_layer(point, layer_id, distance_km)
                        layer_entry['place'] = place

            return Response(
                {
                    'listing_type': listing_type,
                    'count': len(results),
                    'results': results,
                },
                status=status.HTTP_200_OK
            )
        except (ValueError, TypeError) as e:
            return Response(
                {'error': 'ids must be a list of integers', 'details': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Enrichment lookup error: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeveloperListingMediaDetailAPIView(APIView):
    """
    API endpoint to retrieve detailed information about a specific media file
    including TIF metadata if applicable
    
    GET /api/developer-listing-media/{media_id}/
    """
    permission_classes = [AllowAny]
    
    def get(self, request, media_id):
        """Get detailed information for a media file"""
        from .models import DeveloperListingMedia
        from .serializers import DeveloperListingMediaSerializer
        
        try:
            # Get media
            try:
                media = DeveloperListingMedia.objects.select_related(
                    'listing',
                    'tif_metadata'
                ).get(id=media_id)
            except DeveloperListingMedia.DoesNotExist:
                return Response(
                    {'error': f'Media file not found with id {media_id}'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Serialize and return
            serializer = DeveloperListingMediaSerializer(media)
            
            return Response(
                {
                    'success': True,
                    'media': serializer.data,
                    'listing': {
                        'id': media.listing.id,
                        'listing_type': media.listing.listing_type,
                        'backend_listing_id': media.listing.backend_listing_id,
                        'name': media.listing.name
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error retrieving media details: {e}", exc_info=True)
            return Response(
                {
                    'error': 'Internal server error',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WebhookEventListAPIView(APIView):
    """
    API endpoint to list webhook events with filtering
    
    GET /api/webhook-events/
    
    Query parameters:
    - listing_type: Filter by listing type
    - listing_id: Filter by listing ID
    - event_type: Filter by event type
    - processed: Filter by processed status (true/false)
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """List webhook events with filtering"""
        from .models import WebhookEvent
        from .serializers import WebhookEventSerializer
        
        try:
            # Get query parameters
            listing_type = request.query_params.get('listing_type')
            listing_id = request.query_params.get('listing_id')
            event_type = request.query_params.get('event_type')
            processed = request.query_params.get('processed')
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
            
            # Build queryset
            queryset = WebhookEvent.objects.all()
            
            # Apply filters
            if listing_type:
                queryset = queryset.filter(listing_type=listing_type)
            
            if listing_id:
                try:
                    listing_id_int = int(listing_id)
                    queryset = queryset.filter(listing_id=listing_id_int)
                except ValueError:
                    return Response(
                        {'error': 'Invalid listing_id. Must be an integer'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if event_type:
                queryset = queryset.filter(event_type=event_type)
            
            if processed is not None:
                processed_bool = processed.lower() == 'true'
                queryset = queryset.filter(processed=processed_bool)
            
            # Order by most recent
            queryset = queryset.order_by('-received_at')
            
            # Pagination
            total_count = queryset.count()
            start = (page - 1) * page_size
            end = start + page_size
            events = queryset[start:end]
            
            # Serialize
            serializer = WebhookEventSerializer(events, many=True)
            
            return Response(
                {
                    'success': True,
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total_count': total_count,
                        'total_pages': (total_count + page_size - 1) // page_size,
                        'has_next': end < total_count,
                        'has_previous': page > 1
                    },
                    'filters': {
                        'listing_type': listing_type,
                        'listing_id': listing_id,
                        'event_type': event_type,
                        'processed': processed
                    },
                    'events': serializer.data
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error listing webhook events: {e}", exc_info=True)
            return Response(
                {
                    'error': 'Internal server error',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    summary="Check if point is inside Hyderabad HMDA Extended Area",
    description="Check whether a given coordinate point is inside the Hyderabad HMDA Extended Area boundary. Returns true if inside, false if outside.",
    parameters=[
        OpenApiParameter(
            name='lat',
            type=float,
            location=OpenApiParameter.QUERY,
            required=True,
            description='Latitude of the point to check'
        ),
        OpenApiParameter(
            name='lng',
            type=float,
            location=OpenApiParameter.QUERY,
            required=True,
            description='Longitude of the point to check'
        )
    ],
    responses={
        200: extend_schema(
            description="Successfully checked point location",
            examples=[
                OpenApiExample(
                    'Point Inside Boundary',
                    value={
                        "success": True,
                        "is_inside": True,
                        "message": "Point is inside Hyderabad HMDA Extended Area",
                        "point": {
                            "latitude": 17.3850,
                            "longitude": 78.4867,
                            "coordinates": [78.4867, 17.3850]
                        },
                        "layer": {
                            "slug": "hyderabad_hmda_extended_area",
                            "name": "Hyderabad HMDA Extended Area",
                            "city": "hyderabad",
                            "state": "telangana"
                        }
                    }
                ),
                OpenApiExample(
                    'Point Outside Boundary',
                    value={
                        "success": True,
                        "is_inside": False,
                        "message": "Point is outside Hyderabad HMDA Extended Area",
                        "point": {
                            "latitude": 12.9716,
                            "longitude": 77.5946,
                            "coordinates": [77.5946, 12.9716]
                        },
                        "layer": {
                            "slug": "hyderabad_hmda_extended_area",
                            "name": "Hyderabad HMDA Extended Area",
                            "city": "hyderabad",
                            "state": "telangana"
                        }
                    }
                )
            ]
        ),
        400: extend_schema(
            description="Invalid request parameters",
            examples=[
                OpenApiExample(
                    'Missing Parameters',
                    value={
                        "success": False,
                        "error": "Missing required parameters: lat and lng"
                    }
                ),
                OpenApiExample(
                    'Invalid Coordinates',
                    value={
                        "success": False,
                        "error": "Invalid coordinates: lat must be between -90 and 90, lng between -180 and 180"
                    }
                )
            ]
        ),
        404: extend_schema(
            description="Layer not found",
            examples=[
                OpenApiExample(
                    'Layer Not Found',
                    value={
                        "success": False,
                        "error": "Hyderabad HMDA Extended Area layer not found"
                    }
                )
            ]
        )
    },
    tags=['boundary-check']
)
class HyderabadHMDABoundaryCheckAPIView(APIView):
    """
    API endpoint to check if a point is inside the Hyderabad HMDA Extended Area boundary.
    
    URL: /api/check-hmda-boundary/?lat={latitude}&lng={longitude}
    
    Returns:
    - is_inside: boolean - true if point is inside boundary, false if outside
    - message: descriptive message
    - point: coordinates that were checked
    - layer: information about the HMDA boundary layer
    
    Example:
    - /api/check-hmda-boundary/?lat=17.3850&lng=78.4867
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Check if point is inside Hyderabad HMDA Extended Area"""
        try:
            # Get query parameters
            lat = request.GET.get('lat')
            lng = request.GET.get('lng')
            
            # Validate required parameters
            if not lat or not lng:
                return Response({
                    'success': False,
                    'error': 'Missing required parameters: lat and lng'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate and convert coordinates
            try:
                latitude = float(lat)
                longitude = float(lng)
            except ValueError:
                return Response({
                    'success': False,
                    'error': 'Invalid coordinate format: lat and lng must be valid numbers'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate coordinate ranges
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                return Response({
                    'success': False,
                    'error': 'Invalid coordinates: lat must be between -90 and 90, lng between -180 and 180'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get the Hyderabad HMDA Extended Area layer
            try:
                layer = DataLayer.objects.select_related('city', 'city__state_ref').get(
                    slug='hyderabad_hmda_extended_area',
                    is_processed=True
                )
            except DataLayer.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Hyderabad HMDA Extended Area layer not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Create point geometry
            search_point = Point(longitude, latitude, srid=4326)
            
            # Check if point is inside any feature of the HMDA boundary layer
            # Use contains for exact boundary check (no buffer)
            is_inside = GeoFeature.objects.filter(
                layer=layer,
                is_valid=True,
                geometry__contains=search_point
            ).exists()
            
            # Prepare response
            response_data = {
                'success': True,
                'is_inside': is_inside,
                'message': f"Point is {'inside' if is_inside else 'outside'} Hyderabad HMDA Extended Area",
                'point': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'coordinates': [longitude, latitude]
                },
                'layer': {
                    'slug': layer.slug,
                    'name': layer.name,
                    'city': layer.city.slug,
                    'city_name': layer.city.name,
                    'state': layer.city.state_ref.slug if layer.city.state_ref else None,
                    'state_name': layer.city.state_ref.name if layer.city.state_ref else None
                }
            }
            
            logger.info(
                f"HMDA Boundary Check: Point ({latitude}, {longitude}) is "
                f"{'inside' if is_inside else 'outside'} boundary"
            )
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in HyderabadHMDABoundaryCheckAPIView: {e}", exc_info=True)
            return Response({
                'success': False,
                'error': 'Internal server error',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeveloperListingMapDataAPIView(APIView):
    """
    Lightweight API endpoint to get only map-related data for a developer listing.
    Returns bounds, zoom level, and S3 tile paths - everything needed to display on map.
    
    GET /api/developer-listings/{listing_type}/{listing_id}/map-data/
    
    Returns:
    - Bounds (west, south, east, north)
    - Zoom levels (min, max, recommended)
    - Center coordinates
    - S3 tile paths for all TIF files
    - Minimal listing info (name, location)
    
    Much lighter and faster than the full detail API.
    """
    permission_classes = [AllowAny]
    
    def get(self, request, listing_type, listing_id):
        """Get map data for a developer listing"""
        from .models import DeveloperListing, TIFMetadata, DeveloperListingMedia
        
        try:
            # Validate listing_type
            if listing_type not in ['developerland', 'developerplot']:
                return Response(
                    {'error': f'Invalid listing_type. Must be "developerland" or "developerplot"'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get listing
            try:
                listing = DeveloperListing.objects.get(
                    listing_type=listing_type,
                    backend_listing_id=listing_id
                )
            except DeveloperListing.DoesNotExist:
                return Response(
                    {
                        'error': f'Listing not found',
                        'listing_type': listing_type,
                        'listing_id': listing_id
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get all TIF metadata for this listing
            tif_metadata_list = TIFMetadata.objects.filter(
                media__listing=listing,
                media__is_tif=True,
                media__tiles_generated=True
            ).select_related('media')
            
            if not tif_metadata_list.exists():
                return Response(
                    {
                        'success': False,
                        'error': 'No TIF files have been processed yet',
                        'listing': {
                            'id': listing.id,
                            'listing_type': listing.listing_type,
                            'backend_listing_id': listing.backend_listing_id,
                            'name': listing.name
                        }
                    },
                    status=status.HTTP_200_OK
                )
            
            # Calculate combined bounds from all TIF files
            west = min([tm.bounds_west for tm in tif_metadata_list if tm.bounds_west is not None])
            south = min([tm.bounds_south for tm in tif_metadata_list if tm.bounds_south is not None])
            east = max([tm.bounds_east for tm in tif_metadata_list if tm.bounds_east is not None])
            north = max([tm.bounds_north for tm in tif_metadata_list if tm.bounds_north is not None])
            
            # Get zoom levels
            min_zoom = min([tm.min_zoom for tm in tif_metadata_list])
            max_zoom = max([tm.max_zoom for tm in tif_metadata_list])
            
            # Calculate recommended zoom based on area
            width = east - west
            height = north - south
            area = width * height
            
            if area < 0.0001:
                recommended_zoom = 17
            elif area < 0.001:
                recommended_zoom = 15
            elif area < 0.01:
                recommended_zoom = 13
            elif area < 0.1:
                recommended_zoom = 11
            else:
                recommended_zoom = 9
            
            # Ensure within bounds
            recommended_zoom = max(min_zoom, min(recommended_zoom, max_zoom))
            
            # Calculate center
            center_lat = (south + north) / 2
            center_lng = (west + east) / 2
            
            # Get S3 tile paths and file info for each TIF
            tif_files = []
            for tif_meta in tif_metadata_list:
                media = tif_meta.media
                
                # CloudFront URL template
                cloudfront_domain = 'https://d17yosovmfjm4.cloudfront.net'
                tile_url_template = f"{cloudfront_domain}/{media.s3_tile_path}/{{z}}/{{x}}/{{y}}.png"
                
                tif_files.append({
                    'file_name': media.file_name,
                    's3_tile_path': media.s3_tile_path,
                    'tile_url_template': tile_url_template,
                    'tiles_generated': media.total_tiles_generated,
                    'bounds': {
                        'west': tif_meta.bounds_west,
                        'south': tif_meta.bounds_south,
                        'east': tif_meta.bounds_east,
                        'north': tif_meta.bounds_north
                    }
                })
            
            # Return lightweight response
            return Response(
                {
                    'success': True,
                    'listing': {
                        'id': listing.id,
                        'listing_type': listing.listing_type,
                        'backend_listing_id': listing.backend_listing_id,
                        'name': listing.name,
                        'location': listing.location,
                        'city': listing.city,
                        'state': listing.state
                    },
                    'bounds': {
                        'west': west,
                        'south': south,
                        'east': east,
                        'north': north,
                        'bbox': [west, south, east, north],
                        'leaflet_bounds': [[south, west], [north, east]]
                    },
                    'center': {
                        'lat': center_lat,
                        'lng': center_lng,
                        'coordinates': [center_lng, center_lat]
                    },
                    'zoom': {
                        'min': min_zoom,
                        'max': max_zoom,
                        'default': recommended_zoom,
                        'recommended': recommended_zoom
                    },
                    'tif_files': tif_files,
                    'summary': {
                        'total_tif_files': len(tif_files),
                        'total_tiles': sum(tf['tiles_generated'] for tf in tif_files)
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error retrieving map data: {e}", exc_info=True)
            return Response(
                {
                    'error': 'Internal server error',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )