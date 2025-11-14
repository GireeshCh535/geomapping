#!/usr/bin/env python3
"""
Delhi NCR GeoJSON to High-Resolution RGB GeoTIFF Converter
Converts Delhi NCR master plan GeoJSON files to RGB GeoTIFF with transparent background
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
INPUT_DIR = "data/delhi_ncr/master_plan"
OUTPUT_FILE = "delhi_ncr_masterplan_zoom16.tif"

# Resolution (meters per pixel). Zoom 16 (≈2.4 m) keeps detail while staying tractable.
TARGET_RESOLUTION_METERS = 2.4

# ============================================================================
# COLOR SCHEME - Delhi Master Plan (hex fill colors)
# ============================================================================
def hex_to_rgb(hex_color: str):
    hex_color = hex_color.strip().lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


COLOR_MAP = {
    "AGRICULTURE": hex_to_rgb("005CE6"),
    "AIR CITY": hex_to_rgb("FFFFFF"),
    "CITY PARK": hex_to_rgb("4CE600"),
    "COLD STORAGE": hex_to_rgb("FF0000"),
    "COMMUNITY CENTRE": hex_to_rgb("FF0000"),
    "COMMUNITY PARK": hex_to_rgb("4CE600"),
    "CULTURAL COMPLEX": hex_to_rgb("005CE6"),
    "DISTRICT CENTRE": hex_to_rgb("FF0000"),
    "EDUCATION AND RESEARCH": hex_to_rgb("005CE6"),
    "ELECTRICITY (POWER HOUSE SUB STATION)": hex_to_rgb("FFFFFF"),
    "FOREIGN MISSION": hex_to_rgb("FFFF00"),
    "GENERAL BUSINESS": hex_to_rgb("FF0000"),
    "GOVERNMENT LAND": hex_to_rgb("FFFFFF"),
    "GOVERNMET OFFICE": hex_to_rgb("FFFFFF"),
    "HISTORICAL MONUMENTS": hex_to_rgb("4CE600"),
    "HOSPITAL": hex_to_rgb("005CE6"),
    "HOTEL": hex_to_rgb("FF0000"),
    "INDUSTRY": hex_to_rgb("8400A8"),
    "MANUFACTURING SERVICE AND REPAIR INDUSTRY": hex_to_rgb("8400A8"),
    "NON HIERARCHIALCOMMERCIAL CENTRE": hex_to_rgb("FF0000"),
    "PARK": hex_to_rgb("4CE600"),
    "PARLIAMENT HOUSE": hex_to_rgb("FFFFFF"),
    "POLICE": hex_to_rgb("005CE6"),
    "POLICE HEADQUATER": hex_to_rgb("005CE6"),
    "PRESIDENT HOUSE": hex_to_rgb("FFFFFF"),
    "REGIONAL PARK": hex_to_rgb("267300"),
    "RELIGIOUS": hex_to_rgb("FFFFFF"),
    "RESIDENTIAL AREA": hex_to_rgb("FFFF00"),
    "SEWERAGE (TREATMENT PLANT)": hex_to_rgb("FFFFFF"),
    "SOCIAL CULTURAL": hex_to_rgb("005CE6"),
    "SOLID WASTE (SANITERY LANDFILL)": hex_to_rgb("FFFFFF"),
    "SPECIAL AREA": hex_to_rgb("7AF5CA"),
    "SPORTS": hex_to_rgb("4CE600"),
    "SPORTS CENTRE": hex_to_rgb("4CE600"),
    "SPORTS FACILITIES": hex_to_rgb("4CE600"),
    "STADIUM": hex_to_rgb("4CE600"),
    "TERMINAL": hex_to_rgb("FFFFFF"),
    "TERMINAL-RAIL": hex_to_rgb("FFFFFF"),
    "TRANSMISSION CENTRE": hex_to_rgb("005CE6"),
    "TRANSMISSION SITE": hex_to_rgb("005CE6"),
    "UNIVERSITY CENTRE": hex_to_rgb("005CE6"),
    "URBANISABLE AREA": hex_to_rgb("000000"),
    "WAREHOUSING": hex_to_rgb("FF0000"),
    "WASTE LAND": hex_to_rgb("7AF5CA"),
    "WATER BODIES": hex_to_rgb("73B2FF"),
    "WATER TREATMENT PLANT": hex_to_rgb("FFFFFF"),
    "WHOLE SALE": hex_to_rgb("FF73DF"),
}

OUTLINE_COLOR = (0, 0, 0)

# ============================================================================
# HELPERS
# ============================================================================
def normalize_category(value: str | None):
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    value = value.replace("_", " ")
    value = " ".join(value.split())
    return value.upper()

# ============================================================================
# FUNCTIONS
# ============================================================================
def get_geojson_files(directory: str):
    files = glob.glob(os.path.join(directory, "*.geojson"))
    if not files:
        raise ValueError(f"No GeoJSON files found in: {directory}")
    return sorted(files)


def calculate_bounds(geojson_files):
    print("\n[1/6] Calculating bounds...")
    minx = miny = float("inf")
    maxx = maxy = float("-inf")
    total_features = total_skipped = 0

    for filepath in geojson_files:
        filename = os.path.basename(filepath)
        with open(filepath, "r") as f:
            data = json.load(f)

        features = data.get("features", [])
        valid_count = skipped = 0

        for feature in features:
            try:
                geom = shape(feature["geometry"])
                if geom.is_empty:
                    skipped += 1
                    continue
                b = geom.bounds
                minx = min(minx, b[0])
                miny = min(miny, b[1])
                maxx = max(maxx, b[2])
                maxy = max(maxy, b[3])
                valid_count += 1
            except Exception:
                skipped += 1

        total_features += valid_count
        total_skipped += skipped
        status = f"{valid_count} features"
        if skipped:
            status += f" ({skipped} skipped)"
        print(f"  ✓ {filename}: {status}")

    bounds = (minx, miny, maxx, maxy)
    print(f"\n  Bounds: [{minx:.6f}, {miny:.6f}, {maxx:.6f}, {maxy:.6f}]")
    print(f"  Total features: {total_features:,}")
    if total_skipped:
        print(f"  Total skipped: {total_skipped}")
    return bounds


def calculate_dimensions(bounds, target_resolution_meters):
    print("\n[2/6] Calculating dimensions...")
    minx, miny, maxx, maxy = bounds
    width_deg = maxx - minx
    height_deg = maxy - miny

    center_lat = (miny + maxy) / 2
    km_per_deg_lon = 111.32 * math.cos(math.radians(center_lat))
    km_per_deg_lat = 111.32

    width_km = width_deg * km_per_deg_lon
    height_km = height_deg * km_per_deg_lat

    width_m = width_km * 1000
    height_m = height_km * 1000

    width_px = max(1, int(width_m / target_resolution_meters))
    height_px = max(1, int(height_m / target_resolution_meters))

    actual_resolution = width_m / width_px
    total_pixels = width_px * height_px
    uncompressed_mb = (total_pixels * 4) / (1024 * 1024)

    print(f"  Extent: {width_km:.2f} km × {height_km:.2f} km")
    print(f"  Target resolution: {target_resolution_meters:.2f} m/pixel")
    print(f"  Actual resolution: {actual_resolution:.2f} m/pixel")
    print(f"  Output dimensions: {width_px:,} × {height_px:,}")
    print(f"  Total pixels: {total_pixels:,}")
    print(f"  File size (uncompressed RGBA): ~{uncompressed_mb:.0f} MB")

    if total_pixels > 100_000_000:
        print("  ⚠️  Large image - ensure you have sufficient RAM and disk space.")
    return width_px, height_px


def load_features_by_layer(geojson_files):
    print("\n[3/6] Loading features by layer...")
    layers = {}
    color_usage = {}
    unmapped = set()

    for filepath in geojson_files:
        layer_name = os.path.basename(filepath).replace(".geojson", "")
        layer_name_norm = normalize_category(layer_name)
        with open(filepath, "r") as f:
            data = json.load(f)

        features = []
        for feature in data.get("features", []):
            try:
                geom = shape(feature["geometry"])
                if geom.is_empty:
                    continue

                props = feature.get("properties") or {}
                raw_category = (
                    props.get("category") or props.get("CATEGORY") or props.get("Category")
                    or props.get("NAME") or props.get("Name") or props.get("name")
                    or props.get("zone") or props.get("ZONE") or props.get("Zone")
                    or props.get("use") or props.get("USE")
                    or layer_name
                )
                category_norm = normalize_category(raw_category) or layer_name_norm

                color = COLOR_MAP.get(category_norm)
                if color is None and layer_name_norm:
                    color = COLOR_MAP.get(layer_name_norm)
                if color is None:
                    color = (128, 128, 128)
                    unmapped.add(category_norm or layer_name_norm or layer_name)

                features.append({
                    "geometry": mapping(geom),
                    "color": color,
                    "category": category_norm or raw_category or layer_name
                })
            except Exception:
                continue

        if features:
            layers[layer_name] = {
                "features": features,
                "priority": 50,
                "count": len(features)
            }
            sample_color = '#{:02x}{:02x}{:02x}'.format(*features[0]["color"])
            color_usage[layer_name] = sample_color
            print(f"  ✓ {layer_name}: {len(features)} features (color: {sample_color})")

    if unmapped:
        print("\n  ⚠️  Categories without color mapping (using gray):")
        for cat in sorted(unmapped):
            print(f"    - {cat}")
    return layers


def rasterize_rgb(layers, bounds, width, height):
    print("\n[4/6] Rasterizing to RGBA...")
    minx, miny, maxx, maxy = bounds
    transform = from_bounds(minx, miny, maxx, maxy, width, height)

    r_band = np.zeros((height, width), dtype=np.uint8)
    g_band = np.zeros((height, width), dtype=np.uint8)
    b_band = np.zeros((height, width), dtype=np.uint8)
    a_band = np.zeros((height, width), dtype=np.uint8)
    outline_shapes = []

    sorted_layers = sorted(layers.items(), key=lambda x: x[1]["priority"])
    total_features = sum(layer["count"] for layer in layers.values())
    processed = 0

    print(f"  Rendering {len(sorted_layers)} layers ({total_features:,} features)...")

    for layer_idx, (layer_name, layer_data) in enumerate(sorted_layers, 1):
        features = layer_data["features"]
        if not features:
            continue

        print(f"  [{layer_idx}/{len(sorted_layers)}] {layer_name}: {len(features)} features...", end="", flush=True)
        shapes = [(feat["geometry"], 1) for feat in features]

        try:
            mask = rasterize(
                shapes=shapes,
                out_shape=(height, width),
                transform=transform,
                fill=0,
                all_touched=True,
                dtype=np.uint8
            )

            layer_pixels = mask == 1
            if not layer_pixels.any():
                print(" skipped (no pixels).")
                continue

            r, g, b = features[0]["color"]
            r_band[layer_pixels] = r
            g_band[layer_pixels] = g
            b_band[layer_pixels] = b
            a_band[layer_pixels] = 255

            # Collect outline geometries to render at the end (so they stay on top)
            for feat in features:
                try:
                    geom = shape(feat["geometry"])
                    boundary = geom.boundary if hasattr(geom, "boundary") else geom
                    if boundary.is_empty:
                        continue
                    outline_shapes.append((mapping(boundary), 1))
                except Exception:
                    continue

            processed += len(features)
            progress = (processed / total_features) * 100
            print(f" done ({progress:.1f}% complete).")

        except Exception as exc:
            print(f" ERROR: {exc}")
            continue

    # Draw outlines last so they remain visible above fills
    if outline_shapes:
        outline_mask = rasterize(
            shapes=outline_shapes,
            out_shape=(height, width),
            transform=transform,
            fill=0,
            all_touched=True,
            dtype=np.uint8
        )
        outline_pixels = outline_mask == 1
        if outline_pixels.any():
            r_band[outline_pixels] = OUTLINE_COLOR[0]
            g_band[outline_pixels] = OUTLINE_COLOR[1]
            b_band[outline_pixels] = OUTLINE_COLOR[2]
            a_band[outline_pixels] = 255

    return np.stack([r_band, g_band, b_band, a_band]), transform


def write_rgb_geotiff(rgba_data, transform, output_file):
    print("\n[5/6] Writing RGB GeoTIFF (LZW compressed)...")
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
        band_names = ["Red", "Green", "Blue", "Alpha"]
        for idx in range(4):
            print(f"  Writing {band_names[idx]}...", end="", flush=True)
            dst.write(rgba_data[idx], idx + 1)
            print(" done.")

        dst.update_tags(
            description="Delhi NCR Master Plan Land Use Map (RGBA)",
            created_by="geotif_delhi.py",
            alpha_band="4",
            compression="lzw"
        )

    size_mb = os.path.getsize(output_file) / (1024 * 1024)
    print(f"  ✓ File written: {output_file} ({size_mb:.2f} MB)")


def verify_output(output_file):
    print("\n[6/6] Verifying output...")
    with rasterio.open(output_file) as src:
        print(f"  Dimensions: {src.width} × {src.height}")
        print(f"  Bands: {src.count}")
        print(f"  CRS: {src.crs}")
        print(f"  Compression: {src.compression}")

        if src.count >= 4:
            alpha = src.read(4)
            opaque_pixels = np.sum(alpha > 0)
            print(f"  Opaque pixels: {opaque_pixels:,}")
    print("  ✓ Verification complete.")


def main():
    print("=" * 70)
    print("Delhi NCR GeoJSON to High-Resolution RGB GeoTIFF")
    print("=" * 70)
    print(f"\nInput directory: {INPUT_DIR}")
    print(f"Output file: {OUTPUT_FILE}")
    print(f"Target resolution: {TARGET_RESOLUTION_METERS} m/pixel (~Zoom 16)")

    if not os.path.exists(INPUT_DIR):
        print(f"\n❌ ERROR: Directory not found: {INPUT_DIR}")
        return 1

    try:
        geojson_files = get_geojson_files(INPUT_DIR)
        print(f"\nFound {len(geojson_files)} GeoJSON files")

        bounds = calculate_bounds(geojson_files)
        width, height = calculate_dimensions(bounds, TARGET_RESOLUTION_METERS)
        layers = load_features_by_layer(geojson_files)

        if not layers:
            print("\n❌ ERROR: No valid features found!")
            return 1

        rgba_data, transform = rasterize_rgb(layers, bounds, width, height)
        write_rgb_geotiff(rgba_data, transform, OUTPUT_FILE)
        verify_output(OUTPUT_FILE)

        print("\n" + "=" * 70)
        print("✓ SUCCESS: Delhi NCR GeoTIFF created!")
        print("=" * 70)
        return 0

    except Exception as exc:
        print(f"\n❌ ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

