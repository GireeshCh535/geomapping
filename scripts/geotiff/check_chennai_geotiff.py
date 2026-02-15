#!/usr/bin/env python3
"""
Script to analyze Chennai master plan GeoTIFF files
Similar to check_chikkaballapura_geotiff.py but for Chennai data
"""

import rasterio
import numpy as np
import os
from pathlib import Path

def analyze_geotiff(geotiff_path):
    """Analyze a single GeoTIFF file"""
    print(f"\n{'='*80}")
    print(f"ANALYZING: {geotiff_path}")
    print(f"{'='*80}")
    
    try:
        with rasterio.open(geotiff_path) as src:
            print(f"Number of bands: {src.count}")
            print(f"Color interpretation: {src.colorinterp}")
            print(f"Data shape: {src.shape}")
            print(f"Data type: {src.dtypes}")
            print(f"CRS: {src.crs}")
            print(f"Bounds: {src.bounds}")
            print(f"Transform: {src.transform}")
            
            # Try different window locations to find data
            windows_to_try = [
                rasterio.windows.Window(0, 0, 1000, 1000),
                rasterio.windows.Window(5000, 5000, 1000, 1000),
                rasterio.windows.Window(10000, 10000, 1000, 1000),
                rasterio.windows.Window(15000, 15000, 1000, 1000),
                rasterio.windows.Window(20000, 20000, 1000, 1000),
                rasterio.windows.Window(25000, 25000, 1000, 1000),
            ]
            
            for i, window in enumerate(windows_to_try):
                print(f"\n--- Window {i+1}: {window} ---")
                try:
                    data = src.read(window=window)
                    print(f"Sample data shape: {data.shape}")
                    
                    # Find non-zero pixels in the sample
                    if src.count == 4:  # RGBA
                        non_zero_mask = (data[0] > 0) | (data[1] > 0) | (data[2] > 0)
                        non_zero_count = np.sum(non_zero_mask)
                        print(f"Non-zero pixels in sample: {non_zero_count}")
                        
                        if non_zero_count > 0:
                            non_zero_indices = np.where(non_zero_mask)
                            
                            # Sample some non-zero pixels to see the colors
                            print("Sample non-zero pixel values (R,G,B,A):")
                            for j in range(min(10, len(non_zero_indices[0]))):
                                y, x = non_zero_indices[0][j], non_zero_indices[1][j]
                                r, g, b, a = data[:, y, x]
                                print(f"Pixel ({y}, {x}): R={r}, G={g}, B={b}, A={a}")
                            
                            # Check unique RGB combinations in sample
                            print("Unique RGB combinations in sample (first 20):")
                            unique_combinations = set()
                            for j in range(min(500, len(non_zero_indices[0]))):
                                y, x = non_zero_indices[0][j], non_zero_indices[1][j]
                                r, g, b = data[0, y, x], data[1, y, x], data[2, y, x]
                                unique_combinations.add((r, g, b))
                                if len(unique_combinations) >= 20:
                                    break
                            
                            for rgb in sorted(unique_combinations):
                                print(f"RGB{rgb}")
                            break
                        else:
                            print("No non-zero pixels found in this window")
                    
                    elif src.count == 3:  # RGB
                        non_zero_mask = (data[0] > 0) | (data[1] > 0) | (data[2] > 0)
                        non_zero_count = np.sum(non_zero_mask)
                        print(f"Non-zero pixels in sample: {non_zero_count}")
                        
                        if non_zero_count > 0:
                            non_zero_indices = np.where(non_zero_mask)
                            
                            # Sample some non-zero pixels to see the colors
                            print("Sample non-zero pixel values (R,G,B):")
                            for j in range(min(10, len(non_zero_indices[0]))):
                                y, x = non_zero_indices[0][j], non_zero_indices[1][j]
                                r, g, b = data[:, y, x]
                                print(f"Pixel ({y}, {x}): R={r}, G={g}, B={b}")
                            
                            # Check unique RGB combinations in sample
                            print("Unique RGB combinations in sample (first 20):")
                            unique_combinations = set()
                            for j in range(min(500, len(non_zero_indices[0]))):
                                y, x = non_zero_indices[0][j], non_zero_indices[1][j]
                                r, g, b = data[0, y, x], data[1, y, x], data[2, y, x]
                                unique_combinations.add((r, g, b))
                                if len(unique_combinations) >= 20:
                                    break
                            
                            for rgb in sorted(unique_combinations):
                                print(f"RGB{rgb}")
                            break
                        else:
                            print("No non-zero pixels found in this window")
                    
                    elif src.count == 1:  # Single band
                        non_zero_mask = data[0] > 0
                        non_zero_count = np.sum(non_zero_mask)
                        print(f"Non-zero pixels in sample: {non_zero_count}")
                        
                        if non_zero_count > 0:
                            non_zero_indices = np.where(non_zero_mask)
                            
                            # Sample some non-zero pixels to see the values
                            print("Sample non-zero pixel values:")
                            for j in range(min(10, len(non_zero_indices[0]))):
                                y, x = non_zero_indices[0][j], non_zero_indices[1][j]
                                value = data[0, y, x]
                                print(f"Pixel ({y}, {x}): Value={value}")
                            
                            # Check unique values in sample
                            unique_values = np.unique(data[0])
                            print(f"Unique values in sample: {unique_values[:20]}...")
                            break
                        else:
                            print("No non-zero pixels found in this window")
                            
                except Exception as e:
                    print(f"Error reading window: {e}")
            
            # Check unique values in each band (sample)
            print(f"\nUnique values in each band (sample):")
            for band_idx in range(min(src.count, 4)):  # Limit to first 4 bands
                unique_values = np.unique(data[band_idx])
                print(f"Band {band_idx + 1}: {unique_values[:20]}...")
            
            # Check if it's a palette image
            if hasattr(src, 'colormap') and src.colormap(1):
                print(f"\nColormap found for band 1:")
                colormap = src.colormap(1)
                print(f"Colormap entries: {len(colormap)}")
                # Show first 10 colormap entries
                for i, (key, value) in enumerate(list(colormap.items())[:10]):
                    print(f"  {key}: {value}")
                if len(colormap) > 10:
                    print(f"  ... and {len(colormap) - 10} more entries")
            
    except Exception as e:
        print(f"Error analyzing {geotiff_path}: {e}")

def main():
    """Main function to analyze all Chennai GeoTIFF files"""
    print("Chennai Master Plan GeoTIFF Analysis")
    print("="*50)
    
    # Define the data directory
    data_dir = Path("data/chennai/chennai_master_plan")
    
    if not data_dir.exists():
        print(f"Error: Directory {data_dir} does not exist")
        return
    
    # Find all TIFF files
    tiff_files = list(data_dir.glob("*.tif")) + list(data_dir.glob("*.tiff"))
    
    if not tiff_files:
        print(f"No TIFF files found in {data_dir}")
        return
    
    print(f"Found {len(tiff_files)} TIFF files:")
    for tiff_file in tiff_files:
        print(f"  - {tiff_file.name}")
    
    # Analyze each TIFF file
    for tiff_file in tiff_files:
        analyze_geotiff(tiff_file)
    
    print(f"\n{'='*80}")
    print("Analysis completed!")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()

