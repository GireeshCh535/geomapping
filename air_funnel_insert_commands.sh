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
  --city-slug "bhubaneswar" \
  --layer-name "Bhubaneshwar Air Funnel Zones" \
  --layer-slug "bhubaneswar_air_funnel_zones" \
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
  --city-slug "raipur" \
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

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "warangal" \
  --layer-name "Warangal Master Plan" \
  --layer-slug "warangal_master_plan" \
  --data-dir "data/andhra-pradesh/warangal/master_plan" \
  --authority "Kakatiya Urban Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 21. Bengaluru
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Bengaluru Air Funnel Zones" \
  --layer-slug "bengaluru_air_funnel_zones" \
  --data-dir "data/karnataka/bengaluru/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# Bengaluru - Masterplan Roads
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Bengaluru Masterplan Roads" \
  --layer-slug "bengaluru_masterplan_roads" \
  --data-dir "data/karnataka/bengaluru/roads" \
  --authority "BBMP" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# Bengaluru - Metro
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Bengaluru Metro" \
  --layer-slug "bengaluru_metro" \
  --data-dir "data/karnataka/bengaluru/metro" \
  --authority "BBMP" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# Bengaluru - Master Plan 2015
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Bengaluru Master Plan 2015" \
  --layer-slug "bengaluru_master_plan_2015" \
  --data-dir "data/karnataka/bengaluru/master_plan" \
  --authority "Bengaluru Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# Bengaluru - STRR
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Bengaluru STRR" \
  --layer-slug "bengaluru_strr" \
  --data-dir "data/karnataka/bengaluru/strr" \
  --authority "BBMP" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# Bengaluru - Highways
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "Bengaluru Highways" \
  --layer-slug "bengaluru_highways" \
  --data-dir "data/karnataka/bengaluru/highways" \
  --authority "BBMP" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 22. Puducherry Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "puducherry" \
  --layer-name "Puducherry Masterplan" \
  --layer-slug "puducherry_masterplan" \
  --data-dir "data/puducherry/master_plan" \
  --authority "Puducherry Planning Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 23. Jaipur Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "jaipur" \
  --layer-name "Jaipur Masterplan" \
  --layer-slug "jaipur_masterplan" \
  --data-dir "data/rajasthan/jaipur/master_plan" \
  --authority "Jaipur Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 24. Chandigarh Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "chandigarh" \
  --layer-name "Chandigarh Masterplan" \
  --layer-slug "chandigarh_masterplan" \
  --data-dir "data/punjab/chandigarh/master_plan" \
  --authority "Chandigarh Administration" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 25. Bhubaneswar Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bhubaneswar" \
  --layer-name "Bhubaneswar Masterplan" \
  --layer-slug "bhubaneswar_masterplan" \
  --data-dir "data/odisha/bhubaneshwar/master_plan" \
  --authority "Bhubaneswar Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 26. Jagdalpur Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "jagdalpur" \
  --layer-name "Jagdalpur Masterplan" \
  --layer-slug "jagdalpur_masterplan" \
  --data-dir "data/chhatisgarh/jagdalpur/master_plan" \
  --authority "Jagdalpur Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 27. Raigarh Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "raigarh" \
  --layer-name "Raigarh Masterplan" \
  --layer-slug "raigarh_masterplan" \
  --data-dir "data/chhatisgarh/raigarh/master_plan" \
  --authority "Raigarh Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 28. Rajnandgaon Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "	durg-bihlai" \
  --layer-name "Rajnandgaon Masterplan" \
  --layer-slug "rajnandgaon_masterplan" \
  --data-dir "data/chhatisgarh/rajnandgaon/master_plan" \
  --authority "Rajnandgaon Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 29. Durg-Bhilai Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "durg-bihlai" \
  --layer-name "Durg-Bhilai Masterplan" \
  --layer-slug "durg_bihlai_masterplan" \
  --data-dir "data/chhatisgarh/durg-bihlai/master_plan" \
  --authority "Durg-Bhilai Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 30. Mahasamund Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "new-raipur" \
  --layer-name "Mahasamund Masterplan" \
  --layer-slug "mahasamund_masterplan" \
  --data-dir "data/chhatisgarh/mahasamund/master_plan" \
  --authority "Mahasamund Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 31. Balodabazaar Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "new-raipur" \
  --layer-name "Balodabazaar Masterplan" \
  --layer-slug "balodabazaar_masterplan" \
  --data-dir "data/chhatisgarh/balodabazaar/master_plan" \
  --authority "Balodabazaar Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 32. Bhatapara Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "new-raipur" \
  --layer-name "Bhatapara Masterplan" \
  --layer-slug "bhatapara_masterplan" \
  --data-dir "data/chhatisgarh/bhatapara/master_plan" \
  --authority "Bhatapara Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 33. Arang Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "new-raipur" \
  --layer-name "Arang Masterplan" \
  --layer-slug "arang_masterplan" \
  --data-dir "data/chhatisgarh/arang/master_plan" \
  --authority "Arang Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 34. Jodhpur Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "jodhpur" \
  --layer-name "Jodhpur Masterplan" \
  --layer-slug "jodhpur_masterplan" \
  --data-dir "data/rajasthan/jodhpur/master_plan" \
  --authority "Jodhpur Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 35. Udaipur Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "udaipur" \
  --layer-name "Udaipur Masterplan" \
  --layer-slug "udaipur_masterplan" \
  --data-dir "data/rajasthan/udaipur/master_plan" \
  --authority "Udaipur Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 36. Hyderabad Masterplan (Combined HMDA + HUDA)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "hyderabad" \
  --layer-name "Hyderabad Masterplan" \
  --layer-slug "hyderabad_masterplan" \
  --data-dir "data/Telangana/Hyderabad/master_plan" \
  --authority "HMDA & HUDA" \
  --min-zoom 7 \
  --max-zoom 18 \
  --delete-existing

