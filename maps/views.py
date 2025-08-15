from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Prefetch
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import HttpResponseRedirect
from django.contrib.gis.geos import Point
from .models import *
from .serializers import *
import logging
import boto3

logger = logging.getLogger(__name__)

# ================================
# VIEWSETS (Router endpoints)
# ================================

class StateViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for states"""
    queryset = State.objects.filter(is_active=True)
    serializer_class = StateSerializer
    lookup_field = 'slug'

class LayerGroupViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for layer groups"""
    queryset = LayerGroup.objects.all()
    serializer_class = LayerGroupSerializer
    lookup_field = 'slug'

class CityViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for cities"""
    queryset = City.objects.filter(is_active=True).select_related('state_ref')
    serializer_class = CitySerializer
    lookup_field = 'slug'

class LayerCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for layer categories"""
    queryset = LayerCategory.objects.all()
    serializer_class = LayerCategorySerializer
    lookup_field = 'code'

class DataLayerViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for data layers"""
    queryset = DataLayer.objects.filter(is_processed=True).select_related('city', 'category')
    serializer_class = DataLayerSerializer

class GeoFeatureViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for geo features"""
    queryset = GeoFeature.objects.filter(is_valid=True).select_related('layer', 'layer__city')
    serializer_class = GeoFeatureSerializer

# ================================
# API VIEWS
# ================================

