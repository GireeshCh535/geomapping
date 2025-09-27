#!/usr/bin/env python3
"""
High-zoom optimized tile generator for Hosur Masterplan GeoTIFF
Handles zoom levels 16-20+ efficiently with smart caching and edge case handling
"""

import os
import sys
import numpy as np
from pathlib import Path
import mercantile
from PIL import Image, ImageFilter, ImageEnhance
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.windows import Window, from_bounds as window_from_bounds
from rasterio.transform import from_bounds
import logging
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from tqdm import tqdm
import warnings
import pickle
import hashlib
from functools import lru_cache
import gc

# Try to import psutil, but make it optional
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logging.warning("psutil not installed, using default memory settings")

# Suppress warnings
warnings.filterwarnings('ignore')
os.environ['CPL_LOG'] = '/dev/null'
os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'TRUE'
os.environ['GDAL_PAM_ENABLED'] = 'NO'
os.environ['GDAL_CACHEMAX'] = '512'  # MB

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HighZoomTileGenerator:
    """
    Optimized for generating high zoom level tiles (16-20+) efficiently
    """
    
    def __init__(self, data_dir: str = "data/tamil_nadu/hosur/hosur_master_plan",
                 output_dir: str = "hosur_masterplan_tiles",
                 num_workers: int = None,
                 cache_size: int = 1000,
                 batch_size: int = 100):
        
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # Auto-detect optimal workers based on zoom level and system
        if num_workers is None:
            if HAS_PSUTIL:
                cpu_count = psutil.cpu_count(logical=True)
            else:
                cpu_count = os.cpu_count() or 4
            # Use fewer workers for high zoom to avoid memory issues
            self.num_workers = min(cpu_count - 1, 8)
        else:
            self.num_workers = num_workers
            
        self.cache_size = cache_size
        self.batch_size = batch_size
        self.tile_cache = {}
        self.parent_tile_cache = {}
        self.error_tiles = set()
        self.src_dataset = None
        self.pyramid_levels = {}
        
        # Memory management
        if HAS_PSUTIL:
            self.max_memory_mb = psutil.virtual_memory().available // (1024 * 1024) // 2
        else:
            self.max_memory_mb = 2048  # Default 2GB
        
        logger.info(f"High-Zoom Tile Generator initialized")
        logger.info(f"Workers: {self.num_workers}, Cache size: {cache_size}, Max memory: {self.max_memory_mb}MB")
    
    def open_and_prepare_geotiff(self, geotiff_path):
        """Open GeoTIFF and prepare for high-zoom processing"""
        try:
            self.src_dataset = rasterio.open(geotiff_path)
            
            logger.info(f"Opened GeoTIFF: {geotiff_path}")
            logger.info(f"Size: {self.src_dataset.width}x{self.src_dataset.height}")
            logger.info(f"CRS: {self.src_dataset.crs}")
            logger.info(f"Bands: {self.src_dataset.count}")
            logger.info(f"Data type: {self.src_dataset.dtypes[0]}")
            
            # Calculate WGS84 bounds
            self.wgs84_bounds = transform_bounds(
                self.src_dataset.crs, 'EPSG:4326',
                *self.src_dataset.bounds
            )
            logger.info(f"WGS84 bounds: {self.wgs84_bounds}")
            
            # Build overview pyramids for faster access at different zoom levels
            self.build_overview_cache()
            
            # For high zoom levels, determine the optimal tile generation strategy
            try:
                self.determine_strategy()
            except Exception as e:
                logger.warning(f"Could not determine optimal strategy: {e}, using windowed")
                self.strategy = "windowed"
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to open GeoTIFF: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def build_overview_cache(self):
        """Build overview cache for different zoom levels"""
        logger.info("Building overview cache for multi-resolution access...")
        
        overviews = self.src_dataset.overviews(1)
        if overviews:
            logger.info(f"Found {len(overviews)} overview levels: {overviews}")
            self.has_overviews = True
        else:
            logger.info("No overviews found - will use full resolution")
            self.has_overviews = False
    
    def determine_strategy(self):
        """Determine optimal strategy based on file size and system resources"""
        # Get the data type size in bytes
        dtype = np.dtype(self.src_dataset.dtypes[0])
        bytes_per_pixel = dtype.itemsize
        
        file_size_mb = (self.src_dataset.width * self.src_dataset.height * 
                       self.src_dataset.count * bytes_per_pixel) / (1024 * 1024)
        
        if file_size_mb < self.max_memory_mb * 0.3:  # Use 30% of available memory max
            self.strategy = "memory"
            logger.info(f"Using MEMORY strategy (file size: {file_size_mb:.1f}MB)")
            self.load_to_memory()
        else:
            self.strategy = "windowed"
            logger.info(f"Using WINDOWED strategy (file size: {file_size_mb:.1f}MB)")
    
    def load_to_memory(self):
        """Load entire dataset to memory for fastest access"""
        try:
            logger.info("Loading dataset to memory...")
            self.data_array = self.src_dataset.read()
            self.src_transform = self.src_dataset.transform
            self.src_crs = self.src_dataset.crs
            logger.info(f"Loaded {self.data_array.shape} array to memory")
        except Exception as e:
            logger.warning(f"Failed to load to memory: {e}, falling back to windowed")
            self.strategy = "windowed"
    
    def calculate_optimal_window(self, tile_bounds, zoom):
        """Calculate optimal window for reading source data"""
        # Transform tile bounds to source CRS
        src_bounds = transform_bounds(
            'EPSG:4326', self.src_dataset.crs,
            tile_bounds.west, tile_bounds.south,
            tile_bounds.east, tile_bounds.north
        )
        
        # Calculate window with bounds checking
        try:
            window = window_from_bounds(
                *src_bounds,
                transform=self.src_dataset.transform
            )
            
            # Ensure window is within dataset bounds
            col_off = max(0, min(window.col_off, self.src_dataset.width - 1))
            row_off = max(0, min(window.row_off, self.src_dataset.height - 1))
            
            # Calculate width and height with bounds checking
            max_width = self.src_dataset.width - col_off
            max_height = self.src_dataset.height - row_off
            
            width = max(1, min(window.width, max_width))  # Ensure at least 1 pixel
            height = max(1, min(window.height, max_height))  # Ensure at least 1 pixel
            
            # Return valid window
            return Window(col_off, row_off, width, height)
            
        except Exception as e:
            logger.debug(f"Window calculation failed: {e}")
            return None
    
    def generate_tile_from_parent(self, zoom, x, y):
        """Generate high-zoom tile by upsampling from parent tile"""
        try:
            # Calculate parent tile coordinates
            parent_zoom = zoom - 1
            parent_x = x // 2
            parent_y = y // 2
            
            # Check if parent exists
            parent_path = self.output_dir / str(parent_zoom) / str(parent_x) / f"{parent_y}.png"
            
            if parent_path.exists():
                # Load parent tile
                parent_img = Image.open(parent_path)
                
                # Determine which quadrant this tile is in
                quadrant_x = x % 2
                quadrant_y = y % 2
                
                # Extract quadrant (128x128) and upscale to 256x256
                left = quadrant_x * 128
                top = quadrant_y * 128
                quadrant = parent_img.crop((left, top, left + 128, top + 128))
                
                # Upscale with high quality
                tile_img = quadrant.resize((256, 256), Image.Resampling.LANCZOS)
                
                # Apply sharpening for better quality
                tile_img = tile_img.filter(ImageFilter.SHARPEN)
                
                return tile_img
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to generate from parent: {e}")
            return None
    
    def generate_single_tile_highzoom(self, zoom, x, y):
        """Generate a single tile optimized for high zoom levels"""
        tile_key = f"{zoom}/{x}/{y}"
        
        try:
            tile_path = self.output_dir / str(zoom) / str(x) / f"{y}.png"
            
            # Skip if exists
            if tile_path.exists():
                return True
                
            # Skip if previously failed
            if tile_key in self.error_tiles:
                return False
            
            # Create directory
            tile_path.parent.mkdir(exist_ok=True, parents=True)
            
            # Get tile bounds
            tile_bounds = mercantile.bounds(x, y, zoom)
            
            # Check if tile is within data bounds
            if not self.tile_in_bounds(tile_bounds):
                return False
            
            # For very high zoom (18+), try parent tile upsampling first
            if zoom >= 18:
                tile_img = self.generate_tile_from_parent(zoom, x, y)
                if tile_img:
                    tile_img.save(tile_path, 'PNG', optimize=True, compress_level=6)
                    return True
            
            # Calculate optimal window for this tile
            window = self.calculate_optimal_window(tile_bounds, zoom)
            
            if window is None or window.width <= 0 or window.height <= 0:
                logger.debug(f"Invalid window for tile {tile_key}")
                return False
            
            # Generate tile based on strategy
            if self.strategy == "memory":
                success = self.generate_from_memory(tile_bounds, window, tile_path)
            else:
                success = self.generate_from_window(tile_bounds, window, tile_path)
            
            if not success:
                self.error_tiles.add(tile_key)
                
            return success
            
        except Exception as e:
            logger.debug(f"Error generating tile {tile_key}: {e}")
            self.error_tiles.add(tile_key)
            return False
    
    def generate_from_memory(self, tile_bounds, window, tile_path):
        """Generate tile from memory-loaded data"""
        try:
            # Create destination array
            tile_data = np.zeros((4, 256, 256), dtype=np.uint8)
            
            # Create transform for tile
            tile_transform = from_bounds(
                tile_bounds.west, tile_bounds.south,
                tile_bounds.east, tile_bounds.north,
                256, 256
            )
            
            # Extract window from memory array
            row_start = int(max(0, window.row_off))
            row_stop = int(min(self.data_array.shape[1], window.row_off + window.height))
            col_start = int(max(0, window.col_off))
            col_stop = int(min(self.data_array.shape[2], window.col_off + window.width))
            
            if row_stop > row_start and col_stop > col_start:
                window_data = self.data_array[:, row_start:row_stop, col_start:col_stop]
                
                # Get window transform
                window_transform = rasterio.transform.from_bounds(
                    *rasterio.transform.array_bounds(
                        row_stop - row_start,
                        col_stop - col_start,
                        self.src_dataset.window_transform(window)
                    ),
                    col_stop - col_start,
                    row_stop - row_start
                )
                
                # Reproject
                reproject(
                    source=window_data,
                    destination=tile_data,
                    src_transform=window_transform,
                    src_crs=self.src_crs,
                    dst_transform=tile_transform,
                    dst_crs='EPSG:4326',
                    resampling=Resampling.cubic
                )
                
                return self.save_tile(tile_data, tile_path)
            
            return False
            
        except Exception as e:
            logger.debug(f"Memory generation failed: {e}")
            return False
    
    def generate_from_window(self, tile_bounds, window, tile_path):
        """Generate tile using windowed reading"""
        try:
            # Create destination array
            tile_data = np.zeros((4, 256, 256), dtype=np.uint8)
            
            # Create transform for tile
            tile_transform = from_bounds(
                tile_bounds.west, tile_bounds.south,
                tile_bounds.east, tile_bounds.north,
                256, 256
            )
            
            # Read window from dataset
            window_data = self.src_dataset.read(window=window)
            window_transform = self.src_dataset.window_transform(window)
            
            # Reproject with high quality
            reproject(
                source=window_data,
                destination=tile_data,
                src_transform=window_transform,
                src_crs=self.src_dataset.crs,
                dst_transform=tile_transform,
                dst_crs='EPSG:4326',
                resampling=Resampling.cubic
            )
            
            return self.save_tile(tile_data, tile_path)
            
        except Exception as e:
            logger.debug(f"Window generation failed: {e}")
            return False
    
    def save_tile(self, tile_data, tile_path):
        """Save tile with optimization"""
        try:
            # Convert to image
            img_array = np.transpose(tile_data, (1, 2, 0))
            
            # Check for content
            if not np.any(img_array[:, :, 3] > 0):
                return False
            
            # Create PIL image
            img = Image.fromarray(img_array, mode='RGBA')
            
            # Enhance quality
            img = img.filter(ImageFilter.SHARPEN)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.05)
            
            # Save optimized
            img.save(tile_path, 'PNG', optimize=True, compress_level=6)
            return True
            
        except Exception as e:
            logger.debug(f"Failed to save tile: {e}")
            return False
    
    def tile_in_bounds(self, tile_bounds):
        """Check if tile intersects data bounds"""
        return not (
            tile_bounds.east < self.wgs84_bounds[0] or
            tile_bounds.west > self.wgs84_bounds[2] or
            tile_bounds.south > self.wgs84_bounds[3] or
            tile_bounds.north < self.wgs84_bounds[1]
        )
    
    def generate_zoom_level_optimized(self, zoom):
        """Generate all tiles for a zoom level with optimization"""
        # Calculate tile range
        min_tile = mercantile.tile(self.wgs84_bounds[0], self.wgs84_bounds[1], zoom)
        max_tile = mercantile.tile(self.wgs84_bounds[2], self.wgs84_bounds[3], zoom)
        
        # Generate tile list
        tiles = []
        for x in range(min_tile.x, max_tile.x + 1):
            for y in range(max_tile.y, min_tile.y + 1):
                tiles.append((zoom, x, y))
        
        logger.info(f"Generating {len(tiles)} tiles for zoom {zoom}")
        
        # Adjust workers based on zoom level
        if zoom >= 18:
            workers = min(4, self.num_workers)  # Use fewer workers for high zoom
        else:
            workers = self.num_workers
        
        successful = 0
        failed = 0
        
        # Process in batches to manage memory
        batch_size = self.batch_size if zoom < 18 else 50
        
        for i in range(0, len(tiles), batch_size):
            batch = tiles[i:i + batch_size]
            
            # Clear caches periodically
            if i % (batch_size * 10) == 0:
                gc.collect()
                
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(self.generate_single_tile_highzoom, z, x, y): (z, x, y)
                    for z, x, y in batch
                }
                
                with tqdm(total=len(futures), desc=f"Zoom {zoom} batch {i//batch_size + 1}") as pbar:
                    for future in as_completed(futures):
                        try:
                            if future.result():
                                successful += 1
                            else:
                                failed += 1
                        except Exception as e:
                            failed += 1
                            z, x, y = futures[future]
                            logger.debug(f"Failed {z}/{x}/{y}: {e}")
                        pbar.update(1)
        
        logger.info(f"Zoom {zoom}: {successful} successful, {failed} failed/skipped")
        return successful
    
    def generate_tiles_highzoom(self, min_zoom=8, max_zoom=18):
        """Main tile generation function optimized for high zoom levels"""
        # Find GeoTIFF
        geotiff_files = list(self.data_dir.glob("*.tif"))
        if not geotiff_files:
            logger.error(f"No GeoTIFF found in {self.data_dir}")
            return 0
        
        geotiff_path = geotiff_files[0]
        logger.info(f"Processing: {geotiff_path}")
        
        # Open and prepare
        if not self.open_and_prepare_geotiff(geotiff_path):
            return 0
        
        total_generated = 0
        
        try:
            # Generate tiles for each zoom level
            for zoom in range(min_zoom, max_zoom + 1):
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing zoom level {zoom}")
                logger.info(f"{'='*60}")
                
                # Adjust strategy for very high zoom
                if zoom >= 18 and self.strategy == "memory":
                    logger.info("Switching to windowed strategy for high zoom")
                    self.strategy = "windowed"
                    # Free memory
                    if hasattr(self, 'data_array'):
                        del self.data_array
                        gc.collect()
                
                generated = self.generate_zoom_level_optimized(zoom)
                total_generated += generated
                
                logger.info(f"Total tiles so far: {total_generated}")
                
        finally:
            if self.src_dataset:
                self.src_dataset.close()
        
        # Save error report
        if self.error_tiles:
            with open(self.output_dir / "failed_tiles.txt", "w") as f:
                for tile in sorted(self.error_tiles):
                    f.write(f"{tile}\n")
            logger.info(f"Failed tiles saved to failed_tiles.txt ({len(self.error_tiles)} tiles)")
        
        return total_generated

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='High-zoom optimized tile generator')
    parser.add_argument('--data-dir', default='data/tamil_nadu/hosur/hosur_master_plan')
    parser.add_argument('--output-dir', default='hosur_masterplan_tiles')
    parser.add_argument('--min-zoom', type=int, default=8)
    parser.add_argument('--max-zoom', type=int, default=18)
    parser.add_argument('--workers', type=int, default=None)
    parser.add_argument('--batch-size', type=int, default=100)
    parser.add_argument('--cache-size', type=int, default=1000)
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("HIGH-ZOOM OPTIMIZED TILE GENERATOR")
    logger.info("="*60)
    logger.info(f"Configuration:")
    logger.info(f"  Zoom range: {args.min_zoom}-{args.max_zoom}")
    logger.info(f"  Output: {args.output_dir}")
    logger.info("="*60)
    
    generator = HighZoomTileGenerator(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        num_workers=args.workers,
        batch_size=args.batch_size,
        cache_size=args.cache_size
    )
    
    total = generator.generate_tiles_highzoom(
        min_zoom=args.min_zoom,
        max_zoom=args.max_zoom
    )
    
    logger.info("="*60)
    logger.info(f"COMPLETE: Generated {total} tiles")
    logger.info("="*60)

if __name__ == "__main__":
    main()