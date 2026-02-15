#!/usr/bin/env python3
"""
Dedicated script to generate high-quality PNG tiles from Kakinada Master Plan RGBA GeoTIFF
Extracts actual colors from the GeoTIFF for accurate tile generation
Based on the anekal_rgba_tiles.py template
"""

import os
import sys
import math
import numpy as np
from pathlib import Path
import mercantile
from PIL import Image, ImageDraw
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing as mp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KakinadaMasterplanTileGenerator:
    """
    Generate high-quality PNG tiles from Kakinada Master Plan RGBA GeoTIFF
    """
    
    def __init__(self, data_dir: str = "data/andhra_pradesh/kakinada/master_plan",
                 output_dir: str = "kakinada_masterplan_tiles"):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info("Kakinada Master Plan Tile Generator initialized")
    
    def reproject_geotiff_to_wgs84(self, geotiff_path):
        """Reproject RGBA GeoTIFF to WGS84 and return the transformed data and bounds"""
        with rasterio.open(geotiff_path) as src:
            logger.info(f"Original CRS: {src.crs}")
            logger.info(f"Original bounds: {src.bounds}")
            logger.info(f"Original shape: {src.shape}")
            logger.info(f"Number of bands: {src.count}")
            
            # Calculate the transform to WGS84
            transform, width, height = calculate_default_transform(
                src.crs, 'EPSG:4326', src.width, src.height,
                left=src.bounds.left, bottom=src.bounds.bottom,
                right=src.bounds.right, top=src.bounds.top
            )
            
            # Create the destination arrays for RGBA
            destination_r = np.zeros((height, width), dtype=src.dtypes[0])
            destination_g = np.zeros((height, width), dtype=src.dtypes[0])
            destination_b = np.zeros((height, width), dtype=src.dtypes[0])
            destination_a = np.zeros((height, width), dtype=src.dtypes[0])
            
            # Reproject each band
            logger.info("Reprojecting Red band...")
            reproject(
                source=src.read(1),  # Red band
                destination=destination_r,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs='EPSG:4326',
                resampling=Resampling.nearest
            )
            
            logger.info("Reprojecting Green band...")
            reproject(
                source=src.read(2),  # Green band
                destination=destination_g,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs='EPSG:4326',
                resampling=Resampling.nearest
            )
            
            logger.info("Reprojecting Blue band...")
            reproject(
                source=src.read(3),  # Blue band
                destination=destination_b,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs='EPSG:4326',
                resampling=Resampling.nearest
            )
            
            logger.info("Reprojecting Alpha band...")
            reproject(
                source=src.read(4),  # Alpha band
                destination=destination_a,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs='EPSG:4326',
                resampling=Resampling.nearest
            )
            
            # Calculate WGS84 bounds
            wgs84_bounds = {
                'west': transform[2],
                'south': transform[5] + height * transform[4],
                'east': transform[2] + width * transform[0],
                'north': transform[5]
            }
            
            logger.info(f"WGS84 bounds: {wgs84_bounds}")
            logger.info(f"WGS84 data shape: {destination_r.shape}")
            
            return destination_r, destination_g, destination_b, destination_a, wgs84_bounds, transform
    
    def generate_tiles(self, min_zoom=4, max_zoom=18):
        """Generate PNG tiles for Kakinada Master Plan"""
        # Find the GeoTIFF file
        geotiff_path = self.data_dir / "Kakinada_Clipped.tif"
        
        if not geotiff_path.exists():
            logger.error(f"GeoTIFF file not found: {geotiff_path}")
            return 0
        
        logger.info(f"Processing GeoTIFF: {geotiff_path}")
        
        # Reproject GeoTIFF to WGS84
        logger.info("Starting reprojection to WGS84...")
        wgs84_data_r, wgs84_data_g, wgs84_data_b, wgs84_data_a, wgs84_bounds, wgs84_transform = self.reproject_geotiff_to_wgs84(geotiff_path)
        logger.info("Reprojection complete!")
        
        # Calculate tile bounds
        min_tile = mercantile.tile(wgs84_bounds['west'], wgs84_bounds['south'], min_zoom)
        max_tile = mercantile.tile(wgs84_bounds['east'], wgs84_bounds['north'], max_zoom)
        
        total_tiles = 0
        
        # OPTIMIZED: Use parallel processing for faster tile generation
        max_workers = min(mp.cpu_count(), 8)  # Limit to 8 workers to avoid memory issues
        logger.info(f"Using {max_workers} parallel workers for tile generation")
        
        for zoom in range(min_zoom, max_zoom + 1):
            logger.info(f"Processing zoom level {zoom}")
            
            # Recalculate tile bounds for this zoom level
            min_tile = mercantile.tile(wgs84_bounds['west'], wgs84_bounds['south'], zoom)
            max_tile = mercantile.tile(wgs84_bounds['east'], wgs84_bounds['north'], zoom)
            
            zoom_dir = self.output_dir / str(zoom)
            zoom_dir.mkdir(exist_ok=True)
            
            # Collect all tile coordinates for this zoom level
            tile_tasks = []
            for x in range(min_tile.x, max_tile.x + 1):
                x_dir = zoom_dir / str(x)
                x_dir.mkdir(exist_ok=True)
                
                for y in range(max_tile.y, min_tile.y + 1):
                    tile_path = x_dir / f"{y}.png"
                    tile_tasks.append((zoom, x, y, tile_path))
            
            # Process tiles in parallel
            tiles_in_zoom = 0
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tile generation tasks
                future_to_tile = {
                    executor.submit(
                        self.generate_single_tile, 
                        wgs84_data_r, wgs84_data_g, wgs84_data_b, wgs84_data_a,
                        wgs84_bounds, wgs84_transform, zoom, x, y, tile_path
                    ): (zoom, x, y) 
                    for zoom, x, y, tile_path in tile_tasks
                }
                
                # Process completed tiles
                for future in as_completed(future_to_tile):
                    zoom, x, y = future_to_tile[future]
                    try:
                        if future.result():
                            total_tiles += 1
                            tiles_in_zoom += 1
                    except Exception as e:
                        logger.error(f"Error generating tile {zoom}/{x}/{y}: {e}")
            
            logger.info(f"Zoom {zoom} complete: {tiles_in_zoom} tiles generated")
        
        logger.info(f"✅ Generated {total_tiles} PNG tiles for Kakinada Master Plan")
        
        # Create supporting files
        self.create_supporting_files(wgs84_bounds, min_zoom, max_zoom)
        
        return total_tiles
    
    def generate_single_tile(self, wgs84_data_r, wgs84_data_g, wgs84_data_b, wgs84_data_a, wgs84_bounds, wgs84_transform, zoom, x, y, tile_path):
        """Generate a single PNG tile"""
        try:
            # Get tile bounds
            tile_bounds = mercantile.bounds(x, y, zoom)
            
            # Create a blank tile
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Render the WGS84 data to this tile
            has_data = self.render_data_to_tile(wgs84_data_r, wgs84_data_g, wgs84_data_b, wgs84_data_a, wgs84_bounds, wgs84_transform, tile_bounds, draw)
            
            # Only save if tile has data
            if has_data:
                img.save(tile_path, 'PNG', optimize=True)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error generating tile {zoom}/{x}/{y}: {e}")
            return False
    
    def render_data_to_tile(self, wgs84_data_r, wgs84_data_g, wgs84_data_b, wgs84_data_a, wgs84_bounds, wgs84_transform, tile_bounds, draw):
        """Render WGS84 data to a tile - OPTIMIZED for speed"""
        try:
            # Check if tile bounds intersect with data bounds
            if (tile_bounds.east < wgs84_bounds['west'] or 
                tile_bounds.west > wgs84_bounds['east'] or 
                tile_bounds.south > wgs84_bounds['north'] or 
                tile_bounds.north < wgs84_bounds['south']):
                return False
            
            # Get data dimensions
            height, width = wgs84_data_r.shape
            
            # OPTIMIZED: Vectorized coordinate generation
            # Create coordinate grids for the entire tile at once
            tile_size = 256
            lon_coords = np.linspace(tile_bounds.west, tile_bounds.east, tile_size)
            lat_coords = np.linspace(tile_bounds.north, tile_bounds.south, tile_size)
            
            # Create meshgrids for vectorized processing
            lon_grid, lat_grid = np.meshgrid(lon_coords, lat_coords)
            
            # Flatten for batch processing
            lon_flat = lon_grid.flatten()
            lat_flat = lat_grid.flatten()
            
            # Convert all coordinates at once using vectorized operations
            from rasterio.transform import rowcol
            rows, cols = rowcol(wgs84_transform, lon_flat, lat_flat)
            
            # Reshape back to tile dimensions
            rows = rows.reshape(tile_size, tile_size)
            cols = cols.reshape(tile_size, tile_size)
            
            # Create mask for valid coordinates
            valid_mask = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
            
            # Initialize output arrays
            r_out = np.zeros((tile_size, tile_size), dtype=np.uint8)
            g_out = np.zeros((tile_size, tile_size), dtype=np.uint8)
            b_out = np.zeros((tile_size, tile_size), dtype=np.uint8)
            a_out = np.zeros((tile_size, tile_size), dtype=np.uint8)
            
            # Vectorized data extraction - much faster than pixel-by-pixel
            if np.any(valid_mask):
                # Extract data for all valid pixels at once
                valid_rows = rows[valid_mask]
                valid_cols = cols[valid_mask]
                
                r_out[valid_mask] = wgs84_data_r[valid_rows, valid_cols]
                g_out[valid_mask] = wgs84_data_g[valid_rows, valid_cols]
                b_out[valid_mask] = wgs84_data_b[valid_rows, valid_cols]
                a_out[valid_mask] = wgs84_data_a[valid_rows, valid_cols]
            
            # Create mask for pixels with actual content
            # FIXED: Preserve ALL colors including black (0,0,0) - only check alpha
            content_mask = (a_out > 0)
            
            if not np.any(content_mask):
                return False
            
            # OPTIMIZED: Draw only pixels with content using vectorized approach
            # Get coordinates of pixels with content
            content_y, content_x = np.where(content_mask)
            
            # Draw pixels in batches for better performance
            batch_size = 1000
            for i in range(0, len(content_y), batch_size):
                end_idx = min(i + batch_size, len(content_y))
                batch_y = content_y[i:end_idx]
                batch_x = content_x[i:end_idx]
                
                # Get colors for this batch
                batch_r = r_out[batch_y, batch_x]
                batch_g = g_out[batch_y, batch_x]
                batch_b = b_out[batch_y, batch_x]
                
                # Draw pixels in this batch
                for j in range(len(batch_y)):
                    y, x = batch_y[j], batch_x[j]
                    rgb_color = (int(batch_r[j]), int(batch_g[j]), int(batch_b[j]))
                    draw.point((x, y), fill=rgb_color)
            
            return True
        
        except Exception as e:
            logger.error(f"Error rendering data to tile: {e}")
            return False
    
    def wgs84_to_data_pixel(self, lon, lat, wgs84_bounds, wgs84_transform, width, height):
        """Convert WGS84 coordinates to data pixel coordinates"""
        # Use the inverse transform to get pixel coordinates
        from rasterio.transform import rowcol
        
        row, col = rowcol(wgs84_transform, lon, lat)
        return int(col), int(row)
    
    def create_supporting_files(self, bounds, min_zoom, max_zoom):
        """Create supporting files for the tile set"""
        logger.info("Creating supporting files...")
        
        # Create metadata JSON
        import json
        
        metadata = {
            "name": "Andhra Pradesh - Kakinada Master Plan",
            "description": "Master plan tiles for Kakinada, Andhra Pradesh",
            "state": "Andhra Pradesh",
            "city": "Kakinada",
            "authority": "Local Government",
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
            "name": "Andhra Pradesh - Kakinada Master Plan",
            "description": "Master plan tiles for Kakinada, Andhra Pradesh",
            "version": "1.0.0",
            "attribution": "Local Government, Andhra Pradesh",
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
        
        # Create HTML viewer with Mapbox styling
        center_lon = (bounds['west'] + bounds['east']) / 2
        center_lat = (bounds['south'] + bounds['north']) / 2
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
    <title>Kakinada Master Plan Viewer</title>
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
        <h3>🏙️ Kakinada Master Plan</h3>
        <p><strong>Dataset:</strong> Kakinada Master Development Plan</p>
        <p><strong>Authority:</strong> Local Government, Andhra Pradesh</p>
        <p><strong>Zoom:</strong> {min_zoom}-{max_zoom}</p>
        <p><strong>Format:</strong> PNG (256x256)</p>
        <p><strong>Features:</strong></p>
        <ul class="feature-list">
            <li>Kakinada City Master Plan</li>
            <li>Land Use Categories</li>
            <li>High Resolution Tiles</li>
            <li>Interactive Controls</li>
        </ul>
        <div class="opacity-control">
            <label for="opacity">Layer Opacity:</label>
            <input type="range" id="opacity" min="0" max="1" step="0.1" value="0.8">
            <span id="opacity-value">80%</span>
        </div>
        <small>Serve this folder via: python3 -m http.server 8003</small>
    </div>
    <div class="zoom-info" id="zoom-display">Zoom: 10</div>
    <div class="status" id="status">Loading...</div>
    <script>
        mapboxgl.accessToken = 'pk.eyJ1IjoiYXYxYWNyZSIsImEiOiJjbTJtZmdxN3owa2FzMmpyMjJ4OHV5MHhzIn0.FXpMd91JSER-r7LVpSZN-A';
        
        // Kakinada bounds
        const kakinadaBounds = [{bounds['west']}, {bounds['south']}, {bounds['east']}, {bounds['north']}];
        
        const map = new mapboxgl.Map({{
            container: 'map',
            style: 'mapbox://styles/mapbox/satellite-streets-v12',
            center: [{center_lon:.6f}, {center_lat:.6f}], // Kakinada center
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
            
            if (map.getLayer('kakinada-masterplan-tiles')) {{
                map.setPaintProperty('kakinada-masterplan-tiles', 'raster-opacity', opacity);
            }}
        }}

        map.on('zoomend', updateZoom);
        map.on('load', () => {{
            updateZoom();
            updateStatus('Map loaded');
            
            // Add Kakinada master plan raster source for local PNG tiles
            const cacheBuster = Date.now();
            map.addSource('kakinada-masterplan-tiles', {{
                type: 'raster',
                tiles: [`./${{z}}/${{x}}/${{y}}.png?v=${{cacheBuster}}`],
                tileSize: 256,
                minzoom: {min_zoom},
                maxzoom: {max_zoom},
                bounds: kakinadaBounds
            }});

            map.addLayer({{
                id: 'kakinada-masterplan-tiles',
                type: 'raster',
                source: 'kakinada-masterplan-tiles',
                paint: {{ 
                    'raster-opacity': 0.8, 
                    'raster-resampling': 'nearest' 
                }}
            }});

            // Fit to Kakinada bounds
            map.fitBounds([kakinadaBounds.slice(0, 2), kakinadaBounds.slice(2, 4)]);
            updateStatus('Loaded Kakinada master plan tiles');
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
    """Main function"""
    logger.info("=" * 80)
    logger.info("Starting Kakinada Master Plan tile generation")
    logger.info("=" * 80)
    
    # Initialize generator
    generator = KakinadaMasterplanTileGenerator()
    
    # Generate tiles - adjust zoom levels based on needs
    # Higher zoom levels = more detailed tiles but more storage
    total = generator.generate_tiles(min_zoom=4, max_zoom=18)
    
    logger.info("=" * 80)
    logger.info(f"✅ Kakinada Master Plan tile generation completed!")
    logger.info(f"✅ Total tiles generated: {total}")
    logger.info("=" * 80)
    logger.info("\nTo view the tiles:")
    logger.info("  1. cd kakinada_masterplan_tiles")
    logger.info("  2. python3 -m http.server 8003")
    logger.info("  3. Open http://localhost:8003/viewer.html")

if __name__ == "__main__":
    main()
