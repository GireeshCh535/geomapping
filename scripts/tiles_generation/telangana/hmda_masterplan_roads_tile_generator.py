#!/usr/bin/env python3
"""
HMDA Masterplan Roads - Dedicated Tile Generator
================================================

Generates PNG tiles from HMDA_masterplan_roads_merged.geojson only.
Uses explicit RGBA colours and Width_in_Metres for line width (no legend file).

Data: LineString / MultiLineString, properties: Name, Width_in_Metres (18–230), layer.
Rendering: white border (outer) then dark grey body (inner) per feature; line thickness
scaled from Width_in_Metres so wider roads (e.g. 150 m) draw thicker than narrow (18 m).

Usage:
  python hmda_masterplan_roads_tile_generator.py
  python hmda_masterplan_roads_tile_generator.py --force
  python hmda_masterplan_roads_tile_generator.py --geojson path/to/file.geojson --output path/to/tiles
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import List, Tuple

import geopandas as gpd
import mercantile
from shapely.geometry import LineString, Polygon, box
from shapely.validation import make_valid
from PIL import Image, ImageDraw

# Explicit RGBA (no hex) so rendering is consistent across Pillow versions
WHITE_RGBA = (255, 255, 255, 255)
DARK_GREY_RGBA = (43, 43, 43, 255)  # #2B2B2B

# Base line width per zoom (pixels) for reference width 30 m
ZOOM_RESOLUTION = {
    5: 0.8, 6: 1.0, 7: 1.2, 8: 1.5, 9: 1.8, 10: 2.2, 11: 2.6, 12: 3.2,
    13: 3.8, 14: 4.5, 15: 5.5, 16: 6.5, 17: 8.0, 18: 9.5,
}
REFERENCE_WIDTH_M = 30.0  # Width_in_Metres that maps 1:1 to base resolution
MIN_LINE_PX = 1
MAX_INNER_PX = 14
MAX_OUTER_PX = 18
BORDER_EXTRA_PX = 2  # Outer = inner + this so white border is visible

SUPERSAMPLE = 2
TILE_SIZE = 256


class HMDAMasterplanRoadsTileGenerator:
    """Tile generator for HMDA masterplan roads GeoJSON only."""

    def __init__(
        self,
        geojson_path: str,
        output_dir: str,
        skip_existing: bool = True,
    ):
        self.geojson_path = Path(geojson_path)
        self.output_dir = Path(output_dir)
        self.skip_existing = skip_existing
        self.tile_size = TILE_SIZE
        self.bounds = None
        self.gdf = None
        self.spatial_index = None
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._load_data()

    def _load_data(self):
        if not self.geojson_path.exists():
            raise FileNotFoundError(f"GeoJSON not found: {self.geojson_path}")
        self.gdf = gpd.read_file(self.geojson_path)
        if self.gdf.empty:
            raise ValueError("No features in GeoJSON")
        if self.gdf.crs is None:
            self.gdf.set_crs("EPSG:4326", inplace=True)
        elif self.gdf.crs.to_string() != "EPSG:4326":
            self.gdf = self.gdf.to_crs("EPSG:4326")

        def fix_geom(geom):
            if geom is None or geom.is_empty:
                return geom
            if not getattr(geom, "is_valid", True) or (hasattr(geom, "is_valid") and not geom.is_valid):
                try:
                    return make_valid(geom)
                except Exception:
                    try:
                        return geom.buffer(0)
                    except Exception:
                        return geom
            return geom

        self.gdf["geometry"] = self.gdf.geometry.apply(fix_geom)
        self.gdf = self.gdf[self.gdf.geometry.notna() & self.gdf.geometry.is_valid].copy()

        # Width_in_Metres: ensure numeric
        if "Width_in_Metres" not in self.gdf.columns:
            self.gdf["Width_in_Metres"] = REFERENCE_WIDTH_M
        self.gdf["_width_m"] = self.gdf["Width_in_Metres"].apply(
            lambda x: float(x) if x is not None and str(x).strip() not in ("", "nan") else REFERENCE_WIDTH_M
        )
        self.gdf["_width_m"] = self.gdf["_width_m"].clip(lower=1.0, upper=500.0)

        self.bounds = self.gdf.total_bounds
        self.spatial_index = self.gdf.sindex
        print(f"[HMDA] Loaded {len(self.gdf)} features from {self.geojson_path.name}")

    def _base_line_width(self, zoom: int) -> float:
        return ZOOM_RESOLUTION.get(zoom, 3.0)

    def _width_to_px(self, width_m: float, zoom: int, is_outer: bool) -> int:
        base = self._base_line_width(zoom)
        scale = width_m / REFERENCE_WIDTH_M
        px = max(MIN_LINE_PX, int(base * scale))
        if is_outer:
            px = min(MAX_OUTER_PX, px + BORDER_EXTRA_PX)
        else:
            px = min(MAX_INNER_PX, px)
        return px

    def _wgs84_to_tile_pixel(
        self, lon: float, lat: float, tile_x: int, tile_y: int, zoom: int
    ) -> Tuple[int, int]:
        lat = max(-85.051129, min(85.051129, lat))
        tile_lon = (lon + 180) / 360 * (2 ** zoom)
        tile_lat = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * (2 ** zoom)
        pixel_x = round((tile_lon - tile_x) * self.tile_size)
        pixel_y = round((tile_lat - tile_y) * self.tile_size)
        return pixel_x, pixel_y

    def _geom_to_line_coords(self, geom):
        """Yield list of (lon, lat) coords for each line part."""
        if geom is None or geom.is_empty:
            return
        if geom.geom_type == "LineString":
            yield list(geom.coords)
        elif geom.geom_type == "MultiLineString":
            for line in geom.geoms:
                yield list(line.coords)

    def _draw_line(
        self,
        draw: ImageDraw.Draw,
        coordinates: List[Tuple[float, float]],
        color_rgba: Tuple[int, int, int, int],
        width_px: int,
        tile_x: int,
        tile_y: int,
        zoom: int,
        offset_x: int = 0,
        offset_y: int = 0,
        scale: int = 1,
    ):
        if len(coordinates) < 2:
            return
        pixel_coords = []
        for pt in coordinates:
            if len(pt) >= 2:
                lon, lat = float(pt[0]), float(pt[1])
            else:
                continue
            px, py = self._wgs84_to_tile_pixel(lon, lat, tile_x, tile_y, zoom)
            if scale > 1:
                px = px * scale + offset_x
                py = py * scale + offset_y
            else:
                px += offset_x
                py += offset_y
            pixel_coords.append((px, py))
        if len(pixel_coords) < 2:
            return
        w = max(1, round(width_px * scale)) if scale > 1 else width_px
        try:
            draw.line(pixel_coords, fill=color_rgba, width=w, joint="curve")
            return
        except TypeError:
            pass
        try:
            ls = LineString(pixel_coords)
            if ls.is_empty or not ls.is_valid:
                draw.line(pixel_coords, fill=color_rgba, width=w)
                return
            half = max(0.5, w / 2.0)
            buffered = ls.buffer(half, cap_style=2, join_style=2)
            if buffered.is_empty:
                draw.line(pixel_coords, fill=color_rgba, width=w)
                return
            for poly in (buffered.geoms if hasattr(buffered, "geoms") else [buffered]):
                if not isinstance(poly, Polygon) or poly.is_empty:
                    continue
                ext = poly.exterior
                poly_coords = [(float(x), float(y)) for x, y in zip(ext.xy[0], ext.xy[1])]
                if len(poly_coords) >= 3:
                    draw.polygon(poly_coords, fill=color_rgba)
        except Exception:
            try:
                draw.line(pixel_coords, fill=color_rgba, width=w)
            except Exception:
                for i in range(len(pixel_coords) - 1):
                    try:
                        draw.line(
                            [pixel_coords[i], pixel_coords[i + 1]],
                            fill=color_rgba,
                            width=w,
                        )
                    except Exception:
                        continue

    def create_blank_tile(self) -> Image.Image:
        return Image.new("RGBA", (self.tile_size, self.tile_size), (0, 0, 0, 0))

    def generate_tile(self, x: int, y: int, zoom: int) -> Image.Image:
        base = max(1, int(self._base_line_width(zoom)))
        bleed_px = max(2, base * 2)
        canvas_size = (self.tile_size + 2 * bleed_px) * SUPERSAMPLE
        bleed_scaled = bleed_px * SUPERSAMPLE
        img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        tile_bounds = mercantile.bounds(x, y, zoom)
        tile_width_deg = tile_bounds.east - tile_bounds.west
        tile_height_deg = tile_bounds.north - tile_bounds.south
        buffer_px = bleed_px + base
        buffer_lon = tile_width_deg * (buffer_px / self.tile_size)
        buffer_lat = tile_height_deg * (buffer_px / self.tile_size)
        tile_box = box(
            tile_bounds.west - buffer_lon,
            tile_bounds.south - buffer_lat,
            tile_bounds.east + buffer_lon,
            tile_bounds.north + buffer_lat,
        )

        candidate_idxs = list(self.spatial_index.intersection(tile_box.bounds))
        for idx in candidate_idxs:
            row = self.gdf.iloc[idx]
            geometry = row.geometry
            if not geometry.intersects(tile_box):
                continue
            width_m = row["_width_m"]
            inner_px = self._width_to_px(width_m, zoom, is_outer=False)
            outer_px = self._width_to_px(width_m, zoom, is_outer=True)
            for coords in self._geom_to_line_coords(geometry):
                if len(coords) < 2:
                    continue
                # Draw outer (white) first, then inner (dark)
                self._draw_line(
                    draw, coords, WHITE_RGBA, outer_px, x, y, zoom,
                    bleed_scaled, bleed_scaled, scale=SUPERSAMPLE,
                )
                self._draw_line(
                    draw, coords, DARK_GREY_RGBA, inner_px, x, y, zoom,
                    bleed_scaled, bleed_scaled, scale=SUPERSAMPLE,
                )

        cropped = img.crop(
            (bleed_scaled, bleed_scaled,
             bleed_scaled + self.tile_size * SUPERSAMPLE,
             bleed_scaled + self.tile_size * SUPERSAMPLE)
        )
        if SUPERSAMPLE > 1:
            cropped = cropped.resize((self.tile_size, self.tile_size), Image.LANCZOS)
        return cropped

    def generate_tiles(self, min_zoom: int = 5, max_zoom: int = 18):
        print(f"[HMDA] Generating tiles zoom {min_zoom}–{max_zoom}...")
        total = 0
        start = time.time()
        minx, miny, maxx, maxy = self.bounds
        tile_size_deg = 360.0 / (2 ** max_zoom)
        buffer_deg = tile_size_deg * 3
        expanded = [minx - buffer_deg, miny - buffer_deg, maxx + buffer_deg, maxy + buffer_deg]

        for zoom in range(min_zoom, max_zoom + 1):
            zoom_dir = self.output_dir / str(zoom)
            zoom_dir.mkdir(exist_ok=True)
            tiles = list(mercantile.tiles(*expanded, zoom))
            for tile in tiles:
                x_dir = zoom_dir / str(tile.x)
                x_dir.mkdir(exist_ok=True)
                tile_path = x_dir / f"{tile.y}.png"
                if self.skip_existing and tile_path.exists():
                    total += 1
                    continue
                tile_bounds = mercantile.bounds(tile.x, tile.y, zoom)
                within = (
                    tile_bounds.west < maxx and tile_bounds.east > minx
                    and tile_bounds.south < maxy and tile_bounds.north > miny
                )
                img = self.generate_tile(tile.x, tile.y, zoom) if within else self.create_blank_tile()
                img.save(tile_path, "PNG", optimize=True)
                total += 1
            print(f"[HMDA] Zoom {zoom}: {len(tiles)} tiles")
        elapsed = time.time() - start
        print(f"[HMDA] Done: {total} tiles in {elapsed:.1f}s")

    def create_tilejson(self, name: str = "HMDA Masterplan Roads", min_zoom: int = 5, max_zoom: int = 18):
        minx, miny, maxx, maxy = self.bounds
        center = [(minx + maxx) / 2, (miny + maxy) / 2, 10]
        tilejson = {
            "tilejson": "3.0.0",
            "name": name,
            "version": "1.0.0",
            "scheme": "xyz",
            "tiles": ["./{z}/{x}/{y}.png"],
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "bounds": [minx, miny, maxx, maxy],
            "center": center,
        }
        (self.output_dir / "tilejson.json").write_text(json.dumps(tilejson, indent=2))
        print(f"[HMDA] TileJSON: {self.output_dir}/tilejson.json")

    def create_html_viewer(self, layer_name: str = "HMDA Masterplan Roads", min_zoom: int = 5, max_zoom: int = 18):
        minx, miny, maxx, maxy = self.bounds
        center_lat = (miny + maxy) / 2
        center_lon = (minx + maxx) / 2
        pad = 0.02
        sw_lat, sw_lon = miny - pad, minx - pad
        ne_lat, ne_lon = maxy + pad, maxx + pad
        default_zoom = max(min_zoom, min(11, max_zoom))
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{layer_name}</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>body, html, #map {{ margin:0; padding:0; height:100%; }}</style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const bounds = [[{sw_lat:.6f}, {sw_lon:.6f}], [{ne_lat:.6f}, {ne_lon:.6f}]];
    const map = L.map('map', {{
      center: [{center_lat:.6f}, {center_lon:.6f}],
      zoom: {default_zoom},
      maxBounds: bounds,
      maxBoundsViscosity: 1.0
    }});
    map.fitBounds(bounds, {{ padding: [30, 30], maxZoom: {max_zoom} }});
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
      attribution: 'Esri', maxZoom: 19
    }}).addTo(map);
    L.tileLayer('./{{z}}/{{x}}/{{y}}.png', {{
      minZoom: {min_zoom}, maxZoom: {max_zoom}, opacity: 0.9, attribution: '{layer_name}'
    }}).addTo(map);
  </script>
</body>
</html>"""
        (self.output_dir / "index.html").write_text(html, encoding="utf-8")
        print(f"[HMDA] Viewer: {self.output_dir}/index.html")


