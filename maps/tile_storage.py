"""
Tile object storage: Cloudflare R2 only (S3-compatible API). No AWS S3.

Public tile URLs always use PUBLIC_TILE_CDN_HOST (HTTPS).
"""

from __future__ import annotations

import boto3
from botocore.config import Config
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

_BOTO_CONFIG = Config(connect_timeout=30, read_timeout=120, retries={"max_attempts": 3, "mode": "standard"})


def get_tile_object_storage_bucket_name() -> str:
    name = (getattr(settings, "CLOUDFLARE_R2_BUCKET_NAME", None) or "").strip()
    if name:
        return name
    # Optional legacy env name (same bucket on R2)
    return (getattr(settings, "AWS_STORAGE_BUCKET_NAME", None) or "").strip() or "gis-portal-layers"


def get_tile_object_storage_s3_client():
    """
    boto3 client for R2 (upload, delete, head_object). Requires CLOUDFLARE_R2_* settings.
    """
    endpoint = (getattr(settings, "CLOUDFLARE_R2_ENDPOINT_URL", None) or "").strip()
    if not endpoint:
        raise ImproperlyConfigured(
            "Set CLOUDFLARE_R2_ENDPOINT_URL (e.g. https://<ACCOUNT_ID>.r2.cloudflarestorage.com). "
            "AWS S3 is not used for tiles."
        )
    region = (getattr(settings, "CLOUDFLARE_R2_REGION_NAME", None) or "auto").strip() or "auto"
    key = (getattr(settings, "CLOUDFLARE_R2_ACCESS_KEY_ID", None) or "").strip()
    secret = (getattr(settings, "CLOUDFLARE_R2_SECRET_ACCESS_KEY", None) or "").strip()
    if not key or not secret:
        raise ImproperlyConfigured(
            "Set CLOUDFLARE_R2_ACCESS_KEY_ID and CLOUDFLARE_R2_SECRET_ACCESS_KEY for R2 API access."
        )
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        config=_BOTO_CONFIG,
    )


def public_https_url_for_object_key(object_key: str) -> str:
    """HTTPS URL on the public tile CDN (same object key as in R2)."""
    key = (object_key or "").lstrip("/")
    host = (getattr(settings, "PUBLIC_TILE_CDN_HOST", None) or "").strip()
    if not host:
        raise ImproperlyConfigured(
            "Set PUBLIC_TILE_CDN_HOST (e.g. tiles.citylands.in) for public tile URLs."
        )
    prefix = (getattr(settings, "PUBLIC_TILE_CDN_PATH_PREFIX", None) or "").strip().strip("/")
    path = f"{prefix}/{key}" if prefix else key
    return f"https://{host}/{path}"
