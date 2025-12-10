# Heritage Sites - Complete Command Reference

## Quick Start (All Sites)

### 1️⃣ Generate All Tiles
```bash
bash generate_all_heritage_tiles.sh
```

### 2️⃣ Insert All into Database
```bash
bash heritage_insert_commands.sh
```

### 3️⃣ Sync All to S3
```bash
bash heritage_s3_sync_commands.sh
```

---

## Individual Site Commands

### Bengaluru Fort

**Generate Tiles:**
```bash
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru/Bengaluru Fort.geojson" \
  "heritage_tiles/bengaluru_fort" \
  "Bengaluru Fort"
```

**Insert into DB:**
```bash
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

**Sync to S3:**
```bash
aws s3 sync heritage_tiles/bengaluru_fort \
  s3://gis-portal-layers/karnataka/bengaluru/heritage/bengaluru_fort/ --delete
```

---

### Bhoga Nandishwara Temple

**Generate Tiles:**
```bash
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru/Bhoga Nandishwara Temple (Kolar).geojson" \
  "heritage_tiles/bhoga_nandishwara_temple" \
  "Bhoga Nandishwara Temple"
```

**Insert into DB:**
```bash
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Bhoga Nandishwara Temple (Heritage Zones)" \
  --layer-slug "bhoga_nandishwara_temple_heritage" \
  --data-dir "heritage_sites/bengaluru" \
  --authority "Archaeological Survey of India" \
  --min-zoom 7 \
  --max-zoom 18 \
  --delete-existing
```

**Sync to S3:**
```bash
aws s3 sync heritage_tiles/bhoga_nandishwara_temple \
  s3://gis-portal-layers/karnataka/bengaluru/heritage/bhoga_nandishwara_temple/ --delete
```

---

### Devanahalli Fort

**Generate Tiles:**
```bash
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru/Devanahalli Fort.geojson" \
  "heritage_tiles/devanahalli_fort" \
  "Devanahalli Fort"
```

**Insert into DB:**
```bash
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Devanahalli Fort (Heritage Zones)" \
  --layer-slug "devanahalli_fort_heritage" \
  --data-dir "heritage_sites/bengaluru" \
  --authority "Archaeological Survey of India" \
  --min-zoom 7 \
  --max-zoom 18 \
  --delete-existing
```

**Sync to S3:**
```bash
aws s3 sync heritage_tiles/devanahalli_fort \
  s3://gis-portal-layers/karnataka/bengaluru/heritage/devanahalli_fort/ --delete
```

---

### Kolaramma Temple

**Generate Tiles:**
```bash
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru/Kolaramma Temple (Kolar).geojson" \
  "heritage_tiles/kolaramma_temple" \
  "Kolaramma Temple"
```

**Insert into DB:**
```bash
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Kolaramma Temple (Heritage Zones)" \
  --layer-slug "kolaramma_temple_heritage" \
  --data-dir "heritage_sites/bengaluru" \
  --authority "Archaeological Survey of India" \
  --min-zoom 7 \
  --max-zoom 18 \
  --delete-existing
```

**Sync to S3:**
```bash
aws s3 sync heritage_tiles/kolaramma_temple \
  s3://gis-portal-layers/karnataka/bengaluru/heritage/kolaramma_temple/ --delete
```

---

### Someswara Temple

**Generate Tiles:**
```bash
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru/Someswara Temple (Kolar).geojson" \
  "heritage_tiles/someswara_temple" \
  "Someswara Temple"
```

**Insert into DB:**
```bash
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Someswara Temple (Heritage Zones)" \
  --layer-slug "someswara_temple_heritage" \
  --data-dir "heritage_sites/bengaluru" \
  --authority "Archaeological Survey of India" \
  --min-zoom 7 \
  --max-zoom 18 \
  --delete-existing
```

**Sync to S3:**
```bash
aws s3 sync heritage_tiles/someswara_temple \
  s3://gis-portal-layers/karnataka/bengaluru/heritage/someswara_temple/ --delete
```

---

### Tippu Sultan's Birth Palace

**Generate Tiles:**
```bash
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru/Tippu Sultan_s Birth Palace.geojson" \
  "heritage_tiles/tippu_sultan_birth_palace" \
  "Tippu Sultan's Birth Palace"
```

**Insert into DB:**
```bash
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Tippu Sultan's Birth Palace (Heritage Zones)" \
  --layer-slug "tippu_sultan_birth_palace_heritage" \
  --data-dir "heritage_sites/bengaluru" \
  --authority "Archaeological Survey of India" \
  --min-zoom 7 \
  --max-zoom 18 \
  --delete-existing
