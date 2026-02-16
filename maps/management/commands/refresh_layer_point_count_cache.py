"""
Refresh LayerPointCountCache for fast /api/layer-point-counts/ responses.

Use after deploy to backfill cache, or to repair cache for specific layers.
When no --layer-ids given, refreshes all processed layers (excluding DEVELOPER_LISTING).

Usage:
  python manage.py refresh_layer_point_count_cache
  python manage.py refresh_layer_point_count_cache --layer-ids 1,2,3
  python manage.py refresh_layer_point_count_cache --within-km 30
"""

from django.core.management.base import BaseCommand

from maps.listing_layer_enrichment_service import refresh_layer_point_count_cache, NEARBY_THRESHOLD_KM


class Command(BaseCommand):
    help = 'Refresh layer point count cache (all processed layers or given layer IDs).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--layer-ids',
            type=str,
            help='Comma-separated layer IDs to refresh (default: all processed layers)',
        )
        parser.add_argument(
            '--within-km',
            type=float,
            default=NEARBY_THRESHOLD_KM,
            help=f'Within-km radius for nearby count (default: {NEARBY_THRESHOLD_KM})',
        )

    def handle(self, *args, **options):
        layer_ids = None
        if options.get('layer_ids'):
            try:
                layer_ids = [int(x.strip()) for x in options['layer_ids'].split(',') if x.strip()]
            except ValueError:
                self.stderr.write(self.style.ERROR('Invalid --layer-ids: must be comma-separated integers'))
                return
        within_km = options.get('within_km')
        if within_km is None:
            within_km = NEARBY_THRESHOLD_KM
        self.stdout.write(
            f'Refreshing layer point count cache (within_km={within_km}, '
            f'layers={"all" if layer_ids is None else str(layer_ids)})...'
        )
        refresh_layer_point_count_cache(layer_ids=layer_ids, within_km=within_km)
        self.stdout.write(self.style.SUCCESS('Done.'))
