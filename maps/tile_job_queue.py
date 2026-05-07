"""
Single source for enqueueing tile generation jobs to SQS.
Used by both webhook handlers (via thread-local context) and by signals (admin/API saves).
Worker: poll_sqs_tile_worker (job_type 'land_plot_mvt' -> MVT, 'tif' -> PNG).
"""

import json
import logging
import threading
from typing import Any, Dict, Optional

import boto3
from django.conf import settings
from django.urls import reverse

from maps.tile_debug import tile_debug

logger = logging.getLogger(__name__)

# Thread-local context: when set by webhook handlers, signals include webhook_event_id in payload.
_tile_job_ctx = threading.local()


def get_land_plot_webhook_event_id() -> Optional[int]:
    """Get current land/plot webhook event id (set by webhook handler)."""
    return getattr(_tile_job_ctx, "land_plot_webhook_event_id", None)


def set_land_plot_webhook_event_id(value: Optional[int]) -> None:
    """Set/clear land/plot webhook event id (called by webhook handler)."""
    _tile_job_ctx.land_plot_webhook_event_id = value


def get_developer_webhook_event_id() -> Optional[int]:
    """Get current developer listing webhook event id (set by webhook handler)."""
    return getattr(_tile_job_ctx, "developer_webhook_event_id", None)


def set_developer_webhook_event_id(value: Optional[int]) -> None:
    """Set/clear developer webhook event id (called by webhook handler)."""
    _tile_job_ctx.developer_webhook_event_id = value


def get_developer_listing_job_enqueued() -> set:
    """Get set of listing pks for which we already scheduled a TIF job this thread (dedupe)."""
    if not hasattr(_tile_job_ctx, "developer_listing_job_enqueued"):
        _tile_job_ctx.developer_listing_job_enqueued = set()
    return _tile_job_ctx.developer_listing_job_enqueued


def clear_developer_listing_job_enqueued() -> None:
    """Clear dedupe set (called by webhook handler at end)."""
    if hasattr(_tile_job_ctx, "developer_listing_job_enqueued"):
        _tile_job_ctx.developer_listing_job_enqueued = set()


def send_tile_job_to_sqs(event_type: str, job_type: str, data: Dict[str, Any]) -> tuple:
    """
    Send a tile job to SQS. Used by land/plot (MVT) and developer listing (TIF/PNG) flows.
    event_type: 'create' | 'update' | 'delete'
    job_type: 'tif' | 'land_plot_mvt'
    data: full payload for the worker (callback_url, tif_files or lat/lng, webhook_event_id, etc.)
    Returns (success: bool, message_id_or_error: str).
    """
    queue_url = getattr(settings, "TILE_SQS_QUEUE_URL", "").strip()
    if not queue_url:
        tile_debug("SQS enqueue skip: TILE_SQS_QUEUE_URL not set")
        return False, "TILE_SQS_QUEUE_URL not set"
    region = getattr(settings, "AWS_DEFAULT_REGION", "ap-south-1")
    try:
        sqs = boto3.client("sqs", region_name=region)
        body = json.dumps({"event": event_type, "job_type": job_type, "data": data}, default=str)
        response = sqs.send_message(QueueUrl=queue_url, MessageBody=body)
        msg_id = response.get("MessageId", "")
        tile_debug(f"SQS enqueue OK msg_id={msg_id} job_type={job_type} event={event_type}")
        logger.info("[SQS] Queued message: %s job_type=%s event=%s", msg_id, job_type, event_type)
        return True, msg_id
    except Exception as e:
        tile_debug(f"SQS enqueue FAIL job_type={job_type} event={event_type} err={e}")
        logger.exception("[SQS] send_message failed: %s", e)
        return False, str(e)


def send_land_plot_tile_job(record, webhook_event_id: Optional[int] = None) -> tuple:
    """
    Enqueue land/plot MVT tile generation for the given SyncedLand or SyncedPlot record.
    Only sends if record has valid location_point (lat/lng).
    Returns (success: bool, message_id_or_error: str).
    """
    if getattr(record, "location_point", None) is None or getattr(
        record.location_point, "empty", True
    ):
        return False, "no coordinates"
    lat = record.location_point.y
    lng = record.location_point.x
    if lat is None or lng is None:
        return False, "no coordinates"
    listing_type = "land" if record.__class__.__name__ == "SyncedLand" else "plot"
    listing_id = record.backend_id
    base_url = getattr(settings, "TILE_CALLBACK_BASE_URL", "").strip()
    if not base_url:
        logger.warning("[TILE_JOB] TILE_CALLBACK_BASE_URL not set; skipping land/plot job")
        return False, "TILE_CALLBACK_BASE_URL not set"
    callback_url = base_url.rstrip("/") + "/api/webhooks/tile-generation-result/"
    mvt_build_base_url = base_url.rstrip("/") + "/api/tiles/land-plot-mvt-build"
    payload = {
        "webhook_event_id": webhook_event_id,
        "lat": lat,
        "lng": lng,
        "tiles": [],
        "mvt_build_base_url": mvt_build_base_url,
        "s3_tile_prefix": "land-plot",
        "internal_secret": getattr(settings, "TILE_CALLBACK_SECRET", ""),
        "callback_url": callback_url,
        "callback_secret": getattr(settings, "TILE_CALLBACK_SECRET", ""),
        "listing_type": listing_type,
        "listing_id": listing_id,
    }
    return send_tile_job_to_sqs("update", "land_plot_mvt", payload)


def send_tif_tile_job(listing, webhook_event_id: Optional[int] = None) -> tuple:
    """
    Enqueue developer listing TIF (PNG) tile generation for the given DeveloperListing.
    Builds tif_files from listing's DeveloperListingMedia (is_tif=True).
    Returns (success: bool, message_id_or_error: str).
    """
    from .models import DeveloperListingMedia

    tif_media = list(
        DeveloperListingMedia.objects.filter(listing=listing, is_tif=True).values(
            "id", "backend_media_id", "file_name", "file_url", "s3_tile_path"
        )
    )
    if not tif_media:
        return False, "no TIF files"
    tif_files = []
    for m in tif_media:
        tif_files.append({
            "id": m.get("backend_media_id") or m.get("id"),
            "file_name": m.get("file_name", ""),
            "url": m.get("file_url", ""),
            "s3_tile_path": m.get("s3_tile_path", ""),
            "is_tif": True,
        })
    base_url = getattr(settings, "TILE_CALLBACK_BASE_URL", "").strip()
    if not base_url:
        logger.warning("[TILE_JOB] TILE_CALLBACK_BASE_URL not set; skipping TIF job")
        return False, "TILE_CALLBACK_BASE_URL not set"
    callback_path = reverse("tile-generation-callback")
    callback_url = base_url.rstrip("/") + callback_path
    s3_tile_base_path = f"{listing.listing_type}/{listing.backend_listing_id}"
    payload = {
        "webhook_event_id": webhook_event_id,
        "callback_url": callback_url,
        "callback_secret": getattr(settings, "TILE_CALLBACK_SECRET", ""),
        "listing_type": listing.listing_type,
        "listing_id": listing.backend_listing_id,
        "tif_files": tif_files,
        "s3_tile_base_path": s3_tile_base_path,
        "event_type": "developer_listing_updated",
        "action": "updated",
        "data_snapshot": {},
    }
    return send_tile_job_to_sqs("update", "tif", payload)
