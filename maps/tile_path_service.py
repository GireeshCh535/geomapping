# maps/tile_path_service.py
"""
Tile origin URLs: HTTPS on PUBLIC_TILE_CDN_HOST only (same object keys as Cloudflare R2). No AWS S3/CloudFront.
"""

import os
import re
from pathlib import Path
from typing import Dict, Optional, Tuple
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.text import slugify

_DEVELOPER_TILE_ROOT_NORM = "developer_data"


def _norm_state_token(s: str) -> str:
    return (s or "").strip().lower().replace("-", "_")


def _safe_tile_path_piece(p: str) -> bool:
    if not p or ".." in p or "/" in p:
        return False
    return bool(re.fullmatch(r"[a-zA-Z0-9_.-]+", p))


def is_developer_data_tile_request(state_slug: str) -> bool:
    """True when URL is under developer raster prefix (skip DataLayer lookup; S3 key uses literal segments)."""
    return _norm_state_token(state_slug) == _DEVELOPER_TILE_ROOT_NORM


def developer_raster_path_valid(city_slug: str, layer_slug: str) -> bool:
    city = (city_slug or "").strip()
    layer = (layer_slug or "").strip()
    if not _safe_tile_path_piece(city) or not layer:
        return False
    return all(_safe_tile_path_piece(seg) for seg in layer.split("/") if seg)


