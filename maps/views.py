from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Prefetch
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib.gis.geos import Point
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
        summary="Search coordinates across all states and cities",
        description="Find which state, city, layer, and feature a given coordinate belongs to, including detailed category information",
        tags=['coordinates'],
        parameters=[
            OpenApiParameter(name='lat', location=OpenApiParameter.QUERY, required=True, type=float, description='Latitude coordinate'),
            OpenApiParameter(name='lng', location=OpenApiParameter.QUERY, required=True, type=float, description='Longitude coordinate'),
            OpenApiParameter(name='city_slug', location=OpenApiParameter.PATH, required=False, type=str, description='Optional: Limit search to specific city'),
        ],
        responses={
            200: {
                'description': 'Coordinate search results',
                'examples': [
                    {
                        'application/json': {
                            'search_point': {
                                'latitude': 12.9716,
                                'longitude': 77.5946
                            },
                            'found': True,
                            'state': {
                                'slug': 'karnataka',
                                'name': 'Karnataka'
                            },
                            'city': {
                                'slug': 'bengaluru',
                                'name': 'Bangalore'
                            },
                            'features': [
                                {
                                    'feature_id': 12345,
                                    'feature_name': 'Commercial Zone A',
                                    'layer_slug': 'bengaluru_master_plan',
                                    'layer_name': 'Master Plan',
                                    'category': 'COMMERCIAL',
                                    'category_name': 'Commercial',
                                    'land_use': 'Commercial',
                                    'plu_code': 'C1',
                                    'area': 12500.5,
                                    'color': '#FF0000'
                                }
                            ],
                            'summary': 'Location is within Bangalore Master Plan: Commercial Zone A'
                        }
                    }
                ]
            },
            400: {
                'description': 'Invalid coordinates or parameters'
            },
            404: {
                'description': 'No features found at the given coordinates'
            }
        }
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
    """
    permission_classes = [AllowAny]
    
    def get(self, request, city_slug=None):
        try:
            # Get coordinates from query parameters
            lat = request.GET.get('lat')
            lng = request.GET.get('lng')
            
            if not lat or not lng:
                return Response({
                    'error': 'Missing coordinates',
                    'message': 'Please provide lat and lng parameters',
                    'example': f'/api/cities/{city_slug or "any"}/search-coords-test/?lat=12.9716&lng=77.5946'
                }, status=400)
            
            try:
                latitude = float(lat)
                longitude = float(lng)
            except ValueError:
                return Response({
                    'error': 'Invalid coordinate format',
                    'message': 'Coordinates must be valid numbers'
                }, status=400)
            
            # Validate coordinate ranges
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                return Response({
                    'error': 'Invalid coordinates',
                    'message': 'Latitude must be between -90 and 90, longitude between -180 and 180'
                }, status=400)
            
            # Create point geometry
            search_point = Point(longitude, latitude, srid=4326)
            
            # Search for features
            if city_slug:
                # Search within specific city
                result = self._search_in_city(city_slug, search_point, latitude, longitude)
            else:
                # Search across all states and cities
                result = self._search_across_all_cities(search_point, latitude, longitude)
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error in CoordinateSearchTestView: {e}")
            return Response({
                'error': 'Failed to search coordinates',
                'message': str(e)
            }, status=500)
    
    def _search_in_city(self, city_slug, search_point, latitude, longitude):
        """Search for features within a specific city"""
        try:
            city = get_object_or_404(City, slug=city_slug, is_active=True)
            
            # Find containing features
            containing_features = self._find_containing_features(city, search_point)
            
            # Find nearby features if no exact match
            nearby_features = []
            if not containing_features:
                nearby_features = self._find_nearby_features(city, search_point, radius_meters=100)
            
            # Build response
            response_data = {
                'search_point': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'coordinates': [longitude, latitude]
                },
                'found': len(containing_features) > 0,
                'state': {
                    'slug': city.state_ref.slug,
                    'name': city.state_ref.name
                },
                'city': {
                    'slug': city_slug,
                    'name': city.name
                },
                'features': containing_features,
                'nearby_features': nearby_features[:5] if nearby_features else [],
                'summary': self._create_search_summary(containing_features, nearby_features),
                'search_scope': 'city_specific'
            }
            
            if not containing_features and not nearby_features:
                return Response(response_data, status=404)
            
            return response_data
            
        except City.DoesNotExist:
            return Response({
                'error': f'City not found: {city_slug}',
                'city': city_slug
            }, status=404)
    
    def _search_across_all_cities(self, search_point, latitude, longitude):
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
                # Try nearby search across all cities
                nearby_features = self._find_nearby_across_all_cities(search_point)
                
                return {
                    'search_point': {
                        'latitude': latitude,
                        'longitude': longitude,
                        'coordinates': [longitude, latitude]
                    },
                    'found': False,
                    'features': [],
                    'nearby_features': nearby_features[:10],
                    'summary': 'No features found at this location',
                    'search_scope': 'global'
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
            
            return {
                'search_point': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'coordinates': [longitude, latitude]
                },
                'found': True,
                'state': {
                    'slug': state.slug,
                    'name': state.name
                },
                'city': {
                    'slug': city.slug,
                    'name': city.name
                },
                'features': containing_features,
                'nearby_features': [],
                'summary': self._create_search_summary(containing_features, []),
                'search_scope': 'global'
            }
            
        except Exception as e:
            logger.error(f"Error in global search: {e}")
            return Response({
                'error': 'Failed to search across all cities',
                'message': str(e)
            }, status=500)
    
    def _find_containing_features(self, city, point):
        """Find all features that contain the search point"""
        containing_features = []
        
        # Query features that contain the point
        features = GeoFeature.objects.filter(
            layer__city=city,
            layer__is_processed=True,
            is_valid=True,
            geometry__contains=point
        ).select_related('layer', 'layer__category').order_by('-area')
        
        for feature in features:
            feature_data = self._process_feature_data(feature)
            containing_features.append(feature_data)
        
        return containing_features
    
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
                    'name': feature.layer.city.state_ref.name
                }
                feature_data['city'] = {
                    'slug': feature.layer.city.slug,
                    'name': feature.layer.city.name
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
            
            feature_data = {
                'feature_id': feature.id,
                'feature_name': feature.name or 'Unnamed',
                'layer_slug': feature.layer.slug,
                'layer_name': feature.layer.name,
                'category': feature.layer.category.code if feature.layer.category else 'UNKNOWN',
                'category_name': feature.layer.category.name if feature.layer.category else 'Unknown',
                'color': layer_color,
                'area': float(feature.area) if feature.area else 0.0,
                'zone_category': feature.zone_category or '',
                'zone_subcategory': feature.zone_subcategory or '',
                'plu_code': feature.plu_primary_code or '',
                'plu_name': feature.plu_secondary_1 or '',
                'plot_category': feature.plot_category or '',
                'symbology': feature.symbology or '',
                'detailed_category': category_info
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
                'area': 0.0,
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
                'description': feature.layer.category.description or ''
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
class CompleteHierarchyAPIView(APIView):
    """
    Complete Hierarchy API
    
    Returns the complete hierarchy of states, cities, and layers in a single API call.
    This replaces multiple separate API calls with one comprehensive endpoint.
    
    GET /api/hierarchy/
    """
    
    def get(self, request):
        """Get complete hierarchy with statistics"""
        try:
            # Get all active states with their cities and layers
            states = State.objects.filter(is_active=True).prefetch_related(
                Prefetch(
                    'cities',
                    queryset=City.objects.filter(is_active=True).prefetch_related(
                        Prefetch(
                            'layers',
                            queryset=DataLayer.objects.filter(is_processed=True).select_related('category')
                        )
                    )
                )
            )
            
            hierarchy_data = []
            total_states = 0
            
            for state in states:
                state_cities = []
                total_city_features = 0
                
                for city in state.cities.all():
                    city_layers = []
                    layers_with_tiles = 0
                    
                    for layer in city.layers.all():
                        layer_feature_count = GeoFeature.objects.filter(layer=layer, is_valid=True).count()
                        
                        if layer.tiles_generated:
                            layers_with_tiles += 1
                        
                        total_city_features += layer_feature_count
                        
                        # Get CloudFront URLs if tiles are generated
                        tile_urls = None
                        if layer.tiles_generated:
                            tile_urls = self._get_layer_tile_urls(state.slug, city.slug, layer.slug, True)
                        
                        city_layers.append({
                            'name': layer.name,
                            'slug': layer.slug,
                            'status': 'live' if layer.tiles_generated else 'pending',
                            'is_live': layer.tiles_generated,
                            'tiles_generated': layer.tiles_generated,
                            'feature_count': layer_feature_count,
                            'category': layer.category.name if layer.category else 'Unknown',
                            'bounds': {
                                'xmin': layer.bbox_xmin,
                                'ymin': layer.bbox_ymin,
                                'xmax': layer.bbox_xmax,
                                'ymax': layer.bbox_ymax
                            } if layer.has_valid_bbox() else None,
                            'tile_urls': tile_urls
                        })
                    
                    # City status summary
                    city_status = 'live' if layers_with_tiles > 0 else 'pending'
                    is_live = layers_with_tiles > 0
                    
                    city_data = {
                        'name': city.name,
                        'slug': city.slug,
                        'center_lat': city.center_lat,
                        'center_lng': city.center_lng,
                        'is_active': city.is_active,
                        'is_live': is_live,
                        'statistics': {
                            'total_layers': len(city.layers.all()),
                            'processed_layers': len([l for l in city.layers.all() if l.is_processed]),
                            'layers_with_tiles': layers_with_tiles,
                            'total_features': total_city_features
                        },
                        'status': city_status,
                        'layers': city_layers
                    }
                    
                    state_cities.append(city_data)
                
                # State statistics
                state_total_features = sum(city['statistics']['total_features'] for city in state_cities)
                state_total_layers = sum(city['statistics']['total_layers'] for city in state_cities)
                
                state_data = {
                    'state': {
                        'name': state.name,
                        'slug': state.slug,
                        'code': state.code,
                        'center_lat': state.center_lat,
                        'center_lng': state.center_lng,
                        'is_active': state.is_active
                    },
                    'statistics': {
                        'total_cities': len(state_cities),
                        'total_layers': state_total_layers,
                        'total_features': state_total_features
                    },
                    'cities': state_cities
                }
                
                hierarchy_data.append(state_data)
                total_states += 1
            
            return Response({
                'status': 'success',
                'total_states': total_states,
                'hierarchy': hierarchy_data
            })
            
        except Exception as e:
            logger.error(f"Error in CompleteHierarchyAPIView: {e}")
            return Response({
                'error': 'Failed to load hierarchy',
                'message': str(e)
            }, status=500)
    
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
                return self._return_error_tile("Invalid tile coordinates")
            
            # Determine format from URL
            format_type = 'png' if request.path.endswith('.png') else 'mvt'
            
            # Get layer information
            layer = self._get_layer_by_hierarchy(state_slug, city_slug, layer_slug)
            if not layer:
                return self._return_error_tile(f"Layer not found: {state_slug}/{city_slug}/{layer_slug}")
            
            # Try multiple sources in order of preference
            tile_data = self._get_tile_with_fallback(state_slug, city_slug, layer_slug, z, x, y, format_type, layer)
            
            if tile_data:
                # Return the tile data with appropriate headers
                headers = self.tile_path_service.get_tile_cache_headers(format_type)
                response = HttpResponse(tile_data, content_type=headers['ContentType'])
                response['Cache-Control'] = headers['CacheControl']
                return response
            else:
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
        
        tile_data = self._fetch_url(cloudfront_url)
        if tile_data:
            logger.info(f"✅ Served from CloudFront: {cloudfront_url}")
            return tile_data
        
        # 2. Try S3 Direct (fallback)
        s3_url = self.tile_path_service.generate_s3_url(
            state_slug, city_slug, layer_slug, z, x, y, format_type
        )
        
        tile_data = self._fetch_url(s3_url)
        if tile_data:
            logger.info(f"✅ Served from S3: {s3_url}")
            return tile_data
        
        # 3. Generate on-demand (optional - can be disabled for performance)
        if getattr(settings, 'ENABLE_ON_DEMAND_TILE_GENERATION', False):
            tile_data = self._generate_tile_on_demand(layer, z, x, y, format_type)
            if tile_data:
                logger.info(f"✅ Generated on-demand: {z}/{x}/{y}.{format_type}")
                return tile_data
        
        return None
    
    def _fetch_url(self, url, timeout=5):
        """Fetch data from URL with timeout"""
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                return response.content
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
            return Response({
                'error': error_message,
                'status': 'error'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
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
            
            # Check if layer has cached bounds
            if all([layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax]):
                bounds = {
                    'west': layer.bbox_xmin,
                    'south': layer.bbox_ymin,
                    'east': layer.bbox_xmax,
                    'north': layer.bbox_ymax
                }
                data_source = 'cached_bounds'
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