#!/usr/bin/env python3
"""
Optimized Chennai Masterplan Tile Generation Script
Fast, clear rendering with support for individual or combined TIFF processing
"""

import os
import sys
import numpy as np
from pathlib import Path
import mercantile
from PIL import Image
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.merge import merge
import logging
import boto3
from botocore.exceptions import ClientError
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ChennaiMasterplanTileGenerator:
    """
    Optimized Chennai Masterplan Tile Generator with clear rendering and fast processing
    """
    
    def __init__(self, data_dir: str = "data/chennai/chennai_master_plan",
                 output_dir: str = "chennai_masterplan_tiles",
                 s3_bucket: str = "gis-tiles-1acre",
                 s3_prefix: str = "chennai/masterplan",
                 max_workers: int = 8):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.max_workers = max_workers
        
        # Initialize S3 client
        self.s3_client = boto3.client('s3')
        
        # Cache for reprojected data
        self.data_cache = {}
        
        logger.info("Chennai Masterplan Tile Generator initialized")
    
    def analyze_geotiff(self, geotiff_path):
        """Analyze a GeoTIFF file to understand its structure"""
        logger.info(f"Analyzing GeoTIFF: {geotiff_path}")
        
        try:
            with rasterio.open(geotiff_path) as src:
                logger.info(f"Number of bands: {src.count}")
                logger.info(f"Color interpretation: {src.colorinterp}")
                logger.info(f"Data shape: {src.shape}")
                logger.info(f"Data type: {src.dtypes}")
                logger.info(f"CRS: {src.crs}")
                logger.info(f"Bounds: {src.bounds}")
                
                # Quick data check
                sample = src.read(1, window=rasterio.windows.Window(0, 0, min(1000, src.width), min(1000, src.height)))
                non_zero = np.count_nonzero(sample)
                logger.info(f"Non-zero pixels in sample: {non_zero}")
                
                return True
                
        except Exception as e:
            logger.error(f"Error analyzing {geotiff_path}: {e}")
            return False
    
    def load_and_reproject_geotiff(self, geotiff_path, target_crs='EPSG:4326'):
        """Load and reproject GeoTIFF to target CRS with high quality"""
        cache_key = str(geotiff_path)
        
        # Check cache first
        if cache_key in self.data_cache:
            logger.info(f"Using cached data for {geotiff_path.name}")
            return self.data_cache[cache_key]
        
        with rasterio.open(geotiff_path) as src:
            logger.info(f"Loading and reprojecting {geotiff_path.name}")
            logger.info(f"Source CRS: {src.crs}, Target CRS: {target_crs}")
            
            # Calculate transform for target CRS
            transform, width, height = calculate_default_transform(
                src.crs, target_crs, src.width, src.height, *src.bounds
            )
            
            # Create destination arrays
            logger.info(f"Reprojecting to dimensions: {width} x {height}")
            dst_data = np.zeros((src.count, height, width), dtype=np.uint8)
            
            # Reproject with high quality
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
            
            # Separate bands
            data_r = dst_data[0]
            data_g = dst_data[1] if src.count > 1 else dst_data[0]
            data_b = dst_data[2] if src.count > 2 else dst_data[0]
            data_a = dst_data[3] if src.count > 3 else np.full_like(data_r, 255)
            
            result = (data_r, data_g, data_b, data_a, bounds, transform)
            
            # Cache the result
            self.data_cache[cache_key] = result
            
            return result
    
    def combine_geotiffs(self, tiff_files):
        """Combine multiple GeoTIFF files into a single dataset"""
        logger.info(f"Combining {len(tiff_files)} TIFF files")
        
        # Open all datasets
        datasets = []
        for tiff_file in tiff_files:
            ds = rasterio.open(tiff_file)
            datasets.append(ds)
            logger.info(f"{tiff_file.name}: {ds.bounds}")
        
        try:
            # Merge datasets
            logger.info("Merging datasets...")
            mosaic, out_trans = merge(
                datasets,
                method='max',  # Use max value for overlapping pixels
                resampling=Resampling.nearest
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
            
            # Reproject to WGS84
            dst_crs = 'EPSG:4326'
            transform, width, height = calculate_default_transform(
                datasets[0].crs, dst_crs, mosaic.shape[2], mosaic.shape[1],
                *merged_bounds
            )
            
            logger.info(f"Reprojecting combined data to WGS84: {width} x {height}")
            dst_data = np.zeros((4, height, width), dtype=np.uint8)
            
            reproject(
                source=mosaic,
                destination=dst_data,
                src_transform=out_trans,
                src_crs=datasets[0].crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.cubic_spline,
                num_threads=self.max_workers
            )
            
            # Calculate WGS84 bounds
            left, bottom = transform * (0, height)
            right, top = transform * (width, 0)
            bounds = {
                'west': left,
                'south': bottom,
                'east': right,
                'north': top
            }
            
            # Close datasets
            for ds in datasets:
                ds.close()
            
            return dst_data[0], dst_data[1], dst_data[2], dst_data[3], bounds, transform
            
        except Exception as e:
            logger.error(f"Error combining datasets: {e}")
            for ds in datasets:
                ds.close()
            return None
    
    def generate_single_tile_fast(self, data_r, data_g, data_b, data_a, bounds, transform, zoom, x, y):
        """Generate a single tile with optimized rendering"""
        tile_path = self.output_dir / str(zoom) / str(x) / f"{y}.png"
        
        # Skip if exists
        if tile_path.exists():
            return tile_path, True
        
        # Get tile bounds
        tile_bounds = mercantile.bounds(x, y, zoom)
        
        # Check intersection with more tolerance
        tolerance = 0.00001
        if (tile_bounds.west - tolerance > bounds['east'] or 
            tile_bounds.east + tolerance < bounds['west'] or 
            tile_bounds.south - tolerance > bounds['north'] or 
            tile_bounds.north + tolerance < bounds['south']):
            return tile_path, False
        
        # Extract tile from data
        tile_img = self.extract_tile_optimized(
            data_r, data_g, data_b, data_a, bounds, transform, tile_bounds
        )
        
        if tile_img is not None:
            tile_path.parent.mkdir(parents=True, exist_ok=True)
            tile_img.save(tile_path, 'PNG', optimize=True, compress_level=6)
            return tile_path, True
        
        return tile_path, False
    
    def extract_tile_optimized(self, data_r, data_g, data_b, data_a, bounds, transform, tile_bounds):
        """Extract tile with high quality resampling"""
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
        
        # Check for data - be more lenient
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
    
    def generate_tiles_parallel(self, data_r, data_g, data_b, data_a, bounds, transform, 
                               min_zoom, max_zoom, output_dir):
        """Generate tiles in parallel for speed"""
        # Update output_dir for this specific call
        self.output_dir = output_dir
        total_tiles = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            logger.info(f"Processing zoom level {zoom}")
            
            # Calculate tile range - handle the Y-axis correctly
            # mercantile.tile returns the tile containing the point
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
            
            # Generate in parallel
            zoom_tiles = 0
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Create partial function with data
                futures = []
                for tile_zoom, tile_x, tile_y in tiles_to_generate:
                    future = executor.submit(
                        self.generate_single_tile_fast,
                        data_r, data_g, data_b, data_a, bounds, transform,
                        tile_zoom, tile_x, tile_y
                    )
                    futures.append(future)
                
                # Process results
                for future in as_completed(futures):
                    tile_path, success = future.result()
                    if success:
                        zoom_tiles += 1
                        if zoom_tiles % 100 == 0:
                            logger.info(f"Generated {zoom_tiles} tiles for zoom {zoom}")
            
            logger.info(f"Zoom {zoom}: Generated {zoom_tiles} tiles")
            total_tiles += zoom_tiles
        
        return total_tiles
    
    def generate_tiles(self, min_zoom=8, max_zoom=16, analyze_only=False, 
                      use_cma=False, generate_both=False):
        """Generate PNG tiles for Chennai Masterplan"""
        # Find GeoTIFF files
        geotiff_files = list(self.data_dir.glob("*.tif"))
        if not geotiff_files:
            logger.error(f"No GeoTIFF files found in {self.data_dir}")
            return 0
        
        logger.info(f"Found {len(geotiff_files)} TIFF files: {[f.name for f in geotiff_files]}")
        
        # Identify specific files
        chennai_city_file = None
        cma_file = None
        
        for tiff_file in geotiff_files:
            if "ChennaiCityProposedLanduse2026_clipped" in tiff_file.name:
                chennai_city_file = tiff_file
                logger.info(f"Found Chennai City file: {tiff_file.name}")
            elif "CMA_ProposedLanduse2026_clipped" in tiff_file.name:
                cma_file = tiff_file
                logger.info(f"Found CMA file: {tiff_file.name}")
        
        files_to_process = []
        
        if generate_both:
            # Generate TWO SEPARATE tile sets - one for each file
            logger.info("Mode: Generate separate tile sets for Chennai City and CMA")
            if chennai_city_file:
                files_to_process.append(("chennai_city", chennai_city_file, False))
            else:
                logger.warning("Chennai City file not found!")
            
            if cma_file:
                files_to_process.append(("cma", cma_file, True))
            else:
                logger.warning("CMA file not found!")
                
            if not files_to_process:
                logger.error("No valid TIFF files found for processing")
                return 0
                
        elif not use_cma and chennai_city_file and cma_file:
            # Default: combine both files into single tile set
            logger.info("Mode: Combining both TIFF files into single tile set")
            files_to_process = [("combined", [chennai_city_file, cma_file], False)]
        elif use_cma and cma_file:
            # Use only CMA file
            logger.info("Mode: Using only CMA file")
            files_to_process = [("cma", cma_file, True)]
        elif chennai_city_file:
            # Use only Chennai City file
            logger.info("Mode: Using only Chennai City file")
            files_to_process = [("chennai_city", chennai_city_file, False)]
        else:
            # Fallback to first available file
            logger.info("Mode: Using first available file")
            files_to_process = [("default", geotiff_files[0], False)]
        
        if analyze_only:
            for name, file_or_files, _ in files_to_process:
                if isinstance(file_or_files, list):
                    for f in file_or_files:
                        self.analyze_geotiff(f)
                else:
                    self.analyze_geotiff(file_or_files)
            return 0
        
        total_tiles = 0
        
        # Process each file/file-set
        for area_name, file_or_files, is_cma in files_to_process:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing tile set: {area_name}")
            logger.info(f"{'='*60}")
            
            # Set output directory for this tile set
            if generate_both:
                # Create separate directories for each tile set
                current_output_dir = self.output_dir / area_name
            else:
                current_output_dir = self.output_dir
            
            current_output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Output directory: {current_output_dir}")
            
            # Load and prepare data
            if isinstance(file_or_files, list):
                # Combine multiple files
                logger.info(f"Combining {len(file_or_files)} files")
                result = self.combine_geotiffs(file_or_files)
                if result is None:
                    logger.error(f"Failed to combine files for {area_name}")
                    continue
                data_r, data_g, data_b, data_a, bounds, transform = result
            else:
                # Single file
                logger.info(f"Loading single file: {file_or_files.name}")
                data_r, data_g, data_b, data_a, bounds, transform = \
                    self.load_and_reproject_geotiff(file_or_files)
            
            logger.info(f"Data shape: R={data_r.shape}, Bounds: {bounds}")
            
            # Generate tiles in parallel for this tile set
            area_tiles = self.generate_tiles_parallel(
                data_r, data_g, data_b, data_a, bounds, transform,
                min_zoom, max_zoom, current_output_dir
            )
            
            logger.info(f"✓ Generated {area_tiles} tiles for {area_name}")
            total_tiles += area_tiles
            
            # Create supporting files for this tile set
            self.create_supporting_files(bounds, min_zoom, max_zoom, area_name, current_output_dir)
            
            # Clear cache to free memory between tile sets
            if generate_both:
                self.data_cache.clear()
                logger.info(f"Cleared data cache after processing {area_name}")
        
        return total_tiles
    
    def create_supporting_files(self, bounds, min_zoom, max_zoom, area_name, output_dir):
        """Create supporting files for the tile set"""
        logger.info(f"Creating supporting files for {area_name}")
        
        # TileJSON
        tilejson = {
            "tilejson": "2.2.0",
            "name": f"Chennai {area_name} Master Plan",
            "description": f"High-quality master plan tiles for Chennai {area_name}",
            "version": "2.0.0",
            "attribution": "Chennai Metropolitan Development Authority",
            "scheme": "xyz",
            "tiles": [
                f"https://d17yosovmfjm4.cloudfront.net/{self.s3_prefix}/{{z}}/{{x}}/{{y}}.png"
            ],
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "bounds": [bounds['west'], bounds['south'], bounds['east'], bounds['north']],
            "center": [
                (bounds['west'] + bounds['east']) / 2,
                (bounds['south'] + bounds['north']) / 2,
                10
            ]
        }
        
        with open(output_dir / "tilejson.json", "w") as f:
            json.dump(tilejson, f, indent=2)
        
        logger.info("Created tilejson.json")
    
    def upload_to_s3_parallel(self, delete_existing=True, upload_both=False):
        """Upload tiles to S3 with parallel uploads"""
        logger.info(f"Starting S3 upload to s3://{self.s3_bucket}/{self.s3_prefix}")
        
        if delete_existing:
            self.delete_s3_files()
        
        # Determine directories to upload
        directories = []
        if upload_both:
            # Upload both chennai_city and cma directories
            for subdir in ['chennai_city', 'cma']:
                path = self.output_dir / subdir
                if path.exists():
                    directories.append((subdir, path))
                    logger.info(f"Found {subdir} directory for upload")
                else:
                    logger.warning(f"Directory {subdir} not found, skipping")
        else:
            # Check if we have separate directories or a single directory
            chennai_city_path = self.output_dir / 'chennai_city'
            cma_path = self.output_dir / 'cma'
            
            if chennai_city_path.exists() or cma_path.exists():
                # We have separate directories, upload both
                if chennai_city_path.exists():
                    directories.append(("chennai_city", chennai_city_path))
                if cma_path.exists():
                    directories.append(("cma", cma_path))
            else:
                # Single directory upload
                directories.append(("", self.output_dir))
        
        if not directories:
            logger.error("No directories found to upload")
            return False
        
        total_uploaded = 0
        
        for subdir_name, upload_dir in directories:
            logger.info(f"\nUploading from: {upload_dir}")
            
            # Collect all files
            files_to_upload = []
            for file_path in upload_dir.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(upload_dir)
                    
                    # Construct S3 key
                    if subdir_name:
                        s3_key = f"{self.s3_prefix}/{subdir_name}/{relative_path}"
                    else:
                        s3_key = f"{self.s3_prefix}/{relative_path}"
                    
                    files_to_upload.append((str(file_path), s3_key))
            
            logger.info(f"Found {len(files_to_upload)} files to upload from {subdir_name or 'root'}")
            
            # Upload in parallel
            def upload_file(file_info):
                file_path, s3_key = file_info
                try:
                    # Determine content type
                    if file_path.endswith('.png'):
                        content_type = 'image/png'
                    elif file_path.endswith('.json'):
                        content_type = 'application/json'
                    elif file_path.endswith('.html'):
                        content_type = 'text/html'
                    else:
                        content_type = 'application/octet-stream'
                    
                    self.s3_client.upload_file(
                        file_path, self.s3_bucket, s3_key,
                        ExtraArgs={
                            'ContentType': content_type,
                            'CacheControl': 'public, max-age=31536000' if file_path.endswith('.png') else 'public, max-age=3600'
                        }
                    )
                    return True
                except Exception as e:
                    logger.error(f"Upload failed for {file_path}: {e}")
                    return False
            
            uploaded = 0
            failed = 0
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(upload_file, f) for f in files_to_upload]
                for i, future in enumerate(as_completed(futures), 1):
                    if future.result():
                        uploaded += 1
                    else:
                        failed += 1
                    
                    if i % 100 == 0:
                        logger.info(f"Progress: {i}/{len(files_to_upload)} files processed ({uploaded} success, {failed} failed)")
            
            logger.info(f"✓ Uploaded {uploaded}/{len(files_to_upload)} files from {subdir_name or 'root'}")
            if failed > 0:
                logger.warning(f"  {failed} files failed to upload")
            
            total_uploaded += uploaded
        
        logger.info(f"\nTotal uploaded: {total_uploaded} files")
        return total_uploaded > 0
    
    def delete_s3_files(self):
        """Delete existing S3 files"""
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=self.s3_prefix)
            
            objects = []
            for page in pages:
                if 'Contents' in page:
                    objects.extend([{'Key': obj['Key']} for obj in page['Contents']])
            
            if objects:
                for i in range(0, len(objects), 1000):
                    batch = objects[i:i+1000]
                    self.s3_client.delete_objects(
                        Bucket=self.s3_bucket,
                        Delete={'Objects': batch}
                    )
                logger.info(f"Deleted {len(objects)} existing files from S3")
        except Exception as e:
            logger.error(f"Error deleting S3 files: {e}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Optimized Chennai Masterplan Tile Generator')
    parser.add_argument('--analyze-only', action='store_true',
                       help='Only analyze GeoTIFF files')
    parser.add_argument('--use-cma', action='store_true',
                       help='Use CMA file instead of Chennai City')
    parser.add_argument('--generate-both', action='store_true',
                       help='Generate TWO SEPARATE tile sets - one for Chennai City and one for CMA')
    parser.add_argument('--min-zoom', type=int, default=17,
                       help='Minimum zoom level (default: 8)')
    parser.add_argument('--max-zoom', type=int, default=18,
                       help='Maximum zoom level (default: 16)')
    parser.add_argument('--workers', type=int, default=8,
                       help='Number of parallel workers (default: 8)')
    parser.add_argument('--upload', action='store_true',
                       help='Upload to S3 after generation')
    parser.add_argument('--s3-bucket', default='gis-tiles-1acre',
                       help='S3 bucket name')
    parser.add_argument('--s3-prefix', default='chennai/masterplan',
                       help='S3 prefix')
    parser.add_argument('--data-dir', default='data/chennai/chennai_master_plan',
                       help='Data directory containing TIFF files')
    parser.add_argument('--output-dir', default='chennai_masterplan_tiles',
                       help='Output directory for generated tiles')
    
    args = parser.parse_args()
    
    # Log configuration
    logger.info("="*70)
    logger.info("Chennai Masterplan Tile Generator - Optimized Version")
    logger.info("="*70)
    logger.info(f"Configuration:")
    for key, value in vars(args).items():
        logger.info(f"  {key}: {value}")
    logger.info("="*70)
    
    # Initialize generator
    generator = ChennaiMasterplanTileGenerator(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        s3_bucket=args.s3_bucket,
        s3_prefix=args.s3_prefix,
        max_workers=args.workers
    )
    
    # Generate tiles
    start_time = time.time()
    total = generator.generate_tiles(
        min_zoom=args.min_zoom,
        max_zoom=args.max_zoom,
        analyze_only=args.analyze_only,
        use_cma=args.use_cma,
        generate_both=args.generate_both
    )
    
    elapsed_time = time.time() - start_time
    
    if not args.analyze_only:
        if total > 0:
            logger.info("="*70)
            logger.info(f"✓ Successfully generated {total} tiles in {elapsed_time:.1f} seconds")
            logger.info(f"  Average: {total/elapsed_time:.1f} tiles/second")
            logger.info("="*70)
            
            # Upload to S3 if requested
            if args.upload:
                logger.info("\nStarting S3 upload...")
                upload_start = time.time()
                
                # Pass upload_both flag based on generate_both
                if generator.upload_to_s3_parallel(upload_both=args.generate_both):
                    upload_time = time.time() - upload_start
                    logger.info("="*70)
                    logger.info(f"✓ S3 upload completed in {upload_time:.1f} seconds")
                    logger.info("="*70)
                else:
                    logger.error("✗ S3 upload failed")
        else:
            logger.warning("No tiles were generated")
    
    logger.info("\n✓ Process completed!")

if __name__ == "__main__":
    import time
    main()