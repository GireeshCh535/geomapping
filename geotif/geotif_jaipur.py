#!/usr/bin/env python3
"""
Jaipur Master Plan GeoJSON → High-Resolution RGB GeoTIFF Converter
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
INPUT_DIR = "data/rajasthan/jaipur/master_plan"
OUTPUT_FILE = "jaipur_masterplan_zoom16.tif"
TARGET_RESOLUTION_METERS = 2.4  # ~Zoom 16

# ============================================================================
# COLOR MAP
# ============================================================================
def hex_to_rgb(code: str):
    code = code.strip().lstrip("#")
    return tuple(int(code[i:i + 2], 16) for i in (0, 2, 4))


COLOR_MAP = {
    # Solid fill colors
    "AGRICULTURE LAND": hex_to_rgb("D1FF73"),
    "AGRICULTURE_LAND": hex_to_rgb("D1FF73"),
    "COMMERCIAL": hex_to_rgb("FF0000"),
    "EDUCATIONAL": hex_to_rgb("005CE6"),
    "G1": hex_to_rgb("898944"),
    "G2": hex_to_rgb("894465"),
    "G3": hex_to_rgb("C79BDC"),
    "GREEN AREAS": hex_to_rgb("70A800"),
    "GREEN_AREAS": hex_to_rgb("70A800"),
    "HEALTH SERVICES": hex_to_rgb("73FFDF"),
    "HEALTH_SERVICES": hex_to_rgb("73FFDF"),
    "INDUSTRIAL": hex_to_rgb("A900E6"),
    "OTHERS": hex_to_rgb("E1E1E1"),
    "RECREATIONAL": hex_to_rgb("737300"),
    "RESIDENTIAL": hex_to_rgb("FFFF73"),
    "RURAL": hex_to_rgb("730000"),
    "TRANSPORTATION": hex_to_rgb("828282"),
    "VACANT LAND": hex_to_rgb("0070FF"),
    "VACANT_LAND": hex_to_rgb("0070FF"),
    "WATER BODIES": hex_to_rgb("BEE8FF"),
    "WATER_BODIES": hex_to_rgb("BEE8FF"),
}

# Pattern configurations - categories with hatched/dotted patterns
PATTERN_CONFIG = {
    "COMMUNICATION": {
        "type": "hatch",
        "color": hex_to_rgb("E69800"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("E69800"),
    },
    "ECO-SENSITIVE ZONE": {
        "type": "dots",
        "color": hex_to_rgb("38A800"),
        "spacing": 6,
        "solid_fill": hex_to_rgb("38A800"),
        "outline_color": hex_to_rgb("000000"),  # Black outline
    },
    "ECO SENSITIVE ZONE": {
        "type": "dots",
        "color": hex_to_rgb("38A800"),
        "spacing": 6,
        "solid_fill": hex_to_rgb("38A800"),
        "outline_color": hex_to_rgb("000000"),  # Black outline
    },
    "ECO_SENSITIVE__ZONE": {
        "type": "dots",
        "color": hex_to_rgb("38A800"),
        "spacing": 6,
        "solid_fill": hex_to_rgb("38A800"),
        "outline_color": hex_to_rgb("000000"),  # Black outline
    },
    "GOVT AND SEMI GOVERNMERNT": {
        "type": "cross_hatch",
        "color": hex_to_rgb("A87000"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("A87000"),
        "outline_color": hex_to_rgb("000000"),  # Black outline
    },
    "GOVT_AND_SEMI_GOVERNMERNT": {
        "type": "cross_hatch",
        "color": hex_to_rgb("A87000"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("A87000"),
        "outline_color": hex_to_rgb("000000"),  # Black outline
    },
    "HERITAGE": {
        "type": "dotted_line",
        "color": hex_to_rgb("000000"),  # Dotted line fill is black
        "spacing": 4,
        "solid_fill": hex_to_rgb("A3FF73"),  # Solid fill is green
    },
    "MIXED": {
        "type": "hatch",
        "color": hex_to_rgb("000000"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("FFAA00"),
    },
    "PUBLIC & SEMI PUBLIC": {
        "type": "dashed",
        "color": hex_to_rgb("002673"),
        "spacing": 6,
        "width": 2,
        "solid_fill": hex_to_rgb("0070FF"),
    },
    "PUBLIC___SEMI_PUBLIC": {
        "type": "dashed",
        "color": hex_to_rgb("002673"),
        "spacing": 6,
        "width": 2,
        "solid_fill": hex_to_rgb("0070FF"),
    },
    "PUBLIC UTILITIES": {
        "type": "hatch",
        "color": hex_to_rgb("FF0000"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("E69800"),
    },
    "PUBLIC_UTILITIES": {
        "type": "hatch",
        "color": hex_to_rgb("FF0000"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("E69800"),
    },
    "RELIGIOUS": {
        "type": "hatch",
        "color": hex_to_rgb("FF00C5"),  # Hatched lines color
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("FF00C5"),
        "outline_color": hex_to_rgb("FF00C5"),  # Outline same as hatch
    },
    "SPECIFIC LAND USE": {
        "type": "hatch",
        "color": hex_to_rgb("000000"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("000000"),
    },
    "SPECIFIC_LAND_USE": {
        "type": "hatch",
        "color": hex_to_rgb("000000"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("000000"),
    },
    "U1_2025": {
        "type": "hatch",
        "color": hex_to_rgb("73B2FF"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("FFFFFF"),
    },
    "U1 2025": {
        "type": "hatch",
        "color": hex_to_rgb("73B2FF"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("FFFFFF"),
    },
    "U2 HIZ": {
        "type": "hatch",
        "color": hex_to_rgb("E1E1E1"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("00A884"),
    },
    "U2_HIZ": {
        "type": "hatch",
        "color": hex_to_rgb("E1E1E1"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("00A884"),
    },
    "U2 LIZ": {
        "type": "hatch",
        "color": hex_to_rgb("FFFFFF"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("E6E600"),
    },
    "U2_LIZ": {
        "type": "hatch",
        "color": hex_to_rgb("FFFFFF"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("E6E600"),
    },
    "U3 HIZ": {
        "type": "hatch",
        "color": hex_to_rgb("FFFFFF"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("E69800"),
    },
    "U3_HIZ": {
        "type": "hatch",
        "color": hex_to_rgb("FFFFFF"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("E69800"),
    },
    "U3 LIZ": {
        "type": "hatch",
        "color": hex_to_rgb("FF0000"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("FFEBAF"),
    },
    "U3_LIZ": {
        "type": "hatch",
        "color": hex_to_rgb("FF0000"),
        "spacing": 8,
        "width": 2,
        "solid_fill": hex_to_rgb("FFEBAF"),
    },
}

# Outline-only layers (no fill, only outline)
OUTLINE_ONLY_LAYERS = {
    "SPECIFIC LAND USE",
    "SPECIFIC_LAND_USE",
}

OUTLINE_COLOR = (0, 0, 0)

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


def get_geojson_files(directory):
    """Recursively find all GeoJSON files."""
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.lower().endswith(".geojson"):
                files.append(os.path.join(root, filename))
    if not files:
        raise ValueError(f"No GeoJSON files found in {directory}")
    return sorted(files)


# ============================================================================
# CORE PIPELINE
# ============================================================================
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
    key_priority = [
        "LANDUSE_CATEGORY",
        "LANDUSE_SUBCAT_LEVEL_1",
        "NAME",
        "Name",
        "name",
        "category",
        "CATEGORY",
    ]

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
                raw_category = None
                for key in key_priority:
                    if key in props and props[key]:
                        raw_category = str(props[key])
                        break
                if raw_category is None:
                    raw_category = layer_base
                category_norm = normalize_category(raw_category)

                # Determine color and pattern
                color = None
                pattern_config = None
                is_outline_only = False

                # Check if it's an outline-only layer
                if category_norm and category_norm in OUTLINE_ONLY_LAYERS:
                    is_outline_only = True
                    color = OUTLINE_COLOR
                # Check for pattern configuration
                elif category_norm and category_norm in PATTERN_CONFIG:
                    pattern_config = PATTERN_CONFIG[category_norm]
                    color = pattern_config.get("solid_fill", pattern_config["color"])
                # Check regular color map
                elif category_norm and category_norm in COLOR_MAP:
                    color = COLOR_MAP[category_norm]
                # Try layer name as fallback
                elif layer_norm and layer_norm in COLOR_MAP:
                    color = COLOR_MAP[layer_norm]
                elif layer_norm and layer_norm in PATTERN_CONFIG:
                    pattern_config = PATTERN_CONFIG[layer_norm]
                    color = pattern_config.get("solid_fill", pattern_config["color"])
                else:
                    color = (128, 128, 128)
                    unmapped.add(category_norm or layer_norm or layer_base)

                features.append({
                    "geometry": mapping(geom),
                    "color": color,
                    "category": category_norm or layer_norm or layer_base,
                    "pattern_config": pattern_config,
                    "is_outline_only": is_outline_only,
                })
            except Exception:
                continue

        if features:
            layers[rel_path] = {
                "features": features,
                "priority": 50,
                "count": len(features),
            }
            sample = "#{:02x}{:02x}{:02x}".format(*features[0]["color"])
            pattern_note = " (pattern)" if features[0]["pattern_config"] else ""
            outline_note = " (outline only)" if features[0]["is_outline_only"] else ""
            print(f"  ✓ {rel_path}: {len(features)} features (color {sample}){pattern_note}{outline_note}")

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

    rows = np.arange(height).reshape(-1, 1)
    cols = np.arange(width).reshape(1, -1)

    for idx, (layer_name, layer_data) in enumerate(sorted_layers, 1):
        features = layer_data["features"]
        if not features:
            continue
        print(f"  [{idx}/{len(sorted_layers)}] {layer_name}: {len(features)} features…", end="", flush=True)

        is_outline_only = features[0]["is_outline_only"]
        pattern_config = features[0]["pattern_config"]

        # Render solid fill (unless outline-only)
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
                r_val, g_val, b_val = features[0]["color"]
                r[pixels] = r_val
                g[pixels] = g_val
                b[pixels] = b_val
                a[pixels] = 255

                # Collect pattern shapes if this layer has patterns
                if pattern_config:
                    for feat in features:
                        try:
                            geom = shape(feat["geometry"])
                            if not geom.is_empty:
                                pattern_shapes[layer_name].append({
                                    "geometry": mapping(geom),
                                    "config": pattern_config,
                                })
                        except Exception:
                            continue

        # Collect outlines for all features
        for feat in features:
            try:
                geom = shape(feat["geometry"])
                boundary = geom.boundary if hasattr(geom, "boundary") else geom
                if not boundary.is_empty:
                    if is_outline_only:
                        outline_color = OUTLINE_COLOR
                    elif pattern_config and "outline_color" in pattern_config:
                        outline_color = pattern_config["outline_color"]
                    else:
                        outline_color = OUTLINE_COLOR
                    outline_shapes[outline_color].append((mapping(boundary), 1))
            except Exception:
                continue

        processed += len(features)
        print(f" done ({processed / total * 100:.1f}% complete)")

    # Apply patterns
    if pattern_shapes:
        print("\n  Applying patterns…", end="", flush=True)
        for layer_name, pattern_list in pattern_shapes.items():
            if not pattern_list:
                continue
            config = pattern_list[0]["config"]
            pattern_type = config["type"]
            pattern_color = config["color"]
            spacing = config.get("spacing", 8)
            width_px = config.get("width", 2)

            # Rasterize the pattern areas
            shapes = [(item["geometry"], 1) for item in pattern_list]
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

            pattern = np.zeros_like(mask, dtype=bool)

            if pattern_type == "hatch":
                # Diagonal hatch pattern
                pattern = ((rows + cols) % spacing) < width_px
            elif pattern_type == "cross_hatch":
                # Cross hatch (both diagonals)
                pattern = np.logical_or(
                    ((rows + cols) % spacing) < width_px,
                    ((rows - cols) % spacing) < width_px
                )
            elif pattern_type == "dots":
                # Dots pattern
                pattern = ((rows % spacing) == 0) & ((cols % spacing) == 0)
            elif pattern_type == "dotted_line":
                # Dotted line pattern (smaller dots)
                dot_spacing = spacing // 2
                pattern = ((rows % dot_spacing) == 0) & ((cols % dot_spacing) == 0)
            elif pattern_type == "dashed":
                # Dashed line pattern (horizontal lines)
                dash_length = spacing // 2
                pattern = ((rows % spacing) < dash_length) & ((cols % spacing) < width_px)

            # Apply pattern only within the mask
            pattern &= mask
            if pattern.any():
                r[pattern] = pattern_color[0]
                g[pattern] = pattern_color[1]
                b[pattern] = pattern_color[2]
                a[pattern] = 255
        print(" done.")

    # Draw all outlines
    if outline_shapes:
        print("  Drawing outlines…", end="", flush=True)
        for outline_color, shapes_list in outline_shapes.items():
            outline_mask = rasterize(
                shapes_list,
                out_shape=(height, width),
                transform=transform,
                fill=0,
                all_touched=True,
                dtype=np.uint8,
            )
            pixels = outline_mask == 1
            if pixels.any():
                r[pixels] = outline_color[0]
                g[pixels] = outline_color[1]
                b[pixels] = outline_color[2]
                a[pixels] = 255
        print(" done.")

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
        BIGTIFF="YES",
    ) as dst:
        names = ["Red", "Green", "Blue", "Alpha"]
        for idx in range(4):
            print(f"  Writing {names[idx]}…", end="", flush=True)
            dst.write(rgba_data[idx], idx + 1)
            print(" done.")
        dst.update_tags(
            description="Jaipur Master Plan Land Use Map (RGBA)",
            created_by="geotif_jaipur.py",
            alpha_band="4",
            compression="lzw",
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
    print("Jaipur GeoJSON → High-Resolution RGB GeoTIFF")
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
        print("✓ SUCCESS: Jaipur master plan GeoTIFF created!")
        print("=" * 70)
        return 0

    except Exception as exc:
        print(f"\n❌ ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

