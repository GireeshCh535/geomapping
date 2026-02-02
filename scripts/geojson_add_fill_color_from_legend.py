#!/usr/bin/env python3
"""
Unified script: add fill_color from a legend.csv to every feature in GeoJSON files.

Reads a legend CSV (with columns: category, fill_color) and a data directory.
For each .geojson in the directory, adds fill_color to each feature's properties
by matching the feature's 'Name' (or 'name') to the legend's category.

Usage:
    python scripts/geojson_add_fill_color_from_legend.py \
        --legend "data/Telangana/Hyderabad/master_plan/HMDA/legend.csv" \
        --data-dir "data/Telangana/Hyderabad/master_plan/HMDA"

    # With subdirectories (e.g. HMDA + HUDA each with own legend):
    python scripts/geojson_add_fill_color_from_legend.py \
        --legend "data/Telangana/Hyderabad/master_plan/HUDA/legend.csv" \
        --data-dir "data/Telangana/Hyderabad/master_plan/HUDA"

    # Recursive: process .geojson in subdirectories of data-dir
    python scripts/geojson_add_fill_color_from_legend.py \
        --legend "path/to/legend.csv" \
        --data-dir "path/to/data" \
        --recursive

    # Dry run (no writes)
    python scripts/geojson_add_fill_color_from_legend.py \
        --legend "path/to/legend.csv" \
        --data-dir "path/to/data" \
        --dry-run
"""

import argparse
import csv
import json
from pathlib import Path


def load_legend_fill_colors(legend_path: Path, case_insensitive: bool = True) -> dict[str, str]:
    """Build category -> fill_color from legend CSV. First occurrence wins; skips empty fill_color.
    If case_insensitive, keys are stored lowercased so 'Agriculture Land' matches 'AGRICULTURE LAND'.
    """
    mapping = {}
    with open(legend_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = (row.get("category") or "").strip()
            fill = (row.get("fill_color") or "").strip()
            if not category or not fill:
                continue
            # Normalize: lowercase and collapse spaces for case-insensitive match
            key = " ".join(category.lower().split()) if case_insensitive else category
            if key not in mapping:
                mapping[key] = fill
    return mapping


def add_fill_color_to_geojson(
    geojson_path: Path,
    category_to_fill: dict[str, str],
    *,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Load GeoJSON, add fill_color to each feature's properties, optionally save back.
    Returns (features_updated, features_missing_color).
    """
    with open(geojson_path, encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    updated = 0
    missing = 0

    # Property keys to try for category name (Hyderabad: Name; Udaipur: LANDUSE_CA; Jaipur: LANDUSE_CATEGORY)
    name_keys = (
        "Name", "name",
        "LANDUSE_CA", "LANDUSE_CATEGORY", "LANDUSE_SUBCAT_LEVEL_1",
        "zone_name", "Zone", "zone_category", "category",
    )
    # Fallback: use filename stem (e.g. Agriculture_Land.geojson -> "Agriculture Land") when no prop
    file_stem = geojson_path.stem.replace("_", " ")

    for feature in features:
        props = feature.get("properties") or {}
        name = ""
        for key in name_keys:
            val = (props.get(key) or "").strip()
            if val:
                name = val
                break
        if not name:
            name = file_stem
        # Lookup: legend is stored with lowercase keys; normalize spaces for case-insensitive match
        lookup_key = " ".join((name or "").strip().lower().split()) if name else ""
        fill = category_to_fill.get(lookup_key) if lookup_key else None
        if fill is not None:
            props["fill_color"] = fill
            updated += 1
        else:
            missing += 1

    if not dry_run:
        with open(geojson_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    return updated, missing


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add fill_color from legend.csv to every feature in GeoJSON files in a directory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--legend",
        type=Path,
        required=True,
        help="Path to legend CSV (must have columns: category, fill_color)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Directory containing .geojson files (or parent of subdirs if --recursive)",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search for .geojson files in subdirectories of data-dir",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write files; only report what would be updated",
    )
    args = parser.parse_args()

    legend_path = args.legend.resolve()
    data_dir = args.data_dir.resolve()

    if not legend_path.exists():
        raise SystemExit(f"Legend not found: {legend_path}")

    if not data_dir.is_dir():
        raise SystemExit(f"Data directory not found or not a directory: {data_dir}")

    category_to_fill = load_legend_fill_colors(legend_path)
    print(f"Loaded {len(category_to_fill)} category -> fill_color from {legend_path.name}")

    if args.recursive:
        geojson_files = sorted(data_dir.rglob("*.geojson"))
    else:
        geojson_files = sorted(data_dir.glob("*.geojson"))

    if not geojson_files:
        scope = "and subdirs" if args.recursive else ""
        raise SystemExit(f"No .geojson files found in {data_dir} {scope}")

    print(f"Found {len(geojson_files)} .geojson file(s)")
    if args.dry_run:
        print("(dry run — no files will be modified)\n")

    total_updated = 0
    total_missing = 0
    for path in geojson_files:
        updated, missing = add_fill_color_to_geojson(
            path, category_to_fill, dry_run=args.dry_run
        )
        total_updated += updated
        total_missing += missing
        try:
            rel = path.relative_to(data_dir)
        except ValueError:
            rel = path.name
        status = "ok" if missing == 0 else f"missing_color={missing}"
        print(f"  {rel}: {updated} feature(s) updated, {status}")

    print(f"\nDone: {total_updated} features got fill_color, {total_missing} without match in legend.")


if __name__ == "__main__":
    main()
