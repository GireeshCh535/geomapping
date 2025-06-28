from django.shortcuts import get_object_or_404
from django.http import HttpResponse
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

from .models import (
    City, LayerCategory, DataLayer, GeoFeature, VectorTileLayer, 
    PLUCodeMapping, ImportJob
)
from .serializers import (
    CitySerializer, LayerCategorySerializer, DataLayerSerializer, 
    GeoFeatureSerializer, PLUCodeMappingSerializer, ImportJobSerializer
)
from .services import DataImportService, VectorTileService
from .config import get_city_config, get_plu_mapping

class CityViewSet(viewsets.ReadOnlyModelViewSet):
    """Enhanced city viewset with PLU information"""
    queryset = City.objects.annotate(
        layer_count=Count('layers'),
        total_features=Count('layers__features')
    ).filter(is_active=True)
    serializer_class = CitySerializer
    lookup_field = 'slug'

    @action(detail=True, methods=['get'])
    def statistics(self, request, slug=None):  # Keep as 'slug'
        """Get detailed city statistics"""
        city = self.get_object()  # This works with DRF router
        
        # Rest of your method stays the same...
        layers = DataLayer.objects.filter(city=city)
        layer_stats = {
            'total_layers': layers.count(),
            'processed_layers': layers.filter(is_processed=True).count(),
            'layers_with_tiles': layers.filter(tiles_generated=True).count(),
        }
        
        features = GeoFeature.objects.filter(layer__city=city)
        feature_stats = {
            'total_features': features.count(),
            'valid_features': features.filter(is_valid=True).count(),
            'features_with_plu': features.exclude(
                Q(plu_primary_code='') | Q(plu_primary_code__isnull=True)
            ).count(),
        }
        
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
        """Get PLU mappings for a city"""
        city = self.get_object()  # This works with DRF router
        
        mappings = PLUCodeMapping.objects.filter(city=city).select_related('mapped_category')
        serializer = PLUCodeMappingSerializer(mappings, many=True)
        
        return Response({
            'city': city.name,
            'total_mappings': mappings.count(),
            'mappings': serializer.data
        })


class LayerCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LayerCategory.objects.filter(is_active=True)
    serializer_class = LayerCategorySerializer
    lookup_field = 'code'

class DataLayerViewSet(viewsets.ReadOnlyModelViewSet):
    """Enhanced data layer viewset"""
    queryset = DataLayer.objects.select_related('city', 'category').filter(
        is_processed=True
    )
    serializer_class = DataLayerSerializer
    filterset_fields = ['city__slug', 'category__code', 'file_format', 'categorization_method']

    @action(detail=True, methods=['get'])
    def plu_analysis(self, request, pk=None):
        """Get PLU code analysis for a layer"""
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
        """Generate vector tiles for this layer"""
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
    """Enhanced geo feature viewset with PLU support"""
    queryset = GeoFeature.objects.select_related('layer', 'layer__city', 'layer__category')
    serializer_class = GeoFeatureSerializer
    filterset_fields = [
        'layer__slug', 'derived_category', 'land_use_type', 
        'plu_primary_code', 'plu_authority', 'is_valid'
    ]

    def get_queryset(self):
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
    """RESTORED - Original vector tile serving (should work without errors)"""
    
    def get(self, request, city_slug, layer_slug, z, x, y):
        try:
            # Get layer
            layer = get_object_or_404(
                DataLayer, 
                city__slug=city_slug, 
                slug=layer_slug,
                is_processed=True
            )
            
            # Generate tile using your existing service
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
    """RESTORED - Original combined vector tiles"""
    
    def get(self, request, city_slug, z, x, y):
        try:
            # Get all layers for city
            layers = DataLayer.objects.filter(
                city__slug=city_slug,
                is_processed=True
            ).select_related('category')
            
            # Filter layers if specified
            layer_slugs = request.GET.getlist('layers')
            if layer_slugs:
                layers = layers.filter(slug__in=layer_slugs)
            
            categories = request.GET.getlist('categories')
            if categories:
                layers = layers.filter(category__code__in=categories)
            
            # Generate combined tile
            tile_service = VectorTileService()
            mvt_data = tile_service.generate_combined_tile(layers, z, x, y)
            
            if mvt_data:
                response = HttpResponse(mvt_data, content_type='application/vnd.mapbox-vector-tile')
                response['Cache-Control'] = 'max-age=3600'
                response['Access-Control-Allow-Origin'] = '*'
                return response
            
            return HttpResponse(b'', content_type='application/vnd.mapbox-vector-tile')
            
        except Exception as e:
            print(f"Error in CombinedVectorTileView: {e}")
            return HttpResponse(b'', content_type='application/vnd.mapbox-vector-tile', status=500)

class CityLayersView(APIView):
    """Enhanced city layers view with filtering"""
    
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
        
        serializer = DataLayerSerializer(layers, many=True)
        
        return Response({
            'city': city_slug,
            'total_layers': layers.count(),
            'layers': serializer.data
        })

class LayerFeaturesView(APIView):
    """Enhanced layer features view with proper GeoJSON serialization"""
    
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
            # Get layers for city
            layers = DataLayer.objects.filter(
                city__slug=city_slug, 
                is_processed=True
            ).select_related('category')
            
            # Use VectorTileService to get combined MVT
            vector_service = VectorTileService()
            mvt_data = vector_service.generate_combined_tile(layers, z, x, y)
            
            if not mvt_data:
                renderer = TileRenderingService()
                return HttpResponse(renderer.create_empty_tile(), content_type='image/png')
            
            # Use TileRenderingService to convert MVT to PNG
            renderer = TileRenderingService()
            png_data = renderer.combined_mvt_to_png(mvt_data, layers, z, x, y)
            
            # Return PNG response
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
                return self._get_enhanced_tile_response(city, layers, total_features)
                
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
            'RESIDENTIAL': '#FFC400',      # Yellow - Residential
            'COMMERCIAL': '#004DA8',       # Blue - Commercial  
            'MIXED_USE': '#F7931E',        # Orange - Mixed Use
            'INDUSTRIAL': '#AA66B2',       # Purple - Industrial
            'HIGH_TECH': '#C29ED7',        # Light Purple - High Tech
            'GOVERNMENT': '#E60000',       # Red - Government
            'PUBLIC': '#E60000',           # Red - Public/Semi Public
            'DEFENSE': '#8B4513',          # Brown - Defense
            'PROTECTED': '#228B22',        # Forest Green - State Forest/Protected
            'PARKS_GREEN': '#98E600',      # Bright Green - Parks and Green Spaces
            'WATER_BODIES': '#1E90FF',     # Dodger Blue - Lake/Tank
            'TRANSPORT': '#808080',        # Gray - Road/Rail/Airport Transport
            'UTILITIES': '#FF6347',        # Tomato - Power/Water/Utilities
            'AGRICULTURAL': '#9ACD32',     # Yellow Green - Agricultural Land
            'UNCLASSIFIED': '#D3D3D3',     # Light Gray - Unclassified Use
            'DRAINS': '#4682B4'            # Steel Blue - Drains
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
    
    def _get_color_mapping(self):
        """Return standardized color mapping for categories - INCLUDES VIZAG"""
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
    
