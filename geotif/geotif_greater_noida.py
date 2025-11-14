#!/usr/bin/env python3
"""
Greater Noida Master Plan GeoJSON → High-Resolution RGB GeoTIFF Converter
"""

import os
import json
import math
import glob
from collections import defaultdict

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.features import rasterize
from shapely.geometry import shape, mapping

INPUT_DIR = "data/delhi_ncr/greater_noida/master_plan"
OUTPUT_FILE = "greater_noida_masterplan_zoom16.tif"
TARGET_RESOLUTION_METERS = 2.4


def hex_to_rgb(code: str):
    code = code.strip().lstrip("#")
    return tuple(int(code[i:i + 2], 16) for i in (0, 2, 4))


COLOR_MAP = {
    # Greater Noida categories (per spec)
    "FP": hex_to_rgb("FDE2CA"),
    "6% KISAN ABADI": hex_to_rgb("CDAA66"),
    "BUILTUP HOUSING": hex_to_rgb("FFFF73"),
    "BUILDER": hex_to_rgb("FFEBAF"),
    "BUILTUP FLATS": hex_to_rgb("FFFF73"),
    "COMMERCIAL": hex_to_rgb("FF0000"),
    "GREEN": hex_to_rgb("AAFF00"),
    "GREEN BELT": hex_to_rgb("9C9C9C"),
    "GREEN_BELT": hex_to_rgb("9C9C9C"),
    "GROUP HOUSING": hex_to_rgb("FFAA00"),
    "MIXED USE": hex_to_rgb("FFAA00"),
    "MIXED_USE": hex_to_rgb("FFAA00"),
    "IT": hex_to_rgb("73DFFF"),
    "INDUSTRY": hex_to_rgb("7A8EF5"),
    "INSTITUTIONAL": hex_to_rgb("004DA8"),
    "INSTITUTION": hex_to_rgb("004DA8"),
    "NOT KNOWN": hex_to_rgb("FFFFFF"),
    "PARK": hex_to_rgb("4CE600"),
    "RECREATIONAL GREEN": hex_to_rgb("A3FF73"),
    "RESIDENTIAL": hex_to_rgb("E6E600"),
    "SPORTS": hex_to_rgb("9C9C9C"),
    "TRANSPORT": hex_to_rgb("A87000"),
    "UTILITY": hex_to_rgb("B2B2B2"),
    "VILLAGE": hex_to_rgb("E64C00"),
    "VILLAGE ABADI": hex_to_rgb("D7D79E"),
    "WATER BODY": hex_to_rgb("0070FF"),
    "WATER BODIES": hex_to_rgb("0070FF"),
    # Special categories (may be in other files)
    "AIRPORT": hex_to_rgb("FF0000"),  # Solid fill, airplane pattern overlay
    "RAILWAY LINES": hex_to_rgb("000000"),
    "MASTER PLAN": hex_to_rgb("6E6E6E"),  # Outline only
    "SECTOR LAYOUT": hex_to_rgb("FFD37F"),  # Vacant
    "SECTOR LAYOUT ALLOTED": hex_to_rgb("000000"),  # Outline only
    "SECTOR LAYOUT RESERVED": hex_to_rgb("FF7F7F"),  # Solid fill
    "SECTOR LAYOUT VACANT": hex_to_rgb("FFD37F"),  # Solid fill
    "SECTOR BOUNDARY": hex_to_rgb("E69800"),  # Outline only
    "AOI": hex_to_rgb("FF0000"),  # Outline only
    # Yamuna Part 1 PLU Plan 2021 categories
    "AGRICULTURE": hex_to_rgb("ABE066"),
    "CANAL": hex_to_rgb("0070FF"),
    "CANAL GREENBELT": hex_to_rgb("55FF00"),
    "CANAL_GREENBELT": hex_to_rgb("55FF00"),
    "DRAIN": hex_to_rgb("B5CBFD"),
    "DRAIN GREENBELT": hex_to_rgb("55FF00"),
    "DRAIN_GREENBELT": hex_to_rgb("55FF00"),
    "FACILITY": hex_to_rgb("004DA8"),
    "FOREST": hex_to_rgb("55FF00"),
    "GREEN_BELT": hex_to_rgb("55FF00"),
    "NALA": hex_to_rgb("002673"),
    "RIVERFRONT_DEVELOPMENT": hex_to_rgb("00FFC5"),
    "RIVERFRONT DEVELOPMENT": hex_to_rgb("00FFC5"),  # Space variant
    "ROADS": hex_to_rgb("828282"),
    "SDZ": hex_to_rgb("E8BEFF"),
    "SECTOR19_22": hex_to_rgb("FFFF00"),
    "SECTOR 19_22": hex_to_rgb("FFFF00"),  # Space variant
    "TRAFFIC ISLANDS": hex_to_rgb("55FF00"),
    "YAMUNA": hex_to_rgb("005CE6"),
    "POND": hex_to_rgb("0070FF"),  # From user spec
}

