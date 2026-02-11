"""
Daily/incremental listing–layer enrichment for all listing tables.

Enriches DeveloperListing and all 4 Synced* tables (SyncedLand, SyncedPlot,
SyncedDeveloperLand, SyncedDeveloperPlot) with overlapping and nearby (≤30 km)
data layers. Stores unified enriched_layers: [{ layer_id, layer_slug, layer_type, distance_km }].
distance_km = 0 means overlap; 0.01–30 means nearby.

Modes:
  incremental (default): New listings (enriched_at null), stale (synced_at/updated_at > enriched_at),
                         and listings affected by new layers (layer created in last 24h).
  full: Re-enrich all listings that have coordinates.
  new-listings-only: Only never-enriched (enriched_at is null).
  new-layers-only: Only re-enrich listings near layers created in the last 24 hours.

Scheduled: Run daily at off-peak (e.g. cron: 0 2 * * * for 2 AM).

Usage:
  python manage.py enrich_listing_layers
  python manage.py enrich_listing_layers --full
  python manage.py enrich_listing_layers --new-listings-only
  python manage.py enrich_listing_layers --new-layers-only
  python manage.py enrich_listing_layers --developer-only   # only DeveloperListing
  python manage.py enrich_listing_layers --synced-only     # only 4 Synced* tables
  python manage.py enrich_listing_layers --dry-run
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from django.db.models import F

from maps.models import DeveloperListing, DataLayer
from maps.models import SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot
from maps.listing_layer_enrichment_service import (
    enrich_listings_queryset,
    enrich_synced_queryset,
    get_listings_near_layer,
    get_synced_listings_near_layer,
    NEARBY_THRESHOLD_KM,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Enrich all listings (DeveloperListing + 4 Synced* tables) with overlapping and nearby data layers (≤30 km).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Re-enrich all listings with coordinates (default: incremental)',
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
            '--developer-only',
            action='store_true',
            help='Only process DeveloperListing (skip SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot)',
        )
        parser.add_argument(
            '--synced-only',
            action='store_true',
            help='Only process the 4 Synced* tables (skip DeveloperListing)',
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

        do_developer = not options['synced_only']
        do_synced = not options['developer_only']

        total_processed = 0
        total_skipped = 0

        if options['new_layers_only']:
            total_processed, total_skipped = self._enrich_for_new_layers(dry_run, do_developer, do_synced)
        elif options['full']:
            total_processed, total_skipped = self._enrich_full(dry_run, do_developer, do_synced)
        elif options['new_listings_only']:
            total_processed, total_skipped = self._enrich_new_listings_only(dry_run, do_developer, do_synced)
        else:
            total_processed, total_skipped = self._enrich_incremental(dry_run, do_developer, do_synced)

        self.stdout.write(
            self.style.SUCCESS(
                f'Enrichment complete: {total_processed} listings processed, {total_skipped} skipped.'
            )
        )

    def _enrich_full(self, dry_run: bool, do_developer: bool, do_synced: bool):
        processed, skipped = 0, 0
        if do_developer:
            qs = DeveloperListing.objects.filter(is_active=True)
            if dry_run:
                processed += qs.count()
                self.stdout.write(f'[dry-run] DeveloperListing: would process {qs.count()}')
            else:
                p, s = enrich_listings_queryset(qs, update_location_point=True)
                processed += p
                skipped += s
        if do_synced:
            for model, label in [
                (SyncedLand, 'SyncedLand'),
                (SyncedPlot, 'SyncedPlot'),
                (SyncedDeveloperLand, 'SyncedDeveloperLand'),
                (SyncedDeveloperPlot, 'SyncedDeveloperPlot'),
            ]:
                qs = model.objects.all()
                if dry_run:
                    processed += qs.count()
                    self.stdout.write(f'[dry-run] {label}: would process {qs.count()}')
                else:
                    p, s = enrich_synced_queryset(qs, update_location_point=True)
                    processed += p
                    skipped += s
        return processed, skipped

    def _enrich_new_listings_only(self, dry_run: bool, do_developer: bool, do_synced: bool):
        processed, skipped = 0, 0
        if do_developer:
            qs = DeveloperListing.objects.filter(is_active=True, enriched_at__isnull=True)
            if dry_run:
                processed += qs.count()
            else:
                p, s = enrich_listings_queryset(qs, update_location_point=True)
                processed += p
                skipped += s
        if do_synced:
            for model, label in [
                (SyncedLand, 'SyncedLand'),
                (SyncedPlot, 'SyncedPlot'),
                (SyncedDeveloperLand, 'SyncedDeveloperLand'),
                (SyncedDeveloperPlot, 'SyncedDeveloperPlot'),
            ]:
                qs = model.objects.filter(enriched_at__isnull=True)
                if dry_run:
                    processed += qs.count()
                else:
                    p, s = enrich_synced_queryset(qs, update_location_point=True)
                    processed += p
                    skipped += s
        return processed, skipped

    def _enrich_incremental(self, dry_run: bool, do_developer: bool, do_synced: bool):
        processed = 0
        skipped = 0

        if do_developer:
            qs_new = DeveloperListing.objects.filter(is_active=True, enriched_at__isnull=True)
            if dry_run:
                processed += qs_new.count()
            else:
                p, s = enrich_listings_queryset(qs_new, update_location_point=True)
                processed += p
                skipped += s
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

        if do_synced:
            for model in (SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot):
                qs_new = model.objects.filter(enriched_at__isnull=True)
                if dry_run:
                    processed += qs_new.count()
                else:
                    p, s = enrich_synced_queryset(qs_new, update_location_point=True)
                    processed += p
                    skipped += s
                qs_stale = model.objects.filter(
                    enriched_at__isnull=False,
                    synced_at__gt=F('enriched_at'),
                )
                if dry_run:
                    processed += qs_stale.count()
                else:
                    p, s = enrich_synced_queryset(qs_stale, update_location_point=True)
                    processed += p
                    skipped += s

        since = timezone.now() - timedelta(hours=24)
        new_layers = DataLayer.objects.filter(
            is_processed=True,
            created_at__gte=since,
        ).exclude(category__code='DEVELOPER_LISTING')

        for layer in new_layers:
            if do_developer:
                near = get_listings_near_layer(layer, within_km=NEARBY_THRESHOLD_KM)
                ids = set(near.values_list('id', flat=True))
                if ids:
                    qs = DeveloperListing.objects.filter(id__in=ids, is_active=True)
                    if dry_run:
                        processed += len(ids)
                    else:
                        p, s = enrich_listings_queryset(qs, update_location_point=False)
                        processed += p
                        skipped += s
            if do_synced:
                land_qs, plot_qs, dev_land_qs, dev_plot_qs = get_synced_listings_near_layer(layer, within_km=NEARBY_THRESHOLD_KM)
                for qs in (land_qs, plot_qs, dev_land_qs, dev_plot_qs):
                    if dry_run:
                        processed += qs.count()
                    else:
                        p, s = enrich_synced_queryset(qs, update_location_point=False)
                        processed += p
                        skipped += s

        return processed, skipped

    def _enrich_for_new_layers(self, dry_run: bool, do_developer: bool, do_synced: bool):
        since = timezone.now() - timedelta(hours=24)
        new_layers = DataLayer.objects.filter(
            is_processed=True,
            created_at__gte=since,
        ).exclude(category__code='DEVELOPER_LISTING')

        processed = 0
        skipped = 0
        for layer in new_layers:
            if do_developer:
                near = get_listings_near_layer(layer, within_km=NEARBY_THRESHOLD_KM)
                ids = set(near.values_list('id', flat=True))
                if ids:
                    qs = DeveloperListing.objects.filter(id__in=ids, is_active=True)
                    if dry_run:
                        processed += len(ids)
                    else:
                        p, s = enrich_listings_queryset(qs, update_location_point=False)
                        processed += p
                        skipped += s
            if do_synced:
                land_qs, plot_qs, dev_land_qs, dev_plot_qs = get_synced_listings_near_layer(layer, within_km=NEARBY_THRESHOLD_KM)
                for qs in (land_qs, plot_qs, dev_land_qs, dev_plot_qs):
                    if dry_run:
                        processed += qs.count()
                    else:
                        p, s = enrich_synced_queryset(qs, update_location_point=False)
                        processed += p
                        skipped += s

        if processed == 0 and not dry_run:
            self.stdout.write('No listings in range of new layers.')
        return processed, skipped
