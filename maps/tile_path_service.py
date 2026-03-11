# maps/tile_path_service.py
"""
Tile Path Service for consistent S3 and CloudFront path handling
This service ensures all tile paths are generated consistently across the system.
"""

import os
from pathlib import Path
from typing import Dict, Optional, Tuple
from django.conf import settings
from django.utils.text import slugify

class TilePathService:
    """
    Service for generating consistent tile paths for S3 and CloudFront
    """
    
    def __init__(self):
        self.bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'gis-portal-layers')
        self.cloudfront_domain = getattr(settings, 'CLOUDFRONT_DOMAIN', 'd17yosovmfjm4.cloudfront.net')
        self.region = getattr(settings, 'AWS_S3_REGION_NAME', 'ap-south-1')
    
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
        # Ensure all components are properly formatted
        # FIXED: Keep hyphens in all slugs (state, city, and layer) for consistency
        state_slug = slugify(state_slug)
        city_slug = slugify(city_slug)
        layer_slug = slugify(layer_slug)  # Keep hyphens as-is
        
        # Generate S3 key: state/city/layer/z/x/y.format
        s3_key = f"{state_slug}/{city_slug}/{layer_slug}/{z}/{x}/{y}.{format_type}"
        
        return s3_key
    
    def generate_cloudfront_url(self, state_slug: str, city_slug: str, layer_slug: str,
                               z: int, x: int, y: int, format_type: str = 'png') -> str:
        """
        Generate CloudFront URL for tile access
        
        Args:
            state_slug: State identifier
            city_slug: City identifier
            layer_slug: Layer identifier
            z: Zoom level
            x: Tile X coordinate
            y: Tile Y coordinate
            format_type: File format ('png' or 'mvt')
            
        Returns:
            CloudFront URL string
        """
        s3_key = self.generate_s3_key(state_slug, city_slug, layer_slug, z, x, y, format_type)
        
        # CloudFront URL: https://domain/s3_key
        cloudfront_url = f"https://{self.cloudfront_domain}/{s3_key}"
        
        return cloudfront_url
    
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
        
        # S3 URL: https://bucket.s3.region.amazonaws.com/s3_key
        s3_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
        
        return s3_url
    
    def use_cloudfront_for_path(self, s3_key: str) -> bool:
        """
        Return True if this S3 key should be served via CloudFront (path-based, no fallback).
        """
        prefixes = getattr(settings, 'CLOUDFRONT_PATH_PREFIXES', []) or []
        key = (s3_key or '').strip()
        for prefix in prefixes:
            p = (prefix or '').strip().rstrip('/')
            if p and (key == p or key.startswith(p + '/')):
                return True
        return False

    def _backend_label(self, s3_key: str) -> str:
        """Debug: label CloudFront vs S3 for prints."""
        return "CloudFront" if self.use_cloudfront_for_path(s3_key) else "S3"

    def get_backend_url_for_tile(self, state_slug: str, city_slug: str, layer_slug: str,
                                 z: int, x: int, y: int, format_type: str = 'png') -> str:
        """
        Return the single backend URL for this tile (CloudFront or S3 based on path; no fallback).
        """
        s3_key = self.generate_s3_key(state_slug, city_slug, layer_slug, z, x, y, format_type)
        print(f"[tile_proxy] backend for {s3_key} -> {self._backend_label(s3_key)}")
        if self.use_cloudfront_for_path(s3_key):
            return self.generate_cloudfront_url(state_slug, city_slug, layer_slug, z, x, y, format_type)
        return self.generate_s3_url(state_slug, city_slug, layer_slug, z, x, y, format_type)

    def get_backend_url_for_land_plot(self, z: int, x: int, y: int) -> str:
        """
        Return the single backend URL for this land-plot MVT tile (CloudFront or S3 based on path; no fallback).
        """
        s3_key = self.land_plot_s3_key(z, x, y)
        print(f"[tile_proxy] backend for {s3_key} -> {self._backend_label(s3_key)}")
        if self.use_cloudfront_for_path(s3_key):
            return self.land_plot_cloudfront_url(z, x, y)
        return self.land_plot_s3_url(z, x, y)
    
    # Land/plot MVT tiles (global, no state/city/layer) – same pattern as PNGs
    LAND_PLOT_S3_PREFIX = 'land-plot'

    def land_plot_s3_key(self, z: int, x: int, y: int) -> str:
        """S3 key for land/plot MVT tile: land-plot/{z}/{x}/{y}.mvt"""
        return f"{self.LAND_PLOT_S3_PREFIX}/{z}/{x}/{y}.mvt"

    def land_plot_cloudfront_url(self, z: int, x: int, y: int) -> str:
        """CloudFront URL for land/plot MVT tile."""
        s3_key = self.land_plot_s3_key(z, x, y)
        return f"https://{self.cloudfront_domain}/{s3_key}"

    def land_plot_s3_url(self, z: int, x: int, y: int) -> str:
        """Direct S3 URL for land/plot MVT tile (fallback)."""
        s3_key = self.land_plot_s3_key(z, x, y)
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"

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
        # Local storage disabled - using S3/CloudFront only
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
