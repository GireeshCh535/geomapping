#!/usr/bin/env python3
"""Verify all air funnel scripts match the specifications"""

from pathlib import Path
import re

# Expected color mappings from user
EXPECTED = {
    "Calicut.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '144 Meters Above Mean Sea Level': '#559B33',
        '164 Meters Above Mean Sea Level': '#8B36A4',
        '184 Meters Above Mean Sea Level': '#CF9D2C',
        '204 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Warangal.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '313 Meters Above Mean Sea Level': '#559B33',
        '323 Meters Above Mean Sea Level': '#8B36A4',
        '333 Meters Above Mean Sea Level': '#CF9D2C',
        '343 Meters Above Mean Sea Level': '#3A6A99',
        '373 Meters Above Mean Sea Level': '#BFC040',
        '403 Meters Above Mean Sea Level': '#AA8F9D',
        '433 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Delhi-IGI.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '245 Meters Above Mean Sea Level': '#559B33',
        '255 Meters Above Mean Sea Level': '#7EBC4F',
        '265 Meters Above Mean Sea Level': '#8B36A4',
        '285 Meters Above Mean Sea Level': '#C157D9',
        '295 Meters Above Mean Sea Level': '#CF9D2C',
        '315 Meters Above Mean Sea Level': '#F2B02C',
        '325 Meters Above Mean Sea Level': '#3A6A99',
        '345 Meters Above Mean Sea Level': '#5F84B1',
        '355 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Noida(Jewar).geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '214 Meters Above Mean Sea Level': '#559B33',
        '219 Meters Above Mean Sea Level': '#7EBC4F',
        '229 Meters Above Mean Sea Level': '#8B36A4',
        '239 Meters Above Mean Sea Level': '#C157D9',
        '249 Meters Above Mean Sea Level': '#CF9D2C',
        '279 Meters Above Mean Sea Level': '#3A6A99',
        '309 Meters Above Mean Sea Level': '#BFC040',
        '339 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Jaipur.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '396 Meters Above Mean Sea Level': '#559B33',
        '401 Meters Above Mean Sea Level': '#8B36A4',
        '406 Meters Above Mean Sea Level': '#C157D9',
        '416 Meters Above Mean Sea Level': '#CF9D2C',
        '466 Meters Above Mean Sea Level': '#3A6A99',
        '496 Meters Above Mean Sea Level': '#BFC040',
        '526 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Ahmedabad - Gandhinagar.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '77 Meters Above Mean Sea Level': '#559B33',
        '95 Meters Above Mean Sea Level': '#8B36A4',
        '115 Meters Above Mean Sea Level': '#CF9D2C',
        '135 Meters Above Mean Sea Level': '#3A6A99',
        '155 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Dohlera.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '32 Meters Above Mean Sea Level': '#559B33',
        '42 Meters Above Mean Sea Level': '#8B36A4',
        '72 Meters Above Mean Sea Level': '#CF9D2C',
        '102 Meters Above Mean Sea Level': '#3A6A99',
        '152 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Tirupati.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '137 Meters Above Mean Sea Level': '#559B33',
        '147 Meters Above Mean Sea Level': '#8B36A4',
        '157 Meters Above Mean Sea Level': '#CF9D2C',
        '187 Meters Above Mean Sea Level': '#3A6A99',
        '217 Meters Above Mean Sea Level': '#BFC040',
        '247 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Bhubaneswar.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '53 Meters Above Mean Sea Level': '#559B33',
        '63 Meters Above Mean Sea Level': '#8B36A4',
        '183 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Lucknow.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '140 Meters Above Mean Sea Level': '#559B33',
        '160 Meters Above Mean Sea Level': '#8B36A4',
        '180 Meters Above Mean Sea Level': '#CF9D2C',
        '200 Meters Above Mean Sea Level': '#3A6A99',
        '220 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Ayodhya .geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '110 Meters Above Mean Sea Level': '#559B33',
        '120 Meters Above Mean Sea Level': '#7EBC4F',
        '130 Meters Above Mean Sea Level': '#8B36A4',
        '240 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Chennai.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '26 Meters Above Mean Sea Level': '#559B33',
        '31 Meters Above Mean Sea Level': '#7EBC4F',
        '36 Meters Above Mean Sea Level': '#8B36A4',
        '46 Meters Above Mean Sea Level': '#C157D9',
        '56 Meters Above Mean Sea Level': '#CF9D2C',
        '66 Meters Above Mean Sea Level': '#F2B02C',
        '96 Meters Above Mean Sea Level': '#3A6A99',
        '126 Meters Above Mean Sea Level': '#BFC040',
        '156 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Kochi.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '19 Meters Above Mean Sea Level': '#559B33',
        '29 Meters Above Mean Sea Level': '#8B36A4',
        '39 Meters Above Mean Sea Level': '#CF9D2C',
        '49 Meters Above Mean Sea Level': '#3A6A99',
        '119 Meters Above Mean Sea Level': '#AA8F9D',
        '149 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Raipur.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '327 Meters Above Mean Sea Level': '#559B33',
        '332 Meters Above Mean Sea Level': '#8B36A4',
        '337 Meters Above Mean Sea Level': '#C157D9',
        '342 Meters Above Mean Sea Level': '#CF9D2C',
        '347 Meters Above Mean Sea Level': '#F2B02C',
        '352 Meters Above Mean Sea Level': '#3A6A99',
        '357 Meters Above Mean Sea Level': '#5F84B1',
        '367 Meters Above Mean Sea Level': '#BFC040',
        '397 Meters Above Mean Sea Level': '#DED92E',
        '427 Meters Above Mean Sea Level': '#AA8F9D',
        '457 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Raigarh.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '265 Meters Above Mean Sea Level': '#559B33',
        '385 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Patna.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '53 Meters Above Mean Sea Level': '#559B33',
        '73 Meters Above Mean Sea Level': '#8B36A4',
        '83 Meters Above Mean Sea Level': '#CF9D2C',
        '193 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Guwahati.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '64 Meters Above Mean Sea Level': '#559B33',
        '69 Meters Above Mean Sea Level': '#7EBC4F',
        '79 Meters Above Mean Sea Level': '#8B36A4',
        '159 Meters Above Mean Sea Level': '#CF9D2C',
        '189 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Diu.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '39 Meters Above Mean Sea Level': '#559B33',
        '49 Meters Above Mean Sea Level': '#8B36A4',
        '59 Meters Above Mean Sea Level': '#CF9D2C',
        '89 Meters Above Mean Sea Level': '#3A6A99',
        '119 Meters Above Mean Sea Level': '#BFC040',
        '149 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Nagpur.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '335 Meters Above Mean Sea Level': '#559B33',
        '345 Meters Above Mean Sea Level': '#8B36A4',
        '355 Meters Above Mean Sea Level': '#CF9D2C',
        '375 Meters Above Mean Sea Level': '#3A6A99',
        '395 Meters Above Mean Sea Level': '#BFC040',
        '415 Meters Above Mean Sea Level': '#A0A0A0',
    },
    "Navi_Mumbai.geojson": {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '22 Meters Above Mean Sea Level': '#559B33',
        '30 Meters Above Mean Sea Level': '#8B36A4',
        '40 Meters Above Mean Sea Level': '#CF9D2C',
        '60 Meters Above Mean Sea Level': '#3A6A99',
        '90 Meters Above Mean Sea Level': '#BFC040',
        '120 Meters Above Mean Sea Level': '#AA8F9D',
        '150 Meters Above Mean Sea Level': '#A0A0A0',
    },
}

