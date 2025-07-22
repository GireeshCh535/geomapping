from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Avg, Max, Min, Sum
from rest_framework import viewsets, status
from rest_framework.decorators import action
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
from maps.models import Plot, Land

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
        total_features=Count('layers__features')
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
        if city.slug == 'bangalore':
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
        
        if layer.city.slug != 'bangalore':
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
    """Serve combined raster tiles (PNG)"""
    
    def get(self, request, city_slug, z, x, y):
        """Handle request and return combined PNG"""
        try:
            # Check for pre-generated PNG
            png_path = os.path.join('static', 'tiles_png', city_slug, 'combined', f'{z}_{x}_{y}.png')
            if os.path.exists(png_path):
                return FileResponse(open(png_path, 'rb'), content_type='image/png')
            
            # Fallback: generate on the fly
            layers = DataLayer.objects.filter(
                city__slug=city_slug, 
                is_processed=True
            ).select_related('category')
            
            vector_service = VectorTileService()
            mvt_data = vector_service.generate_combined_tile(layers, z, x, y)
            
            if not mvt_data:
                renderer = TileRenderingService()
                return HttpResponse(renderer.create_empty_tile(), content_type='image/png')
            
            renderer = TileRenderingService()
            png_data = renderer.combined_mvt_to_png(mvt_data, layers, z, x, y)
            
            response = HttpResponse(png_data, content_type='image/png')
            response['Cache-Control'] = 'max-age=3600'
            return response
            
        except Exception as e:
            print(f"Error generating combined raster tile for {city_slug}: {e}")
            renderer = TileRenderingService()
            return HttpResponse(renderer.create_empty_tile(), content_type='image/png', status=500)

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

class MapVisualizationView(TemplateView):
    """Simple map visualization frontend"""
    template_name = 'maps/map.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add any context data you need
        context.update({
            'api_base_url': '/api',  # Adjust this if your API is at a different path
            'page_title': 'Geo Mapping Visualization'
        })
        
        return context
    
