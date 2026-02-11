"""
Django signals for automatic listing-layer enrichment.

When a new DataLayer is added (or an existing layer becomes processed),
enrich all listings whose location is within 30 km of that layer.
"""

import logging
from django.db import transaction
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from maps.models import DataLayer
from maps.listing_layer_enrichment_service import (
    get_listings_near_layer,
    get_synced_listings_near_layer,
    enrich_listings_queryset,
    enrich_synced_queryset,
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