# File mapping
FILE_MAPPING = {
    "Calicut.geojson": "calicut_air_funnel_tiles.py",
    "Warangal.geojson": "warangal_air_funnel_tiles.py",
    "Delhi-IGI.geojson": "delhi_igi_air_funnel_tiles.py",
    "Noida(Jewar).geojson": "noida_jewar_air_funnel_tiles.py",
    "Jaipur.geojson": "jaipur_air_funnel_tiles.py",
    "Ahmedabad - Gandhinagar.geojson": "ahmedabad_gandhinagar_air_funnel_tiles.py",
    "Dohlera.geojson": "dohlera_air_funnel_tiles.py",
    "Tirupati.geojson": "tirupati_air_funnel_tiles.py",
    "Bhubaneswar.geojson": "bhubaneswar_air_funnel_tiles.py",
    "Lucknow.geojson": "lucknow_air_funnel_tiles.py",
    "Ayodhya .geojson": "ayodhya_air_funnel_tiles.py",
    "Chennai.geojson": "chennai_air_funnel_tiles.py",
    "Kochi.geojson": "kochi_air_funnel_tiles.py",
    "Raipur.geojson": "raipur_air_funnel_tiles.py",
    "Raigarh.geojson": "raigarh_air_funnel_tiles.py",
    "Patna.geojson": "patna_air_funnel_tiles.py",
    "Guwahati.geojson": "guwahati_air_funnel_tiles.py",
    "Diu.geojson": "diu_air_funnel_tiles.py",
    "Nagpur.geojson": "nagpur_air_funnel_tiles.py",
    "Navi_Mumbai.geojson": "navi_mumbai_air_funnel_tiles.py",
}

