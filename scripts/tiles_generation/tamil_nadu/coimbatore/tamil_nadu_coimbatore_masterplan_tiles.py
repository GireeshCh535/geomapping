#!/usr/bin/env python3
"""
High-performance optimized tile generator for Coimbatore Masterplan GeoTIFF
Handles all zoom levels efficiently with smart caching, parallel processing, and error recovery

Supports multiple CRS:
- EPSG:3857 (Web Mercator) - Optimized handling for web mapping
- EPSG:32644 (UTM Zone 44N) - Standard UTM projection
- Other CRS - Automatic conversion to WGS84
"""

import os
import sys
import numpy as np
from pathlib import Path
import mercantile
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
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
os.environ['CPL_LOG'] = '/dev/null'
os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'TRUE'
os.environ['GDAL_PAM_ENABLED'] = 'NO'
os.environ['GDAL_CACHEMAX'] = '512'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OptimizedCoimbatoreTileGenerator:
    """
    High-performance tile generator for Coimbatore Masterplan with advanced optimizations
    """
    
    def __init__(self, data_dir: str = "data/tamil_nadu/coimbatore/coimbatore_master_plan",
                 output_dir: str = "coimbatore_masterplan_tiles",
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
        
        logger.info(f"Optimized Coimbatore Tile Generator initialized")
        logger.info(f"Workers: {self.num_workers}, Cache size: {cache_size}, Max memory: {self.max_memory_mb}MB")
    
    def open_and_prepare_geotiff(self, geotiff_path):
        """Open GeoTIFF and prepare for processing"""
        try:
            self.src_dataset = rasterio.open(geotiff_path)
            
            logger.info(f"Opened GeoTIFF: {geotiff_path}")
            logger.info(f"Size: {self.src_dataset.width}x{self.src_dataset.height}")
            logger.info(f"CRS: {self.src_dataset.crs}")
            logger.info(f"Bands: {self.src_dataset.count}")
            logger.info(f"Data type: {self.src_dataset.dtypes[0]}")
            logger.info(f"Bounds: {self.src_dataset.bounds}")
            
            # Calculate WGS84 bounds (handle both UTM and Web Mercator)
            if str(self.src_dataset.crs) == 'EPSG:3857':
                # Already in Web Mercator, convert to WGS84
                self.wgs84_bounds = transform_bounds(
                    'EPSG:3857', 'EPSG:4326',
                    *self.src_dataset.bounds
                )
            else:
                # Convert from UTM or other CRS to WGS84
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
            
            # Choose strategy based on size
            if file_size_mb < self.max_memory_mb * 0.3:
                self.strategy = "memory"
                logger.info(f"Using MEMORY strategy (file size: {file_size_mb:.1f}MB)")
                self.load_to_memory()
            else:
                self.strategy = "windowed"
                logger.info(f"Using WINDOWED strategy (file size: {file_size_mb:.1f}MB)")
                
        except Exception as e:
            logger.warning(f"Could not determine optimal strategy: {e}, using windowed")
            self.strategy = "windowed"
    
    def load_to_memory(self):
        """Load entire dataset to memory for fastest access"""
        try:
            logger.info("Loading dataset to memory for fastest processing...")
            self.data_array = self.src_dataset.read()
            self.src_transform = self.src_dataset.transform
            self.src_crs = self.src_dataset.crs
            logger.info(f"Loaded {self.data_array.shape} array to memory")
        except Exception as e:
            logger.warning(f"Failed to load to memory: {e}, falling back to windowed")
            self.strategy = "windowed"
    
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
            
            # For high zoom levels (18+), try parent upsampling
            if zoom >= 18 and self.generate_from_parent(zoom, x, y, tile_path):
                return True
            
            # Generate tile based on strategy
            if self.strategy == "memory":
                success = self.generate_from_memory(tile_bounds, tile_path)
            else:
                success = self.generate_from_window(tile_bounds, tile_path)
            
            if not success:
                self.error_tiles.add(tile_key)
            
            return success
            
        except Exception as e:
            logger.debug(f"Error generating tile {tile_key}: {e}")
            self.error_tiles.add(tile_key)
            return False
    
    def generate_from_parent(self, zoom, x, y, tile_path):
        """Generate high-zoom tile by upsampling parent with improved quality"""
        try:
            parent_zoom = zoom - 1
            parent_x = x // 2
            parent_y = y // 2
            parent_path = self.output_dir / str(parent_zoom) / str(parent_x) / f"{parent_y}.png"
            
            if parent_path.exists():
                parent_img = Image.open(parent_path)
                
                # Extract quadrant
                quad_x = x % 2
                quad_y = y % 2
                left = quad_x * 128
                top = quad_y * 128
                
                quadrant = parent_img.crop((left, top, left + 128, top + 128))
                tile_img = quadrant.resize((256, 256), Image.Resampling.LANCZOS)
                
                # Apply minimal enhancement to preserve original colors
                tile_img = tile_img.filter(ImageFilter.SHARPEN)
                tile_img.save(tile_path, 'PNG', optimize=True, compress_level=6)
                return True
                
        except Exception:
            pass
        return False
    
    def generate_from_memory(self, tile_bounds, tile_path):
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
            
            # Reproject from memory with exact color preservation
            # Handle EPSG:3857 efficiently (no reprojection needed for Web Mercator)
            if str(self.src_crs) == 'EPSG:3857':
                # For Web Mercator, we can use direct resampling without full reprojection
                reproject(
                    source=self.data_array,
                    destination=tile_data,
                    src_transform=self.src_transform,
                    src_crs=self.src_crs,
                    dst_transform=tile_transform,
                    dst_crs='EPSG:4326',
                    resampling=Resampling.nearest,  # Use nearest for exact color preservation
                    src_nodata=0,
                    dst_nodata=0,
                    num_threads=1  # Single thread for consistency
                )
            else:
                # For UTM and other CRS, use standard reprojection
                reproject(
                    source=self.data_array,
                    destination=tile_data,
                    src_transform=self.src_transform,
                    src_crs=self.src_crs,
                    dst_transform=tile_transform,
                    dst_crs='EPSG:4326',
                    resampling=Resampling.nearest,  # Use nearest for exact color preservation
                    src_nodata=0,
                    dst_nodata=0,
                    num_threads=1  # Single thread for consistency
                )
            
            return self.save_tile(tile_data, tile_path)
            
        except Exception as e:
            logger.debug(f"Memory generation failed: {e}")
            return False
    
    def generate_from_window(self, tile_bounds, tile_path):
        """Generate tile using windowed reading with improved overlap handling"""
        try:
            # Check if dataset has proper georeferencing
            if self.src_dataset.transform is None or self.src_dataset.transform == rasterio.Affine.identity():
                logger.warning("Dataset has no proper geotransform, skipping tile")
                return False
            
            # Add generous overlap to prevent gaps (5% of tile size)
            overlap_factor = 0.05
            tile_width = tile_bounds.east - tile_bounds.west
            tile_height = tile_bounds.north - tile_bounds.south
            
            overlap_x = tile_width * overlap_factor
            overlap_y = tile_height * overlap_factor
            
            # Expand bounds to ensure complete coverage
            expanded_bounds = (
                tile_bounds.west - overlap_x,
                tile_bounds.south - overlap_y,
                tile_bounds.east + overlap_x,
                tile_bounds.north + overlap_y
            )
            
            # Transform expanded bounds to source CRS
            if str(self.src_dataset.crs) == 'EPSG:3857':
                # For Web Mercator, use direct transformation
                src_bounds = transform_bounds(
                    'EPSG:4326', 'EPSG:3857',
                    *expanded_bounds
                )
            else:
                # For UTM and other CRS
                src_bounds = transform_bounds(
                    'EPSG:4326', self.src_dataset.crs,
                    *expanded_bounds
                )
            
            # Calculate window with proper rounding
            window = window_from_bounds(
                *src_bounds,
                transform=self.src_dataset.transform
            )
            
            # Use floor for offset and ceil for size to ensure complete coverage
            import math
            col_off = max(0, int(window.col_off))
            row_off = max(0, int(window.row_off))
            width = min(math.ceil(window.width) + 2, self.src_dataset.width - col_off)
            height = min(math.ceil(window.height) + 2, self.src_dataset.height - row_off)
            
            # Ensure minimum size
            width = max(4, width)
            height = max(4, height)
            
            window = Window(col_off, row_off, width, height)
            
            # Create destination array
            tile_data = np.zeros((4, 256, 256), dtype=np.uint8)
            
            # Create transform for tile
            tile_transform = from_bounds(
                tile_bounds.west, tile_bounds.south,
                tile_bounds.east, tile_bounds.north,
                256, 256
            )
            
            # Read and reproject with warning suppression
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                window_data = self.src_dataset.read(window=window, boundless=True, fill_value=0)
                window_transform = self.src_dataset.window_transform(window)
                
                # Handle EPSG:3857 efficiently
                if str(self.src_dataset.crs) == 'EPSG:3857':
                    # For Web Mercator, optimized reprojection
                    reproject(
                        source=window_data,
                        destination=tile_data,
                        src_transform=window_transform,
                        src_crs='EPSG:3857',
                        dst_transform=tile_transform,
                        dst_crs='EPSG:4326',
                        resampling=Resampling.nearest,  # Use nearest for exact color preservation
                        src_nodata=0,
                        dst_nodata=0,
                        num_threads=1  # Single thread for consistency
                    )
                else:
                    # For UTM and other CRS
                    reproject(
                        source=window_data,
                        destination=tile_data,
                        src_transform=window_transform,
                        src_crs=self.src_dataset.crs,
                        dst_transform=tile_transform,
                        dst_crs='EPSG:4326',
                        resampling=Resampling.nearest,  # Use nearest for exact color preservation
                        src_nodata=0,
                        dst_nodata=0,
                        num_threads=1  # Single thread for consistency
                    )
            
            return self.save_tile(tile_data, tile_path)
            
        except Exception as e:
            logger.debug(f"Window generation failed: {e}")
            return False
    
    def save_tile(self, tile_data, tile_path):
        """Save tile with exact color preservation - FIXED for seamless boundaries"""
        try:
            # Convert to image (tile_data is in CHW format)
            img_array = np.transpose(tile_data, (1, 2, 0))
            
            # Check for content - be more lenient to include edge tiles
            if np.sum(img_array[:, :, 3]) < 5:  # Very little alpha content
                return False
            
            # FIXED: Use the BMRDA approach - create completely transparent background
            # and only draw pixels with actual content
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Process each pixel individually like BMRDA scripts
            for y in range(256):
                for x in range(256):
                    r = int(img_array[y, x, 0])
                    g = int(img_array[y, x, 1])
                    b = int(img_array[y, x, 2])
                    a = int(img_array[y, x, 3])
                    
                    # Only draw pixels that are not transparent
                    # FIXED: Preserve ALL colors including black (0,0,0) - only check alpha
                    if a > 0:
                        rgb_color = (r, g, b)
                        draw.point((x, y), fill=rgb_color)
            
            # Save with optimized settings
            img.save(tile_path, 'PNG', optimize=True, compress_level=6)
            return True
            
        except Exception as e:
            logger.debug(f"Failed to save tile: {e}")
            return False
    
    def tile_in_bounds(self, tile_bounds):
        """Check if tile intersects data bounds with generous tolerance to prevent gaps"""
        # Add generous tolerance to avoid gaps at tile boundaries
        tolerance = 1e-4  # Increased tolerance
        
        return not (
            tile_bounds.east < self.wgs84_bounds[0] - tolerance or
            tile_bounds.west > self.wgs84_bounds[2] + tolerance or
            tile_bounds.south > self.wgs84_bounds[3] + tolerance or
            tile_bounds.north < self.wgs84_bounds[1] - tolerance
        )
    
    def generate_tiles_parallel(self, min_zoom=8, max_zoom=16):
        """Generate tiles in parallel with optimal settings"""
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
            for zoom in range(min_zoom, max_zoom + 1):
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing zoom level {zoom}")
                
                # Calculate tile range
                min_tile = mercantile.tile(self.wgs84_bounds[0], self.wgs84_bounds[1], zoom)
                max_tile = mercantile.tile(self.wgs84_bounds[2], self.wgs84_bounds[3], zoom)
                
                # Generate tile list
                tiles = []
                for x in range(min_tile.x, max_tile.x + 1):
                    for y in range(max_tile.y, min_tile.y + 1):
                        tiles.append((zoom, x, y))
                
                logger.info(f"Generating {len(tiles)} tiles for zoom {zoom}")
                
                # Adjust workers and batch size for high zoom
                if zoom >= 18:
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
                    if i % (batch_size * 10) == 0:
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
        
        # Save error report if needed
        if self.error_tiles:
            with open(self.output_dir / "failed_tiles.txt", "w") as f:
                for tile in sorted(self.error_tiles):
                    f.write(f"{tile}\n")
            logger.info(f"Failed tiles saved to failed_tiles.txt ({len(self.error_tiles)} tiles)")
        
        # Create supporting files
        self.create_supporting_files(self.wgs84_bounds, min_zoom, max_zoom)
        
        return total_generated
    
    def create_supporting_files(self, bounds, min_zoom, max_zoom):
        """Create supporting files for the tile set"""
        logger.info("Creating supporting files...")
        
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        # Create Mapbox style JSON
        style_json = {
            "version": 8,
            "name": "Tamil Nadu - Coimbatore Masterplan (Optimized)",
            "sources": {
                "coimbatore-masterplan": {
                    "type": "raster",
                    "tiles": [
                        "https://d17yosovmfjm4.cloudfront.net/tamil_nadu/coimbatore/coimbatore_masterplan/{z}/{x}/{y}.png"
                    ],
                    "tileSize": 256,
                    "minzoom": min_zoom,
                    "maxzoom": max_zoom
                }
            },
            "layers": [
                {
                    "id": "coimbatore-masterplan-layer",
                    "type": "raster",
                    "source": "coimbatore-masterplan",
                    "minzoom": min_zoom,
                    "maxzoom": max_zoom,
                    "paint": {
                        "raster-opacity": 0.9,
                        "raster-resampling": "linear"
                    }
                }
            ]
        }
        
        with open(self.output_dir / "style.json", "w") as f:
            json.dump(style_json, f, indent=2)
        
        # Create TileJSON
        tilejson = {
            "tilejson": "2.2.0",
            "name": "Tamil Nadu - Coimbatore Masterplan (Optimized)",
            "description": "High-quality master plan tiles for Tamil Nadu - Coimbatore",
            "version": "2.0.0",
            "attribution": "Tamil Nadu Government",
            "scheme": "xyz",
            "tiles": [
                "https://d17yosovmfjm4.cloudfront.net/tamil_nadu/coimbatore/coimbatore_masterplan/{z}/{x}/{y}.png"
            ],
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "bounds": list(bounds),
            "center": [center_lon, center_lat, 12]
        }
        
        with open(self.output_dir / "tilejson.json", "w") as f:
            json.dump(tilejson, f, indent=2)
        
        # Create metadata
        metadata = {
            "generated": True,
            "generator": "Optimized Coimbatore Tile Generator v2.0",
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
                "resampling": "cubic",
                "sharpening": True,
                "contrast_enhancement": 1.05,
                "png_compression": 6,
                "parallel_workers": self.num_workers,
                "strategy": self.strategy if hasattr(self, 'strategy') else "unknown"
            }
        }
        
        with open(self.output_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        # Create HTML viewer
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Tamil Nadu - Coimbatore Masterplan (Optimized)</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js'></script>
    <link href='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css' rel='stylesheet' />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
        .info-box {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(255,255,255,0.9);
            padding: 10px;
            border-radius: 5px;
            font-family: Arial;
            font-size: 12px;
            z-index: 1;
        }}
        .controls {{
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(255,255,255,0.9);
            padding: 10px;
            border-radius: 5px;
            font-family: Arial;
            font-size: 12px;
            z-index: 1;
        }}
    </style>
