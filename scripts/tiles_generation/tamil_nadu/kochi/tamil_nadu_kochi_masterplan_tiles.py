#!/usr/bin/env python3
"""
High-performance optimized tile generator for Kochi Masterplan GeoTIFF
Handles large files (1.7+ billion pixels) efficiently with smart windowing and parallel processing
FIXED VERSION - Addresses common tile generation issues
"""

import os
import sys
import numpy as np
from pathlib import Path
import mercantile
from PIL import Image, ImageFilter, ImageEnhance
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds, calculate_default_transform
from rasterio.windows import Window, from_bounds as window_from_bounds
from rasterio.transform import from_bounds
from rasterio import Affine
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import warnings
import gc
import json

# Try to import psutil for better memory management
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')
warnings.filterwarnings('ignore', category=rasterio.errors.NotGeoreferencedWarning)
warnings.filterwarnings('ignore', message='Dataset has no geotransform')

# Suppress GDAL/TIFF warnings about corruption
os.environ['CPL_LOG'] = '/dev/null'
os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'TRUE'
os.environ['GDAL_PAM_ENABLED'] = 'NO'
os.environ['GDAL_CACHEMAX'] = '1024'
os.environ['CPL_DEBUG'] = 'OFF'
os.environ['GDAL_TIFF_INTERNAL_MASK_TO_8BIT'] = 'FALSE'

# Configure logging to filter GDAL messages
class GDALFilter(logging.Filter):
    """Filter out GDAL error messages from logs"""
    def filter(self, record):
        gdal_messages = ['CPLE_AppDefined', 'LZWDecode', 'TIFFReadEncodedTile', 'IReadBlock failed']
        return not any(msg in record.getMessage() for msg in gdal_messages)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.addFilter(GDALFilter())

