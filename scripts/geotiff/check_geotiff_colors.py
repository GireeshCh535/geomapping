#!/usr/bin/env python3
import rasterio
import numpy as np

# Open the GeoTIFF file
with rasterio.open('data/karnataka/BMRDA/Anekal Masterplan/AnekalLandusePlan_clipped.tif') as src:
    print(f"Number of bands: {src.count}")
    print(f"Color interpretation: {src.colorinterp}")
    
    # Read all bands
    data = src.read()
    print(f"Data shape: {data.shape}")
    
    # Find non-zero pixels
    non_zero_mask = (data[0] > 0) | (data[1] > 0) | (data[2] > 0)
    non_zero_indices = np.where(non_zero_mask)
    
    print(f"Non-zero pixels found: {len(non_zero_indices[0])}")
    
    # Sample some non-zero pixels to see the colors
    print("\nSample non-zero pixel values (R,G,B,A):")
    for i in range(min(20, len(non_zero_indices[0]))):
        y, x = non_zero_indices[0][i], non_zero_indices[1][i]
        r, g, b, a = data[:, y, x]
        print(f"Pixel ({y}, {x}): R={r}, G={g}, B={b}, A={a}")
    
    # Check if this is an indexed image by looking at unique combinations
    print(f"\nUnique RGB combinations (first 20):")
    unique_combinations = set()
    for i in range(min(1000, len(non_zero_indices[0]))):
        y, x = non_zero_indices[0][i], non_zero_indices[1][i]
        r, g, b = data[0, y, x], data[1, y, x], data[2, y, x]
        unique_combinations.add((r, g, b))
        if len(unique_combinations) >= 20:
            break
    
    for rgb in sorted(unique_combinations):
        print(f"RGB{rgb}")
