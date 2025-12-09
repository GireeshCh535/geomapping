# Monument Protection Zones - Tile Generator 🏛️

## 📍 Dataset Overview

**21 Protected Monuments** across 2 states:
- **Karnataka**: 18 monuments (Bangalore, Kolar, Tumkur)
- **Telangana**: 3 monuments (Hyderabad, Sangareddy)

## 🎨 Monument Protection Zones

Each monument has **3 protection zones**:

| Zone | Color | Buffer | Description |
|------|-------|--------|-------------|
| **Protected** | 🔴 Red (#E52323) | 0m | Monument itself - No construction allowed |
| **Prohibited** | 🟡 Yellow (#FFFF2B) | 100m | NMA NOC required for construction |
| **Regulated** | 🟢 Green (#36FF36) | 300m | State Govt NOC required |

## 🗂️ Structure

```
monument_data_set1/
├── Karnataka/
│   └── Bangalore Circle/
│       ├── Bangalore/ (6 monuments)
│       │   ├── Fort/
│       │   │   ├── combined_boundaries.geojson
│       │   │   └── legend.csv ✅
│       │   ├── Old Dungeon Fort & Gates/
│       │   ├── Pre-Historic Site/
│       │   ├── Tipu Sultan_s Birth Palace/
│       │   └── Tipu Sultan_s Palace/
│       ├── Kolar/ (6 monuments)
│       │   ├── Bhoganandishwara Temple/
│       │   ├── Haider Ali_s Birth Place/
│       │   ├── Kolaramma Temple/
│       │   ├── Prehistoric Site/
│       │   ├── Ramalingesvara Temples/
│       │   └── Somesvara Temple/
│       └── Tumkur/ (6 monuments)
│           ├── Channigaraya Temple/
│           ├── Fort/
│           ├── Juma Masjid/
│           ├── Keadresvara temple/
│           ├── Malik Rihan Darga/
│           └── Onnakesava Temple/
└── Telangana/
    └── Hyderabad Circle/
        ├── Hyderabad/ (2 monuments)
        │   ├── Charminar/
        │   └── Golconda fort/
        └── Sangareddy/ (1 monument)
            └── Ancient mound/
```

## 🚀 Generate All Monument Tiles

### Option 1: Batch Generate (All at once)
```bash
chmod +x generate_all_monument_tiles.sh
./generate_all_monument_tiles.sh
```

### Option 2: Individual Monument
```bash
python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Bangalore/Fort" \
  "monument_tiles/bangalore_fort" \
  "Bangalore Fort"
```

## 📋 Monument List

### Karnataka - Bangalore (6)
1. Fort
2. Old Dungeon Fort & Gates
3. Pre-Historic Site
4. Pre-Historic Site_1
5. Tipu Sultan's Birth Palace
6. Tipu Sultan's Palace

### Karnataka - Kolar (6)
1. Bhoganandishwara Temple
2. Haider Ali's Birth Place
3. Kolaramma Temple
4. Prehistoric Site
5. Ramalingesvara Temples and Inscriptions
6. Somesvara Temple

### Karnataka - Tumkur (6)
1. Channigaraya Temple
2. Fort
3. Juma Masjid
4. Keadresvara temple
5. Malik Rihan Darga
6. Onnakesava Temple

### Telangana - Hyderabad (2)
1. Charminar
2. Golconda Fort

### Telangana - Sangareddy (1)
1. Ancient Mound

## 💾 Database Insertion

All commands in `monument_insert_commands.sh`:

```bash
# See monument_insert_commands.sh for all 21 insertion commands
```

## ☁️ S3 Sync

All commands in `monument_s3_sync_commands.sh`:

```bash
# See monument_s3_sync_commands.sh for all 21 S3 sync commands
```

## 📊 Files Created

✅ **21 legend.csv files** - One in each monument directory
✅ **1 universal generator** - `scripts/tiles_generation/monuments/universal_monument_tile_generator.py`
✅ **1 batch script** - `generate_all_monument_tiles.sh`
✅ **1 insert script** - `monument_insert_commands.sh`
✅ **1 S3 sync script** - `monument_s3_sync_commands.sh`

## 🎯 Quick Commands

### Generate Single Monument:
```bash
python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Telangana/Hyderabad Circle/Hyderabad/Charminar" \
  "monument_tiles/hyderabad_charminar" \
  "Charminar"
```

### Generate All Monuments:
```bash
bash generate_all_monument_tiles.sh
```

### Insert All to Database:
```bash
bash monument_insert_commands.sh
```

### Sync All to S3:
```bash
bash monument_s3_sync_commands.sh
```

## 📝 legend.csv Format

Each monument folder has the same legend.csv:

```csv
category,fill_color,outline_color,pattern,pattern_color
Protected,#E52323,#E52323,,
Prohibited,#FFFF2B,#FFFF2B,,
Regulated,#36FF36,#36FF36,,
```

## 🔍 Features

- ✅ **Auto color detection** - Reads fill/stroke from GeoJSON
- ✅ **3-zone rendering** - Protected, Prohibited, Regulated
- ✅ **Semi-transparent** - Zones are 70% opacity for overlay
- ✅ **Proper layering** - Largest (regulated) to smallest (protected)
- ✅ **HTML viewer** - Interactive map with legend
- ✅ **ASI compliance** - Colors and zones per Archaeological Survey of India

## 📈 Statistics

- **Total Monuments**: 21
- **Total Features**: 63 (3 per monument)
- **Zoom Levels**: 9-18
- **Est. Processing Time**: ~5-10 minutes for all

Ready to generate all monument protection zone tiles! 🏛️

