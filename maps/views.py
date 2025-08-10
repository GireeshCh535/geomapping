from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Avg, Max, Min, Sum
from rest_framework import viewsets, status
import requests
from rest_framework.decorators import action
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.gis.geos import Polygon
from django.contrib.gis.db.models import Extent
from .services import VectorTileService
from .tile_rendering_service import TileRenderingService
import mercantile
import json
from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import JsonResponse
import mapbox_vector_tile
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance
from .config import get_city_config
import logging
from .caching import gis_cache, cache_gis_response
import time
from django.utils import timezone
from django.http import FileResponse, HttpResponse
import os
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny
from django.db.models import Prefetch
from django.urls import path
from PIL import Image, ImageDraw
import io
from pathlib import Path
from maps.s3_direct_tile_service import *
from .models import *
from .serializers import *
from .services import DataImportService, VectorTileService
from .config import get_city_config, get_plu_mapping
logger = logging.getLogger(__name__)

class StateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing states and their statistics.
    - Lists all active states.
    - Provides statistics for each state (number of cities, layers, features).
    """
    queryset = State.objects.annotate(
        city_count=Count('cities')
    ).filter(is_active=True)
    serializer_class = StateSerializer
    lookup_field = 'slug'
    
    @action(detail=True)
    def statistics(self, request, slug=None):
        """
        Returns statistics for a given state, including:
        - Total cities
        - Active cities
        - Total layers
        - Total features
        """
        state = self.get_object()
        cities = City.objects.filter(state_ref=state)
        
        return Response({
            'total_cities': cities.count(),
            'active_cities': cities.filter(is_active=True).count(),
            'total_layers': DataLayer.objects.filter(city__state_ref=state).count(),
            'total_features': GeoFeature.objects.filter(
                layer__city__state_ref=state
            ).count(),
        })

class LayerGroupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing layer groups.
    - Lists all layer groups.
    - Provides the layers within a group.
    """
    queryset = LayerGroup.objects.annotate(
        layer_count=Count('layers')
    )
    serializer_class = LayerGroupSerializer
    filterset_fields = ['city__slug', 'category__code']
    
    @action(detail=True)
    def layers(self, request, pk=None):
        """
        Returns all layers in a given group.
        """
        group = self.get_object()
        layers = DataLayer.objects.filter(layer_group=group)
        return Response(DataLayerSerializer(layers, many=True).data)

class CityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing cities.
    - Lists all active cities.
    - Provides layer groups and statistics for each city.
    """
    queryset = City.objects.annotate(
        layer_count=Count('layers'),
        total_features=Count('layers__geofeature_set')
    ).filter(is_active=True)
    serializer_class = CitySerializer
    lookup_field = 'slug'
    
    @action(detail=True)
    def layer_groups(self, request, slug=None):
        """
        Returns all layer groups for a city.
        """
        city = self.get_object()
        groups = LayerGroup.objects.filter(city=city).annotate(
            layer_count=Count('layers')
        )
        return Response(LayerGroupSerializer(groups, many=True).data)

    @action(detail=True, methods=['get'])
    def statistics(self, request, slug=None):  # Keep as 'slug'
        """
        Returns detailed statistics for a city, including:
        - Number of layers
        - Number of processed layers
        - Number of layers with tiles
        - Feature statistics (total, valid, with PLU)
        - PLU statistics (for Bangalore)
        - Area statistics
        """
        city = self.get_object()  # This works with DRF router
        
        # Gather layer statistics
        layers = DataLayer.objects.filter(city=city)
        layer_stats = {
            'total_layers': layers.count(),
            'processed_layers': layers.filter(is_processed=True).count(),
            'layers_with_tiles': layers.filter(tiles_generated=True).count(),
        }
        
        # Gather feature statistics
        features = GeoFeature.objects.filter(layer__city=city)
        feature_stats = {
            'total_features': features.count(),
            'valid_features': features.filter(is_valid=True).count(),
            'features_with_plu': features.exclude(
                Q(plu_primary_code='') | Q(plu_primary_code__isnull=True)
            ).count(),
        }
        
        # PLU statistics (Bangalore only)
        plu_stats = {}
        if city.slug == 'bengaluru':
            plu_codes = features.exclude(
                Q(plu_primary_code='') | Q(plu_primary_code__isnull=True)
            ).values('plu_primary_code').annotate(
                count=Count('id')
            ).order_by('-count')
            
            plu_stats = {
                'unique_plu_codes': len(plu_codes),
                'top_plu_codes': list(plu_codes[:10]),
                'plu_mappings': PLUCodeMapping.objects.filter(city=city).count()
            }
        
        # Area statistics
        area_stats = features.aggregate(
            total_area=Sum('calculated_area'),
            avg_area=Avg('calculated_area'),
            max_area=Max('calculated_area'),
            min_area=Min('calculated_area')
        )
        
        return Response({
            'city': {
                'name': city.name,
                'slug': city.slug,
                'state': city.state
            },
            'layers': layer_stats,
            'features': feature_stats,
            'plu_codes': plu_stats,
            'area_statistics': area_stats
        })

    @action(detail=True, methods=['get'])
    def plu_mappings(self, request, slug=None):  # Keep as 'slug'
        """
        Returns PLU mappings for a city (Bangalore only).
        """
        city = self.get_object()  # This works with DRF router
        
        mappings = PLUCodeMapping.objects.filter(city=city).select_related('mapped_category')
        serializer = PLUCodeMappingSerializer(mappings, many=True)
        
        return Response({
            'city': city.name,
            'total_mappings': mappings.count(),
            'mappings': serializer.data
        })

class LayerCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing layer categories.
    - Lists all active categories.
    """
    queryset = LayerCategory.objects.filter(is_active=True)
    serializer_class = LayerCategorySerializer
    lookup_field = 'code'

class DataLayerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing data layers.
    - Lists all processed data layers.
    - Provides PLU analysis and tile generation for each layer.
    """
    queryset = DataLayer.objects.select_related('city', 'category').filter(
        is_processed=True
    )
    serializer_class = DataLayerSerializer
    filterset_fields = ['city__slug', 'category__code', 'file_format', 'categorization_method']

    @action(detail=True, methods=['get'])
    def plu_analysis(self, request, pk=None):
        """
        Returns PLU code analysis for a layer (Bangalore only).
        - PLU code distribution
        - Category mapping accuracy
        """
        layer = self.get_object()
        
        if layer.city.slug != 'bengaluru':
            return Response({
                'error': 'PLU analysis only available for Bangalore layers'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        features = GeoFeature.objects.filter(layer=layer)
        
        # PLU code distribution
        plu_distribution = features.exclude(
            Q(plu_primary_code='') | Q(plu_primary_code__isnull=True)
        ).values('plu_primary_code', 'plu_secondary_1').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Category mapping accuracy
        categorization_stats = features.values('derived_category').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return Response({
            'layer': {
                'name': layer.name,
                'total_features': features.count()
            },
            'plu_distribution': list(plu_distribution),
            'categorization': list(categorization_stats),
            'primary_plu_codes': layer.primary_plu_codes
        })

    @action(detail=True, methods=['post'])
    def generate_tiles(self, request, pk=None):
        """
        Generates vector tiles for this layer and updates its status.
        """
        layer = self.get_object()
        
        min_zoom = request.data.get('min_zoom', 8)
        max_zoom = request.data.get('max_zoom', 14)
        
        try:
            tile_service = VectorTileService()
            result = tile_service.generate_layer_tiles(layer, min_zoom, max_zoom)
            
            # Update layer status
            layer.tiles_generated = True
            layer.save()
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class GeoFeatureViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing geo features.
    - Lists all features with filtering.
    - Supports PLU code and category filtering.
    """
    queryset = GeoFeature.objects.select_related('layer', 'layer__city', 'layer__category')
    serializer_class = GeoFeatureSerializer
    filterset_fields = [
        'layer__slug', 'derived_category', 'land_use_type', 
        'plu_primary_code', 'plu_authority', 'is_valid'
    ]

    def get_queryset(self):
        # Optionally override to add custom filtering logic
        queryset = super().get_queryset()
        # Add PLU filtering for Bangalore
        plu_code = self.request.query_params.get('plu_code')
        if plu_code:
            queryset = queryset.filter(plu_primary_code=plu_code)
        # Area filtering
        min_area = self.request.query_params.get('min_area')
        max_area = self.request.query_params.get('max_area')
        if min_area:
            queryset = queryset.filter(calculated_area__gte=float(min_area))
        if max_area:
            queryset = queryset.filter(calculated_area__lte=float(max_area))
        return queryset

class VectorTileView(APIView):
    """
    API endpoint to serve a single vector tile (MVT) for a given layer and tile coordinates.
    Used by the frontend for fast map rendering.
    """
    def get(self, request, city_slug, layer_slug, z, x, y):
        try:
            # Get the requested layer
            layer = get_object_or_404(
                DataLayer, 
                city__slug=city_slug, 
                slug=layer_slug,
                is_processed=True
            )
            # Generate the MVT tile
            tile_service = VectorTileService()
            mvt_data = tile_service.generate_tile(layer, z, x, y)
            if mvt_data:
                response = HttpResponse(mvt_data, content_type='application/vnd.mapbox-vector-tile')
                response['Cache-Control'] = 'max-age=3600'
                response['Access-Control-Allow-Origin'] = '*'
                return response
            # Return empty tile if no data
            return HttpResponse(b'', content_type='application/vnd.mapbox-vector-tile')
        except Exception as e:
            print(f"Error in VectorTileView: {e}")
            return HttpResponse(b'', content_type='application/vnd.mapbox-vector-tile', status=500)

class CombinedVectorTileView(APIView):
    """
    API endpoint to serve a combined vector tile (MVT) for all or selected layers in a city.
    Supports filtering by layer slug or category.
    """
    def get(self, request, city_slug, z, x, y):
        print(f"[DEBUG] CombinedVectorTileView called for city={city_slug}, z={z}, x={x}, y={y}")
        try:
            # Get all processed layers for the city
            layers = DataLayer.objects.filter(
                city__slug=city_slug,
                is_processed=True
            ).select_related('category')
            # Optional: filter by layer slugs
            layer_slugs = request.GET.getlist('layers')
            if layer_slugs:
                layers = layers.filter(slug__in=layer_slugs)
                print(f"[DEBUG] Filtered to {layers.count()} layers by slugs: {layer_slugs}")
            # Optional: filter by categories
            categories = request.GET.getlist('categories')
            if categories:
                layers = layers.filter(category__code__in=categories)
                print(f"[DEBUG] Filtered to {layers.count()} layers by categories: {categories}")
            # Print layer details for debugging
            for layer in layers:
                print(f"[DEBUG] Layer: {layer.slug} ({layer.name}) - {layer.feature_count} features")
            # Generate the combined MVT tile
            tile_service = VectorTileService()
            print(f"[DEBUG] Calling generate_combined_tile with {len(layers)} layers")
            mvt_data = tile_service.generate_combined_tile(layers, z, x, y)
            if mvt_data:
                print(f"[DEBUG] ✅ Combined tile generated successfully: {len(mvt_data)} bytes")
                response = HttpResponse(mvt_data, content_type='application/vnd.mapbox-vector-tile')
                response['Cache-Control'] = 'max-age=3600'
                response['Access-Control-Allow-Origin'] = '*'
                return response
            print(f"[DEBUG] ❌ No MVT data generated - returning empty tile")
            return HttpResponse(b'', content_type='application/vnd.mapbox-vector-tile')
        except Exception as e:
            print(f"❌ Error in CombinedVectorTileView: {e}")
            import traceback
            traceback.print_exc()
            return HttpResponse(b'', content_type='application/vnd.mapbox-vector-tile', status=500)

class CityLayersView(APIView):
    """
    API endpoint to list all layers for a city, with optional filtering by category, format, group, or PLU.
    Used by the frontend to populate layer lists.
    """
    def get(self, request, city_slug):
        layers = DataLayer.objects.filter(
            city__slug=city_slug,
            is_processed=True
        ).select_related('city', 'category')
        # Filter by category
        category = request.GET.get('category')
        if category:
            layers = layers.filter(category__code=category)
        # Filter by file format
        file_format = request.GET.get('format')
        if file_format:
            layers = layers.filter(file_format=file_format)
        # Filter by PLU availability (Bangalore)
        has_plu = request.GET.get('has_plu')
        if has_plu and has_plu.lower() == 'true':
            layers = layers.filter(categorization_method='PLU_CODE')
        # Add group filter
        group_slug = request.GET.get('group')
        if group_slug:
            layers = layers.filter(layer_group__slug=group_slug)
        serializer = DataLayerSerializer(layers, many=True)
        return Response({
            'city': city_slug,
            'total_layers': layers.count(),
            'layers': serializer.data
        })

