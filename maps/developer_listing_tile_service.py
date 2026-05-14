"""
Service for generating tiles from developer listing TIF files
Downloads TIF files from configured URLs, generates tiles, and uploads to object storage (R2 or S3).
"""

import os
import tempfile
import logging
import requests
import boto3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time
from django.conf import settings
from django.db import close_old_connections

from .tile_path_service import (
    public_https_base_for_s3_tile_prefix,
    tile_proxy_png_template_from_s3_tile_path,
)
from .tile_debug import tile_debug
from .tile_storage import get_tile_object_storage_bucket_name, get_tile_object_storage_s3_client
from botocore.exceptions import ClientError
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import mercantile
from PIL import Image
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import io

logger = logging.getLogger(__name__)


class DeveloperListingTileService:
    """Service for processing TIF files and generating map tiles"""
    
    def __init__(self):
        self.bucket_name = get_tile_object_storage_bucket_name()
        self.region = getattr(settings, 'AWS_S3_REGION_NAME', 'ap-south-1')
        self.s3_client = get_tile_object_storage_s3_client()
        # CloudFront client for cache invalidation
        self.cloudfront_client = None
        self.cloudfront_distribution_id = getattr(settings, 'CLOUDFRONT_DISTRIBUTION_ID', None)
        self.enable_cloudfront_invalidation = getattr(settings, 'ENABLE_CLOUDFRONT_INVALIDATION', True)
        aws_key = (getattr(settings, 'AWS_ACCESS_KEY_ID', None) or '').strip()
        aws_secret = (getattr(settings, 'AWS_SECRET_ACCESS_KEY', None) or '').strip()
        if (
            self.enable_cloudfront_invalidation
            and self.cloudfront_distribution_id
            and aws_key
            and aws_secret
        ):
            try:
                self.cloudfront_client = boto3.client(
                    'cloudfront',
                    region_name='us-east-1',
                    aws_access_key_id=aws_key,
                    aws_secret_access_key=aws_secret,
                )
            except Exception as e:
                logger.warning(f"[CLOUDFRONT] Failed to initialize CloudFront client: {e}")
                self.cloudfront_client = None
        elif not self.cloudfront_distribution_id:
            logger.warning(f"[CLOUDFRONT] Distribution ID not configured, invalidation disabled")
        
        self.tile_size = 256
        self.min_zoom = 8
        self.max_zoom = 18
        self.max_workers = 8  # For parallel processing
        # Backend API URL for fetching listing data
        self.backend_api_url = getattr(
            settings,
            'DEVELOPER_BACKEND_API_URL',
            'http://be.staging.1acre.in'  # Default to staging
        )
    
    def process_webhook(self, webhook_data: Dict, listing=None, webhook_event=None) -> Dict:
        """
        Process webhook data and generate tiles for TIF files
        
        Args:
            webhook_data: Webhook payload from backend
            listing: DeveloperListing instance (optional)
            webhook_event: WebhookEvent instance (optional)
            
        Returns:
            Dict with processing results
        """
        try:
            close_old_connections()
            event_type = webhook_data.get('event_type', '')
            action = webhook_data.get('action', '')
            listing_type = webhook_data.get('listing_type', '')
            listing_id = webhook_data.get('listing_id')
            tif_files = webhook_data.get('tif_files', [])
            s3_tile_base_path = webhook_data.get('s3_tile_base_path', '')
            base_snip = (s3_tile_base_path or "")[:120]
            tile_debug(
                f"TIF process_webhook event={event_type} action={action} "
                f"listing={listing_type}/{listing_id} n_tif={len(tif_files)} base={base_snip}"
            )
            logger.info(f"[TILE_GEN] Starting listing={listing_type} id={listing_id} tif_files={len(tif_files)}")
            
            # Get listing if not provided
            if not listing:
                from .models import DeveloperListing
                try:
                    listing = DeveloperListing.objects.get(
                        listing_type=listing_type,
                        backend_listing_id=listing_id
                    )
                except DeveloperListing.DoesNotExist:
                    logger.warning(f"Listing not found: {listing_type} {listing_id}")
            
            if not tif_files:
                logger.info(f"[TILE_GEN] No TIF files for {listing_type} {listing_id}")
                return {
                    'success': True,
                    'message': 'No TIF files to process',
                    'tiles_generated': 0
                }
            
            print(f"[TIF] Processing {len(tif_files)} TIF file(s)...")
            logger.info(f"[TILE_GEN] 🔄 Processing {len(tif_files)} TIF file(s)...")
            results = []
            for idx, tif_file in enumerate(tif_files, 1):
                file_name = tif_file.get('file_name', 'unknown')
                print(f"[TIF] File {idx}/{len(tif_files)}: {file_name}")
                result = self.process_tif_file(
                    tif_file=tif_file,
                    listing_type=listing_type,
                    listing_id=listing_id,
                    s3_tile_base_path=s3_tile_base_path,
                    listing=listing
                )
                results.append(result)
                
                if result.get('success'):
                    pass  # success
                else:
                    logger.error(f"[TILE_GEN] TIF {file_name} failed: {result.get('error', 'Unknown error')}")
            
            total_tiles = sum(r.get('tiles_generated', 0) for r in results)
            success_count = sum(1 for r in results if r.get('success', False))
            
            logger.info(f"[TILE_GEN] Completed: files={len(tif_files)} success={success_count} tiles={total_tiles}")
            
            return {
                'success': success_count == len(results),
                'listing_type': listing_type,
                'listing_id': listing_id,
                'tif_files_processed': len(tif_files),
                'successful_files': success_count,
                'total_tiles_generated': total_tiles,
                'file_results': results
            }
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _delete_s3_tiles(self, s3_tile_path: str) -> int:
        """
        Delete all tiles from S3 for a given tile path prefix
        
        IMPORTANT: This method ONLY deletes tiles matching the specific path prefix.
        For example, if s3_tile_path = 'developer_data/land/70/map.tif', it will ONLY
        delete tiles under 'developer_data/land/70/map.tif/' and will NOT affect tiles
        for other listings (e.g., 'developer_data/land/71/' or 'developer_data/land/69/').
        
        Args:
            s3_tile_path: S3 path prefix (e.g., 'developer_data/land/123/map.tif')
                          This should be specific to ONE listing/media file
            
        Returns:
            Number of files deleted
        """
        try:
            # Ensure path ends with / for prefix matching
            # This ensures we only delete tiles under this specific path, not other paths
            prefix = s3_tile_path.rstrip('/') + '/'
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
            
            objects_to_delete = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects_to_delete.append({'Key': obj['Key']})
            
            if not objects_to_delete:
                return 0
            
            # Delete in batches of 1000 (S3 limit)
            deleted_count = 0
            for i in range(0, len(objects_to_delete), 1000):
                batch = objects_to_delete[i:i+1000]
                response = self.s3_client.delete_objects(
                    Bucket=self.bucket_name,
                    Delete={'Objects': batch}
                )
                deleted_count += len(response.get('Deleted', []))
            
            # Invalidate CloudFront cache for deleted tiles
            if deleted_count > 0:
                self._invalidate_cloudfront_paths([prefix + '*'])
            
            return deleted_count
            
        except ClientError as e:
            logger.error(f"[S3_CLEANUP] ❌ Error deleting S3 tiles: {e}")
            return 0
        except Exception as e:
            logger.error(f"[S3_CLEANUP] ❌ Unexpected error deleting S3 tiles: {e}", exc_info=True)
            return 0
    
    def _invalidate_cloudfront_paths(self, paths: List[str]) -> Optional[str]:
        """
        Invalidate CloudFront cache for given S3 paths
        
        Args:
            paths: List of S3 path patterns to invalidate (e.g., ['developer_data/land/70/map.tif/*'])
            
        Returns:
            Invalidation ID if successful, None otherwise
        """
        if not self.enable_cloudfront_invalidation or not self.cloudfront_client or not self.cloudfront_distribution_id:
            return None
        
        try:
            # Create invalidation
            response = self.cloudfront_client.create_invalidation(
                DistributionId=self.cloudfront_distribution_id,
                InvalidationBatch={
                    'Paths': {
                        'Quantity': len(paths),
                        'Items': paths
                    },
                    'CallerReference': f"tile-update-{int(time.time())}"
                }
            )
            
            invalidation_id = response.get('Invalidation', {}).get('Id')
            return invalidation_id
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"[CLOUDFRONT] ❌ Error creating CloudFront invalidation: {error_code} - {error_message}")
            return None
        except Exception as e:
            logger.error(f"[CLOUDFRONT] ❌ Unexpected error creating CloudFront invalidation: {e}", exc_info=True)
            return None
    
    def process_tif_file(
        self,
        tif_file: Dict,
        listing_type: str,
        listing_id: int,
        s3_tile_base_path: str,
        listing=None
    ) -> Dict:
        """
        Download TIF file, generate tiles, upload to S3, and save metadata
        
        Args:
            tif_file: TIF file info from webhook
            listing_type: 'developerland' or 'developerplot'
            listing_id: Listing ID
            s3_tile_base_path: Base S3 path for tiles (e.g., 'developerland/123')
            listing: DeveloperListing instance (optional)
            
        Returns:
            Dict with processing results
        """
        import time
        from django.utils import timezone
        from .models import DeveloperListingMedia, TIFMetadata
        
        tif_url = tif_file.get('url')
        file_name = tif_file.get('file_name', 'unknown.tif')
        media_id = tif_file.get('id')
        
        # Get S3 tile path - add developer_data prefix
        s3_tile_path = tif_file.get('s3_tile_path', f"developer_data/{s3_tile_base_path}/{file_name}")
        
        # Ensure developer_data prefix
        if not s3_tile_path.startswith('developer_data/'):
            s3_tile_path = f"developer_data/{s3_tile_path}"
        
        logger.info(f"[TIF_PROCESS] Processing {file_name}")
        
        # Get media record
        media = None
        old_s3_tile_path = None
        if listing and media_id:
            try:
                media = DeveloperListingMedia.objects.get(
                    listing=listing,
                    backend_media_id=media_id
                )
                # Check if media has an old tile path that's different
                if media.s3_tile_path and media.s3_tile_path != s3_tile_path:
                    old_s3_tile_path = media.s3_tile_path
            except DeveloperListingMedia.DoesNotExist:
                pass
        
        # Delete existing tiles at this path before regenerating (avoids stale/orphaned tiles on update)
        deleted_new = self._delete_s3_tiles(s3_tile_path)
        deleted_old = 0
        if old_s3_tile_path and old_s3_tile_path != s3_tile_path:
            deleted_old = self._delete_s3_tiles(old_s3_tile_path)
        if deleted_new or deleted_old:
            print(f"[TIF] Deleted existing tiles: {deleted_new} at current path, {deleted_old} at old path")
            logger.info(f"[TIF_PROCESS] Deleted existing tiles: current={deleted_new} old_path={deleted_old}")

        start_time = time.time()
        
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                tif_path = self._download_tif_file(tif_url, temp_dir, file_name)
                if not tif_path:
                    error_msg = f'Failed to download TIF file from {tif_url}'
                    logger.error(f"[TIF_PROCESS] Download failed: {error_msg}")
                    if media:
                        media.tiles_generation_error = error_msg
                        media.save()
                    return {
                        'success': False,
                        'error': error_msg,
                        'file_name': file_name
                    }
                print(f"[TIF] Downloaded TIF: {file_name}")
                file_size = os.path.getsize(tif_path) if os.path.exists(tif_path) else None
                if media:
                    media.tiles_generation_started_at = timezone.now()
                    media.save()
                
                # Try to extract location from listing data for fallback bounds
                fallback_bounds = None
                if listing and listing.listing_data:
                    listing_data = listing.listing_data
                    # location may be a dict or a string (e.g. JSON); only use .get() when it's a dict
                    location = listing_data.get('location')
                    if not isinstance(location, dict):
                        location = {}
                    # Try to extract lat/lng from common field names
                    lat = listing_data.get('latitude') or listing_data.get('lat') or location.get('latitude')
                    lng = listing_data.get('longitude') or listing_data.get('lng') or listing_data.get('lon') or location.get('longitude')
                    
                    if lat and lng:
                        try:
                            lat = float(lat)
                            lng = float(lng)
                            # Create a small bounding box around the point (0.01 degrees ≈ 1km)
                            fallback_bounds = {
                                'west': lng - 0.005,
                                'east': lng + 0.005,
                                'north': lat + 0.005,
                                'south': lat - 0.005
                            }
                        except (ValueError, TypeError):
                            pass
                
                result = self._generate_tiles_from_tif(
                    tif_path=tif_path,
                    s3_tile_base_path=s3_tile_path,
                    temp_dir=temp_dir,
                    media=media,
                    fallback_bounds=fallback_bounds
                )
                close_old_connections()
                
                tiles_generated = result.get('tiles_generated', 0)
                tiles_by_zoom = result.get('tiles_by_zoom', {})
                tif_metadata = result.get('tif_metadata', {})
                
                print(f"[TIF] Generated {tiles_generated} tiles, uploaded to S3: {s3_tile_path}")
                logger.info(f"[TIF_PROCESS] Tiles generated: {tiles_generated}")
                
                if media:
                    media.tiles_generated = True
                    media.tiles_generation_completed_at = timezone.now()
                    media.total_tiles_generated = tiles_generated
                    media.tiles_generation_error = ''
                    media.save()
                
                if media and tif_metadata:
                    tif_meta_obj, _ = TIFMetadata.objects.update_or_create(
                        media=media,
                        defaults={
                            'source_crs': tif_metadata.get('source_crs', ''),
                            'source_width': tif_metadata.get('source_width'),
                            'source_height': tif_metadata.get('source_height'),
                            'source_bands': tif_metadata.get('source_bands'),
                            'source_bounds_west': tif_metadata.get('source_bounds', {}).get('west'),
                            'source_bounds_south': tif_metadata.get('source_bounds', {}).get('south'),
                            'source_bounds_east': tif_metadata.get('source_bounds', {}).get('east'),
                            'source_bounds_north': tif_metadata.get('source_bounds', {}).get('north'),
                            'reprojected_width': tif_metadata.get('reprojected_width'),
                            'reprojected_height': tif_metadata.get('reprojected_height'),
                            'bounds_west': tif_metadata.get('bounds', {}).get('west'),
                            'bounds_south': tif_metadata.get('bounds', {}).get('south'),
                            'bounds_east': tif_metadata.get('bounds', {}).get('east'),
                            'bounds_north': tif_metadata.get('bounds', {}).get('north'),
                            'transform_matrix': tif_metadata.get('transform', {}),
                            'min_zoom': self.min_zoom,
                            'max_zoom': self.max_zoom,
                            'tile_size': self.tile_size,
                            'total_tiles_generated': tiles_generated,
                            'tiles_by_zoom': tiles_by_zoom,
                            'processing_time_seconds': time.time() - start_time,
                            'file_size_bytes': file_size,
                            'tif_data': tif_metadata,
                        }
                    )
                    self._create_datalayer_and_geofeature(
                        listing=listing,
                        media=media,
                        tif_metadata=tif_metadata,
                        s3_tile_path=s3_tile_path
                    )
                
                if tiles_generated > 0:
                    invalidation_path = f"{s3_tile_path.rstrip('/')}/*"
                    self._invalidate_cloudfront_paths([invalidation_path])
                
                print(f"[TIF] Removed downloaded TIF (temp cleanup): {file_name}")
                return {
                    'success': True,
                    'file_name': file_name,
                    'tiles_generated': tiles_generated,
                    's3_tile_path': s3_tile_path
                }
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[TIF_PROCESS] Error processing {file_name}: {e}", exc_info=True)
                if media:
                    media.tiles_generation_error = error_msg
                    media.save()
                return {
                    'success': False,
                    'error': error_msg,
                    'file_name': file_name
                }
    
    def _create_datalayer_and_geofeature(
        self,
        listing,
        media,
        tif_metadata: Dict,
        s3_tile_path: str
    ):
        """
        Create DataLayer and GeoFeature entries for a TIF file
        This allows the TIF to be spatially queried like other layers
        
        Args:
            listing: DeveloperListing instance
            media: DeveloperListingMedia instance
            tif_metadata: Dictionary with TIF metadata including bounds
            s3_tile_path: S3 path for tiles
        """
        from .models import DataLayer, GeoFeature, City, LayerCategory, State
        from django.contrib.gis.geos import Polygon
        from django.utils.text import slugify
        
        try:
            # Get bounds
            bounds = tif_metadata.get('bounds', {})
            west = bounds.get('west')
            south = bounds.get('south')
            east = bounds.get('east')
            north = bounds.get('north')
            
            if not all([west, south, east, north]):
                logger.warning(f"[DATALAYER] ⚠️  Invalid bounds, skipping DataLayer creation")
                return
            
            # Get or create "Developer Listings" city
            # Try to find existing city or create a generic one
            city_name = listing.city or 'Developer Listings'
            state_name = listing.state or 'Multiple States'
            
            # Get or create state
            state, _ = State.objects.get_or_create(
                name=state_name,
                defaults={
                    'slug': slugify(state_name),
                    'code': state_name[:2].upper(),
                    'center_lat': (south + north) / 2,
                    'center_lng': (west + east) / 2,
                    'default_zoom': 10
                }
            )
            
            # Get or create city
            city, _ = City.objects.get_or_create(
                name=city_name,
                defaults={
                    'slug': slugify(city_name),
                    'state': state_name,
                    'state_ref': state,
                    'center_lat': (south + north) / 2,
                    'center_lng': (west + east) / 2,
                    'min_zoom': 8,
                    'max_zoom': 18
                }
            )
            
            # Get or create "Developer Listing" category
            category, _ = LayerCategory.objects.get_or_create(
                code='DEVELOPER_LISTING',
                defaults={
                    'name': 'Developer Listing',
                    'description': 'Site plans and maps from developer listings',
                    'default_color': '#FF6B6B',
                    'default_stroke': '#C92A2A',
                    'default_opacity': 0.8,
                    'display_order': 100
                }
            )
            
            # Create unique layer name and slug
            layer_name = f"{listing.get_listing_type_display()} #{listing.backend_listing_id} - {media.file_name}"
            layer_slug = f"{listing.listing_type}-{listing.backend_listing_id}-{slugify(media.file_name)}"
            
            # Create or update DataLayer
            data_layer, created = DataLayer.objects.update_or_create(
                city=city,
                slug=layer_slug,
                defaults={
                    'name': layer_name,
                    'category': category,
                    'description': f"TIF site plan for {listing.name}",
                    'original_filename': media.file_name,
                    'file_format': 'GEOTIFF',
                    'file_path': media.file_url,
                    'geometry_type': 'POLYGON',
                    'bbox_xmin': west,
                    'bbox_ymin': south,
                    'bbox_xmax': east,
                    'bbox_ymax': north,
                    'is_processed': True,
                    'feature_count': 1,
                    'tiles_generated': True,
                    'is_true': True,  # Make visible by default
                    'categorization_method': 'MANUAL',
                    'data_source': f'Developer Listing {listing.listing_type} #{listing.backend_listing_id}',
                }
            )
            
            
            # Create bounding box polygon
            # Polygon format: ((west, south), (west, north), (east, north), (east, south), (west, south))
            polygon = Polygon((
                (west, south),
                (west, north),
                (east, north),
                (east, south),
                (west, south)
            ), srid=4326)  # WGS84
            
            # Calculate area (approximate in square meters for display)
            # For rough estimate: 1 degree latitude ≈ 111 km, 1 degree longitude varies
            width_km = abs(east - west) * 111 * abs((south + north) / 2)  # Adjust for latitude
            height_km = abs(north - south) * 111
            area_sqkm = width_km * height_km
            
            # Create or update GeoFeature
            geo_feature, created = GeoFeature.objects.update_or_create(
                layer=data_layer,
                defaults={
                    'geometry': polygon,
                    'name': listing.name or layer_name,
                    'description': listing.description or f"Site plan boundary for {listing.name}",
                    'zone_category': 'Developer Listing',
                    'zone_subcategory': listing.get_listing_type_display(),
                    'source_layer_name': media.file_name,
                    'area': area_sqkm,
                    'is_valid': True,
                    'properties': {
                        'listing_type': listing.listing_type,
                        'listing_id': listing.backend_listing_id,
                        'media_id': media.id,
                        'backend_media_id': media.backend_media_id,
                        'file_name': media.file_name,
                        'file_url': media.file_url,
                        's3_tile_path': s3_tile_path,
                        'tile_url_template': (
                            tile_proxy_png_template_from_s3_tile_path(s3_tile_path)
                            or (
                                f"{public_https_base_for_s3_tile_prefix(s3_tile_path)}"
                                f"/{s3_tile_path}/{{z}}/{{x}}/{{y}}.png"
                            )
                        ),
                        'tiles_generated': media.total_tiles_generated,
                        'location': listing.location,
                        'city': listing.city,
                        'state': listing.state,
                        'tif_metadata': {
                            'source_crs': tif_metadata.get('source_crs'),
                            'source_width': tif_metadata.get('source_width'),
                            'source_height': tif_metadata.get('source_height'),
                            'bounds': bounds
                        }
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"[DATALAYER] Error creating DataLayer/GeoFeature: {e}", exc_info=True)
    
    def _download_tif_file(self, url: str, temp_dir: str, file_name: str) -> Optional[str]:
        """Download TIF file from CloudFront URL"""
        try:
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            tif_path = os.path.join(temp_dir, file_name)
            with open(tif_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return tif_path
            
        except Exception as e:
            logger.error(f"Error downloading TIF file: {e}")
            return None
    
    def _load_and_reproject_geotiff(self, geotiff_path, target_crs='EPSG:4326', fallback_bounds=None):
        """
        Load and reproject GeoTIFF to target CRS (optimized approach from Chennai script)
        
        Args:
            geotiff_path: Path to the GeoTIFF file
            target_crs: Target CRS (default: EPSG:4326)
            fallback_bounds: Optional fallback bounds dict with 'west', 'east', 'north', 'south'
                           to use if file is not georeferenced
        
        Returns:
            Tuple of (data_r, data_g, data_b, data_a, bounds, transform) or None on error
        """
        try:
            with rasterio.open(geotiff_path) as src:
                # Check if file is georeferenced
                # A file is considered non-georeferenced if:
                # 1. CRS is None, OR
                # 2. Transform is None or identity-like, OR
                # 3. Bounds are invalid (all zeros or identical)
                is_georeferenced = True
                try:
                    # Try to calculate transform - if this fails, file is not georeferenced
                    test_transform, _, _ = calculate_default_transform(
                        src.crs, target_crs, src.width, src.height, *src.bounds
                    )
                    # Also check if CRS is None or transform is identity
                    if src.crs is None:
                        is_georeferenced = False
                    elif src.transform is None:
                        is_georeferenced = False
                    elif (src.bounds.left == src.bounds.right or src.bounds.bottom == src.bounds.top):
                        is_georeferenced = False
                except Exception:
                    # If we can't calculate transform, file is likely not georeferenced
                    is_georeferenced = False
                
                if not is_georeferenced:
                    if fallback_bounds:
                        
                        # Read all bands
                        if src.count >= 4:
                            data_r = src.read(1)
                            data_g = src.read(2)
                            data_b = src.read(3)
                            data_a = src.read(4)
                        elif src.count == 3:
                            data_r = src.read(1)
                            data_g = src.read(2)
                            data_b = src.read(3)
                            data_a = np.full_like(data_r, 255, dtype=np.uint8)
                        elif src.count == 1:
                            data_r = src.read(1)
                            data_g = data_r.copy()
                            data_b = data_r.copy()
                            data_a = np.full_like(data_r, 255, dtype=np.uint8)
                        else:
                            logger.error(f"[REPROJECT] ❌ Unsupported number of bands: {src.count}")
                            return None
                        
                        # Create a transform that maps the image to the fallback bounds
                        width = src.width
                        height = src.height
                        west = fallback_bounds.get('west', 0)
                        east = fallback_bounds.get('east', 1)
                        north = fallback_bounds.get('north', 1)
                        south = fallback_bounds.get('south', 0)
                        
                        # Create affine transform: pixel coordinates to lat/lon
                        from rasterio.transform import from_bounds
                        transform = from_bounds(west, south, east, north, width, height)
                        
                        bounds = {
                            'west': west,
                            'south': south,
                            'east': east,
                            'north': north
                        }
                        
                        return data_r, data_g, data_b, data_a, bounds, transform
                    else:
                        logger.error(f"[REPROJECT] TIF not georeferenced and no fallback bounds")
                        return None
                
                transform, width, height = calculate_default_transform(
                    src.crs, target_crs, src.width, src.height, *src.bounds
                )
                dst_data = np.zeros((src.count, height, width), dtype=np.uint8)
                try:
                    reproject(
                        source=rasterio.band(src, list(range(1, src.count + 1))),
                        destination=dst_data,
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=target_crs,
                        resampling=Resampling.cubic_spline,
                        num_threads=self.max_workers
                    )
                except Exception as reproject_error:
                    # Check if error is about missing geotransform
                    error_msg = str(reproject_error).lower()
                    if 'no geotransform' in error_msg or 'no affine transformation' in error_msg:
                        logger.warning(f"[REPROJECT] Reprojection failed (non-georeferenced): {reproject_error}")
                        if fallback_bounds:
                            # Read image data directly
                            if src.count >= 4:
                                data_r = src.read(1)
                                data_g = src.read(2)
                                data_b = src.read(3)
                                data_a = src.read(4)
                            elif src.count == 3:
                                data_r = src.read(1)
                                data_g = src.read(2)
                                data_b = src.read(3)
                                data_a = np.full_like(data_r, 255, dtype=np.uint8)
                            elif src.count == 1:
                                data_r = src.read(1)
                                data_g = data_r.copy()
                                data_b = data_r.copy()
                                data_a = np.full_like(data_r, 255, dtype=np.uint8)
                            else:
                                logger.error(f"[REPROJECT] ❌ Unsupported number of bands: {src.count}")
                                return None
                            
                            width = src.width
                            height = src.height
                            west = fallback_bounds.get('west', 0)
                            east = fallback_bounds.get('east', 1)
                            north = fallback_bounds.get('north', 1)
                            south = fallback_bounds.get('south', 0)
                            
                            from rasterio.transform import from_bounds
                            transform = from_bounds(west, south, east, north, width, height)
                            
                            bounds = {
                                'west': west,
                                'south': south,
                                'east': east,
                                'north': north
                            }
                            
                            return data_r, data_g, data_b, data_a, bounds, transform
                        else:
                            logger.error(f"[REPROJECT] Reprojection failed, no fallback bounds: {reproject_error}")
                            return None
                    else:
                        # Different error - re-raise
                        raise
                
                # Calculate bounds in target CRS
                left, bottom = transform * (0, height)
                right, top = transform * (width, 0)
                bounds = {
                    'west': left,
                    'south': bottom,
                    'east': right,
                    'north': top
                }
                
                # Separate bands - handle different band counts
                data_r = dst_data[0]
                data_g = dst_data[1] if src.count > 1 else dst_data[0]
                data_b = dst_data[2] if src.count > 2 else dst_data[0]
                # Alpha channel: use band 4 if available, otherwise create opaque
                data_a = dst_data[3] if src.count > 3 else np.full_like(data_r, 255)
                
                return data_r, data_g, data_b, data_a, bounds, transform
                
        except Exception as e:
            logger.error(f"Error loading and reprojecting GeoTIFF: {e}", exc_info=True)
            return None
    
    def _extract_tile_optimized(self, data_r, data_g, data_b, data_a, bounds, transform, tile_bounds):
        """
        Extract tile from reprojected data (optimized approach from Chennai script)
        
        Returns:
            PIL Image or None if no data
        """
        # Calculate pixel coordinates
        inv_transform = ~transform
        
        # Get tile corners in pixel space
        ul_col, ul_row = inv_transform * (tile_bounds.west, tile_bounds.north)
        lr_col, lr_row = inv_transform * (tile_bounds.east, tile_bounds.south)
        
        # Ensure valid bounds
        min_col = int(max(0, min(ul_col, lr_col)))
        max_col = int(min(data_r.shape[1], max(ul_col, lr_col) + 1))
        min_row = int(max(0, min(ul_row, lr_row)))
        max_row = int(min(data_r.shape[0], max(ul_row, lr_row) + 1))
        
        if min_col >= max_col or min_row >= max_row:
            return None
        
        # Extract region
        region_r = data_r[min_row:max_row, min_col:max_col]
        region_g = data_g[min_row:max_row, min_col:max_col]
        region_b = data_b[min_row:max_row, min_col:max_col]
        region_a = data_a[min_row:max_row, min_col:max_col]
        
        # Check for data - skip if all transparent/empty
        if region_a.max() == 0 and region_r.max() == 0 and region_g.max() == 0 and region_b.max() == 0:
            return None
        
        # Stack into RGBA
        rgba = np.stack([region_r, region_g, region_b, region_a], axis=-1)
        img = Image.fromarray(rgba, 'RGBA')
        
        # Calculate exact positioning in 256x256 tile
        region_west, region_north = transform * (min_col, min_row)
        region_east, region_south = transform * (max_col, max_row)
        
        tile_width = tile_bounds.east - tile_bounds.west
        tile_height = tile_bounds.north - tile_bounds.south
        
        # Calculate pixel positions
        left_px = int(256 * max(0, (region_west - tile_bounds.west) / tile_width))
        right_px = int(256 * min(1, (region_east - tile_bounds.west) / tile_width))
        top_px = int(256 * max(0, (tile_bounds.north - region_north) / tile_height))
        bottom_px = int(256 * min(1, (tile_bounds.north - region_south) / tile_height))
        
        target_width = right_px - left_px
        target_height = bottom_px - top_px
        
        if target_width <= 0 or target_height <= 0:
            return None
        
        # High quality resample
        resample = Image.LANCZOS if img.width > target_width else Image.BICUBIC
        img_resized = img.resize((target_width, target_height), resample)
        
        # Create final tile
        tile = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        tile.paste(img_resized, (left_px, top_px))
        
        # Check if tile has actual content (not just transparent)
        if tile.getbbox() is None:
            return None
            
        return tile
    
    def _generate_single_tile_fast(self, data_r, data_g, data_b, data_a, bounds, transform,
                                   zoom, x, y, s3_tile_base_path):
        """
        Generate a single tile from reprojected data and upload to S3
        
        Returns:
            True if tile was generated and uploaded, False otherwise
        """
        try:
            # Get tile bounds
            tile_bounds = mercantile.bounds(x, y, zoom)
            
            # Check intersection with tolerance
            tolerance = 0.00001
            if (tile_bounds.west - tolerance > bounds['east'] or 
                tile_bounds.east + tolerance < bounds['west'] or 
                tile_bounds.south - tolerance > bounds['north'] or 
                tile_bounds.north + tolerance < bounds['south']):
                return False
            
            # Extract tile from data
            tile_img = self._extract_tile_optimized(
                data_r, data_g, data_b, data_a, bounds, transform, tile_bounds
            )
            
            if tile_img is None:
                return False
            
            # Convert to bytes
            img_bytes = io.BytesIO()
            tile_img.save(img_bytes, format='PNG', optimize=True, compress_level=6)
            img_bytes.seek(0)
            
            # Upload to S3
            s3_key = f"{s3_tile_base_path}/{zoom}/{x}/{y}.png"
            self.s3_client.upload_fileobj(
                img_bytes,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': 'image/png',
                    'CacheControl': 'public, max-age=31536000'
                }
            )
            
            return True
            
        except Exception:
            return False
    
    def _generate_tiles_from_tif(
        self,
        tif_path: str,
        s3_tile_base_path: str,
        temp_dir: str,
        media=None,
        fallback_bounds=None
    ) -> Dict:
        """
        Generate map tiles from TIF file using optimized approach (like Chennai script)
        
        Args:
            tif_path: Path to TIF file
            s3_tile_base_path: Base S3 path (e.g., 'developerland/123')
            temp_dir: Temporary directory (not used but kept for compatibility)
            media: DeveloperListingMedia instance (optional)
            fallback_bounds: Optional fallback bounds dict for non-georeferenced files
            
        Returns:
            Dict with tiles_generated, tiles_by_zoom, and tif_metadata
        """
        try:
            result = self._load_and_reproject_geotiff(tif_path, fallback_bounds=fallback_bounds)
            if not result:
                logger.error(f"[TILE_GEN] Failed to load and reproject TIF")
                return {
                    'tiles_generated': 0,
                    'tiles_by_zoom': {},
                    'tif_metadata': {}
                }
            
            data_r, data_g, data_b, data_a, bounds, transform = result
            
            # Get source TIF metadata
            source_metadata = {}
            with rasterio.open(tif_path) as src:
                source_metadata = {
                    'source_crs': str(src.crs) if src.crs else '',
                    'source_width': src.width,
                    'source_height': src.height,
                    'source_bands': src.count,
                    'source_bounds': {
                        'west': src.bounds.left,
                        'south': src.bounds.bottom,
                        'east': src.bounds.right,
                        'north': src.bounds.top
                    },
                    'reprojected_width': data_r.shape[1],
                    'reprojected_height': data_r.shape[0],
                    'bounds': bounds,
                    'transform': {
                        'a': transform.a,
                        'b': transform.b,
                        'c': transform.c,
                        'd': transform.d,
                        'e': transform.e,
                        'f': transform.f
                    }
                }
            
            total_tiles = 0
            tiles_by_zoom = {}
            num_zooms = self.max_zoom - self.min_zoom + 1
            print(f"[TIF] Generating PNG tiles for zoom levels {self.min_zoom}-{self.max_zoom} ({num_zooms} levels)...")
            
            for zoom in range(self.min_zoom, self.max_zoom + 1):
                # Calculate tile range for this zoom level
                west_south_tile = mercantile.tile(bounds['west'], bounds['south'], zoom)
                east_north_tile = mercantile.tile(bounds['east'], bounds['north'], zoom)
                
                # Get the actual tile bounds
                min_x = min(west_south_tile.x, east_north_tile.x)
                max_x = max(west_south_tile.x, east_north_tile.x)
                min_y = min(west_south_tile.y, east_north_tile.y)
                max_y = max(west_south_tile.y, east_north_tile.y)
                
                # Create tile list
                tiles_to_generate = [
                    (zoom, x, y)
                    for x in range(min_x, max_x + 1)
                    for y in range(min_y, max_y + 1)
                ]
                
                zoom_tiles = 0
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {
                        executor.submit(
                            self._generate_single_tile_fast,
                            data_r, data_g, data_b, data_a, bounds, transform,
                            tile_zoom, tile_x, tile_y, s3_tile_base_path
                        ): (tile_zoom, tile_x, tile_y)
                        for tile_zoom, tile_x, tile_y in tiles_to_generate
                    }
                    
                    for future in as_completed(futures):
                        tile_zoom, tile_x, tile_y = futures[future]
                        try:
                            success = future.result()
                            if success:
                                zoom_tiles += 1
                        except Exception as e:
                            logger.warning(f"[TILE_GEN] Error generating tile {tile_zoom}/{tile_x}/{tile_y}: {e}")
                
                tiles_by_zoom[zoom] = zoom_tiles
                total_tiles += zoom_tiles
                print(f"[TIF] Zoom {zoom}: {zoom_tiles} PNG tiles (total so far: {total_tiles})")
            
            return {
                'tiles_generated': total_tiles,
                'tiles_by_zoom': tiles_by_zoom,
                'tif_metadata': source_metadata
            }
                
        except Exception as e:
            logger.error(f"Error generating tiles from TIF: {e}", exc_info=True)
            return {
                'tiles_generated': 0,
                'tiles_by_zoom': {},
                'tif_metadata': {}
            }
    
    def fetch_listing_with_tif_files(
        self,
        listing_type: str,
        listing_id: int
    ) -> Optional[Dict]:
        """
        Fetch listing data from backend API and extract TIF files
        
        Args:
            listing_type: 'developerland' or 'developerplot'
            listing_id: Listing ID
            
        Returns:
            Dict with listing data and TIF files, or None if not found
        """
        try:
            # Construct API endpoint
            if listing_type == 'developerland':
                endpoint = f"{self.backend_api_url}/api/developer-lands/{listing_id}/"
            elif listing_type == 'developerplot':
                endpoint = f"{self.backend_api_url}/api/developer-plots/{listing_id}/"
            else:
                logger.error(f"Invalid listing_type: {listing_type}")
                return None
            
            # Fetch listing data
            response = requests.get(endpoint, timeout=30)
            response.raise_for_status()
            
            listing_data = response.json()
            
            # Extract TIF files from media
            tif_files = []
            media_key = 'developer_land_media' if listing_type == 'developerland' else 'developer_plot_media'
            media_items = listing_data.get(media_key, [])
            
            for media_item in media_items:
                # Check if it's a file type
                if media_item.get('media_type') != 'file':
                    continue
                
                # Get file URL
                file_url = media_item.get('file')
                if not file_url:
                    continue
                
                # Check if it's a TIF file
                file_name = file_url.split('/')[-1].split('?')[0]  # Remove query params
                if not file_name.lower().endswith(('.tif', '.tiff')):
                    continue
                
                # Extract S3 path from CloudFront URL
                from urllib.parse import urlparse
                parsed_url = urlparse(file_url)
                s3_path = parsed_url.path.lstrip('/')
                
                tif_file = {
                    'id': media_item.get('id'),
                    'media_type': 'file',
                    'category': media_item.get('category', ''),
                    'url': file_url,
                    'file_name': file_name,
                    's3_path': s3_path,
                    's3_tile_path': f"{listing_type}/{listing_id}/{file_name}"
                }
                tif_files.append(tif_file)
            
            if not tif_files:
                return None
            
            return {
                'listing_type': listing_type,
                'listing_id': listing_id,
                'listing_data': listing_data,
                'tif_files': tif_files,
                's3_tile_base_path': f"{listing_type}/{listing_id}"
            }
            
        except requests.RequestException as e:
            logger.error(f"Error fetching listing from backend API: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing listing data: {e}", exc_info=True)
            return None
    
    def process_existing_listing(
        self,
        listing_type: str,
        listing_id: int
    ) -> Dict:
        """
        Process an existing listing: fetch TIF files and generate tiles
        
        Args:
            listing_type: 'developerland' or 'developerplot'
            listing_id: Listing ID
            
        Returns:
            Dict with processing results
        """
        try:
            # Fetch listing data with TIF files
            listing_info = self.fetch_listing_with_tif_files(listing_type, listing_id)
            
            if not listing_info:
                return {
                    'success': False,
                    'error': f'Listing not found or no TIF files available',
                    'listing_type': listing_type,
                    'listing_id': listing_id
                }
            
            # Process TIF files
            results = []
            for tif_file in listing_info['tif_files']:
                result = self.process_tif_file(
                    tif_file=tif_file,
                    listing_type=listing_type,
                    listing_id=listing_id,
                    s3_tile_base_path=listing_info['s3_tile_base_path']
                )
                results.append(result)
            
            total_tiles = sum(r.get('tiles_generated', 0) for r in results)
            success_count = sum(1 for r in results if r.get('success', False))
            
            return {
                'success': success_count == len(results),
                'listing_type': listing_type,
                'listing_id': listing_id,
                'tif_files_processed': len(listing_info['tif_files']),
                'successful_files': success_count,
                'total_tiles_generated': total_tiles,
                'file_results': results
            }
            
        except Exception as e:
            logger.error(f"Error processing existing listing: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'listing_type': listing_type,
                'listing_id': listing_id
            }