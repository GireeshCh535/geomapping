#!/usr/bin/env python3
"""
Create City Config
==================

Helper script to generate a configuration JSON for a new city.
Scans a data directory for GeoJSON files and matches them with a legend CSV.
"""

import os
import json
import argparse
import csv
from pathlib import Path
from difflib import get_close_matches

def load_legend(legend_path):
    """Load legend zones and styles from CSV."""
    styles = {}
    zones = []
    with open(legend_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            zone = row['Zone']
            zones.append(zone)
            style = {
                "fill_color": row['Color'],
                "hatch": row.get('Hatch', '').strip(),
                "hatch_color": row.get('HatchColor', '').strip()
            }
            styles[zone] = style
    return zones, styles

def create_filename_mapping(data_dir, zones):
    """Map filenames to legend zones using fuzzy matching."""
    mapping = {}
    geojson_files = list(Path(data_dir).glob("*.geojson"))
    
    print(f"\nScanning {len(geojson_files)} files in {data_dir}...")
    
    for file_path in geojson_files:
        filename = file_path.stem
        
        # 1. Exact match
        if filename in zones:
            mapping[filename] = filename
            continue
            
        # 2. Normalized match (replace underscores with spaces)
        normalized_name = filename.replace('_', ' ')
        if normalized_name in zones:
            mapping[filename] = normalized_name
            continue
            
        # 3. Fuzzy match
        matches = get_close_matches(normalized_name, zones, n=1, cutoff=0.6)
        if matches:
            mapping[filename] = matches[0]
            print(f"  Mapped '{filename}' -> '{matches[0]}'")
        else:
            print(f"  WARNING: Could not map file '{filename}' to any zone in legend.")
            mapping[filename] = "Not Known"
            
    return mapping

def main():
    parser = argparse.ArgumentParser(description='Create a config file for a new city.')
    parser.add_argument('--name', type=str, required=True, help='Name of the city/master plan')
    parser.add_argument('--data', type=str, required=True, help='Path to data directory containing GeoJSONs')
    parser.add_argument('--legend', type=str, required=True, help='Path to legend CSV (Zone,Color)')
    parser.add_argument('--output', type=str, required=True, help='Path to save the config JSON')
    parser.add_argument('--tiles-out', type=str, required=True, help='Directory where tiles will be generated')
    
    args = parser.parse_args()
    
    # Validate paths
    if not os.path.exists(args.data):
        print(f"Error: Data directory not found: {args.data}")
        return
    if not os.path.exists(args.legend):
        print(f"Error: Legend file not found: {args.legend}")
        return
        
    # Load legend
    zones, styles = load_legend(args.legend)
    
    # Create mapping
    mapping = create_filename_mapping(args.data, zones)
    
    # Create default rendering priority
    # Default: Water/Roads at bottom, Residential/Commercial on top
    priority = {zone: 5 for zone in zones}
    if "Water Body" in priority: priority["Water Body"] = 1
    if "Road" in priority: priority["Road"] = 2
    if "Green" in priority: priority["Green"] = 3
    
    # Build config
    config = {
        "city_name": args.name,
        "data_dir": os.path.abspath(args.data),
        "output_dir": os.path.abspath(args.tiles_out),
        "zoom_range": [10, 18],
        "tile_size": 256,
        "supersample_factor": 4,
        "legend_path": os.path.abspath(args.legend),
        "styles": styles,
        "filename_mapping": mapping,
        "rendering_priority": priority
    }
    
    # Save config
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(config, f, indent=4)
        
    print(f"\nSuccess! Config saved to: {args.output}")
    print(f"You can now run: python generic_tile_generator.py --config \"{args.output}\"")

if __name__ == "__main__":
    main()
