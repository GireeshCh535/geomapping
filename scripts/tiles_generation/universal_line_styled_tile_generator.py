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
  python universal_line_styled_tile_generator.py geojson_path output_dir [--legend path] [--force] [--min-zoom 5] [--max-zoom 18]
"""

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any

import mercantile
from shapely.geometry import LineString, MultiLineString, Polygon, MultiPolygon, box
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

ZOOM_RESOLUTION = {
    5: 1.0, 6: 1.3, 7: 1.6, 8: 2.0, 9: 2.5, 10: 3.0, 11: 3.5, 12: 4.5,
    13: 5.5, 14: 6.5, 15: 8.0, 16: 10.0, 17: 12.0, 18: 15.0,
}
REFERENCE_STROKE_WIDTH = 3.0


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
    ):
        self.geojson_path = Path(geojson_path)
        self.output_dir = Path(output_dir)
        self.legend_path = Path(legend_path) if legend_path else None
        self.tile_size = 256
        self.skip_existing = skip_existing
        self.buffer_factor = 0.15
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
        self.bounds = self.gdf.total_bounds
        self.spatial_index = self.gdf.sindex
        log_info("Loaded %d features", len(self.gdf))

    def get_line_width(self, zoom: int) -> float:
        return ZOOM_RESOLUTION.get(zoom, 3.0)

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
        pixel_x = int((tile_lon - tile_x) * 256)
        pixel_y = int((tile_lat - tile_y) * 256)
        return pixel_x, pixel_y

    def draw_line(
        self,
        draw: ImageDraw.Draw,
        coordinates: List[Tuple[float, float]],
        color: str,
        width: int,
        tile_x: int, tile_y: int, zoom: int,
        offset_x: int = 0, offset_y: int = 0,
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
            pixel_coords.append((px + offset_x, py + offset_y))
        if len(pixel_coords) < 2:
            return
        try:
            draw.line(pixel_coords, fill=color, width=width, joint="curve")
            return
        except TypeError:
            pass
        try:
            ls = LineString(pixel_coords)
            if ls.is_empty or not ls.is_valid:
                draw.line(pixel_coords, fill=color, width=width)
                return
            half = max(0.5, width / 2.0)
            buffered = ls.buffer(half, cap_style=2, join_style=2)
            if buffered.is_empty:
                draw.line(pixel_coords, fill=color, width=width)
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
                draw.line(pixel_coords, fill=color, width=width)
            except Exception:
                for i in range(len(pixel_coords) - 1):
                    try:
                        draw.line([pixel_coords[i], pixel_coords[i + 1]], fill=color, width=width)
                    except Exception:
                        continue

    def create_blank_tile(self) -> Image.Image:
        return Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))

    def generate_tile(self, x: int, y: int, zoom: int) -> Image.Image:
        line_width_base = max(1, int(self.get_line_width(zoom)))
        bleed_px = max(2, line_width_base * 2)
        canvas_size = 256 + 2 * bleed_px
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

        for idx, row in self.gdf.iterrows():
            geometry = row.geometry
            if not geometry.intersects(tile_box):
                continue
            color, width_px = self.get_feature_stroke(row, zoom)
            for coords in geometry_to_line_coords(geometry):
                if len(coords) >= 2:
                    self.draw_line(draw, coords, color, width_px, x, y, zoom, bleed_px, bleed_px)

        cropped = img.crop((bleed_px, bleed_px, bleed_px + 256, bleed_px + 256))
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

    def create_tilejson(self, name: str = "Universal Line Styled"):
        minx, miny, maxx, maxy = self.bounds
        center = [(minx + maxx) / 2, (miny + maxy) / 2, 10]
        tilejson = {
            "tilejson": "3.0.0",
            "name": name,
            "version": "1.0.0",
            "scheme": "xyz",
            "tiles": [f"./{{z}}/{{x}}/{{y}}.png"],
            "minzoom": 5,
            "maxzoom": 18,
            "bounds": [minx, miny, maxx, maxy],
            "center": center,
        }
        (self.output_dir / "tilejson.json").write_text(json.dumps(tilejson, indent=2))
        log_info("TileJSON: %s/tilejson.json", self.output_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Universal line/polygon styled tile generator (LineString, MultiLineString, Polygon, MultiPolygon)"
    )
    parser.add_argument("geojson", help="Path to GeoJSON file")
    parser.add_argument("output_dir", help="Output directory for tiles")
    parser.add_argument("--legend", "-l", help="Path to legend CSV (style_role, stroke, stroke_width)")
    parser.add_argument("--force", "-f", action="store_true", help="Regenerate all tiles")
    parser.add_argument("--min-zoom", type=int, default=5)
    parser.add_argument("--max-zoom", type=int, default=18)
    args = parser.parse_args()

    if not Path(args.geojson).exists():
        log_error("GeoJSON not found: %s", args.geojson)
        sys.exit(1)

    try:
        gen = UniversalLineStyledTileGenerator(
            args.geojson,
            args.output_dir,
            legend_path=args.legend,
            skip_existing=not args.force,
        )
        gen.generate_tiles(min_zoom=args.min_zoom, max_zoom=args.max_zoom)
        gen.create_tilejson(name=Path(args.geojson).stem)
        log_info("Tiles written to %s", args.output_dir)
    except Exception as e:
        if logger:
            logger.exception("%s", e)
        else:
            print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