class CityCompleteView(APIView):
    """
    OPTIMAL: Return ALL city layers in one response with proper colors
    Perfect for "show entire city at once" use case
    """
    
    def get(self, request, city_slug):
        try:
            city = get_object_or_404(City, slug=city_slug, is_active=True)
            
            # Get layers and calculate total features
            layers = DataLayer.objects.filter(
                city=city,
                is_processed=True
            ).select_related('category').order_by('category__display_order', 'name')
            
            if not layers.exists():
                return Response({
                    'error': 'No layers found for this city',
                    'city': city_slug
                }, status=404)
            
            total_features = sum(layer.feature_count or 0 for layer in layers)
            
            # 🚀 ENHANCED STRATEGY SELECTION
            force_tiles = request.GET.get('force_tiles', 'false').lower() == 'true'
            force_geojson = request.GET.get('force_geojson', 'false').lower() == 'true'
            no_limits = request.GET.get('no_limits', 'false').lower() == 'true'
            
            # Strategy thresholds
            TILE_THRESHOLD = 100000    # Use tiles for 100k+ features
            PROGRESSIVE_THRESHOLD = 5000  # Use progressive for 5k+ features
            
            print(f"🎯 Strategy selection for {city_slug}: {total_features} features")
            print(f"   force_tiles={force_tiles}, force_geojson={force_geojson}")
            
            # Decision logic
            if force_tiles or (total_features > TILE_THRESHOLD and not force_geojson):
                print(f"✅ Using TILE strategy for {total_features} features")
                return self._get_tile_based_response(city, layers, total_features)
                
            elif force_geojson or no_limits:
                print(f"✅ Using COMPLETE GEOJSON strategy (forced)")
                return self._get_complete_geojson_response(city, layers, total_features, request)
                
            elif total_features > PROGRESSIVE_THRESHOLD:
                print(f"✅ Using PROGRESSIVE strategy for {total_features} features")
                return self._get_progressive_info_response(city, layers, total_features)
                
            else:
                print(f"✅ Using COMPLETE strategy for {total_features} features")
                return self._get_complete_geojson_response(city, layers, total_features, request)
            
        except Exception as e:
            print(f"Error in CityCompleteView: {e}")
            return Response({
                'error': 'Failed to load city data',
                'message': str(e)
            }, status=500)
        
    
    
    def _get_complete_geojson_response(self, city, layers, total_features, request=None):
        """Return all city layers as one combined GeoJSON - ENHANCED with no limits"""
        
        # Check for no limits parameter
        no_limits = request.GET.get('no_limits', 'false').lower() == 'true' if request else False
        
        if no_limits:
            max_features_per_layer = None  # ✅ No limit when no_limits=true
            print(f"🚨 NO LIMITS MODE: Loading ALL {total_features:,} features")
        else:
            max_features_per_layer = int(request.GET.get('max_per_layer', 5000)) if request else 5000
        
        all_features = []
        layer_metadata = []
        
        for layer in layers:
            try:
                # Get features for this layer
                features_query = GeoFeature.objects.filter(
                    layer=layer,
                    is_valid=True
                ).select_related('layer__category')
                
                # Apply limit only if not in no_limits mode
                if max_features_per_layer is not None:
                    features = features_query[:max_features_per_layer]
                    layer_feature_count = min(features_query.count(), max_features_per_layer)
                else:
                    features = features_query.all()  # ✅ Get ALL features
                    layer_feature_count = features_query.count()
                
                # Get layer color using enhanced method
                layer_color = self._get_layer_color(layer)
                
                # Add layer metadata
                layer_metadata.append({
                    'slug': layer.slug,
                    'name': layer.name,
                    'category': layer.category.name if layer.category else 'Unknown',
                    'category_code': layer.category.code if layer.category else None,
                    'color': layer_color,
                    'feature_count': layer_feature_count,
                    'total_available': features_query.count(),  # ✅ Show total available
                    'bbox': {
                        'min_lng': layer.bbox_xmin,
                        'min_lat': layer.bbox_ymin,
                        'max_lng': layer.bbox_xmax,
                        'max_lat': layer.bbox_ymax
                    } if all([layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax]) else None
                })
                
                print(f"   Processing {layer.name}: {layer_feature_count:,} features")
                
                # Convert features to GeoJSON
                for i, feature in enumerate(features):
                    try:
                        # Progress indicator for large datasets
                        if no_limits and i % 10000 == 0 and i > 0:
                            print(f"     Progress: {i:,}/{layer_feature_count:,} features")
                        
                        # ✅ PROPER GEOJSON CONVERSION
                        geometry = json.loads(feature.geometry.geojson)
                        
                        properties = {
                            'id': feature.id,
                            'name': feature.name or '',
                            'layer_slug': layer.slug,
                            'layer_name': layer.name,
                            'category': layer.category.name if layer.category else 'Unknown',
                            'category_code': layer.category.code if layer.category else None,
                            'land_use': feature.land_use_type or '',
                            'plu_code': feature.plu_primary_code or '',
                            'area': float(feature.calculated_area) if feature.calculated_area else 0.0,
                            'color': layer_color,
                            'city': city.slug
                        }
                        
                        all_features.append({
                            'type': 'Feature',
                            'geometry': geometry,
                            'properties': properties
                        })
                        
                    except Exception as e:
                        print(f"Skipping feature {feature.id}: {e}")
                        continue
                        
            except Exception as e:
                print(f"Error processing layer {layer.slug}: {e}")
                continue
        
        # Build complete response
        response_data = {
            'type': 'FeatureCollection',
            'strategy': 'complete_geojson',
            'city': {
                'slug': city.slug,
                'name': city.name,
                'center': [city.center_lat, city.center_lng]
            },
            'features': all_features,
            'metadata': {
                'total_features': len(all_features),
                'total_layers': len(layer_metadata),
                'layers': layer_metadata,
                'bounds': self._calculate_city_bounds(layers),
                'no_limits_mode': no_limits,  # ✅ Indicate mode
                'limited': not no_limits and len(all_features) < total_features,
                'max_per_layer': max_features_per_layer
            }
        }
        
        print(f"✅ Generated complete GeoJSON for {city.slug}: {len(all_features):,} features, {len(layer_metadata)} layers")
        
        # Longer cache for complete datasets
        cache_time = 7200 if no_limits else 1800  # 2 hours vs 30 minutes
        response = Response(response_data)
        response['Cache-Control'] = f'max-age={cache_time}'
        response['Access-Control-Allow-Origin'] = '*'
        
        return response
    
    def _get_tile_based_response(self, city, layers, total_features):
        """Return tile-based info for large datasets"""
        
        color_map = self._get_color_mapping()
        layer_info = []
        
        for layer in layers:
            layer_info.append({
                'slug': layer.slug,
                'name': layer.name,
                'category': layer.category.name if layer.category else 'Unknown',
                'color': self._get_layer_color(layer, color_map),
                'feature_count': layer.feature_count,
                'tile_url': f'/api/tiles/{city.slug}/{layer.slug}/{{z}}/{{x}}/{{y}}.mvt'
            })
        
        return Response({
            'strategy': 'tile_based',
            'reason': f'Large dataset ({total_features:,} features)',
            'city': city.slug,
            'combined_tile_url': f'/api/tiles/{city.slug}/combined/{{z}}/{{x}}/{{y}}.mvt',
            'layers': layer_info,
            'recommended_zoom': {'min': 10, 'max': 16},
            'bounds': self._calculate_city_bounds(layers)
        })
    
    def _get_color_mapping(self):
        """Return standardized color mapping for categories - matches your frontend"""
        return {
            # Bangalore colors (existing)
            'RESIDENTIAL': '#FFC400',      # Yellow - Residential
            'COMMERCIAL': '#004DA8',       # Blue - Commercial  
            'INDUSTRIAL': '#AA66B2',       # Purple - Industrial
            'HIGH_TECH': '#C29ED7',        # Light Purple - High Tech
            'PUBLIC': '#E60000',           # Red - Public/Semi Public
            'DEFENSE': '#8B4513',          # Brown - Defense
            'PROTECTED': '#228B22',        # Forest Green - State Forest/Protected
            'PARKS_GREEN': '#98E600',      # Bright Green - Parks and Green Spaces
            'WATER_BODIES': '#1E90FF',     # Dodger Blue - Lake/Tank
            'TRANSPORT': '#808080',        # Gray - Road/Rail/Airport Transport
            'UTILITIES': '#FF6347',        # Tomato - Power/Water/Utilities
            'AGRICULTURAL': '#9ACD32',     # Yellow Green - Agricultural Land
            'UNCLASSIFIED': '#D3D3D3',     # Light Gray - Unclassified Use
            'DRAINS': '#4682B4',           # Steel Blue - Drains
            
            # ✅ VIZAG COLORS (from your specifications)
            'MIXED_USE': '#FFAA00',        # Mixed Use Zone 1
            'GOVERNMENT': '#FF0000',       # Government facilities
            'EDUCATION': '#FF0000',        # Educational facilities  
            'HEALTHCARE': '#FF0000',       # Health facilities
            'CULTURAL': '#FF0000',         # Religious facilities
            'CEMETERY': '#FFFFFF',         # Crematorium/Burial grounds
            'HILLS': '#A87000',           # Brown Zone (Hills)
            'SPECIAL': '#FFFFFF',          # Special Area Use Zone
        }
    
    def _get_layer_color(self, layer, color_map=None):
        """Get color for a specific layer - FIXED for Vizag"""
        
        from .config import get_city_config
        
        # Priority 1: Use city-specific config colors
        city_config = get_city_config(layer.city.slug)
        if city_config and 'colors' in city_config:
            category_code = layer.category.code if layer.category else None
            if category_code and category_code in city_config['colors']:
                return city_config['colors'][category_code]
        
        # Priority 2: Try the passed color_map
        if color_map and layer.category and layer.category.code:
            category_color = color_map.get(layer.category.code.upper())
            if category_color:
                return category_color
        
        # Priority 3: Try layer style
        try:
            style = layer.get_style()
            if isinstance(style, dict) and style.get('fill_color'):
                return style['fill_color']
            elif hasattr(style, 'fill_color'):
                return style.fill_color
        except:
            pass
        
        # Priority 4: Category default color
        if layer.category and layer.category.default_color:
            return layer.category.default_color
        
        # Default fallback
        return '#666666'
    

    
    def _calculate_city_bounds(self, layers):
        """Calculate bounding box for all layers"""
        bounds = {
            'min_lng': float('inf'),
            'min_lat': float('inf'), 
            'max_lng': float('-inf'),
            'max_lat': float('-inf')
        }
        
        valid_bounds = False
        
        for layer in layers:
            if all([layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax]):
                bounds['min_lng'] = min(bounds['min_lng'], layer.bbox_xmin)
                bounds['min_lat'] = min(bounds['min_lat'], layer.bbox_ymin)
                bounds['max_lng'] = max(bounds['max_lng'], layer.bbox_xmax)
                bounds['max_lat'] = max(bounds['max_lat'], layer.bbox_ymax)
                valid_bounds = True
        
        return bounds if valid_bounds else None
    
    def _get_progressive_info_response(self, city, layers, total_features):
        """Return progressive loading info"""
        return Response({
            'strategy': 'progressive_loading',
            'reason': f'Medium dataset ({total_features:,} features)',
            'city': city.slug,
            'total_features': total_features,
            'recommended_chunk_size': 1000,
            'progressive_url': f'/api/cities/{city.slug}/progressive/',
            'layers': [{'slug': l.slug, 'name': l.name, 'feature_count': l.feature_count} for l in layers]
        })
    
