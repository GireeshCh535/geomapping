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
    
    # ================================
    # SPECIFIC PATHS (must come before router to avoid conflicts)
    # ================================
    
    # Nearby layers API - Find all layers within 50km of coordinates or bounds
    # MUST come before router.register(r'layers', ...) to avoid conflict
    path('layers/nearby/',
         views.NearbyLayersAPIView.as_view(), name='nearby_layers'),
    
    # Layer bounds API - Get bounds for a specific layer based on actual data
    path('layers/<slug:state_slug>/<slug:city_slug>/<slug:layer_slug>/bounds/',
         views.LayerBoundsAPIView.as_view(), name='layer_bounds'),
    
    # Layer bounds and zoom level API
    path('layers/<slug:state_slug>/<slug:city_slug>/<str:layer_slugs>/bounds-zoom/',
         views.LayerBoundsZoomAPIView.as_view(), name='layer_bounds_zoom'),
    
    # ================================
    # ROUTER URLs (REST API endpoints)
    # ================================
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
    
    # S3 Direct tile serving (bypasses CloudFront)
    path('s3-tiles/<slug:state_slug>/<slug:city_slug>/<slug:layer_slug>/<int:z>/<int:x>/<int:y>.png',
         views.S3DirectTileView.as_view(),
         name='s3_direct_tile_png'),
    
    # S3 Direct MVT tiles
    path('s3-tiles/<slug:state_slug>/<slug:city_slug>/<slug:layer_slug>/<int:z>/<int:x>/<int:y>.mvt',
         views.S3DirectTileView.as_view(),
         name='s3_direct_tile_mvt'),
    
    path('cities/<slug:city_slug>/tiles/coordinates/',
         TileCoordinatesView.as_view(), name='tile_coordinates'),
    
    path('cities/<slug:city_slug>/tiles/available/',
         AvailableTilesView.as_view(), name='available_tiles'),
    
    path('cities/<slug:city_slug>/search-coords-test/',
         views.CoordinateSearchTestView.as_view(), name='coordinate_search_test'),
    
    # Global coordinate search (across all states/cities)
    path('search-coords-test/',
         views.CoordinateSearchTestView.as_view(), name='global_coordinate_search_test'),
    
    # Layer-specific coordinate search API
    path('search-coords-by-layer/',
         views.LayerCoordinateSearchView.as_view(), name='layer_coordinate_search'),
    
    # Hyderabad HMDA Boundary Check API
    path('check-hmda-boundary/',
         views.HyderabadHMDABoundaryCheckAPIView.as_view(), name='check_hmda_boundary'),
    
    # ================================
    # DEVELOPER LISTING WEBHOOK & TILE GENERATION
    # ================================
    
    # Webhook endpoint for developer listing media uploads
    path('webhooks/developer-listing-media/',
         views.DeveloperListingMediaWebhookView.as_view(),
         name='developer-listing-media-webhook'),

    # Webhook endpoint for Land and Plot (regular listings) create/update/delete
    path('webhooks/land-plot/',
         views.LandPlotWebhookView.as_view(),
         name='land-plot-webhook'),

    # ================================
    # DEVELOPER LISTING APIs (Public Access to Webhook Data)
    # ================================
    
    # List all developer listings with filtering
    path('developer-listings/',
         views.DeveloperListingListAPIView.as_view(),
         name='developer-listing-list'),
    
    # Get complete details for a specific developer listing
    path('developer-listings/<str:listing_type>/<int:listing_id>/',
         views.DeveloperListingDetailAPIView.as_view(),
         name='developer-listing-detail'),
    
    # Get lightweight map data (bounds, zoom, S3 paths only)
    path('developer-listings/<str:listing_type>/<int:listing_id>/map-data/',
         views.DeveloperListingMapDataAPIView.as_view(),
         name='developer-listing-map-data'),
    
    # Get detailed information for a specific media file
    path('developer-listing-media/<int:media_id>/',
         views.DeveloperListingMediaDetailAPIView.as_view(),
         name='developer-listing-media-detail'),
    
    # List webhook events with filtering
    path('webhook-events/',
         views.WebhookEventListAPIView.as_view(),
         name='webhook-event-list'),

    # Enrichment lookup: POST listing_type + ids, get enrichment + full record data
    path('enrichment-lookup/',
         views.EnrichmentLookupAPIView.as_view(),
         name='enrichment-lookup'),
]