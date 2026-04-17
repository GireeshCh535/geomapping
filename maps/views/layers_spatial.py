from ._imports import *

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
                'layer__city',
                'layer__city__state_ref'
            ).values(
                'layer_id',
                'layer__slug',
                'layer__name',
                'layer__description',
                'layer__city__slug',
                'layer__city__name',
                'layer__city__state_ref__slug',
                'layer__city__state_ref__name',
                'layer__bbox_xmin',
                'layer__bbox_ymin',
                'layer__bbox_xmax',
                'layer__bbox_ymax'
            ).distinct()
            
            
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
            
            # Create point geometry for search (exact point only, no buffer)
            search_point = Point(longitude, latitude, srid=4326)
            
            features = GeoFeature.objects.filter(
                layer=layer,
                is_valid=True,
                geometry__intersects=search_point
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
            )
            
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