class LayerFeaturesView(APIView):
    """
    API endpoint to list all features for a given layer, with filtering and paginated GeoJSON output.
    Supports spatial, PLU, category, and area filtering.
    """
    def get(self, request, city_slug, layer_slug):
        layer = get_object_or_404(DataLayer, city__slug=city_slug, slug=layer_slug)
        features = GeoFeature.objects.filter(layer=layer)
        # Spatial filtering by bounding box
        bbox = request.GET.get('bbox')
        if bbox:
            try:
                coords = [float(x) for x in bbox.split(',')]
                if len(coords) == 4:
                    bbox_geom = Polygon.from_bbox(coords)
                    features = features.filter(geometry__intersects=bbox_geom)
            except (ValueError, TypeError):
                pass
        # PLU filtering
        plu_code = request.GET.get('plu_code')
        if plu_code:
            features = features.filter(plu_primary_code=plu_code)
        plu_authority = request.GET.get('plu_authority')
        if plu_authority:
            features = features.filter(plu_authority=plu_authority)
        # Category filtering
        category = request.GET.get('category')
        if category:
            features = features.filter(derived_category=category)
        # Land use filtering
        land_use = request.GET.get('land_use')
        if land_use:
            features = features.filter(land_use_type__icontains=land_use)
        # Area filtering
        min_area = request.GET.get('min_area')
        max_area = request.GET.get('max_area')
        if min_area:
            features = features.filter(calculated_area__gte=float(min_area))
        if max_area:
            features = features.filter(calculated_area__lte=float(max_area))
        # Pagination
        page_size = min(int(request.GET.get('page_size', 100)), 1000)  # Max 1000
        page = int(request.GET.get('page', 1))
        start = (page - 1) * page_size
        end = start + page_size
        total_count = features.count()
        paginated_features = features[start:end]
        # ✅ MANUAL GEOJSON CONVERSION for proper format
        geojson_features = []
        for feature in paginated_features:
            try:
                # Convert geometry to proper GeoJSON
                geom_geojson = json.loads(feature.geometry.geojson)
                # Get feature color
                color = self._get_feature_color(feature)
                geojson_feature = {
                    "id": feature.id,
                    "type": "Feature",
                    "geometry": geom_geojson,  # ✅ Proper GeoJSON geometry
                    "properties": {
                        "layer_name": feature.layer.name,
                        "city_name": feature.layer.city.name,
                        "category_name": feature.layer.category.name if feature.layer.category else 'Unknown',
                        "display_name": feature.get_display_name(),
                        "source_fid": feature.source_fid,
                        "name": feature.name or '',
                        "derived_category": feature.derived_category,
                        "land_use_type": feature.land_use_type or '',
                        "plu_primary_code": feature.plu_primary_code or '',
                        "plu_secondary_1": feature.plu_secondary_1 or '',
                        "plu_secondary_2": feature.plu_secondary_2 or '',
                        "plu_proposed_use": feature.plu_proposed_use or '',
                        "plu_authority": feature.plu_authority or '',
                        "calculated_area": float(feature.calculated_area) if feature.calculated_area else 0.0,
                        "calculated_perimeter": float(feature.calculated_perimeter) if feature.calculated_perimeter else 0.0,
                        "source_area_value": float(feature.source_area_value) if feature.source_area_value else 0.0,
                        "is_valid": feature.is_valid,
                        "geometry_simplified": feature.geometry_simplified,
                        "color": color,  # ✅ Correct color
                        "created_at": feature.created_at.isoformat(),
                    }
                }
                geojson_features.append(geojson_feature)
            except Exception as e:
                print(f"Error serializing feature {feature.id}: {e}")
                continue
        return Response({
            'layer': {
                'name': layer.name,
                'city': layer.city.name,
                'category': layer.category.name if layer.category else 'Unknown'
            },
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size
            },
            'features': {
                "type": "FeatureCollection",
                "features": geojson_features  # ✅ Proper GeoJSON format
            }
        })
    def _get_feature_color(self, feature):
        """Get the correct color for this feature"""
        from .config import get_city_config
        city_slug = feature.layer.city.slug
        category_code = feature.derived_category
        # Get city-specific color
        city_config = get_city_config(city_slug)
        if city_config and 'colors' in city_config:
            return city_config['colors'].get(category_code, '#666666')
        # Fallback to layer style
        try:
            style = feature.layer.get_style()
            if isinstance(style, dict):
                return style.get('fill_color', '#666666')
            elif hasattr(style, 'fill_color'):
                return style.fill_color
        except:
            pass
        return '#666666'