class TilePathService:
    """
    Tile fetch URLs: always PUBLIC_TILE_CDN_HOST (CDN in front of R2).
    """

    def __init__(self):
        self.bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'gis-portal-layers')
        self.region = getattr(settings, 'AWS_S3_REGION_NAME', 'ap-south-1')
        # Legacy attribute name; value is the public tile CDN host (not AWS S3).
        self.s3_tile_domain = (
            (getattr(settings, 'AWS_S3_TILE_DOMAIN', None) or '').strip()
            or (getattr(settings, 'PUBLIC_TILE_CDN_HOST', None) or '').strip()
        )
        self.cloudfront_domain = (getattr(settings, 'CLOUDFRONT_DOMAIN', None) or '').strip()
        self.public_tile_cdn_host = (getattr(settings, 'PUBLIC_TILE_CDN_HOST', None) or '').strip()
        self.public_tile_cdn_path_prefix = (
            (getattr(settings, 'PUBLIC_TILE_CDN_PATH_PREFIX', None) or '').strip().strip('/')
        )

    def use_public_cdn_for_tile_origin(self) -> bool:
        """Always True when PUBLIC_TILE_CDN_HOST is configured (required for this app)."""
        return bool(self.public_tile_cdn_host)

    def _public_cdn_path(self, object_key: str) -> str:
        key = (object_key or '').lstrip('/')
        if self.public_tile_cdn_path_prefix:
            return f"{self.public_tile_cdn_path_prefix}/{key}"
        return key

    def generate_public_cdn_url(self, object_key: str) -> str:
        """https://{PUBLIC_TILE_CDN_HOST}/{optional prefix}/{key}"""
        if not self.public_tile_cdn_host:
            raise ImproperlyConfigured(
                "PUBLIC_TILE_CDN_HOST must be set (e.g. tiles.citylands.in). Tiles are not loaded from AWS S3."
            )
        path = self._public_cdn_path(object_key)
        return f"https://{self.public_tile_cdn_host}/{path}"
    
    def generate_s3_key(self, state_slug: str, city_slug: str, layer_slug: str, 
                       z: int, x: int, y: int, format_type: str = 'png') -> str:
        """
        Generate consistent S3 key for tile storage
        
        Args:
            state_slug: State identifier (e.g., 'karnataka')
            city_slug: City identifier (e.g., 'bengaluru')
            layer_slug: Layer identifier (e.g., 'bengaluru_master_plan_2015')
            z: Zoom level
            x: Tile X coordinate
            y: Tile Y coordinate
            format_type: File format ('png' or 'mvt')
            
        Returns:
            S3 key string (e.g., 'karnataka/bengaluru/bengaluru_master_plan_2015/12/2926/1899.png')
        """
        if is_developer_data_tile_request(state_slug):
            city = (city_slug or "").strip()
            layer = (layer_slug or "").strip()
            if not developer_raster_path_valid(city, layer):
                return f"__invalid__/tile/{z}/{x}/{y}.{format_type}"
            return f"developer_data/{city}/{layer}/{z}/{x}/{y}.{format_type}"

        state_slug = slugify(state_slug)
        city_slug = slugify(city_slug)
        if "/" in (layer_slug or ""):
            layer_part = "/".join(
                slugify(seg) for seg in (layer_slug or "").split("/") if seg.strip()
            )
        else:
            layer_part = slugify(layer_slug or "")

        return f"{state_slug}/{city_slug}/{layer_part}/{z}/{x}/{y}.{format_type}"
    
    def generate_cloudfront_url(self, state_slug: str, city_slug: str, layer_slug: str,
                               z: int, x: int, y: int, format_type: str = 'png') -> str:
        """
        CloudFront URL (CLOUDFRONT_DOMAIN) for whitelisted S3 keys only.
        """
        s3_key = self.generate_s3_key(state_slug, city_slug, layer_slug, z, x, y, format_type)
        return f"https://{self.cloudfront_domain}/{s3_key}"
    
    def generate_s3_url(self, state_slug: str, city_slug: str, layer_slug: str,
                       z: int, x: int, y: int, format_type: str = 'png') -> str:
        """
        Generate direct S3 URL for tile access (fallback)
        
        Args:
            state_slug: State identifier
            city_slug: City identifier
            layer_slug: Layer identifier
            z: Zoom level
            x: Tile X coordinate
            y: Tile Y coordinate
            format_type: File format ('png' or 'mvt')
            
        Returns:
            S3 URL string
        """
        s3_key = self.generate_s3_key(state_slug, city_slug, layer_slug, z, x, y, format_type)
        return f"https://{self.s3_tile_domain}/{s3_key}"
    
    def use_cloudfront_for_path(self, s3_key: str) -> bool:
        """Deprecated: tiles no longer use AWS CloudFront."""
        return False

    def _backend_label(self, s3_key: str) -> str:
        """Debug: label origin for prints."""
        return "CDN"

    def format_tile_api_routing_for_log(
        self,
        django_api_path: str,
        object_key: str,
        upstream_https_url: str,
    ) -> str:
        """
        One line for logs: where the browser called vs where Django loads bytes.
        Reads are always HTTPS to PUBLIC_TILE_CDN_HOST (tile CDN in front of R2), not boto3 AWS S3.
        """
        host = (self.public_tile_cdn_host or "").strip() or "(PUBLIC_TILE_CDN_HOST unset)"
        pfx = (self.public_tile_cdn_path_prefix or "").strip()
        pfx_txt = f" cdn_path_prefix={pfx!r}" if pfx else ""
        key_snip = (object_key or "")[:140]
        url_snip = (upstream_https_url or "")[:220]
        return (
            f"api={django_api_path} | flow=browser→Django_proxy→HTTP_GET→tile_CDN(host={host!r}){pfx_txt} "
            f"| objects_stored_on=Cloudflare_R2 | not_AWS_S3_GetObject | object_key={key_snip} | upstream_url={url_snip}"
        )

    @staticmethod
    def format_tile_api_routing_local_disk(django_api_path: str, local_file: str) -> str:
        return (
            f"api={django_api_path} | flow=browser→Django_proxy→LOCAL_DISK(no HTTP) "
            f"| file={local_file} | (skips CDN/R2 fetch)"
        )

    def get_backend_url_for_tile(self, state_slug: str, city_slug: str, layer_slug: str,
                                 z: int, x: int, y: int, format_type: str = 'png') -> str:
        """HTTPS URL on the public tile CDN (object key matches R2)."""
        s3_key = self.generate_s3_key(state_slug, city_slug, layer_slug, z, x, y, format_type)
        return self.generate_public_cdn_url(s3_key)

    def get_backend_url_for_land_plot(self, z: int, x: int, y: int) -> str:
        """HTTPS URL on the public tile CDN for land-plot MVT."""
        return self.generate_public_cdn_url(self.land_plot_s3_key(z, x, y))
    
    # Land/plot MVT tiles (global, no state/city/layer) – same pattern as PNGs
    LAND_PLOT_S3_PREFIX = 'land-plot'

    def land_plot_s3_key(self, z: int, x: int, y: int) -> str:
        """S3 key for land/plot MVT tile: land-plot/{z}/{x}/{y}.mvt"""
        return f"{self.LAND_PLOT_S3_PREFIX}/{z}/{x}/{y}.mvt"

    def land_plot_cloudfront_url(self, z: int, x: int, y: int) -> str:
        """CloudFront URL for land/plot MVT (prefix land-plot/ must be whitelisted)."""
        s3_key = self.land_plot_s3_key(z, x, y)
        return f"https://{self.cloudfront_domain}/{s3_key}"

    def land_plot_s3_url(self, z: int, x: int, y: int) -> str:
        """Direct S3 URL for land/plot MVT tile (fallback)."""
        s3_key = self.land_plot_s3_key(z, x, y)
        return f"https://{self.s3_tile_domain}/{s3_key}"

    def parse_tile_path(self, tile_path: str) -> Optional[Dict[str, any]]:
        """
        Parse a tile path to extract components
        
        Args:
            tile_path: Path like 'karnataka/bengaluru/layer/12/2926/1899.png'
            
        Returns:
            Dict with parsed components or None if invalid
        """
        try:
            parts = tile_path.split('/')
            if len(parts) < 6:
                return None
            
            # Extract components
            state_slug = parts[0]
            city_slug = parts[1]
            layer_slug = parts[2]
            z = int(parts[3])
            x = int(parts[4])
            
            # Handle file extension
            y_part = parts[5]
            if '.' in y_part:
                y, format_type = y_part.split('.')
                y = int(y)
            else:
                y = int(y_part)
                format_type = 'png'  # Default
            
            return {
                'state_slug': state_slug,
                'city_slug': city_slug,
                'layer_slug': layer_slug,
                'z': z,
                'x': x,
                'y': y,
                'format_type': format_type
            }
        except (ValueError, IndexError):
            return None
    
    def validate_tile_coordinates(self, z: int, x: int, y: int) -> bool:
        """
        Validate tile coordinates
        
        Args:
            z: Zoom level
            x: Tile X coordinate
            y: Tile Y coordinate
            
        Returns:
            True if coordinates are valid
        """
        try:
            # Basic validation
            if z < 0 or z > 22:  # Reasonable zoom range
                return False
            if x < 0 or y < 0:
                return False
            if x >= 2 ** z or y >= 2 ** z:  # Tile bounds for zoom level
                return False
            return True
        except (TypeError, ValueError):
            return False
    
    def get_tile_cache_headers(self, format_type: str = 'png') -> Dict[str, str]:
        """
        Get no-cache headers for tile format
        
        Args:
            format_type: File format ('png' or 'mvt')
            
        Returns:
            Dict with no-cache headers
        """
        if format_type == 'png':
            return {
                'CacheControl': 'no-cache, no-store, must-revalidate',  # No caching
                'Pragma': 'no-cache',
                'Expires': '0',
                'ContentType': 'image/png'
            }
        elif format_type == 'mvt':
            return {
                'CacheControl': 'no-cache, no-store, must-revalidate',  # No caching
                'Pragma': 'no-cache',
                'Expires': '0',
                'ContentType': 'application/vnd.mapbox-vector-tile'
            }
        else:
            return {
                'CacheControl': 'no-cache, no-store, must-revalidate',  # No caching
                'Pragma': 'no-cache',
                'Expires': '0',
                'ContentType': 'application/octet-stream'
            }
    
    def generate_local_path(self, state_slug: str, city_slug: str, layer_slug: str,
                           z: int, x: int, y: int, format_type: str = 'png') -> Path:
        """
        Generate local file path for tile storage (disabled - S3/CloudFront only)
        
        Args:
            state_slug: State identifier
            city_slug: City identifier
            layer_slug: Layer identifier
            z: Zoom level
            x: Tile X coordinate
            y: Tile Y coordinate
            format_type: File format ('png' or 'mvt')
            
        Returns:
            None (local storage disabled)
        """
        # Local storage disabled — tiles on S3 / CDN only
        return None
    
    def ensure_directory_exists(self, file_path: Path) -> bool:
        """
        Ensure the directory for a file path exists
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if directory exists or was created
        """
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False


