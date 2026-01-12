#!/usr/bin/env python3
"""
Universal TIF Tile Generator
Generates high-quality PNG tiles from any RGBA GeoTIFF file
Uses pixel-by-pixel rendering for maximum quality with multi-threading support
"""

import os
import sys
import math
import argparse
import numpy as np
from pathlib import Path
import mercantile
from PIL import Image, ImageDraw
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from concurrent.futures import ThreadPoolExecutor
import multiprocessing as mp
import logging
import time
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UniversalTIFTileGenerator:
    """
    Generate high-quality PNG tiles from any RGBA GeoTIFF with multi-threading
    Maintains pixel-by-pixel rendering for maximum quality
    """
    
    def __init__(self, tif_path: str, output_dir: str, max_workers: int = None, 
                 layer_name: str = None, cdn_url: str = None):
        """
        Initialize Universal TIF Tile Generator
        
        Args:
            tif_path: Path to the GeoTIFF file
            output_dir: Output directory for tiles
            max_workers: Number of worker threads (default: min(CPU count, 8))
            layer_name: Name for the layer (default: derived from tif_path)
            cdn_url: CDN URL template for tiles (optional)
        """
        self.tif_path = Path(tif_path)
        if not self.tif_path.exists():
            raise FileNotFoundError(f"GeoTIFF file not found: {tif_path}")
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set number of workers for parallel processing
        self.max_workers = max_workers or min(mp.cpu_count(), 8)
        
        # Layer name for metadata files
        self.layer_name = layer_name or self.tif_path.stem.replace('_', ' ').title()
        
        # CDN URL template (optional)
        self.cdn_url = cdn_url
        
        # Cache for reprojected data
        self.wgs84_data_r = None
        self.wgs84_data_g = None
        self.wgs84_data_b = None
        self.wgs84_data_a = None
        self.wgs84_bounds = None
        self.wgs84_transform = None
        self.num_bands = None
        
        logger.info(f"Universal TIF Tile Generator initialized with {self.max_workers} workers")
        logger.info(f"Input: {self.tif_path}")
        logger.info(f"Output: {self.output_dir}")
    
    def load_data(self):
        """Load and cache the reprojected data once"""
        if self.wgs84_data_r is not None:
            logger.info("Data already loaded and cached")
            return
        
        logger.info(f"Loading and caching GeoTIFF: {self.tif_path}")
        
        # Reproject GeoTIFF to WGS84 and cache the data
        result = self.reproject_geotiff_to_wgs84(self.tif_path)
        self.wgs84_data_r, self.wgs84_data_g, self.wgs84_data_b, self.wgs84_data_a, \
            self.wgs84_bounds, self.wgs84_transform, self.num_bands = result
        
        logger.info("Data loaded and cached successfully")
    
    def reproject_geotiff_to_wgs84(self, geotiff_path):
        """Reproject RGBA GeoTIFF to WGS84 and return the transformed data and bounds"""
        with rasterio.open(geotiff_path) as src:
            logger.info(f"Original CRS: {src.crs}")
            logger.info(f"Original bounds: {src.bounds}")
            logger.info(f"Original shape: {src.shape}")
            logger.info(f"Number of bands: {src.count}")
            
            num_bands = src.count
            
            # Calculate the transform to WGS84
            transform, width, height = calculate_default_transform(
                src.crs, 'EPSG:4326', src.width, src.height,
                left=src.bounds.left, bottom=src.bounds.bottom,
                right=src.bounds.right, top=src.bounds.top
            )
            
            # Handle different band configurations
            if num_bands >= 4:
                # RGBA or more bands - use first 4 bands
                logger.info("Processing as RGBA (4+ bands)")
                destination_r = np.zeros((height, width), dtype=src.dtypes[0])
                destination_g = np.zeros((height, width), dtype=src.dtypes[0])
                destination_b = np.zeros((height, width), dtype=src.dtypes[0])
                destination_a = np.zeros((height, width), dtype=src.dtypes[0])
                
                # Reproject each band
                reproject(
                    source=src.read(1),  # Red band
                    destination=destination_r,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs='EPSG:4326',
                    resampling=Resampling.nearest
                )
                
                reproject(
                    source=src.read(2),  # Green band
                    destination=destination_g,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs='EPSG:4326',
                    resampling=Resampling.nearest
                )
                
                reproject(
                    source=src.read(3),  # Blue band
                    destination=destination_b,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs='EPSG:4326',
                    resampling=Resampling.nearest
                )
                
                reproject(
                    source=src.read(4),  # Alpha band
                    destination=destination_a,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs='EPSG:4326',
                    resampling=Resampling.nearest
                )
                
            elif num_bands == 3:
                # RGB - create opaque alpha channel
                logger.info("Processing as RGB (3 bands) - creating opaque alpha")
                destination_r = np.zeros((height, width), dtype=src.dtypes[0])
                destination_g = np.zeros((height, width), dtype=src.dtypes[0])
                destination_b = np.zeros((height, width), dtype=src.dtypes[0])
                destination_a = np.full((height, width), 255, dtype=np.uint8)
                
                reproject(
                    source=src.read(1),  # Red band
                    destination=destination_r,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs='EPSG:4326',
                    resampling=Resampling.nearest
                )
                
                reproject(
                    source=src.read(2),  # Green band
                    destination=destination_g,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs='EPSG:4326',
                    resampling=Resampling.nearest
                )
                
                reproject(
                    source=src.read(3),  # Blue band
                    destination=destination_b,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs='EPSG:4326',
                    resampling=Resampling.nearest
                )
                
            elif num_bands == 1:
                # Grayscale - convert to RGB with opaque alpha
                logger.info("Processing as Grayscale (1 band) - converting to RGB")
                destination_gray = np.zeros((height, width), dtype=src.dtypes[0])
                
                reproject(
                    source=src.read(1),  # Grayscale band
                    destination=destination_gray,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs='EPSG:4326',
                    resampling=Resampling.nearest
                )
                
                # Convert grayscale to RGB
                destination_r = destination_gray.copy()
                destination_g = destination_gray.copy()
                destination_b = destination_gray.copy()
                destination_a = np.full((height, width), 255, dtype=np.uint8)
                
            else:
                raise ValueError(f"Unsupported number of bands: {num_bands}")
            
            # Calculate WGS84 bounds
            wgs84_bounds = {
                'west': transform[2],
                'south': transform[5] + height * transform[4],
                'east': transform[2] + width * transform[0],
                'north': transform[5]
            }
            
            logger.info(f"WGS84 bounds: {wgs84_bounds}")
            logger.info(f"WGS84 data shape: {destination_r.shape}")
            
            return destination_r, destination_g, destination_b, destination_a, wgs84_bounds, transform, num_bands
    
    def generate_tiles_for_zoom(self, zoom, min_tile, max_tile):
        """Generate all tiles for a specific zoom level using multi-threading"""
        # Reduce workers for higher zoom levels to prevent memory issues
        if zoom >= 15:
            workers = max(2, self.max_workers // 2)
        elif zoom >= 13:
            workers = max(4, self.max_workers // 2)
        else:
            workers = self.max_workers
        
        logger.info(f"Processing zoom level {zoom} with {workers} workers")
        
        zoom_dir = self.output_dir / str(zoom)
        zoom_dir.mkdir(exist_ok=True)
        
        tiles_generated = 0
        tiles_skipped = 0
        
        # Collect all tile tasks
        tile_tasks = []
        for x in range(min_tile.x, max_tile.x + 1):
            x_dir = zoom_dir / str(x)
            x_dir.mkdir(exist_ok=True)
            
            for y in range(max_tile.y, min_tile.y + 1):
                tile_path = x_dir / f"{y}.png"
                tile_tasks.append((x, y, tile_path))
        
        logger.info(f"Generated {len(tile_tasks)} tile tasks for zoom {zoom}")
        
        # Process tiles in batches to reduce memory pressure
        batch_size = 50 if zoom >= 14 else 100
        
        # Process tiles in parallel using ThreadPoolExecutor
        if tile_tasks:
            # Process in batches
            for batch_start in range(0, len(tile_tasks), batch_size):
                batch_end = min(batch_start + batch_size, len(tile_tasks))
                batch = tile_tasks[batch_start:batch_end]
                
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    # Submit batch tasks
                    future_to_tile = {
                        executor.submit(self.generate_single_tile, zoom, x, y, tile_path): (x, y, tile_path)
                        for x, y, tile_path in batch
                    }
                    
                    # Process completed tasks
                    for future in future_to_tile:
                        x, y, tile_path = future_to_tile[future]
                        try:
                            success = future.result()
                            if success:
                                tiles_generated += 1
                            else:
                                tiles_skipped += 1
                        except Exception as e:
                            logger.error(f"Error generating tile {zoom}/{x}/{y}: {e}")
                            tiles_skipped += 1
                        
                        # Log progress every 50 tiles
                        if (tiles_generated + tiles_skipped) % 50 == 0:
                            logger.info(f"Zoom {zoom}: Generated {tiles_generated}, Skipped {tiles_skipped}")
        
        logger.info(f"Zoom {zoom} completed: {tiles_generated} generated, {tiles_skipped} skipped")
        return tiles_generated
    
    def generate_tiles(self, min_zoom=8, max_zoom=16):
        """Generate PNG tiles for the GeoTIFF with multi-threading"""
        start_time = time.time()
        
        # Load data once and cache it
        self.load_data()
        
        if self.wgs84_data_r is None:
            logger.error("Failed to load data")
            return 0
        
        # Calculate tile bounds
        min_tile = mercantile.tile(self.wgs84_bounds['west'], self.wgs84_bounds['south'], min_zoom)
        max_tile = mercantile.tile(self.wgs84_bounds['east'], self.wgs84_bounds['north'], max_zoom)
        
        total_tiles = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            # Recalculate tile bounds for this zoom level
            min_tile = mercantile.tile(self.wgs84_bounds['west'], self.wgs84_bounds['south'], zoom)
            max_tile = mercantile.tile(self.wgs84_bounds['east'], self.wgs84_bounds['north'], zoom)
            
            # Generate tiles for this zoom level
            tiles_generated = self.generate_tiles_for_zoom(zoom, min_tile, max_tile)
            total_tiles += tiles_generated
        
        end_time = time.time()
        duration = end_time - start_time
        
        logger.info(f"Generated {total_tiles} PNG tiles in {duration:.2f} seconds")
        logger.info(f"Average speed: {total_tiles/duration:.2f} tiles/second")
        
        # Create supporting files
        self.create_supporting_files(self.wgs84_bounds, min_zoom, max_zoom)
        
        return total_tiles
    
    def generate_single_tile(self, zoom, x, y, tile_path):
        """Generate a single PNG tile using pixel-by-pixel rendering"""
        try:
            # Skip if tile already exists
            if tile_path.exists():
                return False
            
            # Get tile bounds
            tile_bounds = mercantile.bounds(x, y, zoom)
            
            # Create a blank tile
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Render the WGS84 data to this tile using pixel-by-pixel approach
            self.render_data_to_tile(tile_bounds, draw)
            
            # Save the tile
            img.save(tile_path, 'PNG')
            return True
            
        except Exception as e:
            logger.error(f"Error generating tile {zoom}/{x}/{y}: {e}")
            return False
    
    def render_data_to_tile(self, tile_bounds, draw):
        """Render WGS84 data to a tile using optimized numpy array operations"""
        try:
            # Check if tile bounds intersect with data bounds
            if (tile_bounds.east < self.wgs84_bounds['west'] or 
                tile_bounds.west > self.wgs84_bounds['east'] or 
                tile_bounds.south > self.wgs84_bounds['north'] or 
                tile_bounds.north < self.wgs84_bounds['south']):
                return
            
            # Get data dimensions
            height, width = self.wgs84_data_r.shape
            
            # Create coordinate arrays for the tile (256x256)
            tile_x_coords = np.arange(256)
            tile_y_coords = np.arange(256)
            
            # Convert tile pixel coordinates to WGS84 coordinates using vectorization
            lon_coords = tile_bounds.west + (tile_bounds.east - tile_bounds.west) * tile_x_coords / 256.0
            lat_coords = tile_bounds.north - (tile_bounds.north - tile_bounds.south) * tile_y_coords / 256.0
            
            # Create meshgrid for all tile pixels
            lon_grid, lat_grid = np.meshgrid(lon_coords, lat_coords)
            
            # Convert WGS84 coordinates to data pixel coordinates using vectorized operation
            from rasterio.transform import rowcol
            
            # Flatten grids for processing
            lon_flat = lon_grid.flatten()
            lat_flat = lat_grid.flatten()
            
            # Convert to data coordinates (vectorized)
            rows, cols = rowcol(self.wgs84_transform, lon_flat, lat_flat)
            rows = np.array(rows, dtype=np.int32)
            cols = np.array(cols, dtype=np.int32)
            
            # Reshape back to tile dimensions
            rows = rows.reshape(256, 256)
            cols = cols.reshape(256, 256)
            
            # Create mask for valid coordinates
            valid_mask = (cols >= 0) & (cols < width) & (rows >= 0) & (rows < height)
            
            # Extract RGB values using advanced indexing (much faster)
            r_values = np.zeros((256, 256), dtype=np.uint8)
            g_values = np.zeros((256, 256), dtype=np.uint8)
            b_values = np.zeros((256, 256), dtype=np.uint8)
            a_values = np.zeros((256, 256), dtype=np.uint8)
            
            # Use numpy advanced indexing for valid pixels
            valid_rows = rows[valid_mask]
            valid_cols = cols[valid_mask]
            
            r_values[valid_mask] = self.wgs84_data_r[valid_rows, valid_cols].astype(np.uint8)
            g_values[valid_mask] = self.wgs84_data_g[valid_rows, valid_cols].astype(np.uint8)
            b_values[valid_mask] = self.wgs84_data_b[valid_rows, valid_cols].astype(np.uint8)
            a_values[valid_mask] = self.wgs84_data_a[valid_rows, valid_cols].astype(np.uint8)
            
            # Create RGBA image array
            rgba_array = np.zeros((256, 256, 4), dtype=np.uint8)
            rgba_array[:, :, 0] = r_values
            rgba_array[:, :, 1] = g_values
            rgba_array[:, :, 2] = b_values
            rgba_array[:, :, 3] = a_values
            
            # Convert to PIL Image and composite onto existing image
            tile_img = Image.fromarray(rgba_array, 'RGBA')
            
            # Composite onto the existing image (which starts transparent)
            # This is more efficient than drawing point by point
            img_array = np.array(draw._image, dtype=np.uint8)
            if img_array.shape[2] == 4:  # RGBA
                # Alpha composite
                alpha = rgba_array[:, :, 3:4] / 255.0
                img_array[:, :, :3] = (img_array[:, :, :3] * (1 - alpha) + 
                                      rgba_array[:, :, :3] * alpha).astype(np.uint8)
                img_array[:, :, 3] = np.maximum(img_array[:, :, 3], rgba_array[:, :, 3])
                draw._image = Image.fromarray(img_array, 'RGBA')
            else:
                # Fallback: draw the image directly
                draw._image = Image.alpha_composite(draw._image, tile_img)
        
        except Exception as e:
            logger.error(f"Error rendering data to tile: {e}")
            # Fallback to point-by-point rendering if vectorized approach fails
            try:
                self._render_data_to_tile_fallback(tile_bounds, draw)
            except Exception as e2:
                logger.error(f"Fallback rendering also failed: {e2}")
    
    def _render_data_to_tile_fallback(self, tile_bounds, draw):
        """Fallback point-by-point rendering if vectorized approach fails"""
        # Check if tile bounds intersect with data bounds
        if (tile_bounds.east < self.wgs84_bounds['west'] or 
            tile_bounds.west > self.wgs84_bounds['east'] or 
            tile_bounds.south > self.wgs84_bounds['north'] or 
            tile_bounds.north < self.wgs84_bounds['south']):
            return
        
        # Get data dimensions
        height, width = self.wgs84_data_r.shape
        
        # Sample every 2nd pixel for fallback to reduce memory
        step = 2
        for tile_y in range(0, 256, step):
            for tile_x in range(0, 256, step):
                # Convert tile pixel to WGS84 coordinates
                lon = tile_bounds.west + (tile_bounds.east - tile_bounds.west) * tile_x / 256
                lat = tile_bounds.north - (tile_bounds.north - tile_bounds.south) * tile_y / 256
                
                # Convert WGS84 coordinates to data pixel coordinates
                data_x, data_y = self.wgs84_to_data_pixel(lon, lat, width, height)
                
                if 0 <= data_x < width and 0 <= data_y < height:
                    r = int(self.wgs84_data_r[data_y, data_x])
                    g = int(self.wgs84_data_g[data_y, data_x])
                    b = int(self.wgs84_data_b[data_y, data_x])
                    a = int(self.wgs84_data_a[data_y, data_x])
                    
                    # Only draw pixels that are not transparent
                    if a > 0:
                        rgb_color = (r, g, b)
                        # Draw a small rectangle instead of point for better coverage
                        draw.rectangle([tile_x, tile_y, tile_x + step - 1, tile_y + step - 1], fill=rgb_color)
    
    def wgs84_to_data_pixel(self, lon, lat, width, height):
        """Convert WGS84 coordinates to data pixel coordinates"""
        # Use the inverse transform to get pixel coordinates
        from rasterio.transform import rowcol
        
        row, col = rowcol(self.wgs84_transform, lon, lat)
        return int(col), int(row)
    
    def create_supporting_files(self, bounds, min_zoom, max_zoom):
        """Create supporting files for the tile set"""
        logger.info("Creating supporting files...")
        
        # Determine tile URL template
        if self.cdn_url:
            tile_url_template = self.cdn_url
        else:
            # Use relative path
            tile_url_template = f"./{{z}}/{{x}}/{{y}}.png"
        
        # Create Mapbox style JSON
        style_json = {
            "version": 8,
            "name": self.layer_name,
            "sources": {
                "tif-layer": {
                    "type": "raster",
                    "tiles": [
                        tile_url_template.replace("{z}", "{z}").replace("{x}", "{x}").replace("{y}", "{y}")
                    ],
                    "tileSize": 256
                }
            },
            "layers": [
                {
                    "id": "tif-layer",
                    "type": "raster",
                    "source": "tif-layer",
                    "paint": {
                        "raster-opacity": 0.8
                    }
                }
            ]
        }
        
        with open(self.output_dir / "style.json", "w") as f:
            json.dump(style_json, f, indent=2)
        
        # Create TileJSON
        tilejson = {
            "tilejson": "2.2.0",
            "name": self.layer_name,
            "description": f"Tiles generated from {self.tif_path.name}",
            "version": "1.0.0",
            "attribution": "",
            "template": "",
            "legend": "",
            "scheme": "xyz",
            "tiles": [
                tile_url_template.replace("{z}", "{z}").replace("{x}", "{x}").replace("{y}", "{y}")
            ],
            "grids": [],
            "data": [],
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "bounds": [
                bounds['west'],
                bounds['south'],
                bounds['east'],
                bounds['north']
            ],
            "center": [
                (bounds['west'] + bounds['east']) / 2,
                (bounds['south'] + bounds['north']) / 2,
                10
            ]
        }
        
        with open(self.output_dir / "tilejson.json", "w") as f:
            json.dump(tilejson, f, indent=2)
        
        # Create HTML viewer
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{self.layer_name}</title>
    <script src='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js'></script>
    <link href='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css' rel='stylesheet' />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
    </style>
</head>
<body>
    <div id='map'></div>
    <script>
        mapboxgl.accessToken = 'pk.eyJ1IjoiZXhhbXBsZSIsImEiOiJjbGV4YW1wbGUifQ.example';
        var map = new mapboxgl.Map({{
            container: 'map',
            style: {{
                "version": 8,
                "sources": {{
                    "tif-layer": {{
                        "type": "raster",
                        "tiles": [
                            "{tile_url_template.replace('{z}', '{{z}}').replace('{x}', '{{x}}').replace('{y}', '{{y}}')}"
                        ],
                        "tileSize": 256
                    }}
                }},
                "layers": [
                    {{
                        "id": "tif-layer",
                        "type": "raster",
                        "source": "tif-layer",
                        "paint": {{
                            "raster-opacity": 0.8
                        }}
                    }}
                ]
            }},
            center: [{(bounds['west'] + bounds['east']) / 2}, {(bounds['south'] + bounds['north']) / 2}],
            zoom: 10
        }});
    </script>
</body>
</html>
"""
        
        with open(self.output_dir / "viewer.html", "w") as f:
            f.write(html_content)
        
        logger.info("Created supporting files: style.json, tilejson.json, viewer.html")


def main():
    """Main function with command-line interface"""
    parser = argparse.ArgumentParser(
        description='Universal TIF Tile Generator - Generate PNG tiles from any GeoTIFF file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python universal_tif_tile_generator.py data/kerala/thiruvananthapuram/masterplan/file.tif output_tiles

  # With custom zoom levels
  python universal_tif_tile_generator.py data/kerala/thiruvananthapuram/masterplan/file.tif output_tiles --min-zoom 10 --max-zoom 18

  # With custom layer name and CDN URL
  python universal_tif_tile_generator.py file.tif tiles --layer-name "Thiruvananthapuram Masterplan" --cdn-url "https://cdn.example.com/tiles/{z}/{x}/{y}.png"

  # With custom number of workers
  python universal_tif_tile_generator.py file.tif tiles --workers 16
        """
    )
    
    parser.add_argument('tif_path', type=str, help='Path to the GeoTIFF file')
    parser.add_argument('output_dir', type=str, help='Output directory for tiles')
    parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level (default: 8)')
    parser.add_argument('--max-zoom', type=int, default=16, help='Maximum zoom level (default: 16)')
    parser.add_argument('--workers', type=int, default=None, 
                       help='Number of worker threads (default: min(CPU count, 8))')
    parser.add_argument('--layer-name', type=str, default=None,
                       help='Layer name for metadata files (default: derived from filename)')
    parser.add_argument('--cdn-url', type=str, default=None,
                       help='CDN URL template for tiles (e.g., "https://cdn.example.com/tiles/{z}/{x}/{y}.png")')
    
    args = parser.parse_args()
    
    logger.info("="*80)
    logger.info("Universal TIF Tile Generator")
    logger.info("="*80)
    logger.info(f"Input TIF: {args.tif_path}")
    logger.info(f"Output Dir: {args.output_dir}")
    logger.info(f"Zoom Levels: {args.min_zoom} - {args.max_zoom}")
    logger.info(f"Workers: {args.workers or 'auto'}")
    logger.info("="*80)
    
    try:
        # Initialize generator
        generator = UniversalTIFTileGenerator(
            tif_path=args.tif_path,
            output_dir=args.output_dir,
            max_workers=args.workers,
            layer_name=args.layer_name,
            cdn_url=args.cdn_url
        )
        
        # Generate tiles
        total_tiles = generator.generate_tiles(
            min_zoom=args.min_zoom,
            max_zoom=args.max_zoom
        )
        
        logger.info("="*80)
        logger.info(f"Successfully generated {total_tiles} tiles!")
        logger.info(f"Output directory: {args.output_dir}")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
