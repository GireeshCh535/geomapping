"""
Django signals for automatic listing-layer enrichment and tile job enqueue.

- DataLayer: when a new layer is added or becomes processed, enrich listings near that layer.
- SyncedLand / SyncedPlot: when saved with coordinates, enqueue land/plot MVT tile job (SQS).
- DeveloperListingMedia (TIF): when saved, enqueue developer listing PNG tile job (SQS) after commit.
"""

import logging
from django.db import transaction
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from maps.models import (
    DataLayer,
    DeveloperListing,
    DeveloperListingMedia,
    LayerListingLink,
    SyncedDeveloperLand,
    SyncedDeveloperPlot,
    SyncedLand,
    SyncedPlot,
)
from maps.tile_job_queue import (
    send_land_plot_tile_job,
    send_tif_tile_job,
    get_land_plot_webhook_event_id,
    get_developer_webhook_event_id,
    get_developer_listing_job_enqueued,
)
from maps.listing_layer_enrichment_service import (
    get_listings_near_layer,
    get_synced_listings_near_layer,
    enrich_listings_queryset,
    enrich_synced_queryset,
    refresh_layer_point_count_cache,
    NEARBY_THRESHOLD_KM,
)

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=DataLayer)
def _datalayer_pre_save(sender, instance, **kwargs):
    """Store previous is_processed so post_save can detect transition to True."""
    if instance.pk:
        try:
            old = DataLayer.objects.filter(pk=instance.pk).values_list('is_processed', flat=True).first()
            instance._signal_was_processed = old
        except Exception:
            instance._signal_was_processed = None
    else:
        instance._signal_was_processed = False  # new instance


def _enrich_listings_near_layer_after_commit(layer_id: int):
    """Run enrichment for all listings near the given layer (called after commit)."""
    try:
        layer = DataLayer.objects.filter(pk=layer_id).first()
        if not layer or not layer.is_processed:
            return
        if layer.category and getattr(layer.category, 'code', None) == 'DEVELOPER_LISTING':
            return
        total_p, total_s = 0, 0
        listings = get_listings_near_layer(layer, within_km=NEARBY_THRESHOLD_KM)
        if listings.exists():
            p, s = enrich_listings_queryset(listings, update_location_point=False)
            total_p += p
            total_s += s
        land_qs, plot_qs, dev_land_qs, dev_plot_qs = get_synced_listings_near_layer(layer, within_km=NEARBY_THRESHOLD_KM)
        for qs in (land_qs, plot_qs, dev_land_qs, dev_plot_qs):
            if qs.exists():
                p, s = enrich_synced_queryset(qs, update_location_point=False)
                total_p += p
                total_s += s
        if total_p or total_s:
            logger.info(
                "Auto-enrichment for new/updated layer id=%s: %d listings processed, %d skipped",
                layer_id, total_p, total_s,
            )
        else:
            logger.debug("No listings near layer id=%s, skipping enrichment", layer_id)
        # Refresh layer point count cache for this layer so /api/layer-point-counts/ is up to date
        try:
            refresh_layer_point_count_cache(layer_ids=[layer_id])
        except Exception as refresh_err:
            logger.warning("Layer point count cache refresh for layer id=%s failed: %s", layer_id, refresh_err)
    except Exception as e:
        logger.exception("Auto-enrichment for layer id=%s failed: %s", layer_id, e)


@receiver(post_save, sender=DataLayer)
def _datalayer_post_save(sender, instance, created, **kwargs):
    """When a new layer is added or a layer becomes processed, enrich affected listings."""
    if not instance.is_processed:
        return
    # Skip listing-owned TIF layers
    if instance.category and getattr(instance.category, 'code', None) == 'DEVELOPER_LISTING':
        return
    should_enrich = False
    if created:
        should_enrich = True
    else:
        was_processed = getattr(instance, '_signal_was_processed', None)
        if was_processed is False:
            should_enrich = True
    if not should_enrich:
        return
    # Run after transaction commits so layer (and any new features) are committed
    layer_id = instance.pk
    transaction.on_commit(lambda: _enrich_listings_near_layer_after_commit(layer_id))


