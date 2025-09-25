#!/usr/bin/env python3
import rasterio
import numpy as np

# Open the GeoTIFF file
with rasterio.open('data/karnataka/BMRDA/Anekal Masterplan/AnekalLandusePlan_clipped.tif') as src:
    data = src.read(1)
    unique_values = np.unique(data)
    
    print('Unique pixel values in GeoTIFF:')
    print(unique_values)
    print('\nValue counts:')
    for val in unique_values:
        if val != 0:
            count = np.sum(data == val)
            print(f'Value {val}: {count} pixels')
    
    print(f'\nTotal non-zero pixels: {np.sum(data != 0)}')
    print(f'Total pixels: {data.size}')
    print(f'Data type: {data.dtype}')
    print(f'Data shape: {data.shape}')
