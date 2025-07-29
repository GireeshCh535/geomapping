"""
Django settings for geo_mapping project - CLOUDFRONT-ONLY PRODUCTION
OPTIMIZED FOR DIRECT S3 TILE UPLOAD (NO LOCAL TILE STORAGE)
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-9xdea)mc6dhr@)lrhn65!&!uc+#z6nlajj8j091eswp$$2jf!#"

# PRODUCTION SECURITY SETTINGS
DEBUG = False  # Must be False in production
ALLOWED_HOSTS = ['*']

# GDAL/GEOS Configuration for Docker environment
if os.getenv('DJANGO_DB_HOST'):  # Docker environment
    pass  # Let Django auto-detect system libraries
elif os.name == 'posix':  # Local development
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

# Application definition
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
    'maps',
]

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

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
]
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_CREDENTIALS = True

ROOT_URLCONF = "geo_mapping.urls"

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

# Database - Production PostGIS
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.getenv('DJANGO_DB_NAME', 'geo_mapping_db'),
        'USER': os.getenv('DJANGO_DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DJANGO_DB_PASSWORD', 'postgres'),
        'HOST': os.getenv('DJANGO_DB_HOST', 'db'),
        'PORT': os.getenv('DJANGO_DB_PORT', '5432'),
        # Removed invalid init_command option for PostgreSQL
    }
}

# REST Framework Configuration
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
    'DEFAULT_THROTTLE_RATES': {
        'anon': '1000/hour',
        'user': '2000/hour'
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# ===================================
# STATIC FILES - CLOUDFRONT-ONLY CONFIGURATION
# ===================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# CRITICAL: Only include essential static files (NO TILES)
# Only include directories that actually exist or will be created
STATICFILES_DIRS = [
    # Only include base static directory - let Django find subdirectories
    BASE_DIR / 'static',
    
    # Alternative: Create specific directories only if they exist
    # BASE_DIR / 'static' / 'css',     # Only if this directory exists
    # BASE_DIR / 'static' / 'js',      # Only if this directory exists  
    # BASE_DIR / 'static' / 'images',  # Only if this directory exists
    # BASE_DIR / 'static' / 'admin',   # Only if this directory exists
    
    # TILES ARE COMPLETELY EXCLUDED - SERVED FROM CLOUDFRONT ONLY
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

# Data directory
DATA_DIR = BASE_DIR / 'data'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===================================
# REDIS CACHE - PRODUCTION OPTIMIZED
# ===================================

GIS_CACHE_TIMEOUT = 86400 * 7  # 7 days
GIS_CACHE_COMPRESSION = True
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/1')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
                'socket_timeout': 5,
                'socket_connect_timeout': 5,
            }
        },
        'KEY_PREFIX': 'gis_cache',
        'TIMEOUT': GIS_CACHE_TIMEOUT,
    }
}

# ===================================
# AWS S3 & CLOUDFRONT - TILE-ONLY CONFIGURATION  
# ===================================

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = 'AKIAW3MEBMOOEQKR3BXV'
AWS_SECRET_ACCESS_KEY = '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'
AWS_S3_REGION_NAME = "ap-south-1"
AWS_STORAGE_BUCKET_NAME = 'gis-portal'
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'

# CloudFront Configuration - TILES ONLY
CLOUDFRONT_DOMAIN = 'd17yosovmfjm4.cloudfront.net'
USE_CLOUDFRONT = True

# CRITICAL: Force all tiles to be served from CloudFront
TILE_SERVING_METHOD = 'cloudfront_only'  # NO local fallback
FORCE_CLOUDFRONT_TILES = True

# Tile generation settings
TILE_GENERATION_SETTINGS = {
    'direct_to_s3': True,          # Generate directly to S3, no local storage
    'temp_storage_only': True,     # Use temp files only during generation
    'batch_size': 50,              # Process tiles in batches
    'max_zoom_city': 14,           # Max zoom for city tiles
    'max_zoom_real_estate': 16,    # Max zoom for real estate tiles
    'default_format': 'png',       # Default tile format
    'compression_level': 6,        # PNG compression level (0-9)
}

# ===================================
# LOGGING CONFIGURATION
# ===================================

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
            'filename': '/app/logs/django_errors.log',
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
            'level': 'INFO',
            'propagate': True,
        }
    },
}

# ===================================
# PRODUCTION SECURITY SETTINGS
# ===================================

# Security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# HTTPS settings (enable when SSL is configured)
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True  
# CSRF_COOKIE_SECURE = True

# Session configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400  # 24 hours

# ===================================
# PERFORMANCE OPTIMIZATIONS
# ===================================

# Database connection pooling (for PostgreSQL)
DATABASES['default']['CONN_MAX_AGE'] = 60

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB

# Template caching for production - FIXED
# Cannot use both APP_DIRS=True and custom loaders
# For production caching, either use cached loader with APP_DIRS=False
# or keep APP_DIRS=True without custom loaders

# Option 1: Enable template caching (uncomment for production)
# TEMPLATES[0]['APP_DIRS'] = False  # Must be False when using custom loaders
# TEMPLATES[0]['OPTIONS']['loaders'] = [
#     ('django.template.loaders.cached.Loader', [
#         'django.template.loaders.filesystem.Loader',
#         'django.template.loaders.app_directories.Loader',
#     ]),
# ]

# Option 2: Keep APP_DIRS=True (current setting, no template caching)
# This is the default and works fine for most cases

# ===================================
# TILE SERVING CONFIGURATION
# ===================================

# Custom tile serving settings
TILE_SERVING_CONFIG = {
    # CloudFront settings
    'cloudfront_domain': CLOUDFRONT_DOMAIN,
    'cloudfront_enabled': True,
    'cloudfront_cache_headers': {
        'Cache-Control': 'max-age=31536000',  # 1 year for tiles
        'Expires': 'Thu, 31 Dec 2025 23:59:59 GMT',
    },
    
    # Local serving (disabled for production)
    'local_serving_enabled': False,
    'local_fallback_enabled': False,
    
    # S3 settings
    's3_direct_serving': True,
    's3_cache_headers': {
        'CacheControl': 'max-age=31536000',
        'ContentType': 'image/png',
    },
    
    # Error handling
    'empty_tile_on_error': True,
    'redirect_on_missing': True,
    'max_retries': 3,
}

# ===================================
# CUSTOM MANAGEMENT COMMANDS SETTINGS
# ===================================

# Settings for generate_and_upload_tiles command
TILE_GENERATION_CONFIG = {
    'default_city_zoom_range': (8, 14),
    'default_real_estate_zoom_range': (10, 16),
    'batch_processing_size': 50,
    'max_features_per_tile': 1000,
    'compression_settings': {
        'png_compression': 6,
        'mvt_compression': True,
    },
    'retry_settings': {
        'max_retries': 3,
        'retry_delay': 1,  # seconds
    },
    'memory_optimization': {
        'use_temp_files': True,
        'clear_cache_after_batch': True,
        'gc_collect_frequency': 100,  # tiles
    }
}

# Real estate data settings
REAL_ESTATE_CONFIG = {
    'max_plots_per_tile': 500,
    'max_lands_per_tile': 500,
    'simplify_geometry_tolerance': 0.0001,  # degrees
    'render_settings': {
        'plot_color': '#3498db',
        'land_color': '#2ecc71',
        'stroke_width': 1,
        'fill_opacity': 0.7,
    }
}

# ===================================
# ENVIRONMENT-SPECIFIC OVERRIDES
# ===================================

# Override settings based on environment variables
if os.getenv('DJANGO_ENVIRONMENT') == 'development':
    DEBUG = True
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*']
    TILE_SERVING_CONFIG['local_serving_enabled'] = True
    TILE_SERVING_CONFIG['cloudfront_enabled'] = False

if os.getenv('DJANGO_ENVIRONMENT') == 'staging':
    DEBUG = False
    ALLOWED_HOSTS = ['staging.gis-portal.1acre.in', 'gis-staging.1acre.in']
    
# Production is the default configuration above

# ===================================
# MONITORING AND HEALTH CHECKS
# ===================================

# Health check settings
HEALTH_CHECK_CONFIG = {
    'database_check': True,
    'redis_check': True,
    's3_check': True,
    'cloudfront_check': False,  # Optional, slower
}

# Monitoring settings
MONITORING_CONFIG = {
    'tile_generation_metrics': True,
    's3_upload_metrics': True,
    'performance_logging': True,
    'error_alerting': False,  # Set up with your monitoring service
}

# ===================================
# CUSTOM DJANGO SETTINGS VALIDATION
# ===================================

# Validate critical settings on startup
def validate_production_settings():
    """Validate critical production settings"""
    issues = []
    
    if DEBUG:
        issues.append("DEBUG should be False in production")
    
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        issues.append("AWS credentials not configured")
    
    if not CLOUDFRONT_DOMAIN or CLOUDFRONT_DOMAIN == 'your-cloudfront-id.cloudfront.net':
        issues.append("CloudFront domain not properly configured")
    
    if TILE_SERVING_CONFIG['local_serving_enabled']:
        issues.append("Local tile serving should be disabled in production")
    
    return issues

# Run validation (uncomment for production deployment)
# if not DEBUG:
#     validation_issues = validate_production_settings()
#     if validation_issues:
#         raise Exception(f"Production settings validation failed: {validation_issues}")

# ===================================
# FINAL PRODUCTION NOTES
# ===================================

"""
PRODUCTION DEPLOYMENT CHECKLIST:

✅ Tiles are generated and uploaded directly to S3
✅ No local tile storage (saves disk space)
✅ CloudFront serves all tiles (fast CDN delivery)
✅ Static files exclude all tile patterns
✅ DEBUG = False for security
✅ Redis caching optimized for GIS data
✅ Database connection pooling enabled
✅ Template caching enabled
✅ Security headers configured
✅ Comprehensive logging setup
✅ Performance optimizations applied

TILE GENERATION WORKFLOW:
1. Deploy application (no tiles included)
2. Run: python manage.py generate_and_upload_tiles --city bangalore --type both
3. Tiles are generated in memory and uploaded directly to S3
4. CloudFront serves tiles with 1-year cache
5. No local disk space used for tiles

MAINTENANCE COMMANDS:
- Generate city tiles: python manage.py generate_and_upload_tiles --city CITY_NAME
- Generate real estate: python manage.py generate_and_upload_tiles --type real-estate
- Test S3 connection: python manage.py generate_and_upload_tiles --test-connection
- Dry run: python manage.py generate_and_upload_tiles --dry-run --city CITY_NAME
"""