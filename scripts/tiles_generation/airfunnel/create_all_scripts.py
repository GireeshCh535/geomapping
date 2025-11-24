#!/usr/bin/env python3
"""Generate all air funnel tile scripts"""

from pathlib import Path
import re

# City configurations
CITIES = [
    ("Delhi-IGI.geojson", "Delhi-IGI", "DelhiIGI", "delhi_igi", 8008, {
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
    }),
    ("Noida(Jewar).geojson", "Noida-Jewar", "NoidaJewar", "noida_jewar", 8009, {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '214 Meters Above Mean Sea Level': '#559B33',
        '219 Meters Above Mean Sea Level': '#7EBC4F',
        '229 Meters Above Mean Sea Level': '#8B36A4',
        '239 Meters Above Mean Sea Level': '#C157D9',
        '249 Meters Above Mean Sea Level': '#CF9D2C',
        '279 Meters Above Mean Sea Level': '#3A6A99',
        '309 Meters Above Mean Sea Level': '#BFC040',
        '339 Meters Above Mean Sea Level': '#A0A0A0',
    }),
    ("Jaipur.geojson", "Jaipur", "Jaipur", "jaipur", 8010, {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '396 Meters Above Mean Sea Level': '#559B33',
        '401 Meters Above Mean Sea Level': '#8B36A4',
        '406 Meters Above Mean Sea Level': '#C157D9',
        '416 Meters Above Mean Sea Level': '#CF9D2C',
        '466 Meters Above Mean Sea Level': '#3A6A99',
        '496 Meters Above Mean Sea Level': '#BFC040',
        '526 Meters Above Mean Sea Level': '#A0A0A0',
    }),
    ("Ahmedabad - Gandhinagar.geojson", "Ahmedabad-Gandhinagar", "AhmedabadGandhinagar", "ahmedabad_gandhinagar", 8011, {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '77 Meters Above Mean Sea Level': '#559B33',
        '95 Meters Above Mean Sea Level': '#8B36A4',
        '115 Meters Above Mean Sea Level': '#CF9D2C',
        '135 Meters Above Mean Sea Level': '#3A6A99',
        '155 Meters Above Mean Sea Level': '#A0A0A0',
    }),
    ("Dohlera.geojson", "Dohlera", "Dohlera", "dohlera", 8012, {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '32 Meters Above Mean Sea Level': '#559B33',
        '42 Meters Above Mean Sea Level': '#8B36A4',
        '72 Meters Above Mean Sea Level': '#CF9D2C',
        '102 Meters Above Mean Sea Level': '#3A6A99',
        '152 Meters Above Mean Sea Level': '#A0A0A0',
    }),
    ("Tirupati.geojson", "Tirupati", "Tirupati", "tirupati", 8013, {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '137 Meters Above Mean Sea Level': '#559B33',
        '147 Meters Above Mean Sea Level': '#8B36A4',
        '157 Meters Above Mean Sea Level': '#CF9D2C',
        '187 Meters Above Mean Sea Level': '#3A6A99',
        '217 Meters Above Mean Sea Level': '#BFC040',
        '247 Meters Above Mean Sea Level': '#A0A0A0',
    }),
    ("Bhubaneswar.geojson", "Bhubaneswar", "Bhubaneswar", "bhubaneswar", 8014, {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '53 Meters Above Mean Sea Level': '#559B33',
        '63 Meters Above Mean Sea Level': '#8B36A4',
        '183 Meters Above Mean Sea Level': '#A0A0A0',
    }),
    ("Lucknow.geojson", "Lucknow", "Lucknow", "lucknow", 8015, {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '140 Meters Above Mean Sea Level': '#559B33',
        '160 Meters Above Mean Sea Level': '#8B36A4',
        '180 Meters Above Mean Sea Level': '#CF9D2C',
        '200 Meters Above Mean Sea Level': '#3A6A99',
        '220 Meters Above Mean Sea Level': '#A0A0A0',
    }),
    ("Ayodhya .geojson", "Ayodhya", "Ayodhya", "ayodhya", 8016, {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '110 Meters Above Mean Sea Level': '#559B33',
        '120 Meters Above Mean Sea Level': '#7EBC4F',
        '130 Meters Above Mean Sea Level': '#8B36A4',
        '240 Meters Above Mean Sea Level': '#A0A0A0',
    }),
    ("Chennai.geojson", "Chennai", "Chennai", "chennai", 8017, {
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
    }),
    ("Kochi.geojson", "Kochi", "Kochi", "kochi", 8018, {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '19 Meters Above Mean Sea Level': '#559B33',
        '29 Meters Above Mean Sea Level': '#8B36A4',
        '39 Meters Above Mean Sea Level': '#CF9D2C',
        '49 Meters Above Mean Sea Level': '#3A6A99',
        '119 Meters Above Mean Sea Level': '#AA8F9D',
        '149 Meters Above Mean Sea Level': '#A0A0A0',
    }),
    ("Raipur.geojson", "Raipur", "Raipur", "raipur", 8019, {
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
    }),
    ("Raigarh.geojson", "Raigarh", "Raigarh", "raigarh", 8020, {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '265 Meters Above Mean Sea Level': '#559B33',
        '385 Meters Above Mean Sea Level': '#A0A0A0',
    }),
    ("Patna.geojson", "Patna", "Patna", "patna", 8021, {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '53 Meters Above Mean Sea Level': '#559B33',
        '73 Meters Above Mean Sea Level': '#8B36A4',
        '83 Meters Above Mean Sea Level': '#CF9D2C',
        '193 Meters Above Mean Sea Level': '#A0A0A0',
    }),
    ("Guwahati.geojson", "Guwahati", "Guwahati", "guwahati", 8022, {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '64 Meters Above Mean Sea Level': '#559B33',
        '69 Meters Above Mean Sea Level': '#7EBC4F',
        '79 Meters Above Mean Sea Level': '#8B36A4',
        '159 Meters Above Mean Sea Level': '#CF9D2C',
        '189 Meters Above Mean Sea Level': '#A0A0A0',
    }),
    ("Diu.geojson", "Diu", "Diu", "diu", 8023, {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '39 Meters Above Mean Sea Level': '#559B33',
        '49 Meters Above Mean Sea Level': '#8B36A4',
        '59 Meters Above Mean Sea Level': '#CF9D2C',
        '89 Meters Above Mean Sea Level': '#3A6A99',
        '119 Meters Above Mean Sea Level': '#BFC040',
        '149 Meters Above Mean Sea Level': '#A0A0A0',
    }),
    ("Nagpur.geojson", "Nagpur", "Nagpur", "nagpur", 8024, {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '335 Meters Above Mean Sea Level': '#559B33',
        '345 Meters Above Mean Sea Level': '#8B36A4',
        '355 Meters Above Mean Sea Level': '#CF9D2C',
        '375 Meters Above Mean Sea Level': '#3A6A99',
        '395 Meters Above Mean Sea Level': '#BFC040',
        '415 Meters Above Mean Sea Level': '#A0A0A0',
    }),
    ("Navi_Mumbai.geojson", "Navi-Mumbai", "NaviMumbai", "navi_mumbai", 8025, {
        'For construction mandatory NOC from AAI is required': '#91302D',
        '22 Meters Above Mean Sea Level': '#559B33',
        '30 Meters Above Mean Sea Level': '#8B36A4',
        '40 Meters Above Mean Sea Level': '#CF9D2C',
        '60 Meters Above Mean Sea Level': '#3A6A99',
        '90 Meters Above Mean Sea Level': '#BFC040',
        '120 Meters Above Mean Sea Level': '#AA8F9D',
        '150 Meters Above Mean Sea Level': '#A0A0A0',
    }),
]