def hierarchical_tile_proxy_base(state_slug: str, city_slug: str, layer_slug: str) -> str:
    """
    Path prefix clients should use for state/city/layer tiles (Django proxy); see TILE_PROXY_PATH_PREFIX.
    """
    prefix = (getattr(settings, 'TILE_PROXY_PATH_PREFIX', None) or '/api/tiles').strip().rstrip('/')
    return f"{prefix}/{state_slug}/{city_slug}/{layer_slug}"


def hierarchical_tile_proxy_url_for_client(state_slug: str, city_slug: str, layer_slug: str) -> str:
    """
    Same as hierarchical_tile_proxy_base, but prefixed with TILE_PROXY_PUBLIC_BASE_URL when set
    so clients get absolute URLs on the Layers app origin (never the tile CDN hostname).
    """
    rel = hierarchical_tile_proxy_base(state_slug, city_slug, layer_slug)
    origin = (getattr(settings, 'TILE_PROXY_PUBLIC_BASE_URL', None) or '').strip().rstrip('/')
    if origin:
        return f"{origin}{rel}"
    return rel


def client_tile_proxy_api_root() -> str:
    """
    Base URL for tile links returned in API JSON: Django proxy only.

    If TILE_PROXY_PUBLIC_BASE_URL is set (e.g. https://layers.citylands.in), returns
    origin + TILE_PROXY_PATH_PREFIX (e.g. https://layers.citylands.in/api/tiles).
    If unset, returns path-only prefix (e.g. /api/tiles) for same-origin relative URLs.

    The tile CDN (PUBLIC_TILE_CDN_HOST) is not included here; Django uses it only server-side.
    """
    origin = (getattr(settings, 'TILE_PROXY_PUBLIC_BASE_URL', None) or '').strip().rstrip('/')
    path_prefix = (getattr(settings, 'TILE_PROXY_PATH_PREFIX', None) or '/api/tiles').strip()
    if not path_prefix.startswith('/'):
        path_prefix = '/' + path_prefix
    path_prefix = path_prefix.rstrip('/')
    if origin:
        return f"{origin}{path_prefix}"
    return path_prefix


