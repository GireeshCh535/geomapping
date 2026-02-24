#!/usr/bin/env python3
"""
Universal Mixed Line + Polygon Tile Generator
=============================================

Combines rendering from:
  - universal_line_styled_tile_generator.py (for LineString / MultiLineString)
  - universal_masterplan_tile_generator.py (for Polygon / MultiPolygon)

Reads a directory of GeoJSON files. Per feature:
  - LineString / MultiLineString → drawn as strokes (color from properties.HEX, width from properties["Stroke Width"])
  - Polygon / MultiPolygon → drawn as filled polygons (fill from properties.HEX, optional outline)

Colors are read from feature properties (e.g. HEX, Stroke Width). No legend.csv required if
properties are present. Draw order: polygons first (by file order), then lines on top.

Usage:
  python universal_mixed_line_polygon_tile_generator.py "data/TamilNadu CRZ layers_processed" output_tiles
  python universal_mixed_line_polygon_tile_generator.py data_dir output_dir [--min-zoom 5] [--max-zoom 18] [--force]
"""

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any

import mercantile
from shapely.geometry import shape, box, Point, Polygon, LineString, MultiLineString, MultiPolygon
from shapely.ops import transform
from shapely.validation import make_valid
from PIL import Image, ImageDraw

try:
    from rtree import index
    HAS_RTREE = True
except ImportError:
    HAS_RTREE = False

try:
    from pyproj import Transformer
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False

# Line rendering (from universal_line_styled)
ZOOM_RESOLUTION = {
    5: 0.8, 6: 1.0, 7: 1.2, 8: 1.5, 9: 1.8, 10: 2.2, 11: 2.6, 12: 3.2,
    13: 3.8, 14: 4.5, 15: 5.5, 16: 6.5, 17: 8.0, 18: 9.5,
}
REFERENCE_STROKE_WIDTH = 3.0
ZOOM_MAX_STROKE_PX = {17: 14, 18: 17}
SUPERSAMPLE = 2


def _parse_stroke_width(val) -> float:
    """Parse stroke width from '2px', '0.5px', 2, etc."""
    if val is None:
        return REFERENCE_STROKE_WIDTH
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().lower().replace(' ', '')
    if not s or s == 'nan':
        return REFERENCE_STROKE_WIDTH
    m = re.match(r'^([\d.]+)\s*px?$', s)
    if m:
        return float(m.group(1))
    try:
        return float(s)
    except ValueError:
        return REFERENCE_STROKE_WIDTH


def _hex_to_rgb(hex_str) -> Optional[Tuple[int, int, int]]:
    if not hex_str or not isinstance(hex_str, str):
        return None
    hex_str = hex_str.strip().lstrip('#')
    if len(hex_str) == 6:
        try:
            return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))
        except ValueError:
            pass
    return None


def geometry_to_line_coords(geom):
    """Yield list of (lon, lat) coords for each line part. Handles LineString, MultiLineString, Polygon, MultiPolygon."""
    if geom is None or geom.is_empty:
        return
    if geom.geom_type == 'LineString':
        yield list(geom.coords)
    elif geom.geom_type == 'MultiLineString':
        for line in geom.geoms:
            yield list(line.coords)
    elif geom.geom_type == 'Polygon':
        ext = geom.exterior
        if ext and len(ext.coords) >= 2:
            yield list(ext.coords)
    elif geom.geom_type == 'MultiPolygon':
        for poly in geom.geoms:
            if poly.exterior and len(poly.exterior.coords) >= 2:
                yield list(poly.exterior.coords)