class OptimizedKochiTileGenerator:
    """
    High-performance tile generator for Kochi Masterplan optimized for large WGS84 GeoTIFFs
    """
    
    def __init__(self, data_dir: str = "data/tamil_nadu/kochi/kochi_master_plan",
                 output_dir: str = "kochi_masterplan_tiles",
                 num_workers: int = None,
                 cache_size: int = 1000,
                 batch_size: int = 100):
        
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # Auto-detect optimal workers
        if num_workers is None:
            if HAS_PSUTIL:
                cpu_count = psutil.cpu_count(logical=True)
            else:
                cpu_count = os.cpu_count() or 4
            self.num_workers = min(cpu_count - 1, 8)
        else:
            self.num_workers = num_workers
        
        self.cache_size = cache_size
        self.batch_size = batch_size
        self.error_tiles = set()
        self.src_dataset = None
        
        # Memory management
        if HAS_PSUTIL:
            self.max_memory_mb = psutil.virtual_memory().available // (1024 * 1024) // 2
        else:
            self.max_memory_mb = 2048  # Default 2GB
        
        # Known Kochi bounds from analysis
        self.kochi_bounds = (76.2371320741556, 9.892724597896889, 76.33993364183216, 10.04961770396189)
        
        logger.info(f"Optimized Kochi Tile Generator initialized")
        logger.info(f"Workers: {self.num_workers}, Cache size: {cache_size}, Max memory: {self.max_memory_mb}MB")
    
    def repair_corrupted_tiff(self, input_path, compression='DEFLATE'):
        """
        Repair a corrupted TIFF by reading what's possible and creating a new clean file
        """
        input_path = Path(input_path)
        output_path = input_path.parent / f"{input_path.stem}_repaired.tif"
        
        logger.info(f"Attempting to repair corrupted TIFF: {input_path}")
        
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with rasterio.open(input_path) as src:
                    logger.info(f"Reading source: {src.width}x{src.height}, {src.count} bands")
                    
                    # Create output profile with safe settings
                    profile = src.profile.copy()
                    profile.update(
                        compress=compression,
                        tiled=True,
                        blockxsize=256,
                        blockysize=256,
                        BIGTIFF='YES',
                        NUM_THREADS='ALL_CPUS'
                    )
                    
                    # Remove problematic options
                    if 'INTERLEAVE' in profile:
                        del profile['INTERLEAVE']
                    
                    # Read data in chunks to handle corruption
                    height, width = src.height, src.width
                    chunk_size = 512  # Smaller chunks for better error handling
                    
                    with rasterio.open(output_path, 'w', **profile) as dst:
                        for band_idx in range(1, src.count + 1):
                            logger.info(f"Processing band {band_idx}/{src.count}")
                            band_data = np.zeros((height, width), dtype=src.dtypes[0])
                            corrupted_count = 0
                            
                            # Process in chunks
                            for row in range(0, height, chunk_size):
                                for col in range(0, width, chunk_size):
                                    row_end = min(row + chunk_size, height)
                                    col_end = min(col + chunk_size, width)
                                    
                                    try:
                                        window = Window(col, row, col_end - col, row_end - row)
                                        chunk = src.read(band_idx, window=window)
                                        band_data[row:row_end, col:col_end] = chunk
                                    except:
                                        corrupted_count += 1
                                        # Fill corrupted areas
                                        if band_idx == 4:  # Alpha
                                            band_data[row:row_end, col:col_end] = 255
                                        else:
                                            band_data[row:row_end, col:col_end] = 128
                            
                            if corrupted_count > 0:
                                logger.warning(f"Band {band_idx}: {corrupted_count} corrupted chunks repaired")
                            
                            dst.write(band_data, band_idx)
                        
                        # Build overviews
                        logger.info("Building overviews for repaired file...")
                        dst.build_overviews([2, 4, 8, 16, 32], Resampling.average)
            
            logger.info(f"Repair complete! Saved to: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to repair: {e}")
            return None
    
    def open_and_prepare_geotiff(self, geotiff_path, auto_repair=True):
        """Open GeoTIFF and prepare for processing with optional auto-repair"""
        try:
            # First, try to open and test the file
            test_successful = False
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    test_src = rasterio.open(geotiff_path)
                    # Try reading a small test window
                    test_window = Window(0, 0, min(100, test_src.width), min(100, test_src.height))
                    test_data = test_src.read(window=test_window)
                    test_src.close()
                    test_successful = True
                except Exception as e:
                    if 'LZWDecode' in str(e) or 'TIFFReadEncodedTile' in str(e):
                        logger.warning(f"LZW corruption detected: {e}")
                        if auto_repair:
                            logger.info("Attempting to repair corrupted TIFF...")
                            repaired_path = self.repair_corrupted_tiff(geotiff_path)
                            if repaired_path and repaired_path.exists():
                                geotiff_path = repaired_path
                                logger.info(f"Using repaired file: {geotiff_path}")
            
            # Open the dataset (original or repaired)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.src_dataset = rasterio.open(geotiff_path)
            
            logger.info(f"Opened GeoTIFF: {geotiff_path}")
            logger.info(f"Size: {self.src_dataset.width}x{self.src_dataset.height}")
            logger.info(f"CRS: {self.src_dataset.crs}")
            logger.info(f"Bands: {self.src_dataset.count}")
            logger.info(f"Data type: {self.src_dataset.dtypes[0]}")
            logger.info(f"Bounds: {self.src_dataset.bounds}")
            
            # Check if CRS is valid
            if self.src_dataset.crs is None:
                logger.warning("No CRS found, assuming EPSG:4326")
                # Use known bounds for Kochi
                self.wgs84_bounds = self.kochi_bounds
            elif str(self.src_dataset.crs) == 'EPSG:4326':
                self.wgs84_bounds = self.src_dataset.bounds
                logger.info("Data is already in WGS84 - no reprojection needed")
            else:
                # Calculate WGS84 bounds
                self.wgs84_bounds = transform_bounds(
                    self.src_dataset.crs, 'EPSG:4326',
                    *self.src_dataset.bounds
                )
                logger.info(f"WGS84 bounds: {self.wgs84_bounds}")
            
            # Check for overviews
            overviews = self.src_dataset.overviews(1)
            if overviews:
                logger.info(f"Found {len(overviews)} overview levels: {overviews}")
            
            # Determine optimal strategy
            self.determine_strategy()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to open GeoTIFF: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def determine_strategy(self):
        """Determine optimal tile generation strategy"""
        try:
            # Calculate file size
            dtype = np.dtype(self.src_dataset.dtypes[0])
            bytes_per_pixel = dtype.itemsize
            file_size_mb = (self.src_dataset.width * self.src_dataset.height * 
                          self.src_dataset.count * bytes_per_pixel) / (1024 * 1024)
            
            logger.info(f"Estimated file size in memory: {file_size_mb:.1f}MB")
            
            # For Kochi's large file (1.7B pixels), always use windowed strategy
            if file_size_mb > 1000:  # Over 1GB
                self.strategy = "windowed_large"
                logger.info(f"Using WINDOWED_LARGE strategy for huge file")
            elif file_size_mb < self.max_memory_mb * 0.3:
                self.strategy = "memory"
                logger.info(f"Using MEMORY strategy")
                self.load_to_memory()
            else:
                self.strategy = "windowed"
                logger.info(f"Using WINDOWED strategy")
                
        except Exception as e:
            logger.warning(f"Could not determine optimal strategy: {e}, using windowed")
            self.strategy = "windowed"
    
    def load_to_memory(self):
        """Load entire dataset to memory for fastest access (only for small files)"""
        try:
            logger.info("Loading dataset to memory for fastest processing...")
            self.data_array = self.src_dataset.read()
            self.src_transform = self.src_dataset.transform
            self.src_crs = self.src_dataset.crs
            logger.info(f"Loaded {self.data_array.shape} array to memory")
        except Exception as e:
            logger.warning(f"Failed to load to memory: {e}, falling back to windowed")
            self.strategy = "windowed"
            self.data_array = None
    
    def generate_single_tile_optimized(self, zoom, x, y):
        """Generate a single tile with optimizations and error handling"""
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
            
            # Check if tile is within bounds
            if not self.tile_in_bounds(tile_bounds):
                return False
            
            # Pass zoom level to generation functions
            # Generate tile based on strategy
            if self.strategy == "memory" and hasattr(self, 'data_array') and self.data_array is not None:
                success = self.generate_from_memory_with_zoom(tile_bounds, tile_path, zoom)
            elif self.strategy == "windowed_large":
                success = self.generate_from_window_optimized(tile_bounds, tile_path)
            else:
                success = self.generate_from_window_with_zoom(tile_bounds, tile_path, zoom)
            
            if not success:
                self.error_tiles.add(tile_key)
            
            return success
            
        except Exception as e:
            logger.debug(f"Error generating tile {tile_key}: {e}")
            self.error_tiles.add(tile_key)
            return False
    
    def generate_from_memory_with_zoom(self, tile_bounds, tile_path, zoom):
        """Generate tile from memory-loaded data with zoom-appropriate detail"""
        try:
            # Create destination array
            tile_data = np.zeros((4, 256, 256), dtype=np.uint8)
            
            # Create transform for tile
            tile_transform = from_bounds(
                tile_bounds.west, tile_bounds.south,
                tile_bounds.east, tile_bounds.north,
                256, 256
            )
            
            # Handle bands properly
            if self.data_array.shape[0] == 3:
                # RGB only - add alpha channel
                source_data = np.concatenate([
                    self.data_array,
                    np.full((1, self.data_array.shape[1], self.data_array.shape[2]), 255, dtype=np.uint8)
                ], axis=0)
            elif self.data_array.shape[0] == 1:
                # Single band - replicate to RGB and add alpha
                source_data = np.concatenate([
                    np.repeat(self.data_array, 3, axis=0),
                    np.full((1, self.data_array.shape[1], self.data_array.shape[2]), 255, dtype=np.uint8)
                ], axis=0)
            else:
                source_data = self.data_array
            
            # Use appropriate resampling based on zoom
            if zoom <= 10:
                resampling = Resampling.average  # Better for downsampling
            elif zoom <= 14:
                resampling = Resampling.bilinear
            else:
                resampling = Resampling.cubic  # Better for upsampling at high zooms
            
            # Reproject
            reproject(
                source=source_data[:4],  # Take only first 4 bands
                destination=tile_data,
                src_transform=self.src_transform,
                src_crs=self.src_crs if self.src_crs else 'EPSG:4326',
                dst_transform=tile_transform,
                dst_crs='EPSG:4326',
                resampling=resampling
            )
            
            return self.save_tile(tile_data, tile_path)
            
        except Exception as e:
            logger.debug(f"Memory generation failed: {e}")
            return False
    
    def generate_from_window_with_zoom(self, tile_bounds, tile_path, zoom):
        """Generate tile using standard windowed reading with zoom-appropriate detail"""
        try:
            # Create destination array
            tile_data = np.zeros((4, 256, 256), dtype=np.uint8)
            
            # Create transform for tile
            tile_transform = from_bounds(
                tile_bounds.west, tile_bounds.south,
                tile_bounds.east, tile_bounds.north,
                256, 256
            )
            
            # Determine source CRS
            src_crs = self.src_dataset.crs if self.src_dataset.crs else 'EPSG:4326'
            
            # Select appropriate resampling based on zoom
            if zoom <= 10:
                resampling = Resampling.average
            elif zoom <= 14:
                resampling = Resampling.bilinear  
            else:
                resampling = Resampling.cubic
            
            # Read and reproject the full dataset bands
            for band_idx in range(1, min(5, self.src_dataset.count + 1)):
                try:
                    if band_idx <= self.src_dataset.count:
                        # Read actual band
                        reproject(
                            source=rasterio.band(self.src_dataset, band_idx),
                            destination=tile_data[band_idx - 1],
                            src_transform=self.src_dataset.transform,
                            src_crs=src_crs,
                            dst_transform=tile_transform,
                            dst_crs='EPSG:4326',
                            resampling=resampling
                        )
                    elif band_idx == 4:
                        # Add alpha channel if missing
                        tile_data[3] = 255
                except Exception as e:
                    logger.debug(f"Failed to reproject band {band_idx}: {e}")
                    if band_idx == 4:
                        tile_data[3] = 255
            
            # Handle single band or RGB data
            if self.src_dataset.count == 1:
                # Replicate single band to RGB
                tile_data[1] = tile_data[0]
                tile_data[2] = tile_data[0]
                tile_data[3] = 255
            elif self.src_dataset.count == 3:
                # Add alpha channel
                tile_data[3] = 255
            
            return self.save_tile(tile_data, tile_path)
            
        except Exception as e:
            logger.debug(f"Window generation failed: {e}")
            return False
    
    
    def generate_from_memory(self, tile_bounds, tile_path):
        """Generate tile from memory-loaded data - delegates to zoom-aware version"""
        # Extract zoom from tile path for backward compatibility
        zoom = int(tile_path.parent.parent.name)
        return self.generate_from_memory_with_zoom(tile_bounds, tile_path, zoom)
    
    def generate_from_window(self, tile_bounds, tile_path):
        """Generate tile using standard windowed reading - delegates to zoom-aware version"""
        # Extract zoom from tile path for backward compatibility  
        zoom = int(tile_path.parent.parent.name)
        return self.generate_from_window_with_zoom(tile_bounds, tile_path, zoom)
    
    def generate_from_window_optimized(self, tile_bounds, tile_path):
        """Generate tile using optimized windowed reading for large files"""
        try:
            # Get the zoom level from the tile path
            zoom = int(tile_path.parent.parent.name)
            
            # Determine appropriate overview level for this zoom
            overview_level = self.get_best_overview_level(zoom)
            
            # Calculate pixel window that corresponds to tile bounds
            if self.src_dataset.transform and self.src_dataset.transform != Affine.identity():
                # Use transform to calculate window
                window = window_from_bounds(
                    tile_bounds.west, tile_bounds.south,
                    tile_bounds.east, tile_bounds.north,
                    transform=self.src_dataset.transform
                )
                
                # Clamp to dataset bounds
                col_off = max(0, min(int(window.col_off), self.src_dataset.width - 1))
                row_off = max(0, min(int(window.row_off), self.src_dataset.height - 1))
                width = max(1, min(int(window.width), self.src_dataset.width - col_off))
                height = max(1, min(int(window.height), self.src_dataset.height - row_off))
            else:
                # Fallback: calculate based on resolution
                res_x = (self.src_dataset.bounds.right - self.src_dataset.bounds.left) / self.src_dataset.width
                res_y = (self.src_dataset.bounds.top - self.src_dataset.bounds.bottom) / self.src_dataset.height
                
                col_off = int((tile_bounds.west - self.src_dataset.bounds.left) / res_x)
                row_off = int((self.src_dataset.bounds.top - tile_bounds.north) / res_y)
                width = int((tile_bounds.east - tile_bounds.west) / res_x)
                height = int((tile_bounds.north - tile_bounds.south) / res_y)
                
                col_off = max(0, min(col_off, self.src_dataset.width - 1))
                row_off = max(0, min(row_off, self.src_dataset.height - 1))
                width = max(1, min(width, self.src_dataset.width - col_off))
                height = max(1, min(height, self.src_dataset.height - row_off))
            
            # Ensure minimum window size for low zoom levels
            if zoom <= 10:
                width = max(width, 4)
                height = max(height, 4)
            
            # Skip if window is too small
            if width < 1 or height < 1:
                return False
            
            window = Window(col_off, row_off, width, height)
            
            # Read the window data with appropriate detail level
            try:
                # Use overview if available for lower zoom levels
                if overview_level and overview_level > 0 and self.src_dataset.overviews(1):
                    window_data = self.src_dataset.read(window=window, out_shape=(self.src_dataset.count, 256, 256), 
                                                  resampling=Resampling.bilinear)
                else:
                    window_data = self.src_dataset.read(window=window)
            except Exception as e:
                # Try to read bands individually if full read fails (corruption handling)
                logger.debug(f"Failed to read window, trying band-by-band: {e}")
                try:
                    window_data = []
                    for band_idx in range(1, min(5, self.src_dataset.count + 1)):
                        try:
                            band_data = self.src_dataset.read(band_idx, window=window)
                            window_data.append(band_data)
                        except:
                            # Create placeholder data for corrupted band
                            if band_idx == 4:  # Alpha channel
                                placeholder = np.full((int(window.height), int(window.width)), 255, dtype=np.uint8)
                            else:
                                # Use gray for RGB channels
                                placeholder = np.full((int(window.height), int(window.width)), 128, dtype=np.uint8)
                            window_data.append(placeholder)
                            logger.debug(f"Band {band_idx} corrupted, using placeholder")
                    
                    window_data = np.array(window_data)
                    
                    # Add alpha if missing
                    if window_data.shape[0] == 3:
                        alpha = np.full((1, window_data.shape[1], window_data.shape[2]), 255, dtype=np.uint8)
                        window_data = np.concatenate([window_data, alpha], axis=0)
                        
                except Exception as e2:
                    logger.debug(f"Band-by-band read also failed: {e2}")
                    return False
            
            # For low zoom levels, ensure we're reading enough data
            if zoom <= 12 and (window_data.shape[1] < 64 or window_data.shape[2] < 64):
                # Try to read a larger area for better quality at low zooms
                try:
                    expand_factor = 2
                    expanded_window = Window(
                        max(0, col_off - width * expand_factor),
                        max(0, row_off - height * expand_factor),
                        min(width * (expand_factor * 2 + 1), self.src_dataset.width - max(0, col_off - width * expand_factor)),
                        min(height * (expand_factor * 2 + 1), self.src_dataset.height - max(0, row_off - height * expand_factor))
                    )
                    window_data = self.src_dataset.read(window=expanded_window)
                except:
                    pass  # Use original window data if expansion fails
            
            # Handle different band counts
            if window_data.shape[0] == 3:
                # RGB - add alpha channel
                alpha = np.full((1, window_data.shape[1], window_data.shape[2]), 255, dtype=np.uint8)
                window_data = np.concatenate([window_data, alpha], axis=0)
            elif window_data.shape[0] == 1:
                # Single band - replicate to RGBA
                rgb = np.repeat(window_data, 3, axis=0)
                alpha = np.full((1, window_data.shape[1], window_data.shape[2]), 255, dtype=np.uint8)
                window_data = np.concatenate([rgb, alpha], axis=0)
            elif window_data.shape[0] > 4:
                # Too many bands - take first 4
                window_data = window_data[:4]
            
            # Convert to PIL Image for resizing
            img_array = np.transpose(window_data, (1, 2, 0)).astype(np.uint8)
            
            # Check if there's any content
            if not np.any(img_array[:, :, :3] > 0):
                return False
            
            img = Image.fromarray(img_array)
            
            # Ensure RGBA mode
            if img.mode != 'RGBA':
                if img.mode == 'RGB':
                    img = img.convert('RGBA')
                elif img.mode in ['L', 'P']:
                    img = img.convert('RGBA')
            
            # Resize to 256x256
            img = img.resize((256, 256), Image.Resampling.LANCZOS)
            
            # Apply enhancements
            try:
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.1)
                enhancer = ImageEnhance.Sharpness(img)
                img = enhancer.enhance(1.2)
            except:
                pass  # Skip enhancement if it fails
            
            # Save
            img.save(tile_path, 'PNG', optimize=True, compress_level=6)
            return True
            
        except Exception as e:
            logger.debug(f"Optimized window generation failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    
    def save_tile(self, tile_data, tile_path):
        """Save tile with optimization and enhancement"""
        try:
            # Convert to image
            img_array = np.transpose(tile_data, (1, 2, 0))
            
            # Check for content (ignore alpha channel for content check)
            if not np.any(img_array[:, :, :3] > 0):
                return False
            
            # Ensure uint8 and create PIL image
            img = Image.fromarray(img_array.astype(np.uint8))
            
            # Verify it's RGBA
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Apply enhancements
            try:
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.1)
                enhancer = ImageEnhance.Sharpness(img) 
                img = enhancer.enhance(1.2)
            except:
                pass  # Skip enhancement if it fails
            
            # Save with optimization
            img.save(tile_path, 'PNG', optimize=True, compress_level=6)
            return True
            
        except Exception as e:
            logger.debug(f"Failed to save tile: {e}")
            return False
    
    def get_best_overview_level(self, zoom):
        """Determine the best overview level for a given zoom"""
        if not self.src_dataset.overviews(1):
            return None
        
        overviews = self.src_dataset.overviews(1)
        
        # Map zoom levels to appropriate overviews
        # Lower zooms should use more downsampled overviews
        if zoom <= 8:
            # Use most downsampled overview
            return len(overviews)
        elif zoom <= 10:
            # Use mid-level overview
            return max(1, len(overviews) - 1)
        elif zoom <= 12:
            # Use less downsampled overview
            return max(1, len(overviews) - 2)
        elif zoom <= 14:
            # Use least downsampled overview
            return 1 if overviews else None
        else:
            # Use full resolution for high zooms
            return None
    
    def calculate_window_for_zoom(self, tile_bounds, zoom):
        """Calculate appropriate window size based on zoom level"""
        # At lower zoom levels, we need to read more data and downsample
        # At higher zoom levels, we read less data at full resolution
        
        # Calculate base window from bounds
        if self.src_dataset.transform and self.src_dataset.transform != Affine.identity():
            window = window_from_bounds(
                tile_bounds.west, tile_bounds.south,
                tile_bounds.east, tile_bounds.north,
                transform=self.src_dataset.transform
            )
        else:
            # Manual calculation based on resolution
            res_x = (self.src_dataset.bounds.right - self.src_dataset.bounds.left) / self.src_dataset.width
            res_y = (self.src_dataset.bounds.top - self.src_dataset.bounds.bottom) / self.src_dataset.height
            
            col_off = (tile_bounds.west - self.src_dataset.bounds.left) / res_x
            row_off = (self.src_dataset.bounds.top - tile_bounds.north) / res_y
            width = (tile_bounds.east - tile_bounds.west) / res_x
            height = (tile_bounds.north - tile_bounds.south) / res_y
            
            window = Window(col_off, row_off, width, height)
        
        # Clamp to dataset bounds
        col_off = max(0, min(int(window.col_off), self.src_dataset.width - 1))
        row_off = max(0, min(int(window.row_off), self.src_dataset.height - 1))
        width = max(1, min(int(window.width), self.src_dataset.width - col_off))
        height = max(1, min(int(window.height), self.src_dataset.height - row_off))
        
        return Window(col_off, row_off, width, height)
    
    def tile_in_bounds(self, tile_bounds):
        """Check if tile intersects data bounds"""
        # Add small buffer to avoid edge issues
        buffer = 0.0001
        return not (
            tile_bounds.east < (self.wgs84_bounds[0] - buffer) or
            tile_bounds.west > (self.wgs84_bounds[2] + buffer) or
            tile_bounds.south > (self.wgs84_bounds[3] + buffer) or
            tile_bounds.north < (self.wgs84_bounds[1] - buffer)
        )
    
    def generate_tiles_parallel(self, min_zoom=8, max_zoom=16):
        """Generate tiles in parallel with optimal settings"""
        # Look for GeoTIFF files
        geotiff_files = [
            "Kochi_Fixed_LZW.tif",
            "Kochi_Fixed.tif", 
            "Kochi_Merged_Clipped.tif",
            "kochi_masterplan.tif"
        ]
        
        geotiff_path = None
        for filename in geotiff_files:
            test_path = self.data_dir / filename
            if test_path.exists():
                geotiff_path = test_path
                logger.info(f"Found GeoTIFF: {geotiff_path}")
                break
        
        if not geotiff_path:
            # Try to find any .tif file
            tif_files = list(self.data_dir.glob("*.tif"))
            if tif_files:
                geotiff_path = tif_files[0]
                logger.info(f"Using first found TIF: {geotiff_path}")
            else:
                logger.error(f"No GeoTIFF files found in {self.data_dir}")
                return 0
        
        # Open and prepare
        if not self.open_and_prepare_geotiff(geotiff_path):
            return 0
        
        total_generated = 0
        
        try:
            for zoom in range(min_zoom, max_zoom + 1):
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing zoom level {zoom}")
                
                # Calculate tile range based on bounds
                min_tile = mercantile.tile(self.wgs84_bounds[0], self.wgs84_bounds[3], zoom)
                max_tile = mercantile.tile(self.wgs84_bounds[2], self.wgs84_bounds[1], zoom)
                
                # Generate tile list
                tiles = []
                for x in range(min_tile.x, max_tile.x + 1):
                    for y in range(min_tile.y, max_tile.y + 1):
                        tiles.append((zoom, x, y))
                
                logger.info(f"Generating {len(tiles)} tiles for zoom {zoom}")
                
                # Adjust workers based on strategy and zoom level
                if self.strategy == "windowed_large" or zoom >= 17:
                    workers = min(4, self.num_workers)
                    batch_size = 50
                else:
                    workers = self.num_workers
                    batch_size = self.batch_size
                
                successful = 0
                failed = 0
                
                # Process in batches
                for i in range(0, len(tiles), batch_size):
                    batch = tiles[i:i + batch_size]
                    
                    # Periodic garbage collection
                    if i % (batch_size * 5) == 0:
                        gc.collect()
                    
                    with ThreadPoolExecutor(max_workers=workers) as executor:
                        futures = {
                            executor.submit(self.generate_single_tile_optimized, z, x, y): (z, x, y)
                            for z, x, y in batch
                        }
                        
                        desc = f"Zoom {zoom}"
                        if len(tiles) > batch_size:
                            desc += f" batch {i//batch_size + 1}/{(len(tiles)-1)//batch_size + 1}"
                        
                        with tqdm(total=len(futures), desc=desc) as pbar:
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
                
                total_generated += successful
                logger.info(f"Zoom {zoom}: {successful} successful, {failed} failed/skipped")
                logger.info(f"Total tiles generated so far: {total_generated}")
                
        finally:
            if self.src_dataset:
                self.src_dataset.close()
        
        # Save error report
        if self.error_tiles:
            error_file = self.output_dir / "failed_tiles.txt"
            with open(error_file, "w") as f:
                for tile in sorted(self.error_tiles):
                    f.write(f"{tile}\n")
            logger.info(f"Failed tiles saved to {error_file} ({len(self.error_tiles)} tiles)")
        
        # Create supporting files
        self.create_supporting_files(self.wgs84_bounds, min_zoom, max_zoom)
        
        return total_generated
    
    def create_supporting_files(self, bounds, min_zoom, max_zoom):
        """Create supporting files for the tile set"""
        logger.info("Creating supporting files...")
        
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        # Create metadata
        metadata = {
            "generated": True,
            "generator": "Optimized Kochi Tile Generator v2.1 (Fixed)",
            "min_zoom": min_zoom,
            "max_zoom": max_zoom,
            "bounds": {
                "west": bounds[0],
                "south": bounds[1],
                "east": bounds[2],
                "north": bounds[3]
            },
            "center": {
                "longitude": center_lon,
                "latitude": center_lat
            },
            "optimization_settings": {
                "resampling": "bilinear/lanczos",
                "sharpening": True,
                "contrast_enhancement": 1.1,
                "png_compression": 6,
                "parallel_workers": self.num_workers,
                "strategy": self.strategy if hasattr(self, 'strategy') else "unknown"
            }
        }
        
        with open(self.output_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        # Create TileJSON
        tilejson = {
            "tilejson": "2.2.0",
            "name": "Kochi Masterplan (Optimized)",
            "description": "High-quality master plan tiles for Kochi",
            "version": "2.1.0",
            "attribution": "Kochi Development Authority",
            "scheme": "xyz",
            "tiles": [
                "https://yourdomain.com/tiles/{z}/{x}/{y}.png"
            ],
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "bounds": list(bounds),
            "center": [center_lon, center_lat, 12]
        }
        
        with open(self.output_dir / "tilejson.json", "w") as f:
            json.dump(tilejson, f, indent=2)
        
        logger.info("Created supporting files: metadata.json, tilejson.json")

def main():
    """Main function with CLI arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Optimized Kochi Masterplan tile generator for large GeoTIFFs'
    )
    parser.add_argument('--data-dir', 
                       default='data/tamil_nadu/kochi/kochi_master_plan',
                       help='Directory containing the GeoTIFF file')
    parser.add_argument('--output-dir', 
                       default='kochi_masterplan_tiles',
                       help='Directory for output tiles')
    parser.add_argument('--min-zoom', type=int, default=6,
                       help='Minimum zoom level (default: 6)')
    parser.add_argument('--max-zoom', type=int, default=18,
                       help='Maximum zoom level (default: 18)')
    parser.add_argument('--workers', type=int, default=None,
                       help='Number of parallel workers (default: auto-detect)')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='Batch size for processing (default: 100)')
    parser.add_argument('--cache-size', type=int, default=1000,
                       help='Cache size for tiles (default: 1000)')
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("OPTIMIZED KOCHI MASTERPLAN TILE GENERATOR - FIXED VERSION")
    logger.info("="*60)
    logger.info(f"Configuration:")
    logger.info(f"  Data directory: {args.data_dir}")
    logger.info(f"  Output directory: {args.output_dir}")
    logger.info(f"  Zoom range: {args.min_zoom} - {args.max_zoom}")
    if args.workers:
        logger.info(f"  Workers: {args.workers}")
    logger.info(f"  Batch size: {args.batch_size}")
    logger.info("="*60)
    
    # Initialize generator
    generator = OptimizedKochiTileGenerator(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        num_workers=args.workers,
        batch_size=args.batch_size,
        cache_size=args.cache_size
    )
    
    # Generate tiles
    total = generator.generate_tiles_parallel(
        min_zoom=args.min_zoom,
        max_zoom=args.max_zoom
    )
    
    logger.info("="*60)
    logger.info(f"PROCESSING COMPLETE!")
    logger.info(f"Total tiles successfully generated: {total}")
    logger.info(f"Output directory: {args.output_dir}")
    logger.info("="*60)

if __name__ == "__main__":
    main()