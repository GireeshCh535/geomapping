#!/usr/bin/env python3
"""
High-quality universal TIF tile generator.

Improvements over universal_tif_tile_generator.py:
  - Bilinear/cubic reprojection (not nearest-neighbor)
  - Region extract + LANCZOS/BICUBIC resize (production-style, no per-pixel draw.point)
  - Reads EPSG:4326 sources directly (no extra warp)
  - Floor/ceil pixel bounds to reduce tile-edge seams
"""

import argparse
import json
import logging
import math
import multiprocessing as mp
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import mercantile
import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import Resampling, calculate_default_transform, reproject

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

RESAMPLING_MAP = {
    "nearest": Resampling.nearest,
    "bilinear": Resampling.bilinear,
    "cubic": Resampling.cubic,
    "lanczos": Resampling.lanczos,
}


class HighQualityTIFTileGenerator:
    TILE_SIZE = 256

    def __init__(
        self,
        tif_path: str,
        output_dir: str,
        max_workers: Optional[int] = None,
        layer_name: Optional[str] = None,
        cdn_url: Optional[str] = None,
        resampling: str = "bilinear",
        force: bool = False,
    ):
        self.tif_path = Path(tif_path)
        if not self.tif_path.exists():
            raise FileNotFoundError(f"GeoTIFF file not found: {tif_path}")

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.max_workers = max_workers or min(mp.cpu_count(), 8)
        self.layer_name = layer_name or self.tif_path.stem.replace("_", " ").title()
        self.cdn_url = cdn_url
        self.resampling = RESAMPLING_MAP.get(resampling, Resampling.bilinear)
        self.force = force

        self.wgs84_data_r = None
        self.wgs84_data_g = None
        self.wgs84_data_b = None
        self.wgs84_data_a = None
        self.wgs84_bounds = None
        self.wgs84_transform = None

        logger.info("HQ TIF Tile Generator | workers=%s | resampling=%s", self.max_workers, resampling)
        logger.info("Input: %s", self.tif_path)
        logger.info("Output: %s", self.output_dir)

    def load_data(self):
        if self.wgs84_data_r is not None:
            return

        logger.info("Loading GeoTIFF: %s", self.tif_path)
        (
            self.wgs84_data_r,
            self.wgs84_data_g,
            self.wgs84_data_b,
            self.wgs84_data_a,
            self.wgs84_bounds,
            self.wgs84_transform,
        ) = self._load_wgs84_rgba(self.tif_path)
        logger.info("WGS84 bounds: %s", self.wgs84_bounds)
        logger.info("Raster shape: %s", self.wgs84_data_r.shape)

    def _load_wgs84_rgba(self, geotiff_path: Path):
        with rasterio.open(geotiff_path) as src:
            logger.info("CRS: %s | bands: %s | size: %s", src.crs, src.count, src.shape)

            if src.crs and src.crs.to_epsg() == 4326:
                logger.info("Source is EPSG:4326 — reading bands directly (no reprojection)")
                r, g, b, a = self._read_rgba_bands(src)
                transform = src.transform
            else:
                logger.info("Reprojecting to EPSG:4326 (%s)", self.resampling)
                r, g, b, a, transform = self._reproject_to_wgs84(src)

            west, south, east, north = rasterio.transform.array_bounds(
                r.shape[0], r.shape[1], transform
            )
            bounds = {"west": west, "south": south, "east": east, "north": north}
            return r, g, b, a, bounds, transform

    def _read_rgba_bands(self, src):
        if src.count >= 4:
            r, g, b, a = src.read(1), src.read(2), src.read(3), src.read(4)
        elif src.count == 3:
            r, g, b = src.read(1), src.read(2), src.read(3)
            a = np.full_like(r, 255, dtype=np.uint8)
        elif src.count == 1:
            r = src.read(1)
            g, b = r.copy(), r.copy()
            a = np.full_like(r, 255, dtype=np.uint8)
        else:
            raise ValueError(f"Unsupported band count: {src.count}")
        return r, g, b, a

    def _reproject_to_wgs84(self, src):
        transform, width, height = calculate_default_transform(
            src.crs,
            "EPSG:4326",
            src.width,
            src.height,
            *src.bounds,
        )
        dtype = src.dtypes[0]
        destination_r = np.zeros((height, width), dtype=dtype)
        destination_g = np.zeros((height, width), dtype=dtype)
        destination_b = np.zeros((height, width), dtype=dtype)
        destination_a = np.zeros((height, width), dtype=np.uint8)

        kw = dict(
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs="EPSG:4326",
            resampling=self.resampling,
        )

        if src.count >= 4:
            for i, dest in enumerate(
                (destination_r, destination_g, destination_b, destination_a), start=1
            ):
                reproject(source=rasterio.band(src, i), destination=dest, **kw)
        elif src.count == 3:
            for i, dest in enumerate((destination_r, destination_g, destination_b), start=1):
                reproject(source=rasterio.band(src, i), destination=dest, **kw)
            destination_a[:] = 255
        elif src.count == 1:
            reproject(source=rasterio.band(src, 1), destination=destination_r, **kw)
            destination_g[:] = destination_r
            destination_b[:] = destination_r
            destination_a[:] = 255
        else:
            raise ValueError(f"Unsupported band count: {src.count}")

        return destination_r, destination_g, destination_b, destination_a, transform

    def extract_tile(self, tile_bounds) -> Optional[Image.Image]:
        """Extract one 256x256 tile using affine window + high-quality resize."""
        b = self.wgs84_bounds
        if (
            tile_bounds.east < b["west"]
            or tile_bounds.west > b["east"]
            or tile_bounds.south > b["north"]
            or tile_bounds.north < b["south"]
        ):
            return None

        inv = ~self.wgs84_transform
        ul_col, ul_row = inv * (tile_bounds.west, tile_bounds.north)
        lr_col, lr_row = inv * (tile_bounds.east, tile_bounds.south)

        h, w = self.wgs84_data_r.shape
        min_col = int(math.floor(min(ul_col, lr_col)))
        max_col = int(math.ceil(max(ul_col, lr_col)))
        min_row = int(math.floor(min(ul_row, lr_row)))
        max_row = int(math.ceil(max(ul_row, lr_row)))

        min_col = max(0, min_col)
        max_col = min(w, max_col)
        min_row = max(0, min_row)
        max_row = min(h, max_row)

        if min_col >= max_col or min_row >= max_row:
            return None

        region_r = self.wgs84_data_r[min_row:max_row, min_col:max_col]
        region_g = self.wgs84_data_g[min_row:max_row, min_col:max_col]
        region_b = self.wgs84_data_b[min_row:max_row, min_col:max_col]
        region_a = self.wgs84_data_a[min_row:max_row, min_col:max_col]

        if (
            region_a.max() == 0
            and region_r.max() == 0
            and region_g.max() == 0
            and region_b.max() == 0
        ):
            return None

        rgba = np.stack([region_r, region_g, region_b, region_a], axis=-1)
        img = Image.fromarray(rgba, "RGBA")

        region_west, region_north = self.wgs84_transform * (min_col, min_row)
        region_east, region_south = self.wgs84_transform * (max_col, max_row)

        tile_w = tile_bounds.east - tile_bounds.west
        tile_h = tile_bounds.north - tile_bounds.south

        left_px = int(self.TILE_SIZE * max(0.0, (region_west - tile_bounds.west) / tile_w))
        right_px = int(self.TILE_SIZE * min(1.0, (region_east - tile_bounds.west) / tile_w))
        top_px = int(self.TILE_SIZE * max(0.0, (tile_bounds.north - region_north) / tile_h))
        bottom_px = int(self.TILE_SIZE * min(1.0, (tile_bounds.north - region_south) / tile_h))

        target_w = right_px - left_px
        target_h = bottom_px - top_px
        if target_w <= 0 or target_h <= 0:
            return None

        resample = Image.LANCZOS if (img.width > target_w or img.height > target_h) else Image.BICUBIC
        img_resized = img.resize((target_w, target_h), resample)

        tile = Image.new("RGBA", (self.TILE_SIZE, self.TILE_SIZE), (0, 0, 0, 0))
        tile.paste(img_resized, (left_px, top_px))

        if tile.getbbox() is None:
            return None
        return tile

    def generate_single_tile(self, zoom: int, x: int, y: int, tile_path: Path) -> bool:
        try:
            if tile_path.exists() and not self.force:
                return False

            tile_bounds = mercantile.bounds(x, y, zoom)
            tile_img = self.extract_tile(tile_bounds)
            if tile_img is None:
                return False

            tile_path.parent.mkdir(parents=True, exist_ok=True)
            tile_img.save(tile_path, "PNG", compress_level=3)
            return True
        except Exception as e:
            logger.error("Tile %s/%s/%s failed: %s", zoom, x, y, e)
            return False

    def generate_tiles_for_zoom(self, zoom: int, min_tile, max_tile) -> int:
        logger.info("Zoom %s | x %s..%s | y %s..%s", zoom, min_tile.x, max_tile.x, max_tile.y, min_tile.y)

        tasks = []
        for x in range(min_tile.x, max_tile.x + 1):
            for y in range(max_tile.y, min_tile.y + 1):
                tasks.append((x, y, self.output_dir / str(zoom) / str(x) / f"{y}.png"))

        generated = 0
        skipped = 0

        if not tasks:
            return 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.generate_single_tile, zoom, x, y, path): (x, y)
                for x, y, path in tasks
            }
            for fut in futures:
                try:
                    if fut.result():
                        generated += 1
                    else:
                        skipped += 1
                except Exception as e:
                    logger.error("Worker error: %s", e)
                    skipped += 1

        logger.info("Zoom %s done: %s generated, %s skipped", zoom, generated, skipped)
        return generated

    def generate_tiles(self, min_zoom: int = 8, max_zoom: int = 16) -> int:
        start = time.time()
        self.load_data()

        if self.wgs84_data_r is None:
            logger.error("Failed to load raster data")
            return 0

        total = 0
        for zoom in range(min_zoom, max_zoom + 1):
            min_tile = mercantile.tile(self.wgs84_bounds["west"], self.wgs84_bounds["south"], zoom)
            max_tile = mercantile.tile(self.wgs84_bounds["east"], self.wgs84_bounds["north"], zoom)
            total += self.generate_tiles_for_zoom(zoom, min_tile, max_tile)

        elapsed = time.time() - start
        logger.info("Generated %s tiles in %.2fs (%.2f tiles/s)", total, elapsed, total / max(elapsed, 0.01))

        self._write_metadata(min_zoom, max_zoom)
        return total

    def _write_metadata(self, min_zoom: int, max_zoom: int):
        b = self.wgs84_bounds
        tile_url = self.cdn_url or "./{z}/{x}/{y}.png"

        tilejson = {
            "tilejson": "2.2.0",
            "name": self.layer_name,
            "description": f"HQ tiles from {self.tif_path.name}",
            "scheme": "xyz",
            "tiles": [tile_url],
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "bounds": [b["west"], b["south"], b["east"], b["north"]],
            "center": [(b["west"] + b["east"]) / 2, (b["south"] + b["north"]) / 2, min_zoom + 2],
        }
        with open(self.output_dir / "tilejson.json", "w") as f:
            json.dump(tilejson, f, indent=2)
        logger.info("Wrote tilejson.json (does not overwrite viewer.html)")


