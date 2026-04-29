#!/usr/bin/env bash
set -euo pipefail

# Run this script from the repository root:
# /Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping

# ---------------------------------------------
# LINE-STYLED TILES (set29 line-based layers only)
# ---------------------------------------------

python3 scripts/tiles_generation/universal_line_styled_tile_generator.py data/set29/Amaravati\ Inner\ Ring\ road/Amaravati\ Inner\ Ring\ road.geojson set29/Amaravati_Inner_Ring_road --legend data/set29/Amaravati\ Inner\ Ring\ road/legend.csv --min-zoom 8 --max-zoom 18

python3 scripts/tiles_generation/universal_line_styled_tile_generator.py data/set29/ChennaiPort_Maduravoyal_Expressway/ChennaiPort_Maduravoyal_Expressway.geojson set29/ChennaiPort_Maduravoyal_Expressway --legend data/set29/ChennaiPort_Maduravoyal_Expressway/legend.csv --min-zoom 8 --max-zoom 18

python3 scripts/tiles_generation/universal_line_styled_tile_generator.py data/set29/CPRR_Final/CPRR_Final.geojson set29/CPRR_Final --legend data/set29/CPRR_Final/legend.csv --min-zoom 8 --max-zoom 18

python3 scripts/tiles_generation/universal_line_styled_tile_generator.py data/set29/vijayawada_metro_actual/vijayawada_metro_actual.geojson set29/vijayawada_metro_actual --legend data/set29/vijayawada_metro_actual/legend.csv --min-zoom 8 --max-zoom 18

# -----------------------------------------
# MASTERPLAN TILES (Navi Mumbai airport)
# -----------------------------------------
# universal_masterplan_tile_generator.py requires legend.csv in:
# category,fill_color,outline_color,pattern,pattern_color
# format. We create a temporary masterplan legend for this run and then restore.

cp data/set29/Navi_Mumbai_International_Airport_Boundary/legend.csv data/set29/Navi_Mumbai_International_Airport_Boundary/legend_line_styled.csv.bak

cat > data/set29/Navi_Mumbai_International_Airport_Boundary/legend.csv <<'EOF'
category,fill_color,outline_color,pattern,pattern_color
DEFAULT,#727272,#4A4A4A,,
EOF

python3 scripts/tiles_generation/universal_masterplan_tile_generator.py data/set29/Navi_Mumbai_International_Airport_Boundary set29/Navi_Mumbai_International_Airport_Boundary_masterplan_filled Navi\ Mumbai\ International\ Airport\ Boundary --min-zoom 7 --max-zoom 18

mv data/set29/Navi_Mumbai_International_Airport_Boundary/legend_line_styled.csv.bak data/set29/Navi_Mumbai_International_Airport_Boundary/legend.csv

echo "Done: set29 tiles generated (line layers + Navi Mumbai via masterplan generator)."
