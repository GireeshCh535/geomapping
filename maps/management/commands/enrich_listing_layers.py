"""
Daily/incremental listing–layer enrichment for all listing tables.

Enriches DeveloperListing and all 4 Synced* tables (SyncedLand, SyncedPlot,
SyncedDeveloperLand, SyncedDeveloperPlot) with overlapping and nearby (≤30 km)
data layers. Stores unified enriched_layers: [{ layer_id, layer_slug, layer_type, distance_km,
nearest_point? }]. nearest_point is GeoJSON Point on the layer geometry closest to the listing.
distance_km = 0 means overlap; 0.01–30 means nearby.

Run after pull_land_plot_from_api when new listings are synced. Safe to run
incremental daily; use --refresh occasionally to keep enrichment fully in sync.

Modes:
  incremental (default): Only process: new (enriched_at null), stale
                         (synced_at/updated_at > enriched_at), and listings
                         near layers created in last 24h.
  full: Re-enrich all listings that have coordinates.
  refresh: Clear enriched_layers/enriched_at then run full enrichment.
  new-listings-only: Only never-enriched (enriched_at is null).
  new-layers-only: Only re-enrich listings near layers created in the last 24 hours.

Usage:
  python manage.py enrich_listing_layers                    # incremental
  python manage.py enrich_listing_layers --refresh         # clear + full re-run
  python manage.py enrich_listing_layers --full
  python manage.py enrich_listing_layers --update-four-tables  # 4 Synced* only: sync coords + enrich
  python manage.py enrich_listing_layers --new-listings-only
  python manage.py enrich_listing_layers --new-layers-only
  python manage.py enrich_listing_layers --developer-only   # only DeveloperListing
  python manage.py enrich_listing_layers --synced-only     # only 4 Synced* tables
  python manage.py enrich_listing_layers --dry-run
"""

