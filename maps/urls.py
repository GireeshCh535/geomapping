# maps/urls.py - Updated with Direct S3 Generation endpoints

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
    
    # Router URLs (REST API endpoints)
    path('', include(router.urls)),
    
    # 🚀 TILE SERVING ENDPOINTS (Updated with Direct S3 fallback)
    path('tiles/<slug:city_slug>/combined/<int:z>/<int:x>/<int:y>.png',
         views.CombinedRasterTileView.as_view(), name='combined_raster_tile'),
    
    path('tiles/<slug:city_slug>/<slug:layer_slug>/<int:z>/<int:x>/<int:y>.png', 
         views.RasterTileView.as_view(), name='raster_tile'),
    
    path('tiles/<slug:city_slug>/combined/<int:z>/<int:x>/<int:y>.mvt',
         views.CombinedVectorTileView.as_view(), name='combined_tile'),
         
    path('tiles/<slug:city_slug>/<slug:layer_slug>/<int:z>/<int:x>/<int:y>.mvt', 
         views.VectorTileView.as_view(), name='vector_tile'),
    
    # 🚀 REAL ESTATE TILES (CloudFront-enabled)
    path('real-estate-tiles/<str:tile_type>/<int:z>/<int:x>/<int:y>.mvt',
         RealEstateVectorTileView.as_view(), name='real_estate_vector_tile'),
         
    path('real-estate-tiles/<str:tile_type>/<int:z>/<int:x>/<int:y>.png',
         views.RealEstateRasterTileView.as_view(), name='real_estate_raster_tile'),

    # 🆕 NEW: DIRECT S3 GENERATION ENDPOINTS
    path('direct-s3/generate/',
         views.DirectS3TileGenerationView.as_view(), name='direct_s3_generation'),
    
    path('direct-s3/generate/<slug:city_slug>/',
         views.DirectS3TileGenerationView.as_view(), name='direct_s3_city_generation'),
    
    # 🔄 UPDATED: Enhanced tile upload management with direct S3 generation
    path('cities/<slug:city_slug>/tile-management/',
         views.TileUploadManagementView.as_view(), name='tile_management'),
    
    # 🆕 NEW: CloudFront URL helper for frontend integration
    path('cities/<slug:city_slug>/tile-urls/',
         views.TileURLView.as_view(), name='city_tile_urls'),

    # 🔄 UPDATED: Legacy upload endpoints (for backward compatibility)
    path('cities/<slug:city_slug>/upload-tiles/',
         views.TileUploadManagementView.as_view(), name='tile_upload_management'),

     path('cities/<slug:city_slug>/search-coords-test/',
         views.CoordinateSearchTestView.as_view(), name='coordinate_search_test'),
    
    # REST OF YOUR EXISTING URLS...
    path('cities/<slug:city_slug>/layers/', 
         views.CityLayersView.as_view(), name='city_layers'),
    
    path('cities/<slug:city_slug>/layers/<slug:layer_slug>/features/',
         views.LayerFeaturesView.as_view(), name='layer_features'),

     path('cities/<slug:city_slug>/center/', 
          views.CityCenterView.as_view(), name='city_center'),
    
    
    # LAYER MANAGEMENT
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
    
    # SETUP AND CONFIGURATION
    path('setup/cities/', 
         views.SetupCitiesView.as_view(), name='city_setup'),
    
    
    # LAYER CONFIGURATION
     path('layer-config/', views.LayerConfigAPIView.as_view(), name='layer_config'),
     path('states/<slug:state_slug>/layer-config/', views.StateLayerConfigView.as_view(), name='state_layer_config'),
     path('layer-config/', views.StateLayerConfigView.as_view(), name='state_layer_config'),
     path('cities/<slug:city_slug>/layer-config/', views.CityLayerConfigView.as_view(), name='city_layer_config'),
     path('layer-config/<slug:layer_slug>/', views.LayerConfigDetailView.as_view(), name='layer_config_detail'),
     path('cities/<slug:city_slug>/tiles/available/',
         AvailableTilesView.as_view(), name='available_tiles'),
    
    path('cities/<slug:city_slug>/tiles/coordinates/', 
         TileCoordinatesView.as_view(), name='tile_coordinates'),

]