def main():
    parser = argparse.ArgumentParser(
        description="High-quality PNG tiles from GeoTIFF (region extract + LANCZOS)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python universal_tif_tile_generator_hq.py data/506.tif local_tiles/506 \\
    --min-zoom 12 --max-zoom 18 --resampling bilinear --force

  docker exec geomapping-web-1 python /app/scripts/tiles_generation/universal_tif_tile_generator_hq.py \\
    /app/data/506.tif /app/local_tiles/506 --min-zoom 12 --max-zoom 18 --force
        """,
    )
    parser.add_argument("tif_path", help="Path to GeoTIFF (e.g. data/506.tif)")
    parser.add_argument("output_dir", help="Output directory for z/x/y.png tiles")
    parser.add_argument("--min-zoom", type=int, default=12)
    parser.add_argument("--max-zoom", type=int, default=18)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--layer-name", type=str, default=None)
    parser.add_argument("--cdn-url", type=str, default=None)
    parser.add_argument(
        "--resampling",
        choices=sorted(RESAMPLING_MAP.keys()),
        default="bilinear",
        help="Warp resampling when source is not EPSG:4326 (default: bilinear)",
    )
    parser.add_argument("--force", action="store_true", help="Regenerate existing PNG tiles")

    args = parser.parse_args()

    try:
        gen = HighQualityTIFTileGenerator(
            tif_path=args.tif_path,
            output_dir=args.output_dir,
            max_workers=args.workers,
            layer_name=args.layer_name,
            cdn_url=args.cdn_url,
            resampling=args.resampling,
            force=args.force,
        )
        total = gen.generate_tiles(min_zoom=args.min_zoom, max_zoom=args.max_zoom)
        logger.info("Success: %s tiles -> %s", total, args.output_dir)
    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
