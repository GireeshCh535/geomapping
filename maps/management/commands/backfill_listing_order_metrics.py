"""
Recompute denormalized ordering columns on Synced* tables and copy them (+ timestamps)
onto maps_layer_listing_link.

Flow:
1. migrate (adds nullable columns via 0047_listing_order_denorm_fields)
2. python manage.py backfill_listing_order_metrics
3. Optional: python manage.py materialize_layer_listing_links  # only if links must be rebuilt from JSON

Step 2 updates Synced* from existing total_price / size columns, then runs SQL UPDATE … FROM
so each LayerListingLink row picks up metrics from its listing row (by source + listing_pk).

Usage:
  python manage.py backfill_listing_order_metrics
  python manage.py backfill_listing_order_metrics --skip-synced   # only refresh link table from synced
  python manage.py backfill_listing_order_metrics --skip-links    # only fill Synced* columns
  python manage.py backfill_listing_order_metrics --batch-size 1000
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from maps.listing_order_metrics import listing_order_metrics_for_synced_record
from maps.models import (
    LayerListingLink,
    SyncedDeveloperLand,
    SyncedDeveloperPlot,
    SyncedLand,
    SyncedPlot,
)

ORDER_FIELDS = (
    'order_total_price_in_lakhs',
    'order_total_size_in_acres',
    'order_price_per_acre_in_lakhs',
)

SYNCED_MODELS = (SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot)


class Command(BaseCommand):
    help = 'Backfill order_* on Synced* and matching columns on LayerListingLink (run after migrate 0047).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-synced',
            action='store_true',
            help='Skip recomputing columns on Synced* tables (only update LayerListingLink from synced).',
        )
        parser.add_argument(
            '--skip-links',
            action='store_true',
            help='Only update Synced* tables; do not run SQL to refresh LayerListingLink.',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Rows per bulk_update when filling Synced* tables (default 500).',
        )

    def _backfill_model(self, model, batch_size):
        label = model.__name__
        self.stdout.write(f'Backfilling {label}…')
        batch = []
        total = 0
        for row in model.objects.all().order_by('pk').iterator(chunk_size=batch_size):
            m = listing_order_metrics_for_synced_record(row)
            row.order_total_price_in_lakhs = m['order_total_price_in_lakhs']
            row.order_total_size_in_acres = m['order_total_size_in_acres']
            row.order_price_per_acre_in_lakhs = m['order_price_per_acre_in_lakhs']
            batch.append(row)
            if len(batch) >= batch_size:
                model.objects.bulk_update(batch, ORDER_FIELDS)
                total += len(batch)
                self.stdout.write(f'  {label}: {total} row(s) updated')
                batch = []
        if batch:
            model.objects.bulk_update(batch, ORDER_FIELDS)
            total += len(batch)
            self.stdout.write(f'  {label}: {total} row(s) updated (done)')

    def _sql_refresh_links(self):
        ll = LayerListingLink._meta.db_table
        specs = [
            ('land', SyncedLand._meta.db_table, 'id'),
            ('plot', SyncedPlot._meta.db_table, 'id'),
            ('developer_land', SyncedDeveloperLand._meta.db_table, 'id'),
            ('developer_plot', SyncedDeveloperPlot._meta.db_table, 'id'),
        ]
        sql_tpl = """
            UPDATE {ll} AS ll
            SET
                order_total_price_in_lakhs = s.order_total_price_in_lakhs,
                order_total_size_in_acres = s.order_total_size_in_acres,
                order_price_per_acre_in_lakhs = s.order_price_per_acre_in_lakhs,
                listing_created_at = s.created_at,
                listing_updated_at = s.updated_at
            FROM {synced} AS s
            WHERE ll.source = %s
              AND ll.listing_pk = s.{pk}
        """
        with transaction.atomic():
            with connection.cursor() as cur:
                for source, synced_table, pkcol in specs:
                    q = sql_tpl.format(ll=ll, synced=synced_table, pk=pkcol)
                    cur.execute(q, [source])
                    self.stdout.write(
                        f'  LayerListingLink ← {synced_table} ({source}): {cur.rowcount} row(s) updated'
                    )

    def handle(self, *args, **options):
        batch_size = max(1, int(options['batch_size'] or 500))
        if not options['skip_synced']:
            for m in SYNCED_MODELS:
                self._backfill_model(m, batch_size)
        else:
            self.stdout.write(self.style.WARNING('Skipping Synced* backfill (--skip-synced).'))

        if not options['skip_links']:
            self.stdout.write('Refreshing LayerListingLink from Synced* via SQL…')
            self._sql_refresh_links()
        else:
            self.stdout.write(self.style.WARNING('Skipping LayerListingLink SQL refresh (--skip-links).'))

        self.stdout.write(self.style.SUCCESS('backfill_listing_order_metrics finished.'))
