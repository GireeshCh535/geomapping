#!/bin/bash
# Generate tiles for all heritage sites

set -e  # Exit on error

# Activate virtual environment if it exists
if [ -d "env_geomappping" ]; then
    source env_geomappping/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "==================================="
echo "HERITAGE SITES TILE GENERATION"
echo "==================================="
echo ""

# Bengaluru Heritage Sites
echo ">>> Bengaluru - Bengaluru Fort"
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru/Bengaluru Fort.geojson" \
  "heritage_tiles/bengaluru_fort" \
  "Bengaluru Fort"

echo ""
echo ">>> Bengaluru - Bhoga Nandishwara Temple"
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru/Bhoga Nandishwara Temple (Kolar).geojson" \
  "heritage_tiles/bhoga_nandishwara_temple" \
  "Bhoga Nandishwara Temple"

echo ""
echo ">>> Bengaluru - Devanahalli Fort"
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru/Devanahalli Fort.geojson" \
  "heritage_tiles/devanahalli_fort" \
  "Devanahalli Fort"

echo ""
echo ">>> Bengaluru - Kolaramma Temple"
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru/Kolaramma Temple (Kolar).geojson" \
  "heritage_tiles/kolaramma_temple" \
  "Kolaramma Temple"

echo ""
echo ">>> Bengaluru - Someswara Temple"
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru/Someswara Temple (Kolar).geojson" \
  "heritage_tiles/someswara_temple" \
  "Someswara Temple"

echo ""
echo ">>> Bengaluru - Tippu Sultan's Birth Palace"
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru/Tippu Sultan_s Birth Palace.geojson" \
  "heritage_tiles/tippu_sultan_birth_palace" \
  "Tippu Sultan's Birth Palace"

echo ""
echo ">>> Bengaluru - Tippu Sultan's Palace"
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru/Tippu Sultan_s Palace.geojson" \
  "heritage_tiles/tippu_sultan_palace" \
  "Tippu Sultan's Palace"

# Hyderabad Heritage Sites
echo ""
echo ">>> Hyderabad - Ancient Mound"
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/hyderabad/ancient_mound.geojson" \
  "heritage_tiles/hyderabad_ancient_mound" \
  "Ancient Mound"

echo ""
echo ">>> Hyderabad - Charminar"
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/hyderabad/charminar.geojson" \
  "heritage_tiles/hyderabad_charminar" \
  "Charminar"

echo ""
echo ">>> Hyderabad - Golconda Fort"
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/hyderabad/golconda_fort.geojson" \
  "heritage_tiles/hyderabad_golconda_fort" \
  "Golconda Fort"

echo ""
echo "==================================="
echo "✓ ALL HERITAGE TILES GENERATED"
echo "==================================="