# ----- LayerListingLink cleanup when listing rows are deleted -----


@receiver(post_delete, sender=SyncedLand)
def _layer_listing_link_delete_land(sender, instance, **kwargs):
    LayerListingLink.objects.filter(source='land', listing_pk=instance.pk).delete()


@receiver(post_delete, sender=SyncedPlot)
def _layer_listing_link_delete_plot(sender, instance, **kwargs):
    LayerListingLink.objects.filter(source='plot', listing_pk=instance.pk).delete()


@receiver(post_delete, sender=SyncedDeveloperLand)
def _layer_listing_link_delete_dev_land(sender, instance, **kwargs):
    LayerListingLink.objects.filter(source='developer_land', listing_pk=instance.pk).delete()


@receiver(post_delete, sender=SyncedDeveloperPlot)
def _layer_listing_link_delete_dev_plot(sender, instance, **kwargs):
    LayerListingLink.objects.filter(source='developer_plot', listing_pk=instance.pk).delete()


# ----- Tile job enqueue (single source: webhook and admin/API both trigger via these signals) -----


@receiver(post_save, sender=SyncedLand)
@receiver(post_save, sender=SyncedPlot)
def _synced_land_plot_post_save_tile_job(sender, instance, created, **kwargs):
    """On SyncedLand/SyncedPlot save with coordinates, enqueue land/plot MVT tile job."""
    webhook_event_id = get_land_plot_webhook_event_id()
    success, result = send_land_plot_tile_job(instance, webhook_event_id=webhook_event_id)
    if success:
        logger.info(
            "[TILE_JOB] Enqueued land/plot MVT job for %s id=%s (event_id=%s) msg_id=%s",
            instance.__class__.__name__, instance.backend_id, webhook_event_id, result,
        )
    elif result not in ("no coordinates", "TILE_CALLBACK_BASE_URL not set"):
        logger.warning("[TILE_JOB] Land/plot job skipped: %s", result)


@receiver(post_delete, sender=SyncedLand)
@receiver(post_delete, sender=SyncedPlot)
def _synced_land_plot_post_delete_tile_job(sender, instance, **kwargs):
    """On SyncedLand/SyncedPlot delete (e.g. from admin), enqueue MVT tile refresh so tiles drop the deleted listing."""
    success, result = send_land_plot_tile_job(instance, webhook_event_id=None)
    if success:
        logger.info(
            "[TILE_JOB] Enqueued land/plot MVT refresh after delete %s id=%s msg_id=%s",
            instance.__class__.__name__, instance.backend_id, result,
        )
    elif result not in ("no coordinates", "TILE_CALLBACK_BASE_URL not set"):
        logger.warning("[TILE_JOB] Land/plot post-delete job skipped: %s", result)


def _enqueue_tif_job_after_commit(listing_id: int, webhook_event_id=None):
    """Run after commit: enqueue one TIF job for the listing (all TIF media)."""
    try:
        listing = DeveloperListing.objects.get(pk=listing_id)
        send_tif_tile_job(listing, webhook_event_id=webhook_event_id)
    except DeveloperListing.DoesNotExist:
        logger.warning("[TILE_JOB] DeveloperListing pk=%s not found for TIF job", listing_id)
    except Exception as e:
        logger.exception("[TILE_JOB] TIF job enqueue failed for listing pk=%s: %s", listing_id, e)


@receiver(post_save, sender=DeveloperListingMedia)
def _developer_listing_media_post_save_tile_job(sender, instance, created, **kwargs):
    """On DeveloperListingMedia (TIF) save, schedule one TIF tile job per listing after commit (deduped)."""
    if not getattr(instance, "is_tif", False):
        return
    listing = getattr(instance, "listing", None)
    if not listing:
        return
    enqueued = get_developer_listing_job_enqueued()
    if listing.pk in enqueued:
        return
    enqueued.add(listing.pk)
    listing_id = listing.pk
    webhook_event_id = get_developer_webhook_event_id()
    transaction.on_commit(
        lambda lid=listing_id, weid=webhook_event_id: _enqueue_tif_job_after_commit(lid, weid)
    )
