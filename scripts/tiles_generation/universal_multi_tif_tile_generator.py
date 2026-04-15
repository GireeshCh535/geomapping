#!/usr/bin/env python3
"""
Multi GeoTIFF → one tile pyramid
Same WGS84 reprojection and per-pixel sampling as universal_tif_tile_generator.py,
but accepts multiple inputs and composites them (source-over: first file on bottom).
"""

import argparse
import json
import logging
import multiprocessing as mp
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import mercantile
import numpy as np
from PIL import Image
from rasterio.transform import rowcol

# Allow `python path/to/universal_multi_tif_tile_generator.py` from repo root
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from universal_tif_tile_generator import UniversalTIFTileGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _src_over_rgba(dst: tuple, src: tuple) -> tuple:
    """Porter–Duff source-over; inputs/outputs are (R, G, B, A) uint8."""
    dr, dg, db, da = (float(x) for x in dst)
    sr, sg, sb, sa = (float(x) for x in src)
    if sa < 1e-6:
        return (int(dr), int(dg), int(db), int(da))
    if da < 1e-6:
        return (int(sr), int(sg), int(sb), int(sa))
    sa_f, da_f = sa / 255.0, da / 255.0
    out_a = sa_f + da_f * (1.0 - sa_f)
    if out_a < 1e-9:
        return (0, 0, 0, 0)
    inv = 1.0 / out_a
    out_r = (sr * sa_f + dr * da_f * (1.0 - sa_f)) * inv
    out_g = (sg * sa_f + dg * da_f * (1.0 - sa_f)) * inv
    out_b = (sb * sa_f + db * da_f * (1.0 - sa_f)) * inv
    return (
        int(max(0, min(255, round(out_r)))),
        int(max(0, min(255, round(out_g)))),
        int(max(0, min(255, round(out_b)))),
        int(max(0, min(255, round(out_a * 255.0)))),
    )


def _union_bounds(bounds_list: list) -> dict:
    return {
        "west": min(b["west"] for b in bounds_list),
        "south": min(b["south"] for b in bounds_list),
        "east": max(b["east"] for b in bounds_list),
        "north": max(b["north"] for b in bounds_list),
    }


