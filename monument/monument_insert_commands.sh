#!/bin/bash
# Database insertion commands for all monuments

# Karnataka - Bangalore
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bangalore" \
  --layer-name "Bangalore Fort - Protected Area" \
  --layer-slug "bangalore_fort_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Bangalore/Fort" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bangalore" \
  --layer-name "Old Dungeon Fort & Gates - Protected Area" \
  --layer-slug "bangalore_old_dungeon_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Bangalore/Old Dungeon Fort & Gates" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bangalore" \
  --layer-name "Pre-Historic Site (Bangalore) - Protected Area" \
  --layer-slug "bangalore_prehistoric_site_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Bangalore/Pre-Historic Site" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bangalore" \
  --layer-name "Pre-Historic Site 1 (Bangalore) - Protected Area" \
  --layer-slug "bangalore_prehistoric_site_1_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Bangalore/Pre-Historic Site_1" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bangalore" \
  --layer-name "Tipu Sultan's Birth Palace - Protected Area" \
  --layer-slug "bangalore_tipu_birth_palace_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Bangalore/Tipu Sultan_s Birth Palace" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bangalore" \
  --layer-name "Tipu Sultan's Palace - Protected Area" \
  --layer-slug "bangalore_tipu_palace_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Bangalore/Tipu Sultan_s Palace" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

# Karnataka - Bangalore Circle - Kolar
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "kolar" \
  --layer-name "Bhoganandishwara Temple - Protected Area" \
  --layer-slug "kolar_bhoganandishwara_temple_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Kolar/Bhoganandishwara Temple" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "kolar" \
  --layer-name "Haider Ali's Birth Place - Protected Area" \
  --layer-slug "kolar_haider_ali_birth_place_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Kolar/Haider Ali_s Birth Place" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "kolar" \
  --layer-name "Kolaramma Temple - Protected Area" \
  --layer-slug "kolar_kolaramma_temple_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Kolar/Kolaramma Temple" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "kolar" \
  --layer-name "Prehistoric Site (Kolar) - Protected Area" \
  --layer-slug "kolar_prehistoric_site_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Kolar/Prehistoric Site" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "kolar" \
  --layer-name "Ramalingesvara Temples - Protected Area" \
  --layer-slug "kolar_ramalingesvara_temples_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Kolar/Ramalingesvara Temples and Inscriptions" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "kolar" \
  --layer-name "Somesvara Temple - Protected Area" \
  --layer-slug "kolar_somesvara_temple_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Kolar/Somesvara Temple" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

# Karnataka - Bangalore Circle - Tumkur
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "tumkur" \
  --layer-name "Channigaraya Temple - Protected Area" \
  --layer-slug "tumkur_channigaraya_temple_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Tumkur/Channigaraya Temple" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "tumkur" \
  --layer-name "Tumkur Fort - Protected Area" \
  --layer-slug "tumkur_fort_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Tumkur/Fort" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "tumkur" \
  --layer-name "Juma Masjid - Protected Area" \
  --layer-slug "tumkur_juma_masjid_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Tumkur/Juma Masjid" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "tumkur" \
  --layer-name "Keadresvara Temple - Protected Area" \
  --layer-slug "tumkur_keadresvara_temple_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Tumkur/Keadresvara temple" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "tumkur" \
  --layer-name "Malik Rihan Darga - Protected Area" \
  --layer-slug "tumkur_malik_rihan_darga_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Tumkur/Malik Rihan Darga" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "tumkur" \
  --layer-name "Onnakesava Temple - Protected Area" \
  --layer-slug "tumkur_onnakesava_temple_protected" \
  --data-dir "monument_data_set1/Karnataka/Bangalore Circle/Tumkur/Onnakesava Temple" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

# Telangana - Hyderabad
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "hyderabad" \
  --layer-name "Charminar - Protected Area" \
  --layer-slug "hyderabad_charminar_protected" \
  --data-dir "monument_data_set1/Telangana/Hyderabad Circle/Hyderabad/Charminar" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "hyderabad" \
  --layer-name "Golconda Fort - Protected Area" \
  --layer-slug "hyderabad_golconda_fort_protected" \
  --data-dir "monument_data_set1/Telangana/Hyderabad Circle/Hyderabad/Golconda fort" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

# Telangana - Sangareddy
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "sangareddy" \
  --layer-name "Ancient Mound - Protected Area" \
  --layer-slug "sangareddy_ancient_mound_protected" \
  --data-dir "monument_data_set1/Telangana/Hyderabad Circle/Sangareddy/Ancient mound" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

