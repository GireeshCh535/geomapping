#!/bin/bash
# S3 sync commands for all monument tiles

# Karnataka - Bangalore
aws s3 sync monument_tiles/bangalore_fort s3://gis-portal-layers/karnataka/bangalore/bangalore_fort/ --delete
aws s3 sync monument_tiles/bangalore_old_dungeon_fort s3://gis-portal-layers/karnataka/bangalore/old_dungeon_fort/ --delete
aws s3 sync monument_tiles/bangalore_prehistoric_site s3://gis-portal-layers/karnataka/bangalore/prehistoric_site/ --delete
aws s3 sync monument_tiles/bangalore_prehistoric_site_1 s3://gis-portal-layers/karnataka/bangalore/monuments/prehistoric_site_1/ --delete
aws s3 sync monument_tiles/bangalore_tipu_birth_palace s3://gis-portal-layers/karnataka/bangalore/monuments/tipu_birth_palace/ --delete
aws s3 sync monument_tiles/bangalore_tipu_palace s3://gis-portal-layers/karnataka/bangalore/monuments/tipu_palace/ --delete

# Karnataka - Kolar
aws s3 sync monument_tiles/kolar_bhoganandishwara_temple s3://gis-portal-layers/karnataka/kolar//bhoganandishwara_temple/ --delete
aws s3 sync monument_tiles/kolar_haider_ali_birth_place s3://gis-portal-layers/karnataka/kolar/haider_ali_birth_place/ --delete
aws s3 sync monument_tiles/kolar_kolaramma_temple s3://gis-portal-layers/karnataka/kolar/kolaramma_temple/ --delete
aws s3 sync monument_tiles/kolar_prehistoric_site s3://gis-portal-layers/karnataka/kolar/prehistoric_site/ --delete
aws s3 sync monument_tiles/kolar_ramalingesvara_temples s3://gis-portal-layers/karnataka/kolar/ramalingesvara_temples/ --delete
aws s3 sync monument_tiles/kolar_somesvara_temple s3://gis-portal-layers/karnataka/kolar/somesvara_temple/ --delete

# Karnataka - Tumkur
aws s3 sync monument_tiles/tumkur_channigaraya_temple s3://gis-portal-layers/karnataka/tumkur/channigaraya_temple/ --delete
aws s3 sync monument_tiles/tumkur_fort s3://gis-portal-layers/karnataka/tumkur/fort/ --delete
aws s3 sync monument_tiles/tumkur_juma_masjid s3://gis-portal-layers/karnataka/tumkur/juma_masjid/ --delete
aws s3 sync monument_tiles/tumkur_keadresvara_temple s3://gis-portal-layers/karnataka/tumkur/keadresvara_temple/ --delete
aws s3 sync monument_tiles/tumkur_malik_rihan_darga s3://gis-portal-layers/karnataka/tumkur/malik_rihan_darga/ --delete
aws s3 sync monument_tiles/tumkur_onnakesava_temple s3://gis-portal-layers/karnataka/tumkur/onnakesava_temple/ --delete

# Telangana - Hyderabad
aws s3 sync monument_tiles/hyderabad_charminar s3://gis-portal-layers/telangana/hyderabad/charminar/ --delete
aws s3 sync monument_tiles/hyderabad_golconda_fort s3://gis-portal-layers/telangana/hyderabad/golconda_fort/ --delete

# Telangana - Sangareddy
aws s3 sync monument_tiles/sangareddy_ancient_mound s3://gis-portal-layers/telangana/sangareddy/ancient_mound/ --delete

