#!/usr/bin/env python3
"""
Yamuna Expressway Master Plan GeoJSON → High-Resolution RGB GeoTIFF Converter
"""

import os
import json
import math
from collections import defaultdict

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.features import rasterize
from shapely.geometry import shape, mapping

# ============================================================================
# CONFIGURATION
# ============================================================================
INPUT_DIR = "data/delhi_ncr/yamuna_expressway/master_plan"
OUTPUT_FILE = "yamuna_expressway_masterplan_zoom16.tif"
TARGET_RESOLUTION_METERS = 2.4  # ~Zoom 16


# ============================================================================
# COLOR MAP
# ============================================================================
def hex_to_rgb(code: str):
    code = code.strip().lstrip("#")
    return tuple(int(code[i:i + 2], 16) for i in (0, 2, 4))


COLOR_MAP = {
    # Airport
    "AIRPORT": hex_to_rgb("FF0000"),
    # Railway Lines
    "RAILWAY LINES": hex_to_rgb("000000"),
    "RAILWAY_LINES": hex_to_rgb("000000"),
    # Master Plan (outline only)
    "MASTER PLAN": hex_to_rgb("6E6E6E"),
    "MASTER_PLAN": hex_to_rgb("6E6E6E"),
    # Sector Layout
    "SECTORLAYOUT ALLOTED": hex_to_rgb("000000"),  # outline only
    "SECTORLAYOUT_ALLOTED": hex_to_rgb("000000"),
    "SECTORLAYOUT RESERVED": hex_to_rgb("FF7F7F"),
    "SECTORLAYOUT_RESERVED": hex_to_rgb("FF7F7F"),
    "SECTORLAYOUT VACANT": hex_to_rgb("FFD37F"),
    "SECTORLAYOUT_VACANT": hex_to_rgb("FFD37F"),
    # Sector Boundary (outline only)
    "SECTOR BOUNDARY": hex_to_rgb("E69800"),
    "SECTOR_BOUNDARY": hex_to_rgb("E69800"),
    # AOI (outline only)
    "AOI": hex_to_rgb("FF0000"),
    # YEIDA Zones - Yamuna_Part1_PLU_Plan_2021
    "AGRICULTURE": hex_to_rgb("ABE066"),
    "CANAL": hex_to_rgb("0070FF"),
    "CANAL GREENBELT": hex_to_rgb("55FF00"),
    "CANAL_GREENBELT": hex_to_rgb("55FF00"),
    "COMMERCIAL": hex_to_rgb("E60000"),
    "DRAIN": hex_to_rgb("B5CBFD"),
    "DRAIN GREENBELT": hex_to_rgb("55FF00"),
    "DRAIN_GREENBELT": hex_to_rgb("55FF00"),
    "FACILITY": hex_to_rgb("004DA8"),
    "FOREST": hex_to_rgb("55FF00"),
    "GREEN BELT": hex_to_rgb("55FF00"),
    "GREEN_BELT": hex_to_rgb("55FF00"),
    "INDUSTRY": hex_to_rgb("C500FF"),
    "INSTITUTION": hex_to_rgb("004DA8"),
    "MIXED USE": hex_to_rgb("FFAA00"),
    "MIXED_USE": hex_to_rgb("FFAA00"),
    "NALA": hex_to_rgb("002673"),
    "PARK": hex_to_rgb("AAFF00"),
    "POND": hex_to_rgb("0070FF"),
    "RECREATIONAL GREEN": hex_to_rgb("38A800"),
    "RECREATIONAL_GREEN": hex_to_rgb("38A800"),
    "RESIDENTIAL": hex_to_rgb("FFFF00"),
    "RIVERFRONT DEVELOPMENT": hex_to_rgb("00FFC5"),
    "RIVERFRONT_DEVELOPMENT": hex_to_rgb("00FFC5"),
    "ROADS": hex_to_rgb("828282"),
    "SDZ": hex_to_rgb("E8BEFF"),
    "SECTOR19 22": hex_to_rgb("FFFF00"),
    "SECTOR19_22": hex_to_rgb("FFFF00"),
    "TRAFFIC ISLANDS": hex_to_rgb("55FF00"),
    "TRAFFIC_ISLANDS": hex_to_rgb("55FF00"),
    "TRANSPORT": hex_to_rgb("B2B2B2"),
    "VILLAGE": hex_to_rgb("E64C00"),
    "YAMUNA": hex_to_rgb("005CE6"),
    # Layer-name fallbacks (directory derived)
    "YEIDA ZONES AGRICULTURE": hex_to_rgb("ABE066"),
    "YEIDA ZONES CANAL": hex_to_rgb("0070FF"),
    "YEIDA ZONES CANAL GREENBELT": hex_to_rgb("55FF00"),
    "YEIDA ZONES COMMERCIAL": hex_to_rgb("E60000"),
    "YEIDA ZONES DRAIN": hex_to_rgb("B5CBFD"),
    "YEIDA ZONES DRAIN GREENBELT": hex_to_rgb("55FF00"),
    "YEIDA ZONES FACILITY": hex_to_rgb("004DA8"),
    "YEIDA ZONES FOREST": hex_to_rgb("55FF00"),
    "YEIDA ZONES GREEN BELT": hex_to_rgb("55FF00"),
    "YEIDA ZONES INDUSTRY": hex_to_rgb("C500FF"),
    "YEIDA ZONES INSTITUTION": hex_to_rgb("004DA8"),
    "YEIDA ZONES MIXED USE": hex_to_rgb("FFAA00"),
    "YEIDA ZONES NALA": hex_to_rgb("002673"),
    "YEIDA ZONES PARK": hex_to_rgb("AAFF00"),
    "YEIDA ZONES POND": hex_to_rgb("0070FF"),
    "YEIDA ZONES RECREATIONAL GREEN": hex_to_rgb("38A800"),
    "YEIDA ZONES RESIDENTIAL": hex_to_rgb("FFFF00"),
    "YEIDA ZONES RIVERFRONT DEVELOPMENT": hex_to_rgb("00FFC5"),
    "YEIDA ZONES ROADS": hex_to_rgb("828282"),
    "YEIDA ZONES SDZ": hex_to_rgb("E8BEFF"),
    "YEIDA ZONES TRAFFIC ISLANDS": hex_to_rgb("55FF00"),
    "YEIDA ZONES TRANSPORT": hex_to_rgb("B2B2B2"),
    "YEIDA ZONES VILLAGE": hex_to_rgb("E64C00"),
    "YEIDA ZONES YAMUNA": hex_to_rgb("005CE6"),
}

