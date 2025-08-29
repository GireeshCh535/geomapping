import json
from pathlib import Path

# Load the GeoJSON file
geojson_path = Path("data/karnataka/bengaluru/metro/Bangalore Metro Phases 1,2,2A&2B.geojson")

with open(geojson_path, 'r') as f:
    data = json.load(f)

print("=== BANGALORE METRO DATA ANALYSIS ===\n")

print(f"Total features: {len(data['features'])}")
print(f"CRS: {data['crs']}")
print(f"Name: {data['name']}")

print("\n=== FEATURE DETAILS ===")
for idx, feature in enumerate(data['features']):
    props = feature['properties']
    geom = feature['geometry']
    
    print(f"\nFeature {idx + 1}:")
    print(f"  FID: {props.get('fid', 'N/A')}")
    print(f"  Object ID: {props.get('objectid', 'N/A')}")
    print(f"  Line Color: {props.get('linecolour', 'N/A')}")
    print(f"  From Junction: {props.get('fromjunction', 'N/A')}")
    print(f"  To Junction: {props.get('tojunction', 'N/A')}")
    print(f"  Number of Stations: {props.get('noofstations', 'N/A')}")
    print(f"  Length (km): {props.get('length', 'N/A')}")
    print(f"  Remarks: {props.get('remarks', 'N/A')}")
    print(f"  Name: {props.get('Name ', 'N/A')}")
    print(f"  Geometry Type: {geom['type']}")

print("\n=== COLOR MAPPING ===")
color_mapping = {}
for feature in data['features']:
    color = feature['properties'].get('linecolour', 'Unknown')
    name = feature['properties'].get('Name ', 'Unknown')
    if color not in color_mapping:
        color_mapping[color] = []
    color_mapping[color].append(name)

for color, names in color_mapping.items():
    print(f"{color}: {', '.join(names)}")

print("\n=== PHASE SUMMARY ===")
phase_summary = {}
for feature in data['features']:
    props = feature['properties']
    phase = props.get('Name ', 'Unknown')
    color = props.get('linecolour', 'Unknown')
    length = props.get('length', 0)
    stations = props.get('noofstations', 0)
    status = props.get('remarks', 'Unknown')
    
    if phase not in phase_summary:
        phase_summary[phase] = {
            'color': color,
            'total_length': 0,
            'total_stations': 0,
            'status': status
        }
    
    phase_summary[phase]['total_length'] += length
    phase_summary[phase]['total_stations'] += stations

for phase, details in phase_summary.items():
    print(f"{phase}:")
    print(f"  Color: {details['color']}")
    print(f"  Total Length: {details['total_length']:.2f} km")
    print(f"  Total Stations: {details['total_stations']}")
    print(f"  Status: {details['status']}")

print("\n=== COORDINATE BOUNDS ===")
all_coords = []
for feature in data['features']:
    coords = feature['geometry']['coordinates']
    for line in coords:
        all_coords.extend(line)

lons = [coord[0] for coord in all_coords]
lats = [coord[1] for coord in all_coords]

print(f"Min Longitude: {min(lons):.6f}")
print(f"Min Latitude: {min(lats):.6f}")
print(f"Max Longitude: {max(lons):.6f}")
print(f"Max Latitude: {max(lats):.6f}")
