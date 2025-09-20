from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Prefetch
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from .models import *
from .serializers import *
from .tile_path_service import TilePathService
import logging
import boto3
import requests

logger = logging.getLogger(__name__)

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
    """
    permission_classes = [AllowAny]
    
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
            
            # Add metadata to response
            result['metadata'] = {
                'search_timestamp': timezone.now().isoformat(),
                'search_radius_meters': radius_meters,
                'total_features_found': len(result.get('features', [])),
                'total_nearby_features': len(result.get('nearby_features', [])),
                'api_version': '2.0'
            }
            
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
            ).order_by('-area')
            
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
        features = GeoFeature.objects.filter(
            layer__city=city,
            layer__is_processed=True,
            is_valid=True,
            geometry__intersects=search_buffer
        ).select_related('layer', 'layer__category').order_by('-area')
        
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
        features = GeoFeature.objects.filter(
            layer__city=city,
            layer__is_processed=True,
            is_valid=True,
            geometry__intersects=buffered_area
        ).select_related('layer', 'layer__category')
        
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
                'default_color': feature.layer.category.default_color or '#666666',
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
            
            category_code = feature.derived_category
            
            # Get city-specific color from config
            city_config = get_city_config(city_slug)
            if city_config and 'colors' in city_config:
                color = city_config['colors'].get(category_code)
                if color:
                    return color
            
            # Fallback to layer style
            try:
                style = feature.layer.get_style()
                if isinstance(style, dict):
                    return style.get('fill_color', '#666666')
                elif hasattr(style, 'fill_color'):
                    return style.fill_color
            except:
                pass
            
            # Fallback to category color or default
            if feature.layer.category:
                return feature.layer.category.color or '#0066CC'
            
            return '#0066CC'  # Default blue
            
        except Exception as e:
            logger.error(f"Error getting feature color: {e}")
            return '#0066CC'
    
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
            # Use a small buffer around the point to handle LineStrings and other geometries
            search_buffer = search_point.buffer(0.0001)  # ~10m buffer
            
            # Search for features in the specific layer that intersect with the point
            features = GeoFeature.objects.filter(
                layer=layer,
                is_valid=True,
                geometry__intersects=search_buffer
            ).order_by('-area')  # Order by area (largest first)
            
            if not features.exists():
                # If no exact intersection found, search for nearby features within 100m buffer
                buffer_100m = search_point.buffer(0.0009)  # ~100m buffer (0.0009 degrees ≈ 100m)
                
                nearby_features = GeoFeature.objects.filter(
                    layer=layer,
                    is_valid=True,
                    geometry__intersects=buffer_100m
                ).annotate(
                    distance=Distance('geometry', search_point)
                ).order_by('distance')
                
                if nearby_features.exists():
                    # Found nearby features within 100m, return the closest one
                    closest_feature = nearby_features.first()
                    feature_data = self._process_feature_data(closest_feature)
                    
                    # Calculate distance in meters
                    # Use the distance method directly on the geometry
                    distance_degrees = closest_feature.geometry.distance(search_point)
                    distance_meters = distance_degrees * 111000  # Approximate conversion
                    
                    # Check if this is one of the special layers that need custom response
                    if layer.slug == 'bengaluru_master_plan_2015':
                        zone_category = feature_data.get('zone_category', '')
                        zone_subcategory = feature_data.get('zone_subcategory', '')
                        
                        if zone_category and zone_subcategory:
                            data = f"{zone_category} , {zone_subcategory}"
                        elif zone_category:
                            data = zone_category
                        else:
                            data = "Unknown"
                        
                        return {
                            'data': data,
                            'distance_meters': round(distance_meters, 2)
                        }
                    
                    elif layer.slug == 'bengaluru_strr':
                        feature_name = feature_data.get('feature_name', '')
                        zone_subcategory = feature_data.get('zone_subcategory', '')
                        
                        if feature_name and zone_subcategory:
                            data = f"{feature_name} , {zone_subcategory}"
                        elif feature_name:
                            data = feature_name
                        else:
                            data = "Unknown"
                        
                        return {
                            'data': data,
                            'distance_meters': round(distance_meters, 2)
                        }
                    
                    elif layer.slug == 'hyderabad_highways':
                        plot_category = feature_data.get('plot_category', '')
                        symbology = feature_data.get('symbology', '')
                        
                        if plot_category and symbology:
                            data = f"{plot_category} , {symbology}"
                        elif plot_category:
                            data = plot_category
                        elif symbology:
                            data = symbology
                        else:
                            data = "Unknown"
                        
                        return {
                            'data': data,
                            'distance_meters': round(distance_meters, 2)
                        }
                    
                    elif layer.slug == 'hyderabad_rrr':
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {})
                        
                        name = properties.get('Name', '')
                        alignment = properties.get('Alignment', '')
                        
                        if name and alignment:
                            data = f"{name} , {alignment}"
                        elif name:
                            data = name
                        elif alignment:
                            data = alignment
                        else:
                            data = "Unknown"
                        
                        return {
                            'data': data,
                            'distance_meters': round(distance_meters, 2)
                        }
                    
                    elif layer.slug == 'hyderabad_ratan_tata_road':
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {})
                        
                        name = properties.get('Name', '')
                        end_to_end = properties.get('End_to_End', '')
                        
                        if name and end_to_end:
                            data = f"{name} , {end_to_end}"
                        elif name:
                            data = name
                        elif end_to_end:
                            data = end_to_end
                        else:
                            data = "Unknown"
                        
                        return {
                            'data': data,
                            'distance_meters': round(distance_meters, 2)
                        }
                    
                    elif layer.slug == 'hyderabad_future_city':
                        detailed_category = feature_data.get('detailed_category', {})
                        properties = detailed_category.get('properties', {})
                        
                        name = properties.get('Name', '')
                        
                        if name:
                            data = name
                        else:
                            data = "Unknown"
                        
                        return {
                            'data': data,
                            'distance_meters': round(distance_meters, 2)
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
            
            # Special handling for bengaluru_master_plan_2015 layer
            if layer.slug == 'bengaluru_master_plan_2015' and containing_features:
                primary_feature = containing_features[0]
                zone_category = primary_feature.get('zone_category', '')
                zone_subcategory = primary_feature.get('zone_subcategory', '')
                
                # Combine zone_category and zone_subcategory
                if zone_category and zone_subcategory:
                    data = f"{zone_category} , {zone_subcategory}"
                elif zone_category:
                    data = zone_category
                else:
                    data = "Unknown"
                
                return {
                    'data': data
                }
            
            # Special handling for bengaluru_strr layer
            if layer.slug == 'bengaluru_strr' and containing_features:
                primary_feature = containing_features[0]
                feature_name = primary_feature.get('feature_name', '')
                zone_subcategory = primary_feature.get('zone_subcategory', '')
                
                # Combine feature_name and zone_subcategory
                if feature_name and zone_subcategory:
                    data = f"{feature_name} , {zone_subcategory}"
                elif feature_name:
                    data = feature_name
                else:
                    data = "Unknown"
                
                return {
                    'data': data
                }
            
            # Special handling for bengaluru_metro layer
            if layer.slug == 'bengaluru_metro' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {})
                
                linecolour = properties.get('linecolour', '')
                name = properties.get('Name ', '')  # Note the space after 'Name'
                remarks = properties.get('remarks', '')
                
                # Combine linecolour, name, and remarks
                data_parts = []
                if linecolour:
                    data_parts.append(linecolour)
                if name:
                    data_parts.append(name)
                if remarks:
                    data_parts.append(remarks)
                
                if data_parts:
                    data = " , ".join(data_parts)
                else:
                    data = "Unknown"
                
                return {
                    'data': data
                }
            
            # Special handling for hyderabad_highways layer
            if layer.slug == 'hyderabad_highways' and containing_features:
                primary_feature = containing_features[0]
                plot_category = primary_feature.get('plot_category', '')
                symbology = primary_feature.get('symbology', '')
                
                # Combine plot_category and symbology
                if plot_category and symbology:
                    data = f"{plot_category} , {symbology}"
                elif plot_category:
                    data = plot_category
                elif symbology:
                    data = symbology
                else:
                    data = "Unknown"
                
                return {
                    'data': data
                }
            
            # Special handling for hyderabad_rrr layer
            if layer.slug == 'hyderabad_rrr' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {})
                
                name = properties.get('Name', '')
                alignment = properties.get('Alignment', '')
                
                # Combine Name and Alignment
                if name and alignment:
                    data = f"{name} , {alignment}"
                elif name:
                    data = name
                elif alignment:
                    data = alignment
                else:
                    data = "Unknown"
                
                return {
                    'data': data
                }
            
            # Special handling for hyderabad_ratan_tata_road layer
            if layer.slug == 'hyderabad_ratan_tata_road' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {})
                
                name = properties.get('Name', '')
                end_to_end = properties.get('End_to_End', '')
                
                # Combine Name and End_to_End
                if name and end_to_end:
                    data = f"{name} , {end_to_end}"
                elif name:
                    data = name
                elif end_to_end:
                    data = end_to_end
                else:
                    data = "Unknown"
                
                return {
                    'data': data
                }
            
            # Special handling for hyderabad_future_city layer
            if layer.slug == 'hyderabad_future_city' and containing_features:
                primary_feature = containing_features[0]
                detailed_category = primary_feature.get('detailed_category', {})
                properties = detailed_category.get('properties', {})
                
                name = properties.get('Name', '')
                
                # Return just the Name
                if name:
                    data = name
                else:
                    data = "Unknown"
                
                return {
                    'data': data
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
                logger.warning(f"❌ Layer not found: {state_slug}/{city_slug}/{layer_slug}")
                return self._return_error_tile(f"Layer not found: {state_slug}/{city_slug}/{layer_slug}")
            
            logger.info(f"🔍 Serving tile: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
            
            # Try multiple sources in order of preference
            tile_data = self._get_tile_with_fallback(state_slug, city_slug, layer_slug, z, x, y, format_type, layer)
            
            if tile_data:
                # Return the tile data with no-cache headers
                headers = self.tile_path_service.get_tile_cache_headers(format_type)
                response = HttpResponse(tile_data, content_type=headers['ContentType'])
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'
                logger.info(f"✅ Successfully served tile: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
                return response
            else:
                logger.warning(f"❌ Tile not found: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
                return self._return_error_tile(f"Tile not found: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
            
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
            logger.info(f"✅ Served from CloudFront: {cloudfront_url}")
            return tile_data
        
        # 2. Try S3 Direct (fallback)
        s3_url = self.tile_path_service.generate_s3_url(
            state_slug, city_slug, layer_slug, z, x, y, format_type
        )
        
        logger.debug(f"🔍 Trying S3 Direct: {s3_url}")
        tile_data = self._fetch_url(s3_url)
        if tile_data:
            logger.info(f"✅ Served from S3: {s3_url}")
            return tile_data
        
        # 3. Generate on-demand (optional - can be disabled for performance)
        if getattr(settings, 'ENABLE_ON_DEMAND_TILE_GENERATION', False):
            logger.debug(f"🔍 Trying on-demand generation for {z}/{x}/{y}.{format_type}")
            tile_data = self._generate_tile_on_demand(layer, z, x, y, format_type)
            if tile_data:
                logger.info(f"✅ Generated on-demand: {z}/{x}/{y}.{format_type}")
                return tile_data
        
        logger.warning(f"❌ Tile not found from any source: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
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
                logger.warning(f"❌ Layer not found: {state_slug}/{city_slug}/{layer_slug}")
                return self._return_error_tile(f"Layer not found: {state_slug}/{city_slug}/{layer_slug}")
            
            logger.info(f"🔍 Serving S3 direct tile: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
            
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
                logger.info(f"✅ Successfully served S3 direct tile: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
                return response
            else:
                logger.warning(f"❌ Tile not found in S3: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
                return self._return_error_tile(f"Tile not found: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}")
            
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
                logger.info(f"✅ Successfully fetched from S3: s3://{self.bucket_name}/{s3_key}")
                return tile_data
            else:
                logger.warning(f"❌ Empty tile data from S3: s3://{self.bucket_name}/{s3_key}")
                return None
                
        except self.s3_client.exceptions.NoSuchKey:
            logger.debug(f"❌ Tile not found in S3: s3://{self.bucket_name}/{s3_key}")
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching from S3: s3://{self.bucket_name}/{s3_key} - {str(e)}")
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
    """
    permission_classes = [AllowAny]
    
    def get(self, request, state_slug, city_slug, layer_slug):
        try:
            # Get the state
            state = State.objects.get(slug=state_slug, is_active=True)
            
            # Get the city within the state
            city = City.objects.get(slug=city_slug, state_ref=state, is_active=True)
            
            # Get the specific layer
            layer = DataLayer.objects.get(
                slug=layer_slug,
                city=city,
                is_processed=True
            )
            
            # Check if layer has stored bounds
            if all([layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax]):
                bounds = {
                    'west': layer.bbox_xmin,
                    'south': layer.bbox_ymin,
                    'east': layer.bbox_xmax,
                    'north': layer.bbox_ymax
                }
                data_source = 'stored_bounds'
            else:
                # Calculate bounds from actual features
                from django.contrib.gis.db.models import Extent
                
                extent = GeoFeature.objects.filter(
                    layer=layer,
                    is_valid=True
                ).aggregate(extent=Extent('geometry'))['extent']
                
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
            
            # Get feature count
            feature_count = GeoFeature.objects.filter(
                layer=layer,
                is_valid=True
            ).count()
            
            return Response({
                'state': state_slug,
                'state_name': state.name,
                'city': city_slug,
                'city_name': city.name,
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
            })
            
        except State.DoesNotExist:
            return Response({
                'error': f'State not found: {state_slug}',
                'state': state_slug,
                'city': city_slug,
                'layer': layer_slug
            }, status=status.HTTP_404_NOT_FOUND)
        except City.DoesNotExist:
            return Response({
                'error': f'City not found: {city_slug} in state: {state_slug}',
                'state': state_slug,
                'city': city_slug,
                'layer': layer_slug
            }, status=status.HTTP_404_NOT_FOUND)
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
        
        # extent is (xmin, ymin, xmax, ymax) in the geometry's SRID
        # For 4326 (WGS84), this is (lng_min, lat_min, lng_max, lat_max)
        return {
            'west': extent[0],   # xmin (longitude)
            'south': extent[1],  # ymin (latitude)
            'east': extent[2],   # xmax (longitude)
            'north': extent[3]   # ymax (latitude)
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