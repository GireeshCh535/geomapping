#!/usr/bin/env python3
"""
Detailed analysis of Coimbatore master plan GeoTIFF file
"""

import rasterio
import numpy as np
from pathlib import Path

def analyze_coimbatore_geotiff():
    """Detailed analysis of Coimbatore GeoTIFF"""
    geotiff_path = "data/tamil_nadu/coimbatore/coimbatore_master_plan/Coimbatore_MDP_Clipped.tif"
    
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
            
            # Calculate file size
            height, width = src.shape
            total_pixels = height * width
            print(f"Total pixels: {total_pixels:,}")
            
            # Try reading the entire file in chunks to find data
            print("\nScanning entire file for data...")
            
            # Read in smaller chunks to avoid memory issues
            chunk_size = 1000
            non_zero_count = 0
            sample_pixels = []
            
            for row_start in range(0, height, chunk_size):
                for col_start in range(0, width, chunk_size):
                    # Define chunk bounds
                    row_end = min(row_start + chunk_size, height)
                    col_end = min(col_start + chunk_size, width)
                    
                    window = rasterio.windows.Window(col_start, row_start, col_end - col_start, row_end - row_start)
                    
                    try:
                        data = src.read(window=window)
                        
                        # Check for non-zero pixels
                        if src.count >= 3:  # RGB or RGBA
                            non_zero_mask = (data[0] > 0) | (data[1] > 0) | (data[2] > 0)
                            chunk_non_zero = np.sum(non_zero_mask)
                            non_zero_count += chunk_non_zero
                            
                            if chunk_non_zero > 0 and len(sample_pixels) < 20:
                                # Sample some pixels from this chunk
                                non_zero_indices = np.where(non_zero_mask)
                                for i in range(min(5, len(non_zero_indices[0]))):
                                    y, x = non_zero_indices[0][i], non_zero_indices[1][i]
                                    pixel_data = data[:, y, x]
                                    sample_pixels.append({
                                        'global_row': row_start + y,
                                        'global_col': col_start + x,
                                        'values': pixel_data.tolist()
                                    })
                        elif src.count == 1:  # Single band
                            non_zero_mask = data[0] > 0
                            chunk_non_zero = np.sum(non_zero_mask)
                            non_zero_count += chunk_non_zero
                            
                            if chunk_non_zero > 0 and len(sample_pixels) < 20:
                                non_zero_indices = np.where(non_zero_mask)
                                for i in range(min(5, len(non_zero_indices[0]))):
                                    y, x = non_zero_indices[0][i], non_zero_indices[1][i]
                                    sample_pixels.append({
                                        'global_row': row_start + y,
                                        'global_col': col_start + x,
                                        'values': [data[0, y, x]]
                                    })
                    
                    except Exception as e:
                        print(f"Error reading chunk at ({row_start}, {col_start}): {e}")
                        continue
            
            print(f"\nTotal non-zero pixels found: {non_zero_count:,}")
            
            if sample_pixels:
                print("\nSample pixel values:")
                for i, pixel in enumerate(sample_pixels[:10]):
                    print(f"Pixel {i+1} at ({pixel['global_row']}, {pixel['global_col']}): {pixel['values']}")
            
            # Try reading a small sample from the center
            print("\nReading center sample...")
            center_row = height // 2
            center_col = width // 2
            sample_window = rasterio.windows.Window(
                max(0, center_col - 500), 
                max(0, center_row - 500), 
                1000, 1000
            )
            
            try:
                center_data = src.read(window=sample_window)
                print(f"Center sample shape: {center_data.shape}")
                
                if src.count >= 3:
                    non_zero_mask = (center_data[0] > 0) | (center_data[1] > 0) | (center_data[2] > 0)
                    center_non_zero = np.sum(non_zero_mask)
                    print(f"Non-zero pixels in center sample: {center_non_zero}")
                    
                    if center_non_zero > 0:
                        non_zero_indices = np.where(non_zero_mask)
                        print("Sample center pixel values:")
                        for i in range(min(10, len(non_zero_indices[0]))):
                            y, x = non_zero_indices[0][i], non_zero_indices[1][i]
                            values = center_data[:, y, x]
                            print(f"  Pixel ({y}, {x}): {values}")
                else:
                    non_zero_mask = center_data[0] > 0
                    center_non_zero = np.sum(non_zero_mask)
                    print(f"Non-zero pixels in center sample: {center_non_zero}")
                    
                    if center_non_zero > 0:
                        non_zero_indices = np.where(non_zero_mask)
                        print("Sample center pixel values:")
                        for i in range(min(10, len(non_zero_indices[0]))):
                            y, x = non_zero_indices[0][i], non_zero_indices[1][i]
                            value = center_data[0, y, x]
                            print(f"  Pixel ({y}, {x}): {value}")
            
            except Exception as e:
                print(f"Error reading center sample: {e}")
            
            # Check for nodata values
            print(f"\nNodata values: {src.nodata}")
            
            # Check if there's a colormap
            try:
                if hasattr(src, 'colormap') and src.colormap(1):
                    colormap = src.colormap(1)
                    print(f"Colormap found with {len(colormap)} entries")
                else:
                    print("No colormap found")
            except:
                print("Could not check for colormap")
    
    except Exception as e:
        print(f"Error analyzing file: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_coimbatore_geotiff()