def main():
    parser = argparse.ArgumentParser(description="HMDA Masterplan Roads tile generator (dedicated script)")
    parser.add_argument(
        "--geojson", "-g",
        default="data/telangana/hyderabad/roads/HMDA_masterplan_roads_merged.geojson",
        help="Path to HMDA masterplan roads GeoJSON",
    )
    parser.add_argument(
        "--output", "-o",
        default="data/telangana/hyderabad/roads/HMDA_masterplan_roads_tiles",
        help="Output directory for tiles",
    )
    parser.add_argument("--force", "-f", action="store_true", help="Regenerate all tiles")
    parser.add_argument("--min-zoom", type=int, default=5, help="Min zoom")
    parser.add_argument("--max-zoom", type=int, default=18, help="Max zoom")
    args = parser.parse_args()

    geojson_path = Path(args.geojson)
    if not geojson_path.exists():
        print(f"[HMDA] Error: GeoJSON not found: {geojson_path}", file=sys.stderr)
        sys.exit(1)

    try:
        gen = HMDAMasterplanRoadsTileGenerator(
            str(geojson_path),
            args.output,
            skip_existing=not args.force,
        )
        gen.generate_tiles(min_zoom=args.min_zoom, max_zoom=args.max_zoom)
        gen.create_tilejson(min_zoom=args.min_zoom, max_zoom=args.max_zoom)
        gen.create_html_viewer(min_zoom=args.min_zoom, max_zoom=args.max_zoom)
        print(f"[HMDA] Tiles written to {args.output}")
    except Exception as e:
        print(f"[HMDA] Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
