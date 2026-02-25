"""
Land/plot MVT tile refresh on webhook: compute affected tiles from (lat, lng),
regenerate with active+public filter, upload to S3, invalidate CloudFront.
"""

import logging
import time
from typing import List, Tuple

import mercantile
from django.conf import settings
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Zoom range for land/plot tiles (align with command and tile serving)
LAND_PLOT_MIN_ZOOM = 2
LAND_PLOT_MAX_ZOOM = 18


def get_affected_land_plot_tile_keys(
    lng: float,
    lat: float,
    min_zoom: int = LAND_PLOT_MIN_ZOOM,
    max_zoom: int = LAND_PLOT_MAX_ZOOM,
) -> List[Tuple[int, int, int]]:
    """
    Return list of (z, x, y) tile keys that contain the point (lng, lat)
    for zoom levels min_zoom through max_zoom (inclusive).
    """
    keys = []
    for z in range(min_zoom, max_zoom + 1):
        t = mercantile.tile(lng, lat, z)
        keys.append((t.z, t.x, t.y))
    return keys


def refresh_tiles_for_listing(
    lat: float,
    lng: float,
) -> None:
    """
    For the given (lat, lng): compute affected land/plot tile keys,
    regenerate each tile (active+public only), upload to S3, then
    invalidate CloudFront for those paths. Logs errors and does not raise.
    """
    from maps.tile_path_service import TilePathService
    from maps.s3_upload_service import S3TileUploadService
    from maps.management.commands.generate_land_plot_mvt_tiles import build_land_plot_tile_mvt

    tile_path_service = TilePathService()
    s3_service = S3TileUploadService()

    affected = get_affected_land_plot_tile_keys(lng, lat)
    if not affected:
        return

    logger.info(f"[LAND_PLOT_TILE_REFRESH] Refreshing {len(affected)} tiles for ({lat}, {lng})")

    for z, x, y in affected:
        s3_key = tile_path_service.land_plot_s3_key(z, x, y)
        try:
            s3_service.delete_object(s3_key)
            mvt_bytes = build_land_plot_tile_mvt(z, x, y, percentiles=None, swap_lat_long=False)
            result = s3_service.upload_bytes(
                mvt_bytes,
                s3_key,
                content_type='application/vnd.mapbox-vector-tile',
            )
            if not result.get('success'):
                logger.warning(f"[LAND_PLOT_TILE_REFRESH] Upload failed for {s3_key}: {result.get('error')}")
        except Exception as e:
            logger.warning(f"[LAND_PLOT_TILE_REFRESH] Tile {z}/{x}/{y} failed: {e}", exc_info=True)

    # One CloudFront invalidation for all affected paths
    paths = [f"/land-plot/{z}/{x}/{y}.mvt" for z, x, y in affected]
    _invalidate_cloudfront_land_plot(paths)


def _invalidate_cloudfront_land_plot(paths: List[str]) -> None:
    """
    Create a CloudFront invalidation for the given paths (e.g. /land-plot/z/x/y.mvt).
    No-op if ENABLE_CLOUDFRONT_INVALIDATION is False or CLOUDFRONT_DISTRIBUTION_ID is missing.
    """
    distribution_id = getattr(settings, 'CLOUDFRONT_DISTRIBUTION_ID', None) or ''
    enable = getattr(settings, 'ENABLE_CLOUDFRONT_INVALIDATION', True)
    if not enable or not distribution_id:
        logger.debug("[LAND_PLOT_TILE_REFRESH] CloudFront invalidation disabled or not configured")
        return

    try:
        client = __get_cloudfront_client()
        if not client:
            return
        response = client.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                'Paths': {
                    'Quantity': len(paths),
                    'Items': paths,
                },
                'CallerReference': f"land-plot-{int(time.time())}",
            },
        )
        invalidation_id = response.get('Invalidation', {}).get('Id')
        if invalidation_id:
            logger.info(f"[LAND_PLOT_TILE_REFRESH] CloudFront invalidation created: {invalidation_id}")
    except ClientError as e:
        code = e.response.get('Error', {}).get('Code', '')
        msg = e.response.get('Error', {}).get('Message', str(e))
        logger.error(f"[LAND_PLOT_TILE_REFRESH] CloudFront invalidation error: {code} - {msg}")
    except Exception as e:
        logger.error(f"[LAND_PLOT_TILE_REFRESH] CloudFront invalidation failed: {e}", exc_info=True)


def __get_cloudfront_client():
    """Lazy boto3 CloudFront client (us-east-1). Returns None on failure."""
    try:
        return __get_cloudfront_client._client
    except AttributeError:
        pass
    try:
        import boto3
        __get_cloudfront_client._client = boto3.client(
            'cloudfront',
            region_name='us-east-1',
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None),
        )
        return __get_cloudfront_client._client
    except Exception as e:
        logger.warning(f"[LAND_PLOT_TILE_REFRESH] CloudFront client init failed: {e}")
        __get_cloudfront_client._client = None
        return None
