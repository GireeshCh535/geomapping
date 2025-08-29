# maps/urls.py - Clean API endpoints

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import *

# Create router for viewsets
router = DefaultRouter()
router.register(r'states', views.StateViewSet)
router.register(r'cities', views.CityViewSet)
router.register(r'categories', views.LayerCategoryViewSet)
router.register(r'layer-groups', views.LayerGroupViewSet)
router.register(r'layers', views.DataLayerViewSet)
router.register(r'features', views.GeoFeatureViewSet)


urlpatterns = [
    
    # Router URLs (REST API endpoints)
    path('', include(router.urls)),
    
    # ================================
    # ENHANCED HIERARCHY AND TILE APIS
    # ================================
    
    # Get complete hierarchy with one API call
    path('hierarchy/',
         views.CompleteHierarchyAPIView.as_view(),
         name='complete_hierarchy_api'),
    
    # CloudFront tile serving with hierarchical structure
    path('tiles/<slug:state_slug>/<slug:city_slug>/<slug:layer_slug>/<int:z>/<int:x>/<int:y>.png',
         views.CloudFrontTileView.as_view(),
         name='cloudfront_tile_png'),
    
    # MVT tiles via CloudFront
    path('tiles/<slug:state_slug>/<slug:city_slug>/<slug:layer_slug>/<int:z>/<int:x>/<int:y>.mvt',
         views.CloudFrontTileView.as_view(),
         name='cloudfront_tile_mvt'),
    
    path('cities/<slug:city_slug>/tiles/coordinates/',
         TileCoordinatesView.as_view(), name='tile_coordinates'),
    
    path('cities/<slug:city_slug>/tiles/available/',
         AvailableTilesView.as_view(), name='available_tiles'),
    
    path('cities/<slug:city_slug>/search-coords-test/',
         views.CoordinateSearchTestView.as_view(), name='coordinate_search_test'),
    
    # Global coordinate search (across all states/cities)
    path('search-coords-test/',
         views.CoordinateSearchTestView.as_view(), name='global_coordinate_search_test'),
    
    # Layer bounds API - Get bounds for a specific layer based on actual data
    path('layers/<slug:state_slug>/<slug:city_slug>/<slug:layer_slug>/bounds/',
         views.LayerBoundsAPIView.as_view(), name='layer_bounds'),
    
    # ================================
    # SPECIAL COMBINED TILE ENDPOINTS
    # ================================
    
    # Hyderabad Future City combined tiles (boundary + geotiff)
    path('tiles/telangana/hyderabad/hyderabad_future_city/<int:z>/<int:x>/<int:y>.png',
         views.HyderabadFutureCityCombinedTileView.as_view(),
         name='hyderabad_future_city_combined_tile'),
    
]