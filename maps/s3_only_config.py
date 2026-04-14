# maps/s3_only_config.py
"""
S3-only tile serving reference (standalone). Production uses geo_mapping/settings.py.

Tiles use direct S3 (AWS_S3_TILE_DOMAIN). Optional CloudFront only if CLOUDFRONT_DOMAIN
and USE_CLOUDFRONT are set.
"""

# S3-Only Tile Serving Settings
S3_ONLY_TILE_SERVING = True

# Disable local tile storage
DISABLE_LOCAL_TILES = True

AWS_STORAGE_BUCKET_NAME = 'gis-portal-layers'
AWS_S3_REGION_NAME = 'ap-south-1'
AWS_S3_TILE_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'

CLOUDFRONT_DOMAIN = ''
TILE_CDN_DOMAIN = AWS_S3_TILE_DOMAIN
CLOUDFLARE_TILE_DOMAIN = AWS_S3_TILE_DOMAIN

USE_CLOUDFRONT = False

CLOUDFRONT_PATH_PREFIXES = []

TILE_PROXY_CACHE_TTL = 3600

GENERATE_TILES_DIRECT_TO_S3 = True
SKIP_LOCAL_TILE_STORAGE = True

TILE_SERVING_FALLBACK_ORDER = [
    'cloudfront',
    's3_direct',
    'on_demand',
]

TILE_CACHE_HEADERS = {
    'png': {
        'CacheControl': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        'ContentType': 'image/png'
    },
    'mvt': {
        'CacheControl': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        'ContentType': 'application/vnd.mapbox-vector-tile'
    }
}

TILE_REQUEST_TIMEOUT = 5
MAX_CONCURRENT_TILE_REQUESTS = 10

RETRY_FAILED_TILE_REQUESTS = True
MAX_TILE_REQUEST_RETRIES = 3
RETRY_DELAY = 1

ENABLE_TILE_SERVING_LOGS = True
LOG_TILE_SOURCE = True
