#!/usr/bin/env python3
"""
Hyderabad RRR Roads - Styled Tile Generator (2-layer from GeoJSON)
==================================================================

Generates PNG tiles from RRR_2_Layer_swapped.geojson.
All styling (stroke, stroke-width, layer order) is read from the GeoJSON;
no hardcoded colors or legend file.

Expected output: dark gray road body with white outer edges (outer → inner draw order).
No middle/center line; 2 layers only.

Resolution: line width at each zoom is controlled by ZOOM_RESOLUTION (base px per zoom).
GeoJSON stroke-width is scaled by (base / REFERENCE_STROKE_WIDTH) so you can tune resolution per zoom.

Usage:
  python telangana_hyderabad_rrr_styled.py              # Skip existing tiles
  python telangana_hyderabad_rrr_styled.py --force      # Regenerate all tiles
"""

import json
import os
import sys
import math
import time
import geopandas as gpd
from pathlib import Path
from PIL import Image, ImageDraw
from typing import Tuple, List
import mercantile
from shapely.geometry import LineString, MultiLineString, Polygon, box
from shapely.ops import unary_union
from shapely.validation import make_valid
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Draw order for _style_role: outer (white edges) first, then inner (dark body). 2 layers only; no middle line.
STYLE_ORDER = {'outer': 0, 'inner': 1}

# Resolution per zoom level: base line width in pixels for a reference stroke-width of 3.
# Tune these so roads look consistent and clear at every zoom. Higher zoom = thicker base for visibility.
ZOOM_RESOLUTION = {
    5: 1.0,    # Far: thin so roads don’t blob
    6: 1.3,
    7: 1.6,
    8: 2.0,
    9: 2.5,
    10: 3.0,
    11: 3.5,
    12: 4.5,
    13: 5.5,
    14: 6.5,
    15: 8.0,
    16: 10.0,
    17: 12.0,
    18: 15.0,
}
REFERENCE_STROKE_WIDTH = 3.0  # GeoJSON stroke-width that maps 1:1 to ZOOM_RESOLUTION[z]


