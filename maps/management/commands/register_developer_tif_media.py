#!/usr/bin/env python3
"""
Register a developer land/plot TIF in the DB when PNG tiles are already on R2.

Example (tiles already synced to R2):
  python manage.py register_developer_tif_media \\
    --listing-type developerland \\
    --listing-id 506 \\
    --media-id 1 \\
    --tif-path /app/data/506.tif \\
    --s3-tile-path developer_data/developerland/506/506.tif \\
    --min-zoom 12 --max-zoom 18
"""

from pathlib import Path

import rasterio
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from rasterio.warp import transform_bounds

from maps.developer_listing_tile_service import DeveloperListingTileService
from maps.models import DeveloperListing, DeveloperListingMedia, TIFMetadata


class Command(BaseCommand):
    help = "Register developer listing TIF media + metadata (tiles already on R2)"

    def add_arguments(self, parser):
        parser.add_argument("--listing-type", required=True, choices=["developerland", "developerplot"])
        parser.add_argument("--listing-id", type=int, required=True, help="backend_listing_id")
        parser.add_argument("--media-id", type=int, required=True, help="backend_media_id from 1acre")
        parser.add_argument("--tif-path", required=True, help="Path to GeoTIFF inside container")
        parser.add_argument("--s3-tile-path", required=True, help="e.g. developer_data/developerland/506/506.tif")
        parser.add_argument("--file-name", default=None, help="Defaults to tif filename")
        parser.add_argument("--file-url", default="", help="CloudFront URL (optional)")
        parser.add_argument("--min-zoom", type=int, default=12)
        parser.add_argument("--max-zoom", type=int, default=18)

    def handle(self, *args, **options):
        tif_path = Path(options["tif_path"])
        if not tif_path.exists():
            raise CommandError(f"GeoTIFF not found: {tif_path}")

        file_name = options["file_name"] or tif_path.name
        s3_tile_path = options["s3_tile_path"].strip().strip("/")
        if not s3_tile_path.startswith("developer_data/"):
            s3_tile_path = f"developer_data/{s3_tile_path}"

        with rasterio.open(tif_path) as src:
            west, south, east, north = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
            tif_metadata = {
                "source_crs": str(src.crs) if src.crs else "",
                "source_width": src.width,
                "source_height": src.height,
                "source_bands": src.count,
                "bounds": {"west": west, "south": south, "east": east, "north": north},
            }

        try:
            listing = DeveloperListing.objects.get(
                listing_type=options["listing_type"],
                backend_listing_id=options["listing_id"],
            )
        except DeveloperListing.DoesNotExist:
            raise CommandError(
                f"No DeveloperListing for {options['listing_type']} id={options['listing_id']}. "
                "Create via webhook/API first."
            )

        file_url = options["file_url"] or f"https://placeholder/{file_name}"

        media, created = DeveloperListingMedia.objects.update_or_create(
            listing=listing,
            backend_media_id=options["media_id"],
            defaults={
                "media_type": "file",
                "file_name": file_name,
                "file_url": file_url,
                "is_tif": True,
                "s3_tile_path": s3_tile_path,
                "tiles_generated": True,
                "tiles_generation_completed_at": timezone.now(),
                "tiles_generation_error": "",
                "total_tiles_generated": 0,
                "media_data": {
                    "id": options["media_id"],
                    "file_name": file_name,
                    "is_tif": True,
                    "s3_tile_path": s3_tile_path,
                },
            },
        )

        TIFMetadata.objects.update_or_create(
            media=media,
            defaults={
                "source_crs": tif_metadata["source_crs"],
                "source_width": tif_metadata["source_width"],
                "source_height": tif_metadata["source_height"],
                "source_bands": tif_metadata["source_bands"],
                "bounds_west": west,
                "bounds_south": south,
                "bounds_east": east,
                "bounds_north": north,
                "min_zoom": options["min_zoom"],
                "max_zoom": options["max_zoom"],
                "tif_data": tif_metadata,
            },
        )

        DeveloperListingTileService()._create_datalayer_and_geofeature(
            listing=listing,
            media=media,
            tif_metadata=tif_metadata,
            s3_tile_path=s3_tile_path,
        )

        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Updated'} media id={media.id} for listing db_id={listing.id} "
            f"(backend {options['listing_id']})"
        ))
        self.stdout.write(f"  s3_tile_path: {media.s3_tile_path}")
        self.stdout.write(f"  bounds (WGS84): {west}, {south}, {east}, {north}")
