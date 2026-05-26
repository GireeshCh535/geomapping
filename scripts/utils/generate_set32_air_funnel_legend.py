#!/usr/bin/env python3
"""
Build legend.csv for each airport folder under data/set32.

IAF Air Funnel Zones (CCZM): category = Max Permissible Height, fill from HEX.
Danger Area → #FF8C00, Prohibited Area → #36454F.

Usage (repo root):
  python3 scripts/utils/generate_set32_air_funnel_legend.py
  python3 scripts/utils/generate_set32_air_funnel_legend.py data/set32/BAGDOGRA
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

DANGER_FILL = "#FF8C00"
PROHIBITED_FILL = "#36454F"
DEFAULT_OUTLINE = "#000000"

HEIGHT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*m", re.I)


def fill_for_file(path: Path, hex_from_props: str) -> str:
    name_upper = path.stem.upper()
    if "DANGER AREA" in name_upper or "DANGER_AREA" in name_upper:
        return DANGER_FILL
    if "PROHIBITED" in name_upper:
        return PROHIBITED_FILL
    h = (hex_from_props or "").strip()
    if h and not h.startswith("#"):
        h = f"#{h}"
    return h


def height_sort_key(category: str) -> tuple:
    """Sort height zones numerically; text-only categories last."""
    m = HEIGHT_RE.search(category)
    if m:
        return (0, float(m.group(1)), category.lower())
    if "mandatory noc" in category.lower():
        return (1, 0, category.lower())
    if "clearances" in category.lower() or "danger" in category.lower():
        return (2, 0, category.lower())
    if "prohibited" in category.lower():
        return (3, 0, category.lower())
    return (4, 0, category.lower())


def category_label(props: dict, base: str, disambiguate: bool) -> str:
    if not disambiguate:
        return base
    colour = (props.get("Colour") or props.get("colour") or "").strip()
    if colour:
        return f"{base} ({colour})"
    return base


def collect_entries(folder: Path) -> tuple[dict[str, str], set[str]]:
    """category (Max Permissible Height) -> fill_color; returns entries and base labels needing disambiguation."""
    raw: dict[str, set[str]] = {}
    label_fill: dict[str, str] = {}

    for gj in sorted(folder.glob("*.geojson")):
        with open(gj, encoding="utf-8") as f:
            data = json.load(f)
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            base = (props.get("Max Permissible Height") or "").strip()
            if not base:
                continue
            hex_val = props.get("HEX") or props.get("hex") or ""
            fill = fill_for_file(gj, str(hex_val))
            if not fill:
                continue
            raw.setdefault(base, set()).add(fill)

    ambiguous = {b for b, fills in raw.items() if len(fills) > 1}
    entries: dict[str, str] = {}

    for gj in sorted(folder.glob("*.geojson")):
        with open(gj, encoding="utf-8") as f:
            data = json.load(f)
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            base = (props.get("Max Permissible Height") or "").strip()
            if not base:
                continue
            hex_val = props.get("HEX") or props.get("hex") or ""
            fill = fill_for_file(gj, str(hex_val))
            if not fill:
                continue
            cat = category_label(props, base, base in ambiguous)
            if cat in entries and entries[cat] != fill:
                raise ValueError(
                    f"{folder.name}/{gj.name}: conflicting fill for {cat!r}: "
                    f"{entries[cat]} vs {fill}"
                )
            entries[cat] = fill

    return entries, ambiguous


def sync_disambiguated_geojson(folder: Path, ambiguous: set[str]) -> int:
    """Align Max Permissible Height with legend when same height has multiple zone colours."""
    if not ambiguous:
        return 0
    updated_files = 0
    for gj in sorted(folder.glob("*.geojson")):
        with open(gj, encoding="utf-8") as f:
            data = json.load(f)
        changed = False
        for feat in data.get("features") or []:
            props = feat.setdefault("properties", {})
            base = (props.get("Max Permissible Height") or "").strip()
            if base not in ambiguous:
                continue
            new_label = category_label(props, base, True)
            if props.get("Max Permissible Height") != new_label:
                props["Max Permissible Height"] = new_label
                changed = True
        if changed:
            with open(gj, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            updated_files += 1
    return updated_files


def write_legend(folder: Path, entries: dict[str, str]) -> Path:
    legend_path = folder / "legend.csv"
    rows = [
        {
            "category": cat,
            "fill_color": fill,
            "outline_color": DEFAULT_OUTLINE,
            "pattern": "",
            "pattern_color": "",
        }
        for cat, fill in sorted(entries.items(), key=lambda x: height_sort_key(x[0]))
    ]
    with open(legend_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["category", "fill_color", "outline_color", "pattern", "pattern_color"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return legend_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate legend.csv for set32 air funnel folders")
    parser.add_argument(
        "folders",
        nargs="*",
        help="Folder(s) under data/set32 (default: all subdirectories)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data/set32"),
        help="set32 root (default: data/set32)",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    if args.folders:
        targets = [Path(p).resolve() for p in args.folders]
    else:
        targets = sorted(p for p in root.iterdir() if p.is_dir())

    if not targets:
        print(f"No folders under {root}")
        return

    for folder in targets:
        if not folder.is_dir():
            print(f"Skip (not a directory): {folder}")
            continue
        entries, ambiguous = collect_entries(folder)
        if not entries:
            print(f"Skip (no features): {folder.name}")
            continue
        n_synced = sync_disambiguated_geojson(folder, ambiguous)
        if ambiguous:
            print(
                f"  {folder.name}: disambiguated {len(ambiguous)} height label(s) "
                f"using Colour ({n_synced} geojson file(s) updated)"
            )
        out = write_legend(folder, entries)
        print(f"✓ {out.relative_to(Path.cwd())} ({len(entries)} categories)")


if __name__ == "__main__":
    main()
