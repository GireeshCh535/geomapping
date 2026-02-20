"""
Fix location_point for SyncedLand and SyncedPlot from scalar lat/long columns.

Your DB has location_point stored as (latitude, longitude) but WGS84 expects (longitude, latitude).
We use raw SQL ST_MakePoint(longitude, latitude) so PostGIS gets the correct order regardless
of Django serialization. Then spatial queries and MVT output will match.

Usage:
  python manage.py fix_land_plot_location_point
  python manage.py fix_land_plot_location_point --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import connection

from maps.models import SyncedLand, SyncedPlot


class Command(BaseCommand):
    help = "Set location_point from lat/long using raw SQL so (lon, lat) is stored correctly in PostGIS"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print what would be updated",
        )

    def _update_table(self, table, dry_run):
        # Use raw SQL: ST_MakePoint(longitude, latitude) so PostGIS stores (x=lon, y=lat)
        with connection.cursor() as cursor:
            if table == "synced_land":
                cursor.execute(
                    """
                    UPDATE synced_land
                    SET location_point = ST_SetSRID(ST_MakePoint("long", "lat"), 4326)::geography
                    WHERE "lat" IS NOT NULL AND "long" IS NOT NULL
                    AND ("long" BETWEEN -180 AND 180 AND "lat" BETWEEN -90 AND 90)
                    """
                )
            else:
                cursor.execute(
                    """
                    UPDATE synced_plot
                    SET location_point = ST_SetSRID(ST_MakePoint("long", "lat"), 4326)::geography
                    WHERE "lat" IS NOT NULL AND "long" IS NOT NULL
                    AND ("long" BETWEEN -180 AND 180 AND "lat" BETWEEN -90 AND 90)
                    """
                )
            count = cursor.rowcount
        return count

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write("Dry run: no changes will be saved.")
            # Count how many would be updated
            land_count = SyncedLand.objects.filter(lat__isnull=False, long__isnull=False).count()
            plot_count = SyncedPlot.objects.filter(lat__isnull=False, long__isnull=False).count()
            self.stdout.write(f"SyncedLand: would update {land_count} rows.")
            self.stdout.write(f"SyncedPlot: would update {plot_count} rows.")
        else:
            land_count = self._update_table("synced_land", dry_run)
            plot_count = self._update_table("synced_plot", dry_run)
            self.stdout.write(f"SyncedLand: updated {land_count} rows.")
            self.stdout.write(f"SyncedPlot: updated {plot_count} rows.")
        self.stdout.write(
            self.style.SUCCESS(
                "Done. Regenerate MVT tiles: python manage.py generate_land_plot_mvt_tiles --min-zoom 2 --max-zoom 14"
            )
        )
