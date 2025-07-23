# urls.py
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
router.register(r'import-jobs', views.ImportJobViewSet)
router.register(r'plots', PlotViewSet)
router.register(r'lands', LandViewSet)

urlpatterns = [
    path('map/', views.MapVisualizationView.as_view(), name='map_visualization'),
    
    # Router URLs (REST API endpoints)
    path('', include(router.urls)),
    
    # Your existing tile URLs...
    path('tiles/<slug:city_slug>/combined/<int:z>/<int:x>/<int:y>.png',
         views.CombinedRasterTileView.as_view(), name='combined_raster_tile'),
    
    path('tiles/<slug:city_slug>/<slug:layer_slug>/<int:z>/<int:x>/<int:y>.png', 
         views.RasterTileView.as_view(), name='raster_tile'),
    
    path('tiles/<slug:city_slug>/combined/<int:z>/<int:x>/<int:y>.mvt',
         views.CombinedVectorTileView.as_view(), name='combined_tile'),
         
    path('tiles/<slug:city_slug>/<slug:layer_slug>/<int:z>/<int:x>/<int:y>.mvt', 
         views.VectorTileView.as_view(), name='vector_tile'),
    
    # Your existing layer URLs...
    path('cities/<slug:city_slug>/layers/', 
         views.CityLayersView.as_view(), name='city_layers'),
    
    path('cities/<slug:city_slug>/layers/<slug:layer_slug>/features/',
         views.LayerFeaturesView.as_view(), name='layer_features'),
    
    path('cities/<slug:city_slug>/complete/',
         views.CityCompleteView.as_view(), name='city_complete'),
    
    # 🚀 NEW COORDINATE SEARCH ENDPOINTS
    path('cities/<slug:city_slug>/search-coords/',
         views.CoordinateSearchView.as_view(), name='coordinate_search'),
    
    # Optional: GET version for testing
    path('cities/<slug:city_slug>/search-coords-test/',
         views.CoordinateSearchTestView.as_view(), name='coordinate_search_test'),
    
    # Rest of your existing URLs...
    path('layers/<int:pk>/plu-analysis/',
         views.DataLayerViewSet.as_view({'get': 'plu_analysis'}), name='layer_plu_analysis'),
    
    path('config/cities/', 
         views.CityConfigView.as_view(), name='city_config'),
    
    path('config/<slug:city_slug>/', 
         views.CityConfigDetailView.as_view(), name='city_config_detail'),
    
    path('import/', 
         views.DataImportView.as_view(), name='data_import'),
    
    path('layers/<int:pk>/generate-tiles/',
         views.DataLayerViewSet.as_view({'post': 'generate_tiles'}), name='generate_layer_tiles'),
    
    path('setup/cities/', 
         views.SetupCitiesView.as_view(), name='setup_cities'),

     path('cities/<slug:city_slug>/progressive/',
         views.CityProgressiveView.as_view(), name='city_progressive'),
         
    # Cached endpoints (add these)
    path('cities/<slug:city_slug>/complete-cached/',
         views.CachedCityCompleteView.as_view(), name='city_complete_cached'),

    path('cities/<slug:city_slug>/progressive-cached/',
         views.CachedProgressiveView.as_view(), name='city_progressive_cached'),

    path('cache/manage/<slug:city_slug>/',
         views.CacheManagementView.as_view(), name='cache_management'),

    path('cache/stats/',
         views.CacheManagementView.as_view(), name='cache_stats'),

    # 🚀 NEW: City tile generation endpoint
    path('cities/<slug:city_slug>/generate-tiles/',
         views.CityTileGenerationView.as_view(), name='city_tile_generation'),

    path('maps/simple/', SimpleMapView.as_view(), name='simple_map'),
    
    # 🏙️ NEW: Masterplan viewer page
    path('maps/masterplan/', views.MasterplanViewerView.as_view(), name='masterplan_viewer'),
    path('api/static-tiles/<slug:city_slug>/<slug:layer_slug>/<int:z>/<int:x>/<int:y>.mvt', StaticVectorTileView.as_view(), name='static-vector-tile'),

    # Add new endpoints
    path('states/<slug:state_slug>/cities/',
         views.StateCitiesView.as_view(), name='state_cities'),
    
    path('cities/<slug:city_slug>/layer-groups/',
         views.CityLayerGroupsView.as_view(), name='city_layer_groups'),
    
    path('layer-groups/<slug:group_slug>/layers/',
         views.LayerGroupLayersView.as_view(), name='layer_group_layers'),

     path('layer-config/', views.LayerConfigAPIView.as_view(), name='layer_config'),
     path('states/<slug:state_slug>/layer-config/', views.StateLayerConfigView.as_view(), name='state_layer_config'),
     path('cities/<slug:city_slug>/layer-config/', views.CityLayerConfigView.as_view(), name='city_layer_config'),
     path('layer-config/<slug:layer_slug>/', views.LayerConfigDetailView.as_view(), name='layer_config_detail'),

     path('real-estate-tiles/<str:tile_type>/<int:z>/<int:x>/<int:y>.mvt',
         RealEstateVectorTileView.as_view(), name='real_estate_vector_tile'),
         
     path('real-estate-tiles/<str:tile_type>/<int:z>/<int:x>/<int:y>.png',
         RealEstateRasterTileView.as_view(), name='real_estate_raster_tile'),

]
# Plots APIs:

# GET /api/plots/ - All plots
# GET /api/plots/in_bbox/?bbox=77.0,17.0,78.0,18.0 - Plots in bounding box
# GET /api/plots/near_point/?lat=17.31&lng=77.91&radius_km=5 - Plots near point

# Lands APIs:

# GET /api/lands/ - All lands
# GET /api/lands/in_bbox/?bbox=77.0,17.0,78.0,18.0 - Lands in bounding box
# GET /api/lands/near_point/?lat=18.01&lng=78.41&radius_km=10 - Lands near poin