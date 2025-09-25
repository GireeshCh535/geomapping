#!/usr/bin/env python3
import rasterio
import numpy as np

# Open the GeoTIFF file
with rasterio.open('data/karnataka/BMRDA/Hosakote Masterplan/Hosakote_Merged.tif') as src:
    print(f"Number of bands: {src.count}")
    print(f"Color interpretation: {src.colorinterp}")
    print(f"Data shape: {src.shape}")
    print(f"CRS: {src.crs}")
    print(f"Bounds: {src.bounds}")
    
    # Try different window locations to find data
    windows_to_try = [
        rasterio.windows.Window(0, 0, 1000, 1000),
        rasterio.windows.Window(5000, 5000, 1000, 1000),
        rasterio.windows.Window(10000, 10000, 1000, 1000),
        rasterio.windows.Window(15000, 15000, 1000, 1000),
        rasterio.windows.Window(20000, 20000, 1000, 1000),
    ]
    
    for i, window in enumerate(windows_to_try):
        print(f"\n--- Window {i+1}: {window} ---")
        try:
            data = src.read(window=window)
            print(f"Sample data shape: {data.shape}")
            
            # Find non-zero pixels in the sample
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
                print("Unique RGB combinations in sample (first 10):")
                unique_combinations = set()
                for j in range(min(200, len(non_zero_indices[0]))):
                    y, x = non_zero_indices[0][j], non_zero_indices[1][j]
                    r, g, b = data[0, y, x], data[1, y, x], data[2, y, x]
                    unique_combinations.add((r, g, b))
                    if len(unique_combinations) >= 10:
                        break
                
                for rgb in sorted(unique_combinations):
                    print(f"RGB{rgb}")
                break
            else:
                print("No non-zero pixels found in this window")
                
        except Exception as e:
            print(f"Error reading window: {e}")
    
    # Check unique values in each band (sample)
    print(f"\nUnique values in Red band (sample): {np.unique(data[0])[:20]}...")
    print(f"Unique values in Green band (sample): {np.unique(data[1])[:20]}...")
    print(f"Unique values in Blue band (sample): {np.unique(data[2])[:20]}...")
    print(f"Unique values in Alpha band (sample): {np.unique(data[3])}")
