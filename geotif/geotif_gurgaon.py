#!/usr/bin/env python3
"""
Gurgaon Master Plan GeoJSON → High-Resolution RGB GeoTIFF Converter
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

# ============================================================================
# CONFIGURATION
# ============================================================================
INPUT_DIR = "data/delhi_ncr/gurgaon/master_plan"
OUTPUT_FILE = "gurgaon_masterplan_zoom16.tif"
TARGET_RESOLUTION_METERS = 2.4  # ~Zoom 16


# ============================================================================
# COLOR MAP
# ============================================================================
def hex_to_rgb(code: str):
    code = code.strip().lstrip("#")
    return tuple(int(code[i:i + 2], 16) for i in (0, 2, 4))


COLOR_MAP = {
    "100 RESIDENTIAL (GROUP HOUSING/PLOTTED)": hex_to_rgb("FFFF73"),
    "1000 NATURAL CONSERVATION ZONE HUBS)": hex_to_rgb("38A800"),
    "200 COMMERCIAL": hex_to_rgb("BED2FF"),
    "300 INDUSTRIAL": hex_to_rgb("A80084"),
    "400 TRANSPORT AND COMMUNICATION": hex_to_rgb("828282"),
    "500 PUBLIC UTILITIES": hex_to_rgb("A83800"),
    "600 PUBLIC AND SEMI PUBLIC USE": hex_to_rgb("E60000"),
    "700 OPEN SPACES": hex_to_rgb("F57A7A"),  # base fill, hatch overlay later
    "800 AGRICULTURE ZONE": hex_to_rgb("FFFFFF"),  # base fill, dot overlay later
    "800 AGGRICULTURE ZONE": hex_to_rgb("FFFFFF"),
    "900 SPECIAL ZONE": hex_to_rgb("DF73FF"),
    "H6 WORLD TRADE HUB": hex_to_rgb("FFFF00"),
    "HUBS": hex_to_rgb("FFAA00"),
}

PATTERN_CONFIG = {
    "700 OPEN SPACES": {
        "type": "hatch",
        "color": hex_to_rgb("FFFFFF"),
        "spacing": 8,
        "width": 2,
    },
    "800 AGRICULTURE ZONE": {
        "type": "dots",
        "color": hex_to_rgb("4CE600"),
        "spacing": 6,
    },
    "800 AGGRICULTURE ZONE": {
        "type": "dots",
        "color": hex_to_rgb("4CE600"),
        "spacing": 6,
    },
}

OUTLINE_COLOR = (0, 0, 0)


# ============================================================================
# HELPERS
# ============================================================================
def normalize_category(value):
    if not value:
        return None
    value = " ".join(value.replace("_", " ").split())
    return value.upper()


# ============================================================================
# CORE PIPELINE
# ============================================================================
def get_geojson_files(directory):
    files = glob.glob(os.path.join(directory, "*.geojson"))
    if not files:
        raise ValueError(f"No GeoJSON files found in {directory}")
    return sorted(files)


def calculate_bounds(geojson_files):
    print("\n[1/6] Calculating bounds…")
    minx = miny = float("inf")
    maxx = maxy = float("-inf")
    total_features = skipped_total = 0

    for path in geojson_files:
        with open(path) as f:
            data = json.load(f)
        valid = skipped = 0
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
        total_features += valid
        skipped_total += skipped
        print(f"  ✓ {os.path.basename(path)}: {valid} features" + (f" ({skipped} skipped)" if skipped else ""))

    print(f"\n  Bounds: [{minx:.6f}, {miny:.6f}, {maxx:.6f}, {maxy:.6f}]")
    print(f"  Total features: {total_features:,}")
    if skipped_total:
        print(f"  Total skipped: {skipped_total}")
    return minx, miny, maxx, maxy


def calculate_dimensions(bounds, target_resolution):
    print("\n[2/6] Calculating dimensions…")
    minx, miny, maxx, maxy = bounds
    width_deg = maxx - minx
    height_deg = maxy - miny

    center_lat = (miny + maxy) / 2
    km_per_deg_lon = 111.32 * math.cos(math.radians(center_lat))
    km_per_deg_lat = 111.32

    width_m = width_deg * km_per_deg_lon * 1000
    height_m = height_deg * km_per_deg_lat * 1000

    width_px = max(1, int(width_m / target_resolution))
    height_px = max(1, int(height_m / target_resolution))

    print(f"  Extent: {width_m/1000:.2f} km × {height_m/1000:.2f} km")
    print(f"  Output size: {width_px:,} × {height_px:,} pixels")
    print(f"  Uncompressed RGBA size: {(width_px*height_px*4)/(1024**2):.0f} MB")

    return width_px, height_px


def load_features_by_layer(geojson_files):
    print("\n[3/6] Loading features…")
    layers = {}
    unmapped = set()

    for path in geojson_files:
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
                raw_category = (
                    props.get("classtext")
                    or props.get("classText")
                    or props.get("class")
                    or props.get("NAME")
                    or props.get("name")
                    or layer_name
                )
                category_norm = normalize_category(str(raw_category)) or layer_norm or layer_name.upper()
                color = COLOR_MAP.get(category_norm)
                if color is None and layer_norm:
                    color = COLOR_MAP.get(layer_norm)
                if color is None:
                    color = (128, 128, 128)
                    unmapped.add(category_norm)
                features.append({
                    "geometry": mapping(geom),
                    "color": color,
                    "category": category_norm
                })
            except Exception:
                continue

        if features:
            layers[layer_name] = {
                "features": features,
                "priority": 50,
                "count": len(features)
            }
            sample = "#{:02x}{:02x}{:02x}".format(*features[0]["color"])
            print(f"  ✓ {layer_name}: {len(features)} features (color {sample})")

    if unmapped:
        print("\n  ⚠️  Unmapped categories (rendered gray):")
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
    outline_shapes = []

    sorted_layers = sorted(layers.items(), key=lambda item: item[1]["priority"])
    total = sum(layer["count"] for layer in layers.values())
    processed = 0
    pattern_shapes = defaultdict(list)

    for idx, (layer_name, layer_data) in enumerate(sorted_layers, 1):
        features = layer_data["features"]
        if not features:
            continue
        print(f"  [{idx}/{len(sorted_layers)}] {layer_name}: {len(features)} features…", end="", flush=True)
        mask = rasterize(
            [(feat["geometry"], 1) for feat in features],
            out_shape=(height, width),
            transform=transform,
            fill=0,
            all_touched=True,
            dtype=np.uint8
        )
        pixels = mask == 1
        if pixels.any():
            r_val, g_val, b_val = features[0]["color"]
            r[pixels] = r_val
            g[pixels] = g_val
            b[pixels] = b_val
            a[pixels] = 255

        for feat in features:
            try:
                geom = shape(feat["geometry"])
                boundary = geom.boundary if hasattr(geom, "boundary") else geom
                if not boundary.is_empty:
                    outline_shapes.append((mapping(boundary), 1))
            except Exception:
                continue

        if features and features[0]["category"] in PATTERN_CONFIG:
            for feat in features:
                try:
                    geom = shape(feat["geometry"])
                    if geom.is_empty:
                        continue
                    pattern_shapes[features[0]["category"]].append((mapping(geom), 1))
                except Exception:
                    continue

        processed += len(features)
        print(f" done ({processed / total * 100:.1f}% complete)")

    # Apply patterns before drawing outlines so outlines stay on top
    rows = np.arange(height).reshape(-1, 1)
    cols = np.arange(width).reshape(1, -1)
    for category, shapes in pattern_shapes.items():
        config = PATTERN_CONFIG.get(category)
        if not config:
            continue
        mask = rasterize(
            shapes,
            out_shape=(height, width),
            transform=transform,
            fill=0,
            all_touched=True,
            dtype=np.uint8
        ) == 1
        if not mask.any():
            continue
        spacing = config.get("spacing", 8)
        pattern = np.zeros_like(mask, dtype=bool)
        if config["type"] == "hatch":
            width_px = config.get("width", 2)
            pattern = ((rows + cols) % spacing) < width_px
        elif config["type"] == "dots":
            pattern = ((rows % spacing) == 0) & ((cols % spacing) == 0)
        pattern &= mask
        color = config["color"]
        r[pattern] = color[0]
        g[pattern] = color[1]
        b[pattern] = color[2]
        a[pattern] = 255

    if outline_shapes:
        outline_mask = rasterize(
            outline_shapes,
            out_shape=(height, width),
            transform=transform,
            fill=0,
            all_touched=True,
            dtype=np.uint8
        )
        pixels = outline_mask == 1
        r[pixels] = OUTLINE_COLOR[0]
        g[pixels] = OUTLINE_COLOR[1]
        b[pixels] = OUTLINE_COLOR[2]
        a[pixels] = 255

    return np.stack([r, g, b, a]), transform


def write_rgb_geotiff(rgba_data, transform, output_file):
    print("\n[5/6] Writing compressed GeoTIFF…")
    bands, height, width = rgba_data.shape
    with rasterio.open(
        output_file,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=4,
        dtype=np.uint8,
        crs="EPSG:4326",
        transform=transform,
        compress="lzw",
        tiled=True,
        blockxsize=512,
        blockysize=512,
        BIGTIFF="YES"
    ) as dst:
        names = ["Red", "Green", "Blue", "Alpha"]
        for idx in range(4):
            print(f"  Writing {names[idx]}…", end="", flush=True)
            dst.write(rgba_data[idx], idx + 1)
            print(" done.")
        dst.update_tags(
            description="Gurgaon Master Plan Land Use Map (RGBA)",
            created_by="geotif_gurgaon.py",
            alpha_band="4",
            compression="lzw"
        )
    size_mb = os.path.getsize(output_file) / (1024 * 1024)
    print(f"  ✓ File written: {output_file} ({size_mb:.2f} MB)")


def verify_output(output_file):
    print("\n[6/6] Verifying output…")
    with rasterio.open(output_file) as src:
        print(f"  Dimensions: {src.width} × {src.height}")
        print(f"  Bands: {src.count}")
        print(f"  CRS: {src.crs}")
        print(f"  Compression: {src.compression}")
        if src.count >= 4:
            alpha = src.read(4)
            print(f"  Opaque pixels: {np.sum(alpha > 0):,}")
    print("  ✓ Verification complete")


def main():
    print("=" * 70)
    print("Gurgaon GeoJSON → High-Resolution RGB GeoTIFF")
    print("=" * 70)
    print(f"Input dir : {INPUT_DIR}")
    print(f"Output    : {OUTPUT_FILE}")
    print(f"Resolution: {TARGET_RESOLUTION_METERS} m/pixel (~Zoom 16)")

    if not os.path.exists(INPUT_DIR):
        print(f"\n❌ ERROR: Directory not found: {INPUT_DIR}")
        return 1

    try:
        files = get_geojson_files(INPUT_DIR)
        print(f"\nFound {len(files)} GeoJSON files")

        bounds = calculate_bounds(files)
        width, height = calculate_dimensions(bounds, TARGET_RESOLUTION_METERS)
        layers = load_features_by_layer(files)
        if not layers:
            print("\n❌ ERROR: No valid features to render")
            return 1

        rgba, transform = rasterize_rgb(layers, bounds, width, height)
        write_rgb_geotiff(rgba, transform, OUTPUT_FILE)
        verify_output(OUTPUT_FILE)

        print("\n" + "=" * 70)
        print("✓ SUCCESS: Gurgaon master plan GeoTIFF created!")
        print("=" * 70)
        return 0

    except Exception as exc:
        print(f"\n❌ ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

