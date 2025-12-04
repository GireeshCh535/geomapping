#!/bin/bash
# Commands to insert air funnel zones for all 20 cities
# Data files are organized in data/state/city/air_funnel_zones/ directories

# 1. Ayodhya
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "ayodhya" \
  --layer-name "Ayodhya Air Funnel Zones" \
  --layer-slug "ayodhya_air_funnel_zones" \
  --data-dir "data/uttar-pradesh/ayodhya/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 2. Kozhikode (Calicut)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "kozhikode" \
  --layer-name "Kozhikode Air Funnel Zones" \
  --layer-slug "kozhikode_air_funnel_zones" \
  --data-dir "data/kerala/kozhikode/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 3. Ahmedabad - Gandhinagar
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "ahmedabad-gandhinagar" \
  --layer-name "Ahmedabad Air Funnel Zones" \
  --layer-slug "ahmedabad_air_funnel_zones" \
  --data-dir "data/gujarat/ahmedabad-gandhinagar/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 4. Bhubaneswar
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bhubaneshwar" \
  --layer-name "Bhubaneshwar Air Funnel Zones" \
  --layer-slug "bhubaneshwar_air_funnel_zones" \
  --data-dir "data/odisha/bhubaneshwar/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 5. Chennai
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "chennai" \
  --layer-name "Chennai Air Funnel Zones" \
  --layer-slug "chennai_air_funnel_zones" \
  --data-dir "data/tamil-nadu/chennai/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 6. Delhi-IGI
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "delhi-ncr" \
  --layer-name "Delhi Air Funnel Zones" \
  --layer-slug "delhi_air_funnel_zones" \
  --data-dir "data/delhi/delhi-ncr/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 7. Diu
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "daman-and-diu" \
  --layer-name "Diu Air Funnel Zones" \
  --layer-slug "diu_air_funnel_zones" \
  --data-dir "data/dadra-nagar-haveli-daman-diu/daman-and-diu/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 8. Dohlera
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "dholera" \
  --layer-name "Dholera Air Funnel Zones" \
  --layer-slug "dholera_air_funnel_zones" \
  --data-dir "data/gujarat/dholera/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 9. Guwahati
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "guwahati" \
  --layer-name "Guwahati Air Funnel Zones" \
  --layer-slug "guwahati_air_funnel_zones" \
  --data-dir "data/assam/guwahati/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 10. Jaipur
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "jaipur" \
  --layer-name "Jaipur Air Funnel Zones" \
  --layer-slug "jaipur_air_funnel_zones" \
  --data-dir "data/rajasthan/jaipur/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 11. Kochi
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "kochi" \
  --layer-name "Kochi Air Funnel Zones" \
  --layer-slug "kochi_air_funnel_zones" \
  --data-dir "data/kerala/kochi/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 12. Lucknow
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "lucknow" \
  --layer-name "Lucknow Air Funnel Zones" \
  --layer-slug "lucknow_air_funnel_zones" \
  --data-dir "data/uttar-pradesh/lucknow/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 13. Nagpur
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "nagpur" \
  --layer-name "Nagpur Air Funnel Zones" \
  --layer-slug "nagpur_air_funnel_zones" \
  --data-dir "data/maharashtra/nagpur/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 14. Navi Mumbai
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "mumbai" \
  --layer-name "Mumbai Air Funnel Zones" \
  --layer-slug "mumbai_air_funnel_zones" \
  --data-dir "data/maharashtra/mumbai/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 15. Noida (Jewar)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "delhi-ncr" \
  --layer-name "Noida Air Funnel Zones" \
  --layer-slug "noida_air_funnel_zones" \
  --data-dir "data/delhi-ncr/delhi-ncr/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 16. Patna
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "patna" \
  --layer-name "Patna Air Funnel Zones" \
  --layer-slug "patna_air_funnel_zones" \
  --data-dir "data/bihar/patna/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 17. Raigarh
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "raigarh" \
  --layer-name "Raigarh Air Funnel Zones" \
  --layer-slug "raigarh_air_funnel_zones" \
  --data-dir "data/chhatisgarh/raigarh/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 18. Raipur
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "new-raipur" \
  --layer-name "Raipur Air Funnel Zones" \
  --layer-slug "raipur_air_funnel_zones" \
  --data-dir "data/chhatisgarh/new-raipur/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 19. Tirupati
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "tirupati" \
  --layer-name "Tirupati Air Funnel Zones" \
  --layer-slug "tirupati_air_funnel_zones" \
  --data-dir "data/andhra-pradesh/tirupati/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 20. Warangal
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "warangal" \
  --layer-name "Warangal Air Funnel Zones" \
  --layer-slug "warangal_air_funnel_zones" \
  --data-dir "data/andhra-pradesh/warangal/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 21. Puducherry Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "puducherry" \
  --layer-name "Puducherry Masterplan" \
  --layer-slug "puducherry_masterplan" \
  --data-dir "data/puducherry/master_plan" \
  --authority "Puducherry Planning Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 22. Jaipur Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "jaipur" \
  --layer-name "Jaipur Masterplan" \
  --layer-slug "jaipur_masterplan" \
  --data-dir "data/rajasthan/jaipur/master_plan" \
  --authority "Jaipur Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 23. Chandigarh Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "chandigarh" \
  --layer-name "Chandigarh Masterplan" \
  --layer-slug "chandigarh_masterplan" \
  --data-dir "data/punjab/chandigarh/master_plan" \
  --authority "Chandigarh Administration" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 24. Bhubaneswar Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bhubaneswar" \
  --layer-name "Bhubaneswar Masterplan" \
  --layer-slug "bhubaneswar_masterplan" \
  --data-dir "data/odisha/bhubaneshwar/master_plan" \
  --authority "Bhubaneswar Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 25. Jagdalpur Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "jagdalpur" \
  --layer-name "Jagdalpur Masterplan" \
  --layer-slug "jagdalpur_masterplan" \
  --data-dir "data/chhatisgarh/jagdalpur/master_plan" \
  --authority "Jagdalpur Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 26. Raigarh Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "raigarh" \
  --layer-name "Raigarh Masterplan" \
  --layer-slug "raigarh_masterplan" \
  --data-dir "data/chhatisgarh/raigarh/master_plan" \
  --authority "Raigarh Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 27. Rajnandgaon Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "rajnandgaon" \
  --layer-name "Rajnandgaon Masterplan" \
  --layer-slug "rajnandgaon_masterplan" \
  --data-dir "data/chhatisgarh/rajnandgaon/master_plan" \
  --authority "Rajnandgaon Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 28. Durg-Bhilai Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "durg-bhilai" \
  --layer-name "Durg-Bhilai Masterplan" \
  --layer-slug "durg_bhilai_masterplan" \
  --data-dir "data/chhatisgarh/durg-bihlai/master_plan" \
  --authority "Durg-Bhilai Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 29. Mahasamund Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "mahasamund" \
  --layer-name "Mahasamund Masterplan" \
  --layer-slug "mahasamund_masterplan" \
  --data-dir "data/chhatisgarh/mahasamund/master_plan" \
  --authority "Mahasamund Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 30. Balodabazaar Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "balodabazaar" \
  --layer-name "Balodabazaar Masterplan" \
  --layer-slug "balodabazaar_masterplan" \
  --data-dir "data/chhatisgarh/balodabazaar/master_plan" \
  --authority "Balodabazaar Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 31. Bhatapara Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bhatapara" \
  --layer-name "Bhatapara Masterplan" \
  --layer-slug "bhatapara_masterplan" \
  --data-dir "data/chhatisgarh/bhatapara/master_plan" \
  --authority "Bhatapara Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 32. Arang Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "arang" \
  --layer-name "Arang Masterplan" \
  --layer-slug "arang_masterplan" \
  --data-dir "data/chhatisgarh/arang/master_plan" \
  --authority "Arang Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 33. Jodhpur Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "jodhpur" \
  --layer-name "Jodhpur Masterplan" \
  --layer-slug "jodhpur_masterplan" \
  --data-dir "data/rajasthan/jodhpur/master_plan" \
  --authority "Jodhpur Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 34. Udaipur Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "udaipur" \
  --layer-name "Udaipur Masterplan" \
  --layer-slug "udaipur_masterplan" \
  --data-dir "data/rajasthan/udaipur/master_plan" \
  --authority "Udaipur Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 35. Hyderabad Masterplan (HMDA)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "hyderabad" \
  --layer-name "Hyderabad Masterplan (HMDA)" \
  --layer-slug "hyderabad_masterplan_hmda" \
  --data-dir "data/Telangana/Hyderabad/master_plan/HMDA" \
  --authority "Hyderabad Metropolitan Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 36. Hyderabad Masterplan (HUDA)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "hyderabad" \
  --layer-name "Hyderabad Masterplan (HUDA)" \
  --layer-slug "hyderabad_masterplan_huda" \
  --data-dir "data/Telangana/Hyderabad/master_plan/HUDA" \
  --authority "Hyderabad Urban Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 37. Visakhapatnam Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "visakhapatnam" \
  --layer-name "Visakhapatnam Masterplan" \
  --layer-slug "visakhapatnam_masterplan" \
  --data-dir "data/andhra_pradesh/visakhapatnam/master_plan" \
  --authority "Greater Visakhapatnam Municipal Corporation" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