import logging
import sys
import time
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
SYNCED_TABLES = [
    (SyncedLand, 'SyncedLand'),
    (SyncedPlot, 'SyncedPlot'),
    (SyncedDeveloperLand, 'SyncedDeveloperLand'),
    (SyncedDeveloperPlot, 'SyncedDeveloperPlot'),
]


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
            '--update-four-tables',
            action='store_true',
            help='Update all 4 Synced* tables only: sync location_point from payload/lat/long, then full enrichment',
        )
        parser.add_argument(
            '--refresh',
            action='store_true',
            help='Clear existing enrichment (enriched_layers, enriched_at) then run full enrichment (keep fresh)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Log what would be done without writing to DB',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        update_four_tables = options.get('update_four_tables', False)
        if update_four_tables:
            do_developer = False
            do_synced = True
            options['synced_only'] = True
            options['full'] = True
        else:
            do_developer = not options['synced_only']
            do_synced = not options['developer_only']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: no changes will be saved.'))

        mode = 'update-four-tables' if update_four_tables else (
            'new-layers-only' if options['new_layers_only'] else (
                'new-listings-only' if options['new_listings_only'] else (
                    'full' if options['full'] else (
                        'refresh' if options['refresh'] else 'incremental'
                    )
                )
            )
        )
        self._log(f'Enrichment started | mode={mode} | developer={do_developer} | synced={do_synced}')
        if mode == 'incremental':
            self._log('Skip-if-done: only processing never-enriched, stale, or near-new-layer listings.')
        start_time = time.time()

        total_processed = 0
        total_skipped = 0
        errors = []

        if options['refresh']:
            cleared = self._clear_enrichment(dry_run, do_developer, do_synced)
            self._log(f'Cleared enrichment for {cleared} records. Running full enrichment...')
            total_processed, total_skipped, errors = self._enrich_full(dry_run, do_developer, do_synced)
        elif options['new_layers_only']:
            total_processed, total_skipped, errors = self._enrich_for_new_layers(dry_run, do_developer, do_synced)
        elif options['full']:
            total_processed, total_skipped, errors = self._enrich_full(dry_run, do_developer, do_synced)
        elif options['new_listings_only']:
            total_processed, total_skipped, errors = self._enrich_new_listings_only(dry_run, do_developer, do_synced)
        else:
            total_processed, total_skipped, errors = self._enrich_incremental(dry_run, do_developer, do_synced)

        if errors:
            for msg in errors:
                self.stdout.write(self.style.ERROR(msg))
                logger.error(msg)
            self.stdout.write(self.style.ERROR(f'Enrichment finished with {len(errors)} error(s).'))
            sys.exit(1)

        elapsed = time.time() - start_time
        self._log(f'Enrichment complete: {total_processed} processed, {total_skipped} skipped in {elapsed:.1f}s')
        self.stdout.write(
            self.style.SUCCESS(
                f'Enrichment complete: {total_processed} listings processed, {total_skipped} skipped in {elapsed:.1f}s'
            )
        )

    def _log(self, msg: str):
        """Write to stdout and logger so progress is visible in console and logs."""
        self.stdout.write(msg)
        logger.info(msg)

    def _clear_enrichment(self, dry_run: bool, do_developer: bool, do_synced: bool) -> int:
        """Clear enriched_layers and enriched_at for all records in scope. Returns count cleared."""
        cleared = 0
        if dry_run:
            if do_developer:
                c = DeveloperListing.objects.filter(is_active=True).count()
                cleared += c
                self._log(f'[dry-run] Would clear DeveloperListing: {c} rows')
            if do_synced:
                for model, label in SYNCED_TABLES:
                    c = model.objects.count()
                    cleared += c
                    self._log(f'[dry-run] Would clear {label}: {c} rows')
            return cleared
        if do_developer:
            c = DeveloperListing.objects.filter(is_active=True).update(enriched_layers=[], enriched_at=None)
            cleared += c
            self._log(f'Cleared DeveloperListing: {c} rows')
        if do_synced:
            for model, label in SYNCED_TABLES:
                c = model.objects.update(enriched_layers=[], enriched_at=None)
                cleared += c
                self._log(f'Cleared {label}: {c} rows')
        return cleared

    def _enrich_full(self, dry_run: bool, do_developer: bool, do_synced: bool):
        processed, skipped = 0, 0
        errors = []
        if do_developer:
            qs = DeveloperListing.objects.filter(is_active=True)
            total = qs.count()
            self._log(f'Processing DeveloperListing (total={total})...')
            try:
                if dry_run:
                    processed += total
                    self._log(f'  [dry-run] Would process {total}')
                else:
                    p, s = enrich_listings_queryset(qs, update_location_point=True)
                    processed += p
                    skipped += s
                    self._log(f'  DeveloperListing: processed={p}, skipped={s}')
            except Exception as e:
                errors.append(f'DeveloperListing: {e}')
                logger.exception('Enrich DeveloperListing failed')
        if do_synced:
            for model, label in SYNCED_TABLES:
                qs = model.objects.all()
                total = qs.count()
                self._log(f'Processing {label} (total={total})...')
                try:
                    if dry_run:
                        processed += total
                        self._log(f'  [dry-run] Would process {total}')
                    else:
                        p, s = enrich_synced_queryset(qs, update_location_point=True)
                        processed += p
                        skipped += s
                        self._log(f'  {label}: processed={p}, skipped={s}')
                except Exception as e:
                    errors.append(f'{label}: {e}')
                    logger.exception('Enrich %s failed', label)
        return processed, skipped, errors

    def _enrich_new_listings_only(self, dry_run: bool, do_developer: bool, do_synced: bool):
        processed, skipped = 0, 0
        errors = []
        self._log('Phase: never-enriched only (enriched_at is null)')
        if do_developer:
            qs = DeveloperListing.objects.filter(is_active=True, enriched_at__isnull=True)
            n = qs.count()
            self._log(f'  DeveloperListing never-enriched: {n}')
            try:
                if dry_run:
                    processed += n
                else:
                    p, s = enrich_listings_queryset(qs, update_location_point=True)
                    processed += p
                    skipped += s
                    self._log(f'  DeveloperListing: processed={p}, skipped={s}')
            except Exception as e:
                errors.append(f'DeveloperListing: {e}')
                logger.exception('Enrich DeveloperListing failed')
        if do_synced:
            for model, label in SYNCED_TABLES:
                qs = model.objects.filter(enriched_at__isnull=True)
                n = qs.count()
                self._log(f'  {label} never-enriched: {n}')
                try:
                    if dry_run:
                        processed += n
                    else:
                        p, s = enrich_synced_queryset(qs, update_location_point=True)
                        processed += p
                        skipped += s
                        self._log(f'  {label}: processed={p}, skipped={s}')
                except Exception as e:
                    errors.append(f'{label}: {e}')
                    logger.exception('Enrich %s failed', label)
        return processed, skipped, errors

    def _enrich_incremental(self, dry_run: bool, do_developer: bool, do_synced: bool):
        processed = 0
        skipped = 0
        errors = []

        self._log('Phase 1: never-enriched and stale')
        if do_developer:
            try:
                qs_new = DeveloperListing.objects.filter(is_active=True, enriched_at__isnull=True)
                n = qs_new.count()
                self._log(f'  DeveloperListing new: {n}')
                if dry_run:
                    processed += n
                else:
                    p, s = enrich_listings_queryset(qs_new, update_location_point=True)
                    processed += p
                    skipped += s
                qs_stale = DeveloperListing.objects.filter(
                    is_active=True,
                    enriched_at__isnull=False,
                    updated_at__gt=F('enriched_at'),
                )
                n = qs_stale.count()
                self._log(f'  DeveloperListing stale: {n}')
                if dry_run:
                    processed += n
                else:
                    p, s = enrich_listings_queryset(qs_stale, update_location_point=True)
                    processed += p
                    skipped += s
            except Exception as e:
                errors.append(f'DeveloperListing: {e}')
                logger.exception('Enrich DeveloperListing failed')

        if do_synced:
            for model, label in SYNCED_TABLES:
                try:
                    qs_new = model.objects.filter(enriched_at__isnull=True)
                    n_new = qs_new.count()
                    if dry_run:
                        processed += n_new
                    else:
                        p, s = enrich_synced_queryset(qs_new, update_location_point=True)
                        processed += p
                        skipped += s
                    qs_stale = model.objects.filter(
                        enriched_at__isnull=False,
                        synced_at__gt=F('enriched_at'),
                    )
                    n_stale = qs_stale.count()
                    if dry_run:
                        processed += n_stale
                    else:
                        p, s = enrich_synced_queryset(qs_stale, update_location_point=True)
                        processed += p
                        skipped += s
                    self._log(f'  {label}: new={n_new}, stale={n_stale}')
                except Exception as e:
                    errors.append(f'{label}: {e}')
                    logger.exception('Enrich %s failed', label)

        since = timezone.now() - timedelta(hours=24)
        new_layers = DataLayer.objects.filter(
            is_processed=True,
            created_at__gte=since,
        ).exclude(category__code='DEVELOPER_LISTING')
        num_new_layers = new_layers.count()
        if num_new_layers:
            self._log(f'Phase 2: listings near new layers (last 24h): {num_new_layers} layers')
        for layer in new_layers:
            try:
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
            except Exception as e:
                errors.append(f'Layer {layer.id} ({layer.slug}): {e}')
                logger.exception('Enrich near layer %s failed', layer.slug)

        return processed, skipped, errors

    def _enrich_for_new_layers(self, dry_run: bool, do_developer: bool, do_synced: bool):
        since = timezone.now() - timedelta(hours=24)
        new_layers = list(
            DataLayer.objects.filter(
                is_processed=True,
                created_at__gte=since,
            ).exclude(category__code='DEVELOPER_LISTING')
        )
        num_layers = len(new_layers)
        self._log(f'Phase: listings near new layers (last 24h): {num_layers} layers')

        processed = 0
        skipped = 0
        errors = []
        for layer in new_layers:
            try:
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
            except Exception as e:
                errors.append(f'Layer {layer.id} ({layer.slug}): {e}')
                logger.exception('Enrich near layer %s failed', layer.slug)

        if processed == 0 and not dry_run and not errors:
            self._log('No listings in range of new layers.')
        else:
            self._log(f'Near new layers: processed={processed}, skipped={skipped}')
        return processed, skipped, errors