class UniversalMixedLinePolygonTileGenerator:
    """
    Tile generator for a directory of GeoJSON files: some layers are lines, some are polygons.
    Colors from feature properties (HEX, Stroke Width). Renders polygons first, then lines.
    """

    def __init__(
        self,
        data_dir: str,
        output_dir: str,
        skip_existing: bool = True,
    ):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.skip_existing = skip_existing
        self.spatial_index = index.Index() if HAS_RTREE else None
        self.all_fids = []  # all feature ids (for fallback when no rtree)
        self.feature_id_counter = 0
        self.feature_lookup = {}  # id -> { 'type': 'line'|'polygon', 'geometry', ... }
        self.polygon_ids = []
        self.line_ids = []
        self.bounds = None
        self.source_crs = None
        self.needs_transform = None
        self.transformer = None

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._load_all_geojson()

    def _load_all_geojson(self):
        geojson_files = sorted(self.data_dir.glob("*.geojson"))
        if not geojson_files:
            raise FileNotFoundError(f"No .geojson files in {self.data_dir}")

        print(f"Loading {len(geojson_files)} GeoJSON files from {self.data_dir}")

        for geojson_path in geojson_files:
            with open(geojson_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            features = data.get("features", [])
            if not features:
                continue

            # CRS detection (first file only)
            if self.needs_transform is None and HAS_PYPROJ:
                crs_info = data.get("crs", {})
                if crs_info:
                    crs_name = crs_info.get("properties", {}).get("name", "")
                    if "3857" in crs_name:
                        self.source_crs = "EPSG:3857"
                        self.needs_transform = True
                        self.transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
                    else:
                        self.needs_transform = False
                else:
                    self.needs_transform = False

            for feature in features:
                geom = feature.get("geometry")
                if not geom:
                    continue
                geom = shape(geom)
                if self.needs_transform and self.transformer:
                    def transform_func(x, y, z=None):
                        r = self.transformer.transform(x, y)
                        return (r[0], r[1], z) if z is not None else r
                    geom = transform(transform_func, geom)
                if not getattr(geom, "is_valid", True) or (hasattr(geom, "is_valid") and not geom.is_valid):
                    try:
                        geom = make_valid(geom)
                    except Exception:
                        try:
                            geom = geom.buffer(0)
                        except Exception:
                            continue
                if geom.is_empty:
                    continue

                props = feature.get("properties") or {}
                hex_color = props.get("HEX") or props.get("hex") or props.get("fill") or "#999999"
                hex_color = str(hex_color).strip() if hex_color else "#999999"
                if not hex_color or hex_color.lower() == "nan":
                    hex_color = "#999999"

                gtype = geom.geom_type
                if gtype in ("LineString", "MultiLineString"):
                    stroke_width = _parse_stroke_width(
                        props.get("Stroke Width") or props.get("stroke_width") or props.get("stroke-width")
                    )
                    fid = self.feature_id_counter
                    self.feature_id_counter += 1
                    self.feature_lookup[fid] = {
                        "type": "line",
                        "geometry": geom,
                        "stroke_hex": hex_color,
                        "stroke_width_ratio": stroke_width / REFERENCE_STROKE_WIDTH,
                        "_line_coords": list(geometry_to_line_coords(geom)),
                    }
                    if HAS_RTREE:
                        self.spatial_index.insert(fid, geom.bounds)
                    self.all_fids.append(fid)
                    self.line_ids.append(fid)
                elif gtype in ("Polygon", "MultiPolygon"):
                    fid = self.feature_id_counter
                    self.feature_id_counter += 1
                    self.feature_lookup[fid] = {
                        "type": "polygon",
                        "geometry": geom,
                        "fill_hex": hex_color,
                    }
                    if HAS_RTREE:
                        self.spatial_index.insert(fid, geom.bounds)
                    self.all_fids.append(fid)
                    self.polygon_ids.append(fid)

        if not self.feature_lookup:
            raise ValueError("No features loaded from any GeoJSON file")

        # Bounds
        minx = min(self.feature_lookup[fid]["geometry"].bounds[0] for fid in self.feature_lookup)
        miny = min(self.feature_lookup[fid]["geometry"].bounds[1] for fid in self.feature_lookup)
        maxx = max(self.feature_lookup[fid]["geometry"].bounds[2] for fid in self.feature_lookup)
        maxy = max(self.feature_lookup[fid]["geometry"].bounds[3] for fid in self.feature_lookup)
        self.bounds = (minx, miny, maxx, maxy)

        print(f"Loaded {len(self.polygon_ids)} polygon features, {len(self.line_ids)} line features")
        print(f"Bounds: {minx:.4f}, {miny:.4f} to {maxx:.4f}, {maxy:.4f}")

    def get_bounds(self):
        return self.bounds

    def get_line_width(self, zoom: int) -> float:
        return ZOOM_RESOLUTION.get(zoom, 3.0)

    def wgs84_to_tile_pixel(self, lon: float, lat: float, tile_x: int, tile_y: int, zoom: int) -> Tuple[int, int]:
        lat = max(-85.051129, min(85.051129, lat))
        tile_lon = (lon + 180) / 360 * (2 ** zoom)
        tile_lat = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * (2 ** zoom)
        pixel_x = round((tile_lon - tile_x) * self.tile_size)
        pixel_y = round((tile_lat - tile_y) * self.tile_size)
        return pixel_x, pixel_y

    def draw_line(
        self,
        draw: ImageDraw.Draw,
        coordinates: List[Tuple[float, float]],
        color_rgb: Tuple[int, int, int],
        width: int,
        tile_x: int, tile_y: int, zoom: int,
        offset_x: int = 0, offset_y: int = 0,
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
            px, py = self.wgs84_to_tile_pixel(lon, lat, tile_x, tile_y, zoom)
            if scale > 1:
                px, py = px * scale + offset_x, py * scale + offset_y
            else:
                px, py = px + offset_x, py + offset_y
            pixel_coords.append((px, py))
        if len(pixel_coords) < 2:
            return
        w = max(1, round(width * scale)) if scale > 1 else width
        try:
            draw.line(pixel_coords, fill=color_rgb, width=w, joint="curve")
        except TypeError:
            draw.line(pixel_coords, fill=color_rgb, width=w)

    def render_polygon_to_tile(
        self,
        draw: ImageDraw.Draw,
        polygon,
        tile_bounds,
        img_size: int,
        buffer_pixels: int,
        fill_rgb: Tuple[int, int, int],
        outline_width: int = 1,
    ):
        """Draw one polygon (with possible holes) onto the tile image."""
        lon_range = tile_bounds.east - tile_bounds.west
        lat_range = tile_bounds.north - tile_bounds.south

        def to_px(lon, lat):
            px = ((lon - tile_bounds.west) / lon_range * img_size) + buffer_pixels
            py = ((tile_bounds.north - lat) / lat_range * img_size) + buffer_pixels
            return (int(px), int(py))

        exterior_pixels = [to_px(c[0], c[1]) for c in polygon.exterior.coords]
        if len(exterior_pixels) < 3:
            return
        fill_rgba = fill_rgb + (255,)
        black = (0, 0, 0, 255)
        draw.polygon(exterior_pixels, fill=fill_rgba)
        if outline_width > 0:
            closed = exterior_pixels + [exterior_pixels[0]]
            draw.line(closed, fill=black, width=outline_width)
        for interior in polygon.interiors:
            interior_pixels = [to_px(c[0], c[1]) for c in interior.coords]
            if len(interior_pixels) >= 3:
                draw.polygon(interior_pixels, fill=(0, 0, 0, 0))
                if outline_width > 0:
                    closed_i = interior_pixels + [interior_pixels[0]]
                    draw.line(closed_i, fill=black, width=outline_width)

    def get_outline_width(self, zoom: int) -> int:
        if zoom <= 10:
            return 2
        elif zoom <= 13:
            return 1
        return 1

    def generate_tile(self, x: int, y: int, zoom: int) -> Image.Image:
        tile_bounds = mercantile.bounds(x, y, zoom)
        tile_width_deg = tile_bounds.east - tile_bounds.west
        tile_height_deg = tile_bounds.north - tile_bounds.south

        line_width_base = max(1, int(self.get_line_width(zoom)))
        bleed_px = max(2, line_width_base * 2)
        scale = SUPERSAMPLE
        canvas_size = (self.tile_size + 2 * bleed_px) * scale
        bleed_scaled = bleed_px * scale
        buffer_deg_lon = tile_width_deg * (bleed_px / self.tile_size)
        buffer_deg_lat = tile_height_deg * (bleed_px / self.tile_size)
        tile_box = box(
            tile_bounds.west - buffer_deg_lon,
            tile_bounds.south - buffer_deg_lat,
            tile_bounds.east + buffer_deg_lon,
            tile_bounds.north + buffer_deg_lat,
        )

        img_size = self.tile_size * scale
        buffer_pixels = int(bleed_scaled)
        outline_width = self.get_outline_width(zoom)

        img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 1) Draw polygons (filled)
        if HAS_RTREE:
            candidate_ids = list(self.spatial_index.intersection(tile_box.bounds))
        else:
            candidate_ids = [fid for fid in self.all_fids if self.feature_lookup[fid]["geometry"].intersects(tile_box)]
        for fid in candidate_ids:
            if fid not in self.feature_lookup:
                continue
            feat = self.feature_lookup[fid]
            if feat["type"] != "polygon":
                continue
            geom = feat["geometry"]
            if not geom.intersects(tile_box):
                continue
            fill_rgb = _hex_to_rgb(feat["fill_hex"])
            if not fill_rgb:
                continue
            if geom.geom_type == "Polygon":
                if geom.area < 1e-12:
                    continue
                self.render_polygon_to_tile(
                    draw, geom, tile_bounds, img_size, buffer_pixels,
                    fill_rgb, outline_width=outline_width,
                )
            else:
                for poly in geom.geoms:
                    if poly.area < 1e-12:
                        continue
                    self.render_polygon_to_tile(
                        draw, poly, tile_bounds, img_size, buffer_pixels,
                        fill_rgb, outline_width=outline_width,
                    )

        # 2) Draw lines (strokes)
        for fid in candidate_ids:
            if fid not in self.feature_lookup:
                continue
            feat = self.feature_lookup[fid]
            if feat["type"] != "line":
                continue
            geom = feat["geometry"]
            if not geom.intersects(tile_box):
                continue
            color_hex = feat["stroke_hex"]
            color_rgb = _hex_to_rgb(color_hex)
            if not color_rgb:
                color_rgb = (153, 153, 153)
            width_px = max(1, int(line_width_base * feat["stroke_width_ratio"]))
            if zoom in ZOOM_MAX_STROKE_PX:
                width_px = min(width_px, ZOOM_MAX_STROKE_PX[zoom])
            for coords in feat["_line_coords"]:
                if len(coords) >= 2:
                    self.draw_line(
                        draw, coords, color_rgb, width_px, x, y, zoom,
                        bleed_scaled, bleed_scaled, scale=scale,
                    )

        # Crop to tile and downsample
        cropped = img.crop((
            bleed_scaled, bleed_scaled,
            bleed_scaled + self.tile_size * scale,
            bleed_scaled + self.tile_size * scale,
        ))
        if scale > 1:
            cropped = cropped.resize((self.tile_size, self.tile_size), Image.LANCZOS)
        return cropped

    def generate_tiles(self, min_zoom: int = 5, max_zoom: int = 18):
        minx, miny, maxx, maxy = self.bounds
        tile_size_deg = 360.0 / (2 ** max_zoom)
        buffer_deg = tile_size_deg * 3
        expanded = [minx - buffer_deg, miny - buffer_deg, maxx + buffer_deg, maxy + buffer_deg]

        total = 0
        start = time.time()
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
                img = self.generate_tile(tile.x, tile.y, zoom) if within else Image.new("RGBA", (self.tile_size, self.tile_size), (0, 0, 0, 0))
                img.save(tile_path, "PNG", optimize=True)
                total += 1
            print(f"Zoom {zoom}: {len(tiles)} tiles")
        elapsed = time.time() - start
        print(f"Done: {total} tiles in {elapsed:.1f}s")

    def create_tilejson(self, name: str = "Mixed Line Polygon"):
        minx, miny, maxx, maxy = self.bounds
        center = [(minx + maxx) / 2, (miny + maxy) / 2, 10]
        tilejson = {
            "tilejson": "3.0.0",
            "name": name,
            "version": "1.0.0",
            "scheme": "xyz",
            "tiles": ["./{z}/{x}/{y}.png"],
            "minzoom": 5,
            "maxzoom": 18,
            "bounds": [minx, miny, maxx, maxy],
            "center": center,
        }
        (self.output_dir / "tilejson.json").write_text(json.dumps(tilejson, indent=2))
        print(f"TileJSON: {self.output_dir}/tilejson.json")

    def generate_html_viewer(self, layer_name: str = "Mixed Line Polygon", min_zoom: int = 5, max_zoom: int = 18):
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
  <title>{layer_name} - Tiles</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style> body, html, #map {{ margin:0; padding:0; height:100%; }} </style>
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
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ attribution: 'Esri', maxZoom: 19 }}).addTo(map);
    L.tileLayer('./{{z}}/{{x}}/{{y}}.png', {{ minZoom: {min_zoom}, maxZoom: {max_zoom}, opacity: 0.9, attribution: '{layer_name}' }}).addTo(map);
  </script>
</body>
</html>"""
        (self.output_dir / "index.html").write_text(html, encoding="utf-8")
        print(f"Viewer: {self.output_dir}/index.html")


def main():
    parser = argparse.ArgumentParser(
        description="Universal mixed line + polygon tile generator (directory of GeoJSON; colors from properties)"
    )
    parser.add_argument("data_dir", help="Directory containing GeoJSON files (e.g. TamilNadu CRZ layers_processed)")
    parser.add_argument("output_dir", help="Output directory for tiles (z/x/y.png)")
    parser.add_argument("--force", "-f", action="store_true", help="Regenerate all tiles")
    parser.add_argument("--min-zoom", type=int, default=5)
    parser.add_argument("--max-zoom", type=int, default=18)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        print(f"Error: data_dir not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        gen = UniversalMixedLinePolygonTileGenerator(
            str(data_dir),
            args.output_dir,
            skip_existing=not args.force,
        )
        gen.generate_tiles(min_zoom=args.min_zoom, max_zoom=args.max_zoom)
        gen.create_tilejson(name=data_dir.name)
        gen.generate_html_viewer(layer_name=data_dir.name, min_zoom=args.min_zoom, max_zoom=args.max_zoom)
        print(f"Tiles written to {args.output_dir}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
