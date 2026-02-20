"""
Decode one land/plot MVT tile and print bounds + first N features with decoded (lon, lat).

Use after generating tiles to verify coordinates (e.g. India: lon 68-96, lat 8-32).

Usage:
  python manage.py debug_land_plot_tile --z 10 --x 707 --y 415 --limit 5
  python manage.py debug_land_plot_tile  # uses defaults (tile covering ~Hyderabad)
"""

from pathlib import Path

import mapbox_vector_tile
import mercantile
from django.conf import settings
from django.core.management.base import BaseCommand

EXTENT = 4096


class Command(BaseCommand):
    help = "Decode one land/plot MVT tile and print bounds + decoded (lon, lat) for first N features"

    def add_arguments(self, parser):
        parser.add_argument(
            "--z",
            type=int,
            default=10,
            help="Tile zoom (default 10)",
        )
        parser.add_argument(
            "--x",
            type=int,
            default=707,
            help="Tile x (default 707, India)",
        )
        parser.add_argument(
            "--y",
            type=int,
            default=415,
            help="Tile y (default 415, India)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=5,
            help="Max features to print (default 5)",
        )
        parser.add_argument(
            "--output-dir",
            type=str,
            default="land_plot_tiles",
            help="Tile output directory (default land_plot_tiles)",
        )

    def handle(self, *args, **options):
        z = options["z"]
        x = options["x"]
        y = options["y"]
        limit = options["limit"]
        output_dir = options["output_dir"]

        out_path = Path(output_dir)
        if not out_path.is_absolute():
            out_path = Path(settings.BASE_DIR) / out_path
        tile_file = out_path / str(z) / str(x) / f"{y}.mvt"

        if not tile_file.is_file():
            self.stdout.write(self.style.ERROR(f"Tile not found: {tile_file}"))
            return

        bounds = mercantile.bounds(x, y, z)
        west, south, east, north = bounds.west, bounds.south, bounds.east, bounds.north

        self.stdout.write(f"Tile: z={z} x={x} y={y}")
        self.stdout.write(f"Bounds: west={west} south={south} east={east} north={north}")
        self.stdout.write("")

        data = tile_file.read_bytes()
        decoded = mapbox_vector_tile.decode(data)

        if "landplot" not in decoded:
            self.stdout.write(self.style.WARNING("No 'landplot' layer in tile."))
            return

        layer = decoded["landplot"]
        layer_extent = layer.get("extent", EXTENT)
        features = layer.get("features", [])

        self.stdout.write(f"Layer extent: {layer_extent}, features: {len(features)}")
        self.stdout.write("")

        for i, feat in enumerate(features[:limit]):
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates")
            props = feat.get("properties") or {}
            if coords is None:
                self.stdout.write(f"  Feature {i}: no coordinates")
                continue
            # Point: [x, y] or sometimes [[x, y]]
            if isinstance(coords[0], (list, tuple)):
                coords = coords[0]
            if len(coords) < 2:
                self.stdout.write(f"  Feature {i}: invalid coordinates")
                continue
            tile_x, tile_y = float(coords[0]), float(coords[1])
            lon = west + (tile_x / layer_extent) * (east - west)
            lat = north - (tile_y / layer_extent) * (north - south)
            fid = props.get("id", "?")
            ftype = props.get("type", "?")
            marker_id = props.get("marker_id", "?")
            self.stdout.write(
                f"  Feature {i}: id={fid} type={ftype} marker_id={marker_id} "
                f"-> decoded (lon={lon:.6f}, lat={lat:.6f})"
            )

        if len(features) > limit:
            self.stdout.write(f"  ... and {len(features) - limit} more features")