class UniversalMultiTIFTileGenerator:
    """Load many GeoTIFFs (WGS84 cache each), write one {z}/{x}/{y}.png tree."""

    def __init__(
        self,
        tif_paths: list,
        output_dir: str,
        max_workers: int = None,
        layer_name: str = None,
        cdn_url: str = None,
    ):
        self.tif_paths = [Path(p) for p in tif_paths]
        for p in self.tif_paths:
            if not p.exists():
                raise FileNotFoundError(f"GeoTIFF not found: {p}")

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.max_workers = max_workers or min(mp.cpu_count(), 8)
        if layer_name:
            self.layer_name = layer_name
        elif len(self.tif_paths) == 1:
            self.layer_name = self.tif_paths[0].stem.replace("_", " ").title()
        else:
            self.layer_name = f"Merged raster ({len(self.tif_paths)} sources)"

        self.cdn_url = cdn_url

        self.layers = []
        self.union_bounds = None
        self._loaded = False

        logger.info("Universal multi-TIF generator: %s workers", self.max_workers)
        logger.info("Inputs (%s): %s", len(self.tif_paths), ", ".join(str(p) for p in self.tif_paths))
        logger.info("Output: %s", self.output_dir)

    def _reproject_one(self, geotiff_path: Path):
        """Reuse reprojection from universal_tif_tile_generator (same resampling/bands)."""
        stub = object.__new__(UniversalTIFTileGenerator)
        return UniversalTIFTileGenerator.reproject_geotiff_to_wgs84(stub, geotiff_path)

    def load_data(self):
        if self._loaded:
            logger.info("Raster data already loaded")
            return

        for path in self.tif_paths:
            logger.info("Loading: %s", path)
            r, g, b, a, bounds, transform, num_bands = self._reproject_one(path)
            self.layers.append(
                {
                    "path": path,
                    "r": r,
                    "g": g,
                    "b": b,
                    "a": a,
                    "bounds": bounds,
                    "transform": transform,
                    "num_bands": num_bands,
                    "shape": r.shape,
                }
            )

        self.union_bounds = _union_bounds([L["bounds"] for L in self.layers])
        self._loaded = True
        logger.info("Union WGS84 bounds: %s", self.union_bounds)

    def generate_tiles_for_zoom(self, zoom, min_tile, max_tile):
        logger.info("Zoom %s with %s workers", zoom, self.max_workers)

        zoom_dir = self.output_dir / str(zoom)
        zoom_dir.mkdir(exist_ok=True)

        tiles_generated = 0
        tiles_skipped = 0
        tile_tasks = []
        for x in range(min_tile.x, max_tile.x + 1):
            x_dir = zoom_dir / str(x)
            x_dir.mkdir(exist_ok=True)
            for y in range(max_tile.y, min_tile.y + 1):
                tile_path = x_dir / f"{y}.png"
                tile_tasks.append((x, y, tile_path))

        logger.info("Zoom %s: %s tile tasks", zoom, len(tile_tasks))

        if tile_tasks:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_tile = {
                    executor.submit(self.generate_single_tile, zoom, x, y, tile_path): (
                        x,
                        y,
                        tile_path,
                    )
                    for x, y, tile_path in tile_tasks
                }
                for future in future_to_tile:
                    x, y, tile_path = future_to_tile[future]
                    try:
                        if future.result():
                            tiles_generated += 1
                        else:
                            tiles_skipped += 1
                    except Exception as e:
                        logger.error("Tile %s/%s/%s: %s", zoom, x, y, e)
                        tiles_skipped += 1
                    if (tiles_generated + tiles_skipped) % 100 == 0:
                        logger.info(
                            "Zoom %s: generated %s, skipped %s",
                            zoom,
                            tiles_generated,
                            tiles_skipped,
                        )

        logger.info("Zoom %s done: %s generated, %s skipped", zoom, tiles_generated, tiles_skipped)
        return tiles_generated

    def generate_tiles(self, min_zoom=8, max_zoom=16):
        start = time.time()
        self.load_data()
        if not self.layers:
            logger.error("No layers loaded")
            return 0

        ub = self.union_bounds
        total = 0
        for zoom in range(min_zoom, max_zoom + 1):
            min_tile = mercantile.tile(ub["west"], ub["south"], zoom)
            max_tile = mercantile.tile(ub["east"], ub["north"], zoom)
            total += self.generate_tiles_for_zoom(zoom, min_tile, max_tile)

        elapsed = time.time() - start
        logger.info("Generated %s PNG tiles in %.2fs", total, elapsed)
        if elapsed > 0:
            logger.info("Average: %.2f tiles/s", total / elapsed)

        self.create_supporting_files(ub, min_zoom, max_zoom)
        return total

    def generate_single_tile(self, zoom, x, y, tile_path):
        try:
            if tile_path.exists():
                return False

            tile_bounds = mercantile.bounds(x, y, zoom)
            buf = np.zeros((256, 256, 4), dtype=np.uint8)
            self.render_layers_to_buffer(tile_bounds, buf)

            Image.fromarray(buf, "RGBA").save(tile_path, "PNG")
            return True
        except Exception as e:
            logger.error("Error tile %s/%s/%s: %s", zoom, x, y, e)
            return False

    def render_layers_to_buffer(self, tile_bounds, buf: np.ndarray):
        ub = self.union_bounds
        if (
            tile_bounds.east < ub["west"]
            or tile_bounds.west > ub["east"]
            or tile_bounds.south > ub["north"]
            or tile_bounds.north < ub["south"]
        ):
            return

        for tile_y in range(256):
            for tile_x in range(256):
                lon = tile_bounds.west + (tile_bounds.east - tile_bounds.west) * tile_x / 256.0
                lat = tile_bounds.north - (tile_bounds.north - tile_bounds.south) * tile_y / 256.0

                rgba = (0, 0, 0, 0)
                for layer in self.layers:
                    b = layer["bounds"]
                    if lon < b["west"] or lon > b["east"] or lat < b["south"] or lat > b["north"]:
                        continue

                    height, width = layer["shape"]
                    row, col = rowcol(layer["transform"], lon, lat)
                    data_x, data_y = int(col), int(row)
                    if not (0 <= data_x < width and 0 <= data_y < height):
                        continue

                    sr = int(layer["r"][data_y, data_x])
                    sg = int(layer["g"][data_y, data_x])
                    sb = int(layer["b"][data_y, data_x])
                    sa = int(layer["a"][data_y, data_x])
                    if sa <= 0:
                        continue
                    rgba = _src_over_rgba(rgba, (sr, sg, sb, sa))

                if rgba[3] > 0:
                    buf[tile_y, tile_x] = rgba

    def create_supporting_files(self, bounds, min_zoom, max_zoom):
        logger.info("Writing style.json, tilejson.json, viewer.html")

        if self.cdn_url:
            tile_url_template = self.cdn_url
        else:
            tile_url_template = "./{z}/{x}/{y}.png"

        names = ", ".join(p.name for p in self.tif_paths)
        style_json = {
            "version": 8,
            "name": self.layer_name,
            "sources": {
                "tif-layer": {
                    "type": "raster",
                    "tiles": [tile_url_template],
                    "tileSize": 256,
                }
            },
            "layers": [
                {
                    "id": "tif-layer",
                    "type": "raster",
                    "source": "tif-layer",
                    "paint": {"raster-opacity": 0.8},
                }
            ],
        }
        with open(self.output_dir / "style.json", "w") as f:
            json.dump(style_json, f, indent=2)

        tilejson = {
            "tilejson": "2.2.0",
            "name": self.layer_name,
            "description": f"Tiles from {len(self.tif_paths)} GeoTIFFs: {names}",
            "version": "1.0.0",
            "attribution": "",
            "template": "",
            "legend": "",
            "scheme": "xyz",
            "tiles": [tile_url_template],
            "grids": [],
            "data": [],
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "bounds": [
                bounds["west"],
                bounds["south"],
                bounds["east"],
                bounds["north"],
            ],
            "center": [
                (bounds["west"] + bounds["east"]) / 2,
                (bounds["south"] + bounds["north"]) / 2,
                10,
            ],
        }
        with open(self.output_dir / "tilejson.json", "w") as f:
            json.dump(tilejson, f, indent=2)

        esc = tile_url_template.replace("{z}", "{{z}}").replace("{x}", "{{x}}").replace("{y}", "{{y}}")
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{self.layer_name}</title>
    <script src='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js'></script>
    <link href='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css' rel='stylesheet' />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
    </style>
