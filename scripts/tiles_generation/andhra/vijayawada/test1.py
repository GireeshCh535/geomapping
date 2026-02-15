#!/usr/bin/env python3
"""
Optimized script to generate high-quality PNG tiles from Vijayawada Master Plan RGBA GeoTIFF
Uses parallel processing and optimized algorithms for faster tile generation with sharp output
"""

import os
import sys
import math
import numpy as np
from pathlib import Path
import mercantile
from PIL import Image
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.windows import from_bounds
from rasterio.transform import rowcol, xy
import logging
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from functools import partial
import multiprocessing
import warnings
warnings.filterwarnings('ignore', category=rasterio.errors.NotGeoreferencedWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OptimizedVijayawadaTileGenerator:
    """
    Generate high-quality PNG tiles from Vijayawada Master Plan RGBA GeoTIFF
    Optimized for speed using parallel processing and efficient algorithms
    """
    
    def __init__(self, data_dir: str = "data/andhra_pradesh/MGTM/master_plan",
                 output_dir: str = "vijayawada_masterplan_tiles1",
                 num_workers: int = None):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Set number of workers for parallel processing
        self.num_workers = num_workers or max(1, multiprocessing.cpu_count() - 1)
        
        logger.info(f"Vijayawada Master Plan Tile Generator initialized with {self.num_workers} workers")
    
    def create_reprojected_vrt(self, geotiff_path):
        """Create a VRT (Virtual Raster) for efficient reprojection without creating intermediate files"""
        import tempfile
        from rasterio.vrt import WarpedVRT
        
        with rasterio.open(geotiff_path) as src:
            logger.info(f"Original CRS: {src.crs}")
            logger.info(f"Original bounds: {src.bounds}")
            logger.info(f"Original shape: {src.shape}")
            logger.info(f"Number of bands: {src.count}")
            
            # Create a warped VRT in WGS84
            vrt = WarpedVRT(src, crs='EPSG:4326', resampling=Resampling.nearest)
            
            # Get WGS84 bounds
            wgs84_bounds = {
                'west': vrt.bounds.left,
                'south': vrt.bounds.bottom,
                'east': vrt.bounds.right,
                'north': vrt.bounds.top
            }
            
            logger.info(f"WGS84 bounds: {wgs84_bounds}")
            
            # Store VRT properties for later use
            vrt_props = {
                'transform': vrt.transform,
                'width': vrt.width,
                'height': vrt.height,
                'bounds': wgs84_bounds
            }
            
            return vrt, vrt_props
    
    def generate_tiles(self, min_zoom=4, max_zoom=18):
        """Generate PNG tiles for Vijayawada Master Plan with optimized parallel processing"""
        # Find the GeoTIFF file
        geotiff_path = self.data_dir / "Vijaywada_Clipped.tif"
        
        if not geotiff_path.exists():
            logger.error(f"GeoTIFF file not found: {geotiff_path}")
            return 0
        
        logger.info(f"Processing GeoTIFF: {geotiff_path}")
        
        total_tiles = 0
        
        # Open the source file once for all operations
        with rasterio.open(geotiff_path) as src_file:
            # Create warped VRT for WGS84 reprojection
            from rasterio.vrt import WarpedVRT
            
            with WarpedVRT(src_file, crs='EPSG:4326', resampling=Resampling.nearest) as vrt:
                wgs84_bounds = {
                    'west': vrt.bounds.left,
                    'south': vrt.bounds.bottom,
                    'east': vrt.bounds.right,
                    'north': vrt.bounds.top
                }
                
                logger.info(f"WGS84 bounds: {wgs84_bounds}")
                
                for zoom in range(min_zoom, max_zoom + 1):
                    logger.info(f"Processing zoom level {zoom}")
                    
                    # Calculate tile bounds for this zoom level
                    min_tile = mercantile.tile(wgs84_bounds['west'], wgs84_bounds['south'], zoom)
                    max_tile = mercantile.tile(wgs84_bounds['east'], wgs84_bounds['north'], zoom)
                    
                    zoom_dir = self.output_dir / str(zoom)
                    zoom_dir.mkdir(exist_ok=True)
                    
                    # Prepare all tile tasks for this zoom level
                    tile_tasks = []
                    for x in range(min_tile.x, max_tile.x + 1):
                        x_dir = zoom_dir / str(x)
                        x_dir.mkdir(exist_ok=True)
                        
                        for y in range(max_tile.y, min_tile.y + 1):
                            tile_path = x_dir / f"{y}.png"
                            tile_tasks.append((zoom, x, y, tile_path))
                    
                    # Process tiles in parallel for this zoom level
                    tiles_in_zoom = self.process_tiles_parallel(vrt, wgs84_bounds, tile_tasks)
                    
                    total_tiles += tiles_in_zoom
                    logger.info(f"Zoom {zoom} complete: {tiles_in_zoom} tiles generated")
        
        logger.info(f"✅ Generated {total_tiles} PNG tiles for Vijayawada Master Plan")
        
        # Create supporting files
        self.create_supporting_files(wgs84_bounds, min_zoom, max_zoom)
        
        return total_tiles
    
    def process_tiles_parallel(self, vrt, wgs84_bounds, tile_tasks):
        """Process multiple tiles in parallel"""
        tiles_generated = 0
        
        # Use ThreadPoolExecutor for I/O bound operations
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            # Create partial function with fixed parameters
            process_func = partial(self.generate_single_tile_optimized, vrt, wgs84_bounds)
            
            # Submit all tasks
            futures = {executor.submit(process_func, *task): task for task in tile_tasks}
            
            # Process completed tasks
            for future in as_completed(futures):
                try:
                    if future.result():
                        tiles_generated += 1
                except Exception as e:
                    task = futures[future]
                    logger.error(f"Error processing tile {task[0]}/{task[1]}/{task[2]}: {e}")
        
        return tiles_generated
    
    def generate_single_tile_optimized(self, vrt, wgs84_bounds, zoom, x, y, tile_path):
        """Generate a single PNG tile using optimized window reading"""
        try:
            # Get tile bounds
            tile_bounds = mercantile.bounds(x, y, zoom)
            
            # Check if tile intersects with data bounds
            if (tile_bounds.east < wgs84_bounds['west'] or 
                tile_bounds.west > wgs84_bounds['east'] or 
                tile_bounds.south > wgs84_bounds['north'] or 
                tile_bounds.north < wgs84_bounds['south']):
                return False
            
            # Calculate the window to read from the VRT
            window = from_bounds(
                max(tile_bounds.west, wgs84_bounds['west']),
                max(tile_bounds.south, wgs84_bounds['south']),
                min(tile_bounds.east, wgs84_bounds['east']),
                min(tile_bounds.north, wgs84_bounds['north']),
                vrt.transform
            )
            
            # Read data for this window
            try:
                # First, read at native resolution to preserve quality
                # Calculate optimal output size based on window size
                window_width = window.width
                window_height = window.height
                
                # Determine scale factor to avoid under-sampling
                scale_x = 256 / window_width if window_width > 0 else 1
                scale_y = 256 / window_height if window_height > 0 else 1
                
                # Read at higher resolution first if needed, then downsample
                if window_width < 256 or window_height < 256:
                    # Window is smaller than tile - read at native resolution
                    data = vrt.read(window=window, 
                                   resampling=Resampling.nearest)
                    
                    # Resize to 256x256 using nearest neighbor to maintain sharpness
                    if data.shape[1] != 256 or data.shape[2] != 256:
                        from scipy import ndimage
                        resized_data = np.zeros((4, 256, 256), dtype=data.dtype)
                        for i in range(min(4, data.shape[0])):
                            zoom_y = 256 / data.shape[1]
                            zoom_x = 256 / data.shape[2]
                            resized_data[i] = ndimage.zoom(data[i], (zoom_y, zoom_x), order=0)  # order=0 for nearest
                        data = resized_data
                else:
                    # Window is larger than tile - read and downsample
                    data = vrt.read(window=window, 
                                   out_shape=(4, 256, 256),
                                   resampling=Resampling.nearest)
                
                if data.size == 0:
                    return False
                
                # Extract RGBA bands
                r_band = data[0]
                g_band = data[1] if data.shape[0] > 1 else data[0]
                b_band = data[2] if data.shape[0] > 2 else data[0]
                a_band = data[3] if data.shape[0] > 3 else np.full((256, 256), 255)
                
                # Check if tile has any non-transparent data
                if np.all(a_band == 0) or (np.all(r_band == 0) and np.all(g_band == 0) and np.all(b_band == 0)):
                    return False
                
                # Create PIL image from numpy arrays
                # Stack the bands and ensure proper data type
                rgba_data = np.stack([r_band, g_band, b_band, a_band], axis=-1)
                rgba_data = np.clip(rgba_data, 0, 255).astype(np.uint8)
                
                # Create and save the image with maximum quality
                img = Image.fromarray(rgba_data, mode='RGBA')
                
                # Use PNG options for maximum sharpness
                img.save(tile_path, 'PNG', 
                        optimize=False,  # Disable optimization for better quality
                        compress_level=1,  # Minimal compression for maximum quality
                        dpi=(300, 300))   # High DPI for clarity
                
                return True
                
            except Exception as e:
                # Window might be out of bounds or too small
                return False
            
        except Exception as e:
            logger.error(f"Error generating tile {zoom}/{x}/{y}: {e}")
            return False
    
    def create_supporting_files(self, bounds, min_zoom, max_zoom):
        """Create supporting files for the tile set"""
        logger.info("Creating supporting files...")
        
        # Create metadata JSON
        import json
        
        metadata = {
            "name": "Andhra Pradesh MGTM - Vijayawada Master Plan",
            "description": "Master plan tiles for Vijayawada, Andhra Pradesh",
            "state": "Andhra Pradesh",
            "city": "Vijayawada",
            "authority": "MGTM",
            "bounds": {
                "west": bounds['west'],
                "south": bounds['south'],
                "east": bounds['east'],
                "north": bounds['north']
            },
            "center": [
                (bounds['west'] + bounds['east']) / 2,
                (bounds['south'] + bounds['north']) / 2
            ],
            "zoom": {
                "min": min_zoom,
                "max": max_zoom
            }
        }
        
        with open(self.output_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        # Create TileJSON
        tilejson = {
            "tilejson": "2.2.0",
            "name": "Andhra Pradesh MGTM - Vijayawada Master Plan",
            "description": "Master plan tiles for Vijayawada, Andhra Pradesh",
            "version": "1.0.0",
            "attribution": "MGTM, Government of Andhra Pradesh",
            "scheme": "xyz",
            "tiles": [
                "./{z}/{x}/{y}.png"
            ],
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
        center_lon = (bounds['west'] + bounds['east']) / 2
        center_lat = (bounds['south'] + bounds['north']) / 2
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
    <title>Vijayawada Master Plan Viewer</title>
    <link href="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css" rel="stylesheet" />
    <script src="https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
        .info {{
            position: fixed;
            top: 10px;
            right: 10px;
            background: white;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            z-index: 1;
            font-family: Arial, sans-serif;
            min-width: 280px;
        }}
        .info h3 {{ margin-top: 0; }}
        .feature-list {{
            margin: 10px 0;
            padding-left: 15px;
        }}
        .feature-list li {{
            margin: 3px 0;
            font-size: 14px;
        }}
        .zoom-info {{
            position: fixed;
            bottom: 10px;
            left: 10px;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            z-index: 1;
            font-family: monospace;
        }}
        .status {{
            position: fixed;
            bottom: 10px;
            right: 10px;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            z-index: 1;
            font-family: Arial, sans-serif;
            font-size: 12px;
        }}
        .opacity-control {{
            margin: 10px 0;
        }}
        .opacity-control label {{
            display: block;
            margin: 5px 0;
            font-size: 14px;
        }}
        .opacity-control input[type="range"] {{
            width: 100%;
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info">
        <h3>🏙️ Vijayawada Master Plan</h3>
        <p><strong>Dataset:</strong> Vijayawada Master Development Plan</p>
        <p><strong>Authority:</strong> MGTM, Andhra Pradesh</p>
        <p><strong>Zoom:</strong> {min_zoom}-{max_zoom}</p>
        <p><strong>Format:</strong> PNG (256x256)</p>
        <p><strong>Features:</strong></p>
        <ul class="feature-list">
            <li>Vijayawada City Master Plan</li>
            <li>Land Use Categories</li>
            <li>High Resolution Tiles</li>
            <li>Interactive Controls</li>
        </ul>
        <div class="opacity-control">
            <label for="opacity">Layer Opacity:</label>
            <input type="range" id="opacity" min="0" max="1" step="0.1" value="0.8">
            <span id="opacity-value">80%</span>
        </div>
        <small>Serve this folder via: python3 -m http.server 8002</small>
    </div>
    <div class="zoom-info" id="zoom-display">Zoom: 10</div>
    <div class="status" id="status">Loading...</div>
    <script>
        mapboxgl.accessToken = 'pk.eyJ1IjoiYXYxYWNyZSIsImEiOiJjbTJtZmdxN3owa2FzMmpyMjJ4OHV5MHhzIn0.FXpMd91JSER-r7LVpSZN-A';
        
        // Vijayawada bounds
        const vijayawadaBounds = [{bounds['west']}, {bounds['south']}, {bounds['east']}, {bounds['north']}];
        
        const map = new mapboxgl.Map({{
            container: 'map',
            style: 'mapbox://styles/mapbox/satellite-streets-v12',
            center: [{center_lon:.6f}, {center_lat:.6f}], // Vijayawada center
            zoom: 10
        }});

        map.addControl(new mapboxgl.NavigationControl(), 'top-left');
        map.addControl(new mapboxgl.ScaleControl());

        function updateZoom() {{
            document.getElementById('zoom-display').textContent = 'Zoom: ' + map.getZoom().toFixed(2);
        }}

        function updateStatus(message) {{
            document.getElementById('status').textContent = message;
        }}

        function updateOpacity(value) {{
            const opacity = parseFloat(value);
            const percentage = Math.round(opacity * 100);
            document.getElementById('opacity-value').textContent = percentage + '%';
            
            if (map.getLayer('vijayawada-masterplan-tiles')) {{
                map.setPaintProperty('vijayawada-masterplan-tiles', 'raster-opacity', opacity);
            }}
        }}

        map.on('zoomend', updateZoom);
        map.on('load', () => {{
            updateZoom();
            updateStatus('Map loaded');
            
            // Add Vijayawada master plan raster source for local PNG tiles
            const cacheBuster = Date.now();
            map.addSource('vijayawada-masterplan-tiles', {{
                type: 'raster',
                tiles: [`./${{z}}/${{x}}/${{y}}.png?v=${{cacheBuster}}`],
                tileSize: 256,
                minzoom: {min_zoom},
                maxzoom: {max_zoom},
                bounds: vijayawadaBounds
            }});

            map.addLayer({{
                id: 'vijayawada-masterplan-tiles',
                type: 'raster',
                source: 'vijayawada-masterplan-tiles',
                paint: {{ 
                    'raster-opacity': 0.8, 
                    'raster-resampling': 'nearest'  // Changed to nearest for sharper display
                }}
            }});

            // Fit to Vijayawada bounds
            map.fitBounds([vijayawadaBounds.slice(0, 2), vijayawadaBounds.slice(2, 4)]);
            updateStatus('Loaded Vijayawada master plan tiles');
        }});

        // Add event listener for opacity control
        document.getElementById('opacity').addEventListener('input', (e) => {{
            updateOpacity(e.target.value);
        }});
    </script>
</body>
</html>"""
        
        with open(self.output_dir / "viewer.html", "w") as f:
            f.write(html_content)
        
        logger.info("✅ Created supporting files: metadata.json, tilejson.json, viewer.html")

def main():
    """Main function with progress tracking"""
    import time
    
    logger.info("=" * 80)
    logger.info("Starting Optimized Vijayawada Master Plan tile generation")
    logger.info("=" * 80)
    
    start_time = time.time()
    
    # Initialize generator with optimal worker count
    # You can adjust num_workers based on your system
    generator = OptimizedVijayawadaTileGenerator(num_workers=None)  # Will auto-detect CPU cores
    
    # Generate tiles - adjust zoom levels based on needs
    total = generator.generate_tiles(min_zoom=4, max_zoom=18)
    
    elapsed_time = time.time() - start_time
    
    logger.info("=" * 80)
    logger.info(f"✅ Vijayawada Master Plan tile generation completed!")
    logger.info(f"✅ Total tiles generated: {total}")
    logger.info(f"⏱️  Time taken: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
    logger.info(f"📊 Average speed: {total/elapsed_time:.2f} tiles/second")
    logger.info("=" * 80)
    logger.info("\nTo view the tiles:")
    logger.info("  1. cd vijayawada_masterplan_tiles1")
    logger.info("  2. python3 -m http.server 8002")
    logger.info("  3. Open http://localhost:8002/viewer.html")

if __name__ == "__main__":
    main()