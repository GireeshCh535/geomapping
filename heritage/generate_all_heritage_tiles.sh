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
echo ">>> Bengaluru - All heritage sites (merged)"
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/bengaluru" \
  "Bengaluru Heritage Sites"

echo ""
echo ">>> Hyderabad - All heritage sites (merged)"
python scripts/tiles_generation/heritage/universal_heritage_tile_generator.py \
  "heritage_sites/hyderabad" \
  "Hyderabad Heritage Sites"

echo ""
echo "==================================="
echo "✓ ALL HERITAGE TILES GENERATED"
echo "==================================="

