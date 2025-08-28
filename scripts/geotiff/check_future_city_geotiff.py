#!/usr/bin/env python3
"""
Script to analyze the Future City Hyderabad GeoTIFF file
"""

import rasterio
import numpy as np
from pathlib import Path

def analyze_geotiff():
    """Analyze the Future City Hyderabad GeoTIFF"""
    geotiff_path = "data/Telangana/Hyderabad/future-city/FutureCityHyderabad_Clipped.tif"
    
    with rasterio.open(geotiff_path) as src:
        print(f"File: {geotiff_path}")
        print(f"CRS: {src.crs}")
        print(f"Bounds: {src.bounds}")
        print(f"Shape: {src.shape}")
        print(f"Number of bands: {src.count}")
        print(f"Data types: {src.dtypes}")
        print(f"Transform: {src.transform}")
        
        # Read a small sample to understand the data
        print("\nReading sample data...")
        try:
            # Read a small window to avoid memory issues
            window = rasterio.windows.Window(0, 0, min(1000, src.width), min(1000, src.height))
            data = src.read(window=window)
            
            print(f"Sample data shape: {data.shape}")
            print(f"Sample data type: {data.dtype}")
            
            # Check unique values in each band
            for i in range(data.shape[0]):
                unique_vals = np.unique(data[i])
                print(f"Band {i+1} unique values (sample): {unique_vals[:20]}...")
                print(f"Band {i+1} value range: {data[i].min()} to {data[i].max()}")
                
        except Exception as e:
            print(f"Error reading sample data: {e}")

if __name__ == "__main__":
    analyze_geotiff()
