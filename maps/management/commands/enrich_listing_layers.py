"""
Daily/incremental listing–layer enrichment.

For each developer listing with coordinates, computes overlapping and nearby (≤30 km)
data layers and stores them in listing.enriched_layers.

Modes:
  incremental (default): New listings (enriched_at null), stale listings (updated_at > enriched_at),
                         and listings affected by new layers (layer created in last 24h).
  full: Re-enrich all active listings that have coordinates.

Usage:
  python manage.py enrich_listing_layers
  python manage.py enrich_listing_layers --full
  python manage.py enrich_listing_layers --new-listings-only
  python manage.py enrich_listing_layers --dry-run
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand

from maps.models import DeveloperListing, DataLayer
from maps.listing_layer_enrichment_service import (
    enrich_listing,
    enrich_listings_queryset,
    get_listings_near_layer,
    NEARBY_THRESHOLD_KM,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Enrich developer listings with overlapping and nearby data layers (≤30 km).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Re-enrich all active listings with coordinates (default: incremental)',
        )
        parser.add_argument(
            '--new-listings-only',
            action='store_true',
            help='Only process listings that have never been enriched (enriched_at is null)',
        )
        parser.add_argument(
            '--new-layers-only',
            action='store_true',
            help='Only re-enrich listings affected by layers created in the last 24 hours',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Log what would be done without writing to DB',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: no changes will be saved.'))

        processed = 0
        skipped = 0

        if options['new_layers_only']:
            processed, skipped = self._enrich_for_new_layers(dry_run)
        elif options['full']:
            processed, skipped = self._enrich_full(dry_run)
        elif options['new_listings_only']:
            processed, skipped = self._enrich_new_listings_only(dry_run)
        else:
            processed, skipped = self._enrich_incremental(dry_run)

        self.stdout.write(
            self.style.SUCCESS(
                f'Enrichment complete: {processed} listings processed, {skipped} skipped.'
            )
        )

    def _enrich_full(self, dry_run: bool):
        qs = DeveloperListing.objects.filter(is_active=True)
        if dry_run:
            count = qs.count()
            self.stdout.write(f'[dry-run] Would process all active listings: {count}')
            return count, 0
        return enrich_listings_queryset(qs, update_location_point=True)

    def _enrich_new_listings_only(self, dry_run: bool):
        qs = DeveloperListing.objects.filter(is_active=True, enriched_at__isnull=True)
        if dry_run:
            count = qs.count()
            self.stdout.write(f'[dry-run] Would process never-enriched listings: {count}')
            return count, 0
        return enrich_listings_queryset(qs, update_location_point=True)

    def _enrich_incremental(self, dry_run: bool):
        """New listings + stale listings (updated after last enrichment) + listings near new layers."""
        processed = 0
        skipped = 0

        # 1) Never enriched
        qs_new = DeveloperListing.objects.filter(is_active=True, enriched_at__isnull=True)
        if dry_run:
            processed += qs_new.count()
        else:
            p, s = enrich_listings_queryset(qs_new, update_location_point=True)
            processed += p
            skipped += s

        # 2) Updated after enriched_at (stale)
        from django.db.models import F
        qs_stale = DeveloperListing.objects.filter(
            is_active=True,
            enriched_at__isnull=False,
            updated_at__gt=F('enriched_at'),
        )
        if dry_run:
            processed += qs_stale.count()
        else:
            p, s = enrich_listings_queryset(qs_stale, update_location_point=True)
            processed += p
            skipped += s

        # 3) New layers (created in last 24h): re-enrich listings near them
        since = timezone.now() - timedelta(hours=24)
        new_layers = DataLayer.objects.filter(
            is_processed=True,
            created_at__gte=since,
        ).exclude(category__code='DEVELOPER_LISTING')

        listing_ids_to_refresh = set()
        for layer in new_layers:
            near = get_listings_near_layer(layer, within_km=NEARBY_THRESHOLD_KM)
            listing_ids_to_refresh.update(near.values_list('id', flat=True))

        if listing_ids_to_refresh:
            qs_affected = DeveloperListing.objects.filter(id__in=listing_ids_to_refresh, is_active=True)
            if dry_run:
                processed += len(listing_ids_to_refresh)
            else:
                p, s = enrich_listings_queryset(qs_affected, update_location_point=False)
                processed += p
                skipped += s

        return processed, skipped

    def _enrich_for_new_layers(self, dry_run: bool):
        """Only re-enrich listings that are near layers created in the last 24 hours."""
        since = timezone.now() - timedelta(hours=24)
        new_layers = DataLayer.objects.filter(
            is_processed=True,
            created_at__gte=since,
        ).exclude(category__code='DEVELOPER_LISTING')

        listing_ids = set()
        for layer in new_layers:
            near = get_listings_near_layer(layer, within_km=NEARBY_THRESHOLD_KM)
            listing_ids.update(near.values_list('id', flat=True))

        if not listing_ids:
            self.stdout.write('No listings in range of new layers.')
            return 0, 0

        qs = DeveloperListing.objects.filter(id__in=listing_ids, is_active=True)
        if dry_run:
            self.stdout.write(f'[dry-run] Would re-enrich {len(listing_ids)} listings near new layers.')
            return len(listing_ids), 0
        return enrich_listings_queryset(qs, update_location_point=False)
