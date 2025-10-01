#!/usr/bin/env python3
"""
Optimized Chennai Combined Masterplan Tile Generator
Fast, clear rendering with both TIFF files combined into single tiles
"""

import os
import sys
import numpy as np
from pathlib import Path
import mercantile
from PIL import Image, ImageDraw
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.merge import merge
from rasterio.enums import Resampling
import logging
import boto3
from botocore.exceptions import ClientError
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
import json
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ChennaiCombinedMasterplanTileGenerator:
    """
    Optimized tile generator for Chennai Masterplan with clear rendering and fast processing
    """
    
    def __init__(self, data_dir: str = "data/tamil_nadu/chennai/chennai_master_plan",
                 output_dir: str = "tiles/tamil-nadu/chennai/chennai_master_plan",
                 s3_bucket: str = "gis-tiles-1acre",
                 s3_prefix: str = "tamil-nadu/chennai/chennai_master_plan",
                 max_workers: int = 8):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.max_workers = max_workers
        
        # Initialize S3 client
        self.s3_client = boto3.client('s3')
        
        # Store reprojected data in memory for faster access
        self.wgs84_data = None
        self.wgs84_transform = None
        self.wgs84_bounds = None
        
        logger.info("Chennai Combined Masterplan Tile Generator initialized")
    
    def prepare_combined_dataset(self):
        """Merge and reproject both Chennai TIFF files to WGS84 with high quality"""
        # Find both TIFF files
        tiff_files = list(self.data_dir.glob("*.tif"))
        
        if len(tiff_files) < 2:
            logger.error(f"Found only {len(tiff_files)} TIFF files. Need both Chennai City and CMA files.")
            return False
        
        logger.info(f"Found TIFF files: {[f.name for f in tiff_files]}")
        
        # Open both datasets
        datasets = []
        for tiff_file in tiff_files:
            ds = rasterio.open(tiff_file)
            datasets.append(ds)
            logger.info(f"{tiff_file.name} - CRS: {ds.crs}, Bounds: {ds.bounds}, Shape: {ds.shape}")
        
        try:
            # Merge datasets using rasterio's merge function
            # This handles overlapping areas automatically
            logger.info("Merging datasets...")
            mosaic, out_trans = merge(
                datasets,
                method='max',  # Use max value for overlapping pixels
                resampling=Resampling.nearest  # Preserve exact pixel values
            )
            
            # Get merged bounds
            merged_bounds = datasets[0].bounds
            for ds in datasets[1:]:
                merged_bounds = rasterio.coords.BoundingBox(
                    min(merged_bounds.left, ds.bounds.left),
                    min(merged_bounds.bottom, ds.bounds.bottom),
                    max(merged_bounds.right, ds.bounds.right),
                    max(merged_bounds.top, ds.bounds.top)
                )
            
            # Calculate transform and dimensions for WGS84
            dst_crs = 'EPSG:4326'
            transform, width, height = calculate_default_transform(
                datasets[0].crs, dst_crs, mosaic.shape[2], mosaic.shape[1],
                left=merged_bounds.left, bottom=merged_bounds.bottom,
                right=merged_bounds.right, top=merged_bounds.top
            )
            
            # Create destination arrays for WGS84 data
            logger.info(f"Reprojecting to WGS84 with dimensions: {width} x {height}")
            dst_data = np.zeros((4, height, width), dtype=np.uint8)
            
            # Reproject with high quality settings
            reproject(
                source=mosaic,
                destination=dst_data,
                src_transform=out_trans,
                src_crs=datasets[0].crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.nearest,  # FIXED: Use nearest for sharp, clear tiles
                num_threads=self.max_workers
            )
            
            # Store in memory for fast tile generation
            self.wgs84_data = dst_data
            self.wgs84_transform = transform
            
            # Calculate WGS84 bounds
            left, bottom = transform * (0, height)
            right, top = transform * (width, 0)
            self.wgs84_bounds = {
                'west': left,
                'south': bottom,
                'east': right,
                'north': top
            }
            
            logger.info(f"WGS84 bounds: {self.wgs84_bounds}")
            
            # Close datasets
            for ds in datasets:
                ds.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Error preparing combined dataset: {e}")
            for ds in datasets:
                ds.close()
            return False
    
    def generate_tile_batch(self, tiles):
        """Generate a batch of tiles in parallel"""
        results = []
        for tile_info in tiles:
            result = self.generate_single_tile_optimized(*tile_info)
            results.append(result)
        return results
    
    def generate_single_tile_optimized(self, zoom, x, y):
        """Generate a single tile with optimized rendering"""
        try:
            tile_path = self.output_dir / str(zoom) / str(x) / f"{y}.png"
            
            # Skip if already exists
            if tile_path.exists():
                return True
            
            # Get tile bounds in WGS84
            tile_bounds = mercantile.bounds(x, y, zoom)
            
            # Check if tile intersects with data bounds (with small tolerance for edge cases)
            tolerance = 0.0001
            if (tile_bounds.west - tolerance > self.wgs84_bounds['east'] or 
                tile_bounds.east + tolerance < self.wgs84_bounds['west'] or 
                tile_bounds.south - tolerance > self.wgs84_bounds['north'] or 
                tile_bounds.north + tolerance < self.wgs84_bounds['south']):
                return False
            
            # Create tile using proper resampling
            tile_img = self.extract_tile_from_data(tile_bounds)
            
            if tile_img is not None:
                # Ensure directory exists
                tile_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Save with PNG optimization
                tile_img.save(tile_path, 'PNG', optimize=True, compress_level=6)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error generating tile {zoom}/{x}/{y}: {e}")
            return False
    
    def extract_tile_from_data(self, tile_bounds):
        """Extract tile from reprojected data with high quality resampling"""
        try:
            # Calculate pixel coordinates in source data
            inv_transform = ~self.wgs84_transform
            
            # Get corners of tile in pixel coordinates
            ul_col, ul_row = inv_transform * (tile_bounds.west, tile_bounds.north)
            lr_col, lr_row = inv_transform * (tile_bounds.east, tile_bounds.south)
            
            # Convert to integers with proper bounds checking
            min_col = int(np.floor(min(ul_col, lr_col)))
            max_col = int(np.ceil(max(ul_col, lr_col)))
            min_row = int(np.floor(min(ul_row, lr_row)))
            max_row = int(np.ceil(max(ul_row, lr_row)))
            
            # Ensure we're within data bounds
            min_col = max(0, min_col)
            max_col = min(self.wgs84_data.shape[2], max_col)
            min_row = max(0, min_row)
            max_row = min(self.wgs84_data.shape[1], max_row)
            
            # Check if we have any data in this region
            if min_col >= max_col or min_row >= max_row:
                return None
            
            # Extract the region
            region = self.wgs84_data[:, min_row:max_row, min_col:max_col]
            
            # Check if region has any non-transparent pixels
            if region.size == 0:
                return None
            
            # Check if there's actual data (only check alpha channel for transparency)
            # FIXED: Preserve ALL colors including black (0,0,0)
            has_data = False
            if region.shape[0] >= 4:  # Has alpha channel
                # Check if any non-transparent pixels exist
                alpha_channel = region[3]
                if alpha_channel.max() > 0:
                    has_data = True
            else:
                # No alpha channel, assume all data is valid
                has_data = True
            
            if not has_data:
                return None
            
            # Create RGBA image from the region
            rgba_data = np.moveaxis(region, 0, -1)  # Move channels to last dimension
            # Ensure data is uint8 for PIL
            rgba_data = rgba_data.astype(np.uint8)
            img = Image.fromarray(rgba_data)
            
            # Calculate exact positioning for the tile
            # Get the exact bounds of the extracted region in geographic coordinates
            region_west, region_north = self.wgs84_transform * (min_col, min_row)
            region_east, region_south = self.wgs84_transform * (max_col, max_row)
            
            # Calculate where this region fits in the 256x256 tile
            tile_width = tile_bounds.east - tile_bounds.west
            tile_height = tile_bounds.north - tile_bounds.south
            
            # Calculate pixel positions in the output tile
            left_px = max(0, int(256 * (region_west - tile_bounds.west) / tile_width))
            right_px = min(256, int(256 * (region_east - tile_bounds.west) / tile_width))
            top_px = max(0, int(256 * (tile_bounds.north - region_north) / tile_height))
            bottom_px = min(256, int(256 * (tile_bounds.north - region_south) / tile_height))
            
            target_width = right_px - left_px
            target_height = bottom_px - top_px
            
            if target_width <= 0 or target_height <= 0:
                return None
            
            # Resize the image to fit the tile
            # FIXED: Use NEAREST for sharp, clear tiles without blurring
            img_resized = img.resize((target_width, target_height), Image.NEAREST)
            
            # Create the final 256x256 tile
            tile = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            tile.paste(img_resized, (left_px, top_px))
            
            # Final check - make sure the tile has actual content
            if tile.getbbox() is None:
                return None
            
            return tile
            
        except Exception as e:
            logger.error(f"Error extracting tile: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def generate_tiles(self, min_zoom=8, max_zoom=16):
        """Generate tiles with parallel processing for speed"""
        logger.info("Preparing combined dataset...")
        
        if not self.prepare_combined_dataset():
            logger.error("Failed to prepare combined dataset")
            return 0
        
        logger.info("Starting tile generation...")
        logger.info(f"Data bounds: {self.wgs84_bounds}")
        
        total_tiles = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            logger.info(f"Processing zoom level {zoom}")
            
            # Calculate tile range for this zoom level - FIX THE CALCULATION
            # Get tiles for all four corners to ensure complete coverage
            west_south_tile = mercantile.tile(self.wgs84_bounds['west'], self.wgs84_bounds['south'], zoom)
            east_north_tile = mercantile.tile(self.wgs84_bounds['east'], self.wgs84_bounds['north'], zoom)
            west_north_tile = mercantile.tile(self.wgs84_bounds['west'], self.wgs84_bounds['north'], zoom)
            east_south_tile = mercantile.tile(self.wgs84_bounds['east'], self.wgs84_bounds['south'], zoom)
            
            # Get the actual range
            min_x = min(west_south_tile.x, east_north_tile.x, west_north_tile.x, east_south_tile.x)
            max_x = max(west_south_tile.x, east_north_tile.x, west_north_tile.x, east_south_tile.x)
            min_y = min(west_south_tile.y, east_north_tile.y, west_north_tile.y, east_south_tile.y)
            max_y = max(west_south_tile.y, east_north_tile.y, west_north_tile.y, east_south_tile.y)
            
            logger.info(f"Tile range for zoom {zoom}: x={min_x}-{max_x}, y={min_y}-{max_y}")
            
            # Prepare list of tiles to generate
            tiles_to_generate = []
            for x in range(min_x, max_x + 1):
                for y in range(min_y, max_y + 1):
                    tiles_to_generate.append((zoom, x, y))
            
            logger.info(f"Will process {len(tiles_to_generate)} potential tiles at zoom {zoom}")
            
            # Generate tiles in parallel
            zoom_tiles = 0
            batch_size = 50  # Smaller batch size for better progress tracking
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                
                # Submit all tiles as individual tasks for better parallelization
                for tile_info in tiles_to_generate:
                    future = executor.submit(self.generate_single_tile_optimized, *tile_info)
                    futures.append(future)
                
                # Process results as they complete
                for i, future in enumerate(as_completed(futures), 1):
                    if future.result():
                        zoom_tiles += 1
                        total_tiles += 1
                        
                        if zoom_tiles % 100 == 0:
                            logger.info(f"  Generated {zoom_tiles} tiles at zoom {zoom}...")
                    
                    if i % 100 == 0:
                        logger.info(f"  Processed {i}/{len(tiles_to_generate)} tiles at zoom {zoom}")
            
            logger.info(f"Zoom {zoom}: Generated {zoom_tiles} tiles")
        
        logger.info(f"Total tiles generated: {total_tiles}")
        
        # Create supporting files
        self.create_supporting_files(min_zoom, max_zoom)
        
        return total_tiles
    
    def create_supporting_files(self, min_zoom, max_zoom):
        """Create supporting files for the tile set"""
        logger.info("Creating supporting files...")
        
        # Create TileJSON
        tilejson = {
            "tilejson": "2.2.0",
            "name": "Chennai Combined Master Plan",
            "description": "High-quality combined master plan tiles for Chennai City and CMA",
            "version": "2.0.0",
            "attribution": "Chennai Metropolitan Development Authority",
            "scheme": "xyz",
            "tiles": [
                f"https://d17yosovmfjm4.cloudfront.net/{self.s3_prefix}/{{z}}/{{x}}/{{y}}.png"
            ],
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "bounds": [
                self.wgs84_bounds['west'],
                self.wgs84_bounds['south'],
                self.wgs84_bounds['east'],
                self.wgs84_bounds['north']
            ],
            "center": [
                (self.wgs84_bounds['west'] + self.wgs84_bounds['east']) / 2,
                (self.wgs84_bounds['south'] + self.wgs84_bounds['north']) / 2,
                10
            ]
        }
        
        import json
        with open(self.output_dir / "tilejson.json", "w") as f:
            json.dump(tilejson, f, indent=2)
        
        logger.info("Created tilejson.json")
    
    def upload_to_s3(self, delete_existing=True):
        """Upload tiles to S3 with parallel uploads"""
        logger.info(f"Starting S3 upload to s3://{self.s3_bucket}/{self.s3_prefix}")
        
        if not self.output_dir.exists():
            logger.error(f"Output directory {self.output_dir} does not exist")
            return False
        
        # Delete existing files if requested
        if delete_existing:
            logger.info("Deleting existing files in S3...")
            self.delete_s3_files()
        
        # Collect all files to upload
        files_to_upload = []
        for png_file in self.output_dir.rglob("*.png"):
            relative_path = png_file.relative_to(self.output_dir)
            s3_key = f"{self.s3_prefix}/{relative_path}"
            files_to_upload.append((str(png_file), s3_key))
        
        # Also add supporting files
        for filename in ['tilejson.json']:
            file_path = self.output_dir / filename
            if file_path.exists():
                s3_key = f"{self.s3_prefix}/{filename}"
                files_to_upload.append((str(file_path), s3_key))
        
        logger.info(f"Found {len(files_to_upload)} files to upload")
        
        # Upload in parallel
        uploaded_count = 0
        failed_count = 0
        
        def upload_file(file_info):
            file_path, s3_key = file_info
            try:
                content_type = 'image/png' if file_path.endswith('.png') else 'application/json'
                self.s3_client.upload_file(
                    file_path,
                    self.s3_bucket,
                    s3_key,
                    ExtraArgs={
                        'ContentType': content_type,
                        'CacheControl': 'public, max-age=31536000'
                    }
                )
                return True
            except ClientError as e:
                logger.error(f"Error uploading {file_path}: {e}")
                return False
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(upload_file, f) for f in files_to_upload]
            
            for future in as_completed(futures):
                if future.result():
                    uploaded_count += 1
                else:
                    failed_count += 1
                
                if uploaded_count % 100 == 0:
                    logger.info(f"Uploaded {uploaded_count}/{len(files_to_upload)} files...")
        
        logger.info(f"Upload complete: {uploaded_count} successful, {failed_count} failed")
        return uploaded_count > 0
    
    def delete_s3_files(self):
        """Delete existing files in S3 prefix"""
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=self.s3_prefix)
            
            objects_to_delete = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects_to_delete.append({'Key': obj['Key']})
            
            if objects_to_delete:
                # Delete in batches of 1000
                for i in range(0, len(objects_to_delete), 1000):
                    batch = objects_to_delete[i:i+1000]
                    self.s3_client.delete_objects(
                        Bucket=self.s3_bucket,
                        Delete={'Objects': batch}
                    )
                logger.info(f"Deleted {len(objects_to_delete)} existing files from S3")
            
        except ClientError as e:
            logger.error(f"Error deleting S3 files: {e}")

