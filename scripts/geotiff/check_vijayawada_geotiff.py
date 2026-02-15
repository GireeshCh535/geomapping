#!/usr/bin/env python3
"""
Comprehensive GeoTIFF Analysis Script for Vijayawada Master Plan
Analyzes metadata, CRS, bounds, bands, colors, and data structure
"""

import rasterio
from rasterio.warp import calculate_default_transform, transform_bounds
import numpy as np
from pathlib import Path
import sys

def analyze_geotiff(geotiff_path):
    """Perform comprehensive analysis of a GeoTIFF file"""
    
    print(f"\n{'='*80}")
    print(f"ANALYZING: {geotiff_path}")
    print(f"{'='*80}\n")
    
    try:
        with rasterio.open(geotiff_path) as src:
            # Basic metadata
            print("📊 BASIC METADATA")
            print(f"  Driver: {src.driver}")
            print(f"  Width: {src.width} pixels")
            print(f"  Height: {src.height} pixels")
            print(f"  Number of Bands: {src.count}")
            print(f"  Data Type: {src.dtypes[0]}")
            print(f"  CRS: {src.crs}")
            print(f"  No Data Value: {src.nodata}")
            
            # Bounds
            print(f"\n🗺️  BOUNDS (Original CRS)")
            bounds = src.bounds
            print(f"  Left: {bounds.left}")
            print(f"  Bottom: {bounds.bottom}")
            print(f"  Right: {bounds.right}")
            print(f"  Top: {bounds.top}")
            print(f"  Width: {bounds.right - bounds.left:.2f}")
            print(f"  Height: {bounds.top - bounds.bottom:.2f}")
            
            # Transform to WGS84 for web mapping
            if src.crs != 'EPSG:4326':
                print(f"\n🌍 BOUNDS (WGS84 / EPSG:4326)")
                wgs84_bounds = transform_bounds(src.crs, 'EPSG:4326', *bounds)
                print(f"  West: {wgs84_bounds[0]:.6f}")
                print(f"  South: {wgs84_bounds[1]:.6f}")
                print(f"  East: {wgs84_bounds[2]:.6f}")
                print(f"  North: {wgs84_bounds[3]:.6f}")
                print(f"  Center: [{(wgs84_bounds[0] + wgs84_bounds[2])/2:.6f}, {(wgs84_bounds[1] + wgs84_bounds[3])/2:.6f}]")
            
            # Transform
            print(f"\n📐 TRANSFORM")
            transform = src.transform
            print(f"  Pixel Size X: {transform.a}")
            print(f"  Pixel Size Y: {transform.e}")
            print(f"  Rotation: {transform.b}, {transform.d}")
            print(f"  Origin: ({transform.c}, {transform.f})")
            
            # Band information
            print(f"\n🎨 BAND INFORMATION")
            for i in range(1, src.count + 1):
                band = src.read(i)
                print(f"\n  Band {i}:")
                print(f"    Data Type: {src.dtypes[i-1]}")
                print(f"    Min Value: {band.min()}")
                print(f"    Max Value: {band.max()}")
                print(f"    Mean Value: {band.mean():.2f}")
                print(f"    Non-zero pixels: {np.count_nonzero(band)}")
                
                # Color interpretation
                color_interp = src.colorinterp[i-1]
                print(f"    Color Interpretation: {color_interp}")
            
            # Check for colormap
            try:
                colormap = src.colormap(1)
                if colormap:
                    print(f"\n🎨 COLORMAP DETECTED")
                    print(f"  Number of colors: {len(colormap)}")
                    print(f"  Sample colors (first 10):")
                    for idx, (value, color) in enumerate(list(colormap.items())[:10]):
                        print(f"    Value {value}: RGB{color}")
            except (ValueError, TypeError):
                print(f"\n🎨 NO COLORMAP (Direct RGBA data)")
            
            # Sample actual pixel values
            print(f"\n🔍 SAMPLING ACTUAL DATA")
            print(f"  Reading center region (100x100 pixels)...")
            
            center_x = src.width // 2
            center_y = src.height // 2
            window_size = 100
            
            window = rasterio.windows.Window(
                center_x - window_size//2,
                center_y - window_size//2,
                window_size,
                window_size
            )
            
            sample_data = []
            for i in range(1, min(src.count + 1, 5)):  # Read up to 4 bands
                band_data = src.read(i, window=window)
                sample_data.append(band_data)
            
            # Find non-zero pixels
            if len(sample_data) >= 3:
                # Assuming RGB or RGBA
                non_zero_mask = sample_data[0] > 0
                if non_zero_mask.any():
                    print(f"  ✅ Found {non_zero_mask.sum()} non-zero pixels in center sample")
                    
                    # Get unique color combinations
                    if len(sample_data) == 4:
                        colors = np.column_stack([
                            sample_data[0][non_zero_mask],
                            sample_data[1][non_zero_mask],
                            sample_data[2][non_zero_mask],
                            sample_data[3][non_zero_mask]
                        ])
                        print(f"\n  Sample RGBA colors (first 20 unique):")
                        unique_colors = np.unique(colors, axis=0)[:20]
                        for color in unique_colors:
                            print(f"    RGBA: ({color[0]}, {color[1]}, {color[2]}, {color[3]})")
                    elif len(sample_data) == 3:
                        colors = np.column_stack([
                            sample_data[0][non_zero_mask],
                            sample_data[1][non_zero_mask],
                            sample_data[2][non_zero_mask]
                        ])
                        print(f"\n  Sample RGB colors (first 20 unique):")
                        unique_colors = np.unique(colors, axis=0)[:20]
                        for color in unique_colors:
                            print(f"    RGB: ({color[0]}, {color[1]}, {color[2]})")
                else:
                    print(f"  ⚠️  No non-zero pixels found in center sample")
            
            # File size
            file_path = Path(geotiff_path)
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            print(f"\n💾 FILE SIZE: {file_size_mb:.2f} MB")
            
            # Compression info
            print(f"\n📦 COMPRESSION")
            print(f"  Compression: {src.compression}")
            print(f"  Tiled: {src.is_tiled}")
            if src.is_tiled:
                print(f"  Block shapes: {src.block_shapes}")
            
            print(f"\n{'='*80}")
            print("✅ ANALYSIS COMPLETE")
            print(f"{'='*80}\n")
            
    except Exception as e:
        print(f"\n❌ ERROR analyzing GeoTIFF: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def main():
    # Path to the Vijayawada GeoTIFF
    geotiff_path = "data/andhra_pradesh/MGTM/master_plan/Vijaywada_Clipped.tif"
    
    if not Path(geotiff_path).exists():
        print(f"❌ ERROR: File not found: {geotiff_path}")
        sys.exit(1)
    
    print("\n🔬 VIJAYAWADA MASTER PLAN GEOTIFF ANALYSIS")
    print("=" * 80)
    
    success = analyze_geotiff(geotiff_path)
    
    if success:
        print("\n✨ Analysis completed successfully!")
        print("\nKey information for tile generation:")
        print("  - Check the CRS (should note if reprojection is needed)")
        print("  - Note the number of bands (3=RGB, 4=RGBA)")
        print("  - Verify actual color values are present")
        print("  - WGS84 bounds will be used for web mapping")
    else:
        print("\n❌ Analysis failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
