# maps/management/commands/generate_land_plot_mvt_tiles.py
"""
Generate local MVT tiles for SyncedLand and SyncedPlot points.
Follows the same pattern as universal_line_styled_tile_generator and
universal_masterplan_tile_generator:
- Iterate every tile in bounds for each zoom (full grid), don't skip tiles.
- Always write a tile: with features or empty MVT, so zooming in never
  causes points to "disappear" (no 404s for requested tiles).
- Use a small buffer when querying points so edge points are included.
- 3 price tiers (low / mid / high) per type for coloring.
"""

from pathlib import Path

import mapbox_vector_tile
import mercantile
from django.conf import settings
from django.contrib.gis.geos import Polygon
from django.core.management.base import BaseCommand

from maps.models import SyncedLand, SyncedPlot

# Small buffer in degrees when querying points (avoids missing points on tile edges)
TILE_QUERY_BUFFER_DEG = 1e-6


def get_price_percentiles():
    """Compute 33rd and 66th percentile of total_price per type for 3 tiers."""
    land_prices = list(
        SyncedLand.objects.filter(
            location_point__isnull=False
        ).exclude(
            total_price__isnull=True
        ).values_list("total_price", flat=True)
    )
    land_prices = [float(p) for p in land_prices if p is not None and p > 0]
    land_prices.sort()
    n_land = len(land_prices)
    land_p33 = land_prices[int(n_land * 0.33)] if n_land else 0
    land_p66 = land_prices[int(n_land * 0.66)] if n_land else 0

    plot_prices = list(
        SyncedPlot.objects.filter(
            location_point__isnull=False
        ).exclude(
            total_price__isnull=True
        ).values_list("total_price", flat=True)
    )
    plot_prices = [float(p) for p in plot_prices if p is not None and p > 0]
    plot_prices.sort()
    n_plot = len(plot_prices)
    plot_p33 = plot_prices[int(n_plot * 0.33)] if n_plot else 0
    plot_p66 = plot_prices[int(n_plot * 0.66)] if n_plot else 0

    return {
        "land": (land_p33, land_p66),
        "plot": (plot_p33, plot_p66),
    }


def tier_for_price(price, p33, p66):
    """Return 1=low, 2=mid, 3=high. None price -> 1."""
    if price is None or price <= 0:
        return 1
    if price <= p33:
        return 1
    if price <= p66:
        return 2
    return 3


