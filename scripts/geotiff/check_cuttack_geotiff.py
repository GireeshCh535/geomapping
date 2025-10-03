#!/usr/bin/env python3
"""
Script to analyze Cuttack master plan GeoTIFF file
"""

import rasterio
import numpy as np
from pathlib import Path

def analyze_cuttack_geotiff():
    """Detailed analysis of Cuttack GeoTIFF"""
    geotiff_path = "data/odisha/cuttack/cuttack_master_plan/Cuttack_Clipped.tif"
    
    print(f"Analyzing: {geotiff_path}")
    print("="*80)
    
    try:
        with rasterio.open(geotiff_path) as src:
            print(f"File: {geotiff_path}")
            print(f"CRS: {src.crs}")
            print(f"Bounds: {src.bounds}")
            print(f"Shape: {src.shape} (height, width)")
            print(f"Number of bands: {src.count}")
            print(f"Data types: {src.dtypes}")
            print(f"Color interpretation: {src.colorinterp}")
            print(f"Transform: {src.transform}")
            print(f"NoData values: {src.nodata}")
            
            # Calculate file size
            height, width = src.shape
            total_pixels = height * width
            print(f"Total pixels: {total_pixels:,}")
            
            # Read a sample to check data
            print("\nReading sample data from center...")
            center_row = height // 2
            center_col = width // 2
            sample_window = rasterio.windows.Window(
                max(0, center_col - 500), 
                max(0, center_row - 500), 
                min(1000, width), 
                min(1000, height)
            )
            
            try:
                sample_data = src.read(window=sample_window)
                print(f"Sample data shape: {sample_data.shape}")
                
                # Check for non-zero pixels
                for band_idx in range(src.count):
                    band_data = sample_data[band_idx]
                    non_zero = np.count_nonzero(band_data)
                    unique_vals = len(np.unique(band_data))
                    print(f"\nBand {band_idx + 1}:")
                    print(f"  Non-zero pixels: {non_zero:,}")
                    print(f"  Min value: {band_data.min()}")
                    print(f"  Max value: {band_data.max()}")
                    print(f"  Unique values: {unique_vals}")
                    
                    if non_zero > 0:
                        non_zero_vals = band_data[band_data > 0]
                        print(f"  Sample non-zero values: {non_zero_vals[:10]}")
                
                # If RGBA, check color combinations
                if src.count >= 3:
                    print("\nSample RGB combinations:")
                    non_zero_mask = (sample_data[0] > 0) | (sample_data[1] > 0) | (sample_data[2] > 0)
                    if np.any(non_zero_mask):
                        non_zero_indices = np.where(non_zero_mask)
                        print(f"Non-zero pixels in sample: {len(non_zero_indices[0])}")
                        
                        # Sample some colors
                        unique_colors = set()
                        for i in range(min(100, len(non_zero_indices[0]))):
                            y, x = non_zero_indices[0][i], non_zero_indices[1][i]
                            if src.count >= 4:
                                r, g, b, a = sample_data[0, y, x], sample_data[1, y, x], sample_data[2, y, x], sample_data[3, y, x]
                                unique_colors.add((r, g, b, a))
                            else:
                                r, g, b = sample_data[0, y, x], sample_data[1, y, x], sample_data[2, y, x]
                                unique_colors.add((r, g, b))
                        
                        print(f"\nUnique color combinations (first 20):")
                        for color in sorted(unique_colors)[:20]:
                            if len(color) == 4:
                                print(f"  RGBA{color}")
                            else:
                                print(f"  RGB{color}")
            
            except Exception as e:
                print(f"Error reading sample: {e}")
            
            # Check for colormap
            try:
                if hasattr(src, 'colormap') and src.colormap(1):
                    colormap = src.colormap(1)
                    print(f"\nColormap found with {len(colormap)} entries")
                    print("Sample colormap entries (first 10):")
                    for idx, (value, color) in enumerate(list(colormap.items())[:10]):
                        print(f"  Value {value}: RGBA{color}")
                else:
                    print("\nNo colormap found (Direct RGBA/RGB data)")
            except:
                print("\nCould not check for colormap")
    
    except Exception as e:
        print(f"Error analyzing file: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_cuttack_geotiff()