class CoordinateSearchTestView(APIView):
    """Test version using GET parameters for coordinate search"""
    
    def get(self, request, city_slug):
        try:
            # Get coordinates from query parameters
            lat = request.GET.get('lat')
            lng = request.GET.get('lng')
            
            if not lat or not lng:
                return Response({
                    'error': 'Missing coordinates',
                    'message': 'Please provide lat and lng parameters',
                    'example': f'/api/cities/{city_slug}/search-coords-test/?lat=12.9716&lng=77.5946'
                }, status=400)
            
            try:
                latitude = float(lat)
                longitude = float(lng)
            except ValueError:
                return Response({
                    'error': 'Invalid coordinate format',
                    'message': 'Coordinates must be valid numbers'
                }, status=400)
            
            # Get city
            city = get_object_or_404(City, slug=city_slug, is_active=True)
            
            # Validate coordinate ranges
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                return Response({
                    'error': 'Invalid coordinates',
                    'message': 'Latitude must be between -90 and 90, longitude between -180 and 180'
                }, status=400)
            
            # Create point geometry
            search_point = Point(longitude, latitude, srid=4326)
            
            # Find all features containing this point
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
                    'coordinates': [longitude, latitude]  # GeoJSON format
                },
                'city': city_slug,
                'found': len(containing_features) > 0,
                'containing_features': containing_features,
                'nearby_features': nearby_features[:5],  # Limit to 5 nearby
                'summary': self._create_search_summary(containing_features, nearby_features),
                'method': 'GET'  # To distinguish from POST version
            }
            
            return Response(response_data)
            
        except Exception as e:
            print(f"Error in CoordinateSearchTestView: {e}")
            return Response({
                'error': 'Failed to load city data',
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
            try:
                # Get layer color using existing config system
                layer_color = self._get_feature_color_from_config(feature, city.slug)
                
                feature_data = {
                    'feature_id': feature.id,
                    'feature_name': feature.name or 'Unnamed',
                    'layer_slug': feature.layer.slug,
                    'layer_name': feature.layer.name,
                    'category': feature.layer.category.name if feature.layer.category else 'Unknown',
                    'color': layer_color,
                    'area': float(feature.area) if feature.area else 0.0,
                    'land_use': feature.land_use_type or '',
                    'plu_code': feature.plu_primary_code or ''
                }
                
                containing_features.append(feature_data)
                
            except Exception as e:
                print(f"Error processing feature {feature.id}: {e}")
                continue
        
        return containing_features
    
    def _find_nearby_features(self, city, point, radius_meters=100):
        """Find features near the search point"""
        
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
                
                layer_color = self._get_feature_color_from_config(feature, city.slug)
                
                nearby_data = {
                    'feature_id': feature.id,
                    'feature_name': feature.name or 'Unnamed',
                    'layer_slug': feature.layer.slug,
                    'layer_name': feature.layer.name,
                    'category': feature.layer.category.name if feature.layer.category else 'Unknown',
                    'color': layer_color,
                    'distance_meters': round(distance, 1),
                    'area': float(feature.area) if feature.area else 0.0
                }
                
                nearby_features.append(nearby_data)
                
            except Exception as e:
                print(f"Error processing nearby feature {feature.id}: {e}")
                continue
        
        # Sort by distance
        nearby_features.sort(key=lambda x: x['distance_meters'])
        
        return nearby_features
    
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
            print(f"Error getting feature color: {e}")
            return '#0066CC'
    
    def _create_search_summary(self, containing_features, nearby_features):
        """Create a human-readable summary of the search results"""
        
        if containing_features:
            if len(containing_features) == 1:
                feature = containing_features[0]
                return f"Location is within {feature['layer_name']}: {feature['feature_name']}"
            else:
                primary = containing_features[0]  # Largest by area
                return f"Location is within {primary['layer_name']}: {primary['feature_name']}. Also overlaps with {len(containing_features) - 1} other features."
            
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

class CloudFrontTileView(APIView):
    """
    CloudFront Tile Serving API
    
    Serves tiles from CloudFront CDN with hierarchical URL structure:
    GET /api/tiles/<state_slug>/<city_slug>/<layer_slug>/<z>/<x>/<y>.png
    GET /api/tiles/<state_slug>/<city_slug>/<layer_slug>/<z>/<x>/<y>.mvt
    
    Examples:
    - /api/tiles/karnataka/bengaluru/master_plan/12/2048/2048.png
    - /api/tiles/andhra-pradesh/visakhapatnam/master_plan/12/2048/2048.png
    - /api/tiles/telangana/hyderabad/rrr/12/2048/2048.mvt
    
    This API redirects to CloudFront URLs for optimal performance.
    """
    
    def get(self, request, state_slug, city_slug, layer_slug, z, x, y):
        """Serve tiles via CloudFront with fallback to local generation"""
        try:
            z, x, y = int(z), int(x), int(y)
            
            # Validate tile coordinates
            if not self._validate_tile_coordinates(z, x, y):
                return self._return_error_tile("Invalid tile coordinates")
            
            # Determine format from URL
            format_type = 'png' if request.path.endswith('.png') else 'mvt'
            
            # Get layer information
            layer = self._get_layer_by_hierarchy(state_slug, city_slug, layer_slug)
            if not layer:
                return self._return_error_tile(f"Layer not found: {state_slug}/{city_slug}/{layer_slug}")
            
            # Check if layer has tiles generated or is processed
            # Note: tiles_generated flag might not be updated when tiles are uploaded to S3
            if not layer.tiles_generated and not layer.is_processed:
                return self._return_error_tile(f"Layer not ready: {layer_slug}")
            
            # Get CloudFront URL
            cloudfront_url = self._get_cloudfront_tile_url(state_slug, city_slug, layer_slug, z, x, y, format_type)
            
            # Redirect to CloudFront for optimal performance
            return HttpResponseRedirect(cloudfront_url)
            
        except Exception as e:
            return self._return_error_tile(f"Error serving tile: {str(e)}")
    
    def _validate_tile_coordinates(self, z, x, y):
        """Validate tile coordinates"""
        try:
            # Basic validation
            if z < 0 or z > 22:  # Reasonable zoom range
                return False
            if x < 0 or y < 0:
                return False
            if x >= 2 ** z or y >= 2 ** z:  # Tile bounds for zoom level
                return False
            return True
        except Exception as e:
            return False
    
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
            
    def _get_cloudfront_tile_url(self, state_slug, city_slug, layer_slug, z, x, y, format_type):
        """Generate CloudFront URL for tile"""
        # Get CloudFront domain from settings
        cloudfront_domain = getattr(settings, 'CLOUDFRONT_DOMAIN', 'd17yosovmfjm4.cloudfront.net')
        
        # Use CloudFront URL without /tiles/ prefix to match S3 structure
        cloudfront_url = f"https://{cloudfront_domain}/{state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}"
        
        return cloudfront_url
    
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


class CombinedLayerCenterView(APIView):
    """
    API endpoint to get the center coordinates of combined layers
    URL: /api/cities/{city_slug}/combined-layer-center/
    """
    permission_classes = [AllowAny]
    
    def get(self, request, state_slug, city_slug):
        """
        Get center coordinates of all combined layers for a city
        
        Returns:
        {
            "city": "bangalore",
            "city_name": "Bangalore",
            "center": {
                "lat": 12.9716,
                "lng": 77.5946
            },
            "bounds": {
                "west": 77.4846,
                "south": 12.8716,
                "east": 77.7046,
                "north": 13.0716
            },
            "dimensions": {
                "width": 0.22,
                "height": 0.20
            },
            "layers_count": 15,
            "layers": ["parks", "roads", "buildings", ...]
        }
        """
        result = self.get_combined_layer_center(state_slug, city_slug)
        
        if 'error' in result:
            return Response(result, status=400)
        
        return Response(result, status=200)
    
    def get_combined_layer_center(self, state_slug, city_slug):
        """
        Calculate the center coordinates of the combined bounds of all layers for a city.
        
        Args:
            state_slug: The slug identifier for the state
            city_slug: The slug identifier for the city
            
        Returns:
            dict: Center coordinates and bounds information
        """
        from maps.models import City, DataLayer, State
        
        try:
            # Get the state
            state = State.objects.get(slug=state_slug, is_active=True)
            
            # Get the city within the state
            city = City.objects.get(slug=city_slug, state_ref=state, is_active=True)
            
            # Get all processed layers for this city
            layers = DataLayer.objects.filter(
                city=city,
                is_processed=True
            )
            
            if not layers.exists():
                return {
                    'error': f'No processed layers found for {city_slug}',
                    'state': state_slug,
                    'city': city_slug
                }
            
            # Check if any layers have bounds data
            layers_with_bounds = layers.exclude(
                bbox_xmin__isnull=True,
                bbox_ymin__isnull=True,
                bbox_xmax__isnull=True,
                bbox_ymax__isnull=True
            )
            
            # If no layers have bounds, calculate bounds from city center
            if not layers_with_bounds.exists():
                # Use city center coordinates to create a reasonable bounding box
                city_center_lng = city.center_lng or 77.5946  # Default to Bangalore if not set
                city_center_lat = city.center_lat or 12.9716
                
                # Create a bounding box around the city center (±0.2 degrees)
                buffer_degrees = 0.2
                combined_bounds = {
                    'west': city_center_lng - buffer_degrees,
                    'south': city_center_lat - buffer_degrees,
                    'east': city_center_lng + buffer_degrees,
                    'north': city_center_lat + buffer_degrees
                }
            else:
                # Use actual bounds from layers
                combined_bounds = {
                    'west': float('inf'),
                    'south': float('inf'),
                    'east': float('-inf'),
                    'north': float('-inf')
                }
                
                # Iterate through all layers to find the overall bounds
                for layer in layers_with_bounds:
                    combined_bounds['west'] = min(combined_bounds['west'], layer.bbox_xmin)
                    combined_bounds['south'] = min(combined_bounds['south'], layer.bbox_ymin)
                    combined_bounds['east'] = max(combined_bounds['east'], layer.bbox_xmax)
                    combined_bounds['north'] = max(combined_bounds['north'], layer.bbox_ymax)
            

            
            # Calculate center coordinates
            center_lng = (combined_bounds['west'] + combined_bounds['east']) / 2
            center_lat = (combined_bounds['south'] + combined_bounds['north']) / 2
            
            # Calculate dimensions
            width = combined_bounds['east'] - combined_bounds['west']
            height = combined_bounds['north'] - combined_bounds['south']
            
            return {
                'state': state_slug,
                'state_name': state.name,
                'city': city_slug,
                'city_name': city.name,
                'center': {
                    'lat': center_lat,
                    'lng': center_lng
                },
                'bounds': combined_bounds,
                'dimensions': {
                    'width': width,
                    'height': height
                },
                'layers_count': layers.count(),
                'layers': list(layers.values_list('name', flat=True))
            }
            
        except State.DoesNotExist:
            return {
                'error': f'State not found: {state_slug}',
                'state': state_slug,
                'city': city_slug
            }
        except City.DoesNotExist:
            return {
                'error': f'City not found: {city_slug} in state: {state_slug}',
                'state': state_slug,
                'city': city_slug
            }
        except Exception as e:
            return {
                'error': f'Error calculating combined layer center: {str(e)}',
                'state': state_slug,
                'city': city_slug
            }