</head>
<body>
    <div id='map'></div>
    <div class='info-box'>
        <strong>Coimbatore Masterplan</strong><br>
        Zoom: <span id='zoom'>12</span><br>
        Range: {min_zoom} - {max_zoom}
    </div>
    <div class='controls'>
        <label>
            <input type="range" id="opacity" min="0" max="100" value="90" />
            Opacity: <span id="opacity-value">90%</span>
        </label>
    </div>
    <script>
        // Initialize map with OSM base layer
        var map = new mapboxgl.Map({{
            container: 'map',
            style: {{
                "version": 8,
                "sources": {{
                    "osm": {{
                        "type": "raster",
                        "tiles": [
                            "https://a.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png"
                        ],
                        "tileSize": 256,
                        "attribution": "© OpenStreetMap contributors"
                    }},
                    "coimbatore-masterplan": {{
                        "type": "raster",
                        "tiles": [
                            "./{{z}}/{{x}}/{{y}}.png"
                        ],
                        "tileSize": 256,
                        "minzoom": {min_zoom},
                        "maxzoom": {max_zoom}
                    }}
                }},
                "layers": [
                    {{
                        "id": "osm-base",
                        "type": "raster",
                        "source": "osm",
                        "paint": {{
                            "raster-opacity": 0.5
                        }}
                    }},
                    {{
                        "id": "coimbatore-masterplan-layer",
                        "type": "raster",
                        "source": "coimbatore-masterplan",
                        "minzoom": {min_zoom},
                        "maxzoom": {max_zoom},
                        "paint": {{
                            "raster-opacity": 0.9,
                            "raster-resampling": "linear"
                        }}
                    }}
                ]
            }},
            center: [{center_lon}, {center_lat}],
            zoom: 12,
            minZoom: {min_zoom},
            maxZoom: {max_zoom}
        }});
        
        // Update zoom display
        map.on('zoom', function() {{
            document.getElementById('zoom').innerText = map.getZoom().toFixed(1);
        }});
        
        // Opacity control
        document.getElementById('opacity').addEventListener('input', function(e) {{
            var opacity = e.target.value / 100;
            map.setPaintProperty('coimbatore-masterplan-layer', 'raster-opacity', opacity);
            document.getElementById('opacity-value').innerText = e.target.value + '%';
        }});
        
        // Add controls
        map.addControl(new mapboxgl.NavigationControl());
        map.addControl(new mapboxgl.FullscreenControl());
        map.addControl(new mapboxgl.ScaleControl());
    </script>