# 38. Visakhapatnam Masterplan
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "visakhapatnam" \
  --layer-name "Visakhapatnam Masterplan" \
  --layer-slug "visakhapatnam_masterplan" \
  --data-dir "data/andhra_pradesh/visakhapatnam/master_plan" \
  --authority "Greater Visakhapatnam Municipal Corporation" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

#!/bin/bash
# Commands to insert masterplan layers for all new locations
# Data files are organized in data/ directories

# 1. Thiruvananthapuram (Kerala)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "thiruvananthapuram" \
  --layer-name "Thiruvananthapuram Masterplan" \
  --layer-slug "thiruvananthapuram_masterplan" \
  --data-dir "data/kerala/thiruvananthapuram/masterplan" \
  --authority "Thiruvananthapuram Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 2. BIAPPA (Karnataka) - Inserted as layer under Bengaluru
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "bengaluru" \
  --layer-name "BIAPPA Masterplan" \
  --layer-slug "biappa_masterplan" \
  --data-dir "data/karnataka/biappa/masterplan" \
  --authority "Bangalore International Airport Planning Area Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 3. Thrissur (Karnataka)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "thrissur" \
  --layer-name "Thrissur Masterplan" \
  --layer-slug "thrissur_masterplan" \
  --data-dir "data/karnataka/thrissur/masterplan" \
  --authority "Thrissur Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 4. Bhiwadi (Delhi NCR)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "delhi-ncr" \
  --layer-name "Bhiwadi Masterplan" \
  --layer-slug "bhiwadi_masterplan" \
  --data-dir "data/delhi/delhi_ncr/bhiwadi/masterplan" \
  --authority "Bhiwadi Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 5. Hodal (Delhi NCR)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "delhi-ncr" \
  --layer-name "Hodal Masterplan" \
  --layer-slug "hodal_masterplan" \
  --data-dir "data/delhi/delhi_ncr/hodal/masterplan" \
  --authority "Hodal Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 6. Jhajjar (Delhi NCR)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "delhi-ncr" \
  --layer-name "Jhajjar Masterplan" \
  --layer-slug "jhajjar_masterplan" \
  --data-dir "data/delhi/delhi_ncr/jhajjar/masterplan" \
  --authority "Jhajjar Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 7. Meerut (Delhi NCR)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "delhi-ncr" \
  --layer-name "Meerut Masterplan" \
  --layer-slug "meerut_masterplan" \
  --data-dir "data/delhi/delhi_ncr/meerut/masterplan" \
  --authority "Meerut Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 8. Nuh (Delhi NCR)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "delhi-ncr" \
  --layer-name "Nuh Masterplan" \
  --layer-slug "nuh_masterplan" \
  --data-dir "data/delhi/delhi_ncr/nuh/masterplan" \
  --authority "Nuh Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 9. Rewari (Delhi NCR)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "delhi-ncr" \
  --layer-name "Rewari Masterplan" \
  --layer-slug "rewari_masterplan" \
  --data-dir "data/delhi/delhi_ncr/rewari/masterplan" \
  --authority "Rewari Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 10. Gohana (Delhi NCR)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "delhi-ncr" \
  --layer-name "Gohana Masterplan" \
  --layer-slug "gohana_masterplan" \
  --data-dir "data/delhi/delhi_ncr/gohana/masterplan" \
  --authority "Gohana Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 11. Itanagar (Arunachal Pradesh)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "itanagar" \
  --layer-name "Itanagar Masterplan" \
  --layer-slug "itanagar_masterplan" \
  --data-dir "data/arunachal-pradesh/itanagar/itanagar/masterplan" \
  --authority "Itanagar Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 12. Port Blair (Andaman and Nicobar Islands)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "port-blair" \
  --layer-name "Port Blair Masterplan" \
  --layer-slug "port_blair_masterplan" \
  --data-dir "data/andaman-and-nicobar-islands/port-blair/port_blair/masterplan" \
  --authority "Port Blair Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 13. Alwar (Delhi NCR)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "delhi-ncr" \
  --layer-name "Alwar Masterplan" \
  --layer-slug "alwar_masterplan" \
  --data-dir "data/delhi/delhi_ncr/alwar/masterplan" \
  --authority "Alwar Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing


docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "visakhapatnam" \
  --layer-name "Visakhapatnam Masterplan" \
  --layer-slug "visakhapatnam_masterplan" \
  --data-dir "data/andhra_pradesh/visakhapatnam/master_plan" \
  --authority "Greater Visakhapatnam Municipal Corporation" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

  docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "amaravati" \
  --layer-name "Amaravati Masterplan" \
  --layer-slug "amaravati_masterplan" \
  --data-dir "data/andhra_pradesh/amaravati/master_plan" \
  --authority "Amaravati Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing


docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "delhi-ncr" \
  --layer-name "Faridabad Master Plan" \
  --layer-slug "faridabad_masterplan" \
  --data-dir "data/delhi_ncr/faridabad/master_plan" \
  --authority "Faridabad Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing \
  --legend "data/delhi_ncr/faridabad/master_plan/legend.csv"


docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "delhi-ncr" \
  --layer-name "Gurugram Master Plan" \
  --layer-slug "gurugram_masterplan" \
  --data-dir "data/delhi_ncr/gurgaon/master_plan" \
  --authority "Town and Country Planning Department, Haryana" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing \
  --legend "data/delhi_ncr/gurgaon/master_plan/legend.csv"


docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "delhi-ncr" \
  --layer-name "Noida Master Plan" \
  --layer-slug "noida_masterplan" \
  --data-dir "data/delhi_ncr/noida/master_plan" \
  --authority "Noida Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing \
  --legend "data/delhi_ncr/noida/master_plan/legend.csv"


docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "delhi-ncr" \
  --layer-name "Greater Noida Master Plan" \
  --layer-slug "greater_noida_masterplan" \
  --data-dir "data/delhi_ncr/greater_noida/master_plan" \
  --authority "Greater Noida Industrial Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing \
  --legend "data/delhi_ncr/greater_noida/master_plan/legend.csv"

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "delhi-ncr" \
  --layer-name "Delhi Master Plan" \
  --layer-slug "delhi_masterplan" \
  --data-dir "data/delhi_ncr/master_plan" \
  --authority "Delhi Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing \
  --legend "data/delhi_ncr/master_plan/legend.csv"

# ========== Telangana Hyderabad ==========
# Run fill_color first: see scripts/FILL_COLOR_COMMANDS.md §48 (48.1–48.6).

# Hyderabad Air Funnel Zones (run fill_color first: FILL_COLOR_COMMANDS.md §48.1)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "hyderabad" \
  --layer-name "Hyderabad Air Funnel Zones" \
  --layer-slug "hyderabad_air_funnel_zones" \
  --data-dir "data/Telangana/Hyderabad/air_funnel_zones" \
  --authority "Airports Authority of India" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# Hyderabad HMDA Extended Area (run fill_color first: FILL_COLOR_COMMANDS.md §48.2)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "hyderabad" \
  --layer-name "Hyderabad HMDA Extended Area" \
  --layer-slug "hyderabad_hmda_extended_area" \
  --data-dir "data/Telangana/Hyderabad/hmda_extended_area" \
  --authority "HMDA" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# Hyderabad: highways, metro-lines, rrr, ratan-tata-road (insert_hyderabad_data)
docker-compose exec web python manage.py insert_hyderabad_data --delete-existing

# ========== Maharashtra – Roads / Corridors (data/roads/*) ==========
# state/city/layer from paths; --data-dir = data/roads/<subdir>