class CoordinateSearchView(APIView):
    """
    Search for features containing a specific coordinate point
    Uses city-specific configuration for colors (NO HARDCODING)
    """
    
    def post(self, request, city_slug):
        try:
            # Get city
            city = get_object_or_404(City, slug=city_slug, is_active=True)
            
            # Parse coordinates from request
            data = request.data
            latitude = float(data.get('latitude', 0))
            longitude = float(data.get('longitude', 0))
            
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
                'summary': self._create_search_summary(containing_features, nearby_features)
            }
            
            return Response(response_data)
            
        except ValueError:
            return Response({
                'error': 'Invalid coordinate format',
                'message': 'Coordinates must be valid numbers'
            }, status=400)
        except Exception as e:
            print(f"Error in CoordinateSearchView: {e}")
            return Response({
                'error': 'Search failed',
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
                    'category_code': feature.layer.category.code if feature.layer.category else None,
                    'land_use': feature.land_use_type or '',
                    'plu_code': feature.plu_primary_code or '',
                    'area': float(feature.calculated_area) if feature.calculated_area else 0.0,
                    'color': layer_color,
                    'administrative_info': {
                        'state': feature.state or '',
                        'district': feature.district or '',
                        'village': feature.village or ''
                    }
                }
                
                containing_features.append(feature_data)
                
            except Exception as e:
                print(f"Error processing feature {feature.id}: {e}")
                continue
        
        return containing_features
    
    def _find_nearby_features(self, city, point, radius_meters=100):
        """Find features near the point if no exact match"""
        
        nearby_features = []
        
        # Create buffer around point (rough conversion to degrees)
        buffer_degrees = radius_meters / 111320  # Very rough conversion
        search_area = point.buffer(buffer_degrees)
        
        # Find intersecting features
        features = GeoFeature.objects.filter(
            layer__city=city,
            layer__is_processed=True,
            is_valid=True,
            geometry__intersects=search_area
        ).select_related('layer', 'layer__category')[:10]
        
        for feature in features:
            try:
                # Calculate distance (rough)
                distance = point.distance(feature.geometry) * 111320  # Convert to meters
                
                layer_color = self._get_feature_color_from_config(feature, city.slug)
                
                feature_data = {
                    'feature_id': feature.id,
                    'feature_name': feature.name or 'Unnamed',
                    'layer_name': feature.layer.name,
                    'category': feature.layer.category.name if feature.layer.category else 'Unknown',
                    'land_use': feature.land_use_type or '',
                    'color': layer_color,
                    'distance_meters': round(distance, 1)
                }
                
                nearby_features.append(feature_data)
                
            except Exception as e:
                print(f"Error processing nearby feature {feature.id}: {e}")
                continue
        
        # Sort by distance
        nearby_features.sort(key=lambda x: x['distance_meters'])
        
        return nearby_features
    
    def _get_feature_color_from_config(self, feature, city_slug):
        """
        Get color for a feature using the existing configuration system
        NO HARDCODING - uses city-specific config
        """
        
        try:
            # Method 1: Try to use the existing layer.get_style() method
            style = feature.layer.get_style()
            if isinstance(style, dict) and style.get('fill_color'):
                return style['fill_color']
            elif hasattr(style, 'fill_color'):
                return style.fill_color
        except Exception as e:
            print(f"Could not get style from layer.get_style(): {e}")
        
        try:
            # Method 2: Try to get CityLayerStyle directly
            if feature.layer.category:
                from .models import CityLayerStyle
                city_style = CityLayerStyle.objects.get(
                    city__slug=city_slug,
                    category=feature.layer.category
                )
                return city_style.fill_color
        except Exception as e:
            print(f"Could not get CityLayerStyle: {e}")
        
        try:
            # Method 3: Get color from city config
            city_config = get_city_config(city_slug)
            if city_config and 'colors' in city_config:
                if feature.layer.category and feature.layer.category.code:
                    category_code = feature.layer.category.code.upper()
                    if category_code in city_config['colors']:
                        return city_config['colors'][category_code]
        except Exception as e:
            print(f"Could not get color from city config: {e}")
        
        try:
            # Method 4: Fallback to category default color
            if feature.layer.category:
                return feature.layer.category.default_color
        except Exception as e:
            print(f"Could not get category default color: {e}")
        
        # Final fallback
        print(f"Using fallback color for feature {feature.id}")
        return '#666666'
    
    def _create_search_summary(self, containing_features, nearby_features):
        """Create human-readable summary of search results"""
        
        if containing_features:
            primary_feature = containing_features[0]  # Largest containing feature
            
            summary = f"This location is in {primary_feature['layer_name']}"
            
            if primary_feature['land_use']:
                summary += f" ({primary_feature['land_use']})"
            
            if primary_feature['administrative_info']['village']:
                summary += f", {primary_feature['administrative_info']['village']}"
            
            if len(containing_features) > 1:
                summary += f". Also overlaps with {len(containing_features) - 1} other features."
            
            return summary
            
        elif nearby_features:
            nearest = nearby_features[0]
            return f"No exact match. Nearest feature is {nearest['layer_name']} ({nearest['distance_meters']}m away)"
            
        else:
            return "No features found at this location"


# Also add a GET version for testing
class CoordinateSearchTestView(APIView):
    """Test version using GET parameters - FIXED VERSION"""
    
    def get(self, request, city_slug):
        try:
            # Get city
            city = get_object_or_404(City, slug=city_slug, is_active=True)
            
            # Get all layers for this city
            layers = DataLayer.objects.filter(
                city=city,
                is_processed=True
            ).select_related('category').order_by('category__display_order', 'name')
            
            if not layers.exists():
                return Response({
                    'error': 'No layers found for this city',
                    'city': city_slug
                }, status=404)
            
            # Calculate total features to decide response strategy
            total_features = sum(layer.feature_count or 0 for layer in layers)
            
            # ✅ CHECK FOR OVERRIDE PARAMETERS
            force_geojson = request.GET.get('force_geojson', 'false').lower() == 'true'
            max_features = int(request.GET.get('max_features', 100000))  # Configurable threshold
            
            # DECISION: Strategy based on dataset size and parameters
            if not force_geojson and total_features > max_features:
                return self._get_tile_based_response(city, layers, total_features)
            
            # Return complete GeoJSON (with size limits for safety)
            return self._get_complete_geojson_response(city, layers, total_features, request)
            
        except Exception as e:
            print(f"Error in CityCompleteView: {e}")
            return Response({
                'error': 'Failed to load city data',
                'message': str(e)
            }, status=500)

class CityProgressiveView(APIView):
    """
    🚀 PROGRESSIVE LOADING: Load city data in chunks
    Perfect for handling large datasets (1GB+ JSON files)
    """
    
    def get(self, request, city_slug):
        try:
            city = get_object_or_404(City, slug=city_slug, is_active=True)
            
            # Get pagination parameters
            chunk_size = int(request.GET.get('chunk_size', 1000))
            chunk_index = int(request.GET.get('chunk', 0))  # 0-based
            layer_slug = request.GET.get('layer')  # Optional: specific layer
            
            # Calculate offset
            offset = chunk_index * chunk_size
            
            print(f"🔄 Loading chunk {chunk_index}: features {offset}-{offset + chunk_size - 1}")
            
            # Get layers to process
            if layer_slug:
                layers = DataLayer.objects.filter(
                    city=city, 
                    slug=layer_slug,
                    is_processed=True
                )
            else:
                layers = DataLayer.objects.filter(
                    city=city,
                    is_processed=True
                ).order_by('category__display_order', 'name')
            
            if not layers.exists():
                return Response({
                    'error': 'No layers found',
                    'city': city_slug
                }, status=404)
            
            # Progressive loading logic
            chunk_data = self._load_progressive_chunk(
                city, layers, offset, chunk_size, chunk_index
            )
            
            return Response(chunk_data)
            
        except Exception as e:
            print(f"Error in CityProgressiveView: {e}")
            return Response({
                'error': 'Failed to load chunk',
                'message': str(e)
            }, status=500)
    
    def _load_progressive_chunk(self, city, layers, offset, chunk_size, chunk_index):
        """Load a specific chunk of features across all layers"""
        
        chunk_features = []
        total_available = 0
        layers_info = []
        
        # Get total count first (for progress calculation)
        for layer in layers:
            layer_total = GeoFeature.objects.filter(
                layer=layer,
                is_valid=True
            ).count()
            total_available += layer_total
            
            layers_info.append({
                'slug': layer.slug,
                'name': layer.name,
                'total_features': layer_total,
                'color': self._get_layer_color(layer, city.slug)
            })
        
        # Load features for this chunk (across all layers)
        features_query = GeoFeature.objects.filter(
            layer__city=city,
            layer__is_processed=True,
            is_valid=True
        ).select_related('layer', 'layer__category').order_by('id')
        
        # Apply pagination
        chunk_features_data = features_query[offset:offset + chunk_size]
        
        # Convert to GeoJSON
        for feature in chunk_features_data:
            try:
                geometry = json.loads(feature.geometry.geojson)
                layer_color = self._get_layer_color(feature.layer, city.slug)
                
                properties = {
                    'id': feature.id,
                    'name': feature.name or '',
                    'layer_slug': feature.layer.slug,
                    'layer_name': feature.layer.name,
                    'category': feature.layer.category.name if feature.layer.category else 'Unknown',
                    'category_code': feature.layer.category.code if feature.layer.category else None,
                    'land_use': feature.land_use_type or '',
                    'plu_code': feature.plu_primary_code or '',
                    'area': float(feature.calculated_area) if feature.calculated_area else 0.0,
                    'color': layer_color,
                    'city': city.slug
                }
                
                chunk_features.append({
                    'type': 'Feature',
                    'geometry': geometry,
                    'properties': properties
                })
                
            except Exception as e:
                print(f"Skipping feature {feature.id}: {e}")
                continue
        
        # Calculate progress info
        features_loaded = len(chunk_features)
        is_last_chunk = (offset + chunk_size) >= total_available
        progress_percentage = min(((chunk_index + 1) * chunk_size / total_available) * 100, 100)
        
        return {
            'type': 'FeatureCollection',
            'strategy': 'progressive_loading',
            'chunk_info': {
                'chunk_index': chunk_index,
                'chunk_size': chunk_size,
                'features_in_chunk': features_loaded,
                'offset': offset,
                'is_last_chunk': is_last_chunk,
                'progress_percentage': round(progress_percentage, 1)
            },
            'city': {
                'slug': city.slug,
                'name': city.name,
                'center': [city.center_lat, city.center_lng]
            },
            'features': chunk_features,
            'metadata': {
                'total_available_features': total_available,
                'total_layers': len(layers_info),
                'layers': layers_info,
                'bounds': self._calculate_city_bounds(layers) if chunk_index == 0 else None
            }
        }
    
    def _get_layer_color(self, layer, city_slug):
        """Get color for a layer using existing configuration system"""
        try:
            from .config import get_city_config
            city_config = get_city_config(city_slug)
            if city_config and 'colors' in city_config:
                category_code = layer.category.code if layer.category else None
                if category_code and category_code in city_config['colors']:
                    return city_config['colors'][category_code]
            
            # Try city-specific style
            try:
                style = layer.get_style()
                if isinstance(style, dict):
                    return style.get('fill_color', '#666666')
                elif hasattr(style, 'fill_color'):
                    return style.fill_color
            except:
                pass
            
            # Fallback to category default
            if layer.category:
                return layer.category.default_color
            
            return '#666666'
        except Exception as e:
            print(f"Error getting layer color: {e}")
            return '#666666'
    
    def _calculate_city_bounds(self, layers):
        """Calculate city bounds from layers"""
        bounds = {
            'min_lng': float('inf'),
            'min_lat': float('inf'), 
            'max_lng': float('-inf'),
            'max_lat': float('-inf')
        }
        
        valid_bounds = False
        
        for layer in layers:
            if all([layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax]):
                bounds['min_lng'] = min(bounds['min_lng'], layer.bbox_xmin)
                bounds['min_lat'] = min(bounds['min_lat'], layer.bbox_ymin)
                bounds['max_lng'] = max(bounds['max_lng'], layer.bbox_xmax)
                bounds['max_lat'] = max(bounds['max_lat'], layer.bbox_ymax)
                valid_bounds = True
        
        return bounds if valid_bounds else None
    


class CachedCityCompleteView(APIView):
    """
    🚀 CACHED VERSION: Complete city data with intelligent caching
    - First load: Generates and caches data (may take time)
    - Subsequent loads: Instant from cache
    """
    
    def get(self, request, city_slug):
        start_time = time.time()
        
        try:
            city = get_object_or_404(City, slug=city_slug, is_active=True)
            
            # Extract cache parameters
            cache_params = {
                'no_limits': request.GET.get('no_limits', 'false').lower() == 'true',
                'max_per_layer': request.GET.get('max_per_layer', '5000'),
                'force_geojson': request.GET.get('force_geojson', 'false').lower() == 'true',
                'force_tiles': request.GET.get('force_tiles', 'false').lower() == 'true'
            }
            
            # 🚀 CACHE CHECK: Try to get from cache first
            logger.info(f"🔍 Checking cache for {city_slug} with params: {cache_params}")
            cached_data = gis_cache.get_city_complete(city_slug, **cache_params)
            
            if cached_data:
                # ⚡ CACHE HIT: Return instantly
                cache_time = time.time() - start_time
                logger.info(f"⚡ CACHE HIT! Loaded {city_slug} in {cache_time:.3f}s")
                
                # Add cache metadata to response
                cached_data['cache_info'] = {
                    'cache_hit': True,
                    'load_time_seconds': round(cache_time, 3),
                    'loaded_from': 'cache'
                }
                
                response = Response(cached_data)
                response['X-Cache-Status'] = 'HIT'
                response['X-Load-Time'] = str(cache_time)
                return response
            
            # 💾 CACHE MISS: Generate data and cache it
            logger.info(f"💾 CACHE MISS for {city_slug}. Generating data...")
            
            # Get layers and calculate total features
            layers = DataLayer.objects.filter(
                city=city,
                is_processed=True
            ).select_related('category').order_by('category__display_order', 'name')
            
            if not layers.exists():
                return Response({
                    'error': 'No layers found for this city',
                    'city': city_slug
                }, status=404)
            
            total_features = sum(layer.feature_count or 0 for layer in layers)
            
            # 📊 STRATEGY SELECTION (same as original but with caching)
            TILE_THRESHOLD = 100000
            PROGRESSIVE_THRESHOLD = 5000
            
            logger.info(f"📊 Strategy selection: {total_features} features")
            
            if (cache_params['force_tiles'] or 
                (total_features > TILE_THRESHOLD and not cache_params['force_geojson'])):
                
                # Return tile-based response (no caching needed - tiles are cached separately)
                response_data = self._get_tile_based_response(city, layers, total_features)
                
            elif (cache_params['force_geojson'] or cache_params['no_limits'] or 
                  total_features <= PROGRESSIVE_THRESHOLD):
                
                # Generate complete GeoJSON and cache it
                response_data = self._get_complete_geojson_response(
                    city, layers, total_features, request
                )
                
                # 🔥 CACHE THE RESPONSE for future requests
                generation_time = time.time() - start_time
                logger.info(f"📦 Caching complete data for {city_slug} (took {generation_time:.1f}s)")
                
                cache_success = gis_cache.cache_city_complete(city_slug, response_data, **cache_params)
                
                response_data['cache_info'] = {
                    'cache_hit': False,
                    'load_time_seconds': round(generation_time, 3),
                    'loaded_from': 'database',
                    'cached_for_future': cache_success
                }
                
            else:
                # Progressive loading info
                response_data = self._get_progressive_info_response(city, layers, total_features)
            
            total_time = time.time() - start_time
            response = Response(response_data)
            response['X-Cache-Status'] = 'MISS'
            response['X-Load-Time'] = str(total_time)
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Error in CachedCityCompleteView: {e}")
            return Response({
                'error': 'Failed to load city data',
                'message': str(e)
            }, status=500)
    
    def _get_complete_geojson_response(self, city, layers, total_features, request):
        """Generate complete GeoJSON response (same as original but optimized)"""
        # This is the same logic as your original CityCompleteView._get_complete_geojson_response
        # but I'll add some optimizations
        
        no_limits = request.GET.get('no_limits', 'false').lower() == 'true'
        max_features_per_layer = None if no_limits else int(request.GET.get('max_per_layer', 5000))
        
        all_features = []
        layer_metadata = []
        
        logger.info(f"🔄 Processing {len(layers)} layers...")
        
        for i, layer in enumerate(layers):
            logger.info(f"   📂 [{i+1}/{len(layers)}] Processing {layer.name}...")
            
            try:
                # Get features for this layer
                features_query = GeoFeature.objects.filter(
                    layer=layer,
                    is_valid=True
                ).select_related('layer__category')
                
                if max_features_per_layer is not None:
                    features = features_query[:max_features_per_layer]
                    layer_feature_count = min(features_query.count(), max_features_per_layer)
                else:
                    features = features_query.all()
                    layer_feature_count = features_query.count()
                
                # Get layer color
                layer_color = self._get_layer_color(layer)
                
                # Add layer metadata
                layer_metadata.append({
                    'slug': layer.slug,
                    'name': layer.name,
                    'category': layer.category.name if layer.category else 'Unknown',
                    'category_code': layer.category.code if layer.category else None,
                    'color': layer_color,
                    'feature_count': layer_feature_count,
                    'total_available': features_query.count(),
                })
                
                # Convert features to GeoJSON with batch processing
                batch_size = 1000
                for batch_start in range(0, len(features), batch_size):
                    batch_features = features[batch_start:batch_start + batch_size]
                    
                    for feature in batch_features:
                        try:
                            import json
                            geometry = json.loads(feature.geometry.geojson)
                            
                            properties = {
                                'id': feature.id,
                                'name': feature.name or '',
                                'layer_slug': layer.slug,
                                'layer_name': layer.name,
                                'category': layer.category.name if layer.category else 'Unknown',
                                'category_code': layer.category.code if layer.category else None,
                                'land_use': feature.land_use_type or '',
                                'plu_code': feature.plu_primary_code or '',
                                'area': float(feature.calculated_area) if feature.calculated_area else 0.0,
                                'color': layer_color,
                                'city': city.slug
                            }
                            
                            all_features.append({
                                'type': 'Feature',
                                'geometry': geometry,
                                'properties': properties
                            })
                            
                        except Exception as e:
                            logger.warning(f"Skipping feature {feature.id}: {e}")
                            continue
                
                logger.info(f"   ✅ Processed {layer_feature_count:,} features")
                
            except Exception as e:
                logger.error(f"❌ Error processing layer {layer.slug}: {e}")
                continue
        
        # Build response
        response_data = {
            'type': 'FeatureCollection',
            'strategy': 'complete_geojson_cached',
            'city': {
                'slug': city.slug,
                'name': city.name,
                'center': [city.center_lat, city.center_lng]
            },
            'features': all_features,
            'metadata': {
                'total_features': len(all_features),
                'total_layers': len(layer_metadata),
                'layers': layer_metadata,
                'no_limits_mode': no_limits,
                'max_per_layer': max_features_per_layer,
                'generated_at': timezone.now().isoformat()
            }
        }
        
        logger.info(f"✅ Generated complete GeoJSON: {len(all_features):,} features, {len(layer_metadata)} layers")
        
        return response_data
    
    def _get_tile_based_response(self, city, layers, total_features):
        """Return tile-based response for large datasets"""
        layer_info = []
        
        for layer in layers:
            layer_info.append({
                'slug': layer.slug,
                'name': layer.name,
                'category': layer.category.name if layer.category else 'Unknown',
                'color': self._get_layer_color(layer),
                'feature_count': layer.feature_count,
                'tile_url': f'/api/tiles/{city.slug}/{layer.slug}/{{z}}/{{x}}/{{y}}.mvt'
            })
        
        return {
            'strategy': 'tile_based',
            'reason': f'Large dataset ({total_features:,} features)',
            'city': city.slug,
            'combined_tile_url': f'/api/tiles/{city.slug}/combined/{{z}}/{{x}}/{{y}}.mvt',
            'layers': layer_info,
            'recommended_zoom': {'min': 10, 'max': 16},
        }
    
    def _get_progressive_info_response(self, city, layers, total_features):
        """Return progressive loading info"""
        return {
            'strategy': 'progressive_loading',
            'reason': f'Medium dataset ({total_features:,} features)',
            'city': city.slug,
            'total_features': total_features,
            'recommended_chunk_size': 1000,
            'progressive_url': f'/api/cities/{city.slug}/progressive/',
            'layers': [{'slug': l.slug, 'name': l.name, 'feature_count': l.feature_count} for l in layers]
        }
    
    def _get_layer_color(self, layer):
        """Get color for a layer"""
        try:
            from .config import get_city_config
            city_config = get_city_config(layer.city.slug)
            if city_config and 'colors' in city_config:
                category_code = layer.category.code if layer.category else None
                if category_code and category_code in city_config['colors']:
                    return city_config['colors'][category_code]
            
            if layer.category:
                return layer.category.default_color
            return '#666666'
        except:
            return '#666666'

class CachedProgressiveView(APIView):
    """
    🚀 CACHED VERSION: Progressive loading with chunk-level caching
    """
    
    def get(self, request, city_slug):
        try:
            city = get_object_or_404(City, slug=city_slug, is_active=True)
            
            # Get pagination parameters
            chunk_size = int(request.GET.get('chunk_size', 1000))
            chunk_index = int(request.GET.get('chunk', 0))
            layer_slug = request.GET.get('layer')
            
            cache_params = {
                'chunk_size': chunk_size,
                'layer_slug': layer_slug or 'all'
            }
            
            # 🚀 CACHE CHECK: Try to get chunk from cache
            cached_chunk = gis_cache.get_progressive_chunk(city_slug, chunk_index, **cache_params)
            
            if cached_chunk:
                logger.info(f"⚡ CACHE HIT for chunk {chunk_index} of {city_slug}")
                cached_chunk['cache_info'] = {
                    'cache_hit': True,
                    'chunk_index': chunk_index
                }
                response = Response(cached_chunk)
                response['X-Cache-Status'] = 'HIT'
                return response
            
            # 💾 CACHE MISS: Generate chunk
            logger.info(f"💾 CACHE MISS for chunk {chunk_index} of {city_slug}")
            
            # Generate chunk data (use existing logic)
            chunk_data = self._load_progressive_chunk(city, chunk_index, chunk_size, layer_slug)
            
            # 🔥 CACHE THE CHUNK
            cache_success = gis_cache.cache_progressive_chunk(city_slug, chunk_index, chunk_data, **cache_params)
            
            chunk_data['cache_info'] = {
                'cache_hit': False,
                'chunk_index': chunk_index,
                'cached_for_future': cache_success
            }
            
            response = Response(chunk_data)
            response['X-Cache-Status'] = 'MISS'
            return response
            
        except Exception as e:
            logger.error(f"❌ Error in CachedProgressiveView: {e}")
            return Response({
                'error': 'Failed to load chunk',
                'message': str(e)
            }, status=500)
    
    def _load_progressive_chunk(self, city, chunk_index, chunk_size, layer_slug=None):
        """Load a specific chunk (same as original logic)"""
        # Implementation here matches your existing CityProgressiveView._load_progressive_chunk
        # but with optimizations
        
        offset = chunk_index * chunk_size
        
        # Get layers to process
        layers = DataLayer.objects.filter(city=city, is_processed=True)
        if layer_slug:
            layers = layers.filter(slug=layer_slug)
        
        chunk_features = []
        total_available = 0
        
        # Get features for this chunk
        features_query = GeoFeature.objects.filter(
            layer__city=city,
            layer__is_processed=True,
            is_valid=True
        ).select_related('layer', 'layer__category').order_by('id')
        
        total_available = features_query.count()
        chunk_features_data = features_query[offset:offset + chunk_size]
        
        # Convert to GeoJSON
        for feature in chunk_features_data:
            try:
                import json
                geometry = json.loads(feature.geometry.geojson)
                
                properties = {
                    'id': feature.id,
                    'name': feature.name or '',
                    'layer_slug': feature.layer.slug,
                    'category': feature.layer.category.name if feature.layer.category else 'Unknown',
                    'land_use': feature.land_use_type or '',
                    'area': float(feature.calculated_area) if feature.calculated_area else 0.0,
                    'city': city.slug
                }
                
                chunk_features.append({
                    'type': 'Feature',
                    'geometry': geometry,
                    'properties': properties
                })
                
            except Exception as e:
                logger.warning(f"Skipping feature {feature.id}: {e}")
                continue
        
        is_last_chunk = (offset + chunk_size) >= total_available
        progress_percentage = min(((chunk_index + 1) * chunk_size / total_available) * 100, 100)
        
        return {
            'type': 'FeatureCollection',
            'strategy': 'progressive_loading_cached',
            'chunk_info': {
                'chunk_index': chunk_index,
                'chunk_size': chunk_size,
                'features_in_chunk': len(chunk_features),
                'offset': offset,
                'is_last_chunk': is_last_chunk,
                'progress_percentage': round(progress_percentage, 1)
            },
            'city': {
                'slug': city.slug,
                'name': city.name,
            },
            'features': chunk_features,
            'metadata': {
                'total_available_features': total_available,
                'generated_at': timezone.now().isoformat()
            }
        }

class CacheManagementView(APIView):
    """
    🛠️ Cache Management API
    """
    
    def get(self, request, city_slug=None):
        """Get cache statistics"""
        if city_slug:
            stats = gis_cache.get_cache_stats(city_slug)
        else:
            # Get stats for all cities
            from .models import City
            cities = City.objects.filter(is_active=True)
            stats = {}
            for city in cities:
                stats[city.slug] = gis_cache.get_cache_stats(city.slug)
        
        return Response(stats)
    
    def post(self, request, city_slug):
        """Cache management operations"""
        action = request.data.get('action')
        
        if action == 'warm':
            # Warm cache for city
            force = request.data.get('force', False)
            result = gis_cache.warm_cache(city_slug, force=force)
            return Response(result)
            
        elif action == 'invalidate':
            # Invalidate cache for city
            deleted_count = gis_cache.invalidate_city_cache(city_slug)
            return Response({
                'status': 'success',
                'deleted_entries': deleted_count,
                'city': city_slug
            })
            
        else:
            return Response({
                'error': 'Invalid action',
                'valid_actions': ['warm', 'invalidate']
            }, status=400)

class SimpleMapView(TemplateView):
    template_name = 'maps/simple_map.html'

class MasterplanViewerView(TemplateView):
    """Masterplan viewer page with combined PNG tiles"""
    template_name = 'maps/masterplan_viewer.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Bangalore Masterplan Viewer',
            'api_base_url': '/api'
        })
        return context

