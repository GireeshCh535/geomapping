#!/usr/bin/env python3
"""
Universal Line / Polygon Styled Tile Generator
=============================================

Renders GeoJSON with LineString, MultiLineString, Polygon, or MultiPolygon
using the same styling approach as the Hyderabad RRR script:
- Stroke colour and width from feature properties (stroke, stroke-width) or from legend.csv
- Draw order by Style_role (outer first, then inner)
- Polygon/MultiPolygon: drawn as their exterior boundary lines (same stroke styling)

Legend CSV format (optional):
  style_role,stroke,stroke_width,description
  outer,#FFFFFF,6,Outer edge
  inner,#313131,4,Inner body

Usage:
  python universal_line_styled_tile_generator.py data/49\ \(2\).geojson output_tiles
  python universal_line_styled_tile_generator.py data/49\ \(2\).geojson output_tiles --legend data/49_ring_roads/legend.csv
  python universal_line_styled_tile_generator.py geojson_path output_dir [--legend path] [--force] [--swap-xy] [--min-zoom 5] [--max-zoom 18]
"""

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any

import pandas as pd
import mercantile
from shapely.geometry import LineString, MultiLineString, Polygon, MultiPolygon, box
from shapely.ops import transform
from shapely.validation import make_valid
from PIL import Image, ImageDraw

logging_available = True
try:
    import geopandas as gpd
except ImportError:
    gpd = None

try:
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
    logger = logging.getLogger(__name__)
except Exception:
    logger = None
    def log_info(*a): print('[INFO]', *a)
    def log_debug(*a): pass
    def log_error(*a): print('[ERROR]', *a)

if logger:
    log_info = logger.info
    log_debug = logger.debug
    log_error = logger.error

# Draw order: outer first, then inner (same as RRR)
STYLE_ORDER = {'outer': 0, 'inner': 1}

# Base line width per zoom. Kept smaller for thinner lines; higher resolution comes from supersampling.
ZOOM_RESOLUTION = {
    5: 0.8, 6: 1.0, 7: 1.2, 8: 1.5, 9: 1.8, 10: 2.2, 11: 2.6, 12: 3.2,
    13: 3.8, 14: 4.5, 15: 5.5, 16: 6.5, 17: 8.0, 18: 9.5,
}
REFERENCE_STROKE_WIDTH = 3.0

# Cap stroke at high zoom. Outer (white) must be WIDER than inner (dark) so the border shows.
# Inner (dark center): stricter cap so it stays thin and doesn't merge at interchanges.
ZOOM_MAX_STROKE_PX_INNER = {17: 10, 18: 12}
# Outer (white border): can be wider than inner so white outline is visible.
ZOOM_MAX_STROKE_PX_OUTER = {17: 14, 18: 17}

# Render at 2x then downsample to 256 for sharper, higher-resolution result.
SUPERSAMPLE = 2


