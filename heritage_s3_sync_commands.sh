#!/bin/bash
# S3 sync commands for heritage site tiles

# Bengaluru Heritage Sites
aws s3 sync heritage_tiles/bengaluru_fort s3://gis-portal-layers/karnataka/bengaluru/heritage/bengaluru_fort/ --delete

aws s3 sync heritage_tiles/bhoga_nandishwara_temple s3://gis-portal-layers/karnataka/bengaluru/heritage/bhoga_nandishwara_temple/ --delete

aws s3 sync heritage_tiles/devanahalli_fort s3://gis-portal-layers/karnataka/bengaluru/heritage/devanahalli_fort/ --delete

aws s3 sync heritage_tiles/kolaramma_temple s3://gis-portal-layers/karnataka/bengaluru/heritage/kolaramma_temple/ --delete

aws s3 sync heritage_tiles/someswara_temple s3://gis-portal-layers/karnataka/bengaluru/heritage/someswara_temple/ --delete

aws s3 sync heritage_tiles/tippu_sultan_birth_palace s3://gis-portal-layers/karnataka/bengaluru/heritage/tippu_sultan_birth_palace/ --delete

aws s3 sync heritage_tiles/tippu_sultan_palace s3://gis-portal-layers/karnataka/bengaluru/heritage/tippu_sultan_palace/ --delete

# Hyderabad Heritage Sites
aws s3 sync heritage_tiles/hyderabad_ancient_mound s3://gis-portal-layers/telangana/hyderabad/heritage/ancient_mound/ --delete

aws s3 sync heritage_tiles/hyderabad_charminar s3://gis-portal-layers/telangana/hyderabad/heritage/charminar/ --delete

aws s3 sync heritage_tiles/hyderabad_golconda_fort s3://gis-portal-layers/telangana/hyderabad/heritage/golconda_fort/ --delete

