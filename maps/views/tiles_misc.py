from ._imports import *

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