def tile_proxy_png_template_from_s3_tile_path(s3_tile_path: str) -> Optional[str]:
    """
    /api/tiles/developer_data/<city>/<id>/<tif_name>/{{z}}/{{x}}/{{y}}.png (matches s3_tile_path in DB).
    """
    p = (s3_tile_path or "").strip().strip("/")
    if not p:
        return None
    parts = [x for x in p.split("/") if x]
    if len(parts) < 4 or _norm_state_token(parts[0]) != _DEVELOPER_TILE_ROOT_NORM:
        return None
    state, city = parts[0], parts[1]
    layer = "/".join(parts[2:])
    if not developer_raster_path_valid(city, layer):
        return None
    base = hierarchical_tile_proxy_url_for_client(state, city, layer)
    return f"{base}/{{z}}/{{x}}/{{y}}.png"


def public_https_base_for_layer_path(state_slug: str, city_slug: str, layer_slug: str) -> str:
    """
    Base URL for client-visible tile API paths (Django proxy). Legacy name; not the CDN.

    state_slug/city_slug/layer_slug are ignored; use hierarchical_tile_proxy_url_for_client when
    you have hierarchy segments.
    """
    return client_tile_proxy_api_root()


def public_https_base_for_s3_tile_prefix(s3_tile_path: str) -> str:
    """
    Base URL for building client tile URL templates (Django proxy). Legacy name; s3_tile_path ignored.
    """
    return client_tile_proxy_api_root()
