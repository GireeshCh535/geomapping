"""
Service for generating tiles from developer listing TIF files
Downloads TIF files from CloudFront, generates tiles, and uploads to S3
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
        self.bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'gis-portal')
        self.region = getattr(settings, 'AWS_S3_REGION_NAME', 'ap-south-1')
        self.s3_client = boto3.client(
            's3',
            region_name=self.region,
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        )
        # CloudFront client for cache invalidation
        self.cloudfront_client = None
        self.cloudfront_distribution_id = getattr(settings, 'CLOUDFRONT_DISTRIBUTION_ID', None)
        self.enable_cloudfront_invalidation = getattr(settings, 'ENABLE_CLOUDFRONT_INVALIDATION', True)
        if self.enable_cloudfront_invalidation and self.cloudfront_distribution_id:
            try:
                self.cloudfront_client = boto3.client(
                    'cloudfront',
                    region_name='us-east-1',  # CloudFront API is always us-east-1
                    aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
                    aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
                )
                logger.info(f"[CLOUDFRONT] ✅ CloudFront invalidation enabled for distribution: {self.cloudfront_distribution_id}")
            except Exception as e:
                logger.warning(f"[CLOUDFRONT] ⚠️  Failed to initialize CloudFront client: {e}")
                self.cloudfront_client = None
        else:
            if not self.cloudfront_distribution_id:
                logger.warning(f"[CLOUDFRONT] ⚠️  CloudFront distribution ID not configured, invalidation disabled")
            else:
                logger.info(f"[CLOUDFRONT] ℹ️  CloudFront invalidation disabled via settings")
        
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
            event_type = webhook_data.get('event_type', '')
            action = webhook_data.get('action', '')
            listing_type = webhook_data.get('listing_type', '')
            listing_id = webhook_data.get('listing_id')
            tif_files = webhook_data.get('tif_files', [])
            s3_tile_base_path = webhook_data.get('s3_tile_base_path', '')
            
            logger.info(f"[TILE_GEN] ===== Starting tile generation process =====")
            logger.info(f"[TILE_GEN] 📋 Event: {event_type}, Action: {action}")
            logger.info(f"[TILE_GEN] 📋 Listing: {listing_type} ID={listing_id}")
            logger.info(f"[TILE_GEN] 📋 TIF files to process: {len(tif_files)}")
            
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
                logger.info(f"[TILE_GEN] ⚠️  No TIF files found for {listing_type} {listing_id}")
                logger.info(f"[TILE_GEN] ===== Process completed (no TIF files) =====")
                return {
                    'success': True,
                    'message': 'No TIF files to process',
                    'tiles_generated': 0
                }
            
            logger.info(f"[TILE_GEN] 🔄 Processing {len(tif_files)} TIF file(s)...")
            results = []
            for idx, tif_file in enumerate(tif_files, 1):
                file_name = tif_file.get('file_name', 'unknown')
                logger.info(f"[TILE_GEN] 📄 Processing TIF {idx}/{len(tif_files)}: {file_name}")
                
                result = self.process_tif_file(
                    tif_file=tif_file,
                    listing_type=listing_type,
                    listing_id=listing_id,
                    s3_tile_base_path=s3_tile_base_path,
                    listing=listing
                )
                results.append(result)
                
                if result.get('success'):
                    logger.info(f"[TILE_GEN] ✅ TIF {idx} processed: {result.get('tiles_generated', 0)} tiles generated")
                else:
                    logger.error(f"[TILE_GEN] ❌ TIF {idx} failed: {result.get('error', 'Unknown error')}")
            
            total_tiles = sum(r.get('tiles_generated', 0) for r in results)
            success_count = sum(1 for r in results if r.get('success', False))
            
            logger.info(f"[TILE_GEN] ===== Tile generation process completed =====")
            logger.info(f"[TILE_GEN] 📊 Summary:")
            logger.info(f"[TILE_GEN]    - Files processed: {len(tif_files)}")
            logger.info(f"[TILE_GEN]    - Successful: {success_count}")
            logger.info(f"[TILE_GEN]    - Failed: {len(tif_files) - success_count}")
            logger.info(f"[TILE_GEN]    - Total tiles generated: {total_tiles}")
            
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
            logger.info(f"[S3_CLEANUP] 🗑️  Deleting tiles from S3: {s3_tile_path}")
            logger.info(f"[S3_CLEANUP]    ⚠️  This will ONLY delete tiles matching this specific path prefix")
            
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
                logger.info(f"[S3_CLEANUP] ℹ️  No existing tiles found at {prefix}")
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
            
            logger.info(f"[S3_CLEANUP] ✅ Deleted {deleted_count} old tiles from {prefix}")
            
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
            logger.debug(f"[CLOUDFRONT] ⚠️  CloudFront invalidation disabled or not configured")
            return None
        
        try:
            logger.info(f"[CLOUDFRONT] 🔄 Creating CloudFront invalidation for {len(paths)} path(s)...")
            logger.info(f"[CLOUDFRONT]    Paths: {paths}")
            
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
            status = response.get('Invalidation', {}).get('Status')
            
            logger.info(f"[CLOUDFRONT] ✅ CloudFront invalidation created: ID={invalidation_id}, Status={status}")
            logger.info(f"[CLOUDFRONT]    ⚠️  Cache will be cleared in a few minutes")
            
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
        
        logger.info(f"[TIF_PROCESS] ===== Processing TIF file =====")
        logger.info(f"[TIF_PROCESS] 📄 File: {file_name}")
        logger.info(f"[TIF_PROCESS] 🔗 URL: {tif_url}")
        logger.info(f"[TIF_PROCESS] 📍 S3 tile path: {s3_tile_path}")
        
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
                    logger.info(f"[TIF_PROCESS] 🔄 Media has different old tile path: {old_s3_tile_path}")
            except DeveloperListingMedia.DoesNotExist:
                logger.warning(f"Media record not found: {media_id}")
        
        # Delete old tiles before generating new ones
        # This handles cases where:
        # 1. File updated with same name (same path) - delete old tiles, generate new ones to same path
        # 2. File updated with different name (different path) - delete old path, generate to new path
        # 3. Media is updated/recreated (same backend_media_id, potentially different file/path)
        # 4. File is deleted and recreated
        logger.info(f"[TIF_PROCESS] 🗑️  Cleaning up old tiles before generating new ones...")
        
        # Always delete tiles from new path first (handles case where file is updated with same name)
        # This ensures we clean up any existing tiles before generating new ones
        logger.info(f"[TIF_PROCESS]    ⚠️  Deleting tiles from target path: {s3_tile_path}")
        deleted_new = self._delete_s3_tiles(s3_tile_path)
        
        # If path changed, also delete from old path
        # (If path is same, we already deleted above, so this is just for different paths)
        deleted_old = 0
        if old_s3_tile_path and old_s3_tile_path != s3_tile_path:
            logger.info(f"[TIF_PROCESS]    ⚠️  Path changed, also deleting tiles from old path: {old_s3_tile_path}")
            deleted_old = self._delete_s3_tiles(old_s3_tile_path)
            logger.info(f"[TIF_PROCESS] 🗑️  Deleted {deleted_old} tiles from old path: {old_s3_tile_path}")
        elif old_s3_tile_path and old_s3_tile_path == s3_tile_path:
            logger.info(f"[TIF_PROCESS]    ℹ️  File updated with same name/path - old tiles already deleted above")
        
        total_deleted = deleted_new + deleted_old
        if total_deleted > 0:
            logger.info(f"[TIF_PROCESS] ✅ Cleanup complete: {total_deleted} old tiles deleted")
        else:
            logger.info(f"[TIF_PROCESS] ℹ️  No old tiles found to delete (first time processing)")
        
        start_time = time.time()
        
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Download TIF file
                logger.info(f"[TIF_PROCESS] ⬇️  Downloading TIF file from CloudFront...")
                tif_path = self._download_tif_file(tif_url, temp_dir, file_name)
                if not tif_path:
                    error_msg = f'Failed to download TIF file from {tif_url}'
                    logger.error(f"[TIF_PROCESS] ❌ Download failed: {error_msg}")
                    if media:
                        media.tiles_generation_error = error_msg
                        media.save()
                    return {
                        'success': False,
                        'error': error_msg,
                        'file_name': file_name
                    }
                
                logger.info(f"[TIF_PROCESS] ✅ TIF file downloaded: {tif_path}")
                
                # Get file size
                file_size = os.path.getsize(tif_path) if os.path.exists(tif_path) else None
                logger.info(f"[TIF_PROCESS] 📦 File size: {file_size / (1024*1024):.2f} MB" if file_size else "[TIF_PROCESS] 📦 File size: unknown")
                
                # Update media - mark as started
                if media:
                    logger.info(f"[TIF_PROCESS] 💾 Updating media record: marking as started...")
                    media.tiles_generation_started_at = timezone.now()
                    media.save()
                    logger.info(f"[TIF_PROCESS] ✅ Media record updated")
                
                # Generate tiles and get metadata
                logger.info(f"[TIF_PROCESS] 🗺️  Starting tile generation (zoom {self.min_zoom}-{self.max_zoom})...")
                result = self._generate_tiles_from_tif(
                    tif_path=tif_path,
                    s3_tile_base_path=s3_tile_path,
                    temp_dir=temp_dir,
                    media=media
                )
                
                tiles_generated = result.get('tiles_generated', 0)
                tiles_by_zoom = result.get('tiles_by_zoom', {})
                tif_metadata = result.get('tif_metadata', {})
                
                logger.info(f"[TIF_PROCESS] ✅ Tile generation completed: {tiles_generated} tiles")
                logger.info(f"[TIF_PROCESS] 📊 Tiles by zoom: {tiles_by_zoom}")
                
                # Update media record
                if media:
                    logger.info(f"[TIF_PROCESS] 💾 Updating media record: marking as completed...")
                    media.tiles_generated = True
                    media.tiles_generation_completed_at = timezone.now()
                    media.total_tiles_generated = tiles_generated
                    media.tiles_generation_error = ''
                    media.save()
                    logger.info(f"[TIF_PROCESS] ✅ Media record updated: tiles_generated=True, total={tiles_generated}")
                
                # Save/update TIF metadata
                if media and tif_metadata:
                    logger.info(f"[TIF_PROCESS] 💾 Saving TIF metadata to database...")
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
                    logger.info(f"[TIF_PROCESS] ✅ TIF metadata saved")
                    logger.info(f"[TIF_PROCESS] 📐 Bounds: west={tif_metadata.get('bounds', {}).get('west')}, "
                              f"east={tif_metadata.get('bounds', {}).get('east')}, "
                              f"south={tif_metadata.get('bounds', {}).get('south')}, "
                              f"north={tif_metadata.get('bounds', {}).get('north')}")
                    
                    # Create/Update DataLayer and GeoFeature for spatial querying
                    logger.info(f"[TIF_PROCESS] 🗺️  Creating DataLayer and GeoFeature for spatial queries...")
                    self._create_datalayer_and_geofeature(
                        listing=listing,
                        media=media,
                        tif_metadata=tif_metadata,
                        s3_tile_path=s3_tile_path
                    )
                    logger.info(f"[TIF_PROCESS] ✅ DataLayer and GeoFeature created")
                
                logger.info(f"[TIF_PROCESS] ✅ Successfully processed {file_name}")
                logger.info(f"[TIF_PROCESS]    - Tiles generated: {tiles_generated}")
                logger.info(f"[TIF_PROCESS]    - Processing time: {time.time() - start_time:.2f}s")
                
                # Invalidate CloudFront cache for newly generated tiles
                if tiles_generated > 0:
                    invalidation_path = f"{s3_tile_path.rstrip('/')}/*"
                    logger.info(f"[TIF_PROCESS] 🔄 Invalidating CloudFront cache for new tiles...")
                    invalidation_id = self._invalidate_cloudfront_paths([invalidation_path])
                    if invalidation_id:
                        logger.info(f"[TIF_PROCESS] ✅ CloudFront invalidation created: {invalidation_id}")
                    else:
                        logger.warning(f"[TIF_PROCESS] ⚠️  CloudFront invalidation skipped or failed")
                
                logger.info(f"[TIF_PROCESS] ===== TIF processing completed =====")
                
                return {
                    'success': True,
                    'file_name': file_name,
                    'tiles_generated': tiles_generated,
                    's3_tile_path': s3_tile_path
                }
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[TIF_PROCESS] ❌ Error processing TIF file {file_name}: {e}", exc_info=True)
                
                # Update media
                if media:
                    logger.error(f"[TIF_PROCESS] 💾 Updating media record with error...")
                    media.tiles_generation_error = error_msg
                    media.save()
                    logger.error(f"[TIF_PROCESS] ✅ Media record updated with error")
                
                logger.error(f"[TIF_PROCESS] ===== TIF processing failed =====")
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
            
            logger.info(f"[DATALAYER] {'✅ Created' if created else '🔄 Updated'} DataLayer: {layer_name}")
            
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
                        'tile_url_template': f"https://d3js84ohvqla36.cloudfront.net/{s3_tile_path}/{{z}}/{{x}}/{{y}}.png",
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
            
            logger.info(f"[DATALAYER] {'✅ Created' if created else '🔄 Updated'} GeoFeature with bounds polygon")
            logger.info(f"[DATALAYER] 📍 Polygon: {polygon.wkt[:100]}...")
            logger.info(f"[DATALAYER] 📊 Area: {area_sqkm:.2f} sq km")
            logger.info(f"[DATALAYER] ✅ TIF now available for spatial queries!")
            
        except Exception as e:
            logger.error(f"[DATALAYER] ❌ Error creating DataLayer/GeoFeature: {e}", exc_info=True)
    
    def _download_tif_file(self, url: str, temp_dir: str, file_name: str) -> Optional[str]:
        """Download TIF file from CloudFront URL"""
        try:
            logger.info(f"Downloading TIF file from {url}")
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            tif_path = os.path.join(temp_dir, file_name)
            with open(tif_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(tif_path)
            logger.info(f"Downloaded {file_name}: {file_size / (1024*1024):.2f} MB")
            
            return tif_path
            
        except Exception as e:
            logger.error(f"Error downloading TIF file: {e}")
            return None
    
    def _load_and_reproject_geotiff(self, geotiff_path, target_crs='EPSG:4326'):
        """
        Load and reproject GeoTIFF to target CRS (optimized approach from Chennai script)
        
        Returns:
            Tuple of (data_r, data_g, data_b, data_a, bounds, transform) or None on error
        """
        try:
            logger.info(f"[REPROJECT] 🔄 Loading TIF file...")
            with rasterio.open(geotiff_path) as src:
                logger.info(f"[REPROJECT] 📄 File: {geotiff_path}")
                logger.info(f"[REPROJECT] 📐 Source CRS: {src.crs}, Target CRS: {target_crs}")
                logger.info(f"[REPROJECT] 📐 Source dimensions: {src.width} x {src.height}, Bands: {src.count}")
                logger.info(f"[REPROJECT] 📐 Source bounds: {src.bounds}")
                
                # Calculate transform for target CRS
                transform, width, height = calculate_default_transform(
                    src.crs, target_crs, src.width, src.height, *src.bounds
                )
                
                logger.info(f"[REPROJECT] 🔄 Reprojecting to dimensions: {width} x {height}...")
                
                # Create destination arrays (use uint8 for efficiency)
                dst_data = np.zeros((src.count, height, width), dtype=np.uint8)
                
                # Reproject with high quality resampling
                logger.info(f"[REPROJECT] 🔄 Performing reprojection (this may take a while)...")
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
                
                logger.info(f"[REPROJECT] ✅ Reprojection completed")
                
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
                
                logger.info(f"[REPROJECT] ✅ Reprojected bounds: {bounds}")
                logger.info(f"[REPROJECT] ✅ Data bands: R={data_r.shape}, G={data_g.shape}, B={data_b.shape}, A={data_a.shape}")
                
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
            
        except Exception as e:
            logger.debug(f"Error generating tile {zoom}/{x}/{y}: {e}")
            return False
    
    def _generate_tiles_from_tif(
        self,
        tif_path: str,
        s3_tile_base_path: str,
        temp_dir: str,
        media=None
    ) -> Dict:
        """
        Generate map tiles from TIF file using optimized approach (like Chennai script)
        
        Args:
            tif_path: Path to TIF file
            s3_tile_base_path: Base S3 path (e.g., 'developerland/123')
            temp_dir: Temporary directory (not used but kept for compatibility)
            media: DeveloperListingMedia instance (optional)
            job: TileGenerationJob instance (optional)
            
        Returns:
            Dict with tiles_generated, tiles_by_zoom, and tif_metadata
        """
        try:
            logger.info(f"[TILE_GEN] ===== Starting tile generation =====")
            logger.info(f"[TILE_GEN] 📄 TIF file: {tif_path}")
            
            # Step 1: Load and reproject entire TIF to WGS84 (optimized approach)
            logger.info(f"[TILE_GEN] 🔄 Step 1: Loading and reprojecting TIF to WGS84...")
            result = self._load_and_reproject_geotiff(tif_path)
            if not result:
                logger.error(f"[TILE_GEN] ❌ Failed to load and reproject TIF file")
                return {
                    'tiles_generated': 0,
                    'tiles_by_zoom': {},
                    'tif_metadata': {}
                }
            
            data_r, data_g, data_b, data_a, bounds, transform = result
            logger.info(f"[TILE_GEN] ✅ TIF loaded and reprojected successfully")
            
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
            
            logger.info(f"[TILE_GEN] 📐 Reprojected data shape: {data_r.shape}")
            logger.info(f"[TILE_GEN] 📐 Bounds: west={bounds['west']:.6f}, east={bounds['east']:.6f}, "
                      f"south={bounds['south']:.6f}, north={bounds['north']:.6f}")
            
            # Step 2: Generate tiles for zoom levels 8-18
            logger.info(f"[TILE_GEN] 🔄 Step 2: Generating tiles for zoom levels {self.min_zoom}-{self.max_zoom}...")
            total_tiles = 0
            tiles_by_zoom = {}
            
            for zoom in range(self.min_zoom, self.max_zoom + 1):
                logger.info(f"[TILE_GEN] 🔍 Processing zoom level {zoom}...")
                
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
                
                logger.info(f"[TILE_GEN] 📊 Zoom {zoom}: {len(tiles_to_generate)} potential tiles "
                          f"(x: {min_x}-{max_x}, y: {min_y}-{max_y})")
                
                # Generate tiles in parallel
                logger.info(f"[TILE_GEN] 🚀 Generating tiles in parallel (workers: {self.max_workers})...")
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
                                if zoom_tiles % 100 == 0:
                                    logger.info(f"[TILE_GEN] 📈 Progress: {zoom_tiles} tiles generated for zoom {zoom}")
                        except Exception as e:
                            logger.warning(f"[TILE_GEN] ⚠️  Error generating tile {tile_zoom}/{tile_x}/{tile_y}: {e}")
                
                logger.info(f"[TILE_GEN] ✅ Zoom {zoom}: Generated {zoom_tiles} tiles")
                tiles_by_zoom[zoom] = zoom_tiles
                total_tiles += zoom_tiles
            
            logger.info(f"[TILE_GEN] ✅ Total tiles generated: {total_tiles}")
            logger.info(f"[TILE_GEN] ===== Tile generation completed =====")
            
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
            
            logger.info(f"Fetching listing data from: {endpoint}")
            
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
                logger.info(f"No TIF files found for {listing_type} {listing_id}")
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