def get_outline(fill):
    h = fill.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f'#{int(r*0.8):02x}{int(g*0.8):02x}{int(b*0.8):02x}'

script_dir = Path(__file__).resolve().parent
template = (script_dir / "calicut_air_funnel_tiles.py").read_text()

for filename, city_name, class_name, output_dir, port, colors in CITIES:
    script = template
    
    # Replace city names
    script = script.replace('Calicut', city_name)
    script = script.replace('calicut', output_dir)
    script = script.replace('CalicutAirFunnelTileGenerator', f'{class_name}AirFunnelTileGenerator')
    script = script.replace('8006', str(port))
    script = script.replace('Calicut.geojson', filename)
    
    # Replace color map
    color_lines = []
    for zone, fill in colors.items():
        outline = get_outline(fill)
        color_lines.append(f"            '{zone}': {{'fill': '{fill}', 'outline': '{outline}'}},")
    color_map_str = '\n'.join(color_lines)
    
    # Find color map section and replace - match the entire return block
    pattern = r"(    def get_color_map\(self\):.*?return \{)(.*?)(        \})"
    script = re.sub(pattern, r'\1' + '\n' + color_map_str + r'\n        }', script, flags=re.DOTALL)
    
    # Generate legend items for HTML
    legend_items = []
    for zone, fill in colors.items():
        label = 'NOC Required' if 'NOC' in zone else zone.replace(' Meters Above Mean Sea Level', 'm')
        legend_items.append(f'    <div class="legend-item">\n      <div class="legend-color" style="background-color: {fill};"></div>\n      <span style="font-size: 10px;">{label}</span>\n    </div>')
    legend_str = '\n'.join(legend_items)
    
    # Replace legend in HTML
    script = script.replace('{chr(10).join(legend_items)}', legend_str)
    
    output_file = script_dir / f"{output_dir}_air_funnel_tiles.py"
    output_file.write_text(script)
    print(f"Generated: {output_file.name}")

print(f"\nGenerated {len(CITIES)} scripts successfully!")

