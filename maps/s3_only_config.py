# maps/s3_only_config.py
"""
S3-only tile serving reference (standalone). Production uses geo_mapping/settings.py.

Active split: direct S3 (AWS_S3_TILE_DOMAIN), public tile host (TILE_CDN_DOMAIN),
AWS CloudFront host (CLOUDFRONT_DOMAIN) for some URL templates.
CLOUDFLARE_TILE_DOMAIN: reserved for a future all-Cloudflare migration — not used by tile logic yet.
"""

# S3-Only Tile Serving Settings
S3_ONLY_TILE_SERVING = True

# Disable local tile storage
DISABLE_LOCAL_TILES = True

AWS_STORAGE_BUCKET_NAME = 'gis-portal-layers'
AWS_S3_REGION_NAME = 'ap-south-1'
AWS_S3_TILE_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'

CLOUDFRONT_DOMAIN = 'd17yosovmfjm4.cloudfront.net'
TILE_CDN_DOMAIN = 'tiles.citylands.in'
# Future Cloudflare-only cutover placeholder (keep equal to TILE_CDN_DOMAIN until you switch).
CLOUDFLARE_TILE_DOMAIN = TILE_CDN_DOMAIN

CLOUDFRONT_ENABLED = True

CLOUDFRONT_PATH_PREFIXES = [
    'karnataka/bengaluru/',
    'telangana/hyderabad/',
    'andhra-pradesh/amaravati/',
    'land-plot/',
]

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