</head>
<body>
    <div id='map'></div>
    <script>
        mapboxgl.accessToken = 'pk.eyJ1IjoiZXhhbXBsZSIsImEiOiJjbGV4YW1wbGUifQ.example';
        var map = new mapboxgl.Map({{
            container: 'map',
            style: {{
                "version": 8,
                "sources": {{
                    "tif-layer": {{
                        "type": "raster",
                        "tiles": ["{esc}"],
                        "tileSize": 256
                    }}
                }},
                "layers": [
                    {{
                        "id": "tif-layer",
                        "type": "raster",
                        "source": "tif-layer",
                        "paint": {{ "raster-opacity": 0.8 }}
                    }}
                ]
            }},
            center: [{(bounds['west'] + bounds['east']) / 2}, {(bounds['south'] + bounds['north']) / 2}],
            zoom: 10
        }});
    </script>
</body>
</html>
"""
        with open(self.output_dir / "viewer.html", "w") as f:
            f.write(html_content)


def main():
    parser = argparse.ArgumentParser(
        description="Generate one PNG tile pyramid from multiple GeoTIFFs (source-over composite).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python universal_multi_tif_tile_generator.py -o data/daman/tiles_merged \\
    data/daman/CLIPPED_FILE/*.tif

  python universal_multi_tif_tile_generator.py -o out/tiles \\
    a.tif b.tif --min-zoom 10 --max-zoom 18 --layer-name "Daman sheets"
        """,
    )
    parser.add_argument(
        "tif_paths",
        nargs="+",
        help="One or more GeoTIFF paths (shell glob OK). First = bottom, last = top where they overlap.",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Single output directory for {z}/{x}/{y}.png plus style.json / tilejson.json / viewer.html",
    )
    parser.add_argument("--min-zoom", type=int, default=8)
    parser.add_argument("--max-zoom", type=int, default=16)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--layer-name", type=str, default=None)
    parser.add_argument("--cdn-url", type=str, default=None)

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("Universal multi-TIF tile generator")
    logger.info("=" * 80)
    logger.info("Output: %s", args.output)
    logger.info("Zoom: %s–%s", args.min_zoom, args.max_zoom)
    logger.info("Sources: %s", len(args.tif_paths))
    logger.info("=" * 80)

    try:
        gen = UniversalMultiTIFTileGenerator(
            tif_paths=args.tif_paths,
            output_dir=args.output,
            max_workers=args.workers,
            layer_name=args.layer_name,
            cdn_url=args.cdn_url,
        )
        n = gen.generate_tiles(min_zoom=args.min_zoom, max_zoom=args.max_zoom)
        logger.info("Done: %s new tiles written", n)
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