def main():
    """Main function with command line arguments"""
    parser = argparse.ArgumentParser(description='Optimized Chennai Combined Masterplan Tile Generator')
    parser.add_argument('--min-zoom', type=int, default=17, 
                       help='Minimum zoom level (default: 8)')
    parser.add_argument('--max-zoom', type=int, default=18, 
                       help='Maximum zoom level (default: 16)')
    parser.add_argument('--workers', type=int, default=8,
                       help='Number of parallel workers (default: 8)')
    parser.add_argument('--upload', action='store_true', 
                       help='Upload tiles to S3 after generation')
    parser.add_argument('--s3-bucket', default='gis-tiles-1acre', 
                       help='S3 bucket name')
    parser.add_argument('--s3-prefix', default='chennai/masterplan', 
                       help='S3 prefix')
    parser.add_argument('--data-dir', default='data/tamil_nadu/chennai/chennai_master_plan', 
                       help='Data directory')
    parser.add_argument('--output-dir', default='chennai_combined_masterplan_tiles', 
                       help='Output directory')
    
    args = parser.parse_args()
    
    logger.info("="*70)
    logger.info("Chennai Combined Masterplan Tile Generator - Optimized Version")
    logger.info("="*70)
    logger.info("Configuration:")
    for key, value in vars(args).items():
        logger.info(f"  {key}: {value}")
    logger.info("="*70)
    
    # Initialize generator
    generator = ChennaiCombinedMasterplanTileGenerator(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        s3_bucket=args.s3_bucket,
        s3_prefix=args.s3_prefix,
        max_workers=args.workers
    )
    
    # Generate tiles
    start_time = time.time()
    total_tiles = generator.generate_tiles(
        min_zoom=args.min_zoom, 
        max_zoom=args.max_zoom
    )
    elapsed_time = time.time() - start_time
    
    if total_tiles > 0:
        logger.info("="*70)
        logger.info(f"✓ Successfully generated {total_tiles} tiles in {elapsed_time:.1f} seconds")
        logger.info(f"  Average: {total_tiles/elapsed_time:.1f} tiles/second")
        logger.info("="*70)
        
        # Upload to S3 if requested
        if args.upload:
            logger.info("\nStarting S3 upload...")
            upload_start = time.time()
            if generator.upload_to_s3():
                upload_time = time.time() - upload_start
                logger.info("="*70)
                logger.info(f"✓ S3 upload completed in {upload_time:.1f} seconds")
                logger.info("="*70)
            else:
                logger.error("✗ S3 upload encountered errors")
    else:
        logger.warning("No tiles were generated - check your data files and bounds")
    
    logger.info("\n✓ Process completed!")

if __name__ == "__main__":
    main()