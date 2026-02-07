#!/usr/bin/env python3
"""
Add fill_color from legend.csv to every feature in HMDA and HUDA GeoJSON files.

For each folder (HMDA, HUDA) under data/Telangana/Hyderabad/master_plan/:
  - Reads that folder's legend.csv and maps category -> fill_color
  - For each .geojson in that folder, adds fill_color to each feature's properties
    based on the feature's 'Name' property (matched to legend category).
"""

import csv
import json
import os
from pathlib import Path


def load_legend_fill_colors(legend_path: Path) -> dict[str, str]:
    """Build category -> fill_color from legend CSV. First occurrence wins; skips empty fill_color."""
    mapping = {}
    with open(legend_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = (row.get("category") or "").strip()
            fill = (row.get("fill_color") or "").strip()
            if category and fill and category not in mapping:
                mapping[category] = fill
    return mapping


def add_fill_color_to_geojson(geojson_path: Path, category_to_fill: dict[str, str]) -> tuple[int, int]:
    """
    Load GeoJSON, add fill_color to each feature's properties, save back.
    Returns (features_updated, features_missing_color).
    """
    with open(geojson_path, encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    updated = 0
    missing = 0

    for feature in features:
        props = feature.get("properties") or {}
        name = (props.get("Name") or props.get("name") or "").strip()
        fill = category_to_fill.get(name) if name else None
        if fill is not None:
            props["fill_color"] = fill
            updated += 1
        else:
            missing += 1

    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return updated, missing


def main() -> None:
    # Paths relative to project root (script lives in scripts/)
    project_root = Path(__file__).resolve().parent.parent
    master_plan_base = project_root / "data" / "Telangana" / "Hyderabad" / "master_plan"

    total_updated = 0
    total_missing = 0

    for folder_name in ("HMDA", "HUDA"):
        folder_path = master_plan_base / folder_name
        legend_path = folder_path / "legend.csv"

        if not legend_path.exists():
            print(f"[{folder_name}] Legend not found: {legend_path}, skipping.")
            continue

        category_to_fill = load_legend_fill_colors(legend_path)
        print(f"\n[{folder_name}] Loaded {len(category_to_fill)} category -> fill_color from legend.csv")

        geojson_files = sorted(folder_path.glob("*.geojson"))
        if not geojson_files:
            print(f"  No .geojson files in {folder_path}")
            continue

        for path in geojson_files:
            updated, missing = add_fill_color_to_geojson(path, category_to_fill)
            total_updated += updated
            total_missing += missing
            status = "ok" if missing == 0 else f"missing_color={missing}"
            print(f"  {path.name}: {updated} feature(s) updated, {status}")

    print(f"\nDone: {total_updated} features got fill_color, {total_missing} without match in legend.")


if __name__ == "__main__":
    main()
