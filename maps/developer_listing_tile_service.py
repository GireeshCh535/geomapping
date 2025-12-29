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
            
            logger.info(
                f"Processing webhook: event={event_type}, action={action}, "
                f"type={listing_type}, id={listing_id}, tif_count={len(tif_files)}"
            )
            
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
                logger.info(f"No TIF files found for {listing_type} {listing_id}")
                return {
                    'success': True,
                    'message': 'No TIF files to process',
                    'tiles_generated': 0
                }
            
            results = []
            for tif_file in tif_files:
                result = self.process_tif_file(
                    tif_file=tif_file,
                    listing_type=listing_type,
                    listing_id=listing_id,
                    s3_tile_base_path=s3_tile_base_path,
                    listing=listing
                )
                results.append(result)
            
            total_tiles = sum(r.get('tiles_generated', 0) for r in results)
            success_count = sum(1 for r in results if r.get('success', False))
            
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
        s3_tile_path = tif_file.get('s3_tile_path', f"{s3_tile_base_path}/{file_name}")
        
        logger.info(f"Processing TIF file: {file_name} from {tif_url}")
        
        # Get media record
        media = None
        if listing and media_id:
            try:
                media = DeveloperListingMedia.objects.get(
                    listing=listing,
                    backend_media_id=media_id
                )
            except DeveloperListingMedia.DoesNotExist:
                logger.warning(f"Media record not found: {media_id}")
        
        start_time = time.time()
        
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Download TIF file
                tif_path = self._download_tif_file(tif_url, temp_dir, file_name)
                if not tif_path:
                    error_msg = f'Failed to download TIF file from {tif_url}'
                    if media:
                        media.tiles_generation_error = error_msg
                        media.save()
                    return {
                        'success': False,
                        'error': error_msg,
                        'file_name': file_name
                    }
                
                # Get file size
                file_size = os.path.getsize(tif_path) if os.path.exists(tif_path) else None
                
                # Update media - mark as started
                if media:
                    media.tiles_generation_started_at = timezone.now()
                    media.save()
                
                # Generate tiles and get metadata
                result = self._generate_tiles_from_tif(
                    tif_path=tif_path,
                    s3_tile_base_path=s3_tile_path,
                    temp_dir=temp_dir,
                    media=media
                )
                
                tiles_generated = result.get('tiles_generated', 0)
                tiles_by_zoom = result.get('tiles_by_zoom', {})
                tif_metadata = result.get('tif_metadata', {})
                
                # Update media record
                if media:
                    media.tiles_generated = True
                    media.tiles_generation_completed_at = timezone.now()
                    media.total_tiles_generated = tiles_generated
                    media.tiles_generation_error = ''
                    media.save()
                
                # Save/update TIF metadata
                if media and tif_metadata:
                    TIFMetadata.objects.update_or_create(
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
                
                logger.info(
                    f"Successfully processed {file_name}: "
                    f"{tiles_generated} tiles generated and uploaded"
                )
                
                return {
                    'success': True,
                    'file_name': file_name,
                    'tiles_generated': tiles_generated,
                    's3_tile_path': s3_tile_path
                }
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error processing TIF file {file_name}: {e}", exc_info=True)
                
                # Update media
                if media:
                    media.tiles_generation_error = error_msg
                    media.save()
                
                return {
                    'success': False,
                    'error': error_msg,
                    'file_name': file_name
                }
    
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
            with rasterio.open(geotiff_path) as src:
                logger.info(f"Loading and reprojecting {geotiff_path}")
                logger.info(f"Source CRS: {src.crs}, Target CRS: {target_crs}")
                logger.info(f"Source dimensions: {src.width} x {src.height}, Bands: {src.count}")
                
                # Calculate transform for target CRS
                transform, width, height = calculate_default_transform(
                    src.crs, target_crs, src.width, src.height, *src.bounds
                )
                
                logger.info(f"Reprojecting to dimensions: {width} x {height}")
                
                # Create destination arrays (use uint8 for efficiency)
                dst_data = np.zeros((src.count, height, width), dtype=np.uint8)
                
                # Reproject with high quality resampling
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
                
                logger.info(f"Reprojected bounds: {bounds}")
                
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
            logger.info(f"Starting tile generation for {tif_path}")
            
            # Step 1: Load and reproject entire TIF to WGS84 (optimized approach)
            result = self._load_and_reproject_geotiff(tif_path)
            if not result:
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
            
            logger.info(f"Reprojected data shape: {data_r.shape}, Bounds: {bounds}")
            
            # Step 2: Generate tiles for zoom levels 8-18
            total_tiles = 0
            tiles_by_zoom = {}
            
            for zoom in range(self.min_zoom, self.max_zoom + 1):
                logger.info(f"Processing zoom level {zoom}")
                
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
                
                logger.info(f"Zoom {zoom}: Processing {len(tiles_to_generate)} potential tiles (x: {min_x}-{max_x}, y: {min_y}-{max_y})")
                
                # Generate tiles in parallel
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
                                    logger.info(f"Generated {zoom_tiles} tiles for zoom {zoom}")
                        except Exception as e:
                            logger.warning(f"Error generating tile {tile_zoom}/{tile_x}/{tile_y}: {e}")
                
                logger.info(f"Zoom {zoom}: Generated {zoom_tiles} tiles")
                tiles_by_zoom[zoom] = zoom_tiles
                total_tiles += zoom_tiles
            
            logger.info(f"Total tiles generated: {total_tiles}")
            
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

