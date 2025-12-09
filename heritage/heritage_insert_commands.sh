#!/bin/bash
# Database insertion commands for heritage sites

# Bengaluru Heritage Sites
# 1. Bengaluru Fort
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Bengaluru Fort (Heritage Zones)" \
  --layer-slug "bengaluru_fort_heritage" \
  --data-dir "heritage_sites/bengaluru" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

# 2. Bhoga Nandishwara Temple
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Bhoga Nandishwara Temple (Heritage Zones)" \
  --layer-slug "bhoga_nandishwara_temple_heritage" \
  --data-dir "heritage_sites/bengaluru" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

# 3. Devanahalli Fort
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Devanahalli Fort (Heritage Zones)" \
  --layer-slug "devanahalli_fort_heritage" \
  --data-dir "heritage_sites/bengaluru" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

# 4. Kolaramma Temple
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Kolaramma Temple (Heritage Zones)" \
  --layer-slug "kolaramma_temple_heritage" \
  --data-dir "heritage_sites/bengaluru" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

# 5. Someswara Temple
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Someswara Temple (Heritage Zones)" \
  --layer-slug "someswara_temple_heritage" \
  --data-dir "heritage_sites/bengaluru" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

# 6. Tippu Sultan's Birth Palace
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Tippu Sultan's Birth Palace (Heritage Zones)" \
  --layer-slug "tippu_sultan_birth_palace_heritage" \
  --data-dir "heritage_sites/bengaluru" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

# 7. Tippu Sultan's Palace
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Tippu Sultan's Palace (Heritage Zones)" \
  --layer-slug "tippu_sultan_palace_heritage" \
  --data-dir "heritage_sites/bengaluru" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

# Hyderabad Heritage Sites
# 8. Ancient Mound
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "hyderabad" \
  --layer-name "Ancient Mound (Heritage Zones)" \
  --layer-slug "hyderabad_ancient_mound_heritage" \
  --data-dir "heritage_sites/hyderabad" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

# 9. Charminar
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "hyderabad" \
  --layer-name "Charminar (Heritage Zones)" \
  --layer-slug "hyderabad_charminar_heritage" \
  --data-dir "heritage_sites/hyderabad" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

# 10. Golconda Fort
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "hyderabad" \
  --layer-name "Golconda Fort (Heritage Zones)" \
  --layer-slug "hyderabad_golconda_fort_heritage" \
  --data-dir "heritage_sites/hyderabad" \
  --authority "Archaeological Survey of India" \
  --min-zoom 9 \
  --max-zoom 18 \
  --delete-existing

