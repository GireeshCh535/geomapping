"""
Rebuild maps_layer_listing_link from enriched_layers on Synced* tables only.

Run after enrich_listing_layers or to repair drift. Uses stored JSON only (no spatial recompute).
After adding order denormalization columns (migrate 0047), run backfill_listing_order_metrics so
LayerListingLink rows get order_* / listing_* timestamps; or rely on this command to refresh links
(which calls refresh_layer_listing_links_from_stored_enrichment and copies metrics from each Synced* row).

Usage:
  python manage.py materialize_layer_listing_links
  python manage.py materialize_layer_listing_links --clear
  python manage.py materialize_layer_listing_links --dry-run
"""

from django.core.management.base import BaseCommand

from maps.models import (
    LayerListingLink,
    SyncedDeveloperLand,
    SyncedDeveloperPlot,
    SyncedLand,
    SyncedPlot,
)
from maps.listing_layer_enrichment_service import refresh_layer_listing_links_from_stored_enrichment


SYNCED_MODELS = [
    (SyncedLand, 'SyncedLand'),
    (SyncedPlot, 'SyncedPlot'),
    (SyncedDeveloperLand, 'SyncedDeveloperLand'),
    (SyncedDeveloperPlot, 'SyncedDeveloperPlot'),
]


class Command(BaseCommand):
    help = 'Populate LayerListingLink rows from enriched_layers on SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all LayerListingLink rows before rebuilding',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print counts only; do not write',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if options['clear'] and not dry_run:
            n_del = LayerListingLink.objects.count()
            LayerListingLink.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Cleared {n_del} LayerListingLink row(s).'))
        elif options['clear'] and dry_run:
            n_del = LayerListingLink.objects.count()
            self.stdout.write(self.style.WARNING(f'[dry-run] Would clear {n_del} LayerListingLink row(s).'))

        would_process = 0
        processed = 0

        for model, label in SYNCED_MODELS:
            qs = model.objects.all().order_by('id')
            n = qs.count()
            self.stdout.write(f'{label} rows: {n}')
            would_process += n
            if dry_run:
                continue
            k = 0
            for rec in qs.iterator():
                refresh_layer_listing_links_from_stored_enrichment(rec)
                k += 1
                processed += 1
            self.stdout.write(f'  Refreshed links for {k} {label} row(s).')

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'[dry-run] Would process {would_process} synced row(s).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Materialize complete ({processed} synced row(s) processed).'))
