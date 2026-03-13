#!/usr/bin/env python3
"""
Add fill_color to every feature in Hyderabad master plan GeoJSON files (HMDA + HUDA).
Reads legend.csv in each subdir and sets feature['properties']['fill_color'] by category.
Category is resolved from ORIGINAL_CATEGORY, LANDUSE_CATEGORY, CATEGORY, Name, etc., or filename stem.
Output is written to a new directory by default (input_dir + '_colored') so originals are unchanged.

Usage:
  python3 add_fill_color_to_hyderabad_features.py
  python3 add_fill_color_to_hyderabad_features.py --input-dir data/telangana/hyderabad/master_plan_split --output-dir data/telangana/hyderabad/master_plan_split_colored
  python3 add_fill_color_to_hyderabad_features.py --input-dir data/telangana/hyderabad/masterplan --output-dir data/telangana/hyderabad/masterplan_colored
"""

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

DEFAULT_FILL = "#cccccc"


def normalize_category(value):
    """Match tile generator: uppercase, spaces normalized."""
    if not value:
        return None
    value = " ".join(str(value).replace("_", " ").split())
    return value.upper()


def load_legend_fill_map(legend_path: Path) -> dict:
    """Load legend.csv and return dict: normalized_category -> fill_color (hex)."""
    fill_map = {}
    if not legend_path.exists():
        return fill_map
    with open(legend_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = (row.get("category") or "").strip()
            if not category:
                continue
            fill = (row.get("fill_color") or "").strip()
            if not fill:
                fill = DEFAULT_FILL
            norm = normalize_category(category)
            fill_map[norm] = fill
            fill_map[norm.replace(" ", "_")] = fill
    return fill_map


def get_feature_category(feature: dict, filename_stem: str) -> str:
    """Resolve category from feature properties or filename (same order as tile generator)."""
    props = feature.get("properties") or {}
    raw = (
        props.get("ORIGINAL_CATEGORY")
        or props.get("LANDUSE_CATEGORY")
        or props.get("CATEGORY")
        or props.get("Name")
        or props.get("name")
        or props.get("LAYER")
        or filename_stem
    )
    return normalize_category(str(raw)) if raw is not None else normalize_category(filename_stem)


def process_geojson(input_path: Path, output_path: Path, fill_map: dict, filename_stem: str) -> int:
    """Load GeoJSON, add fill_color to each feature, write to output_path. Returns feature count."""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    features = data.get("features", [])
    for feat in features:
        category_norm = get_feature_category(feat, filename_stem)
        fill_color = fill_map.get(category_norm, DEFAULT_FILL)
        if "properties" not in feat:
            feat["properties"] = {}
        feat["properties"]["fill_color"] = fill_color
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    return len(features)


def main():
    parser = argparse.ArgumentParser(
        description="Add fill_color from legend.csv to every feature in HMDA/HUDA GeoJSON files"
    )
    parser.add_argument(
        "--input-dir", "-i",
        default="data/telangana/hyderabad/master_plan_split",
        help="Input directory containing HMDA/ and HUDA/ with .geojson and legend.csv",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Output directory (default: <input-dir>_colored). Use same as input-dir for in-place.",
    )
    args = parser.parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir) if args.output_dir is not None else Path(str(input_dir) + "_colored")

    if not input_dir.exists():
        print(f"Error: input directory not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Input:  {input_dir}")
    print(f"Output: {output_dir}")
    print()

    total_files = 0
    total_features = 0

    for subdir in ["HMDA", "HUDA"]:
        in_sub = input_dir / subdir
        out_sub = output_dir / subdir
        if not in_sub.exists():
            print(f"Skip (not found): {in_sub}")
            continue

        legend_path = in_sub / "legend.csv"
        fill_map = load_legend_fill_map(legend_path)
        if not fill_map:
            print(f"Warning: no legend or empty legend at {legend_path}")
        else:
            print(f"[{subdir}] Loaded {len(fill_map)} category→fill_color entries from legend.csv")

        if legend_path.exists():
            out_sub.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legend_path, out_sub / "legend.csv")
            print(f"[{subdir}] Copied legend.csv")

        for geojson_path in sorted(in_sub.glob("*.geojson")):
            out_path = out_sub / geojson_path.name
            stem = geojson_path.stem
            n = process_geojson(geojson_path, out_path, fill_map, stem)
            total_files += 1
            total_features += n
            print(f"[{subdir}] {geojson_path.name} → {n} features")

    print()
    print(f"Done: {total_files} files, {total_features} features written to {output_dir}")


if __name__ == "__main__":
    main()