class DataImportView(APIView):
    """Enhanced data import with ESRI and configuration support"""
    
    def post(self, request):
        try:
            city_slug = request.data.get('city')
            category_code = request.data.get('category')
            uploaded_file = request.FILES.get('file')
            use_config = request.data.get('use_config', 'true').lower() == 'true'
            
            if not all([city_slug, uploaded_file]):
                return Response(
                    {'error': 'city and file are required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get city
            city = get_object_or_404(City, slug=city_slug)
            
            import_service = DataImportService()
            
            if use_config and not category_code:
                # Use configuration-based import (automatic category detection)
                try:
                    # Save file temporarily for config-based import
                    import tempfile
                    import os
                    
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=uploaded_file.name)
                    for chunk in uploaded_file.chunks():
                        temp_file.write(chunk)
                    temp_file.close()
                    
                    result = import_service.import_file_with_config(temp_file.name, city_slug)
                    os.unlink(temp_file.name)
                    
                except Exception as e:
                    return Response(
                        {'error': f'Configuration-based import failed: {str(e)}'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # Manual import with specified category
                if not category_code:
                    return Response(
                        {'error': 'category required for manual import'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                category = get_object_or_404(LayerCategory, code=category_code)
                result = import_service.import_file(uploaded_file, city, category)
            
            return Response(result, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ImportJobViewSet(viewsets.ReadOnlyModelViewSet):
    """View import job history and status"""
    queryset = ImportJob.objects.all().select_related('city')
    serializer_class = ImportJobSerializer
    filterset_fields = ['city__slug', 'status', 'file_format']
    ordering = ['-started_at']

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
        ).select_related('layer', 'layer__category').order_by('-calculated_area')
        
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
                    'area': float(feature.calculated_area) if feature.calculated_area else 0.0,
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
                    'area': float(feature.calculated_area) if feature.calculated_area else 0.0
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

# Configuration and utility views
class CityConfigView(APIView):
    """Get all city configurations"""
    
    def get(self, request):
        from .config import CITY_CONFIGS
        
        configs = {}
        for city_slug, config in CITY_CONFIGS.items():
            # Get city statistics if exists
            try:
                city = City.objects.get(slug=city_slug)
                layer_count = DataLayer.objects.filter(city=city).count()
                feature_count = GeoFeature.objects.filter(layer__city=city).count()
            except City.DoesNotExist:
                layer_count = 0
                feature_count = 0
            
            configs[city_slug] = {
                'city_info': config['city_info'],
                'total_files': len(config['file_mappings']),
                'categories': list(set(config['file_mappings'].values())),
                'colors': config['colors'],
                'data_format': config.get('data_format', 'UNKNOWN'),
                'has_plu_mapping': 'plu_mapping' in config,
                'statistics': {
                    'layers_imported': layer_count,
                    'features_imported': feature_count
                }
            }
        
        return Response(configs)

class CityConfigDetailView(APIView):
    """Get detailed configuration for a specific city"""
    
    def get(self, request, city_slug):
        config = get_city_config(city_slug)
        if not config:
            return Response(
                {'error': f'Configuration not found for city: {city_slug}'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Add import status for each file
        try:
            city = City.objects.get(slug=city_slug)
            existing_layers = DataLayer.objects.filter(city=city).values_list('original_filename', flat=True)
        except City.DoesNotExist:
            existing_layers = []
        
        file_status = {}
        for filename, category_code in config['file_mappings'].items():
            file_status[filename] = {
                'category': category_code,
                'imported': filename in existing_layers,
                'color': config['colors'].get(category_code, '#666666')
            }
        
        # Add PLU mapping info
        plu_info = {}
        if 'plu_mapping' in config:
            plu_mapping = config['plu_mapping']
            plu_info = {
                'total_codes': len(plu_mapping),
                'codes': list(plu_mapping.keys()),
                'categories_mapped': list(set(info['category'] for info in plu_mapping.values()))
            }
        
        return Response({
            'city_info': config['city_info'],
            'file_mappings': config['file_mappings'],
            'colors': config['colors'],
            'file_status': file_status,
            'data_format': config.get('data_format', 'UNKNOWN'),
            'coordinate_precision': config.get('coordinate_precision', 8),
            'plu_mapping': plu_info
        })

class SetupCitiesView(APIView):
    """Setup all cities and categories from configuration"""
    
    def post(self, request):
        try:
            from django.core.management import call_command
            from io import StringIO
            
            # Capture command output
            out = StringIO()
            call_command('setup_cities', '--with-plu', stdout=out)
            output = out.getvalue()
            
            return Response({
                'message': 'Setup completed successfully',
                'output': output
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class RasterTileView(APIView):
    """Convert MVT tiles to PNG images for anti-scraping protection - FIXED VERSION"""
    
    def get(self, request, city_slug, layer_slug, z, x, y):
        try:
            # Get layer
            layer = get_object_or_404(
                DataLayer, 
                city__slug=city_slug, 
                slug=layer_slug,
                is_processed=True
            )
            
            # Generate MVT data
            tile_service = VectorTileService()
            mvt_data = tile_service.generate_tile(layer, z, x, y)
            
            # Convert MVT to PNG
            render_service = TileRenderingService()
            
            if mvt_data:
                try:
                    png_data = render_service.mvt_to_png(mvt_data, layer, z, x, y)
                    
                    if png_data and len(png_data) > 0:
                        response = HttpResponse(png_data, content_type='image/png')
                        response['Cache-Control'] = 'max-age=3600'
                        response['Access-Control-Allow-Origin'] = '*'
                        return response
                        
                except Exception as e:
                    print(f"Error converting MVT to PNG: {e}")
                    # Fall through to empty tile
            
            # Return empty/transparent image if no data or error
            empty_png = render_service.create_empty_tile()
            response = HttpResponse(empty_png, content_type='image/png')
            response['Cache-Control'] = 'max-age=3600'
            response['Access-Control-Allow-Origin'] = '*'
            return response
            
        except Exception as e:
            print(f"Error in RasterTileView: {e}")
            # Return empty tile on any error
            try:
                render_service = TileRenderingService()
                empty_png = render_service.create_empty_tile()
                return HttpResponse(empty_png, content_type='image/png')
            except:
                # Last resort - return minimal response
                return HttpResponse(b'', content_type='image/png', status=204)

class CombinedRasterTileView(APIView):
    """
    🔄 UPDATED: Enhanced tile serving with direct S3 fallback
    Priority: CloudFront → S3 Direct → Local → On-demand → Empty
    """
    
    def get(self, request, city_slug, z, x, y):
        """
        Serve tiles with updated priority system including direct S3 generation
        """
        try:
            z, x, y = int(z), int(x), int(y)
            
            # 1. Try CloudFront redirect (fastest)
            if self._should_use_cloudfront():
                cloudfront_response = self._redirect_to_cloudfront(city_slug, z, x, y)
                if cloudfront_response:
                    return cloudfront_response
            
            # 2. Try serving from local files (backward compatibility)
            local_response = self._serve_local_tile(city_slug, z, x, y)
            if local_response:
                return local_response
            
            # 3. Generate tile directly to S3 and serve (NEW)
            direct_s3_response = self._generate_and_serve_from_s3(city_slug, z, x, y)
            if direct_s3_response:
                return direct_s3_response
            
            # 4. Fallback: Generate on-demand (temporary)
            on_demand_response = self._generate_tile_on_demand(city_slug, z, x, y)
            if on_demand_response:
                return on_demand_response
            
            # 5. Last resort: Empty tile
            return self._return_empty_tile()
            
        except ValueError:
            return Response({'error': 'Invalid tile coordinates'}, status=400)
        except Exception as e:
            logger.error(f"Error serving tile {city_slug}/{z}/{x}/{y}: {e}")
            return self._return_empty_tile()
    
    def _should_use_cloudfront(self):
        """Check if CloudFront should be used"""
        return (
            hasattr(settings, 'CLOUDFRONT_DOMAIN') and 
            settings.CLOUDFRONT_DOMAIN and 
            getattr(settings, 'USE_CLOUDFRONT', True)
        )
    
    def _redirect_to_cloudfront(self, city_slug, z, x, y):
        """Redirect to CloudFront for fast tile serving"""
        try:
            from django.shortcuts import redirect
            
            cloudfront_url = f"https://{settings.CLOUDFRONT_DOMAIN}/{city_slug}/combined/{z}_{x}_{y}.png"
            logger.info(f"☁️  Redirecting to CloudFront: {cloudfront_url}")
            
            response = redirect(cloudfront_url)
            response['X-Tile-Source'] = 'cloudfront-redirect'
            response['Cache-Control'] = 'max-age=300'  # 5 minute cache for redirects
            return response
            
        except Exception as e:
            logger.error(f"CloudFront redirect failed: {e}")
            return None
    
    def _serve_local_tile(self, city_slug, z, x, y):
        """Serve from local files (backward compatibility)"""
        try:
            import os
            from django.http import FileResponse
            
            # Try multiple possible local paths
            possible_paths = [
                f'static/tiles_png/{city_slug}/combined/{z}_{x}_{y}.png',
                f'static/tiles_png/{city_slug}/{z}_{x}_{y}.png',
                f'media/tiles_png/{city_slug}/combined/{z}_{x}_{y}.png',
            ]
            
            for png_path in possible_paths:
                if os.path.exists(png_path):
                    logger.info(f"📁 Serving local tile: {png_path}")
                    response = FileResponse(
                        open(png_path, 'rb'), 
                        content_type='image/png'
                    )
                    response['Cache-Control'] = 'max-age=3600'
                    response['X-Tile-Source'] = 'local-file'
                    return response
            
            return None
            
        except Exception as e:
            logger.error(f"Error serving local tile: {e}")
            return None
    
    def _generate_and_serve_from_s3(self, city_slug, z, x, y):
        """
        🆕 NEW: Generate tile directly to S3 and serve
        This is the new primary method for tile generation
        """
        try:
            logger.info(f"🚀 Generating tile directly to S3: {city_slug}/{z}/{x}/{y}")
            
            # Initialize direct S3 service
            service = S3DirectTileGenerationService()
            
            # Get city layers
            from maps.models import DataLayer, City
            
            try:
                city = City.objects.get(slug=city_slug, is_active=True)
                layers = DataLayer.objects.filter(
                    city=city,
                    is_processed=True
                ).select_related('category', 'city')
                
                if not layers.exists():
                    logger.warning(f"No processed layers found for city: {city_slug}")
                    return None
                
            except City.DoesNotExist:
                logger.error(f"City not found: {city_slug}")
                return None
            
            # Generate single tile directly to S3
            tile_result = service._generate_and_upload_single_tile(
                city_slug, layers, z, x, y, ['png']
            )
            
            if tile_result.get('success') and tile_result.get('png_size'):
                # Tile generated successfully, redirect to S3/CloudFront
                if service.cloudfront_domain:
                    tile_url = f"https://{service.cloudfront_domain}/{city_slug}/combined/{z}_{x}_{y}.png"
                else:
                    tile_url = f"https://{service.bucket_name}.s3.{service.region}.amazonaws.com/{city_slug}/combined/{z}_{x}_{y}.png"
                
                logger.info(f"✅ Generated and redirecting to: {tile_url}")
                
                from django.shortcuts import redirect
                response = redirect(tile_url)
                response['X-Tile-Source'] = 'generated-s3-direct'
                response['X-Generation-Time'] = 'real-time'
                response['Cache-Control'] = 'max-age=31536000'  # 1 year cache
                return response
            
            else:
                logger.warning(f"Failed to generate tile to S3: {tile_result}")
                return None
            
        except Exception as e:
            logger.error(f"Error in direct S3 generation: {e}")
            return None
    
    def _generate_tile_on_demand(self, city_slug, z, x, y):
        """Generate tile on-demand (fallback method)"""
        try:
            logger.warning(f"🔄 Generating tile on-demand: {city_slug}/{z}/{x}/{y}")
            
            from maps.models import DataLayer
            from maps.services import VectorTileService
            from maps.tile_rendering_service import TileRenderingService
            from django.http import HttpResponse
            
            # Get processed layers for the city
            layers = DataLayer.objects.filter(
                city__slug=city_slug, 
                is_processed=True
            ).select_related('category', 'city')
            
            if not layers.exists():
                logger.warning(f"No processed layers found for city: {city_slug}")
                return None
            
            # Generate MVT data
            vector_service = VectorTileService()
            mvt_data = vector_service.generate_combined_tile(layers, z, x, y)
            
            if not mvt_data or len(mvt_data) == 0:
                logger.info(f"No MVT data generated for tile {city_slug}/{z}/{x}/{y}")
                return None
            
            # Convert MVT to PNG
            renderer = TileRenderingService()
            png_data = renderer.combined_mvt_to_png(mvt_data, layers, z, x, y)
            
            if not png_data or len(png_data) == 0:
                logger.warning(f"Failed to convert MVT to PNG for {city_slug}/{z}/{x}/{y}")
                return None
            
            # Create response
            response = HttpResponse(png_data, content_type='image/png')
            response['Cache-Control'] = 'max-age=3600'  # 1 hour cache
            response['X-Tile-Source'] = 'generated-on-demand'
            response['X-Generation-Time'] = 'real-time'
            response['X-Tile-Size'] = str(len(png_data))
            response['Access-Control-Allow-Origin'] = '*'
            
            logger.info(f"✅ Generated tile on-demand: {city_slug}/{z}/{x}/{y} ({len(png_data)} bytes)")
            return response
            
        except Exception as e:
            logger.error(f"Error generating tile on-demand: {e}")
            return None
    
    def _return_empty_tile(self):
        """Return empty/transparent tile"""
        try:
            from maps.tile_rendering_service import TileRenderingService
            from django.http import HttpResponse
            
            renderer = TileRenderingService()
            empty_png = renderer.create_empty_tile()
            
            response = HttpResponse(empty_png, content_type='image/png')
            response['Cache-Control'] = 'max-age=3600'
            response['X-Tile-Source'] = 'empty-tile'
            response['Access-Control-Allow-Origin'] = '*'
            
            return response
            
        except Exception as e:
            logger.error(f"Error creating empty tile: {e}")
            from django.http import HttpResponse
            return HttpResponse(b'', content_type='image/png', status=204)

class SimpleVectorTileView(APIView):
    """A simplified view to directly test VectorTileService"""
    
    def get(self, request, city_slug, layer_slug, z, x, y):
        try:
            layer = DataLayer.objects.get(city__slug=city_slug, slug=layer_slug)
            service = VectorTileService()
            mvt_data = service.generate_tile(layer, z, x, y)
            
            if mvt_data:
                return HttpResponse(mvt_data, content_type='application/vnd.mapbox-vector-tile')
            
            return HttpResponse(b'', status=204) # No Content
            
        except DataLayer.DoesNotExist:
            return HttpResponse("Layer not found", status=404)
        except Exception as e:
            print(f"[SimpleVectorTileView] Error: {e}")
            return HttpResponse(f"Error: {e}", status=500)

class SimpleRasterTileView(APIView):
    """A simplified view to directly test TileRenderingService"""
    
    def get(self, request, city_slug, layer_slug, z, x, y):
        try:
            layer = DataLayer.objects.get(city__slug=city_slug, slug=layer_slug)
            
            # Step 1: Generate MVT
            vector_service = VectorTileService()
            mvt_data = vector_service.generate_tile(layer, z, x, y)
            
            # Step 2: Render to PNG
            renderer = TileRenderingService()
            if not mvt_data:
                return HttpResponse(renderer.create_empty_tile(), content_type='image/png')
            
            png_data = renderer.mvt_to_png(mvt_data, layer, z, x, y)
            
            return HttpResponse(png_data, content_type='image/png')
            
        except DataLayer.DoesNotExist:
            return HttpResponse("Layer not found", status=404)
        except Exception as e:
            print(f"[SimpleRasterTileView] Error: {e}")
            renderer = TileRenderingService()
            return HttpResponse(renderer.create_empty_tile(), content_type='image/png', status=500)

class StateCitiesView(APIView):
    """Get all cities for a specific state"""
    
    def get(self, request, state_slug):
        try:
            state = State.objects.get(slug=state_slug)
            cities = City.objects.filter(state_ref=state).annotate(
                layer_count=Count('layers'),
                total_features=Count('layers__features')
            )
            return Response({
                'state': StateSerializer(state).data,
                'cities': CitySerializer(cities, many=True).data
            })
        except State.DoesNotExist:
            return Response(
                {'error': f'State not found: {state_slug}'}, 
                status=status.HTTP_404_NOT_FOUND
            )

class CityLayerGroupsView(APIView):
    """Get all layer groups for a specific city"""
    
    def get(self, request, city_slug):
        try:
            city = City.objects.get(slug=city_slug)
            groups = LayerGroup.objects.filter(city=city).annotate(
                layer_count=Count('layers')
            )
            return Response({
                'city': CitySerializer(city).data,
                'layer_groups': LayerGroupSerializer(groups, many=True).data
            })
        except City.DoesNotExist:
            return Response(
                {'error': f'City not found: {city_slug}'}, 
                status=status.HTTP_404_NOT_FOUND
            )

class LayerGroupLayersView(APIView):
    """Get all layers in a specific layer group"""
    
    def get(self, request, group_slug):
        try:
            group = LayerGroup.objects.get(slug=group_slug)
            layers = DataLayer.objects.filter(layer_group=group)
            return Response({
                'group': LayerGroupSerializer(group).data,
                'layers': DataLayerSerializer(layers, many=True).data
            })
        except LayerGroup.DoesNotExist:
            return Response(
                {'error': f'Layer group not found: {group_slug}'}, 
                status=status.HTTP_404_NOT_FOUND
            )
class StaticVectorTileView(APIView):
    """Serve pre-generated MVT files from disk only."""
    permission_classes = [AllowAny]

    def get(self, request, city_slug, layer_slug, z, x, y):
        tile_path = os.path.join('media', 'tiles', city_slug, layer_slug, str(z), str(x), f'{y}.mvt')
        if os.path.exists(tile_path):
            return FileResponse(open(tile_path, 'rb'), content_type='application/vnd.mapbox-vector-tile')
        return Response({'error': 'Pre-generated tile not found', 'path': tile_path}, status=status.HTTP_404_NOT_FOUND)

class LayerConfigAPIView(APIView):
    """
    API endpoint that returns the exact structure you specified
    URL: /api/layer-config/
    """
    
    def get(self, request):
        # Get all active states with their layer configs and cities
        states = State.objects.filter(
            is_active=True
        ).prefetch_related(
            # Prefetch state-level layers
            Prefetch(
                'layer_configs',
                queryset=LayerConfig.objects.filter(
                    scope='state',
                    is_active=True
                ).order_by('sort_order', 'title'),
                to_attr='state_layers'
            ),
            # Prefetch cities with their layers
            Prefetch(
                'cities',
                queryset=City.objects.filter(
                    is_active=True
                ).prefetch_related(
                    Prefetch(
                        'layer_configs',
                        queryset=LayerConfig.objects.filter(
                            scope='urban_area',
                            is_active=True
                        ).order_by('sort_order', 'title'),
                        to_attr='urban_layers'
                    )
                ),
                to_attr='urban_areas'
            )
        ).order_by('name')
        
        # Build the response data
        states_data = []
        
        for state in states:
            # State-level layers
            state_layers = [layer.to_api_format() for layer in state.state_layers]
            
            # Urban areas with their layers
            urban_areas = []
            for city in state.urban_areas:
                if hasattr(city, 'urban_layers') and city.urban_layers:
                    urban_areas.append({
                        'id': city.id,
                        'name': city.name,
                        'slug': city.slug,
                        'layers': [layer.to_api_format() for layer in city.urban_layers]
                    })
            
            # Only include states that have either state_layers or urban_areas with layers
            if state_layers or urban_areas:
                state_data = {
                    'id': state.id,
                    'name': state.name,
                    'slug': state.slug,
                    'state_layers': state_layers,
                    'urban_areas': urban_areas
                }
                states_data.append(state_data)
        
        return Response({
            'data': {
                'states': states_data
            }
        })


class StateLayerConfigView(APIView):
    """
    Get layer configuration for a specific state
    URL: /api/states/{state_slug}/layer-config/
    """
    
    def get(self, request, state_slug):
        try:
            state = State.objects.get(slug=state_slug, is_active=True)
        except State.DoesNotExist:
            return Response({'error': 'State not found'}, status=404)
        
        # Get state-level layers
        state_layers = LayerConfig.objects.filter(
            state=state,
            scope='state',
            is_active=True
        ).order_by('sort_order', 'title')
        
        # Get urban areas with layers
        cities = City.objects.filter(
            state_ref=state,
            is_active=True
        ).prefetch_related(
            Prefetch(
                'layer_configs',
                queryset=LayerConfig.objects.filter(
                    scope='urban_area',
                    is_active=True
                ).order_by('sort_order', 'title'),
                to_attr='urban_layers'
            )
        )
        
        urban_areas = []
        for city in cities:
            if hasattr(city, 'urban_layers') and city.urban_layers:
                urban_areas.append({
                    'id': city.id,
                    'name': city.name,
                    'slug': city.slug,
                    'layers': [layer.to_api_format() for layer in city.urban_layers]
                })
        
        return Response({
            'id': state.id,
            'name': state.name,
            'slug': state.slug,
            'state_layers': [layer.to_api_format() for layer in state_layers],
            'urban_areas': urban_areas
        })


class CityLayerConfigView(APIView):
    """
    Get layer configuration for a specific city
    URL: /api/cities/{city_slug}/layer-config/
    """
    
    def get(self, request, city_slug):
        try:
            city = City.objects.select_related('state_ref').get(
                slug=city_slug, 
                is_active=True
            )
        except City.DoesNotExist:
            return Response({'error': 'City not found'}, status=404)
        
        # Get city-specific layers
        layers = LayerConfig.objects.filter(
            city=city,
            scope='urban_area',
            is_active=True
        ).order_by('sort_order', 'title')
        
        return Response({
            'id': city.id,
            'name': city.name,
            'slug': city.slug,
            'state': {
                'id': city.state_ref.id,
                'name': city.state_ref.name,
                'slug': city.state_ref.slug
            },
            'layers': [layer.to_api_format() for layer in layers]
        })


class LayerConfigDetailView(APIView):
    """
    Get details for a specific layer configuration
    URL: /api/layer-config/{layer_slug}/
    """
    
    def get(self, request, layer_slug):
        try:
            layer = LayerConfig.objects.select_related(
                'state', 'city', 'data_layer'
            ).get(slug=layer_slug, is_active=True)
        except LayerConfig.DoesNotExist:
            return Response({'error': 'Layer configuration not found'}, status=404)
        
        data = layer.to_api_format()
        
        # Add additional details
        data.update({
            'state': {
                'id': layer.state.id,
                'name': layer.state.name,
                'slug': layer.state.slug
            }
        })
        
        if layer.city:
            data['city'] = {
                'id': layer.city.id,
                'name': layer.city.name,
                'slug': layer.city.slug
            }
        
        if layer.data_layer:
            data['data_layer'] = {
                'id': layer.data_layer.id,
                'name': layer.data_layer.name,
                'slug': layer.data_layer.slug,
                'feature_count': layer.data_layer.feature_count,
                'is_processed': layer.data_layer.is_processed
            }
        
        return Response(data)

class PlotViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Plot data
    - GET /api/plots/ - List all plots
    - GET /api/plots/{id}/ - Get specific plot
    - GET /api/plots/in_bbox/ - Get plots in bounding box
    """
    queryset = Plot.objects.filter(is_active=True)
    serializer_class = PlotSerializer
    
    @action(detail=False, methods=['get'])
    def in_bbox(self, request):
        """Get plots within bounding box: ?bbox=west,south,east,north"""
        bbox = request.query_params.get('bbox')
        
        if not bbox:
            return Response({'error': 'bbox parameter required'}, status=400)
        
        try:
            west, south, east, north = map(float, bbox.split(','))
            bbox_polygon = Polygon.from_bbox((west, south, east, north))
            
            plots = self.queryset.filter(location__within=bbox_polygon)
            serializer = self.get_serializer(plots, many=True)
            
            return Response({
                'type': 'FeatureCollection',
                'features': serializer.data,
                'count': plots.count()
            })
            
        except (ValueError, TypeError):
            return Response({'error': 'Invalid bbox format'}, status=400)
    
    @action(detail=False, methods=['get'])
    def near_point(self, request):
        """Get plots near a point: ?lat=17.123&lng=77.456&radius_km=10"""
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        radius_km = float(request.query_params.get('radius_km', 10))
        
        if not lat or not lng:
            return Response({'error': 'lat and lng parameters required'}, status=400)
        
        try:
            from django.contrib.gis.geos import Point
            point = Point(float(lng), float(lat))
            
            plots = self.queryset.filter(
                location__distance_lte=(point, Distance(km=radius_km))
            )
            
            serializer = self.get_serializer(plots, many=True)
            
            return Response({
                'type': 'FeatureCollection',
                'features': serializer.data,
                'count': plots.count(),
                'search_center': {'lat': float(lat), 'lng': float(lng)},
                'radius_km': radius_km
            })
            
        except (ValueError, TypeError):
            return Response({'error': 'Invalid coordinates'}, status=400)

class LandViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Land data
    - GET /api/lands/ - List all lands
    - GET /api/lands/{id}/ - Get specific land
    - GET /api/lands/in_bbox/ - Get lands in bounding box
    """
    queryset = Land.objects.filter(is_active=True)
    serializer_class = LandSerializer
    
    @action(detail=False, methods=['get'])
    def in_bbox(self, request):
        """Get lands within bounding box: ?bbox=west,south,east,north"""
        bbox = request.query_params.get('bbox')
        
        if not bbox:
            return Response({'error': 'bbox parameter required'}, status=400)
        
        try:
            west, south, east, north = map(float, bbox.split(','))
            bbox_polygon = Polygon.from_bbox((west, south, east, north))
            
            lands = self.queryset.filter(location__within=bbox_polygon)
            serializer = self.get_serializer(lands, many=True)
            
            return Response({
                'type': 'FeatureCollection',
                'features': serializer.data,
                'count': lands.count()
            })
            
        except (ValueError, TypeError):
            return Response({'error': 'Invalid bbox format'}, status=400)
    
    @action(detail=False, methods=['get'])
    def near_point(self, request):
        """Get lands near a point: ?lat=17.123&lng=77.456&radius_km=10"""
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        radius_km = float(request.query_params.get('radius_km', 10))
        
        if not lat or not lng:
            return Response({'error': 'lat and lng parameters required'}, status=400)
        
        try:
            from django.contrib.gis.geos import Point
            point = Point(float(lng), float(lat))
            
            lands = self.queryset.filter(
                location__distance_lte=(point, Distance(km=radius_km))
            )
            
            serializer = self.get_serializer(lands, many=True)
            
            return Response({
                'type': 'FeatureCollection',
                'features': serializer.data,
                'count': lands.count(),
                'search_center': {'lat': float(lat), 'lng': float(lng)},
                'radius_km': radius_km
            })
            
        except (ValueError, TypeError):
            return Response({'error': 'Invalid coordinates'}, status=400)
        

class RealEstateVectorTileView(APIView):
    """
    Serve MVT tiles for real estate data
    URL: /api/real-estate-tiles/{type}/{z}/{x}/{y}.mvt
    type: plots, lands, or combined
    """
    
    def get(self, request, tile_type, z, x, y):
        try:
            z, x, y = int(z), int(x), int(y)
            
            # Try to serve pre-generated tile first (matching management command output)
            tile_path = Path('media/real_estate_tiles') / tile_type / str(z) / str(x) / f'{y}.mvt'
            
            if tile_path.exists():
                return FileResponse(
                    open(tile_path, 'rb'), 
                    content_type='application/vnd.mapbox-vector-tile'
                )
            
            # Generate tile on-the-fly if not pre-generated
            if tile_type == 'plots':
                mvt_data = self.generate_plot_mvt_tile(z, x, y)
            elif tile_type == 'lands':
                mvt_data = self.generate_land_mvt_tile(z, x, y)
            elif tile_type == 'combined':
                mvt_data = self.generate_combined_mvt_tile(z, x, y)
            else:
                return HttpResponse('Invalid tile type', status=404)
            
            if mvt_data:
                response = HttpResponse(mvt_data, content_type='application/vnd.mapbox-vector-tile')
                response['Cache-Control'] = 'max-age=3600'
                response['Access-Control-Allow-Origin'] = '*'
                return response
            
            # Return empty tile if no data
            return HttpResponse(b'', content_type='application/vnd.mapbox-vector-tile')
            
        except Exception as e:
            print(f"Error in RealEstateVectorTileView: {e}")
            return HttpResponse(b'', content_type='application/vnd.mapbox-vector-tile', status=500)

    def generate_plot_mvt_tile(self, z, x, y):
        """Generate MVT tile for plots"""
        tile_bounds = self.get_tile_bounds(z, x, y)
        
        plots = Plot.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        )
        
        if not plots.exists():
            return None
        
        # Limit features at low zoom
        max_features = 100 if z < 12 else 500
        plots = plots[:max_features]
        
        return self.features_to_mvt(plots, 'plots', Plot)

    def generate_land_mvt_tile(self, z, x, y):
        """Generate MVT tile for lands"""
        tile_bounds = self.get_tile_bounds(z, x, y)
        
        lands = Land.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        )
        
        if not lands.exists():
            return None
        
        # Limit features at low zoom
        max_features = 100 if z < 12 else 500
        lands = lands[:max_features]
        
        return self.features_to_mvt(lands, 'lands', Land)

    def generate_combined_mvt_tile(self, z, x, y):
        """Generate combined MVT tile"""
        tile_bounds = self.get_tile_bounds(z, x, y)
        
        plots = Plot.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        )
        
        lands = Land.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        )
        
        if not plots.exists() and not lands.exists():
            return None
        
        # Limit features
        max_features = 50 if z < 12 else 250
        plots = plots[:max_features]
        lands = lands[:max_features]
        
        return self.features_to_combined_mvt(plots, lands)

    def features_to_mvt(self, features, layer_name, model):
        """Convert features to MVT format (matching management command logic)"""
        try:
            mvt_features = []
            
            for feature in features:
                try:
                    # Prepare properties based on model type
                    if model == Plot:
                        properties = {
                            'id': feature.plot_id,
                            'name': feature.marker_title or '',
                            'title': feature.marker_title or '',
                            'marker_id': feature.marker_id or '',
                            'area_sq_yards': feature.area_sq_yards or 0,
                            'price_per_sq_yard': feature.price_per_sq_yard or 0,
                            'total_price': feature.total_price or 0,
                            'type': 'plot',
                            'category': 'Real Estate'
                        }
                    else:  # Land
                        properties = {
                            'id': feature.land_id,
                            'name': feature.marker_title or '',
                            'title': feature.marker_title or '',
                            'marker_id': feature.marker_id or '',
                            'area_text': feature.area_text or '',
                            'price_text': feature.price_text or '',
                            'type': 'land',
                            'category': 'Real Estate'
                        }
                    
                    mvt_feature = {
                        'geometry': {
                            'type': 'Point',
                            'coordinates': [feature.location.x, feature.location.y]
                        },
                        'properties': properties
                    }
                    
                    mvt_features.append(mvt_feature)
                    
                except Exception:
                    continue
            
            if not mvt_features:
                return None
            
            # Encode MVT (matching management command)
            layer_data = [{
                'name': layer_name,
                'features': mvt_features,
                'version': 2,
                'extent': 4096
            }]
            
            return mapbox_vector_tile.encode(layer_data)
            
        except Exception as e:
            print(f"Error encoding MVT for {layer_name}: {e}")
            return None

    def features_to_combined_mvt(self, plots, lands):
        """Convert combined features to MVT format"""
        try:
            layers_list = []
            
            # Add plots layer
            if plots.exists():
                plot_features = []
                for plot in plots:
                    try:
                        plot_features.append({
                            'geometry': {
                                'type': 'Point',
                                'coordinates': [plot.location.x, plot.location.y]
                            },
                            'properties': {
                                'id': plot.plot_id,
                                'name': plot.marker_title or '',
                                'title': plot.marker_title or '',
                                'marker_id': plot.marker_id or '',
                                'area_sq_yards': plot.area_sq_yards or 0,
                                'price_per_sq_yard': plot.price_per_sq_yard or 0,
                                'total_price': plot.total_price or 0,
                                'type': 'plot',
                                'category': 'Real Estate'
                            }
                        })
                    except Exception:
                        continue
                
                if plot_features:
                    layers_list.append({
                        'name': 'plots',
                        'features': plot_features,
                        'version': 2,
                        'extent': 4096
                    })
            
            # Add lands layer
            if lands.exists():
                land_features = []
                for land in lands:
                    try:
                        land_features.append({
                            'geometry': {
                                'type': 'Point',
                                'coordinates': [land.location.x, land.location.y]
                            },
                            'properties': {
                                'id': land.land_id,
                                'name': land.marker_title or '',
                                'title': land.marker_title or '',
                                'marker_id': land.marker_id or '',
                                'area_text': land.area_text or '',
                                'price_text': land.price_text or '',
                                'type': 'land',
                                'category': 'Real Estate'
                            }
                        })
                    except Exception:
                        continue
                
                if land_features:
                    layers_list.append({
                        'name': 'lands',
                        'features': land_features,
                        'version': 2,
                        'extent': 4096
                    })
            
            if not layers_list:
                return None
            
            return mapbox_vector_tile.encode(layers_list)
            
        except Exception as e:
            print(f"Error encoding combined MVT: {e}")
            return None

    def get_tile_bounds(self, z, x, y):
        """Get tile bounding box as Polygon"""
        bounds = mercantile.bounds(x, y, z)
        return Polygon.from_bbox([
            bounds.west, bounds.south,
            bounds.east, bounds.north
        ])

class RealEstateRasterTileView(APIView):
    """
    Serve real estate tiles (plots/lands) from CloudFront with fallback options.
    Supports: plots, lands, combined
    """
    permission_classes = []  # Public access for tiles
    
    def get(self, request, tile_type, z, x, y):
        try:
            # Convert parameters to integers
            z, x, y = int(z), int(x), int(y)
            
            # Validate tile type
            if tile_type not in ['plots', 'lands', 'combined']:
                return HttpResponse("Invalid tile type. Use: plots, lands, or combined", status=400)
            
            # Validate zoom level
            if not (0 <= z <= 20):
                return HttpResponse("Invalid zoom level", status=400)
            
            # Method 1: Redirect to CloudFront
            if self._should_use_cloudfront():
                cloudfront_url = self._get_cloudfront_url(tile_type, z, x, y)
                
                # Direct redirect for production
                if not settings.DEBUG:
                    return redirect(cloudfront_url)
                
                # Validate first for development
                if self._validate_cloudfront_tile(cloudfront_url):
                    return redirect(cloudfront_url)
            
            # Method 2: Serve pre-generated local file
            local_tile_response = self._serve_local_real_estate_tile(tile_type, z, x, y)
            if local_tile_response:
                return local_tile_response
            
            # Method 3: Generate on-demand
            return self._generate_real_estate_tile(tile_type, z, x, y)
            
        except Exception as e:
            logger.error(f"Error in RealEstateRasterTileView for {tile_type}/{z}/{x}/{y}: {e}")
            return self._return_empty_tile()
    
    def _should_use_cloudfront(self):
        """Check if CloudFront is configured"""
        return (
            hasattr(settings, 'CLOUDFRONT_DOMAIN') and 
            settings.CLOUDFRONT_DOMAIN and 
            settings.CLOUDFRONT_DOMAIN != 'your-cloudfront-id.cloudfront.net'
        )
    
    def _get_cloudfront_url(self, tile_type, z, x, y):
        """Generate CloudFront URL for real estate tile"""
        return f"https://{settings.CLOUDFRONT_DOMAIN}/real_estate/{tile_type}/{z}_{x}_{y}.png"
    
    def _validate_cloudfront_tile(self, url):
        """Check if tile exists in CloudFront"""
        try:
            response = requests.head(url, timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def _serve_local_real_estate_tile(self, tile_type, z, x, y):
        """Serve pre-generated local real estate tile"""
        # Try multiple possible paths
        possible_paths = [
            f'static/real_estate_tiles_png/{tile_type}/{z}_{x}_{y}.png',
            f'static/real_estate_tiles_png/combined/{z}_{x}_{y}.png' if tile_type == 'combined' else None,
            f'media/real_estate_tiles/{tile_type}/{z}_{x}_{y}.png',
        ]
        
        # Filter out None values
        possible_paths = [path for path in possible_paths if path]
        
        for png_path in possible_paths:
            if os.path.exists(png_path):
                logger.info(f"Serving local real estate tile: {png_path}")
                response = FileResponse(
                    open(png_path, 'rb'), 
                    content_type='image/png'
                )
                response['Cache-Control'] = 'max-age=3600'
                response['X-Tile-Source'] = 'local-real-estate'
                return response
        
        return None
    
    def _generate_real_estate_tile(self, tile_type, z, x, y):
        """Generate real estate tile on-demand"""
        try:
            from maps.models import Plot, Land
            from django.contrib.gis.geos import Polygon
            import mercantile
            import mapbox_vector_tile
            
            logger.warning(f"Generating real estate tile on-demand: {tile_type}/{z}/{x}/{y}")
            
            # Get tile bounds
            tile_bounds = self._get_tile_bounds(z, x, y)
            if not tile_bounds:
                return self._return_empty_tile()
            
            # Generate MVT data based on tile type
            if tile_type == 'plots':
                mvt_data = self._generate_plots_mvt(tile_bounds, z, x, y)
            elif tile_type == 'lands':
                mvt_data = self._generate_lands_mvt(tile_bounds, z, x, y)
            else:  # combined
                mvt_data = self._generate_combined_real_estate_mvt(tile_bounds, z, x, y)
            
            if not mvt_data:
                return self._return_empty_tile()
            
            # Convert MVT to PNG
            png_data = self._convert_real_estate_mvt_to_png(mvt_data, tile_type, z, x, y)
            
            response = HttpResponse(png_data, content_type='image/png')
            response['Cache-Control'] = 'max-age=3600'
            response['X-Tile-Source'] = f'generated-real-estate-{tile_type}'
            response['Access-Control-Allow-Origin'] = '*'
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating real estate tile: {e}")
            return self._return_empty_tile()
    
    def _get_tile_bounds(self, z, x, y):
        """Get geographic bounds for tile"""
        try:
            import mercantile
            from django.contrib.gis.geos import Polygon
            
            bounds = mercantile.bounds(x, y, z)
            tile_polygon = Polygon.from_bbox((
                bounds.west, bounds.south, bounds.east, bounds.north
            ))
            return tile_polygon
        except:
            return None
    
    def _generate_plots_mvt(self, tile_bounds, z, x, y):
        """Generate MVT for plots only"""
        try:
            from maps.models import Plot
            import mapbox_vector_tile
            
            plots = Plot.objects.filter(
                location__intersects=tile_bounds,
                is_active=True
            )[:500]  # Limit for performance
            
            if not plots.exists():
                return None
            
            features = []
            for plot in plots:
                features.append({
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [plot.location.x, plot.location.y]
                    },
                    'properties': {
                        'id': plot.plot_id,
                        'title': plot.marker_title or '',
                        'type': 'plot'
                    }
                })
            
            layer_data = [{
                'name': 'plots',
                'features': features,
                'version': 2,
                'extent': 4096
            }]
            
            return mapbox_vector_tile.encode(layer_data)
            
        except Exception as e:
            logger.error(f"Error generating plots MVT: {e}")
            return None
    
    def _generate_lands_mvt(self, tile_bounds, z, x, y):
        """Generate MVT for lands only"""
        try:
            from maps.models import Land
            import mapbox_vector_tile
            
            lands = Land.objects.filter(
                location__intersects=tile_bounds,
                is_active=True
            )[:500]  # Limit for performance
            
            if not lands.exists():
                return None
            
            features = []
            for land in lands:
                features.append({
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [land.location.x, land.location.y]
                    },
                    'properties': {
                        'id': land.land_id,
                        'title': land.marker_title or '',
                        'type': 'land'
                    }
                })
            
            layer_data = [{
                'name': 'lands',
                'features': features,
                'version': 2,
                'extent': 4096
            }]
            
            return mapbox_vector_tile.encode(layer_data)
            
        except Exception as e:
            logger.error(f"Error generating lands MVT: {e}")
            return None
    
    def _generate_combined_real_estate_mvt(self, tile_bounds, z, x, y):
        """Generate combined MVT with both plots and lands"""
        try:
            from maps.models import Plot, Land
            import mapbox_vector_tile
            
            # Get both plots and lands
            plots = Plot.objects.filter(
                location__intersects=tile_bounds,
                is_active=True
            )[:250]
            
            lands = Land.objects.filter(
                location__intersects=tile_bounds,
                is_active=True
            )[:250]
            
            layers_list = []
            
            # Add plots layer
            if plots.exists():
                plot_features = []
                for plot in plots:
                    plot_features.append({
                        'geometry': {
                            'type': 'Point',
                            'coordinates': [plot.location.x, plot.location.y]
                        },
                        'properties': {
                            'id': plot.plot_id,
                            'title': plot.marker_title or '',
                            'type': 'plot'
                        }
                    })
                
                layers_list.append({
                    'name': 'plots',
                    'features': plot_features,
                    'version': 2,
                    'extent': 4096
                })
            
            # Add lands layer
            if lands.exists():
                land_features = []
                for land in lands:
                    land_features.append({
                        'geometry': {
                            'type': 'Point',
                            'coordinates': [land.location.x, land.location.y]
                        },
                        'properties': {
                            'id': land.land_id,
                            'title': land.marker_title or '',
                            'type': 'land'
                        }
                    })
                
                layers_list.append({
                    'name': 'lands',
                    'features': land_features,
                    'version': 2,
                    'extent': 4096
                })
            
            if not layers_list:
                return None
            
            return mapbox_vector_tile.encode(layers_list)
            
        except Exception as e:
            logger.error(f"Error generating combined real estate MVT: {e}")
            return None
    
    def _convert_real_estate_mvt_to_png(self, mvt_data, tile_type, z, x, y):
        """Convert real estate MVT to PNG"""
        try:
            import mapbox_vector_tile
            from PIL import Image, ImageDraw
            import io
            
            # Decode MVT
            decoded_data = mapbox_vector_tile.decode(mvt_data)
            if not decoded_data:
                return self._create_empty_png()
            
            # Create image
            img = Image.new('RGBA', (256, 256), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            
            # Draw features
            for layer_name, layer_data in decoded_data.items():
                features = layer_data.get('features', [])
                
                # Set colors based on layer
                if layer_name == 'plots':
                    color = (255, 120, 0, 200)      # Orange
                    outline = (255, 120, 0, 255)
                else:  # lands
                    color = (0, 255, 0, 200)       # Green
                    outline = (0, 255, 0, 255)
                
                for feature in features:
                    self._draw_point_feature(draw, feature, color, outline, z)
            
            # Convert to PNG
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG', optimize=True)
            return img_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error converting real estate MVT to PNG: {e}")
            return self._create_empty_png()
    
    def _draw_point_feature(self, draw, feature, color, outline_color, zoom):
        """Draw a point feature on the image"""
        try:
            geometry = feature.get('geometry', {})
            if geometry.get('type') != 'Point':
                return
            
            coords = geometry.get('coordinates', [])
            if len(coords) != 2:
                return
            
            # Convert to pixel coordinates (simplified)
            x, y = coords
            pixel_x = int((x + 180) / 360 * 256)
            pixel_y = int((90 - y) / 180 * 256)
            
            # Draw point with size based on zoom
            radius = max(2, min(8, zoom - 8))
            
            draw.ellipse(
                [pixel_x - radius, pixel_y - radius, pixel_x + radius, pixel_y + radius],
                fill=color,
                outline=outline_color
            )
            
        except Exception as e:
            logger.error(f"Error drawing point feature: {e}")
    
    def _create_empty_png(self):
        """Create empty PNG bytes"""
        try:
            from PIL import Image
            import io
            
            img = Image.new('RGBA', (256, 256), (255, 255, 255, 0))
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            return img_buffer.getvalue()
        except:
            return b''
    
    def _return_empty_tile(self):
        """Return empty tile response"""
        try:
            renderer = TileRenderingService()
            empty_png = renderer.create_empty_tile()
            response = HttpResponse(empty_png, content_type='image/png')
            response['Cache-Control'] = 'max-age=3600'
            response['X-Tile-Source'] = 'empty-real-estate'
            response['Access-Control-Allow-Origin'] = '*'
            return response
        except:
            return HttpResponse(b'', content_type='image/png', status=204)
        
class TileUploadManagementView(APIView):
    """
    🔄 UPDATED: Enhanced tile upload management with direct S3 generation
    Provides both legacy local upload and new direct S3 generation
    """
    
    def get(self, request, city_slug):
        """Get upload status and available actions"""
        try:
            # Initialize services
            direct_service = S3DirectTileGenerationService()
            
            # Test S3 connection
            connection_test = direct_service.test_connection()
            
            # Check for local tiles (for backward compatibility)
            local_tiles = self._check_local_tiles(city_slug)
            
            # Get CloudFront status
            cloudfront_status = self._get_cloudfront_status()
            
            return Response({
                'city': city_slug,
                's3_connection': connection_test,
                'local_tiles': local_tiles,
                'cloudfront': cloudfront_status,
                'available_actions': [
                    'generate_direct_s3',      # NEW: Direct S3 generation
                    'upload_city_png',         # Legacy: Upload existing local files
                    'upload_city_mvt',         # Legacy: Upload existing local files
                    'upload_real_estate',      # Legacy: Upload existing local files
                    'test_s3_connection'       # Test connection
                ],
                'recommended_action': 'generate_direct_s3',
                'direct_generation_available': True
            })
            
        except Exception as e:
            return Response({
                'error': f'Failed to get upload status: {str(e)}'
            }, status=500)
    
    def post(self, request, city_slug):
        """Trigger tile operations (upload or direct generation)"""
        try:
            action = request.data.get('action')
            
            if not action:
                return Response({
                    'error': 'Action required',
                    'available_actions': [
                        'generate_direct_s3',
                        'upload_city_png', 
                        'upload_city_mvt',
                        'upload_real_estate',
                        'test_s3_connection'
                    ]
                }, status=400)
            
            # Handle direct S3 generation (NEW)
            if action == 'generate_direct_s3':
                return self._handle_direct_s3_generation(request, city_slug)
            
            # Handle legacy uploads (existing functionality)
            elif action in ['upload_city_png', 'upload_city_mvt', 'upload_real_estate', 'test_s3_connection']:
                return self._handle_legacy_upload(request, city_slug, action)
            
            else:
                return Response({
                    'error': f'Unknown action: {action}'
                }, status=400)
                
        except Exception as e:
            return Response({
                'error': f'Operation failed: {str(e)}'
            }, status=500)
    
    def _handle_direct_s3_generation(self, request, city_slug):
        """Handle direct S3 tile generation"""
        try:
            service = S3DirectTileGenerationService()
            
            # Get parameters with defaults
            tile_types = request.data.get('tile_types', ['png', 'mvt'])
            min_zoom = int(request.data.get('min_zoom', 8))
            max_zoom = int(request.data.get('max_zoom', 14))
            include_real_estate = request.data.get('include_real_estate', False)
            
            results = {}
            
            # Generate city tiles
            city_result = service.generate_and_upload_city_tiles(
                city_slug=city_slug,
                min_zoom=min_zoom,
                max_zoom=max_zoom,
                tile_types=tile_types
            )
            results['city'] = city_result
            
            # Optionally generate real estate tiles
            if include_real_estate:
                real_estate_result = service.generate_and_upload_real_estate_tiles(
                    data_type='combined',
                    min_zoom=min_zoom,
                    max_zoom=max_zoom,
                    tile_types=tile_types
                )
                results['real_estate'] = real_estate_result
            
            # Determine overall success
            overall_success = city_result.get('success', False)
            if include_real_estate:
                overall_success = overall_success and results['real_estate'].get('success', False)
            
            return Response({
                'action': 'generate_direct_s3',
                'city': city_slug,
                'success': overall_success,
                'results': results,
                'message': 'Direct S3 generation completed',
                'cloudfront_urls': city_result.get('sample_urls', {}) if city_result.get('success') else None
            })
            
        except Exception as e:
            logger.error(f"Error in direct S3 generation: {e}")
            return Response({
                'action': 'generate_direct_s3',
                'city': city_slug,
                'success': False,
                'error': str(e),
                'message': 'Direct S3 generation failed'
            }, status=500)
    
    def _handle_legacy_upload(self, request, city_slug, action):
        """Handle legacy file upload operations"""
        try:
            # Use existing S3TileUploadService for backward compatibility
            from maps.s3_upload_service import S3TileUploadService
            upload_service = S3TileUploadService()
            
            # Handle different legacy actions
            if action == 'test_s3_connection':
                result = upload_service.test_connection()
                
            elif action == 'upload_city_png':
                result = upload_service.upload_city_tiles(city_slug, 'png')
                
            elif action == 'upload_city_mvt':
                result = upload_service.upload_city_tiles(city_slug, 'mvt')
                
            elif action == 'upload_real_estate':
                data_type = request.data.get('data_type', 'combined')
                tile_type = request.data.get('type', 'png')
                result = upload_service.upload_real_estate_tiles(data_type, tile_type)
            
            # Return result
            if result.get('success'):
                return Response({
                    'action': action,
                    'city': city_slug,
                    'result': result,
                    'message': f'{action} completed successfully'
                })
            else:
                return Response({
                    'action': action,
                    'city': city_slug,
                    'result': result,
                    'message': f'{action} failed'
                }, status=500)
                
        except Exception as e:
            logger.error(f"Error in legacy upload: {e}")
            return Response({
                'action': action,
                'city': city_slug,
                'success': False,
                'error': str(e),
                'message': f'{action} failed'
            }, status=500)
    
    def _check_local_tiles(self, city_slug):
        """Check what tiles are available locally (for backward compatibility)"""
        import os
        from pathlib import Path
        
        tile_info = {
            'city_png': 0,
            'city_mvt': 0,
            'real_estate_png': 0,
            'real_estate_mvt': 0
        }
        
        # Check city PNG tiles
        city_png_dir = Path(f'static/tiles_png/{city_slug}')
        if city_png_dir.exists():
            tile_info['city_png'] = len(list(city_png_dir.rglob('*.png')))
        
        # Check city MVT tiles  
        city_mvt_dir = Path(f'media/tiles/{city_slug}')
        if city_mvt_dir.exists():
            tile_info['city_mvt'] = len(list(city_mvt_dir.rglob('*.mvt')))
        
        # Check real estate PNG tiles
        re_png_dir = Path('static/real_estate_tiles_png')
        if re_png_dir.exists():
            tile_info['real_estate_png'] = len(list(re_png_dir.rglob('*.png')))
        
        # Check real estate MVT tiles
        re_mvt_dir = Path('media/real_estate_tiles')
        if re_mvt_dir.exists():
            tile_info['real_estate_mvt'] = len(list(re_mvt_dir.rglob('*.mvt')))
        
        return tile_info
    
    def _get_cloudfront_status(self):
        """Get CloudFront configuration status"""
        cloudfront_configured = (
            hasattr(settings, 'CLOUDFRONT_DOMAIN') and 
            settings.CLOUDFRONT_DOMAIN and 
            settings.CLOUDFRONT_DOMAIN != 'your-cloudfront-id.cloudfront.net'
        )
        
        return {
            'configured': cloudfront_configured,
            'domain': getattr(settings, 'CLOUDFRONT_DOMAIN', 'Not configured'),
            'status': 'Ready' if cloudfront_configured else 'Needs configuration'
        }
    
class TileURLView(APIView):
    """
    Return CloudFront URLs for frontend mapping libraries.
    Useful for configuring mapping libraries like Leaflet, Mapbox, etc.
    """
    
    def get(self, request, city_slug):
        try:
            # Check if CloudFront is configured
            if not hasattr(settings, 'CLOUDFRONT_DOMAIN') or not settings.CLOUDFRONT_DOMAIN:
                return Response({
                    'error': 'CloudFront not configured',
                    'message': 'Set CLOUDFRONT_DOMAIN in settings.py'
                }, status=503)
            
            base_url = f"https://{settings.CLOUDFRONT_DOMAIN}"
            
            # Generate URL templates
            tile_urls = {
                'city_tiles': {
                    'combined_png': f"{base_url}/{city_slug}/combined/{{z}}_{{x}}_{{y}}.png",
                    'combined_mvt': f"{base_url}/{city_slug}/combined/{{z}}_{{x}}_{{y}}.mvt",
                    'description': 'City masterplan layers combined'
                },
                'real_estate_tiles': {
                    'plots_png': f"{base_url}/real_estate/plots/{{z}}_{{x}}_{{y}}.png",
                    'lands_png': f"{base_url}/real_estate/lands/{{z}}_{{x}}_{{y}}.png",
                    'combined_png': f"{base_url}/real_estate/combined/{{z}}_{{x}}_{{y}}.png",
                    'description': 'Real estate data (plots and lands)'
                },
                'leaflet_examples': {
                    'city_layer': f"L.tileLayer('{base_url}/{city_slug}/combined/{{z}}_{{x}}_{{y}}.png')",
                    'real_estate_layer': f"L.tileLayer('{base_url}/real_estate/combined/{{z}}_{{x}}_{{y}}.png')"
                }
            }
            
            # Example URLs for testing
            example_urls = {
                'city_tile_example': f"{base_url}/{city_slug}/combined/12_3119_3222.png",
                'real_estate_example': f"{base_url}/real_estate/combined/12_3119_3222.png",
                'test_instructions': 'Open these URLs in browser to test tile serving'
            }
            
            return Response({
                'city': city_slug,
                'cloudfront_domain': settings.CLOUDFRONT_DOMAIN,
                'tile_urls': tile_urls,
                'example_urls': example_urls,
                'status': 'CloudFront configured and ready'
            })
            
        except Exception as e:
            logger.error(f"Error in TileURLView: {e}")
            return Response({
                'error': 'Internal server error',
                'message': str(e)
            }, status=500)
        
class DirectS3TileGenerationView(APIView):
    """
    🚀 NEW: Generate tiles directly to S3 without local storage
    Supports both city tiles and real estate tiles
    """
    
    def post(self, request, city_slug=None):
        """Trigger direct S3 tile generation"""
        try:
            # Initialize service
            service = S3DirectTileGenerationService()
            
            # Test connection first
            connection_test = service.test_connection()
            if not connection_test['success']:
                return Response({
                    'error': 'S3 connection failed',
                    'details': connection_test['error']
                }, status=503)
            
            # Get parameters
            action = request.data.get('action', 'generate_city')
            tile_types = request.data.get('tile_types', ['png', 'mvt'])
            min_zoom = int(request.data.get('min_zoom', 8))
            max_zoom = int(request.data.get('max_zoom', 14))
            
            # Validate zoom levels
            if min_zoom < 0 or max_zoom > 18 or min_zoom > max_zoom:
                return Response({
                    'error': 'Invalid zoom levels',
                    'message': 'Zoom levels must be between 0-18 and min_zoom <= max_zoom'
                }, status=400)
            
            # Validate tile types
            if not isinstance(tile_types, list) or not all(t in ['png', 'mvt'] for t in tile_types):
                return Response({
                    'error': 'Invalid tile_types',
                    'message': 'tile_types must be a list containing "png" and/or "mvt"'
                }, status=400)
            
            result = None
            
            # Handle city tile generation
            if action == 'generate_city':
                if not city_slug:
                    return Response({
                        'error': 'city_slug required for city tile generation'
                    }, status=400)
                
                result = service.generate_and_upload_city_tiles(
                    city_slug=city_slug,
                    min_zoom=min_zoom,
                    max_zoom=max_zoom,
                    tile_types=tile_types
                )
                
            # Handle real estate tile generation
            elif action == 'generate_real_estate':
                data_type = request.data.get('data_type', 'combined')
                
                if data_type not in ['plots', 'lands', 'combined']:
                    return Response({
                        'error': 'Invalid data_type',
                        'message': 'data_type must be "plots", "lands", or "combined"'
                    }, status=400)
                
                result = service.generate_and_upload_real_estate_tiles(
                    data_type=data_type,
                    min_zoom=min_zoom,
                    max_zoom=max_zoom,
                    tile_types=tile_types
                )
                
            # Handle all cities generation
            elif action == 'generate_all_cities':
                from maps.models import City
                
                cities = City.objects.filter(is_active=True).values_list('slug', flat=True)
                if not cities:
                    return Response({
                        'error': 'No active cities found'
                    }, status=404)
                
                all_results = {
                    'cities_processed': 0,
                    'cities_successful': 0,
                    'total_tiles_generated': 0,
                    'total_size_mb': 0,
                    'city_results': {}
                }
                
                for city in cities:
                    city_result = service.generate_and_upload_city_tiles(
                        city_slug=city,
                        min_zoom=min_zoom,
                        max_zoom=max_zoom,
                        tile_types=tile_types
                    )
                    
                    all_results['cities_processed'] += 1
                    all_results['city_results'][city] = city_result
                    
                    if city_result['success']:
                        all_results['cities_successful'] += 1
                        all_results['total_tiles_generated'] += city_result['results']['generated_tiles']
                        all_results['total_size_mb'] += city_result['results']['total_size_mb']
                
                result = {
                    'success': all_results['cities_successful'] > 0,
                    'summary': all_results,
                    'message': f"Processed {all_results['cities_processed']} cities, {all_results['cities_successful']} successful"
                }
                
            else:
                return Response({
                    'error': 'Invalid action',
                    'valid_actions': ['generate_city', 'generate_real_estate', 'generate_all_cities']
                }, status=400)
            
            # Return result
            if result and result.get('success'):
                return Response({
                    'status': 'success',
                    'action': action,
                    'result': result,
                    'message': 'Tile generation completed successfully'
                })
            else:
                return Response({
                    'status': 'error',
                    'action': action,
                    'result': result,
                    'message': 'Tile generation failed'
                }, status=500)
                
        except Exception as e:
            logger.error(f"Error in DirectS3TileGenerationView: {e}")
            return Response({
                'error': 'Internal server error',
                'message': str(e)
            }, status=500)
        
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
        self.bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'gis-portal')
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
                    bbox_parts = bbox_param.split(',')
                    if len(bbox_parts) != 4:
                        raise ValueError("bbox must have 4 values: west,south,east,north")
                    
                    west, south, east, north = map(float, bbox_parts)
                    bounds = {
                        'west': west,
                        'south': south, 
                        'east': east,
                        'north': north
                    }
                except ValueError as e:
                    return Response({
                        'error': f'Invalid bbox format: {str(e)}',
                        'expected_format': 'west,south,east,north (e.g., 77.5,12.9,77.6,13.0)'
                    }, status=400)
            else:
                # Use city bounds or layer bounds
                bounds = self._get_city_bounds(city)
                if not bounds:
                    return Response({
                        'error': 'No bounds available for city. Please provide bbox parameter.',
                        'city': city_slug
                    }, status=400)
            
            # Get potential tile coordinates for the area
            potential_tiles = self._get_potential_tiles(bounds, zoom, limit)
            
            # Check which tiles actually exist in S3
            available_tiles = self._check_tiles_existence(city_slug, potential_tiles)
            
            # Build response
            response_data = {
                'city': city_slug,
                'zoom': zoom,
                'bounds': bounds,
                'total_potential_tiles': len(potential_tiles),
                'available_tiles_count': len(available_tiles),
                'available_tiles': available_tiles,
                'tile_template': {
                    'cloudfront_url': f"https://{self.cloudfront_domain}/{city_slug}/combined/{{z}}_{{x}}_{{y}}.png" if self.cloudfront_domain else None,
                    's3_url': f"https://{self.bucket_name}.s3.amazonaws.com/{city_slug}/combined/{{z}}_{{x}}_{{y}}.png",
                    'api_url': f"/api/tiles/{city_slug}/combined/{{z}}/{{x}}/{{y}}.png"
                }
            }
            
            # Add performance info
            if len(available_tiles) < len(potential_tiles):
                response_data['performance_note'] = f"Only {len(available_tiles)} out of {len(potential_tiles)} potential tiles exist. This will reduce load times."
            
            return Response(response_data, status=200)
            
        except Exception as e:
            logger.error(f"Error in AvailableTilesView: {str(e)}")
            return Response({
                'error': 'Internal server error',
                'message': str(e)
            }, status=500)
    
    def _get_city_bounds(self, city):
        """Get bounds for the city from its layers"""
        try:
            # Try to get bounds from city center if available
            if city.center_lat and city.center_lng:
                # Create a reasonable bounds around the city center
                # This is approximate - adjust the buffer based on your cities
                buffer = 0.1  # roughly 10km buffer
                return {
                    'west': city.center_lng - buffer,
                    'south': city.center_lat - buffer,
                    'east': city.center_lng + buffer,
                    'north': city.center_lat + buffer
                }
            
            # Get bounds from processed layers
            from django.contrib.gis.db.models import Extent
            layers = DataLayer.objects.filter(city=city, is_processed=True)
            
            if layers.exists():
                # Use layer bounds if available
                layer_with_bounds = layers.exclude(
                    bbox_xmin__isnull=True
                ).first()
                
                if layer_with_bounds:
                    return {
                        'west': layer_with_bounds.bbox_xmin,
                        'south': layer_with_bounds.bbox_ymin,
                        'east': layer_with_bounds.bbox_xmax,
                        'north': layer_with_bounds.bbox_ymax
                    }
                
                # Calculate bounds from features
                from maps.models import GeoFeature
                extent = GeoFeature.objects.filter(
                    layer__city=city,
                    layer__is_processed=True,
                    is_valid=True
                ).aggregate(extent=Extent('geometry'))['extent']
                
                if extent:
                    return {
                        'west': extent[0],
                        'south': extent[1],
                        'east': extent[2], 
                        'north': extent[3]
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting city bounds: {str(e)}")
            return None
    
    def _get_potential_tiles(self, bounds, zoom, limit):
        """Get all potential tile coordinates for the given bounds and zoom"""
        try:
            # Use mercantile to get tiles that intersect with bounds
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'], 
                zoom
            ))
            
            # Limit the number of tiles to avoid massive responses
            if len(tiles) > limit:
                logger.warning(f"Limiting tiles from {len(tiles)} to {limit}")
                tiles = tiles[:limit]
            
            # Convert to simple coordinate format
            potential_tiles = []
            for tile in tiles:
                potential_tiles.append({
                    'z': tile.z,
                    'x': tile.x,
                    'y': tile.y,
                    'coordinates': f"{tile.z}/{tile.x}/{tile.y}"
                })
            
            return potential_tiles
            
        except Exception as e:
            logger.error(f"Error getting potential tiles: {str(e)}")
            return []
    
    def _check_tiles_existence(self, city_slug, potential_tiles):
        """Check which tiles actually exist in S3"""
        available_tiles = []
        
        try:
            # For large numbers of tiles, we'll batch check them
            batch_size = 50
            
            for i in range(0, len(potential_tiles), batch_size):
                batch = potential_tiles[i:i + batch_size]
                
                for tile in batch:
                    s3_key = f"{city_slug}/combined/{tile['z']}_{tile['x']}_{tile['y']}.png"
                    
                    try:
                        # Check if object exists in S3
                        self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
                        
                        # Tile exists, add to available list
                        tile_data = tile.copy()
                        tile_data.update({
                            's3_key': s3_key,
                            'exists': True
                        })
                        available_tiles.append(tile_data)
                        
                    except ClientError as e:
                        error_code = e.response['Error']['Code']
                        if error_code == '404':
                            # Tile doesn't exist, skip it
                            continue
                        else:
                            # Other S3 error, log but continue
                            logger.warning(f"S3 error checking tile {s3_key}: {error_code}")
                            continue
                    except Exception as e:
                        # Other error, log but continue
                        logger.error(f"Error checking tile {s3_key}: {str(e)}")
                        continue
            
            return available_tiles
            
        except Exception as e:
            logger.error(f"Error checking tile existence: {str(e)}")
            # Return all potential tiles if S3 check fails
            return potential_tiles


class TileCoordinatesView(APIView):
    """
    Optimized API for getting tile coordinates without S3 checks
    GET /api/cities/{city_slug}/tiles/coordinates/?zoom={z}&bbox={west,south,east,north}
    """
    
    def get(self, request, city_slug):
        """
        Get tile coordinates for a city and zoom level (fast, no existence check)
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
            bbox_param = request.GET.get('bbox')
            limit = int(request.GET.get('limit', 1000))
            
            # Validate zoom
            if not zoom:
                return Response({
                    'error': 'zoom parameter is required'
                }, status=400)
            
            try:
                zoom = int(zoom)
                if zoom < 0 or zoom > 18:
                    raise ValueError("Zoom must be between 0 and 18")
            except ValueError as e:
                return Response({
                    'error': f'Invalid zoom level: {str(e)}'
                }, status=400)
            
            # Parse bbox
            if bbox_param:
                try:
                    west, south, east, north = map(float, bbox_param.split(','))
                    bounds = {'west': west, 'south': south, 'east': east, 'north': north}
                except ValueError:
                    return Response({
                        'error': 'Invalid bbox format. Use: west,south,east,north'
                    }, status=400)
            else:
                # Get city bounds
                bounds = self._get_city_bounds_fast(city)
                if not bounds:
                    return Response({
                        'error': 'No bounds available. Please provide bbox parameter.'
                    }, status=400)
            
            # Calculate tile coordinates
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'],
                zoom
            ))
            
            # Limit response size
            if len(tiles) > limit:
                tiles = tiles[:limit]
            
            # Format response
            tile_coordinates = []
            for tile in tiles:
                tile_coordinates.append({
                    'z': tile.z,
                    'x': tile.x, 
                    'y': tile.y
                })
            
            return Response({
                'city': city_slug,
                'zoom': zoom,
                'bounds': bounds,
                'total_tiles': len(tile_coordinates),
                'tiles': tile_coordinates,
                'note': 'This endpoint returns coordinates only. Use /available/ endpoint to check existence.'
            })
            
        except Exception as e:
            logger.error(f"Error in TileCoordinatesView: {str(e)}")
            return Response({
                'error': 'Internal server error',
                'message': str(e)
            }, status=500)
    
    def _get_city_bounds_fast(self, city):
        """Fast bounds lookup using cached city center"""
        if city.center_lat and city.center_lng:
            buffer = 0.1  # Adjust based on your city sizes
            return {
                'west': city.center_lng - buffer,
                'south': city.center_lat - buffer,
                'east': city.center_lng + buffer,
                'north': city.center_lat + buffer
            }
        return None
    

class CityCenterView(APIView):
    """
    API endpoint to get city center coordinates with default zoom
    URL: /api/cities/{city_slug}/center/
    """
    permission_classes = [AllowAny]
    
    def get(self, request, city_slug):
        """
        Get center coordinates for a city with default zoom level 9
        
        Returns:
        {
            "city_slug": "bangalore",
            "city_name": "Bangalore", 
            "center": {
                "latitude": 12.9716,
                "longitude": 77.5946
            },
            "zoom": 9,
            "state": {
                "name": "Karnataka",
                "slug": "karnataka"
            }
        }
        """
        try:
            # Get city with state information
            city = City.objects.select_related('state_ref').get(
                slug=city_slug, 
                is_active=True
            )
            
            # Validate that city has center coordinates
            if not city.center_lat or not city.center_lng:
                return Response({
                    'error': 'City center coordinates not available',
                    'message': f'Center coordinates are not set for {city.name}',
                    'city_slug': city_slug
                }, status=400)
            
            # Build response
            response_data = {
                'city_slug': city.slug,
                'city_name': city.name,
                'center': {
                    'latitude': city.center_lat,
                    'longitude': city.center_lng
                },
                'zoom': 9,  # Default zoom level as requested
            }
            
            # Add state information if available
            if city.state_ref:
                response_data['state'] = {
                    'name': city.state_ref.name,
                    'slug': city.state_ref.slug
                }
            else:
                # Fallback to legacy state field
                response_data['state'] = {
                    'name': city.state,
                    'slug': None
                }
            
            return Response(response_data, status=200)
            
        except City.DoesNotExist:
            return Response({
                'error': 'City not found',
                'message': f'No active city found with slug: {city_slug}',
                'available_cities_endpoint': '/api/cities/'
            }, status=404)
            
        except Exception as e:
            return Response({
                'error': 'Internal server error',
                'message': str(e)
            }, status=500)
        
class CombinedLayerCenterView(APIView):
    """
    API endpoint to get the center coordinates of combined layers
    URL: /api/cities/{city_slug}/combined-layer-center/
    """
    permission_classes = [AllowAny]
    
    def get(self, request, city_slug):
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
        result = self.get_combined_layer_center(city_slug)
        
        if 'error' in result:
            return Response(result, status=400)
        
        return Response(result, status=200)
    
    def get_combined_layer_center(self, city_slug):
        """
        Calculate the center coordinates of the combined bounds of all layers for a city.
        
        Args:
            city_slug: The slug identifier for the city
            
        Returns:
            dict: Center coordinates and bounds information
        """
        from maps.models import City, DataLayer
        
        try:
            # Get the city
            city = City.objects.get(slug=city_slug, is_active=True)
            
            # Get all processed layers for this city
            layers = DataLayer.objects.filter(
                city=city,
                is_processed=True
            ).exclude(
                bbox_xmin__isnull=True,
                bbox_ymin__isnull=True,
                bbox_xmax__isnull=True,
                bbox_ymax__isnull=True
            )
            
            if not layers.exists():
                return {
                    'error': f'No processed layers with bounds found for {city_slug}',
                    'city': city_slug
                }
            
            # Calculate combined bounds
            combined_bounds = {
                'west': float('inf'),
                'south': float('inf'),
                'east': float('-inf'),
                'north': float('-inf')
            }
            
            # Iterate through all layers to find the overall bounds
            for layer in layers:
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
            
        except City.DoesNotExist:
            return {
                'error': f'City not found: {city_slug}',
                'city': city_slug
            }
        except Exception as e:
            return {
                'error': f'Error calculating combined layer center: {str(e)}',
                'city': city_slug
            }

class CompleteHierarchyAPIView(APIView):
    """
    Complete Hierarchy API - Returns all states, cities, layers with their status
    
    GET /api/hierarchy/
    
    Returns:
    - All states with their cities
    - Each city with its layers
    - Status of each layer (processed, tiles available, live status)
    - Statistics and metadata
    """
    
    def get(self, request):
        """Get complete hierarchy with status information"""
        try:
            # ❌ BROKEN: .annotate(feature_count=Count('geofeature_set'))
            # ✅ FIXED: Don't annotate, use the existing feature_count field
            states = State.objects.filter(is_active=True).prefetch_related(
                Prefetch(
                    'cities',
                    queryset=City.objects.filter(is_active=True).prefetch_related(
                        Prefetch(
                            'layers',
                            queryset=DataLayer.objects.select_related('category')
                            # Removed conflicting annotation
                        )
                    )
                )
            ).annotate(
                total_cities=Count('cities', filter=Q(cities__is_active=True)),
                total_layers=Count('cities__layers'),
                total_features=Count('cities__layers__geofeature_set')  # Fixed relationship
            ).order_by('name')
            
            hierarchy_data = []
            
            for state in states:
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
                        'total_cities': state.total_cities,
                        'total_layers': state.total_layers,
                        'total_features': state.total_features
                    },
                    'cities': []
                }
                
                for city in state.cities.all():
                    layers_data = []
                    
                    # Process layers for this city
                    processed_layers = 0
                    layers_with_tiles = 0
                    total_city_features = 0
                    
                    for layer in city.layers.all():
                        # Use existing feature_count field instead of annotation
                        layer_feature_count = layer.feature_count or 0
                        
                        # Determine layer status
                        is_live = layer.is_processed and layer.tiles_generated
                        layer_status = 'live' if is_live else 'pending' if layer.is_processed else 'no_data'
                        
                        if layer.is_processed:
                            processed_layers += 1
                        if layer.tiles_generated:
                            layers_with_tiles += 1
                        
                        total_city_features += layer_feature_count
                        
                        layers_data.append({
                            'name': layer.name,
                            'slug': layer.slug,
                            'description': layer.description,
                            'category': {
                                'name': layer.category.name,
                                'code': layer.category.code,
                                'color': layer.category.default_color
                            },
                            'status': layer_status,
                            'is_live': is_live,
                            'is_processed': layer.is_processed,
                            'tiles_generated': layer.tiles_generated,
                            'feature_count': layer_feature_count,  # Use existing field
                            'file_format': layer.file_format,
                            'last_updated': layer.updated_at.isoformat() if layer.updated_at else None,
                            'bounds': {
                                'xmin': layer.bbox_xmin,
                                'ymin': layer.bbox_ymin,
                                'xmax': layer.bbox_xmax,
                                'ymax': layer.bbox_ymax
                            } if layer.has_valid_bbox() else None
                        })
                    
                    # City status summary
                    city_is_live = processed_layers > 0 and layers_with_tiles > 0
                    
                    city_data = {
                        'name': city.name,
                        'slug': city.slug,
                        'center_lat': city.center_lat,
                        'center_lng': city.center_lng,
                        'is_active': city.is_active,
                        'is_live': city_is_live,
                        'statistics': {
                            'total_layers': len(layers_data),
                            'processed_layers': processed_layers,
                            'layers_with_tiles': layers_with_tiles,
                            'total_features': total_city_features
                        },
                        'status': 'live' if city_is_live else 'pending' if processed_layers > 0 else 'no_data',
                        'layers': layers_data
                    }
                    
                    state_data['cities'].append(city_data)
                
                hierarchy_data.append(state_data)
            
            return Response({
                'status': 'success',
                'total_states': len(hierarchy_data),
                'hierarchy': hierarchy_data
            })
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_layer_status(self, layer):
        """Determine detailed layer status"""
        if not layer.is_processed:
            return 'not_processed'
        elif layer.feature_count == 0:
            return 'no_features'
        elif not layer.tiles_generated:
            return 'tiles_pending'
        else:
            return 'live'
    
    def _get_layer_tile_urls(self, state_slug, city_slug, layer_slug, tiles_available):
        """Get tile URLs for a layer"""
        if not tiles_available:
            return None
        
        # Use your CloudFront domain or S3 bucket
        base_url = getattr(settings, 'CLOUDFRONT_DOMAIN', 'd17yosovmfjm4.cloudfront.net')
        
        return {
            'png_template': f"https://{base_url}/tiles/{state_slug}/{city_slug}/{layer_slug}/{{z}}/{{x}}/{{y}}.png",
            'mvt_template': f"https://{base_url}/tiles/{state_slug}/{city_slug}/{layer_slug}/{{z}}/{{x}}/{{y}}.mvt",
            'api_png_template': f"/api/tiles/{state_slug}/{city_slug}/{layer_slug}/{{z}}/{{x}}/{{y}}.png",
            'api_mvt_template': f"/api/tiles/{state_slug}/{city_slug}/{layer_slug}/{{z}}/{{x}}/{{y}}.mvt"
        }

# ================================
# API 2: HIERARCHICAL TILE SERVING API
# ================================

class HierarchicalTileView(APIView):
    """
    Hierarchical Tile Serving API
    
    Serves tiles using the hierarchical URL structure:
    GET /api/tiles/<state_slug>/<city_slug>/<layer_slug>/<z>/<x>/<y>.<format>
    
    Examples:
    - /api/tiles/karnataka/bengaluru/master_plan/12/2048/2048.png
    - /api/tiles/andhra_pradesh/visakhapatnam/master_plan/12/2048/2048.png
    - /api/tiles/telangana/hyderabad/rrr/12/2048/2048.mvt
    """
    
    def get(self, request, state_slug, city_slug, layer_slug, z, x, y, format='png'):
        """Serve hierarchical tiles with multiple fallback strategies"""
        try:
            z, x, y = int(z), int(x), int(y)
            
            # Validate tile coordinates
            if not self._validate_tile_coordinates(z, x, y):
                return self._return_error_tile(format, "Invalid tile coordinates")
            
            # Get layer information
            layer = self._get_layer_by_hierarchy(state_slug, city_slug, layer_slug)
            if not layer:
                return self._return_error_tile(format, f"Layer not found: {state_slug}/{city_slug}/{layer_slug}")
            
            # Check if layer has tiles
            if not layer.tiles_generated:
                # Try to generate tile on-demand
                generated_response = self._generate_hierarchical_tile_on_demand(layer, z, x, y, format)
                if generated_response:
                    return generated_response
                
                return self._return_empty_tile(format)
            
            # Try multiple serving strategies
            
            # 1. CloudFront redirect (fastest for production)
            if self._should_use_cloudfront():
                cloudfront_response = self._redirect_to_cloudfront_hierarchical(state_slug, city_slug, layer_slug, z, x, y, format)
                if cloudfront_response:
                    return cloudfront_response
            
            # 2. Direct S3 serving
            s3_response = self._serve_from_s3_hierarchical(state_slug, city_slug, layer_slug, z, x, y, format)
            if s3_response:
                return s3_response
            
            # 3. Local file serving (backward compatibility)
            local_response = self._serve_local_hierarchical_tile(state_slug, city_slug, layer_slug, z, x, y, format)
            if local_response:
                return local_response
            
            # 4. Generate and serve on-demand
            on_demand_response = self._generate_hierarchical_tile_on_demand(layer, z, x, y, format)
            if on_demand_response:
                return on_demand_response
            
            # 5. Return empty tile as last resort
            return self._return_empty_tile(format)
            
        except ValueError as e:
            logger.error(f"Invalid coordinates for hierarchical tile: {e}")
            return self._return_error_tile(format, "Invalid tile coordinates")
        except Exception as e:
            logger.error(f"Error serving hierarchical tile {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format}: {e}")
            return self._return_empty_tile(format)
    
    def _get_layer_by_hierarchy(self, state_slug, city_slug, layer_slug):
        """Get layer using hierarchical slugs"""
        try:
            return DataLayer.objects.select_related('city__state_ref', 'category').get(
                city__state_ref__slug=state_slug,
                city__slug=city_slug,
                slug=layer_slug,
                city__is_active=True,
                city__state_ref__is_active=True
            )
        except DataLayer.DoesNotExist:
            logger.warning(f"Layer not found: {state_slug}/{city_slug}/{layer_slug}")
            return None
    
    def _validate_tile_coordinates(self, z, x, y):
        """Validate tile coordinates"""
        if z < 0 or z > 20:
            return False
        if x < 0 or x >= (2 ** z):
            return False
        if y < 0 or y >= (2 ** z):
            return False
        return True
    
    def _should_use_cloudfront(self):
        """Check if CloudFront should be used"""
        return (
            hasattr(settings, 'CLOUDFRONT_DOMAIN') and 
            settings.CLOUDFRONT_DOMAIN and 
            getattr(settings, 'USE_CLOUDFRONT', True)
        )
    
    def _redirect_to_cloudfront_hierarchical(self, state_slug, city_slug, layer_slug, z, x, y, format):
        """Redirect to CloudFront for hierarchical tiles"""
        try:
            from django.shortcuts import redirect
            
            cloudfront_url = f"https://{settings.CLOUDFRONT_DOMAIN}/tiles/{state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format}"
            logger.info(f"☁️  Redirecting to CloudFront: {cloudfront_url}")
            
            response = redirect(cloudfront_url)
            response['X-Tile-Source'] = 'cloudfront-hierarchical'
            response['Cache-Control'] = 'max-age=3600'  # 1 hour cache
            return response
            
        except Exception as e:
            logger.error(f"CloudFront hierarchical redirect failed: {e}")
            return None
    
    def _serve_from_s3_hierarchical(self, state_slug, city_slug, layer_slug, z, x, y, format):
        """Serve hierarchical tiles directly from S3"""
        try:
            # Implementation would depend on your S3 setup
            # This is a placeholder for S3 direct serving
            logger.info(f"🪣 Attempting S3 hierarchical serve: {state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format}")
            return None  # Implement based on your S3 configuration
            
        except Exception as e:
            logger.error(f"S3 hierarchical serving failed: {e}")
            return None
    
    def _serve_local_hierarchical_tile(self, state_slug, city_slug, layer_slug, z, x, y, format):
        """Serve hierarchical tiles from local files"""
        try:
            # Try multiple possible local paths
            possible_paths = [
                f'static/tiles_{format}/{state_slug}/{city_slug}/{layer_slug}/{z}_{x}_{y}.{format}',
                f'media/tiles_{format}/{state_slug}/{city_slug}/{layer_slug}/{z}_{x}_{y}.{format}',
                f'static/tiles_{format}/{city_slug}/{layer_slug}/{z}_{x}_{y}.{format}',  # Fallback
            ]
            
            for tile_path in possible_paths:
                if os.path.exists(tile_path):
                    logger.info(f"📁 Serving local hierarchical tile: {tile_path}")
                    
                    content_type = 'image/png' if format == 'png' else 'application/x-protobuf'
                    response = FileResponse(
                        open(tile_path, 'rb'), 
                        content_type=content_type
                    )
                    response['Cache-Control'] = 'max-age=3600'
                    response['X-Tile-Source'] = 'local-hierarchical'
                    response['Access-Control-Allow-Origin'] = '*'
                    return response
            
            return None
            
        except Exception as e:
            logger.error(f"Error serving local hierarchical tile: {e}")
            return None
    
    def _generate_hierarchical_tile_on_demand(self, layer, z, x, y, format):
        """Generate hierarchical tile on-demand"""
        try:
            logger.info(f"🔄 Generating hierarchical tile on-demand: {layer.city.slug}/{layer.slug}/{z}/{x}/{y}.{format}")
            
            # Use existing vector tile service
            vector_service = VectorTileService()
            
            # Generate MVT data for this specific layer
            mvt_data = vector_service.generate_layer_tile([layer], z, x, y)
            
            if not mvt_data or len(mvt_data) == 0:
                return self._return_empty_tile(format)
            
            if format == 'mvt':
                # Return MVT directly
                response = HttpResponse(mvt_data, content_type='application/x-protobuf')
                response['Cache-Control'] = 'max-age=300'  # 5 minute cache for on-demand
                response['X-Tile-Source'] = 'on-demand-hierarchical-mvt'
                response['Access-Control-Allow-Origin'] = '*'
                return response
            
            elif format == 'png':
                # Convert MVT to PNG
                render_service = TileRenderingService()
                png_data = render_service.render_mvt_to_png(mvt_data, layer)
                
                response = HttpResponse(png_data, content_type='image/png')
                response['Cache-Control'] = 'max-age=300'  # 5 minute cache for on-demand
                response['X-Tile-Source'] = 'on-demand-hierarchical-png'
                response['Access-Control-Allow-Origin'] = '*'
                return response
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating hierarchical tile on-demand: {e}")
            return None
    
    def _return_empty_tile(self, format):
        """Return empty tile for the requested format"""
        try:
            if format == 'png':
                render_service = TileRenderingService()
                empty_png = render_service.create_empty_tile()
                response = HttpResponse(empty_png, content_type='image/png')
            elif format == 'mvt':
                # Empty MVT tile
                response = HttpResponse(b'', content_type='application/x-protobuf')
            else:
                response = HttpResponse(b'', content_type='application/octet-stream')
            
            response['Cache-Control'] = 'max-age=3600'
            response['X-Tile-Source'] = 'empty-hierarchical'
            response['Access-Control-Allow-Origin'] = '*'
            return response
            
        except Exception as e:
            logger.error(f"Error creating empty hierarchical tile: {e}")
            return HttpResponse(b'', content_type='application/octet-stream', status=204)
    
    def _return_error_tile(self, format, error_message):
        """Return error tile with message"""
        logger.error(f"Hierarchical tile error: {error_message}")
        return self._return_empty_tile(format)

# ================================
# ADDITIONAL UTILITY VIEWS
# ================================

class LayerStatusAPIView(APIView):
    """Get status of a specific layer in the hierarchy"""
    
    def get(self, request, state_slug, city_slug, layer_slug):
        """Get detailed status of a specific layer"""
        try:
            layer = DataLayer.objects.select_related('city__state_ref', 'category').get(
                city__state_ref__slug=state_slug,
                city__slug=city_slug,
                slug=layer_slug
            )
            
            return Response({
                'state': layer.city.state_ref.name,
                'city': layer.city.name,
                'layer': {
                    'name': layer.name,
                    'slug': layer.slug,
                    'category': layer.category.name,
                    'is_processed': layer.is_processed,
                    'tiles_generated': layer.tiles_generated,
                    'feature_count': layer.feature_count,
                    'is_live': layer.is_processed and layer.tiles_generated,
                    'last_updated': layer.updated_at.isoformat() if layer.updated_at else None
                }
            })
            
        except DataLayer.DoesNotExist:
            return Response({
                'error': f'Layer not found: {state_slug}/{city_slug}/{layer_slug}'
            }, status=status.HTTP_404_NOT_FOUND)
        
@api_view(['GET'])
def state_list_api(request):
    """
    List all states for hierarchy navigation
    GET /api/hierarchy/states/
    """
    try:
        states = State.objects.filter(is_active=True).annotate(
            city_count=Count('cities', filter=Q(cities__is_active=True)),
            layer_count=Count('cities__layers'),
            total_features=Count('cities__layers__geofeature_set')  # Fixed relationship
        ).order_by('name')
        
        states_data = []
        for state in states:
            states_data.append({
                'id': state.id,
                'name': state.name,
                'slug': state.slug,
                'code': state.code,
                'center_lat': state.center_lat,
                'center_lng': state.center_lng,
                'statistics': {
                    'cities': state.city_count,
                    'layers': state.layer_count,
                    'features': state.total_features
                }
            })
        
        return Response({
            'status': 'success',
            'count': len(states_data),
            'states': states_data
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def state_cities_api(request, state_slug):
    """
    List all cities for a specific state
    GET /api/hierarchy/states/<state_slug>/cities/
    """
    try:
        try:
            state = State.objects.get(slug=state_slug, is_active=True)
        except State.DoesNotExist:
            return Response({
                'status': 'error',
                'message': f'State not found: {state_slug}'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get cities with statistics
        cities = City.objects.filter(state_ref=state, is_active=True).annotate(
            layer_count=Count('layers'),
            total_features=Count('layers__geofeature_set'),  # Fixed relationship
            processed_layers=Count('layers', filter=Q(layers__is_processed=True)),
            layers_with_tiles=Count('layers', filter=Q(layers__tiles_generated=True))
        ).order_by('name')
        
        cities_data = []
        for city in cities:
            # Determine city status
            is_live = city.processed_layers > 0 and city.layers_with_tiles > 0
            
            cities_data.append({
                'id': city.id,
                'name': city.name,
                'slug': city.slug,
                'center_lat': city.center_lat,
                'center_lng': city.center_lng,
                'is_active': city.is_active,
                'status': 'live' if is_live else 'pending' if city.processed_layers > 0 else 'no_data',
                'statistics': {
                    'total_layers': city.layer_count,
                    'processed_layers': city.processed_layers,
                    'layers_with_tiles': city.layers_with_tiles,
                    'total_features': city.total_features
                }
            })
        
        return Response({
            'status': 'success',
            'state': {
                'id': state.id,
                'name': state.name,
                'slug': state.slug,
                'code': state.code
            },
            'count': len(cities_data),
            'cities': cities_data
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def city_layers_api(request, city_slug):
    """
    List all layers for a specific city
    GET /api/hierarchy/cities/<city_slug>/layers/
    """
    try:
        try:
            city = City.objects.select_related('state_ref').get(slug=city_slug, is_active=True)
        except City.DoesNotExist:
            return Response({
                'status': 'error',
                'message': f'City not found: {city_slug}'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # ❌ BROKEN: .annotate(feature_count=Count('geofeature_set'))
        # ✅ FIXED: Use the existing feature_count field
        layers = DataLayer.objects.filter(city=city).select_related('category')
        
        layers_data = []
        for layer in layers:
            # Use existing feature_count field
            layer_feature_count = layer.feature_count or 0
            
            # Determine layer status
            is_live = layer.is_processed and layer.tiles_generated
            layer_status = 'live' if is_live else 'pending' if layer.is_processed else 'no_data'
            
            layers_data.append({
                'id': layer.id,
                'name': layer.name,
                'slug': layer.slug,
                'description': layer.description,
                'category': {
                    'name': layer.category.name,
                    'code': layer.category.code,
                    'color': layer.category.default_color
                },
                'status': layer_status,
                'is_live': is_live,
                'is_processed': layer.is_processed,
                'tiles_generated': layer.tiles_generated,
                'feature_count': layer_feature_count,  # Use existing field
                'file_format': layer.file_format,
                'created_at': layer.created_at.isoformat(),
                'updated_at': layer.updated_at.isoformat() if layer.updated_at else None,
                'bounds': {
                    'xmin': layer.bbox_xmin,
                    'ymin': layer.bbox_ymin,
                    'xmax': layer.bbox_xmax,
                    'ymax': layer.bbox_ymax
                } if layer.has_valid_bbox() else None
            })
        
        return Response({
            'status': 'success',
            'city': {
                'id': city.id,
                'name': city.name,
                'slug': city.slug,
                'state': city.state_ref.name if city.state_ref else city.state
            },
            'count': len(layers_data),
            'layers': layers_data
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class OneCompleteHierarchyAPI(APIView):
    """
    🚀 SINGLE COMPLETE HIERARCHY API
    
    GET /api/complete-hierarchy/
    
    Returns EVERYTHING in one API call:
    - All states with their cities
    - All cities with their layers  
    - All layers with their complete status
    - Statistics at every level
    - Ready-to-use frontend data structure
    
    No annotation conflicts, all relationships fixed!
    """
    
    def get(self, request):
        """Get the complete hierarchy in one optimized call"""
        try:
            # 🔥 OPTIMIZED QUERY - No annotation conflicts!
            states = State.objects.filter(is_active=True).prefetch_related(
                Prefetch(
                    'cities',
                    queryset=City.objects.filter(is_active=True).prefetch_related(
                        Prefetch(
                            'layers',
                            queryset=DataLayer.objects.select_related('category').order_by('category__display_order', 'name')
                        )
                    ).order_by('name')
                )
            ).order_by('name')
            
            # 📊 Build the complete hierarchy
            complete_hierarchy = {
                'status': 'success',
                'generated_at': timezone.now().isoformat(),
                'summary': {
                    'total_states': 0,
                    'total_cities': 0,
                    'total_layers': 0,
                    'total_features': 0,
                    'live_cities': 0,
                    'pending_cities': 0
                },
                'hierarchy': []
            }
            
            for state in states:
                state_stats = {
                    'total_cities': 0,
                    'active_cities': 0,
                    'total_layers': 0,
                    'processed_layers': 0,
                    'layers_with_tiles': 0,
                    'total_features': 0
                }
                
                cities_data = []
                
                for city in state.cities.all():
                    city_stats = {
                        'total_layers': 0,
                        'processed_layers': 0,
                        'layers_with_tiles': 0,
                        'total_features': 0
                    }
                    
                    layers_data = []
                    
                    # Process all layers for this city
                    for layer in city.layers.all():
                        # ✅ Use existing feature_count field (no annotation conflict!)
                        layer_feature_count = layer.feature_count or 0
                        
                        # Determine layer status
                        is_live = layer.is_processed and layer.tiles_generated
                        
                        if layer.is_processed:
                            city_stats['processed_layers'] += 1
                            state_stats['processed_layers'] += 1
                            
                        if layer.tiles_generated:
                            city_stats['layers_with_tiles'] += 1
                            state_stats['layers_with_tiles'] += 1
                        
                        city_stats['total_features'] += layer_feature_count
                        state_stats['total_features'] += layer_feature_count
                        
                        # Layer data
                        layer_data = {
                            'id': layer.id,
                            'name': layer.name,
                            'slug': layer.slug,
                            'description': layer.description or '',
                            'category': {
                                'id': layer.category.id,
                                'name': layer.category.name,
                                'code': layer.category.code,
                                'color': layer.category.default_color,
                                'display_order': layer.category.display_order
                            },
                            'status': {
                                'is_live': is_live,
                                'is_processed': layer.is_processed,
                                'tiles_generated': layer.tiles_generated,
                                'has_data': layer_feature_count > 0,
                                'status_text': 'live' if is_live else 'pending' if layer.is_processed else 'no_data'
                            },
                            'data': {
                                'feature_count': layer_feature_count,
                                'file_format': layer.file_format,
                                'geometry_type': layer.geometry_type or 'unknown',
                                'categorization_method': layer.categorization_method
                            },
                            'spatial': {
                                'has_bbox': layer.has_valid_bbox(),
                                'bounds': {
                                    'xmin': layer.bbox_xmin,
                                    'ymin': layer.bbox_ymin,
                                    'xmax': layer.bbox_xmax,
                                    'ymax': layer.bbox_ymax
                                } if layer.has_valid_bbox() else None
                            },
                            'timestamps': {
                                'created_at': layer.created_at.isoformat(),
                                'updated_at': layer.updated_at.isoformat() if layer.updated_at else None
                            },
                            'urls': {
                                'vector_tile': f'/api/tiles/{state.slug}/{city.slug}/{layer.slug}/{{z}}/{{x}}/{{y}}.mvt',
                                'raster_tile': f'/api/tiles/{state.slug}/{city.slug}/{layer.slug}/{{z}}/{{x}}/{{y}}.png',
                                'features_api': f'/api/layers/{layer.id}/features/',
                                'layer_detail': f'/api/layers/{layer.id}/'
                            }
                        }
                        
                        layers_data.append(layer_data)
                        city_stats['total_layers'] += 1
                        state_stats['total_layers'] += 1
                    
                    # City status determination
                    city_is_live = city_stats['processed_layers'] > 0 and city_stats['layers_with_tiles'] > 0
                    city_is_pending = city_stats['processed_layers'] > 0 and not city_is_live
                    
                    if city_is_live:
                        complete_hierarchy['summary']['live_cities'] += 1
                    elif city_is_pending:
                        complete_hierarchy['summary']['pending_cities'] += 1
                    
                    # City data
                    city_data = {
                        'id': city.id,
                        'name': city.name,
                        'slug': city.slug,
                        'state_name': state.name,
                        'coordinates': {
                            'center_lat': city.center_lat,
                            'center_lng': city.center_lng,
                            'zoom_range': {
                                'min': city.min_zoom,
                                'max': city.max_zoom
                            }
                        },
                        'status': {
                            'is_active': city.is_active,
                            'is_live': city_is_live,
                            'is_pending': city_is_pending,
                            'status_text': 'live' if city_is_live else 'pending' if city_is_pending else 'no_data'
                        },
                        'statistics': city_stats,
                        'urls': {
                            'city_api': f'/api/cities/{city.slug}/',
                            'layers_api': f'/api/hierarchy/cities/{city.slug}/layers/',
                            'tiles_base': f'/api/tiles/{state.slug}/{city.slug}/'
                        },
                        'layers': layers_data
                    }
                    
                    cities_data.append(city_data)
                    state_stats['total_cities'] += 1
                    if city.is_active:
                        state_stats['active_cities'] += 1
                
                # State data
                state_data = {
                    'id': state.id,
                    'name': state.name,
                    'slug': state.slug,
                    'code': state.code,
                    'coordinates': {
                        'center_lat': state.center_lat,
                        'center_lng': state.center_lng,
                        'default_zoom': state.default_zoom
                    },
                    'status': {
                        'is_active': state.is_active,
                        'has_data': state_stats['total_features'] > 0,
                        'completion_percentage': round(
                            (state_stats['processed_layers'] / state_stats['total_layers'] * 100) 
                            if state_stats['total_layers'] > 0 else 0, 1
                        )
                    },
                    'statistics': state_stats,
                    'urls': {
                        'state_api': f'/api/states/{state.slug}/',
                        'cities_api': f'/api/hierarchy/states/{state.slug}/cities/',
                        'tiles_base': f'/api/tiles/{state.slug}/'
                    },
                    'cities': cities_data
                }
                
                complete_hierarchy['hierarchy'].append(state_data)
                
                # Update summary
                complete_hierarchy['summary']['total_states'] += 1
                complete_hierarchy['summary']['total_cities'] += state_stats['total_cities']
                complete_hierarchy['summary']['total_layers'] += state_stats['total_layers']
                complete_hierarchy['summary']['total_features'] += state_stats['total_features']
            
            # Add completion percentage to summary
            complete_hierarchy['summary']['completion_percentage'] = round(
                (complete_hierarchy['summary']['live_cities'] / complete_hierarchy['summary']['total_cities'] * 100)
                if complete_hierarchy['summary']['total_cities'] > 0 else 0, 1
            )
            
            # 🎯 Cache response for 5 minutes (optional)
            # cache.set('complete_hierarchy', complete_hierarchy, 300)
            
            return Response(complete_hierarchy)
            
        except Exception as e:
            import traceback
            return Response({
                'status': 'error',
                'message': str(e),
                'traceback': traceback.format_exc() if settings.DEBUG else None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_cache_key(self, request):
        """Generate cache key for this response"""
        return 'complete_hierarchy_v1'
    
    def should_cache(self, request):
        """Determine if this response should be cached"""
        return request.GET.get('no_cache', '').lower() != 'true'