# 1. maharashtra/navi-mumbai/kharghar_coastal_road
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "navi-mumbai" \
  --layer-name "Kharghar Coastal Road" \
  --layer-slug "kharghar_coastal_road" \
  --data-dir "data/roads/Kharghar" \
  --authority "Mumbai Metropolitan Region Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 2. maharashtra/mumbai/versova_bhayander_coastal_road (create data/roads/versova-bhayander/ if needed)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "mumbai" \
  --layer-name "Versova-Bhayander Coastal Road" \
  --layer-slug "versova_bhayander_coastal_road" \
  --data-dir "data/roads/versova-bhayander" \
  --authority "Mumbai Metropolitan Region Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 3. maharashtra/pune/pune_ring_roads
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "pune" \
  --layer-name "Pune Ring Roads" \
  --layer-slug "pune_ring_roads" \
  --data-dir "data/roads/pune-ring-road" \
  --authority "Pune Metropolitan Region Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 4. maharashtra/chandrapur/nagpur_chandrapur_expressway
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "chandrapur" \
  --layer-name "Nagpur-Chandrapur Expressway" \
  --layer-slug "nagpur_chandrapur_expressway" \
  --data-dir "data/roads/Nagpur-Chandrapur Expressway" \
  --authority "Maharashtra State Road Development Corporation" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 5. maharashtra/gondia/nagpur_gondia_expressway
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "gondia" \
  --layer-name "Nagpur-Gondia Expressway" \
  --layer-slug "nagpur_gondia_expressway" \
  --data-dir "data/roads/Nagpur-Gondia Expressway" \
  --authority "Maharashtra State Road Development Corporation" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 6. maharashtra/navi-mumbai/virar_alibaug_multimodal_corridor
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "navi-mumbai" \
  --layer-name "Virar-Alibaug Multi Modal Corridor" \
  --layer-slug "virar_alibaug_multimodal_corridor" \
  --data-dir "data/roads/Virar-Alibaug Multi Modal Corridor" \
  --authority "Mumbai Metropolitan Region Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 7. maharashtra/yavatmal/shaktipeeth_expressway
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "yavatmal" \
  --layer-name "Nagpur-Goa Shaktipeeth Expressway" \
  --layer-slug "shaktipeeth_expressway" \
  --data-dir "data/roads/Nagpur-Goa Shaktipeeth" \
  --authority "Maharashtra State Road Development Corporation" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 8. maharashtra/mumbai/madh_versova_bridge
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "mumbai" \
  --layer-name "Madh-Versova Bridge" \
  --layer-slug "madh_versova_bridge" \
  --data-dir "data/roads/madh" \
  --authority "Mumbai Metropolitan Region Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 9. maharashtra/mumbai/uttan_virar_sea_link
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "mumbai" \
  --layer-name "Uttan-Virar Sea Link" \
  --layer-slug "uttan_virar_sea_link" \
  --data-dir "data/roads/Uttan" \
  --authority "Mumbai Metropolitan Region Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 10. maharashtra/mumbai/vadhvan_tawa_connector_expressway
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "mumbai" \
  --layer-name "Vadhvan-Tawa Connector Expressway" \
  --layer-slug "vadhvan_tawa_connector_expressway" \
  --data-dir "data/roads/Vadhvan" \
  --authority "Mumbai Metropolitan Region Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 11. maharashtra/navi-mumbai/revas_karanja_bridge
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "navi-mumbai" \
  --layer-name "Revas-Karanja Bridge" \
  --layer-slug "revas_karanja_bridge" \
  --data-dir "data/roads/Revas-Karanja Bridge" \
  --authority "Mumbai Metropolitan Region Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 12. maharashtra/mumbai/bandra_versova_sea_link
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "mumbai" \
  --layer-name "Bandra-Versova Sea Link" \
  --layer-slug "bandra_versova_sea_link" \
  --data-dir "data/roads/bandra" \
  --authority "Mumbai Metropolitan Region Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 13. maharashtra/thane/thane_coastal_road (create data/roads/thane-coastal/ if needed)
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "thane" \
  --layer-name "Thane Coastal Road" \
  --layer-slug "thane_coastal_road" \
  --data-dir "data/roads/thane-coastal" \
  --authority "Mumbai Metropolitan Region Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 14. maharashtra/pune/pune_bengaluru_expressway
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "pune" \
  --layer-name "Pune-Bengaluru Expressway" \
  --layer-slug "pune_bengaluru_expressway" \
  --data-dir "data/roads/pune-bengaluru" \
  --authority "Pune Metropolitan Region Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 15. maharashtra/mumbai/konkan_expressway
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "mumbai" \
  --layer-name "Konkan Expressway" \
  --layer-slug "konkan_expressway" \
  --data-dir "data/roads/konkan" \
  --authority "Mumbai Metropolitan Region Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# 16. maharashtra/pune/talegaon_chakan_shikrapur_corridor
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "pune" \
  --layer-name "Talegaon-Chakan-Shikrapur Corridor" \
  --layer-slug "talegaon_chakan_shikrapur_corridor" \
  --data-dir "data/roads/Talegaon" \
  --authority "Pune Metropolitan Region Development Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# ========== Tamil Nadu – Chennai CRZ ==========
