# Amaravati Master Plan Data Insertion

This directory contains scripts to insert Amaravati master plan data into the database models.

## Files

1. **`insert_amaravati_data.py`** - Standalone Python script
2. **`../maps/management/commands/insert_amaravati_data.py`** - Django management command

## Data Structure

The scripts process 40 GeoJSON files from `data/andhra_pradesh/amaravati/master_plan/`:

### Zone Categories
- **Commercial**: C1-C6 zones, Commercial_Vacant
- **Industrial**: I1-I3 zones  
- **Residential**: R1, R3, R4, RAA, Residential_Vacant, SR2, SR4
- **Mixed Use**: SC1a, SC1b
- **Parks & Green**: P1, P2, PGN_G, PGN_V, SP1, SP2
- **Protected**: P3, P3_Hills, SP3
- **Government**: SS1
- **Education**: S2, SS2a
- **Health**: SS2c
- **Cultural**: SS2b
- **Transport**: SU2, U2
- **Burial**: Burial_Ground
- **Unclassified**: S3, SS3, SU1, U1

### Color Mapping
Each zone has specific colors and patterns:
- **R1_Village_planning_zone**: White background with black hatches
- **Burial_Ground**: White background with orange dots
- **All other zones**: Solid colors as per master plan specifications

## Usage

### Option 1: Django Management Command (Recommended)

```bash
# Delete existing data and insert fresh data
python manage.py insert_amaravati_data --delete-existing

# Insert data without deleting existing
python manage.py insert_amaravati_data

# Skip creating styles (if you want to create them separately)
python manage.py insert_amaravati_data --skip-styles
```

### Option 2: Standalone Script

```bash
# Make sure you're in the project root directory
cd /path/to/geomapping

# Run the script
python scripts/insert_amaravati_data.py
```

## What the Script Does

1. **Creates/Updates**:
   - State: Andhra Pradesh
   - City: Amaravati
   - Layer Categories (13 categories)
   - Layer Group: "Amaravati Master Plan"

2. **Deletes Existing Data** (if `--delete-existing` is used):
   - All GeoFeatures for Amaravati
   - All DataLayers for Amaravati
   - All CityLayerStyles for Amaravati
   - All CityZoneMappings for Amaravati

3. **Creates New Data**:
   - 40 DataLayers (one for each GeoJSON file)
   - CityLayerStyles with proper colors and patterns
   - GeoFeatures from all GeoJSON files
   - Calculates bounding boxes for all layers

## Database Models Used

- **State**: Andhra Pradesh state information
- **City**: Amaravati city information  
- **LayerCategory**: Zone categories (Residential, Commercial, etc.)
- **LayerGroup**: Groups all master plan layers together
- **DataLayer**: Individual zone layers (C1, R1, etc.)
- **GeoFeature**: Individual polygons from GeoJSON files
- **CityLayerStyle**: Colors and patterns for each zone type

## Expected Results

After running the script, you should have:
- 1 State record
- 1 City record
- 13 LayerCategory records
- 1 LayerGroup record
- 40 DataLayer records
- ~10,000+ GeoFeature records (varies by zone)
- 13 CityLayerStyle records

## Troubleshooting

### Common Issues

1. **"Data directory not found"**
   - Make sure you're running from the project root
   - Check that `data/andhra_pradesh/amaravati/master_plan/` exists

2. **"Category not found"**
   - The script creates categories automatically
   - If this error persists, check the zone_category_mapping

3. **"Geometry error"**
   - Some GeoJSON files might have invalid geometries
   - The script will skip invalid features and continue

4. **"Permission denied"**
   - Make sure the database user has INSERT/UPDATE/DELETE permissions
   - Check Django database settings

### Verification

After running the script, verify the data:

```python
# In Django shell
from maps.models import *

# Check counts
print(f"States: {State.objects.count()}")
print(f"Cities: {City.objects.count()}")
print(f"Layers: {DataLayer.objects.filter(city__slug='amaravati').count()}")
print(f"Features: {GeoFeature.objects.filter(layer__city__slug='amaravati').count()}")

# Check a specific layer
layer = DataLayer.objects.filter(city__slug='amaravati').first()
print(f"Layer: {layer.name}, Features: {layer.feature_count}")
```

## Notes

- The script uses database transactions, so if it fails, no partial data will be saved
- All coordinates are stored in WGS84 (EPSG:4326)
- The script preserves all original properties from GeoJSON files
- Pattern rendering (hatches, dots) is configured in the CityLayerStyle model