class HyderabadRRRStyledTileGenerator:
    """
    Tile generator for Hyderabad RRR using per-feature styling from GeoJSON.
    """

    def __init__(self, geojson_path: str, output_dir: str = "hyderabad_rrr_styled_tiles", skip_existing: bool = True):
        self.geojson_path = Path(geojson_path)
        self.output_dir = Path(output_dir)
        self.tile_size = 256
        self.skip_existing = skip_existing
        self.buffer_factor = 0.15
        self.bounds = None
        self.gdf = None
        self.spatial_index = None
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.load_and_process_data()
        logger.info("Hyderabad RRR Styled Tile Generator initialized")
        logger.info("GeoJSON: %s (styling from properties)", geojson_path)
        logger.info("Output: %s", output_dir)

    def load_and_process_data(self):
        """Load styled GeoJSON and keep properties (stroke, stroke-width, _style_role)."""
        if not self.geojson_path.exists():
            raise FileNotFoundError(f"GeoJSON not found: {self.geojson_path}")
        logger.info("Loading RRR styled data...")
        self.gdf = gpd.read_file(self.geojson_path)
        if self.gdf.empty:
            raise ValueError("No features in GeoJSON")
        if self.gdf.crs is None:
            self.gdf.set_crs('EPSG:4326', inplace=True)
        elif self.gdf.crs.to_string() != 'EPSG:4326':
            self.gdf = self.gdf.to_crs('EPSG:4326')

        # Fix invalid geometries
        def fix_geom(geom):
            if not geom.is_valid:
                try:
                    geom = make_valid(geom)
                except Exception:
                    try:
                        geom = geom.buffer(0)
                    except Exception:
                        pass
            return geom

        self.gdf['geometry'] = self.gdf.geometry.apply(fix_geom)
        self.gdf = self.gdf[self.gdf.geometry.is_valid].copy()

        # Sort by _style_role so draw order is outer → inner (2 layers; no middle line)
        if '_style_role' in self.gdf.columns:
            self.gdf['_draw_order'] = self.gdf['_style_role'].map(
                lambda x: STYLE_ORDER.get(str(x).strip().lower() if isinstance(x, str) else x, 0)
            )
            self.gdf = self.gdf.sort_values('_draw_order').reset_index(drop=True)
        else:
            self.gdf['_draw_order'] = 0

        self.bounds = self.gdf.total_bounds
        self.spatial_index = self.gdf.sindex
        logger.info("Loaded %d features (styled)", len(self.gdf))

    def get_rrr_line_width(self, zoom: int) -> float:
        """Base line width in pixels for this zoom (resolution for this zoom level)."""
        return ZOOM_RESOLUTION.get(zoom, 3.0)

    def get_features_for_tile(self, tile_bounds: mercantile.LngLatBbox) -> gpd.GeoDataFrame:
        """Return features intersecting the tile (with buffer)."""
        tile_width = tile_bounds.east - tile_bounds.west
        buffer = tile_width * self.buffer_factor
        search_bounds = (
            tile_bounds.west - buffer,
            tile_bounds.south - buffer,
            tile_bounds.east + buffer,
            tile_bounds.north + buffer,
        )
        try:
            possible = list(self.spatial_index.intersection(search_bounds))
            if not possible:
                return gpd.GeoDataFrame()
            features = self.gdf.iloc[possible].copy()
            tile_poly = box(
                tile_bounds.west, tile_bounds.south,
                tile_bounds.east, tile_bounds.north
            ).buffer(buffer * 0.1)
            return features[features.geometry.intersects(tile_poly)]
        except Exception as e:
            logger.debug("get_features_for_tile: %s", e)
            return gpd.GeoDataFrame()

    def wgs84_to_tile_pixel(self, lon: float, lat: float, tile_x: int, tile_y: int, zoom: int) -> Tuple[int, int]:
        """Convert WGS84 coordinates to pixel coordinates within a tile (same as telangana_hyderabad_rrr.py)."""
        lat = max(-85.051129, min(85.051129, lat))
        tile_lon = (lon + 180) / 360 * (2 ** zoom)
        tile_lat = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * (2 ** zoom)
        pixel_x = int((tile_lon - tile_x) * 256)
        pixel_y = int((tile_lat - tile_y) * 256)
        return pixel_x, pixel_y

    def draw_line(self, draw: ImageDraw.Draw, coordinates: List[Tuple[float, float]],
                  color: str, width: int, tile_x: int, tile_y: int, zoom: int,
                  offset_x: int = 0, offset_y: int = 0):
        """Draw a line with smooth rounded joins at corners (joint='curve' or buffered polygon fallback)."""
        if len(coordinates) < 2:
            return
        pixel_coords = []
        for lon, lat in coordinates:
            pixel_x, pixel_y = self.wgs84_to_tile_pixel(lon, lat, tile_x, tile_y, zoom)
            pixel_coords.append((pixel_x + offset_x, pixel_y + offset_y))
        if len(pixel_coords) < 2:
            return

        # Use rounded joins at bends so edges don't break or look jagged
        try:
            draw.line(pixel_coords, fill=color, width=width, joint="curve")
            return
        except TypeError:
            pass  # Pillow < 8.2 without joint parameter

        # Fallback: draw line as buffered polygon for smooth rounded corners and caps
        try:
            ls = LineString(pixel_coords)
            if ls.is_empty or not ls.is_valid:
                draw.line(pixel_coords, fill=color, width=width)
                return
            half = max(0.5, width / 2.0)
            buffered = ls.buffer(half, cap_style=2, join_style=2)  # round cap, round join
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
        """Create a fully transparent PNG tile (same as telangana_hyderabad_rrr.py)."""
        return Image.new('RGBA', (self.tile_size, self.tile_size), (0, 0, 0, 0))

    def generate_tile(self, x: int, y: int, zoom: int) -> Image.Image:
        """Generate a single tile (same rendering as telangana_hyderabad_rrr.py; color/width from GeoJSON)."""
        line_width = max(1, int(self.get_rrr_line_width(zoom)))
        bleed_px = max(2, line_width * 2)
        canvas_size = 256 + 2 * bleed_px
        img = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        tile_bounds = mercantile.bounds(x, y, zoom)
        tile_width_deg = tile_bounds.east - tile_bounds.west
        tile_height_deg = tile_bounds.north - tile_bounds.south
        buffer_px = bleed_px + line_width
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
            # Colour from GeoJSON properties only (stroke)
            color = None
            if 'stroke' in row.index:
                color = row['stroke']
            if not color and 'Stroke' in row.index:
                color = row['Stroke']
            if not color or (isinstance(color, (int, float)) and math.isnan(color)):
                color = '#999999'  # fallback only when stroke missing in GeoJSON
            color = str(color).strip()
            if not color or color.lower() == 'nan':
                color = '#999999'
            # Width from GeoJSON properties only (stroke-width)
            stroke_width = None
            if 'stroke-width' in row.index:
                stroke_width = row['stroke-width']
            if stroke_width is None and 'stroke_width' in row.index:
                stroke_width = row['stroke_width']
            base_width = self.get_rrr_line_width(zoom)  # resolution for this zoom
            if stroke_width is not None and str(stroke_width).strip().lower() not in ('', 'nan', 'none'):
                try:
                    line_width_feature = max(1, int(base_width * float(stroke_width) / REFERENCE_STROKE_WIDTH))
                except (TypeError, ValueError):
                    line_width_feature = max(1, int(base_width))
            else:
                line_width_feature = max(1, int(base_width))

            if geometry.geom_type == 'MultiLineString':
                for line in geometry.geoms:
                    coords = list(line.coords)
                    if len(coords) >= 2:
                        self.draw_line(draw, coords, color, line_width_feature, x, y, zoom, bleed_px, bleed_px)
            elif geometry.geom_type == 'LineString':
                coords = list(geometry.coords)
                if len(coords) >= 2:
                    self.draw_line(draw, coords, color, line_width_feature, x, y, zoom, bleed_px, bleed_px)

        cropped = img.crop((bleed_px, bleed_px, bleed_px + 256, bleed_px + 256))
        return cropped

    def generate_tiles(self, min_zoom: int = 5, max_zoom: int = 18):
        logger.info("Generating styled RRR tiles (zoom %d–%d)", min_zoom, max_zoom)
        total = 0
        start = time.time()
        minx, miny, maxx, maxy = self.bounds
        tile_size_deg = 360.0 / (2 ** max_zoom)
        buffer_deg = tile_size_deg * 3
        expanded = [minx - buffer_deg, miny - buffer_deg, maxx + buffer_deg, maxy + buffer_deg]

        for zoom in range(min_zoom, max_zoom + 1):
            resolution_px = self.get_rrr_line_width(zoom)
            logger.info("Zoom %d: resolution (base line width) = %.1f px", zoom, resolution_px)
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
            logger.info("Zoom %d: %d tiles", zoom, len(tiles))
        elapsed = time.time() - start
        logger.info("Done: %d tiles in %.1fs", total, elapsed)

    def create_viewer_html(self):
        minx, miny, maxx, maxy = self.bounds
        center_lat = (miny + maxy) / 2
        center_lon = (minx + maxx) / 2
        MAPBOX_TOKEN = 'pk.eyJ1IjoiYXYxYWNyZSIsImEiOiJjbTJtZmdxN3owa2FzMmpyMjJ4OHV5MHhzIn0.FXpMd91JSER-r7LVpSZN-A'
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Hyderabad RRR - Styled (2-layer)</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ height: 100vh; width: 100%; }}
        .info {{
            position: fixed; top: 10px; right: 10px;
            background: white; padding: 15px; border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3); z-index: 1000;
        }}
        .zoom-info {{ position: fixed; bottom: 10px; left: 10px; background: rgba(0,0,0,0.8); color: white; padding: 8px 12px; border-radius: 4px; z-index: 1000; }}
        .coordinates {{ position: fixed; bottom: 10px; right: 10px; background: rgba(0,0,0,0.8); color: white; padding: 8px 12px; border-radius: 4px; z-index: 1000; font-size: 12px; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info">
        <h3>Hyderabad RRR (Styled)</h3>
        <p>Styling from GeoJSON: outer (white), inner (gray). 2 layers; no middle line.</p>
        <p>Zoom: 5–18</p>
    </div>
    <div class="zoom-info" id="zoom">Zoom: 10</div>
    <div class="coordinates" id="coords">Lat: 0, Lon: 0</div>
    <script>
        const MAPBOX_TOKEN = '{MAPBOX_TOKEN}';
        const map = L.map('map').setView([{center_lat}, {center_lon}], 10);
        L.tileLayer('https://api.mapbox.com/v4/mapbox.satellite/{{z}}/{{x}}/{{y}}.png?access_token=' + MAPBOX_TOKEN, {{
            attribution: '© Mapbox', maxZoom: 22
        }}).addTo(map);
        L.tileLayer('http://localhost:9000/{{z}}/{{x}}/{{y}}.png', {{
            minZoom: 5, maxZoom: 18, opacity: 1.0, attribution: 'RRR Styled'
        }}).addTo(map);
        function updateZoom() {{ document.getElementById('zoom').textContent = 'Zoom: ' + map.getZoom().toFixed(2); }}
        function updateCoords(e) {{
            const lat = e.latlng ? e.latlng.lat : map.getCenter().lat;
            const lon = e.latlng ? e.latlng.lng : map.getCenter().lng;
            document.getElementById('coords').textContent = 'Lat: ' + lat.toFixed(4) + ', Lon: ' + lon.toFixed(4);
        }}
        map.on('zoom', updateZoom);
        map.on('mousemove', updateCoords);
        map.on('move', updateCoords);
    </script>
</body>
</html>"""
        viewer_path = self.output_dir / "viewer.html"
        viewer_path.write_text(html, encoding='utf-8')
        logger.info("Viewer: %s", viewer_path)

    def create_tilejson(self):
        minx, miny, maxx, maxy = self.bounds
        center = [(minx + maxx) / 2, (miny + maxy) / 2, 10]
        tilejson = {
            "tilejson": "3.0.0",
            "name": "Hyderabad RRR (Styled)",
            "description": "RRR 2-layer styling from GeoJSON (no middle line)",
            "version": "2.0.0",
            "scheme": "xyz",
            "tiles": ["http://localhost:9000/{z}/{x}/{y}.png"],
            "minzoom": 5,
            "maxzoom": 18,
            "bounds": [minx, miny, maxx, maxy],
            "center": center,
            "attribution": "RRR Styled",
        }
        (self.output_dir / "tilejson.json").write_text(json.dumps(tilejson, indent=2))
        logger.info("TileJSON: %s/tilejson.json", self.output_dir)


def main():
    skip_existing = True
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help":
            print(__doc__)
            return
        if sys.argv[1] == "--force":
            skip_existing = False
    geojson_path = "data/Telangana/Hyderabad/rrr/RRR_2_Layer_swapped.geojson"
    output_dir = "hyderabad_rrr_styled_tiles_new"
    if not os.path.exists(geojson_path):
        logger.error("GeoJSON not found: %s", geojson_path)
        sys.exit(1)
    try:
        gen = HyderabadRRRStyledTileGenerator(geojson_path, output_dir, skip_existing)
        gen.generate_tiles(min_zoom=5, max_zoom=18)
        gen.create_viewer_html()
        gen.create_tilejson()
        logger.info("Run: cd %s && python -m http.server 9000  then open viewer.html", output_dir)
    except Exception as e:
        logger.exception("%s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