# Layers that should be outline-only (no fill)
OUTLINE_ONLY_LAYERS = {
    "MASTER PLAN",
    "MASTER_PLAN",
    "SECTORLAYOUT ALLOTED",
    "SECTORLAYOUT_ALLOTED",
    "SECTOR BOUNDARY",
    "SECTOR_BOUNDARY",
    "AOI",
}

# Airport airplane marker color
AIRPORT_MARKER_COLOR = hex_to_rgb("FFFFFF")

# Default outline color for outline-only layers
OUTLINE_COLOR = (0, 0, 0)

PATTERN_CONFIG = {
    "AIRPORT": {
        "type": "airplane",
        "color": AIRPORT_MARKER_COLOR,
        "spacing": 18,
    },
}


# ============================================================================
# HELPERS
# ============================================================================
def normalize_category(value):
    if not value:
        return None
    value = value.replace("_", " ")
    value = value.replace("/", " ")
    value = value.replace("-", " ")
    value = " ".join(value.split())
    return value.upper()


# ============================================================================
# CORE PIPELINE
# ============================================================================
def get_geojson_files(directory):
    """Recursively find all GeoJSON files in directory and subdirectories."""
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.lower().endswith(".geojson"):
                files.append(os.path.join(root, filename))

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
        rel_path = os.path.relpath(path, INPUT_DIR)
        print(f"  ✓ {rel_path}: {valid} features" + (f" ({skipped} skipped)" if skipped else ""))

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
        rel_path = os.path.relpath(path, INPUT_DIR)
        layer_base = os.path.splitext(os.path.basename(path))[0]
        layer_norm = normalize_category(layer_base)
        
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
                    or layer_base
                )
                category_norm = normalize_category(str(raw_category)) or layer_norm or layer_base.upper()
                
                # Try to find color
                color = COLOR_MAP.get(category_norm)
                if color is None and layer_norm:
                    color = COLOR_MAP.get(layer_norm)
                if color is None:
                    color = (128, 128, 128)
                    unmapped.add(category_norm)
                
                # Check if this is an outline-only layer
                is_outline_only = (
                    category_norm in OUTLINE_ONLY_LAYERS or
                    layer_norm in OUTLINE_ONLY_LAYERS
                )
                
                features.append({
                    "geometry": mapping(geom),
                    "color": color,
                    "category": category_norm,
                    "layer_name": layer_base,
                    "is_outline_only": is_outline_only
                })
            except Exception:
                continue

        if features:
            layers[layer_base] = {
                "features": features,
                "priority": 50,
                "count": len(features)
            }
            sample = "#{:02x}{:02x}{:02x}".format(*features[0]["color"])
            outline_note = " (outline only)" if features[0]["is_outline_only"] else ""
            print(f"  ✓ {layer_base}: {len(features)} features (color {sample}){outline_note}")

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
    outline_shapes = defaultdict(list)
    pattern_shapes = defaultdict(list)

    sorted_layers = sorted(layers.items(), key=lambda item: item[1]["priority"])
    total = sum(layer["count"] for layer in layers.values())
    processed = 0

    for idx, (layer_name, layer_data) in enumerate(sorted_layers, 1):
        features = layer_data["features"]
        if not features:
            continue
        print(f"  [{idx}/{len(sorted_layers)}] {layer_name}: {len(features)} features…", end="", flush=True)
        
        is_outline_only = features[0]["is_outline_only"]
        
        if not is_outline_only:
            # Regular fill rendering
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

        # Collect outlines for all features (both filled and outline-only)
        for feat in features:
            try:
                geom = shape(feat["geometry"])
                boundary = geom.boundary if hasattr(geom, "boundary") else geom
                if not boundary.is_empty:
                    outline_color = feat["color"] if is_outline_only else OUTLINE_COLOR
                    outline_shapes[outline_color].append((mapping(boundary), 1))
            except Exception:
                continue

        if not is_outline_only and features[0]["category"] in PATTERN_CONFIG:
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

    # Apply patterns (e.g., airplane markers) before outlines
    if pattern_shapes:
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
                dtype=np.uint8,
            ) == 1
            if not mask.any():
                continue
            spacing = config.get("spacing", 16)
            pattern = np.zeros_like(mask, dtype=bool)
            if config["type"] == "airplane":
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

    # Draw all outlines
    if outline_shapes:
        for outline_color, shapes_list in outline_shapes.items():
            outline_mask = rasterize(
                shapes_list,
                out_shape=(height, width),
                transform=transform,
                fill=0,
                all_touched=True,
                dtype=np.uint8
            )
            pixels = outline_mask == 1
            if pixels.any():
                r[pixels] = outline_color[0]
                g[pixels] = outline_color[1]
                b[pixels] = outline_color[2]
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
            description="Yamuna Expressway Master Plan Land Use Map (RGBA)",
            created_by="geotif_yamuna_expressway.py",
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
    print("Yamuna Expressway GeoJSON → High-Resolution RGB GeoTIFF")
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
        print("✓ SUCCESS: Yamuna Expressway master plan GeoTIFF created!")
        print("=" * 70)
        return 0

    except Exception as exc:
        print(f"\n❌ ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

