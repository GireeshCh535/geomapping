#!/usr/bin/env python3
"""
Generic multi-threaded RGBA GeoTIFF → XYZ tile generator.
Reprojects once, caches in memory, and renders pixel-perfect PNG tiles.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import multiprocessing as mp
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import mercantile
import numpy as np
from PIL import Image, ImageDraw
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject


# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("threaded-rgba-tile-generator")

CLOUDFRONT_BASE_URL = "https://d17yosovmfjm4.cloudfront.net"


# -----------------------------------------------------------------------------
# Generator
# -----------------------------------------------------------------------------
class ThreadedRGBATileGenerator:
    """Reuseable RGBA tile generator with caching + multi-threading."""

    def __init__(
        self,
        data_path: str,
        output_dir: str,
        tiles_relative_path: Optional[str] = None,
        style_name: str = "Masterplan Tiles (Threaded)",
        attribution: str = "Urban Development Authority",
        max_workers: Optional[int] = None,
    ):
        self.data_path = Path(data_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        rel = tiles_relative_path.strip("/") if tiles_relative_path else self.output_dir.name
        self.tiles_base_url = f"{CLOUDFRONT_BASE_URL}/{rel}"
        self.style_name = style_name
        self.attribution = attribution
        self.max_workers = max_workers or min(mp.cpu_count(), 8)

        self.wgs84_data_r = None
        self.wgs84_data_g = None
        self.wgs84_data_b = None
        self.wgs84_data_a = None
        self.wgs84_bounds = None
        self.wgs84_transform = None

        logger.info(
            "Initialized generator | data_path=%s output_dir=%s workers=%s",
            self.data_path,
            self.output_dir,
            self.max_workers,
        )

    # ------------------------------------------------------------------ #
    # Data prep
    # ------------------------------------------------------------------ #
    def load_data(self):
        if self.wgs84_data_r is not None:
            logger.info("Data already cached")
            return

        if self.data_path.is_file():
            geotiff_path = self.data_path
        else:
            geotiffs = sorted(self.data_path.glob("*.tif"))
            if not geotiffs:
                raise FileNotFoundError(f"No GeoTIFF files found in {self.data_path}")
            geotiff_path = geotiffs[0]
        logger.info("Loading GeoTIFF: %s", geotiff_path)
        (
            self.wgs84_data_r,
            self.wgs84_data_g,
            self.wgs84_data_b,
            self.wgs84_data_a,
            self.wgs84_bounds,
            self.wgs84_transform,
        ) = self._reproject_to_wgs84(geotiff_path)

    @staticmethod
    def _reproject_to_wgs84(geotiff_path: Path):
        with rasterio.open(geotiff_path) as src:
            logger.info("Source CRS: %s | size: %s", src.crs, src.shape)
            transform, width, height = calculate_default_transform(
                src.crs,
                "EPSG:4326",
                src.width,
                src.height,
                left=src.bounds.left,
                bottom=src.bounds.bottom,
                right=src.bounds.right,
                top=src.bounds.top,
            )

            dst_r = np.zeros((height, width), dtype=src.dtypes[0])
            dst_g = np.zeros((height, width), dtype=src.dtypes[0])
            dst_b = np.zeros((height, width), dtype=src.dtypes[0])
            dst_a = np.zeros((height, width), dtype=src.dtypes[0])

            for band_idx, dest in zip(
                (1, 2, 3, 4), (dst_r, dst_g, dst_b, dst_a)
            ):
                reproject(
                    source=src.read(band_idx),
                    destination=dest,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs="EPSG:4326",
                    resampling=Resampling.nearest,
                )

        bounds = {
            "west": transform[2],
            "south": transform[5] + height * transform[4],
            "east": transform[2] + width * transform[0],
            "north": transform[5],
        }
        logger.info("Reprojected bounds: %s", bounds)
        return dst_r, dst_g, dst_b, dst_a, bounds, transform

    # ------------------------------------------------------------------ #
    # Tiling
    # ------------------------------------------------------------------ #
    def generate_tiles(self, min_zoom: int, max_zoom: int) -> int:
        self.load_data()
        if self.wgs84_data_r is None:
            return 0

        total_tiles = 0
        start = time.time()

        for zoom in range(min_zoom, max_zoom + 1):
            min_tile = mercantile.tile(
                self.wgs84_bounds["west"], self.wgs84_bounds["south"], zoom
            )
            max_tile = mercantile.tile(
                self.wgs84_bounds["east"], self.wgs84_bounds["north"], zoom
            )
            total_tiles += self._generate_tiles_for_zoom(zoom, min_tile, max_tile)

        duration = time.time() - start
        if duration > 0:
            logger.info(
                "Generated %s tiles in %.2fs (%.2f tiles/s)",
                total_tiles,
                duration,
                total_tiles / duration,
            )

        self._create_supporting_files(min_zoom, max_zoom)
        return total_tiles

    def _generate_tiles_for_zoom(self, zoom, min_tile, max_tile):
        zoom_dir = self.output_dir / str(zoom)
        zoom_dir.mkdir(exist_ok=True)
        tasks = []

        for x in range(min_tile.x, max_tile.x + 1):
            x_dir = zoom_dir / str(x)
            x_dir.mkdir(exist_ok=True)
            for y in range(max_tile.y, min_tile.y + 1):
                tasks.append((x, y, x_dir / f"{y}.png"))

        logger.info("Zoom %s: %s tile tasks", zoom, len(tasks))

        generated = skipped = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._generate_single_tile, zoom, x, y, tile_path): (
                    x,
                    y,
                    tile_path,
                )
                for (x, y, tile_path) in tasks
            }
            for future in futures:
                try:
                    if future.result():
                        generated += 1
                    else:
                        skipped += 1
                except Exception as exc:  # pylint: disable=broad-except
                    logger.error("Tile error: %s", exc)
                    skipped += 1

                total = generated + skipped
                if total and total % 100 == 0:
                    logger.info(
                        "Zoom %s progress: generated=%s skipped=%s",
                        zoom,
                        generated,
                        skipped,
                    )

        logger.info(
            "Zoom %s: %s generated, %s skipped", zoom, generated, skipped
        )
        return generated

    def _generate_single_tile(self, zoom, x, y, tile_path: Path) -> bool:
        """Generate a single PNG tile using pixel-by-pixel rendering"""
        try:
            # Get tile bounds
            tile_bounds = mercantile.bounds(x, y, zoom)
            
            # Create a blank tile
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Render the WGS84 data to this tile using pixel-by-pixel approach
            self._render_tile(tile_bounds, draw)
            
            # Save the tile
            img.save(tile_path, 'PNG')
            return True
            
        except Exception as e:
            logger.error(f"Error generating tile {zoom}/{x}/{y}: {e}")
            return False

    def _render_tile(self, tile_bounds, draw):
        """Render WGS84 data to a tile using pixel-by-pixel approach for maximum quality"""
        try:
            # Check if tile bounds intersect with data bounds
            if (tile_bounds.east < self.wgs84_bounds['west'] or 
                tile_bounds.west > self.wgs84_bounds['east'] or 
                tile_bounds.south > self.wgs84_bounds['north'] or 
                tile_bounds.north < self.wgs84_bounds['south']):
                return

            # Get data dimensions
            height, width = self.wgs84_data_r.shape
            
            # Sample points in the tile (every pixel for high quality)
            for tile_y in range(0, 256, 1):
                for tile_x in range(0, 256, 1):
                    # Convert tile pixel to WGS84 coordinates
                    lon = tile_bounds.west + (tile_bounds.east - tile_bounds.west) * tile_x / 256
                    lat = tile_bounds.north - (tile_bounds.north - tile_bounds.south) * tile_y / 256
                    
                    # Convert WGS84 coordinates to data pixel coordinates
                    data_x, data_y = self._wgs84_to_pixel(lon, lat, width, height)
                    
                    if 0 <= data_x < width and 0 <= data_y < height:
                        r = int(self.wgs84_data_r[data_y, data_x])
                        g = int(self.wgs84_data_g[data_y, data_x])
                        b = int(self.wgs84_data_b[data_y, data_x])
                        a = int(self.wgs84_data_a[data_y, data_x])
                        
                        # Only draw pixels that are not transparent
                        # Preserve ALL colors including black (0,0,0) - only check alpha
                        if a > 0:
                            # Use the actual RGB values from the GeoTIFF
                            rgb_color = (r, g, b)
                            
                            # Draw the pixel
                            draw.point((tile_x, tile_y), fill=rgb_color)

        except Exception as e:
            logger.error(f"Error rendering data to tile: {e}")

    def _wgs84_to_pixel(self, lon, lat, width, height):
        """Convert WGS84 coordinates to data pixel coordinates"""
        # Use the inverse transform to get pixel coordinates
        from rasterio.transform import rowcol
        
        row, col = rowcol(self.wgs84_transform, lon, lat)
        return int(col), int(row)

    # ------------------------------------------------------------------ #
    # Supporting files
    # ------------------------------------------------------------------ #
    def _create_supporting_files(self, min_zoom, max_zoom):
        logger.info("Creating supporting files in %s", self.output_dir)
        center_lon = (self.wgs84_bounds["west"] + self.wgs84_bounds["east"]) / 2
        center_lat = (self.wgs84_bounds["south"] + self.wgs84_bounds["north"]) / 2

        tile_url = f"{self.tiles_base_url}/{{z}}/{{x}}/{{y}}.png"

        style = {
            "version": 8,
            "name": self.style_name,
            "sources": {
                "rgba-masterplan": {
                    "type": "raster",
                    "tiles": [tile_url],
                    "tileSize": 256,
                }
            },
            "layers": [
                {
                    "id": "rgba-masterplan-layer",
                    "type": "raster",
                    "source": "rgba-masterplan",
                    "paint": {"raster-opacity": 0.8},
                }
            ],
        }
        with open(self.output_dir / "style.json", "w", encoding="utf-8") as f:
            json.dump(style, f, indent=2)

        tilejson = {
            "tilejson": "2.2.0",
            "name": self.style_name,
            "description": f"Tiles generated from {self.data_path}",
            "version": "1.0.0",
            "attribution": self.attribution,
            "scheme": "xyz",
            "tiles": [tile_url],
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "bounds": [
                self.wgs84_bounds["west"],
                self.wgs84_bounds["south"],
                self.wgs84_bounds["east"],
                self.wgs84_bounds["north"],
            ],
            "center": [center_lon, center_lat, min_zoom],
        }
        with open(self.output_dir / "tilejson.json", "w", encoding="utf-8") as f:
            json.dump(tilejson, f, indent=2)

        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{self.style_name}</title>
  <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
  <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet" />
  <style>
    body {{ margin:0; padding:0; }}
    #map {{ position:absolute; top:0; bottom:0; width:100%; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <script>
    mapboxgl.accessToken = 'pk.eyJ1IjoiZXhhbXBsZSIsImEiOiJjbGV4YW1wbGUifQ.example';
    var map = new mapboxgl.Map({{
      container: 'map',
      style: {{
        "version": 8,
        "sources": {{
          "rgba-masterplan": {{
            "type": "raster",
            "tiles": ["{tile_url}"],
            "tileSize": 256
          }}
        }},
        "layers": [
          {{
            "id": "rgba-masterplan-layer",
            "type": "raster",
            "source": "rgba-masterplan",
            "paint": {{"raster-opacity": 0.8}}
          }}
        ]
      }},
      center: [{center_lon}, {center_lat}],
      zoom: {min_zoom}
    }});
  </script>
</body>
</html>
"""
        with open(self.output_dir / "viewer.html", "w", encoding="utf-8") as f:
            f.write(html)


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Generic RGBA tile generator")
    parser.add_argument("--data-path", required=True, help="Path to GeoTIFF file or directory containing it")
    parser.add_argument("--output-dir", required=True, help="Directory to write tiles")
    parser.add_argument("--min-zoom", type=int, default=8)
    parser.add_argument("--max-zoom", type=int, default=16)
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--tiles-relative-path", default=None, help="Relative CloudFront path (defaults to output dir name)")
    parser.add_argument("--style-name", default="Masterplan Tiles (Threaded)")
    parser.add_argument("--attribution", default="Urban Development Authority")
    return parser.parse_args()


def main():
    args = parse_args()
    generator = ThreadedRGBATileGenerator(
        data_path=args.data_path,
        output_dir=args.output_dir,
        tiles_relative_path=args.tiles_relative_path,
        style_name=args.style_name,
        attribution=args.attribution,
        max_workers=args.max_workers,
    )
    generator.generate_tiles(min_zoom=args.min_zoom, max_zoom=args.max_zoom)


if __name__ == "__main__":
    main()