class Command(BaseCommand):
    help = "Generate local MVT tiles for land/plot points with 3 price-tier colors"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            type=str,
            default="land_plot_tiles",
            help="Output directory for tiles (default: land_plot_tiles)",
        )
        parser.add_argument(
            "--min-zoom",
            type=int,
            default=8,
            help="Min zoom (default 8)",
        )
        parser.add_argument(
            "--max-zoom",
            type=int,
            default=14,
            help="Max zoom (default 14)",
        )
        parser.add_argument(
            "--bounds",
            type=str,
            default="68,8,96,32",
            help="West,south,east,north (default: India 68,8,96,32)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit number of tiles (for testing)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Verbose output",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip writing if tile file already exists (like universal generators)",
        )

    def handle(self, *args, **options):
        output_dir = options["output_dir"]
        min_zoom = options["min_zoom"]
        max_zoom = options["max_zoom"]
        bounds_str = options["bounds"]
        limit = options["limit"]
        verbose = options["verbose"]
        skip_existing = options.get("skip_existing", False)

        try:
            w, s, e, n = [float(x) for x in bounds_str.split(",")]
        except Exception:
            self.stdout.write(self.style.ERROR("Invalid --bounds; use west,south,east,north"))
            return

        out_path = Path(output_dir)
        if not out_path.is_absolute():
            out_path = Path(settings.BASE_DIR) / out_path
        out_path.mkdir(parents=True, exist_ok=True)
        self.stdout.write(f"Output: {out_path}")
        self.stdout.write(f"Bounds: {w},{s},{e},{n}  Zoom: {min_zoom}-{max_zoom}")

        percentiles = get_price_percentiles()
        self.stdout.write(
            f"Land price tiers (33%%/66%%): {percentiles['land'][0]:.0f} / {percentiles['land'][1]:.0f}"
        )
        self.stdout.write(
            f"Plot price tiers (33%%/66%%): {percentiles['plot'][0]:.0f} / {percentiles['plot'][1]:.0f}"
        )

        land_p33, land_p66 = percentiles["land"]
        plot_p33, plot_p66 = percentiles["plot"]

        # Expand bounds slightly (like universal_line_styled) so full tile grid is generated
        tile_size_deg = 360.0 / (2 ** max_zoom)
        buffer_deg = min(tile_size_deg * 2, 0.01)
        w_exp, s_exp = w - buffer_deg, s - buffer_deg
        e_exp, n_exp = e + buffer_deg, n + buffer_deg

        total_written = 0
        total_skipped_existing = 0

        for zoom in range(min_zoom, max_zoom + 1):
            tiles_for_zoom = list(mercantile.tiles(w_exp, s_exp, e_exp, n_exp, zooms=[zoom]))
            if limit is not None:
                tiles_for_zoom = tiles_for_zoom[:limit]
                if limit <= 0:
                    continue
            zoom_dir = out_path / str(zoom)
            zoom_dir.mkdir(parents=True, exist_ok=True)
            written_zoom = 0
            skipped_zoom = 0

            for tile in tiles_for_zoom:
                z, x, y = tile.z, tile.x, tile.y
                tile_dir = zoom_dir / str(x)
                tile_file = tile_dir / f"{y}.mvt"
                if skip_existing and tile_file.exists():
                    total_skipped_existing += 1
                    skipped_zoom += 1
                    continue

                bounds = mercantile.bounds(x, y, z)
                # Buffered bbox so points on tile edges are included (consistent across zooms)
                bbox = Polygon.from_bbox(
                    (
                        bounds.west - TILE_QUERY_BUFFER_DEG,
                        bounds.south - TILE_QUERY_BUFFER_DEG,
                        bounds.east + TILE_QUERY_BUFFER_DEG,
                        bounds.north + TILE_QUERY_BUFFER_DEG,
                    )
                )

                features = []

                # Lands in this tile
                lands = SyncedLand.objects.filter(
                    location_point__isnull=False,
                    location_point__intersects=bbox,
                ).only(
                    "backend_id", "total_price", "total_land_size", "slug", "status",
                    "location_point", "lat", "long",
                )
                for obj in lands:
                    pt = obj.location_point
                    if not pt:
                        continue
                    lon, lat = pt.x, pt.y
                    # Only include if inside strict tile bounds (buffer was for query only)
                    if not (bounds.west <= lon <= bounds.east and bounds.south <= lat <= bounds.north):
                        continue
                    price = obj.total_price
                    if price is not None:
                        try:
                            price = float(price)
                        except (TypeError, ValueError):
                            price = None
                    t = tier_for_price(price, land_p33, land_p66)
                    size = obj.total_land_size
                    if size is not None:
                        try:
                            size = float(size)
                        except (TypeError, ValueError):
                            size = None
                    features.append({
                        "lon": lon,
                        "lat": lat,
                        "type": "land",
                        "backend_id": obj.backend_id,
                        "total_price": price or 0,
                        "size": size,
                        "size_label": "acres",
                        "slug": (obj.slug or "")[:200],
                        "status": obj.status or "",
                        "tier": t,
                        "sort_key": price or 0,
                    })

                # Plots in this tile
                plots = SyncedPlot.objects.filter(
                    location_point__isnull=False,
                    location_point__intersects=bbox,
                ).only(
                    "backend_id", "total_price", "total_plot_size", "slug", "status",
                    "location_point", "lat", "long",
                )
                for obj in plots:
                    pt = obj.location_point
                    if not pt:
                        continue
                    lon, lat = pt.x, pt.y
                    if not (bounds.west <= lon <= bounds.east and bounds.south <= lat <= bounds.north):
                        continue
                    price = obj.total_price
                    if price is not None:
                        try:
                            price = float(price)
                        except (TypeError, ValueError):
                            price = None
                    t = tier_for_price(price, plot_p33, plot_p66)
                    size = obj.total_plot_size
                    if size is not None:
                        try:
                            size = float(size)
                        except (TypeError, ValueError):
                            size = None
                    features.append({
                        "lon": lon,
                        "lat": lat,
                        "type": "plot",
                        "backend_id": obj.backend_id,
                        "total_price": price or 0,
                        "size": size,
                        "size_label": "sqyd",
                        "slug": (obj.slug or "")[:200],
                        "status": obj.status or "",
                        "tier": t,
                        "sort_key": price or 0,
                    })

                # Sort by sort_key ascending so higher price is drawn last (on top)
                features.sort(key=lambda f: f["sort_key"])

                # Build MVT: Point geometry in tile coords (0-4096), properties. Always write (empty or not).
                extent = 4096
                mvt_features = []
                for f in features:
                    lon, lat = f["lon"], f["lat"]
                    tile_x = int(
                        (lon - bounds.west) / (bounds.east - bounds.west) * extent
                    )
                    tile_y = int(
                        (bounds.north - lat) / (bounds.north - bounds.south) * extent
                    )
                    geom = {
                        "type": "Point",
                        "coordinates": [tile_x, tile_y],
                    }
                    props = {
                        "id": f["backend_id"],
                        "type": f["type"],
                        "total_price": f["total_price"],
                        "size": f["size"] if f["size"] is not None else 0,
                        "size_label": f["size_label"],
                        "slug": f["slug"],
                        "status": f["status"],
                        "tier": f["tier"],
                        "sort_key": f["sort_key"],
                    }
                    mvt_features.append({
                        "geometry": geom,
                        "properties": props,
                    })

                layer_data = [{
                    "name": "landplot",
                    "features": mvt_features,
                    "version": 2,
                    "extent": extent,
                }]
                mvt_bytes = mapbox_vector_tile.encode(layer_data)

                tile_dir.mkdir(parents=True, exist_ok=True)
                tile_file.write_bytes(mvt_bytes)
                written_zoom += 1
                total_written += 1
                if verbose and total_written <= 5:
                    self.stdout.write(f"  {z}/{x}/{y}.mvt  features={len(features)}")

            self.stdout.write(f"  Zoom {zoom}: wrote {written_zoom} tiles, skipped existing {skipped_zoom}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Written {total_written} tiles total, skipped existing {total_skipped_existing}"
            )
        )
