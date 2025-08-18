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

# S3 Configuration
AWS_STORAGE_BUCKET_NAME = 'gis-portal-layers'
AWS_S3_REGION_NAME = 'ap-south-1'

# Tile Generation Settings
GENERATE_TILES_DIRECT_TO_S3 = True
SKIP_LOCAL_TILE_STORAGE = True

# Fallback Configuration
TILE_SERVING_FALLBACK_ORDER = [
    'cloudfront',  # Primary: CloudFront CDN
    's3_direct',   # Secondary: S3 Direct
    'on_demand'    # Tertiary: On-demand generation (optional)
]

# Cache Settings
TILE_CACHE_HEADERS = {
    'png': {
        'CacheControl': 'public, max-age=31536000',  # 1 year
        'ContentType': 'image/png'
    },
    'mvt': {
        'CacheControl': 'public, max-age=86400',     # 1 day
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