```

**Sync to S3:**
```bash
aws s3 sync heritage_tiles/tippu_sultan_birth_palace \
  s3://gis-portal-layers/karnataka/bengaluru/heritage/tippu_sultan_birth_palace/ --delete
```

---

### Tippu Sultan's Palace

**Generate Tiles:**
```bash
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru/Tippu Sultan_s Palace.geojson" \
  "heritage_tiles/tippu_sultan_palace" \
  "Tippu Sultan's Palace"
```

**Insert into DB:**
```bash
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Tippu Sultan's Palace (Heritage Zones)" \
  --layer-slug "tippu_sultan_palace_heritage" \
  --data-dir "heritage_sites/bengaluru" \
  --authority "Archaeological Survey of India" \
  --min-zoom 7 \
  --max-zoom 18 \
  --delete-existing
```

**Sync to S3:**
```bash
aws s3 sync heritage_tiles/tippu_sultan_palace \
  s3://gis-portal-layers/karnataka/bengaluru/heritage/tippu_sultan_palace/ --delete
```

---

### Ancient Mound (Hyderabad)

**Generate Tiles:**
```bash
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/hyderabad/ancient_mound.geojson" \
  "heritage_tiles/hyderabad_ancient_mound" \
  "Ancient Mound"
```

**Insert into DB:**
```bash
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "hyderabad" \
  --layer-name "Ancient Mound (Heritage Zones)" \
  --layer-slug "hyderabad_ancient_mound_heritage" \
  --data-dir "heritage_sites/hyderabad" \
  --authority "Archaeological Survey of India" \
  --min-zoom 7 \
  --max-zoom 18 \
  --delete-existing
```

**Sync to S3:**
```bash
aws s3 sync heritage_tiles/hyderabad_ancient_mound \
  s3://gis-portal-layers/telangana/hyderabad/heritage/ancient_mound/ --delete
```

---

### Charminar (Hyderabad)

**Generate Tiles:**
```bash
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/hyderabad/charminar.geojson" \
  "heritage_tiles/hyderabad_charminar" \
  "Charminar"
```

**Insert into DB:**
```bash
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "hyderabad" \
  --layer-name "Charminar (Heritage Zones)" \
  --layer-slug "hyderabad_charminar_heritage" \
  --data-dir "heritage_sites/hyderabad" \
  --authority "Archaeological Survey of India" \
  --min-zoom 7 \
  --max-zoom 18 \
  --delete-existing
```

**Sync to S3:**
```bash
aws s3 sync heritage_tiles/hyderabad_charminar \
  s3://gis-portal-layers/telangana/hyderabad/heritage/charminar/ --delete
```

---

### Golconda Fort (Hyderabad)

**Generate Tiles:**
```bash
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/hyderabad/golconda_fort.geojson" \
  "heritage_tiles/hyderabad_golconda_fort" \
  "Golconda Fort"
```

**Insert into DB:**
```bash
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "hyderabad" \
  --layer-name "Golconda Fort (Heritage Zones)" \
  --layer-slug "hyderabad_golconda_fort_heritage" \
  --data-dir "heritage_sites/hyderabad" \
  --authority "Archaeological Survey of India" \
  --min-zoom 7 \
  --max-zoom 18 \
  --delete-existing
```

**Sync to S3:**
```bash
aws s3 sync heritage_tiles/hyderabad_golconda_fort \
  s3://gis-portal-layers/telangana/hyderabad/heritage/golconda_fort/ --delete
```

---

## Zone Color Reference

| Zone Type | Color | Hex Code | Description |
|-----------|-------|----------|-------------|
| **Protected** | 🔴 Red | `#E52323` | No construction or renovation allowed |
| **Prohibited** | 🟡 Yellow | `#FFFF2B` | NMA (National Monuments Authority) NOC required |
| **Regulated** | 🟢 Green | `#36FF36` | State government NOC required |

---

## File Structure

```
heritage_sites/
├── bengaluru/
│   ├── Bengaluru Fort.geojson
│   ├── Bengaluru Fort_legend.csv
│   └── ... (6 more sites)
└── hyderabad/
    ├── charminar.geojson
    ├── charminar_legend.csv
    └── ... (2 more sites)

heritage_tiles/                    # Generated output
├── bengaluru_fort/
│   ├── 7/, 8/, ..., 18/          # Zoom levels
│   └── index.html                 # Viewer
└── ... (9 more sites)
```

