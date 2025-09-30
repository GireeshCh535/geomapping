#!/usr/bin/env python3
"""
Script to analyze Kakinada GeoTIFF file and understand its structure
"""

import rasterio
import numpy as np
from pathlib import Path
import sys

def analyze_geotiff(geotiff_path):
    """Analyze the GeoTIFF file and print detailed information"""
    print("=" * 80)
    print(f"🔍 ANALYZING GEOTIFF: {geotiff_path}")
    print("=" * 80)
    
    try:
        with rasterio.open(geotiff_path) as src:
            print(f"📁 File: {geotiff_path}")
            print(f"📊 Shape: {src.shape} (height x width)")
            print(f"📈 Bands: {src.count}")
            print(f"🗺️  CRS: {src.crs}")
            print(f"📍 Bounds: {src.bounds}")
            print(f"📐 Transform: {src.transform}")
            print(f"💾 Data Type: {src.dtypes}")
            print(f"📋 NoData Value: {src.nodata}")
            
            # Check for colormap
            try:
                colormap = src.colormap(1)
                if colormap:
                    print(f"\n🎨 COLORMAP DETECTED")
                    print(f"  Number of colors: {len(colormap)}")
                    print(f"  Sample colors (first 10):")
                    for idx, (value, color) in enumerate(list(colormap.items())[:10]):
                        print(f"    Value {value}: RGB{color}")
                else:
                    print(f"\n🎨 NO COLORMAP (Direct RGBA data)")
            except (ValueError, TypeError):
                print(f"\n🎨 NO COLORMAP (Direct RGBA data)")
            
            # Sample data from different bands
            print(f"\n📊 BAND ANALYSIS:")
            for band_idx in range(1, min(src.count + 1, 5)):  # Analyze first 4 bands
                band_data = src.read(band_idx)
                print(f"\n  Band {band_idx}:")
                print(f"    Shape: {band_data.shape}")
                print(f"    Data type: {band_data.dtype}")
                print(f"    Min value: {np.min(band_data)}")
                print(f"    Max value: {np.max(band_data)}")
                print(f"    Unique values: {len(np.unique(band_data))}")
                
                # Check for non-zero pixels
                non_zero_pixels = np.count_nonzero(band_data)
                total_pixels = band_data.size
                print(f"    Non-zero pixels: {non_zero_pixels:,} / {total_pixels:,} ({non_zero_pixels/total_pixels*100:.2f}%)")
                
                # Sample some non-zero values
                if non_zero_pixels > 0:
                    non_zero_values = band_data[band_data > 0]
                    if len(non_zero_values) > 0:
                        sample_values = np.random.choice(non_zero_values, min(10, len(non_zero_values)), replace=False)
                        print(f"    Sample non-zero values: {sample_values}")
            
            # If it's RGBA, analyze color combinations
            if src.count >= 3:
                print(f"\n🌈 COLOR ANALYSIS:")
                # Read all bands
                bands = []
                for i in range(1, min(src.count + 1, 5)):
                    bands.append(src.read(i))
                
                # Sample pixels to understand color patterns
                sample_size = 10000
                height, width = bands[0].shape
                
                # Sample random pixels
                y_coords = np.random.randint(0, height, sample_size)
                x_coords = np.random.randint(0, width, sample_size)
                
                sample_colors = []
                for i in range(sample_size):
                    y, x = y_coords[i], x_coords[i]
                    if len(bands) >= 3:
                        r, g, b = bands[0][y, x], bands[1][y, x], bands[2][y, x]
                        if r > 0 or g > 0 or b > 0:  # Only non-black pixels
                            sample_colors.append((r, g, b))
                
                if sample_colors:
                    print(f"  Sampled {len(sample_colors)} non-black pixels")
                    
                    # Find unique color combinations
                    unique_colors = list(set(sample_colors))
                    print(f"  Unique color combinations found: {len(unique_colors)}")
                    
                    if len(unique_colors) <= 20:
                        print(f"  All unique colors:")
                        for color in unique_colors:
                            print(f"    RGB{color}")
                    else:
                        print(f"  Sample unique colors (first 20):")
                        for color in unique_colors[:20]:
                            print(f"    RGB{color}")
                
                # Check for alpha channel
                if src.count >= 4:
                    alpha_band = bands[3]
                    alpha_non_zero = np.count_nonzero(alpha_band)
                    print(f"\n🔍 ALPHA CHANNEL (Band 4):")
                    print(f"  Non-zero alpha pixels: {alpha_non_zero:,} / {alpha_band.size:,} ({alpha_non_zero/alpha_band.size*100:.2f}%)")
                    if alpha_non_zero > 0:
                        alpha_values = alpha_band[alpha_band > 0]
                        unique_alpha = np.unique(alpha_values)
                        print(f"  Unique alpha values: {unique_alpha}")
            
            # Window-based analysis for large files
            if src.width > 1000 or src.height > 1000:
                print(f"\n🔍 WINDOW-BASED ANALYSIS (Large file detected):")
                
                # Analyze in windows
                window_size = 1000
                windows_analyzed = 0
                total_non_zero = 0
                sample_colors_window = set()
                
                for row in range(0, src.height, window_size):
                    for col in range(0, src.width, window_size):
                        window = rasterio.windows.Window(col, row, 
                                                       min(window_size, src.width - col),
                                                       min(window_size, src.height - row))
                        
                        # Read window data
                        window_data = src.read(1, window=window)
                        non_zero_in_window = np.count_nonzero(window_data)
                        total_non_zero += non_zero_in_window
                        
                        if non_zero_in_window > 0 and len(sample_colors_window) < 50:
                            # Sample some colors from this window
                            if src.count >= 3:
                                r_win = src.read(1, window=window)
                                g_win = src.read(2, window=window)
                                b_win = src.read(3, window=window)
                                
                                # Find non-zero pixels in this window
                                non_zero_mask = (r_win > 0) | (g_win > 0) | (b_win > 0)
                                if np.any(non_zero_mask):
                                    non_zero_coords = np.where(non_zero_mask)
                                    if len(non_zero_coords[0]) > 0:
                                        # Sample up to 10 pixels from this window
                                        sample_indices = np.random.choice(len(non_zero_coords[0]), 
                                                                        min(10, len(non_zero_coords[0])), 
                                                                        replace=False)
                                        for idx in sample_indices:
                                            y, x = non_zero_coords[0][idx], non_zero_coords[1][idx]
                                            color = (r_win[y, x], g_win[y, x], b_win[y, x])
                                            sample_colors_window.add(color)
                        
                        windows_analyzed += 1
                        if windows_analyzed >= 10:  # Limit to first 10 windows for performance
                            break
                    if windows_analyzed >= 10:
                        break
                
                print(f"  Analyzed {windows_analyzed} windows")
                print(f"  Total non-zero pixels found: {total_non_zero:,}")
                print(f"  Unique colors sampled: {len(sample_colors_window)}")
                
                if sample_colors_window:
                    print(f"  Sample colors from windows:")
                    for color in list(sample_colors_window)[:15]:
                        print(f"    RGB{color}")
    
    except Exception as e:
        print(f"❌ Error analyzing GeoTIFF: {str(e)}")
        return False
    
    print("=" * 80)
    print("✅ Analysis complete!")
    print("=" * 80)
    return True

def main():
    """Main function"""
    # Path to the Kakinada GeoTIFF
    geotiff_path = Path("data/andhra_pradesh/kakinada/master_plan/Kakinada_Clipped.tif")
    
    if not geotiff_path.exists():
        print(f"❌ GeoTIFF file not found: {geotiff_path}")
        print("Please make sure the file exists in the correct location.")
        sys.exit(1)
    
    # Analyze the GeoTIFF
    success = analyze_geotiff(geotiff_path)
    
    if success:
        print("\n🎯 RECOMMENDATIONS:")
        print("1. Check if this is an RGBA GeoTIFF (4 bands)")
        print("2. Verify the CRS and bounds are correct")
        print("3. Check if colors are direct RGB values or use a colormap")
        print("4. Ensure the file is not corrupted")
        print("5. Consider the file size for tile generation performance")
    else:
        print("\n❌ Analysis failed. Please check the file and try again.")

if __name__ == "__main__":
    main()