PATTERN_CONFIG = {
    "SPORTS": {
        "type": "hatch",
        "color": hex_to_rgb("000000"),
        "spacing": 8,
        "width": 1,
    },
    "AIRPORT": {
        "type": "airplane",
        "color": hex_to_rgb("FFFFFF"),
        "spacing": 18,
    },
}

OUTLINE_ONLY = {
    "MASTER PLAN": hex_to_rgb("6E6E6E"),  # No fill, only outline
    "SECTOR LAYOUT ALLOTED": hex_to_rgb("000000"),  # No fill, only outline
    "SECTOR BOUNDARY": hex_to_rgb("E69800"),  # No fill, only outline
    "AOI": hex_to_rgb("FF0000"),  # No fill, only outline
    # Note: SECTOR LAYOUT RESERVED and VACANT have solid fills, not outline-only
}

OUTLINE_COLOR = (0, 0, 0)


def normalize_category(value):
    if not value:
        return None
    value = value.replace("_", " ")
    value = " ".join(value.split())
    return value.upper()


def get_geojson_files(directory):
    files = glob.glob(os.path.join(directory, "*.geojson"))
    if not files:
        raise ValueError(f"No GeoJSON files found in {directory}")
    return sorted(files)


def calculate_bounds(files):
    print("\n[1/6] Calculating bounds…")
    minx = miny = float("inf")
    maxx = maxy = float("-inf")
    total = skipped = 0
    for path in files:
        with open(path) as f:
            data = json.load(f)
        valid = 0
        for feat in data.get("features", []):
            try:
                geom = shape(feat["geometry"])
                if geom.is_empty:
                    skipped += 1
                    continue
                b = geom.bounds
                minx = min(minx, b[0])
                miny = min(miny, b[1])
                maxx = max(maxx, b[2])
                maxy = max(maxy, b[3])
                valid += 1
            except Exception:
                skipped += 1
        total += valid
        print(f"  ✓ {os.path.basename(path)}: {valid} features")
    print(f"\n  Bounds: [{minx:.6f}, {miny:.6f}, {maxx:.6f}, {maxy:.6f}]")
    print(f"  Total features: {total:,}")
    if skipped:
        print(f"  Skipped: {skipped}")
    return minx, miny, maxx, maxy


def calculate_dimensions(bounds, resolution):
    print("\n[2/6] Calculating dimensions…")
    minx, miny, maxx, maxy = bounds
    width_deg = maxx - minx
    height_deg = maxy - miny
    center_lat = (miny + maxy) / 2
    km_per_deg_lon = 111.32 * math.cos(math.radians(center_lat))
    km_per_deg_lat = 111.32
    width_m = width_deg * km_per_deg_lon * 1000
    height_m = height_deg * km_per_deg_lat * 1000
    width_px = max(1, int(width_m / resolution))
    height_px = max(1, int(height_m / resolution))
    print(f"  Output size: {width_px:,} × {height_px:,}")
    print(f"  Uncompressed RGBA: {(width_px*height_px*4)/(1024**2):.0f} MB")
    return width_px, height_px


