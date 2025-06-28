# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for viewsets
router = DefaultRouter()
router.register(r'cities', views.CityViewSet)
router.register(r'categories', views.LayerCategoryViewSet)
router.register(r'layers', views.DataLayerViewSet)
router.register(r'features', views.GeoFeatureViewSet)
router.register(r'import-jobs', views.ImportJobViewSet)

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
         
]