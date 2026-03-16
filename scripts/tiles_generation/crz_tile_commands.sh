#!/bin/bash
# CRZ tile generation using universal_masterplan_tile_generator.py
# Each data/crz/<Region> CRZ layers_processed/ has its own legend.csv (category,fill_color,outline_color,pattern,pattern_color).
# Run from project root: geomapping/ (where data/crz exists).
# Usage: cd geomapping && [source ../env_geomappping/bin/activate] && bash scripts/tiles_generation/crz_tile_commands.sh

set -e
cd "$(dirname "$0")/../.."
if [ -n "$VIRTUAL_ENV" ]; then
  : # already in venv
elif [ -d "../env_geomappping" ]; then
  source "../env_geomappping/bin/activate"
fi
SCRIPT="scripts/tiles_generation/universal_masterplan_tile_generator.py"
DATA_BASE="data/crz"

# 1. Andhra Pradesh CRZ
python3 "$SCRIPT" "$DATA_BASE/AndhraPradesh CRZ layers_processed" "tiles_crz_andhrapradesh" "Andhra Pradesh CRZ"

# 2. Diu CRZ
python3 "$SCRIPT" "$DATA_BASE/Diu CRZ layers_processed" "tiles_crz_diu" "Diu CRZ"

# 3. Gujarat CRZ
python3 "$SCRIPT" "$DATA_BASE/Gujarat CRZ layers_processed" "tiles_crz_gujarat" "Gujarat CRZ"

# 4. Karaikal CRZ
python3 "$SCRIPT" "$DATA_BASE/Karaikal CRZ layers_processed" "tiles_crz_karaikal" "Karaikal CRZ"

# 5. Karnataka CRZ
python3 "$SCRIPT" "$DATA_BASE/Karnataka CRZ layers_processed" "tiles_crz_karnataka" "Karnataka CRZ"

# 6. Kerala CRZ
python3 "$SCRIPT" "$DATA_BASE/Kerala CRZ layers_processed" "tiles_crz_kerala" "Kerala CRZ"

# 7. Maharashtra CRZ
python3 "$SCRIPT" "$DATA_BASE/Maharashtra CRZ layers_processed" "tiles_crz_maharashtra" "Maharashtra CRZ"

# 8. Mahe CRZ
python3 "$SCRIPT" "$DATA_BASE/Mahe CRZ layers_processed" "tiles_crz_mahe" "Mahe CRZ"

# 9. Odisha CRZ
python3 "$SCRIPT" "$DATA_BASE/Odisha CRZ layers_processed" "tiles_crz_odisha" "Odisha CRZ"

# 10. Puducherry CRZ
python3 "$SCRIPT" "$DATA_BASE/Puducherry CRZ layers_processed" "tiles_crz_puducherry" "Puducherry CRZ"

# 11. Yanam CRZ (data/Yanam CRZ layers_processed/)
python3 "$SCRIPT" "data/Yanam CRZ layers_processed" "tiles_crz_yanam" "Yanam CRZ"

echo "Done. Tiles written to tiles_crz_* directories."



python3 scripts/tiles_generation/universal_masterplan_tile_generator.py "data/crz/AndhraPradesh CRZ layers_processed" tiles_crz_andhrapradesh "Andhra Pradesh CRZ"
python3 scripts/tiles_generation/universal_masterplan_tile_generator.py "data/crz/Diu CRZ layers_processed" tiles_crz_diu "Diu CRZ"
python3 scripts/tiles_generation/universal_masterplan_tile_generator.py "data/crz/Gujarat CRZ layers_processed" tiles_crz_gujarat "Gujarat CRZ"
python3 scripts/tiles_generation/universal_masterplan_tile_generator.py "data/crz/Karaikal CRZ layers_processed" tiles_crz_karaikal "Karaikal CRZ"
python3 scripts/tiles_generation/universal_masterplan_tile_generator.py "data/crz/Karnataka CRZ layers_processed" tiles_crz_karnataka "Karnataka CRZ"
python3 scripts/tiles_generation/universal_masterplan_tile_generator.py "data/crz/Kerala CRZ layers_processed" tiles_crz_kerala "Kerala CRZ"
python3 scripts/tiles_generation/universal_masterplan_tile_generator.py "data/crz/Maharashtra CRZ layers_processed" tiles_crz_maharashtra "Maharashtra CRZ"
python3 scripts/tiles_generation/universal_masterplan_tile_generator.py "data/crz/Mahe CRZ layers_processed" tiles_crz_mahe "Mahe CRZ"
python3 scripts/tiles_generation/universal_masterplan_tile_generator.py "data/crz/Odisha CRZ layers_processed" tiles_crz_odisha "Odisha CRZ"
python3 scripts/tiles_generation/universal_masterplan_tile_generator.py "data/crz/Puducherry CRZ layers_processed" tiles_crz_puducherry "Puducherry CRZ"
python3 scripts/tiles_generation/universal_masterplan_tile_generator.py "data/Yanam CRZ layers_processed" tiles_crz_yanam "Yanam CRZ"