class CityTileGenerationView(APIView):
    """
    🚀 Generate tiles for all layers of a city
    Provides sample URLs for testing after generation
    """
    
    def post(self, request, city_slug):
        try:
            # Get city
            city = get_object_or_404(City, slug=city_slug, is_active=True)
            
            # Get parameters
            min_zoom = int(request.data.get('min_zoom', 8))
            max_zoom = int(request.data.get('max_zoom', 14))
            force_regenerate = request.data.get('force', False)
            validate_after = request.data.get('validate', False)
            
            # Validate zoom levels
            if min_zoom < 0 or max_zoom > 18 or min_zoom > max_zoom:
                return Response({
                    'error': 'Invalid zoom levels',
                    'message': 'Zoom levels must be between 0-18 and min_zoom <= max_zoom'
                }, status=400)
            
            # Get layers to process
            layers = DataLayer.objects.filter(
                city=city,
                is_processed=True
            ).select_related('category')
            
            if not layers.exists():
                return Response({
                    'error': 'No processed layers found',
                    'city': city_slug
                }, status=404)
            
            # Initialize tile service
            tile_service = VectorTileService()
            
            # Process each layer
            results = []
            total_tiles_generated = 0
            successful_layers = 0
            failed_layers = 0
            
            start_time = time.time()
            
            for layer in layers:
                layer_result = {
                    'layer_slug': layer.slug,
                    'layer_name': layer.name,
                    'feature_count': layer.feature_count,
                    'status': 'pending'
                }
                
                try:
                    # Check if tiles already exist
                    try:
                        vector_tile_layer = VectorTileLayer.objects.get(layer=layer)
                        if vector_tile_layer.is_generated and not force_regenerate:
                            layer_result.update({
                                'status': 'existing',
                                'tiles_generated': vector_tile_layer.total_tiles,
                                'message': 'Tiles already exist'
                            })
                            successful_layers += 1
                            results.append(layer_result)
                            continue
                    except VectorTileLayer.DoesNotExist:
                        vector_tile_layer = None
                    
                    # Generate tiles
                    layer_start_time = time.time()
                    result = tile_service.generate_layer_tiles(layer, min_zoom, max_zoom)
                    layer_duration = time.time() - layer_start_time
                    
                    tiles_count = result.get('tiles_generated', 0)
                    
                    # Update or create vector tile layer record
                    if vector_tile_layer:
                        vector_tile_layer.min_zoom = min_zoom
                        vector_tile_layer.max_zoom = max_zoom
                        vector_tile_layer.is_generated = True
                        vector_tile_layer.total_tiles = tiles_count
                        vector_tile_layer.generated_at = timezone.now()
                        vector_tile_layer.save()
                    else:
                        VectorTileLayer.objects.create(
                            layer=layer,
                            min_zoom=min_zoom,
                            max_zoom=max_zoom,
                            is_generated=True,
                            total_tiles=tiles_count,
                            generated_at=timezone.now()
                        )
                    
                    # Update layer status
                    layer.tiles_generated = True
                    layer.save()
                    
                    layer_result.update({
                        'status': 'generated',
                        'tiles_generated': tiles_count,
                        'duration_seconds': round(layer_duration, 2),
                        'performance_tiles_per_second': round(tiles_count / layer_duration, 2) if layer_duration > 0 else 0
                    })
                    
                    total_tiles_generated += tiles_count
                    successful_layers += 1
                    
                except Exception as e:
                    failed_layers += 1
                    layer_result.update({
                        'status': 'failed',
                        'error': str(e),
                        'tiles_generated': 0
                    })
                
                results.append(layer_result)
            
            # Calculate total time
            total_duration = time.time() - start_time
            
            # Generate sample URLs
            sample_urls = self._generate_sample_urls(city_slug, results, min_zoom, max_zoom)
            
            # Build response
            response_data = {
                'city': {
                    'slug': city_slug,
                    'name': city.name
                },
                'generation_config': {
                    'min_zoom': min_zoom,
                    'max_zoom': max_zoom,
                    'force_regenerate': force_regenerate
                },
                'summary': {
                    'total_layers': len(results),
                    'successful_layers': successful_layers,
                    'failed_layers': failed_layers,
                    'total_tiles_generated': total_tiles_generated,
                    'total_duration_seconds': round(total_duration, 2),
                    'average_tiles_per_second': round(total_tiles_generated / total_duration, 2) if total_duration > 0 else 0
                },
                'layer_results': results,
                'sample_urls': sample_urls,
                'next_steps': [
                    f'Test individual tiles: GET /api/tiles/{city_slug}/{{layer}}/{{z}}/{{x}}/{{y}}.mvt',
                    f'Test combined tiles: GET /api/tiles/{city_slug}/combined/{{z}}/{{x}}/{{y}}.mvt',
                    f'View city layers: GET /api/cities/{city_slug}/layers/',
                    f'Get complete city data: GET /api/cities/{city_slug}/complete/'
                ]
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': 'Tile generation failed',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _generate_sample_urls(self, city_slug, layer_results, min_zoom, max_zoom):
        """Generate sample URLs for testing the generated tiles"""
        
        # Get city center coordinates
        try:
            city = City.objects.get(slug=city_slug)
            if city.center_lat and city.center_lng:
                center_lat, center_lng = city.center_lat, city.center_lng
            else:
                # Fallback coordinates
                center_lat, center_lng = 12.9716, 77.5946
        except:
            center_lat, center_lng = 12.9716, 77.5946
        
        # Generate sample tile coordinates
        sample_zooms = [min_zoom, (min_zoom + max_zoom) // 2, max_zoom]
        sample_urls = {
            'individual_layers': {},
            'combined_tiles': [],
            'test_coordinates': []
        }
        
        for zoom in sample_zooms:
            # Get tile coordinates for the center point
            tile = mercantile.tile(center_lng, center_lat, zoom)
            
            # Individual layer tiles
            for result in layer_results:
                if result['status'] in ['generated', 'existing'] and result['tiles_generated'] > 0:
                    layer_slug = result['layer_slug']
                    if layer_slug not in sample_urls['individual_layers']:
                        sample_urls['individual_layers'][layer_slug] = []
                    
                    sample_urls['individual_layers'][layer_slug].append({
                        'zoom': zoom,
                        'coordinates': f'{tile.z}/{tile.x}/{tile.y}',
                        'url': f'/api/tiles/{city_slug}/{layer_slug}/{tile.z}/{tile.x}/{tile.y}.mvt',
                        'png_url': f'/api/tiles/{city_slug}/{layer_slug}/{tile.z}/{tile.x}/{tile.y}.png'
                    })
            
            # Combined tiles
            sample_urls['combined_tiles'].append({
                'zoom': zoom,
                'coordinates': f'{tile.z}/{tile.x}/{tile.y}',
                'mvt_url': f'/api/tiles/{city_slug}/combined/{tile.z}/{tile.x}/{tile.y}.mvt',
                'png_url': f'/api/tiles/{city_slug}/combined/{tile.z}/{tile.x}/{tile.y}.png'
            })
        
        # Additional test coordinates
        additional_coords = [
            (12.9716, 77.5946, 12),  # Bangalore center
            (12.9716, 77.5946, 10),  # Lower zoom
            (12.9716, 77.5946, 14),  # Higher zoom
        ]
        
        for lat, lng, z in additional_coords:
            tile = mercantile.tile(lng, lat, z)
            sample_urls['test_coordinates'].append({
                'lat': lat,
                'lng': lng,
                'zoom': z,
                'tile_coordinates': f'{z}/{tile.x}/{tile.y}'
            })
        
        return sample_urls

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
            
            # Try to serve pre-generated tile first
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
        
        # Create MVT layers
        mvt_layers = {}
        
        if plots.exists():
            mvt_layers['plots'] = self.prepare_features_for_mvt(plots, Plot)
        
        if lands.exists():
            mvt_layers['lands'] = self.prepare_features_for_mvt(lands, Land)
        
        if mvt_layers:
            return mapbox_vector_tile.encode(mvt_layers)
        
        return None

    def features_to_mvt(self, features, layer_name, model):
        """Convert features to MVT"""
        mvt_features = self.prepare_features_for_mvt(features, model)
        
        if mvt_features:
            mvt_layers = {layer_name: mvt_features}
            return mapbox_vector_tile.encode(mvt_layers)
        
        return None

    def prepare_features_for_mvt(self, features, model):
        """Prepare features for MVT encoding"""
        mvt_features = []
        
        for feature in features:
            try:
                coords = [feature.location.x, feature.location.y]
                
                if model == Plot:
                    properties = {
                        'id': feature.plot_id,
                        'title': feature.marker_title,
                        'marker_id': feature.marker_id,
                        'area_sq_yards': feature.area_sq_yards or 0,
                        'price_per_sq_yard': feature.price_per_sq_yard or 0,
                        'total_price': feature.total_price or 0,
                        'type': 'plot'
                    }
                else:  # Land
                    properties = {
                        'id': feature.land_id,
                        'title': feature.marker_title,
                        'marker_id': feature.marker_id,
                        'area_text': feature.area_text,
                        'price_text': feature.price_text,
                        'type': 'land'
                    }
                
                mvt_feature = {
                    'geometry': {
                        'type': 'Point',
                        'coordinates': coords
                    },
                    'properties': properties
                }
                
                mvt_features.append(mvt_feature)
                
            except Exception:
                continue
        
        return {
            'features': mvt_features,
            'extent': 4096,
            'version': 2
        }

    def get_tile_bounds(self, z, x, y):
        """Get tile bounding box as Polygon"""
        bounds = mercantile.bounds(x, y, z)
        return Polygon.from_bbox([
            bounds.west, bounds.south,
            bounds.east, bounds.north
        ])

class RealEstateRasterTileView(APIView):
    """
    Serve PNG tiles for real estate data
    URL: /api/real-estate-tiles/{type}/{z}/{x}/{y}.png
    type: plots, lands, or combined
    """
    
    def get(self, request, tile_type, z, x, y):
        try:
            z, x, y = int(z), int(x), int(y)
            
            # Try to serve pre-generated tile first
            tile_path = Path('media/real_estate_tiles_png') / tile_type / str(z) / str(x) / f'{y}.png'
            
            if tile_path.exists():
                return FileResponse(
                    open(tile_path, 'rb'), 
                    content_type='image/png'
                )
            
            # Generate tile on-the-fly if not pre-generated
            if tile_type == 'plots':
                png_data = self.generate_plot_png_tile(z, x, y)
            elif tile_type == 'lands':
                png_data = self.generate_land_png_tile(z, x, y)
            elif tile_type == 'combined':
                png_data = self.generate_combined_png_tile(z, x, y)
            else:
                return HttpResponse('Invalid tile type', status=404)
            
            if png_data:
                response = HttpResponse(png_data, content_type='image/png')
                response['Cache-Control'] = 'max-age=3600'
                response['Access-Control-Allow-Origin'] = '*'
                return response
            
            # Return empty tile
            return HttpResponse(self.create_empty_tile(), content_type='image/png')
            
        except Exception as e:
            print(f"Error in RealEstateRasterTileView: {e}")
            return HttpResponse(self.create_empty_tile(), content_type='image/png', status=500)

    def generate_plot_png_tile(self, z, x, y):
        """Generate PNG tile for plots"""
        tile_bounds = self.get_tile_bounds(z, x, y)
        
        plots = Plot.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        )
        
        if not plots.exists():
            return self.create_empty_tile()
        
        max_features = 50 if z < 10 else 200 if z < 12 else 1000
        plots = plots[:max_features]
        
        return self.render_features_to_png(plots, Plot, z, x, y)

    def generate_land_png_tile(self, z, x, y):
        """Generate PNG tile for lands"""
        tile_bounds = self.get_tile_bounds(z, x, y)
        
        lands = Land.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        )
        
        if not lands.exists():
            return self.create_empty_tile()
        
        max_features = 50 if z < 10 else 200 if z < 12 else 1000
        lands = lands[:max_features]
        
        return self.render_features_to_png(lands, Land, z, x, y)

    def generate_combined_png_tile(self, z, x, y):
        """Generate combined PNG tile"""
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
            return self.create_empty_tile()
        
        max_features = 25 if z < 10 else 100 if z < 12 else 500
        plots = plots[:max_features]
        lands = lands[:max_features]
        
        return self.render_combined_features_to_png(plots, lands, z, x, y)

    def render_features_to_png(self, features, model, z, x, y):
        """Render features to PNG image"""
        tile_size = 256
        img = Image.new('RGBA', (tile_size, tile_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        bounds = mercantile.bounds(x, y, z)
        
        # Define colors
        if model == Plot:
            color = (255, 120, 0, 200)  # Orange
            outline_color = (255, 120, 0, 255)
        else:  # Land
            color = (0, 255, 0, 200)   # Green
            outline_color = (0, 255, 0, 255)
        
        # Draw features
        for feature in features:
            try:
                pixel_x, pixel_y = self.latlng_to_pixel(
                    feature.location.y, feature.location.x,
                    bounds, tile_size
                )
                
                radius = 6 if z < 12 else 8 if z < 14 else 10
                
                draw.ellipse(
                    [pixel_x - radius, pixel_y - radius, 
                     pixel_x + radius, pixel_y + radius],
                    fill=color,
                    outline=outline_color,
                    width=2
                )
                
            except Exception:
                continue
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        return buffer.getvalue()

    def render_combined_features_to_png(self, plots, lands, z, x, y):
        """Render combined features to PNG"""
        tile_size = 256
        img = Image.new('RGBA', (tile_size, tile_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        bounds = mercantile.bounds(x, y, z)
        
        # Draw lands first (background)
        for land in lands:
            try:
                pixel_x, pixel_y = self.latlng_to_pixel(
                    land.location.y, land.location.x,
                    bounds, tile_size
                )
                
                radius = 8 if z < 12 else 10 if z < 14 else 12
                
                draw.ellipse(
                    [pixel_x - radius, pixel_y - radius, 
                     pixel_x + radius, pixel_y + radius],
                    fill=(0, 255, 0, 180),
                    outline=(0, 180, 0, 255),
                    width=2
                )
                
            except Exception:
                continue
        
        # Draw plots on top
        for plot in plots:
            try:
                pixel_x, pixel_y = self.latlng_to_pixel(
                    plot.location.y, plot.location.x,
                    bounds, tile_size
                )
                
                radius = 6 if z < 12 else 8 if z < 14 else 10
                
                draw.ellipse(
                    [pixel_x - radius, pixel_y - radius, 
                     pixel_x + radius, pixel_y + radius],
                    fill=(255, 120, 0, 200),
                    outline=(255, 120, 0, 255),
                    width=2
                )
                
            except Exception:
                continue
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        return buffer.getvalue()

    def latlng_to_pixel(self, lat, lng, bounds, tile_size):
        """Convert lat/lng to pixel coordinates"""
        x_ratio = (lng - bounds.west) / (bounds.east - bounds.west)
        y_ratio = (bounds.north - lat) / (bounds.north - bounds.south)
        
        pixel_x = int(x_ratio * tile_size)
        pixel_y = int(y_ratio * tile_size)
        
        return pixel_x, pixel_y

    def create_empty_tile(self):
        """Create transparent empty tile"""
        img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        buffer = io.BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        return buffer.getvalue()

    def get_tile_bounds(self, z, x, y):
        """Get tile bounding box as Polygon"""
        bounds = mercantile.bounds(x, y, z)
        return Polygon.from_bbox([
            bounds.west, bounds.south,
            bounds.east, bounds.north
        ])