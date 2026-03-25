#!/usr/bin/env python3
"""
Sync legend.csv fill (and outline) colors from GeoJSON HEX properties.
Tile generator uses legend.csv; HEX in GeoJSON is ignored when legend has a fill.

Run from repo root:
  python3 scripts/utils/sync_crz_legend_from_geojson.py
      → all data/crz/*/legend.csv
  python3 scripts/utils/sync_crz_legend_from_geojson.py "data/Yanam CRZ layers_processed"
      → that folder only (must contain legend.csv)
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
from pathlib import Path


def norm(s: str) -> str:
    return " ".join(str(s).replace("_", " ").split()).upper()


def canon_hex(h: str | None) -> str | None:
    if not h:
        return None
    h = str(h).strip().lower()
    return h if h.startswith("#") else f"#{h}"


# Outlines paired with synced fills (same keys as Andhra Pradesh reference).
OUTLINE_BY_CATEGORY: dict[str, str] = {
    norm("CRZ 1A"): "#2d5a1e",
    norm("CRZ 1B"): "#3d2fa8",
    norm("CRZ 2"): "#b32d6a",
    norm("CRZ 3"): "#c4860a",
    norm("CRZ 3B"): "#d4c020",
    norm("CRZ 4A"): "#0d7ea6",
    norm("CRZ 4B"): "#0a5f7a",
    norm("CRZ (Coastal Regulation Zone) Boundary"): "#2db8a0",
    norm("CRZ 1A - 50 m Mangrove Buffer Zone"): "#2d5a1e",
    norm("CRZ 1A - 50 m Mangrove Buffer Zone (CRZ IA)"): "#2d5a1e",
    norm("CRZ 1A - Sand Dune Beyond CRZ Boundary"): "#4a5a38",
    norm("CRZ 1A - Diversion of Reserved Forest"): "#2d5a1e",
    norm("CRZ 1A - Ecologically Sensitive Zone"): "#2d5a1e",
    norm("High Tide Line (HTL)"): "#b2007a",
    norm("Low Tide Line (LTL)"): "#0d1499",
    norm("CVCA (Critically Vulnerable Coastal Area) Boundary"): "#989826",
}


def darken_hex(fill: str, factor: float = 0.55) -> str:
    h = fill.lstrip("#")
    if len(h) != 6:
        return "#333333"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r, g, b = int(r * factor), int(g * factor), int(b * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def outline_for_category(category: str, fill: str) -> str:
    k = norm(category)
    return OUTLINE_BY_CATEGORY.get(k, darken_hex(fill))


def hexes_from_geojson(path: Path) -> set[str]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    out: set[str] = set()
    for feat in data.get("features") or []:
        p = feat.get("properties") or {}
        h = p.get("HEX") or p.get("hex")
        c = canon_hex(h)
        if c:
            out.add(c)
    return out


def _row_only_fieldnames(row: dict, fieldnames: list[str]) -> dict[str, str]:
    """Drop stray keys (e.g. None) from DictReader when CSV has an extra trailing comma."""
    return {fn: (row.get(fn) or "").strip() if row.get(fn) is not None else "" for fn in fieldnames}


def sync_region(region_dir: Path) -> tuple[int, list[str]]:
    legend_path = region_dir / "legend.csv"
    if not legend_path.is_file():
        return 0, [f"skip (no legend): {region_dir}"]

    stem_to_hex: dict[str, str] = {}
    logs: list[str] = []

    for gj in sorted(region_dir.glob("*.geojson")):
        hx = hexes_from_geojson(gj)
        if not hx:
            logs.append(f"  {gj.name}: no HEX in properties")
            continue
        if len(hx) > 1:
            logs.append(f"  {gj.name}: multiple HEX {sorted(hx)} — using {sorted(hx)[0]}")
        stem_to_hex[norm(gj.stem)] = sorted(hx)[0]

    rows: list[dict[str, str]] = []
    updated = 0
    with open(legend_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        raw_fields = reader.fieldnames or []
        fieldnames = [x for x in raw_fields if x]
        if not fieldnames:
            return 0, ["empty legend"]
        for row in reader:
            row = _row_only_fieldnames(row, fieldnames)
            cat = (row.get("category") or "").strip()
            if not cat:
                rows.append(row)
                continue
            key = norm(cat)
            if key not in stem_to_hex:
                rows.append(row)
                continue
            new_fill = stem_to_hex[key]
            old_fill = (row.get("fill_color") or "").strip().lower()
            new_outline = outline_for_category(cat, new_fill)
            if old_fill != new_fill or (row.get("outline_color") or "").strip().lower() != new_outline:
                updated += 1
            row["fill_color"] = new_fill
            row["outline_color"] = new_outline
            rows.append(row)

    fd, tmp_path = tempfile.mkstemp(
        suffix=".csv", prefix="legend_", dir=str(legend_path.parent)
    )
    try:
        with open(fd, "w", encoding="utf-8", newline="") as out:
            w = csv.DictWriter(out, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        shutil.move(tmp_path, legend_path)
    except OSError:
        Path(tmp_path).unlink(missing_ok=True)
        raise

    return updated, logs


def _resolve_under_repo(repo_root: Path, p: Path) -> Path:
    if p.is_absolute():
        return p.resolve()
    return (repo_root / p).resolve()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    argv_paths = [Path(a) for a in sys.argv[1:] if a.strip()]

    if argv_paths:
        regions: list[Path] = []
        for raw in argv_paths:
            p = _resolve_under_repo(repo_root, raw)
            if (p / "legend.csv").is_file():
                regions.append(p)
            elif p.is_dir():
                found = {x.parent for x in p.rglob("legend.csv")}
                if not found:
                    print(f"⚠️  No legend.csv under: {p}", file=sys.stderr)
                regions.extend(found)
            else:
                print(f"⚠️  Not found or not a directory: {raw}", file=sys.stderr)
        regions = sorted(set(regions), key=lambda x: str(x))
    else:
        crz = repo_root / "data" / "crz"
        if not crz.is_dir():
            print(f"Not found: {crz}", file=sys.stderr)
            return 1
        regions = sorted({p.parent for p in crz.rglob("legend.csv")}, key=lambda x: str(x))

    if not regions:
        print("No legend.csv to sync.", file=sys.stderr)
        return 1

    total_updates = 0
    for region_dir in regions:
        n, logs = sync_region(region_dir)
        total_updates += n
        try:
            rel = region_dir.relative_to(repo_root)
            label = str(rel)
        except ValueError:
            label = str(region_dir)
        print(f"\n{label}: updated {n} legend row(s)")
        for line in logs:
            print(line)

    print(f"\nDone. Total legend rows touched: {total_updates}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