def extract_color_map(file_content):
    """Extract color map from script file"""
    # Find the get_color_map function and extract the return block
    # Match from "def get_color_map" to the closing brace of return statement
    pattern = r"def get_color_map\(self\):.*?return \{"
    start_match = re.search(pattern, file_content, re.DOTALL)
    if not start_match:
        return None
    
    start_pos = start_match.end()
    # Now find matching closing brace by counting braces
    brace_count = 1
    pos = start_pos
    while pos < len(file_content) and brace_count > 0:
        if file_content[pos] == '{':
            brace_count += 1
        elif file_content[pos] == '}':
            brace_count -= 1
        pos += 1
    
    if brace_count != 0:
        return None
    
    content = file_content[start_pos:pos-1]  # -1 to exclude the closing brace
    
    color_map = {}
    # Match all zone entries: 'zone': {'fill': '#color', ...}
    zone_pattern = r"'([^']+)':\s*\{'fill':\s*'([^']+)'"
    for zone_match in re.finditer(zone_pattern, content):
        zone = zone_match.group(1)
        color = zone_match.group(2)
        color_map[zone] = color
    
    return color_map

script_dir = Path(__file__).resolve().parent
errors = []
all_correct = True

print("=" * 80)
print("VERIFICATION REPORT: Air Funnel Tile Scripts")
print("=" * 80)
print()

for geojson_file, expected_colors in EXPECTED.items():
    script_file = FILE_MAPPING.get(geojson_file)
    if not script_file:
        print(f"❌ ERROR: No script file mapping for {geojson_file}")
        errors.append(f"No mapping for {geojson_file}")
        all_correct = False
        continue
    
    script_path = script_dir / script_file
    if not script_path.exists():
        print(f"❌ ERROR: Script file not found: {script_file}")
        errors.append(f"File not found: {script_file}")
        all_correct = False
        continue
    
    content = script_path.read_text()
    actual_colors = extract_color_map(content)
    
    if not actual_colors:
        print(f"❌ ERROR: Could not extract color map from {script_file}")
        errors.append(f"Could not extract color map from {script_file}")
        all_correct = False
        continue
    
    # Compare
    missing = set(expected_colors.keys()) - set(actual_colors.keys())
    extra = set(actual_colors.keys()) - set(expected_colors.keys())
    wrong_colors = []
    
    for zone, expected_color in expected_colors.items():
        if zone in actual_colors:
            if actual_colors[zone].upper() != expected_color.upper():
                wrong_colors.append((zone, expected_color, actual_colors[zone]))
    
    if missing or extra or wrong_colors:
        print(f"❌ {geojson_file} -> {script_file}")
        if missing:
            print(f"   Missing zones: {missing}")
        if extra:
            print(f"   Extra zones: {extra}")
        if wrong_colors:
            for zone, expected, actual in wrong_colors:
                print(f"   Wrong color for '{zone}': expected {expected}, got {actual}")
        errors.append((geojson_file, missing, extra, wrong_colors))
        all_correct = False
    else:
        print(f"✅ {geojson_file} -> {script_file} ({len(expected_colors)} zones)")

print()
print("=" * 80)
if all_correct:
    print("✅ ALL FILES ARE CORRECT!")
else:
    print(f"❌ FOUND {len(errors)} FILE(S) WITH ERRORS")
    print()
    print("Errors:")
    for error in errors:
        print(f"  - {error}")
print("=" * 80)

