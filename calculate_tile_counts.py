#!/usr/bin/env python3
"""
Calculate tile counts for each zoom level for a GeoTIFF file.
"""

import sys
from pathlib import Path
import rasterio
from rasterio.warp import calculate_default_transform
import mercantile

def calculate_tile_counts(geotiff_path, min_zoom=8, max_zoom=16):
    """Calculate tile counts for each zoom level."""
    
    geotiff_path = Path(geotiff_path)
    if not geotiff_path.exists():
        print(f"Error: File not found: {geotiff_path}")
        return
    
    print(f"Analyzing: {geotiff_path}")
    print(f"Zoom range: {min_zoom} to {max_zoom}\n")
    
    # Open and reproject to WGS84 to get bounds
    with rasterio.open(geotiff_path) as src:
        print(f"Source CRS: {src.crs}")
        print(f"Source size: {src.width} x {src.height}")
        print(f"Source bounds: {src.bounds}")
        
        transform, width, height = calculate_default_transform(
            src.crs,
            "EPSG:4326",
            src.width,
            src.height,
            left=src.bounds.left,
            bottom=src.bounds.bottom,
            right=src.bounds.right,
            top=src.bounds.top,
        )
        
        # Calculate WGS84 bounds
        wgs84_bounds = {
            "west": transform[2],
            "south": transform[5] + height * transform[4],
            "east": transform[2] + width * transform[0],
            "north": transform[5],
        }
        
        print(f"\nWGS84 bounds:")
        print(f"  West:  {wgs84_bounds['west']:.6f}")
        print(f"  South: {wgs84_bounds['south']:.6f}")
        print(f"  East:  {wgs84_bounds['east']:.6f}")
        print(f"  North: {wgs84_bounds['north']:.6f}")
        print(f"\n{'Zoom':<6} {'Min Tile':<20} {'Max Tile':<20} {'X Range':<12} {'Y Range':<12} {'Total Tiles':<12}")
        print("-" * 90)
        
        total_all_zooms = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            # Calculate tile bounds (same logic as threaded_rgba_tile_generator.py)
            min_tile = mercantile.tile(
                wgs84_bounds["west"], wgs84_bounds["south"], zoom
            )
            max_tile = mercantile.tile(
                wgs84_bounds["east"], wgs84_bounds["north"], zoom
            )
            
            # Calculate tile counts
            x_range = max_tile.x - min_tile.x + 1
            y_range = min_tile.y - max_tile.y + 1  # Note: Y is inverted
            total_tiles = x_range * y_range
            
            total_all_zooms += total_tiles
            
            min_tile_str = f"({min_tile.x},{min_tile.y})"
            max_tile_str = f"({max_tile.x},{max_tile.y})"
            print(f"{zoom:<6} {min_tile_str:<20} {max_tile_str:<20} {x_range:<12} {y_range:<12} {total_tiles:<12}")
        
        print("-" * 90)
        print(f"{'TOTAL':<6} {'':<20} {'':<20} {'':<12} {'':<12} {total_all_zooms:<12}")

if __name__ == "__main__":
    geotiff_path = "tif_files/noida_masterplan_zoom16.tif"
    if len(sys.argv) > 1:
        geotiff_path = sys.argv[1]
    
    min_zoom = 8
    max_zoom = 16
    if len(sys.argv) > 2:
        min_zoom = int(sys.argv[2])
    if len(sys.argv) > 3:
        max_zoom = int(sys.argv[3])
    
    calculate_tile_counts(geotiff_path, min_zoom, max_zoom)

