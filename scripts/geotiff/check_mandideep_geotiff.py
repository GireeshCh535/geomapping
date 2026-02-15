#!/usr/bin/env python3
"""
GeoTIFF Analysis Script for Mandideep Master Plan
Analyzes the structure, CRS, bounds, and color information of the GeoTIFF file
"""

import rasterio
import numpy as np
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_mandideep_geotiff(tiff_path):
    """Analyze Mandideep GeoTIFF file"""
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
                logger.info("RGBA COLOR ANALYSIS")
                logger.info(f"{'='*40}")
                
                # Read all bands
                r_band = src.read(1)
                g_band = src.read(2)
                b_band = src.read(3)
                a_band = src.read(4)
                
                # Find non-transparent pixels
                non_transparent = a_band > 0
                non_transparent_count = np.sum(non_transparent)
                logger.info(f"Non-transparent pixels: {non_transparent_count:,}")
                
                if non_transparent_count > 0:
                    # Extract RGB values for non-transparent pixels
                    r_values = r_band[non_transparent]
                    g_values = g_band[non_transparent]
                    b_values = b_band[non_transparent]
                    
                    # Find unique RGB combinations
                    rgb_combinations = np.column_stack([r_values, g_values, b_values])
                    unique_rgb = np.unique(rgb_combinations, axis=0)
                    
                    logger.info(f"Unique RGB combinations: {len(unique_rgb)}")
                    
                    if len(unique_rgb) <= 20:
                        logger.info("All RGB combinations:")
                        for i, rgb in enumerate(unique_rgb):
                            logger.info(f"  {i+1:2d}. RGB{rgb}")
                    else:
                        logger.info("Sample RGB combinations:")
                        for i, rgb in enumerate(unique_rgb[:20]):
                            logger.info(f"  {i+1:2d}. RGB{rgb}")
                        logger.info(f"  ... and {len(unique_rgb) - 20} more")
                    
                    # Color statistics
                    logger.info(f"\nColor Statistics:")
                    logger.info(f"  Red   - Min: {np.min(r_values)}, Max: {np.max(r_values)}, Mean: {np.mean(r_values):.1f}")
                    logger.info(f"  Green - Min: {np.min(g_values)}, Max: {np.max(g_values)}, Mean: {np.mean(g_values):.1f}")
                    logger.info(f"  Blue  - Min: {np.min(b_values)}, Max: {np.max(b_values)}, Mean: {np.mean(b_values):.1f}")
            
            # File size analysis
            file_size = Path(tiff_path).stat().st_size
            logger.info(f"\nFile size: {file_size / (1024*1024):.2f} MB")
            logger.info(f"Compression ratio: {file_size / (total_pixels * src.count * 4):.2f}x")
            
    except Exception as e:
        logger.error(f"Error analyzing GeoTIFF: {e}")

def main():
    """Main function to analyze Mandideep GeoTIFF"""
    tiff_path = "data/madhya-pradesh/mandideep/mandideep_masterplan/MandideepLandusePlan_clipped.tif"
    
    if not Path(tiff_path).exists():
        logger.error(f"GeoTIFF file not found: {tiff_path}")
        return
    
    check_mandideep_geotiff(tiff_path)

if __name__ == "__main__":
    main()
