# maps/s3_only_config.py
"""
S3-Only Tile Serving Configuration
This configuration ensures tiles are served only from S3/CloudFront without local storage.
"""

# S3-Only Tile Serving Settings
S3_ONLY_TILE_SERVING = True

# Disable local tile storage
DISABLE_LOCAL_TILES = True

# CloudFront Configuration
CLOUDFRONT_DOMAIN = 'd17yosovmfjm4.cloudfront.net'
CLOUDFRONT_ENABLED = True

# Tile proxy: paths served via CloudFront; all others via S3 only (no fallback)
CLOUDFRONT_PATH_PREFIXES = [
    'karnataka/bengaluru/',
    'telangana/hyderabad/',
    'andhra-pradesh/amaravati/',
    'land-plot/',
]

# Tile proxy server-side cache TTL (seconds); 0 = no cache
TILE_PROXY_CACHE_TTL = 3600

# S3 Configuration
AWS_STORAGE_BUCKET_NAME = 'gis-portal-layers'
AWS_S3_REGION_NAME = 'ap-south-1'

# Tile Generation Settings
GENERATE_TILES_DIRECT_TO_S3 = True
SKIP_LOCAL_TILE_STORAGE = True

# Fallback Configuration (not used by tile proxy; proxy uses path-based CloudFront vs S3 only, no fallback)
TILE_SERVING_FALLBACK_ORDER = [
    'cloudfront',
    's3_direct',
    'on_demand',
]

# No-Cache Settings
TILE_CACHE_HEADERS = {
    'png': {
        'CacheControl': 'no-cache, no-store, must-revalidate',  # No caching
        'Pragma': 'no-cache',
        'Expires': '0',
        'ContentType': 'image/png'
    },
    'mvt': {
        'CacheControl': 'no-cache, no-store, must-revalidate',  # No caching
        'Pragma': 'no-cache',
        'Expires': '0',
        'ContentType': 'application/vnd.mapbox-vector-tile'
    }
}

# Performance Settings
TILE_REQUEST_TIMEOUT = 5  # seconds
MAX_CONCURRENT_TILE_REQUESTS = 10

# Error Handling
RETRY_FAILED_TILE_REQUESTS = True
MAX_TILE_REQUEST_RETRIES = 3
RETRY_DELAY = 1  # seconds

# Monitoring
ENABLE_TILE_SERVING_LOGS = True
LOG_TILE_SOURCE = True  # Log which source served the tile (CloudFront/S3)