# 📋 UPDATED API DOCUMENTATION
"""
# 🚀 NEW DIRECT S3 GENERATION ENDPOINTS:

## Direct S3 Generation APIs:
POST /api/direct-s3/generate/ - Generate tiles directly to S3
POST /api/direct-s3/generate/{city_slug}/ - Generate city-specific tiles to S3

### Request Body Example:
{
    "action": "generate_city",           // or "generate_real_estate", "generate_all_cities"
    "tile_types": ["png", "mvt"],        // Array of tile types to generate
    "min_zoom": 8,                       // Minimum zoom level
    "max_zoom": 14,                      // Maximum zoom level
    "data_type": "combined",             // For real estate: "plots", "lands", "combined"
    "include_real_estate": false         // Include real estate tiles for city generation
}

### Response Example:
{
    "status": "success",
    "action": "generate_city",
    "result": {
        "success": true,
        "city": "bangalore",
        "results": {
            "total_tiles": 1024,
            "generated_tiles": 1024,
            "failed_tiles": 0,
            "png_uploads": 1024,
            "mvt_uploads": 1024,
            "total_size_mb": 45.3
        },
        "success_rate": "100.0%",
        "sample_urls": {
            "city_tile_example": "https://d17yosovmfjm4.cloudfront.net/bangalore/combined/12_2048_2048.png",
            "template_png": "https://d17yosovmfjm4.cloudfront.net/bangalore/combined/{z}_{x}_{y}.png"
        }
    }
}

## Enhanced Tile Management APIs:
GET /api/cities/{city_slug}/tile-management/ - Get status and available actions
POST /api/cities/{city_slug}/tile-management/ - Trigger operations

### Available Actions:
- "generate_direct_s3" - 🆕 NEW: Generate tiles directly to S3 (RECOMMENDED)
- "upload_city_png" - Legacy: Upload existing local PNG files
- "upload_city_mvt" - Legacy: Upload existing local MVT files
- "upload_real_estate" - Legacy: Upload existing real estate files
- "test_s3_connection" - Test S3 connectivity

## Tile Serving APIs (Updated):
GET /api/tiles/{city_slug}/combined/{z}/{x}/{y}.png - City tiles with enhanced fallback
GET /api/tiles/{city_slug}/{layer_slug}/{z}/{x}/{y}.png - Individual layer tiles
GET /api/tiles/{city_slug}/combined/{z}/{x}/{y}.mvt - Combined MVT tiles
GET /api/tiles/{city_slug}/{layer_slug}/{z}/{x}/{y}.mvt - Individual MVT tiles

### Updated Serving Priority:
1. 🌐 CloudFront (Production, fastest)
2. 📁 Local files (Backward compatibility)
3. 🚀 Direct S3 generation (NEW - Primary method)
4. 🔄 On-demand generation (Fallback)
5. ⚪ Empty tile (Last resort)

## Real Estate Tile APIs:
GET /api/real-estate-tiles/{tile_type}/{z}/{x}/{y}.mvt - Real estate MVT tiles
GET /api/real-estate-tiles/{tile_type}/{z}/{x}/{y}.png - Real estate PNG tiles

## CloudFront Integration APIs:
GET /api/cities/{city_slug}/tile-urls/ - Get all CloudFront URLs for frontend

## Plot & Land APIs:
GET /api/plots/ - All plots
GET /api/plots/in_bbox/?bbox=77.0,17.0,78.0,18.0 - Plots in bounding box
GET /api/plots/near_point/?lat=17.31&lng=77.91&radius_km=5 - Plots near point
GET /api/lands/ - All lands
GET /api/lands/in_bbox/?bbox=77.0,17.0,78.0,18.0 - Lands in bounding box
GET /api/lands/near_point/?lat=18.01&lng=78.41&radius_km=10 - Lands near point

# 🎯 RECOMMENDED WORKFLOW:

## For New Deployments:
1. Use direct S3 generation: POST /api/direct-s3/generate/{city_slug}/
2. Tiles are generated and uploaded directly to S3
3. CloudFront serves tiles globally with CDN caching
4. No local storage required

## For Existing Deployments:
1. Can continue using legacy upload methods
2. Gradually migrate to direct S3 generation
3. Both methods work together seamlessly

# 🚀 PERFORMANCE BENEFITS:
- No local disk space required for tiles
- Faster deployment (no tile file transfers)
- Automatic CDN distribution
- Concurrent tile generation
- Better error handling and retry logic
- Real-time progress tracking
"""