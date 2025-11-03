#!/usr/bin/env python3
"""
Quick test to verify polygon holes are rendering correctly
"""
import sys
sys.path.insert(0, 'scripts/tiles_generation/telangana')

from warangal_masterplan_tile_generator import WarangalSeamlessTiles
from pathlib import Path

data_dir = Path('data/Telangana/warangal/master_plan')
output_dir = Path('./warangal_test_holes')

print("="*80)
print("TESTING POLYGON HOLES FIX")
print("Generating just zoom 12-13 for quick verification")
print("="*80)

generator = WarangalSeamlessTiles(data_dir, output_dir)
generator.load_geojson_files()

if generator.feature_id_counter == 0:
    print("✗ No features loaded!")
    sys.exit(1)

# Generate just zoom 12-13 for quick test
generator.generate_tiles(min_zoom=14, max_zoom=18)
generator.generate_html_viewer()

print(f"\n💡 To view: cd {output_dir} && python3 -m http.server 8012")
print(f"   Then open: http://localhost:8012/\n")
print("✅ Check if the gray Road Buffer areas now have holes/transparency!\n")

