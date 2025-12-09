# Heritage Sites Tile Generation

This directory contains tools for generating map tiles for heritage sites with protected, prohibited, and regulated zones.

## Overview

Each heritage site GeoJSON file contains three types of boundary zones:
- **Protected** (Red `#E52323`): No construction or renovation allowed
- **Prohibited** (Yellow `#FFFF2B`): NMA (National Monuments Authority) NOC required
- **Regulated** (Green `#36FF36`): State government NOC required

## Heritage Sites Included

### Bengaluru (7 sites)
1. Bengaluru Fort
2. Bhoga Nandishwara Temple (Kolar)
3. Devanahalli Fort
4. Kolaramma Temple (Kolar)
5. Someswara Temple (Kolar)
6. Tippu Sultan's Birth Palace
7. Tippu Sultan's Palace

### Hyderabad (3 sites)
1. Ancient Mound
2. Charminar
3. Golconda Fort

## Directory Structure

```
heritage_sites/
├── bengaluru/
│   ├── Bengaluru Fort.geojson
│   ├── Bengaluru Fort_legend.csv
│   ├── ... (other sites)
└── hyderabad/
    ├── charminar.geojson
    ├── charminar_legend.csv
    └── ... (other sites)

heritage_tiles/                    # Generated tiles (output)
├── bengaluru_fort/
│   ├── 7/, 8/, ..., 18/          # Zoom levels
│   └── index.html                 # Tile viewer
└── ... (other sites)
```

## Usage

### 1. Generate All Heritage Site Tiles

```bash
# Generate tiles for all 10 heritage sites
bash generate_all_heritage_tiles.sh
```

### 2. Generate Individual Site Tiles

```bash
python3 scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru/Bengaluru Fort.geojson" \
  "heritage_tiles/bengaluru_fort" \
  "Bengaluru Fort"
```

**Parameters:**
- `<geojson_file>`: Path to heritage site GeoJSON file
- `<output_dir>`: Output directory for tiles
- `<site_name>`: Display name for the site

### 3. Insert into Database

```bash
# Insert all heritage sites
bash heritage_insert_commands.sh

# Or insert individual site
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Bengaluru Fort (Heritage Zones)" \
  --layer-slug "bengaluru_fort_heritage" \
  --data-dir "heritage_sites/bengaluru" \
  --authority "Archaeological Survey of India" \
  --min-zoom 7 \
  --max-zoom 18 \
  --delete-existing
```

### 4. Sync to S3

```bash
# Sync all heritage site tiles to S3
bash heritage_s3_sync_commands.sh

# Or sync individual site
aws s3 sync heritage_tiles/bengaluru_fort \
  s3://gis-portal-layers/karnataka/bengaluru/heritage/bengaluru_fort/ \
  --delete
```

## Legend CSV Format

Each heritage site has a `legend.csv` file with standardized zone colors:

```csv
category,fill_color,outline_color,pattern,pattern_color
Protected,#E52323,#E52323,,
Prohibited,#FFFF2B,#FFFF2B,,
Regulated,#36FF36,#36FF36,,
```

## Tile Generation Features

✅ **Seamless rendering** - No visible tile boundaries
✅ **Polygon holes support** - Correctly handles interior rings
✅ **70% opacity** - Semi-transparent zones for base map visibility
✅ **CRS auto-detection** - Handles both WGS84 and Web Mercator
✅ **4x supersampling** - Fixed scale for crisp, consistent edges
✅ **Alpha compositing** - Professional-quality rendering
✅ **Optimized performance** - Spatial indexing and caching
✅ **Identical to monuments** - Same rendering engine as monument tiles

## Zoom Levels

- **Min Zoom**: 9 (City view)
- **Max Zoom**: 18 (Building-level detail)

## Viewing Tiles Locally

After generating tiles:

```bash
cd heritage_tiles/bengaluru_fort
python3 -m http.server 8000
```

Then open http://localhost:8000/ in your browser.

## Color Extraction

Colors are automatically extracted from the GeoJSON `properties.fill` and `properties.stroke` fields. The generator falls back to standard zone colors if not specified in the GeoJSON.

## Notes

- All heritage sites use the same 3-zone color scheme (Protected/Prohibited/Regulated)
- Tiles are generated with 70% opacity for better base map integration
- The universal generator handles all heritage sites consistently
- Legend CSV files are automatically created for each site

