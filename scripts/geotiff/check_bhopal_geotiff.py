#!/usr/bin/env python3
"""
Analyze Bhopal Land Use Plan GeoTIFF to extract metadata, CRS, bounds, and band information
"""

import os
import sys
import numpy as np
from pathlib import Path
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_geotiff(tiff_path):
    """Analyze GeoTIFF file and extract comprehensive information"""
    logger.info(f"Analyzing GeoTIFF: {tiff_path}")
    
    with rasterio.open(tiff_path) as src:
        print(f"\n{'='*60}")
        print(f"GEOGRAPHIC ANALYSIS: {Path(tiff_path).name}")
        print(f"{'='*60}")
        
        # Basic file information
        print(f"File: {tiff_path}")
        print(f"CRS: {src.crs}")
        print(f"Bounds: {src.bounds}")
        print(f"Shape: {src.shape} (height, width)")
        print(f"Number of bands: {src.count}")
        print(f"Data types: {src.dtypes}")
        print(f"Color interpretation: {src.colorinterp}")
        print(f"Transform: | {src.transform[0]:.2f}, {src.transform[1]:.2f}, {src.transform[2]:.2f}|")
        print(f"          | {src.transform[3]:.2f}, {src.transform[4]:.2f}, {src.transform[5]:.2f}|")
        print(f"          | {src.transform[6]:.2f}, {src.transform[7]:.2f}, {src.transform[8]:.2f}|")
        print(f"NoData values: {src.nodatavals}")
        print(f"Total pixels: {src.width * src.height:,}")
        
        # Band analysis
        print(f"\n{'='*40}")
        print("BAND ANALYSIS")
        print(f"{'='*40}")
        
        for band_idx in range(1, src.count + 1):
            band_data = src.read(band_idx)
            print(f"\nBand {band_idx}:")
            print(f"  Shape: {band_data.shape}")
            print(f"  Data type: {band_data.dtype}")
            print(f"  Min value: {band_data.min()}")
            print(f"  Max value: {band_data.max()}")
            print(f"  Unique values: {len(np.unique(band_data))}")
            
            # Sample some non-zero values
            non_zero_mask = band_data > 0
            if non_zero_mask.any():
                non_zero_values = band_data[non_zero_mask]
                print(f"  Non-zero pixels: {len(non_zero_values):,}")
                print(f"  Sample non-zero values: {non_zero_values[:10].tolist()}")
            else:
                print(f"  Non-zero pixels: 0")
        
        # Color analysis for multi-band images
        if src.count >= 3:
            print(f"\n{'='*40}")
            print("COLOR ANALYSIS")
            print(f"{'='*40}")
            
            # Read RGB bands
            red = src.read(1)
            green = src.read(2)
            blue = src.read(3)
            
            # Create a mask for non-transparent pixels
            if src.count == 4:
                alpha = src.read(4)
                mask = alpha > 0
                print(f"Alpha channel present - analyzing {mask.sum():,} non-transparent pixels")
            else:
                # For RGB images, consider all pixels
                mask = np.ones(red.shape, dtype=bool)
                print(f"RGB image - analyzing {mask.sum():,} pixels")
            
            if mask.any():
                # Sample some pixel colors
                masked_red = red[mask]
                masked_green = green[mask]
                masked_blue = blue[mask]
                
                # Show some sample colors
                sample_indices = np.random.choice(len(masked_red), min(10, len(masked_red)), replace=False)
                print(f"\nSample RGB colors:")
                for i, idx in enumerate(sample_indices):
                    r, g, b = masked_red[idx], masked_green[idx], masked_blue[idx]
                    print(f"  Color {i+1}: RGB({r}, {g}, {b}) = #{r:02x}{g:02x}{b:02x}")
        
        # Coordinate system analysis
        print(f"\n{'='*40}")
        print("COORDINATE SYSTEM ANALYSIS")
        print(f"{'='*40}")
        
        if src.crs and src.crs != 'EPSG:4326':
            print(f"Source CRS: {src.crs}")
            
            # Calculate transform to WGS84
            transform, width, height = calculate_default_transform(
                src.crs, 'EPSG:4326', src.width, src.height,
                left=src.bounds.left, bottom=src.bounds.bottom,
                right=src.bounds.right, top=src.bounds.top
            )
            
            # Calculate WGS84 bounds
            wgs84_bounds = {
                'west': transform[2],
                'south': transform[5] + height * transform[4],
                'east': transform[2] + width * transform[0],
                'north': transform[5]
            }
            
            print(f"WGS84 bounds: {wgs84_bounds}")
            print(f"WGS84 center: ({(wgs84_bounds['west'] + wgs84_bounds['east']) / 2:.6f}, {(wgs84_bounds['south'] + wgs84_bounds['north']) / 2:.6f})")
            
            # Calculate approximate area in square kilometers
            lat_center = (wgs84_bounds['south'] + wgs84_bounds['north']) / 2
            lon_span = wgs84_bounds['east'] - wgs84_bounds['west']
            lat_span = wgs84_bounds['north'] - wgs84_bounds['south']
            
            # Approximate conversion to km (rough estimation)
            km_per_degree_lat = 111.0
            km_per_degree_lon = 111.0 * np.cos(np.radians(lat_center))
            
            area_km2 = (lon_span * km_per_degree_lon) * (lat_span * km_per_degree_lat)
            print(f"Approximate area: {area_km2:.2f} km²")
        
        print(f"\n{'='*60}")
        print("ANALYSIS COMPLETE")
        print(f"{'='*60}")

def main():
    """Main function to analyze Bhopal GeoTIFF"""
    # Path to the Bhopal GeoTIFF
    tiff_path = "data/madhya-pradesh/bhopal/BhopalLandusePlan_clipped.tif"
    
    if not os.path.exists(tiff_path):
        logger.error(f"GeoTIFF file not found: {tiff_path}")
        return
    
    analyze_geotiff(tiff_path)

if __name__ == "__main__":
    main()