# state/city/layer: tamil-nadu/chennai/crz_layer
# Exclude line files (HTL, LTL, CRZ Boundary) so only zone polygons are inserted
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "chennai" \
  --layer-name "Chennai CRZ Layer" \
  --layer-slug "crz_layer" \
  --data-dir "data/TamilNadu CRZ layers_processed" \
  --authority "Tamil Nadu State Coastal Zone Management Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --exclude "Tide Line,CRZ (Coastal Regulation Zone) Boundary" \
  --delete-existing

# ========== Andhra Pradesh – Yanam CRZ ==========
# state/city/layer: andhra-pradesh/yanam_crz/yanam_crz_layer
# Exclude line files (HTL, LTL, CRZ Boundary) so only zone polygons are inserted
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "yanam_crz" \
  --layer-name "Yanam CRZ Layer" \
  --layer-slug "yanam_crz_layer" \
  --data-dir "data/Yanam CRZ layers_processed" \
  --authority "Puducherry State Coastal Zone Management Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --exclude "Tide Line,CRZ (Coastal Regulation Zone) Boundary" \
  --delete-existing

# ========== Dadra and Nagar Haveli and Daman and Diu – Diu CRZ ==========
# state/city/layer: dadra-nagar-haveli-daman-diu/diu_crz/diu_crz_layers
# Exclude line files (HTL, LTL, CRZ Boundary) so only zone polygons are inserted
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "diu_crz" \
  --layer-name "Diu CRZ Layer" \
  --layer-slug "diu_crz_layers" \
  --data-dir "data/crz/Diu CRZ layers_processed" \
  --authority "Dadra and Nagar Haveli and Daman and Diu Coastal Zone Management Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# ========== Puducherry – Karaikal CRZ ==========
# state/city/layer: puducherry/karaikal_crz/karaikal_crz_layer
# Exclude line files (HTL, LTL, CRZ Boundary) so only zone polygons are inserted
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "karaikal_crz" \
  --layer-name "Karaikal CRZ Layer" \
  --layer-slug "karaikal_crz_layer" \
  --data-dir "data/crz/Karaikal CRZ layers_processed" \
  --authority "Puducherry State Coastal Zone Management Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# ========== Gujarat – Gujarat CRZ ==========
# state/city/layer: gujarat/gujarat_crz/gujarat_crz_layer
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "gujarat_crz" \
  --layer-name "Gujarat CRZ Layer" \
  --layer-slug "gujarat_crz_layer" \
  --data-dir "data/crz/Gujarat CRZ layers_processed" \
  --authority "Gujarat Coastal Zone Management Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# ========== Kerala – Kerala CRZ ==========
# state/city/layer: kerala/kerala_crz/kerala_crz_layer
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "kerela_crz" \
  --layer-name "Kerela CRZ Layer" \
  --layer-slug "kerela_crz_layer" \
  --data-dir "data/crz/Kerala CRZ layers_processed" \
  --authority "Kerala State Coastal Zone Management Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# ========== Maharashtra – Maharashtra CRZ ==========
# state/city/layer: maharashtra/maharashtra_crz/maharashtra_crz_layer
docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "maharashtra_crz" \
  --layer-name "Maharashtra CRZ Layer" \
  --layer-slug "maharashtra_crz_layer" \
  --data-dir "data/crz/Maharashtra CRZ layers_processed" \
  --authority "Maharashtra Coastal Zone Management Authority" \
  --min-zoom 8 \
  --max-zoom 18 \
  --delete-existing

# Insert HMDA Masterplan Roads layer for Hyderabad
# State/city/layer: telangana/hyderabad/hyderabad_master_plan_roads
# Data: data/telangana/hyderabad/roads/HMDA_masterplan_roads_merged.geojson (and tiles in roads/)

docker-compose exec web python manage.py insert_masterplan_layer \
  --city-slug "hyderabad" \
  --layer-name "Hyderabad Master Plan Roads (HMDA)" \
  --layer-slug "hyderabad_master_plan_roads" \
  --data-dir "data/telangana/hyderabad/roads" \
  --authority "Hyderabad Metropolitan Development Authority" \
  --min-zoom 5 \
  --max-zoom 18 \
  --delete-existing