def load_legend(legend_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load legend CSV: style_role -> {stroke, stroke_width}."""
    legend = {}
    if not legend_path or not legend_path.exists():
        return legend
    with open(legend_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            role = (row.get('style_role') or row.get('category') or '').strip().lower()
            if not role:
                continue
            stroke = (row.get('stroke') or row.get('fill_color') or '#999999').strip()
            try:
                stroke_width = float(row.get('stroke_width', row.get('stroke-width', REFERENCE_STROKE_WIDTH)))
            except (ValueError, TypeError):
                stroke_width = REFERENCE_STROKE_WIDTH
            legend[role] = {'stroke': stroke, 'stroke_width': stroke_width}
    return legend


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
    else:
        return


class UniversalLineStyledTileGenerator:
    """
    Universal tile generator for LineString / MultiLineString / Polygon / MultiPolygon
    with styling from properties or legend (same rendering as RRR styled).
    """

    def __init__(
        self,
        geojson_path: str,
        output_dir: str,
        legend_path: Optional[str] = None,
        skip_existing: bool = True,
        swap_xy: bool = False,
    ):
        self.geojson_path = Path(geojson_path)
        self.output_dir = Path(output_dir)
        self.legend_path = Path(legend_path) if legend_path else None
        self.tile_size = 256
        self.skip_existing = skip_existing
        self.buffer_factor = 0.15
        self._swap_xy = swap_xy
        self.bounds = None
        self.gdf = None
        self.legend = load_legend(self.legend_path) if self.legend_path else {}
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._load_data()
        log_info("Universal line styled tile generator initialized: %s -> %s", geojson_path, output_dir)

    def _load_data(self):
        if not self.geojson_path.exists():
            raise FileNotFoundError(f"GeoJSON not found: {self.geojson_path}")
        if gpd is None:
            raise ImportError("geopandas is required. pip install geopandas")
        log_info("Loading GeoJSON...")
        self.gdf = gpd.read_file(self.geojson_path)
        if self.gdf.empty:
            raise ValueError("No features in GeoJSON")
        if self.gdf.crs is None:
            self.gdf.set_crs('EPSG:4326', inplace=True)
        elif self.gdf.crs.to_string() != 'EPSG:4326':
            self.gdf = self.gdf.to_crs('EPSG:4326')

        def fix_geom(geom):
            if geom is None or geom.is_empty:
                return geom
            if not getattr(geom, 'is_valid', True) or (hasattr(geom, 'is_valid') and not geom.is_valid):
                try:
                    geom = make_valid(geom)
                except Exception:
                    try:
                        geom = geom.buffer(0)
                    except Exception:
                        pass
            return geom

        self.gdf['geometry'] = self.gdf.geometry.apply(fix_geom)
        self.gdf = self.gdf[self.gdf.geometry.notna() & self.gdf.geometry.is_valid].copy()

        # Optionally fix coordinate order: (lat,lon) -> (lon,lat) for correct tile alignment
        b = self.gdf.total_bounds
        minx, miny, maxx, maxy = b[0], b[1], b[2], b[3]
        do_swap = getattr(self, '_swap_xy', False)
        if not do_swap:
            x_in_lat_range = -90 <= minx and maxx <= 90
            y_span_large = (maxy - miny) > 100
            do_swap = x_in_lat_range and y_span_large
        if do_swap:
            def swap_xy(x, y):
                return (y, x)
            self.gdf['geometry'] = self.gdf.geometry.apply(lambda g: transform(swap_xy, g) if g and not g.is_empty else g)
            log_info("Swapped coordinates to (lon,lat) for correct alignment")

        # Normalize property names (Style_role vs _style_role, stroke-width vs stroke_width)
        if 'Style_role' in self.gdf.columns:
            self.gdf['_style_role'] = self.gdf['Style_role'].astype(str).str.strip().str.lower()
        elif '_style_role' not in self.gdf.columns:
            self.gdf['_style_role'] = 'inner'
        if 'stroke-width' in self.gdf.columns and 'stroke_width' not in self.gdf.columns:
            self.gdf['stroke_width'] = self.gdf['stroke-width']
        self.gdf['_draw_order'] = self.gdf['_style_role'].map(
            lambda x: STYLE_ORDER.get(str(x).strip().lower() if isinstance(x, str) else str(x).lower(), 0)
        )
        self.gdf = self.gdf.sort_values('_draw_order').reset_index(drop=True)

        # If legend has both outer and inner but all features are "inner", draw two layers (outer then inner) from same geometry
        legend_roles = set(self.legend.keys())
        all_inner = (self.gdf['_style_role'].astype(str).str.strip().str.lower() == 'inner').all()
        if legend_roles >= {'outer', 'inner'} and all_inner and len(self.gdf) > 0:
            parts = []
            for role in ('outer', 'inner'):
                part = self.gdf.copy()
                part['_style_role'] = role
                part['_draw_order'] = STYLE_ORDER.get(role, 0)
                parts.append(part)
            self.gdf = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=self.gdf.crs)
            self.gdf = self.gdf.sort_values('_draw_order').reset_index(drop=True)
            log_info("Legend has outer+inner: drawing two layers (outer white, then inner) from same geometry")

        self.bounds = self.gdf.total_bounds
        self.spatial_index = self.gdf.sindex

        # Precompute stroke (color + width ratio) and line coords once per feature for fast tile generation
        stroke_resolved = self.gdf.apply(self._resolve_stroke_for_row, axis=1)
        self.gdf['_stroke_color'] = [t[0] for t in stroke_resolved]
        self.gdf['_stroke_width_ratio'] = [t[1] / REFERENCE_STROKE_WIDTH for t in stroke_resolved]
        self.gdf['_line_coords'] = self.gdf.geometry.apply(lambda g: list(geometry_to_line_coords(g)))

        log_info("Loaded %d features", len(self.gdf))

    def get_line_width(self, zoom: int) -> float:
        return ZOOM_RESOLUTION.get(zoom, 3.0)

    def _resolve_stroke_for_row(self, row) -> Tuple[str, float]:
        """Return (stroke_hex, stroke_width_val) for a feature row (no zoom). Used to precompute _stroke_color and _stroke_width_ratio."""
        color = None
        for key in ('stroke', 'Stroke'):
            if key in row.index and row.get(key) is not None:
                v = row[key]
                if isinstance(v, str) and v.strip() and v.strip().lower() != 'nan':
                    color = v.strip()
                    break
        if not color:
            style_role = str(row.get('_style_role', row.get('Style_role', 'inner')) or 'inner').strip().lower()
            color = self.legend.get(style_role, {}).get('stroke', '#999999')
        if not color or (isinstance(color, (int, float)) and math.isnan(color)):
            color = '#999999'
        color = str(color).strip()
        if not color or color.lower() == 'nan':
            color = '#999999'

        stroke_width_val = None
        for key in ('stroke-width', 'stroke_width'):
            if key in row.index and row.get(key) is not None:
                v = row[key]
                if v is not None and str(v).strip().lower() not in ('', 'nan', 'none'):
                    try:
                        stroke_width_val = float(v)
                        break
                    except (TypeError, ValueError):
                        pass
        if stroke_width_val is None:
            style_role = str(row.get('_style_role', row.get('Style_role', 'inner')) or 'inner').strip().lower()
            # For 'outer' (border) always use legend so border thickness is consistent
            if style_role == 'outer':
                stroke_width_val = self.legend.get(style_role, {}).get('stroke_width', REFERENCE_STROKE_WIDTH * 2)
            else:
                # For 'inner': use Width_in_Metres (e.g. HMDA roads) to scale line width when present
                for key in ('Width_in_Metres', 'width_in_metres', 'width'):
                    if key in row.index and row.get(key) is not None:
                        try:
                            w = float(row[key])
                            if w > 0:
                                stroke_width_val = max(1.0, min(20.0, REFERENCE_STROKE_WIDTH * (w / 30.0)))
                                break
                        except (TypeError, ValueError):
                            pass
                if stroke_width_val is None:
                    stroke_width_val = self.legend.get(style_role, {}).get('stroke_width', REFERENCE_STROKE_WIDTH)
        return color, float(stroke_width_val)

    def get_feature_stroke(self, row, zoom: int) -> Tuple[str, float]:
        """Return (stroke_hex, stroke_width_px) for a feature row."""
        color = None
        for key in ('stroke', 'Stroke'):
            if key in row.index and row.get(key) is not None:
                v = row[key]
                if isinstance(v, str) and v.strip() and v.strip().lower() != 'nan':
                    color = v.strip()
                    break
        if not color:
            style_role = str(row.get('_style_role', row.get('Style_role', 'inner')) or 'inner').strip().lower()
            color = self.legend.get(style_role, {}).get('stroke', '#999999')
        if not color or (isinstance(color, (int, float)) and math.isnan(color)):
            color = '#999999'
        color = str(color).strip()
        if not color or color.lower() == 'nan':
            color = '#999999'

        stroke_width_val = None
        for key in ('stroke-width', 'stroke_width'):
            if key in row.index and row.get(key) is not None:
                v = row[key]
                if v is not None and str(v).strip().lower() not in ('', 'nan', 'none'):
                    try:
                        stroke_width_val = float(v)
                        break
                    except (TypeError, ValueError):
                        pass
        if stroke_width_val is None:
            style_role = str(row.get('_style_role', row.get('Style_role', 'inner')) or 'inner').strip().lower()
            stroke_width_val = self.legend.get(style_role, {}).get('stroke_width', REFERENCE_STROKE_WIDTH)
        base_width = self.get_line_width(zoom)
        try:
            width_px = max(1, int(base_width * float(stroke_width_val) / REFERENCE_STROKE_WIDTH))
        except (TypeError, ValueError):
            width_px = max(1, int(base_width))
        return color, width_px

    def wgs84_to_tile_pixel(self, lon: float, lat: float, tile_x: int, tile_y: int, zoom: int) -> Tuple[int, int]:
        lat = max(-85.051129, min(85.051129, lat))
        tile_lon = (lon + 180) / 360 * (2 ** zoom)
        tile_lat = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * (2 ** zoom)
        pixel_x = round((tile_lon - tile_x) * 256)
        pixel_y = round((tile_lat - tile_y) * 256)
        return pixel_x, pixel_y

    def draw_line(
        self,
        draw: ImageDraw.Draw,
        coordinates: List[Tuple[float, float]],
        color: str,
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
            draw.line(pixel_coords, fill=color, width=w, joint="curve")
            return
        except TypeError:
            pass
        try:
            ls = LineString(pixel_coords)
            if ls.is_empty or not ls.is_valid:
                draw.line(pixel_coords, fill=color, width=w)
                return
            half = max(0.5, w / 2.0)
            buffered = ls.buffer(half, cap_style=2, join_style=2)
            if buffered.is_empty:
                draw.line(pixel_coords, fill=color, width=w)
                return
            geoms = buffered.geoms if hasattr(buffered, "geoms") else [buffered]
            for geom in geoms:
                if not isinstance(geom, Polygon) or geom.is_empty:
                    continue
                ext = geom.exterior
                poly_coords = [(float(x), float(y)) for x, y in zip(ext.xy[0], ext.xy[1])]
                if len(poly_coords) >= 3:
                    draw.polygon(poly_coords, fill=color)
        except Exception:
            try:
                draw.line(pixel_coords, fill=color, width=w)
            except Exception:
                for i in range(len(pixel_coords) - 1):
                    try:
                        draw.line([pixel_coords[i], pixel_coords[i + 1]], fill=color, width=w)
                    except Exception:
                        continue

    def create_blank_tile(self) -> Image.Image:
        return Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))

    def generate_tile(self, x: int, y: int, zoom: int) -> Image.Image:
        scale = SUPERSAMPLE
        line_width_base = max(1, int(self.get_line_width(zoom)))
        bleed_px = max(2, line_width_base * 2)
        canvas_size = (256 + 2 * bleed_px) * scale
        bleed_scaled = bleed_px * scale
        img = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        tile_bounds = mercantile.bounds(x, y, zoom)
        tile_width_deg = tile_bounds.east - tile_bounds.west
        tile_height_deg = tile_bounds.north - tile_bounds.south
        buffer_px = bleed_px + line_width_base
        buffer_lon = tile_width_deg * (buffer_px / 256.0)
        buffer_lat = tile_height_deg * (buffer_px / 256.0)
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
            color = row['_stroke_color']
            width_px = max(1, int(line_width_base * row['_stroke_width_ratio']))
            role = str(row.get('_style_role', '')).strip().lower()
            max_px = ZOOM_MAX_STROKE_PX_OUTER.get(zoom) if role == 'outer' else ZOOM_MAX_STROKE_PX_INNER.get(zoom)
            if max_px is not None:
                width_px = min(width_px, max_px)
            for coords in row['_line_coords']:
                if len(coords) >= 2:
                    self.draw_line(
                        draw, coords, color, width_px, x, y, zoom,
                        bleed_scaled, bleed_scaled, scale=scale,
                    )

        cropped = img.crop((bleed_scaled, bleed_scaled, bleed_scaled + 256 * scale, bleed_scaled + 256 * scale))
        if scale > 1:
            cropped = cropped.resize((256, 256), Image.LANCZOS)
        return cropped

    def generate_tiles(self, min_zoom: int = 5, max_zoom: int = 18):
        log_info("Generating tiles (zoom %d–%d)", min_zoom, max_zoom)
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
                    tile_bounds.west < maxx and tile_bounds.east > minx and
                    tile_bounds.south < maxy and tile_bounds.north > miny
                )
                img = self.generate_tile(tile.x, tile.y, zoom) if within else self.create_blank_tile()
                img.save(tile_path, 'PNG', optimize=True)
                total += 1
            log_info("Zoom %d: %d tiles", zoom, len(tiles))
        elapsed = time.time() - start
        log_info("Done: %d tiles in %.1fs", total, elapsed)

    def create_tilejson(self, name: str = "Universal Line Styled", min_zoom: int = 5, max_zoom: int = 18):
        minx, miny, maxx, maxy = self.bounds
        center = [(minx + maxx) / 2, (miny + maxy) / 2, 10]
        tilejson = {
            "tilejson": "3.0.0",
            "name": name,
            "version": "1.0.0",
            "scheme": "xyz",
            "tiles": [f"./{{z}}/{{x}}/{{y}}.png"],
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "bounds": [minx, miny, maxx, maxy],
            "center": center,
        }
        (self.output_dir / "tilejson.json").write_text(json.dumps(tilejson, indent=2))
        log_info("TileJSON: %s/tilejson.json", self.output_dir)

    def generate_html_viewer(
        self,
        layer_name: str = "Line Styled",
        min_zoom: int = 5,
        max_zoom: int = 18,
    ):
        """Generate HTML viewer: fit to data bounds, use actual zoom range, restrict pan to avoid 404s."""
        minx, miny, maxx, maxy = self.bounds
        center_lat = (miny + maxy) / 2
        center_lon = (minx + maxx) / 2
        # Slightly expand bounds so maxBounds doesn't feel clamped; Leaflet wants [southWest, northEast]
        pad = 0.02
        sw_lat = miny - pad
        sw_lon = minx - pad
        ne_lat = maxy + pad
        ne_lon = maxx + pad
        default_zoom = max(min_zoom, min(11, max_zoom))

        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{layer_name} - Seamless Tiles</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    body, html, #map {{ margin:0; padding:0; height:100%; }}
    .info {{ padding: 10px; background: white; border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.2); }}
  </style>
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
      attribution: 'Esri',
      maxZoom: 19
    }}).addTo(map);

    L.tileLayer('./{{z}}/{{x}}/{{y}}.png', {{
      minZoom: {min_zoom},
      maxZoom: {max_zoom},
      opacity: 0.9,
      attribution: '{layer_name}'
    }}).addTo(map);

    const info = L.control({{position: 'topright'}});
    info.onAdd = function() {{
      this._div = L.DomUtil.create('div', 'info');
      this._div.innerHTML = '<b>{layer_name}</b><br/>Seamless tiles<br/>Zoom: ' + map.getZoom();
      return this._div;
    }};
    info.addTo(map);

    map.on('zoomend', function() {{
      info._div.innerHTML = '<b>{layer_name}</b><br/>Seamless tiles<br/>Zoom: ' + map.getZoom();
    }});
  </script>
</body>
</html>"""

        viewer_path = self.output_dir / "index.html"
        viewer_path.write_text(html, encoding="utf-8")
        log_info("Viewer saved: %s", viewer_path)


def main():
    parser = argparse.ArgumentParser(
        description="Universal line/polygon styled tile generator (LineString, MultiLineString, Polygon, MultiPolygon)"
    )
    parser.add_argument("geojson", help="Path to GeoJSON file")
    parser.add_argument("output_dir", help="Output directory for tiles")
    parser.add_argument("--legend", "-l", help="Path to legend CSV (style_role, stroke, stroke_width)")
    parser.add_argument("--force", "-f", action="store_true", help="Regenerate all tiles")
    parser.add_argument("--swap-xy", action="store_true", help="Force (lat,lon)->(lon,lat) if overlay aligns wrong")
    parser.add_argument(
        "--min-zoom",
        dest="min_zoom",
        type=int,
        default=5,
        help="Minimum zoom level to generate (default: 5)",
    )
    parser.add_argument(
        "--max-zoom",
        dest="max_zoom",
        type=int,
        default=18,
        help="Maximum zoom level to generate (default: 18)",
    )
    args = parser.parse_args()

    # Log zoom range so it's obvious what was parsed (avoids confusion when only one zoom is requested)
    log_info("Requested zoom range: --min-zoom %d --max-zoom %d", args.min_zoom, args.max_zoom)

    if not Path(args.geojson).exists():
        log_error("GeoJSON not found: %s", args.geojson)
        sys.exit(1)

    try:
        gen = UniversalLineStyledTileGenerator(
            args.geojson,
            args.output_dir,
            legend_path=args.legend,
            skip_existing=not args.force,
            swap_xy=args.swap_xy,
        )
        gen.generate_tiles(min_zoom=args.min_zoom, max_zoom=args.max_zoom)
        gen.create_tilejson(
            name=Path(args.geojson).stem,
            min_zoom=args.min_zoom,
            max_zoom=args.max_zoom,
        )
        gen.generate_html_viewer(
            layer_name=Path(args.geojson).stem,
            min_zoom=args.min_zoom,
            max_zoom=args.max_zoom,
        )
        log_info("Tiles written to %s", args.output_dir)
    except Exception as e:
        if logger:
            logger.exception("%s", e)
        else:
            print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
