#!/bin/bash
# Hyderabad Master Plan (HMDA + HUDA) tile generation
# Legends: data/telangana/hyderabad/masterplan/HMDA/legend.csv and HUDA/legend.csv

set -e
cd "$(dirname "$0")/../../.."

DATA_RAW="data/telangana/hyderabad/masterplan"
DATA_SPLIT="data/telangana/hyderabad/master_plan_split"
OUTPUT_DIR="hyderabad_tiles_seamless_optimized"

echo "=== Option A: With preprocessing (recommended for large datasets) ==="
echo "Step 1: Preprocess (splits MultiPolygons, copies legends)"
echo "  python3 scripts/tiles_generation/telangana/preprocess_hyderabad_features.py --input-dir $DATA_RAW --output-dir $DATA_SPLIT"
echo ""
echo "Step 2: Generate tiles from pre-split data"
echo "  python3 scripts/tiles_generation/telangana/hyderabad_masterplan_tile_generator_optimized.py --data-dir $DATA_SPLIT --output-dir $OUTPUT_DIR"
echo ""

echo "=== Option B: Without preprocessing (use raw masterplan folder) ==="
echo "  python3 scripts/tiles_generation/telangana/hyderabad_masterplan_tile_generator_optimized.py --data-dir $DATA_RAW --output-dir $OUTPUT_DIR"
echo ""

# Run Option A by default
if [ "${1:-}" = "run" ]; then
  echo "Running preprocessing..."
  python3 scripts/tiles_generation/telangana/preprocess_hyderabad_features.py --input-dir "$DATA_RAW" --output-dir "$DATA_SPLIT"
  echo "Running tile generator..."
  python3 scripts/tiles_generation/telangana/hyderabad_masterplan_tile_generator_optimized.py --data-dir "$DATA_SPLIT" --output-dir "$OUTPUT_DIR"
  echo "Done. Tiles in $OUTPUT_DIR/"
else
  echo "To run preprocessing + tile generation, use: $0 run"
fi
