#!/bin/bash
# Generate tiles for all monuments in monument_data_set1

echo "================================================================================"
echo "GENERATING TILES FOR ALL MONUMENTS"
echo "================================================================================"

# Karnataka - Bangalore Circle - Bangalore
python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Bangalore/Fort" \
  "monument_tiles/bangalore_fort" \
  "Bangalore Fort"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Bangalore/Old Dungeon Fort & Gates" \
  "monument_tiles/bangalore_old_dungeon_fort" \
  "Old Dungeon Fort & Gates"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Bangalore/Pre-Historic Site" \
  "monument_tiles/bangalore_prehistoric_site" \
  "Pre-Historic Site (Bangalore)"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Bangalore/Pre-Historic Site_1" \
  "monument_tiles/bangalore_prehistoric_site_1" \
  "Pre-Historic Site 1 (Bangalore)"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Bangalore/Tipu Sultan_s Birth Palace" \
  "monument_tiles/bangalore_tipu_birth_palace" \
  "Tipu Sultan's Birth Palace"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Bangalore/Tipu Sultan_s Palace" \
  "monument_tiles/bangalore_tipu_palace" \
  "Tipu Sultan's Palace"

# Karnataka - Bangalore Circle - Kolar
python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Kolar/Bhoganandishwara Temple" \
  "monument_tiles/kolar_bhoganandishwara_temple" \
  "Bhoganandishwara Temple"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Kolar/Haider Ali_s Birth Place" \
  "monument_tiles/kolar_haider_ali_birth_place" \
  "Haider Ali's Birth Place"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Kolar/Kolaramma Temple" \
  "monument_tiles/kolar_kolaramma_temple" \
  "Kolaramma Temple"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Kolar/Prehistoric Site" \
  "monument_tiles/kolar_prehistoric_site" \
  "Prehistoric Site (Kolar)"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Kolar/Ramalingesvara Temples and Inscriptions" \
  "monument_tiles/kolar_ramalingesvara_temples" \
  "Ramalingesvara Temples and Inscriptions"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Kolar/Somesvara Temple" \
  "monument_tiles/kolar_somesvara_temple" \
  "Somesvara Temple"

# Karnataka - Bangalore Circle - Tumkur
python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Tumkur/Channigaraya Temple" \
  "monument_tiles/tumkur_channigaraya_temple" \
  "Channigaraya Temple"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Tumkur/Fort" \
  "monument_tiles/tumkur_fort" \
  "Tumkur Fort"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Tumkur/Juma Masjid" \
  "monument_tiles/tumkur_juma_masjid" \
  "Juma Masjid"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Tumkur/Keadresvara temple" \
  "monument_tiles/tumkur_keadresvara_temple" \
  "Keadresvara Temple"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Tumkur/Malik Rihan Darga" \
  "monument_tiles/tumkur_malik_rihan_darga" \
  "Malik Rihan Darga"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Karnataka/Bangalore Circle/Tumkur/Onnakesava Temple" \
  "monument_tiles/tumkur_onnakesava_temple" \
  "Onnakesava Temple"

# Telangana - Hyderabad Circle - Hyderabad
python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Telangana/Hyderabad Circle/Hyderabad/Charminar" \
  "monument_tiles/hyderabad_charminar" \
  "Charminar"

python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Telangana/Hyderabad Circle/Hyderabad/Golconda fort" \
  "monument_tiles/hyderabad_golconda_fort" \
  "Golconda Fort"

# Telangana - Hyderabad Circle - Sangareddy
python scripts/tiles_generation/monuments/universal_monument_tile_generator.py \
  "monument_data_set1/Telangana/Hyderabad Circle/Sangareddy/Ancient mound" \
  "monument_tiles/sangareddy_ancient_mound" \
  "Ancient Mound (Sangareddy)"

echo ""
echo "================================================================================"
echo "✓ ALL MONUMENT TILES GENERATED"
echo "================================================================================"
echo ""
echo "To view all monuments, use the monument_tiles/ directory"
echo ""

