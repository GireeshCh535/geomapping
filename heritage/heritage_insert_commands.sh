#!/bin/bash
# Database insertion commands for heritage sites (merged per city)

# Bengaluru Heritage Sites (merged)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Bengaluru Heritage Sites" \
  --layer-slug "bengaluru_heritage_sites" \
  --data-dir "heritage_sites/bengaluru" \
  --authority "Archaeological Survey of India" \
  --min-zoom 7 \
  --max-zoom 18 \
  --delete-existing

# Hyderabad Heritage Sites (merged)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "hyderabad" \
  --layer-name "Hyderabad Heritage Sites" \
  --layer-slug "hyderabad_heritage_sites" \
  --data-dir "data/heritage_sites/hyderabad" \
  --authority "Archaeological Survey of India" \
  --min-zoom 7 \
  --max-zoom 18 \
  --delete-existing