def load_layers(files):
    print("\n[3/6] Loading features by layer…")
    layers = {}
    unmapped = set()
    for path in files:
        layer_name = os.path.basename(path).replace(".geojson", "")
        layer_norm = normalize_category(layer_name)
        with open(path) as f:
            data = json.load(f)
        features = []
        for feat in data.get("features", []):
            try:
                geom = shape(feat["geometry"])
                if geom.is_empty:
                    continue
                props = feat.get("properties") or {}
                # Prioritize ppt_full (most accurate category), then layer name
                raw_cat = (
                    props.get("ppt_full")
                    or props.get("classtext")
                    or props.get("class")
                    or props.get("NAME")
                    or layer_name
                )
                category = normalize_category(str(raw_cat)) or layer_norm
                color = COLOR_MAP.get(category)
                if color is None and layer_norm:
                    color = COLOR_MAP.get(layer_norm)
                if color is None:
                    color = (128, 128, 128)
                    unmapped.add(category or layer_norm or layer_name)
                features.append({
                    "geometry": mapping(geom),
                    "color": color,
                    "category": category or layer_norm or layer_name,
                })
            except Exception:
                continue
        if features:
            layers[layer_name] = {
                "features": features,
                "priority": 50,
                "count": len(features),
            }
            sample = "#{:02x}{:02x}{:02x}".format(*features[0]["color"])
            print(f"  ✓ {layer_name}: {len(features)} features ({sample})")
    if unmapped:
        print("\n  ⚠️  Unmapped categories (gray fallback):")
        for cat in sorted(unmapped):
            print(f"    - {cat}")
    return layers


def rasterize_rgb(layers, bounds, width, height):
    print("\n[4/6] Rasterizing RGBA image…")
    minx, miny, maxx, maxy = bounds
    transform = from_bounds(minx, miny, maxx, maxy, width, height)

    r = np.zeros((height, width), dtype=np.uint8)
    g = np.zeros((height, width), dtype=np.uint8)
    b = np.zeros((height, width), dtype=np.uint8)
    a = np.zeros((height, width), dtype=np.uint8)

    outline_shapes_default = []
    outline_shapes_colored = defaultdict(list)
    pattern_shapes = defaultdict(list)

    sorted_layers = sorted(layers.items(), key=lambda item: item[1]["priority"])
    total = sum(layer["count"] for layer in layers.values())
    processed = 0

    for idx, (name, layer) in enumerate(sorted_layers, 1):
        features = layer["features"]
        if not features:
            continue
        print(f"  [{idx}/{len(sorted_layers)}] {name}: {len(features)} features…", end="", flush=True)

        category = features[0]["category"]
        is_outline_only = category in OUTLINE_ONLY

        mask = None
        if not is_outline_only:
            mask = rasterize(
                [(feat["geometry"], 1) for feat in features],
                out_shape=(height, width),
                transform=transform,
                fill=0,
                all_touched=True,
                dtype=np.uint8,
            )
            pixels = mask == 1
            if pixels.any():
                rv, gv, bv = features[0]["color"]
                r[pixels] = rv
                g[pixels] = gv
                b[pixels] = bv
                a[pixels] = 255

        if category in PATTERN_CONFIG and not is_outline_only:
            for feat in features:
                try:
                    geom = shape(feat["geometry"])
                    if not geom.is_empty:
                        pattern_shapes[category].append((mapping(geom), 1))
                except Exception:
                    continue

        for feat in features:
            try:
                geom = shape(feat["geometry"])
                boundary = geom.boundary if hasattr(geom, "boundary") else geom
                if not boundary.is_empty:
                    color = OUTLINE_ONLY.get(category)
                    if color:
                        outline_shapes_colored[color].append((mapping(boundary), 1))
                    else:
                        outline_shapes_default.append((mapping(boundary), 1))
            except Exception:
                continue

        processed += len(features)
        print(f" done ({processed / total * 100:.1f}% complete)")

    rows = np.arange(height).reshape(-1, 1)
    cols = np.arange(width).reshape(1, -1)
    for category, shapes in pattern_shapes.items():
        config = PATTERN_CONFIG[category]
        mask = rasterize(
            shapes,
            out_shape=(height, width),
            transform=transform,
            fill=0,
            all_touched=True,
            dtype=np.uint8,
        ) == 1
        if not mask.any():
            continue
        spacing = config.get("spacing", 8)
        pattern = np.zeros_like(mask, dtype=bool)
        if config["type"] == "hatch":
            width_px = config.get("width", 1)
            pattern = ((rows + cols) % spacing) < width_px
        elif config["type"] == "dots":
            pattern = ((rows % spacing) == 0) & ((cols % spacing) == 0)
        elif config["type"] == "airplane":
            center = spacing // 2
            pattern = (
                ((rows % spacing) == center)
                | ((cols % spacing) == center)
                | (((rows - cols) % spacing) == 0)
                | (((rows + cols) % spacing) == 0)
            )
        pattern &= mask
        color = config["color"]
        r[pattern] = color[0]
        g[pattern] = color[1]
        b[pattern] = color[2]
        a[pattern] = 255

    if outline_shapes_default:
        outline_mask = rasterize(
            outline_shapes_default,
            out_shape=(height, width),
            transform=transform,
            fill=0,
            all_touched=True,
            dtype=np.uint8,
        )
        pixels = outline_mask == 1
        r[pixels] = OUTLINE_COLOR[0]
        g[pixels] = OUTLINE_COLOR[1]
        b[pixels] = OUTLINE_COLOR[2]
        a[pixels] = 255

    for color, shapes in outline_shapes_colored.items():
        outline_mask = rasterize(
            shapes,
            out_shape=(height, width),
            transform=transform,
            fill=0,
            all_touched=True,
            dtype=np.uint8,
        )
        pixels = outline_mask == 1
        r[pixels] = color[0]
        g[pixels] = color[1]
        b[pixels] = color[2]
        a[pixels] = 255

    return np.stack([r, g, b, a]), transform


