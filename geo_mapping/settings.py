"""
Django settings for geo_mapping project
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# SECRET KEY
SECRET_KEY = "django-insecure-9xdea)mc6dhr@)lrhn65!&!uc+#z6nlajj8j091eswp$$2jf!#"

# DEBUG
DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() == 'true'

# ALLOWED HOSTS
ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = [
    'https://gis-map.1acre.in',
    'http://gis-map.1acre.in',  # if you also use HTTP
    'https://lita-unsarcastic-serina.ngrok-free.dev',  # ngrok domain for testing
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
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware", 
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# CORS
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
]
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_CREDENTIALS = True

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

# REST FRAMEWORK
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
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
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

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
CLOUDFRONT_DOMAIN = 'd17yosovmfjm4.cloudfront.net'
USE_CLOUDFRONT = os.getenv('USE_CLOUDFRONT', 'True').lower() == 'true'

# S3-Only Tile Serving Configuration
S3_ONLY_TILE_SERVING = True
DISABLE_LOCAL_TILES = True
GENERATE_TILES_DIRECT_TO_S3 = True
SKIP_LOCAL_TILE_STORAGE = True

# Tile Serving Fallback Configuration
TILE_SERVING_FALLBACK_ORDER = [
    'cloudfront',  # Primary: CloudFront CDN
    's3_direct',   # Secondary: S3 Direct
    'on_demand'    # Tertiary: On-demand generation (optional)
]

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
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'ERROR',
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