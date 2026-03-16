"""
Django settings for geo_mapping project
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env into os.environ when running locally (Docker sets env via compose, so those take precedence)
_env_file = BASE_DIR / '.env'
if _env_file.exists():
    with open(_env_file, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, value = line.partition('=')
                key, value = key.strip(), value.strip()
                if key:
                    if value.startswith(('"', "'")) and value[0] == value[-1]:
                        value = value[1:-1].strip()
                    os.environ.setdefault(key, value)

# SECRET KEY
SECRET_KEY = "django-insecure-9xdea)mc6dhr@)lrhn65!&!uc+#z6nlajj8j091eswp$$2jf!#"

# DEBUG
DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() == 'true'

# ALLOWED HOSTS (include IP with ports when Host header has port, e.g. behind nginx)
_required_hosts = ['*', '3.108.10.59', '3.108.10.59:80', '3.108.10.59:443', 'layers.1acre.in']
_allowed = os.getenv('DJANGO_ALLOWED_HOSTS')
if _allowed:
    ALLOWED_HOSTS = list(dict.fromkeys(
        [h.strip() for h in _allowed.split(',') if h.strip()] + _required_hosts
    ))
else:
    ALLOWED_HOSTS = _required_hosts

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'https://localhost:8000',
    'http://localhost:3000',
    'https://layers.1acre.in',
    'http://layers.1acre.in',  # if you also use HTTP
    'https://gis-map.1acre.in',  # Legacy domain (keep for backward compatibility)
    'http://3.108.10.59',  # Direct IP access
    'https://3.108.10.59',  # Direct IP access (HTTPS)
    # Cloudflare Tunnel (quick tunnels; add your current URL when it changes)
    'https://jungle-played-zoo-remedy.trycloudflare.com',
    # Local dev (frontend on different port or origin)
    'http://localhost:8000',
    'http://localhost:3001',
    'http://localhost:3000',
    'http://127.0.0.1:8000',
    'http://127.0.0.1:3000',
]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True


# GDAL/GEOS Configuration for Docker
if os.getenv('DJANGO_DB_HOST'):  # Docker environment
    pass  # Let Django auto-detect
elif os.name == 'posix':  # Local Mac development
    import platform
    if platform.machine() == 'arm64':  # M1/M2 Mac
        GDAL_LIBRARY_PATH = '/opt/homebrew/opt/gdal/lib/libgdal.dylib'
        GEOS_LIBRARY_PATH = '/opt/homebrew/opt/geos/lib/libgeos_c.dylib'
        PROJ_LIB = '/opt/homebrew/opt/proj/share/proj'
        os.environ.update({
            'GDAL_LIBRARY_PATH': GDAL_LIBRARY_PATH,
            'GEOS_LIBRARY_PATH': GEOS_LIBRARY_PATH,
            'PROJ_LIB': PROJ_LIB
        })

# INSTALLED APPS
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes", 
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'django.contrib.gis',
    'corsheaders',
    'rest_framework',
    'django_filters',
    'drf_spectacular',
    'maps',
]

# MIDDLEWARE
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'geo_mapping.middleware.RestrictAPIOriginMiddleware',  # Only allow API from frontend origins
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# CORS – restrict to frontend origins so only your app can call the API from browsers.
# (Avoid putting an API key in frontend code; it would be visible in DevTools/headers.
# Restricting by origin is the right approach for browser clients.)
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    'https://layers.1acre.in',
    'http://layers.1acre.in',
    'https://gis-map.1acre.in',
    'http://gis-map.1acre.in',
    'https://lita-unsarcastic-serina.ngrok-free.dev',
    'https://fantasy-correction-analysis-communication.trycloudflare.com',
    'http://3.108.10.59',
    'https://3.108.10.59',
    'http://localhost:8000',
    'http://localhost:3000',
    'http://localhost:3001',
    'http://localhost:5173',   # Vite default
    'http://127.0.0.1:8000',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:3001',
    'http://127.0.0.1:5173',
]
# Optional: allow extra origins from env (comma-separated), e.g. for new frontend domains
_extra_origins = os.getenv('CORS_EXTRA_ORIGINS', '')
if _extra_origins:
    CORS_ALLOWED_ORIGINS = list(CORS_ALLOWED_ORIGINS) + [o.strip() for o in _extra_origins.split(',') if o.strip()]
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
]
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_CREDENTIALS = True

# When True, /api/ requests are rejected if Origin/Referer is present and not in CORS_ALLOWED_ORIGINS.
# Set to False (or env RESTRICT_API_ORIGIN=false) to allow any origin (e.g. local testing).
RESTRICT_API_ORIGIN = os.getenv('RESTRICT_API_ORIGIN', 'true').lower() == 'true'

ROOT_URLCONF = "geo_mapping.urls"

# TEMPLATES
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        'DIRS': [BASE_DIR / 'templates'],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request", 
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "geo_mapping.wsgi.application"

# DATABASE - Using django-db-connection-pool for high concurrency
# This provides proper connection pooling for 1000+ concurrent users
DATABASES = {
    'default': {
        'ENGINE': 'dj_db_conn_pool.backends.postgis',
        'NAME': os.getenv('DJANGO_DB_NAME', 'geo_mapping_db'),
        'USER': os.getenv('DJANGO_DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DJANGO_DB_PASSWORD', 'postgres'),
        'HOST': os.getenv('DJANGO_DB_HOST', 'localhost'),
        # 'HOST': os.getenv('DJANGO_DB_HOST', 'db'),
        'PORT': os.getenv('DJANGO_DB_PORT', '5432'),
        'CONN_MAX_AGE': 0,  # Set to 0 when using connection pool
        'CONN_HEALTH_CHECKS': True,  # Django 4.1+: Check connection health
        'OPTIONS': {
            'connect_timeout': 10,
        },
        # Connection pool settings for high concurrency
        'POOL_OPTIONS': {
            'POOL_SIZE': 20,  # Number of connections per worker process
            'MAX_OVERFLOW': 10,  # Additional connections beyond pool_size
            'POOL_RECYCLE': 3600,  # Recycle connections after 1 hour
            'POOL_PRE_PING': True,  # Verify connections before using
            'ECHO': False,  # Set to True for SQL debugging
        },
    }
}

# REDIS CACHE
# Get Redis URL from environment (docker-compose sets this)
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/1')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            # Connection pool settings for better performance
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            # Socket timeout settings
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,
        },
        'KEY_PREFIX': 'geomapping',
        'TIMEOUT': 300,  # Default cache timeout: 5 minutes
    },
    # Separate cache for coordinate searches (optional, for isolation)
    'coordinates': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL.replace('/1', '/2') if '/1' in REDIS_URL else REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 100,  # More connections for high-traffic endpoint
                'retry_on_timeout': True,
            },
        },
        'KEY_PREFIX': 'coord_search',
        'TIMEOUT': 300,
    }
}

# API KEY (required for all API access except webhooks; leave empty to disable)
API_KEY = os.getenv('GEO_MAPPING_API_KEY', '').strip()

# REST FRAMEWORK
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'maps.authentication.APIKeyAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'maps.permissions.AllowIfWebhookOrHasAPIKey',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '200/hour',   # anonymous (e.g. from frontend) rate limit
        'user': '1000/hour',
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# PASSWORD VALIDATION
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# INTERNATIONALIZATION
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# STATIC FILES
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
_static_dir = BASE_DIR / 'static'
_1acre_icons_dir = BASE_DIR / '1acre-icons'
STATICFILES_DIRS = []
if _static_dir.exists():
    STATICFILES_DIRS.append(_static_dir)
# Serve 1acre-icons at /static/1acre-icons/{type}/{folder}/{marker_id}.svg (e.g. plot/owner/plot-owner-1.svg)
if _1acre_icons_dir.exists():
    STATICFILES_DIRS.append(('1acre-icons', _1acre_icons_dir))

# Custom StaticFiles configuration to explicitly exclude all tile files
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Ignore all tile-related files during static collection
STATICFILES_IGNORE_PATTERNS = [
    # PNG Tiles
    '*/tiles_png/*',
    '*/real_estate_tiles_png/*', 
    '**/tiles_png/**',
    '**/real_estate_tiles_png/**',
    
    # MVT Tiles  
    '*/tiles/*',
    '*/real_estate_tiles/*',
    '**/tiles/**',
    '**/real_estate_tiles/**',
    
    # Pattern-based exclusions
    '**/combined/*.png',
    '**/combined/*.mvt',
    '*/[0-9]*_[0-9]*_[0-9]*.png',  # Tile pattern: z_x_y.png
    '*/[0-9]*_[0-9]*_[0-9]*.mvt',  # Tile pattern: z_x_y.mvt
    
    # Be very careful with this - only if you're sure
    # '*.png',  # This would exclude ALL PNGs - use cautiously
]

# Media files (still local for user uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ===================================
# AWS S3 & CLOUDFRONT - TILE-ONLY CONFIGURATION  
# ===================================

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = 'AKIAW3MEBMOOEQKR3BXV'
AWS_SECRET_ACCESS_KEY = '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'
AWS_S3_REGION_NAME = "ap-south-1"
AWS_STORAGE_BUCKET_NAME = 'gis-portal-layers'
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'

# CloudFront Configuration - TILES ONLY
# Tiles are stored in S3; CloudFront is the CDN in front. Default flow: request -> Django 302 -> CloudFront -> S3.
CLOUDFRONT_DOMAIN = 'd17yosovmfjm4.cloudfront.net'
CLOUDFRONT_DISTRIBUTION_ID = os.getenv('CLOUDFRONT_DISTRIBUTION_ID', '')  # Set via environment variable
USE_CLOUDFRONT = os.getenv('USE_CLOUDFRONT', 'True').lower() == 'true'
ENABLE_CLOUDFRONT_INVALIDATION = os.getenv('ENABLE_CLOUDFRONT_INVALIDATION', 'True').lower() == 'true'

# Tile proxy: paths served via CloudFront; all others via S3 only (no fallback)
CLOUDFRONT_PATH_PREFIXES = [
    'karnataka/bengaluru/',
    'telangana/hyderabad/',
    'andhra-pradesh/amaravati/',
    'land-plot/',
]
# Tile proxy server-side cache TTL in seconds (0 = no cache)
TILE_PROXY_CACHE_TTL = 3600

# All masterplan layer slugs (from maps/views.py) – reference list for CloudFront path prefixes
MASTERPLAN_LAYER_SLUGS = [
    # Bengaluru / BMRDA
    'bengaluru_anekal_masterplan',
    'bengaluru_chikkaballapura_masterplan',
    'bengaluru_hosakote_masterplan',
    'bengaluru_nelamangala_masterplan',
    'bengaluru_master_plan_2015',
    'bengaluru_masterplan_roads',
    # Tamil Nadu
    'coimbatore_master_plan',
    'hosur_master_plan',
    'chennai_master_plan',
    'tirupati_masterplan',
    # Kerala
    'kochi_master_plan',
    'kannur_masterplan',
    'kollam_masterplan',
    'kozhikode_masterplan',
    'thiruvananthapuram_masterplan',
    'thrissur_masterplan',
    # Odisha / Andhra
    'cuttack_masterplan',
    'vgtm_masterplan',
    'kakinada_masterplan',
    'amaravati_master_plan',
    'amaravati_masterplan',
    'bhubaneswar_masterplan',
    # Madhya Pradesh
    'mandideep_masterplan',
    'bhopal_masterplan',
    'pithampur_masterplan',
    # Rajasthan / Gujarat
    'ajmer_masterplan',
    'ahmedabad_masterplan',
    'vadodara_masterplan',
    'gift_city_masterplan',
    # Punjab / Haryana / NCR
    'mohali_sas_nagar_masterplan',
    'derabassi_masterplan',
    'banur_masterplan',
    'mullanpur_masterplan',
    'kharar_masterplan',
    'sonipat_kundli_masterplan',
    'sonipat_masterplan',
    'arogya_dham_badsa_masterplan',
    'palwal_masterplan',
    'prithla_masterplan',
    'loni_masterplan',
    'bhagpat_baraut_khekra_masterplan',
    'modinagar_masterplan',
    'kharkhauda_masterplan',
    'ghaziabad_masterplan',
    'gurugram_masterplan',
    'faridabad_masterplan',
    'noida_masterplan',
    'greater_noida_masterplan',
    'yamuna_expressway_masterplan',
    'delhi_masterplan',
    'nuh_masterplan',
    'jhajjar_masterplan',
    'meerut_masterplan',
    'hodal_masterplan',
    'rewari_masterplan',
    'gohana_masterplan',
    'bhiwadi_masterplan',
    'alwar_masterplan',
    # Himachal / Chandigarh
    'pinjore_kalka_masterplan',
    'panchkula_extension_1_masterplan',
    'panchkula_masterplan',
    'dharuhera_masterplan',
    'zirakpur_masterplan',
    'chandigarh_masterplan',
    # UTs / North East / Other
    'daman_and_diu_masterplan',
    'dadra_and_nagar_haveli_masterplan',
    'patna_masterplan',
    'ayodhya_masterplan',
    'lucknow_masterplan',
    'varanasi_masterplan',
    'srinagar_masterplan',
    'guwahati_masterplan',
    'new_raipur_masterplan',
    'biappa_masterplan',
    'port_blair_masterplan',
    'itanagar_masterplan',
    'puducherry_masterplan',
    'jagdalpur_masterplan',
    # Telangana
    'hyderabad_masterplan',
    'warangal_master_plan',
    # Maharashtra
    'mumbai_masterplan',
    'pune_city_pmc_masterplan',
    'pimpri_chinchwad_masterplan',
    'pmrda_masterplan',
    'pmrda-masterplan-pmrda_masterplan',
    'nagpur_masterplan',
]

# S3-Only Tile Serving Configuration
S3_ONLY_TILE_SERVING = True
DISABLE_LOCAL_TILES = True
GENERATE_TILES_DIRECT_TO_S3 = True
SKIP_LOCAL_TILE_STORAGE = True

# ---------------------------------------------------------------------------
# TILE SERVING FLOW (see maps/views.py CloudFrontTileView, S3DirectTileView)
# ---------------------------------------------------------------------------
# 1) /api/tiles/... (no query): Django returns 302 to CloudFront URL.
#    Client then loads tile from CloudFront; CloudFront serves from S3.
#    Flow: Client -> Django (302) -> Client -> CloudFront -> S3.
#
# 2) /api/tiles/...?proxy=1 (debug): Django fetches tile (CloudFront then S3
#    fallback) and returns bytes. Flow: Client -> Django -> CloudFront or S3.
#    Requires ENABLE_TILE_PROXY_DEBUG (defaults to DEBUG).
#
# 3) /api/s3-tiles/...: Django fetches tile from S3 via boto3 and returns bytes.
#    Bypasses CloudFront. Flow: Client -> Django -> S3.
# ---------------------------------------------------------------------------
TILE_SERVING_FALLBACK_ORDER = [
    'cloudfront',  # Primary: CloudFront CDN (used when proxy=1)
    's3_direct',   # Secondary: S3 Direct URL fetch (used when proxy=1)
    'on_demand'    # Tertiary: on-demand generation if enabled
]
# When True, /api/tiles/...?proxy=1 returns tile bytes instead of redirect. Unset => use DEBUG.
_def = os.getenv('ENABLE_TILE_PROXY_DEBUG')
ENABLE_TILE_PROXY_DEBUG = (_def or '').lower() == 'true' if _def else DEBUG

# Tile No-Cache Headers
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


if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

# SESSION CONFIGURATION - No Caching
SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # Use database instead of cache
SESSION_COOKIE_AGE = 86400  # 24 hours

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',  # INFO and above (INFO, WARNING, ERROR) to console
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',  # INFO and above to file (not only errors)
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django_errors.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        # Suppress 404 warnings for tile endpoints (normal in tile serving)
        # Missing tiles are expected - not every coordinate has data
        'django.request': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',  # Only log errors, not 404 warnings
            'propagate': False,
        },
        # Suppress general Django 404 warnings (they're logged by our views at appropriate levels)
        'django.server': {
            'handlers': ['console'],
            'level': 'ERROR',  # Only log errors, suppress 404 warnings
            'propagate': False,
        },
        'maps.tile_generation': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'maps.s3_upload': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'maps.views': {
            'handlers': ['console'],
            'level': 'INFO',  # Change to DEBUG to see cache hits/misses
            'propagate': True,
        },
        # Log slow database queries
        'django.db.backends': {
            'level': 'WARNING',  # Change to DEBUG to see all queries
            'handlers': ['console'],
        },
    },
}

# Data directory
DATA_DIR = BASE_DIR / 'data'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===================================
# DRF SPECTACULAR - API DOCUMENTATION
# ===================================

SPECTACULAR_SETTINGS = {
    'TITLE': 'Geo Mapping API',
    'DESCRIPTION': 'A comprehensive API for geospatial data management and tile serving',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api/',
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
    },
    'TAGS': [
        {'name': 'states', 'description': 'State management endpoints'},
        {'name': 'cities', 'description': 'City management endpoints'},
        {'name': 'categories', 'description': 'Layer category management'},
        {'name': 'layers', 'description': 'Data layer management'},
        {'name': 'features', 'description': 'Geospatial features'},
        {'name': 'tiles', 'description': 'Map tile serving endpoints'},
        {'name': 'hierarchy', 'description': 'Hierarchical data structure'},
    ],
}

# ============================================
# COORDINATE SEARCH SPECIFIC SETTINGS
# ============================================

# Custom settings for coordinate search optimization
COORDINATE_SEARCH_SETTINGS = {
    'CACHE_TTL': 300,  # Cache results for 5 minutes
    'CACHE_TTL_EMPTY': 60,  # Cache empty results for 1 minute
    'COORDINATE_PRECISION': 5,  # Decimal places (5 = ~1.1m precision)
    'MAX_CONTAINING_FEATURES': 20,  # Max features to return
    'MAX_NEARBY_FEATURES': 10,
    'DEFAULT_NEARBY_RADIUS_METERS': 100,
    'MAX_NEARBY_RADIUS_METERS': 10000,
}

# ============================================
# DEVELOPER LISTING TILE GENERATION SETTINGS
# ============================================

# Backend API URL for fetching developer listing data
DEVELOPER_BACKEND_API_URL = os.getenv(
    'DEVELOPER_BACKEND_API_URL',
    'http://be.staging.1acre.in'  # Default to staging, can be overridden via env var
)

# --------------------------------------------
# Tile generation via SQS (no Lambda)
# Webhooks push jobs to SQS; local server polls SQS and runs tile gen + S3 upload.
# --------------------------------------------
TILE_SQS_QUEUE_URL = os.getenv('TILE_SQS_QUEUE_URL', '').strip()
TILE_CALLBACK_SECRET = os.getenv('TILE_CALLBACK_SECRET', '')
# Base URL for tile worker callback and MVT build (e.g. https://layers.1acre.in)
TILE_CALLBACK_BASE_URL = os.getenv('TILE_CALLBACK_BASE_URL', '')