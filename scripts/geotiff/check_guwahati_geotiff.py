#!/usr/bin/env python3
"""
GeoTIFF Analysis Script for Guwahati Master Plan
Analyzes the structure, CRS, bounds, and color information of the GeoTIFF file
"""

import rasterio
import numpy as np
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_guwahati_geotiff(tiff_path):
    """Analyze Guwahati GeoTIFF file"""
    logger.info(f"Analyzing GeoTIFF: {tiff_path}")
    
    try:
        with rasterio.open(tiff_path) as src:
            logger.info(f"CRS: {src.crs}")
            logger.info(f"Bounds: {src.bounds}")
            logger.info(f"Shape: {src.shape} (height, width)")
            logger.info(f"Number of bands: {src.count}")
            logger.info(f"Data types: {src.dtypes}")
            logger.info(f"Color interpretation: {src.colorinterp}")
            logger.info(f"Transform:\n{src.transform}")
            logger.info(f"NoData values: {src.nodata}")
            
            total_pixels = src.shape[0] * src.shape[1]
            logger.info(f"Total pixels: {total_pixels:,}")
            
            # Analyze each band
            for i in range(1, src.count + 1):
                band = src.read(i)
                unique_values = np.unique(band)
                non_zero_pixels = np.sum(band > 0)
                logger.info(f"\nBand {i}:")
                logger.info(f"  Non-zero pixels: {non_zero_pixels:,}")
                logger.info(f"  Min value: {np.min(band)}")
                logger.info(f"  Max value: {np.max(band)}")
                logger.info(f"  Unique values: {len(unique_values)}")
                if len(unique_values) <= 10:
                    logger.info(f"  All unique values: {unique_values}")
                else:
                    logger.info(f"  Sample unique values: {unique_values[:10]}...")
            
            # Color analysis for RGBA files
            if src.count >= 4:
                logger.info(f"\n{'='*40}")
                logger.info("COLOR ANALYSIS")
                logger.info(f"{'='*40}")
                
                red = src.read(1)
                green = src.read(2)
                blue = src.read(3)
                alpha = src.read(4)
                
                # Create mask for non-transparent pixels
                mask = alpha > 0
                non_transparent_pixels = np.sum(mask)
                logger.info(f"Alpha channel present - analyzing {non_transparent_pixels:,} non-transparent pixels")
                
                if non_transparent_pixels > 0:
                    masked_red = red[mask]
                    masked_green = green[mask]
                    masked_blue = blue[mask]
                    
                    # Show some sample colors
                    sample_indices = np.random.choice(len(masked_red), min(10, len(masked_red)), replace=False)
                    logger.info(f"\nSample RGB colors:")
                    for i, idx in enumerate(sample_indices):
                        r, g, b = masked_red[idx], masked_green[idx], masked_blue[idx]
                        logger.info(f"  Color {i+1}: RGB({r}, {g}, {b}) = #{r:02x}{g:02x}{b:02x}")
            
            # Coordinate system analysis
            logger.info(f"\n{'='*40}")
            logger.info("COORDINATE SYSTEM ANALYSIS")
            logger.info(f"{'='*40}")
            
            logger.info(f"Source CRS: {src.crs}")
            
            # Convert bounds to WGS84 for reference
            from rasterio.warp import transform_bounds
            wgs84_bounds = transform_bounds(src.crs, 'EPSG:4326', *src.bounds)
            logger.info(f"WGS84 bounds: {wgs84_bounds}")
            
            # Calculate center and approximate area
            center_lon = (wgs84_bounds[0] + wgs84_bounds[2]) / 2
            center_lat = (wgs84_bounds[1] + wgs84_bounds[3]) / 2
            logger.info(f"WGS84 center: ({center_lon:.6f}, {center_lat:.6f})")
            
            # Approximate area calculation
            from geopy.distance import geodesic
            width = geodesic((center_lat, wgs84_bounds[0]), (center_lat, wgs84_bounds[2])).kilometers
            height = geodesic((wgs84_bounds[1], center_lon), (wgs84_bounds[3], center_lon)).kilometers
            area_km2 = width * height
            logger.info(f"Approximate area: {area_km2:.2f} km²")
            
    except rasterio.errors.RasterioIOError as e:
        logger.error(f"Error opening or reading GeoTIFF file {tiff_path}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

def main():
    """Main function"""
    guwahati_tif_path = Path("data/assam/guwahati")
    
    # Find TIF files in the directory
    tif_files = list(guwahati_tif_path.glob("*.tif")) + list(guwahati_tif_path.glob("*.tiff"))
    
    if not tif_files:
        logger.error(f"No TIF files found in {guwahati_tif_path}")
        return
    
    logger.info(f"Found {len(tif_files)} TIF file(s):")
    for tif_file in tif_files:
        logger.info(f"  - {tif_file.name}")
    
    # Analyze each TIF file
    for tif_file in tif_files:
        logger.info(f"\n{'='*60}")
        logger.info(f"GEOGRAPHIC ANALYSIS: {tif_file.name}")
        logger.info(f"{'='*60}")
        check_guwahati_geotiff(tif_file)
    
    logger.info(f"\n{'='*60}")
    logger.info("ANALYSIS COMPLETE")
    logger.info(f"{'='*60}")

if __name__ == "__main__":
    main()
