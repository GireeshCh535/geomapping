#!/usr/bin/env python3
"""
Enhanced GeoTIFF Deep Scanner
Thoroughly scans the entire image to find where actual data exists
"""

import os
import sys
import json
import warnings
from pathlib import Path
import numpy as np
from datetime import datetime
import random

warnings.filterwarnings('ignore')

try:
    import rasterio
    from rasterio.windows import Window
except ImportError as e:
    print(f"ERROR: rasterio not installed - {e}")
    sys.exit(1)

class EnhancedTiffScanner:
    def __init__(self, tiff_path):
        self.tiff_path = Path(tiff_path)
        self.scan_results = {
            'timestamp': datetime.now().isoformat(),
            'file': str(self.tiff_path),
            'file_size_mb': self.tiff_path.stat().st_size / (1024 * 1024) if self.tiff_path.exists() else 0,
            'data_regions': [],
            'empty_regions': [],
            'band_statistics': [],
            'actual_data_bounds': None,
            'percentage_with_data': 0,
            'scan_summary': {}
        }
    
    def deep_scan(self, grid_size=10, sample_size=256):
        """
        Perform a deep scan of the image using a grid pattern
        grid_size: divide image into NxN grid
        sample_size: size of sample window at each grid point
        """
        print("="*70)
        print("ENHANCED GEOTIFF DEEP SCANNER")
        print("="*70)
        
        try:
            with rasterio.open(self.tiff_path) as src:
                width, height = src.width, src.height
                bands = src.count
                
                print(f"File: {self.tiff_path.name}")
                print(f"Dimensions: {width}x{height} pixels")
                print(f"Bands: {bands}")
                print(f"File size: {self.scan_results['file_size_mb']:.2f} MB")
                print()
                
                # Calculate grid points
                x_step = width // grid_size
                y_step = height // grid_size
                
                print(f"Scanning {grid_size}x{grid_size} grid points across image...")
                print(f"Each sample: {sample_size}x{sample_size} pixels")
                print("-"*70)
                
                data_points = []
                empty_points = []
                all_values = []
                
                # Scan grid
                for grid_y in range(grid_size):
                    for grid_x in range(grid_size):
                        # Calculate window position
                        col = min(grid_x * x_step, width - sample_size)
                        row = min(grid_y * y_step, height - sample_size)
                        
                        window = Window(col, row, 
                                      min(sample_size, width - col),
                                      min(sample_size, height - row))
                        
                        try:
                            # Read all bands for this window
                            data = src.read(window=window)
                            
                            # Analyze data
                            has_data = False
                            band_info = []
                            
                            for b in range(data.shape[0]):
                                band_data = data[b]
                                non_zero = np.count_nonzero(band_data)
                                
                                if non_zero > 0:
                                    has_data = True
                                    band_stats = {
                                        'min': float(np.min(band_data)),
                                        'max': float(np.max(band_data)),
                                        'mean': float(np.mean(band_data)),
                                        'non_zero_pixels': non_zero,
                                        'unique_values': len(np.unique(band_data))
                                    }
                                    band_info.append(band_stats)
                                    all_values.extend(band_data[band_data > 0].flatten().tolist()[:100])
                            
                            point_info = {
                                'grid_x': grid_x,
                                'grid_y': grid_y,
                                'col': col,
                                'row': row,
                                'width': window.width,
                                'height': window.height,
                                'has_data': has_data
                            }
                            
                            if has_data:
                                point_info['band_stats'] = band_info
                                data_points.append(point_info)
                                print(f"✓ Grid[{grid_x},{grid_y}] at pixel({col},{row}): DATA FOUND")
                            else:
                                empty_points.append(point_info)
                                print(f"✗ Grid[{grid_x},{grid_y}] at pixel({col},{row}): empty")
                            
                        except Exception as e:
                            print(f"ERROR at grid[{grid_x},{grid_y}]: {e}")
                
                print("-"*70)
                
                # Analyze results
                self.scan_results['data_regions'] = data_points
                self.scan_results['empty_regions'] = empty_points
                self.scan_results['percentage_with_data'] = (len(data_points) / (grid_size * grid_size)) * 100
                
                # Find actual data bounds
                if data_points:
                    min_col = min(p['col'] for p in data_points)
                    max_col = max(p['col'] + p['width'] for p in data_points)
                    min_row = min(p['row'] for p in data_points)
                    max_row = max(p['row'] + p['height'] for p in data_points)
                    
                    self.scan_results['actual_data_bounds'] = {
                        'pixel_bounds': {
                            'min_col': min_col,
                            'max_col': max_col,
                            'min_row': min_row,
                            'max_row': max_row,
                            'width': max_col - min_col,
                            'height': max_row - min_row
                        }
                    }
                    
                    # Calculate geographic bounds
                    transform = src.transform
                    west = transform.c + min_col * transform.a
                    north = transform.f + min_row * transform.e
                    east = transform.c + max_col * transform.a
                    south = transform.f + max_row * transform.e
                    
                    self.scan_results['actual_data_bounds']['geo_bounds'] = {
                        'west': west,
                        'north': north,
                        'east': east,
                        'south': south
                    }
                    
                    # Sample statistics
                    if all_values:
                        all_values = np.array(all_values)
                        self.scan_results['scan_summary'] = {
                            'regions_with_data': len(data_points),
                            'regions_empty': len(empty_points),
                            'sample_value_range': [float(np.min(all_values)), float(np.max(all_values))],
                            'sample_mean': float(np.mean(all_values)),
                            'sample_std': float(np.std(all_values)),
                            'unique_values_sampled': min(len(np.unique(all_values)), 1000)
                        }
                
                return self.scan_results
                
        except Exception as e:
            print(f"ERROR: {e}")
            self.scan_results['error'] = str(e)
            return self.scan_results
    
    def edge_scan(self):
        """Specifically scan the edges of the image"""
        print("\nEDGE SCAN")
        print("-"*40)
        
        edge_results = {
            'top': None,
            'bottom': None,
            'left': None,
            'right': None,
            'center': None
        }
        
        try:
            with rasterio.open(self.tiff_path) as src:
                width, height = src.width, src.height
                sample_size = 500
                
                # Define edge samples
                samples = {
                    'top': Window(width//2 - sample_size//2, 0, sample_size, sample_size),
                    'bottom': Window(width//2 - sample_size//2, height - sample_size, sample_size, sample_size),
                    'left': Window(0, height//2 - sample_size//2, sample_size, sample_size),
                    'right': Window(width - sample_size, height//2 - sample_size//2, sample_size, sample_size),
                    'center': Window(width//2 - sample_size//2, height//2 - sample_size//2, sample_size, sample_size)
                }
                
                for location, window in samples.items():
                    try:
                        data = src.read(window=window)
                        has_data = np.any(data > 0)
                        
                        if has_data:
                            edge_results[location] = {
                                'has_data': True,
                                'max_value': float(np.max(data)),
                                'mean_value': float(np.mean(data[data > 0])),
                                'non_zero_pixels': int(np.count_nonzero(data))
                            }
                            print(f"✓ {location.upper()}: Data found (max={edge_results[location]['max_value']:.0f})")
                        else:
                            edge_results[location] = {'has_data': False}
                            print(f"✗ {location.upper()}: Empty")
                    except Exception as e:
                        print(f"ERROR scanning {location}: {e}")
                        edge_results[location] = {'error': str(e)}
                
                self.scan_results['edge_scan'] = edge_results
                
        except Exception as e:
            print(f"Edge scan error: {e}")
    
    def random_scan(self, num_samples=20):
        """Randomly sample points across the image"""
        print("\nRANDOM SAMPLING")
        print("-"*40)
        
        random_results = []
        
        try:
            with rasterio.open(self.tiff_path) as src:
                width, height = src.width, src.height
                sample_size = 256
                
                for i in range(num_samples):
                    col = random.randint(0, max(1, width - sample_size))
                    row = random.randint(0, max(1, height - sample_size))
                    
                    window = Window(col, row, 
                                  min(sample_size, width - col),
                                  min(sample_size, height - row))
                    
                    try:
                        data = src.read(window=window)
                        has_data = np.any(data > 0)
                        
                        result = {
                            'sample_id': i,
                            'col': col,
                            'row': row,
                            'has_data': has_data
                        }
                        
                        if has_data:
                            result['max_value'] = float(np.max(data))
                            result['non_zero_ratio'] = float(np.count_nonzero(data) / data.size)
                            print(f"✓ Sample {i}: ({col},{row}) - Data found")
                        else:
                            print(f"✗ Sample {i}: ({col},{row}) - Empty")
                        
                        random_results.append(result)
                        
                    except Exception as e:
                        print(f"ERROR sampling at ({col},{row}): {e}")
                
                self.scan_results['random_samples'] = random_results
                
                # Calculate statistics
                samples_with_data = sum(1 for r in random_results if r.get('has_data', False))
                print(f"\nRandom sampling: {samples_with_data}/{num_samples} samples contain data")
                
        except Exception as e:
            print(f"Random scan error: {e}")
    
    def diagnose(self):
        """Provide diagnosis based on scan results"""
        print("\n" + "="*70)
        print("DIAGNOSIS")
        print("="*70)
        
        diagnosis = []
        
        # Check if any data was found
        if self.scan_results.get('percentage_with_data', 0) == 0:
            diagnosis.append({
                'severity': 'CRITICAL',
                'issue': 'No data found in any scanned region',
                'explanation': 'The file appears to be completely empty or data is stored in an unusual format',
                'action': 'Check if the file was properly written or if it needs special decoding'
            })
        elif self.scan_results.get('percentage_with_data', 0) < 10:
            diagnosis.append({
                'severity': 'HIGH',
                'issue': f"Only {self.scan_results['percentage_with_data']:.1f}% of image contains data",
                'explanation': 'Most of the image is empty, data is highly sparse',
                'action': 'Extract only the data region to reduce file size and improve performance'
            })
        
        # Check data distribution
        if self.scan_results.get('actual_data_bounds'):
            bounds = self.scan_results['actual_data_bounds']['pixel_bounds']
            if bounds['width'] < 1000 or bounds['height'] < 1000:
                diagnosis.append({
                    'severity': 'MEDIUM',
                    'issue': f"Data region is very small: {bounds['width']}x{bounds['height']} pixels",
                    'explanation': 'The actual data occupies a tiny portion of the declared image size',
                    'action': 'Crop the image to the actual data bounds'
                })
        
        # Check edge scan results
        edge_scan = self.scan_results.get('edge_scan', {})
        if edge_scan:
            edges_with_data = sum(1 for v in edge_scan.values() if v and v.get('has_data', False))
            if edges_with_data == 0:
                diagnosis.append({
                    'severity': 'HIGH',
                    'issue': 'No data found at image edges or center',
                    'explanation': 'Data might be offset or image might have large borders',
                    'action': 'Use deep scan to locate actual data position'
                })
        
        self.scan_results['diagnosis'] = diagnosis
        
        # Print diagnosis
        for d in diagnosis:
            print(f"[{d['severity']}] {d['issue']}")
            print(f"  → {d['explanation']}")
            print(f"  ⚡ {d['action']}")
            print()
        
        if not diagnosis:
            print("✓ No critical issues found with data distribution")
        
        return diagnosis
    
    def save_report(self, output_path=None):
        """Save detailed report"""
        if output_path is None:
            output_path = self.tiff_path.parent / f"{self.tiff_path.stem}_deep_scan.json"
        
        with open(output_path, 'w') as f:
            json.dump(self.scan_results, f, indent=2, default=str)
        
        print(f"\n📄 Detailed report saved to: {output_path}")
        return output_path
    
    def print_summary(self):
        """Print summary of findings"""
        print("\n" + "="*70)
        print("SCAN SUMMARY")
        print("="*70)
        
        print(f"File: {self.tiff_path.name}")
        print(f"Regions with data: {len(self.scan_results.get('data_regions', []))}")
        print(f"Empty regions: {len(self.scan_results.get('empty_regions', []))}")
        print(f"Data coverage: {self.scan_results.get('percentage_with_data', 0):.1f}%")
        
        if self.scan_results.get('actual_data_bounds'):
            bounds = self.scan_results['actual_data_bounds']['pixel_bounds']
            print(f"\nActual data location:")
            print(f"  Pixel range: ({bounds['min_col']},{bounds['min_row']}) to ({bounds['max_col']},{bounds['max_row']})")
            print(f"  Size: {bounds['width']}x{bounds['height']} pixels")
            
            geo = self.scan_results['actual_data_bounds'].get('geo_bounds', {})
            if geo:
                print(f"  Geographic: ({geo['west']:.6f},{geo['south']:.6f}) to ({geo['east']:.6f},{geo['north']:.6f})")
        
        if self.scan_results.get('scan_summary'):
            summary = self.scan_results['scan_summary']
            if 'sample_value_range' in summary:
                print(f"\nData values:")
                print(f"  Range: {summary['sample_value_range'][0]:.0f} to {summary['sample_value_range'][1]:.0f}")
                print(f"  Mean: {summary.get('sample_mean', 0):.1f}")
                print(f"  Unique values: {summary.get('unique_values_sampled', 0)}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python enhanced_scanner.py <tiff_file> [grid_size]")
        print("\nThis will thoroughly scan your TIFF to find where data actually exists")
        print("grid_size: optional, default is 10 (for 10x10 grid scan)")
        sys.exit(1)
    
    tiff_path = sys.argv[1]
    grid_size = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    scanner = EnhancedTiffScanner(tiff_path)
    
    # Perform comprehensive scan
    scanner.deep_scan(grid_size=grid_size)
    scanner.edge_scan()
    scanner.random_scan(num_samples=20)
    
    # Diagnose issues
    scanner.diagnose()
    
    # Print summary
    scanner.print_summary()
    
    # Save report
    report_path = scanner.save_report()
    
    print("\n" + "="*70)
    print("SCAN COMPLETE!")
    print("="*70)
    print("\nNext steps:")
    print("1. Review the diagnosis above")
    print("2. Check the detailed JSON report")
    print("3. If data was found, use the actual_data_bounds to extract it")
    print("4. Run the fixer script to create an optimized version")

if __name__ == "__main__":
    main()