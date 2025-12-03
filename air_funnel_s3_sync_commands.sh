#!/bin/bash
# Commands to sync air funnel tiles to S3 for all 20 cities

# 1. Ayodhya
aws s3 sync ayodhya_air_funnel_tiles s3://gis-portal-layers/uttar-pradesh/ayodhya/ayodhya_air_funnel_zones/ --delete

# 2. Kozhikode (Calicut)
aws s3 sync kozhikode_air_funnel_tiles s3://gis-portal-layers/kerala/kozhikode/kozhikode_air_funnel_zones/ --delete

# 3. Ahmedabad - Gandhinagar
aws s3 sync ahmedabad_gandhinagar_air_funnel_tiles s3://gis-portal-layers/gujarat/ahmedabad-gandhinagar/ahmedabad_air_funnel_zones/ --delete

# 4. Bhubaneswar
aws s3 sync bhubaneswar_air_funnel_tiles s3://gis-portal-layers/odisha/bhubaneshwar/bhubaneshwar_air_funnel_zones/ --delete

# 5. Chennai
aws s3 sync chennai_air_funnel_tiles s3://gis-portal-layers/tamil-nadu/chennai/chennai_air_funnel_zones/ --delete

# 6. Delhi-IGI
aws s3 sync delhi_igi_air_funnel_tiles s3://gis-portal-layers/delhi/delhi-ncr/delhi_air_funnel_zones/ --delete

# 7. Diu
aws s3 sync diu_air_funnel_tiles s3://gis-portal-layers/dadra-nagar-haveli-daman-diu/daman-and-diu/diu_air_funnel_zones/ --delete

# 8. Dohlera
aws s3 sync dohlera_air_funnel_tiles s3://gis-portal-layers/gujarat/dholera/dholera_air_funnel_zones/ --delete

# 9. Guwahati
aws s3 sync guwahati_air_funnel_tiles s3://gis-portal-layers/assam/guwahati/guwahati_air_funnel_zones/ --delete

# 10. Jaipur
aws s3 sync jaipur_air_funnel_tiles s3://gis-portal-layers/rajasthan/jaipur/jaipur_air_funnel_zones/ --delete

# 11. Kochi
aws s3 sync kochi_air_funnel_tiles s3://gis-portal-layers/kerala/kochi/kochi_air_funnel_zones/ --delete

# 12. Lucknow
aws s3 sync lucknow_air_funnel_tiles s3://gis-portal-layers/uttar-pradesh/lucknow/lucknow_air_funnel_zones/ --delete

# 13. Nagpur
aws s3 sync nagpur_air_funnel_tiles s3://gis-portal-layers/maharashtra/nagpur/nagpur_air_funnel_zones/ --delete

# 14. Navi Mumbai
aws s3 sync navi_mumbai_air_funnel_tiles s3://gis-portal-layers/maharashtra/mumbai/mumbai_air_funnel_zones/ --delete

# 15. Noida (Jewar)
aws s3 sync noida_jewar_air_funnel_tiles s3://gis-portal-layers/delhi-ncr/delhi-ncr/noida_air_funnel_zones/ --delete

# 16. Patna
aws s3 sync patna_air_funnel_tiles s3://gis-portal-layers/bihar/patna/patna_air_funnel_zones/ --delete

# 17. Raigarh
aws s3 sync raigarh_air_funnel_tiles s3://gis-portal-layers/chhatisgarh/raigarh/raigarh_air_funnel_zones/ --delete

# 18. Raipur
aws s3 sync raipur_air_funnel_tiles s3://gis-portal-layers/chhatisgarh/new-raipur/raipur_air_funnel_zones/ --delete

# 19. Tirupati
aws s3 sync tirupati_air_funnel_tiles s3://gis-portal-layers/andhra-pradesh/tirupati/tirupati_air_funnel_zones/ --delete

# 20. Warangal
aws s3 sync warangal_air_funnel_tiles s3://gis-portal-layers/andhra-pradesh/warangal/warangal_air_funnel_zones/ --delete



aws s3 sync amaravati_tiles_seamless s3://gis-portal-layers/andhra-pradesh/amaravati/amaravati_masterplan/ --delete

aws s3 sync bhubaneshwar_tiles_seamless s3://gis-portal-layers/odisha/bhubaneswar/bhubaneswar_masterplan/ --delete

aws s3 sync faridabad_tiles_seamless s3://gis-portal-layers/delhi/delhi-ncr/faridabad_masterplan/ --delete

aws s3 sync noida_tiles_seamless s3://gis-portal-layers/delhi/delhi-ncr/noida_masterplan/ --delete

aws s3 sync delhi_tiles_seamless s3://gis-portal-layers/delhi/delhi-ncr/delhi_masterplan/ --delete

aws s3 sync greater_noida_tiles_seamless s3://gis-portal-layers/delhi/delhi-ncr/greater_noida_masterplan/ --delete

aws s3 sync gurgaon_tiles_seamless s3://gis-portal-layers/delhi/delhi-ncr/gurugram_masterplan/ --delete

aws s3 sync yamuna_expressway_tiles_seamless s3://gis-portal-layers/delhi/delhi-ncr/yamuna_expressway_masterplan/ --delete

aws s3 sync chandigarh_tiles_seamless_fast s3://gis-portal-layers/punjab/chandigarh/chandigarh_masterplan/ --delete

aws s3 sync jaipur_tiles_seamless_fast s3://gis-portal-layers/rajasthan/jaipur/jaipur_masterplan/ --delete

aws s3 sync puducherry_tiles_seamless s3://gis-portal-layers/puducherry/puducherry/puducherry_masterplan/ --delete