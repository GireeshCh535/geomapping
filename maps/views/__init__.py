"""
Maps HTTP API (DRF viewsets + APIView). Split across submodules for maintainability.

`from maps import views` / `from maps.views import SomeView` — all public classes are re-exported here.
"""
from .viewsets import (
    CityViewSet,
    DataLayerViewSet,
    GeoFeatureViewSet,
    LayerCategoryViewSet,
    LayerGroupViewSet,
    StateViewSet,
)
from .coordinate_search import CoordinateSearchTestView
from .tiles_misc import AvailableTilesView, TileCoordinatesView
from .hierarchy import (
    CompleteHierarchyAPIView,
    OptimizedHierarchyAPIView,
    _build_layer_data_full_trimmed,
    _build_layer_data_minimal,
    _build_layer_data_optimized,
)
from .tile_proxy import CloudFrontTileView, S3DirectTileView
from .layers_spatial import (
    LayerBoundsAPIView,
    LayerBoundsZoomAPIView,
    LayerCoordinateSearchView,
    NearbyLayersAPIView,
)
from .webhooks import (
    DeveloperListingMediaWebhookView,
    LandPlotMVTBuildView,
    LandPlotWebhookView,
    TileGenerationCallbackView,
    _execute_listing_deletion,
    _execute_media_deletion,
    _parse_datetime_webhook,
    _print_webhook_response,
    _process_developer_listing_webhook,
    _process_land_plot_webhook,
    _webhook_payload_snapshot,
)
from .listings import (
    DeveloperListingDetailAPIView,
    DeveloperListingListAPIView,
    DeveloperListingMapDataAPIView,
    DeveloperListingMediaDetailAPIView,
    EnrichmentLookupAPIView,
    HyderabadHMDABoundaryCheckAPIView,
    LayerListingLinksAPIView,
    LayerPointCountsAPIView,
    WebhookEventListAPIView,
)
from .land_plot import (
    LandPlotGeoJSONView,
    LandPlotLocalTileView,
    LandPlotMapTestView,
    LandPlotTileView,
    _fetch_tile_url,
    _land_plot_price_percentiles,
    _marker_id_for_listing,
    _tier_for_price,
)

__all__ = [
    "StateViewSet",
    "LayerGroupViewSet",
    "CityViewSet",
    "LayerCategoryViewSet",
    "DataLayerViewSet",
    "GeoFeatureViewSet",
    "CoordinateSearchTestView",
    "AvailableTilesView",
    "TileCoordinatesView",
    "CompleteHierarchyAPIView",
    "OptimizedHierarchyAPIView",
    "_build_layer_data_minimal",
    "_build_layer_data_optimized",
    "_build_layer_data_full_trimmed",
    "CloudFrontTileView",
    "S3DirectTileView",
    "NearbyLayersAPIView",
    "LayerBoundsAPIView",
    "LayerCoordinateSearchView",
    "LayerBoundsZoomAPIView",
    "_webhook_payload_snapshot",
    "_print_webhook_response",
    "_parse_datetime_webhook",
    "_execute_listing_deletion",
    "_execute_media_deletion",
    "_process_developer_listing_webhook",
    "TileGenerationCallbackView",
    "DeveloperListingMediaWebhookView",
    "LandPlotMVTBuildView",
    "_process_land_plot_webhook",
    "LandPlotWebhookView",
    "DeveloperListingDetailAPIView",
    "DeveloperListingListAPIView",
    "EnrichmentLookupAPIView",
    "LayerPointCountsAPIView",
    "LayerListingLinksAPIView",
    "DeveloperListingMediaDetailAPIView",
    "WebhookEventListAPIView",
    "DeveloperListingMapDataAPIView",
    "HyderabadHMDABoundaryCheckAPIView",
    "_fetch_tile_url",
    "LandPlotTileView",
    "LandPlotLocalTileView",
    "_land_plot_price_percentiles",
    "_tier_for_price",
    "_marker_id_for_listing",
    "LandPlotGeoJSONView",
    "LandPlotMapTestView",
]