</body>
</html>
"""
        
        with open(self.output_dir / "viewer.html", "w") as f:
            f.write(html_content)
        
        logger.info("Created supporting files: style.json, tilejson.json, metadata.json, viewer.html")

def main():
    """Main function with CLI arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Optimized Coimbatore Masterplan tile generator with high performance and error recovery'
    )
    parser.add_argument('--data-dir', 
                       default='data/tamil_nadu/coimbatore/coimbatore_master_plan',
                       help='Directory containing the GeoTIFF file')
    parser.add_argument('--output-dir', 
                       default='coimbatore_masterplan_tiles_main',
                       help='Directory for output tiles')
    parser.add_argument('--min-zoom', type=int, default=8,
                       help='Minimum zoom level (default: 8)')
    parser.add_argument('--max-zoom', type=int, default=18,
                       help='Maximum zoom level (default: 16)')
    parser.add_argument('--workers', type=int, default=None,
                       help='Number of parallel workers (default: auto-detect)')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='Batch size for processing (default: 100)')
    parser.add_argument('--cache-size', type=int, default=1000,
                       help='Cache size for tiles (default: 1000)')
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("OPTIMIZED COIMBATORE MASTERPLAN TILE GENERATOR")
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
    generator = OptimizedCoimbatoreTileGenerator(
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