def write_geotiff(rgba, transform):
    print("\n[5/6] Writing GeoTIFF…")
    with rasterio.open(
        OUTPUT_FILE,
        "w",
        driver="GTiff",
        height=rgba.shape[1],
        width=rgba.shape[2],
        count=4,
        dtype=np.uint8,
        crs="EPSG:4326",
        transform=transform,
        compress="lzw",
        tiled=True,
        blockxsize=512,
        blockysize=512,
        BIGTIFF="YES",
    ) as dst:
        names = ["Red", "Green", "Blue", "Alpha"]
        for idx in range(4):
            print(f"  Writing {names[idx]}…", end="", flush=True)
            dst.write(rgba[idx], idx + 1)
            print(" done.")
        dst.update_tags(
            description="Greater Noida Master Plan Land Use Map (RGBA)",
            created_by="geotif_greater_noida.py",
            alpha_band="4",
            compression="lzw",
        )
    size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"  ✓ File written: {OUTPUT_FILE} ({size_mb:.2f} MB)")


def verify(output_file):
    print("\n[6/6] Verifying output…")
    with rasterio.open(output_file) as src:
        print(f"  Dimensions: {src.width} × {src.height}")
        print(f"  Bands: {src.count}")
        print(f"  CRS: {src.crs}")
        if src.count >= 4:
            alpha = src.read(4)
            print(f"  Opaque pixels: {np.sum(alpha > 0):,}")
    print("  ✓ Verification complete")


def main():
    print("=" * 70)
    print("Greater Noida GeoJSON → High-Resolution RGB GeoTIFF")
    print("=" * 70)
    print(f"Input directory : {INPUT_DIR}")
    print(f"Output file     : {OUTPUT_FILE}")
    print(f"Resolution      : {TARGET_RESOLUTION_METERS} m/pixel (~Zoom 16)")

    if not os.path.exists(INPUT_DIR):
        print(f"\n❌ ERROR: Directory not found: {INPUT_DIR}")
        return 1
    try:
        files = get_geojson_files(INPUT_DIR)
        print(f"\nFound {len(files)} GeoJSON files")
        bounds = calculate_bounds(files)
        width, height = calculate_dimensions(bounds, TARGET_RESOLUTION_METERS)
        layers = load_layers(files)
        if not layers:
            print("\n❌ ERROR: No features loaded")
            return 1
        rgba, transform = rasterize_rgb(layers, bounds, width, height)
        write_geotiff(rgba, transform)
        verify(OUTPUT_FILE)
        print("\n" + "=" * 70)
        print("✓ SUCCESS: Greater Noida master plan GeoTIFF created!")
        print("=" * 70)
        return 0
    except Exception as exc:
        print(f"\n❌ ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

