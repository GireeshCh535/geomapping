#!/usr/bin/env python3
"""
Dedicated script to generate high-quality PNG tiles from Tirupati Masterplan RGBA GeoTIFF
Extracts actual colors from the GeoTIFF for accurate tile generation
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TirupatiRGBATileGenerator:
    """
    Generate high-quality PNG tiles from Tirupati Masterplan RGBA GeoTIFF
    """
    
    def __init__(self, data_dir: str = "data/andhra_pradesh/tirupati/tirupati_masterplan",
                 output_dir: str = "tirupati_masterplan_tiles"):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info("Tirupati RGBA Tile Generator initialized")
    
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
    
    def generate_tiles(self, min_zoom=8, max_zoom=16):
        """Generate PNG tiles for Tirupati Masterplan"""
        # Find the GeoTIFF file
        geotiff_files = list(self.data_dir.glob("*.tif"))
        if not geotiff_files:
            logger.error(f"No GeoTIFF files found in {self.data_dir}")
            return
        
        geotiff_path = geotiff_files[0]
        logger.info(f"Processing GeoTIFF: {geotiff_path}")
        
        # Reproject GeoTIFF to WGS84
        wgs84_data_r, wgs84_data_g, wgs84_data_b, wgs84_data_a, wgs84_bounds, wgs84_transform = self.reproject_geotiff_to_wgs84(geotiff_path)
        
        # Calculate tile bounds
        min_tile = mercantile.tile(wgs84_bounds['west'], wgs84_bounds['south'], min_zoom)
        max_tile = mercantile.tile(wgs84_bounds['east'], wgs84_bounds['north'], max_zoom)
        
        total_tiles = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            logger.info(f"Processing zoom level {zoom}")
            
            # Recalculate tile bounds for this zoom level
            min_tile = mercantile.tile(wgs84_bounds['west'], wgs84_bounds['south'], zoom)
            max_tile = mercantile.tile(wgs84_bounds['east'], wgs84_bounds['north'], zoom)
            
            zoom_dir = self.output_dir / str(zoom)
            zoom_dir.mkdir(exist_ok=True)
            
            for x in range(min_tile.x, max_tile.x + 1):
                x_dir = zoom_dir / str(x)
                x_dir.mkdir(exist_ok=True)
                
                for y in range(max_tile.y, min_tile.y + 1):
                    tile_path = x_dir / f"{y}.png"
                    
                    if self.generate_single_tile(wgs84_data_r, wgs84_data_g, wgs84_data_b, wgs84_data_a, wgs84_bounds, wgs84_transform, zoom, x, y, tile_path):
                        total_tiles += 1
                    
                    # Log progress every 100 tiles
                    if total_tiles % 100 == 0:
                        logger.info(f"Generated {total_tiles} tiles so far...")
        
        logger.info(f"Generated {total_tiles} PNG tiles for Tirupati Masterplan")
        
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
            self.render_data_to_tile(wgs84_data_r, wgs84_data_g, wgs84_data_b, wgs84_data_a, wgs84_bounds, wgs84_transform, tile_bounds, draw)
            
            # Save the tile
            img.save(tile_path, 'PNG')
            return True
            
        except Exception as e:
            logger.error(f"Error generating tile {zoom}/{x}/{y}: {e}")
            return False
    
    def render_data_to_tile(self, wgs84_data_r, wgs84_data_g, wgs84_data_b, wgs84_data_a, wgs84_bounds, wgs84_transform, tile_bounds, draw):
        """Render WGS84 data to a tile"""
        try:
            # Check if tile bounds intersect with data bounds
            if (tile_bounds.east < wgs84_bounds['west'] or 
                tile_bounds.west > wgs84_bounds['east'] or 
                tile_bounds.south > wgs84_bounds['north'] or 
                tile_bounds.north < wgs84_bounds['south']):
                return
            
            # Get data dimensions
            height, width = wgs84_data_r.shape
            
            # Sample points in the tile (every pixel for high quality)
            for tile_y in range(0, 256, 1):
                for tile_x in range(0, 256, 1):
                    # Convert tile pixel to WGS84 coordinates
                    lon = tile_bounds.west + (tile_bounds.east - tile_bounds.west) * tile_x / 256
                    lat = tile_bounds.north - (tile_bounds.north - tile_bounds.south) * tile_y / 256
                    
                    # Convert WGS84 coordinates to data pixel coordinates
                    data_x, data_y = self.wgs84_to_data_pixel(lon, lat, wgs84_bounds, wgs84_transform, width, height)
                    
                    if 0 <= data_x < width and 0 <= data_y < height:
                        r = int(wgs84_data_r[data_y, data_x])
                        g = int(wgs84_data_g[data_y, data_x])
                        b = int(wgs84_data_b[data_y, data_x])
                        a = int(wgs84_data_a[data_y, data_x])
                        
                        # Only draw pixels that are not transparent
                        # FIXED: Preserve ALL colors including black (0,0,0) - only check alpha
                        if a > 0:
                            # Use the actual RGB values from the GeoTIFF
                            rgb_color = (r, g, b)
                            
                            # Draw the pixel
                            draw.point((tile_x, tile_y), fill=rgb_color)
        
        except Exception as e:
            logger.error(f"Error rendering data to tile: {e}")
    
    def wgs84_to_data_pixel(self, lon, lat, wgs84_bounds, wgs84_transform, width, height):
        """Convert WGS84 coordinates to data pixel coordinates"""
        # Use the inverse transform to get pixel coordinates
        from rasterio.transform import rowcol
        
        row, col = rowcol(wgs84_transform, lon, lat)
        return int(col), int(row)
    
    def create_supporting_files(self, bounds, min_zoom, max_zoom):
        """Create supporting files for the tile set"""
        logger.info("Creating supporting files...")
        
        # Create Mapbox style JSON
        style_json = {
            "version": 8,
            "name": "Andhra Pradesh - Tirupati Masterplan",
            "sources": {
                "tirupati-masterplan": {
                    "type": "raster",
                    "tiles": [
                        "https://d17yosovmfjm4.cloudfront.net/andhra-pradesh/tirupati_masterplan/{z}/{x}/{y}.png"
                    ],
                    "tileSize": 256
                }
            },
            "layers": [
                {
                    "id": "tirupati-masterplan-layer",
                    "type": "raster",
                    "source": "tirupati-masterplan",
                    "paint": {
                        "raster-opacity": 0.8
                    }
                }
            ]
        }
        
        with open(self.output_dir / "style.json", "w") as f:
            import json
            json.dump(style_json, f, indent=2)
        
        # Create TileJSON
        tilejson = {
            "tilejson": "2.2.0",
            "name": "Andhra Pradesh - Tirupati Masterplan",
            "description": "Master plan tiles for Tirupati, Andhra Pradesh",
            "version": "1.0.0",
            "attribution": "Tirupati Development Authority",
            "template": "",
            "legend": "",
            "scheme": "xyz",
            "tiles": [
                "https://d17yosovmfjm4.cloudfront.net/andhra-pradesh/tirupati_masterplan/{z}/{x}/{y}.png"
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
            import json
            json.dump(tilejson, f, indent=2)
        
        # Create HTML viewer
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Andhra Pradesh - Tirupati Masterplan</title>
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
                    "tirupati-masterplan": {{
                        "type": "raster",
                        "tiles": [
                            "https://d17yosovmfjm4.cloudfront.net/andhra-pradesh/tirupati_masterplan/{{z}}/{{x}}/{{y}}.png"
                        ],
                        "tileSize": 256
                    }}
                }},
                "layers": [
                    {{
                        "id": "tirupati-masterplan-layer",
                        "type": "raster",
                        "source": "tirupati-masterplan",
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
    """Main function"""
    logger.info("Starting Tirupati RGBA Masterplan tile generation")
    
    # Initialize generator
    generator = TirupatiRGBATileGenerator()
    
    # Generate tiles with higher zoom levels for better quality
    generator.generate_tiles(min_zoom=5, max_zoom=18)
    
    logger.info("Tirupati RGBA Masterplan tile generation completed!")

if __name__ == "__main__":
    main()
