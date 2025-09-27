#!/usr/bin/env python3
"""
Comprehensive GeoTIFF Analyzer
Gathers all necessary information to debug and fix tile generation issues
"""

import os
import sys
import json
import warnings
from pathlib import Path
import numpy as np
from datetime import datetime

# Suppress warnings temporarily
warnings.filterwarnings('ignore')

# Try imports
libraries = {}
try:
    import rasterio
    from rasterio.windows import Window
    from rasterio.transform import from_bounds
    from rasterio.warp import transform_bounds
    libraries['rasterio'] = rasterio.__version__
except ImportError as e:
    print(f"ERROR: rasterio not installed - {e}")
    sys.exit(1)

try:
    import mercantile
    libraries['mercantile'] = mercantile.__version__ if hasattr(mercantile, '__version__') else 'installed'
except ImportError:
    libraries['mercantile'] = 'not installed'

try:
    from PIL import Image
    libraries['PIL'] = Image.__version__ if hasattr(Image, '__version__') else 'installed'
except ImportError:
    libraries['PIL'] = 'not installed'

try:
    import gdal
    from osgeo import gdal
    libraries['GDAL'] = gdal.__version__
except ImportError:
    libraries['GDAL'] = 'not available'

class GeoTIFFAnalyzer:
    def __init__(self, tiff_path):
        self.tiff_path = Path(tiff_path)
        self.report = {
            'timestamp': datetime.now().isoformat(),
            'file': str(self.tiff_path),
            'file_exists': self.tiff_path.exists(),
            'file_size_mb': 0,
            'libraries': libraries,
            'basic_info': {},
            'georeferencing': {},
            'data_info': {},
            'corruption_check': {},
            'tile_generation_params': {},
            'recommendations': []
        }
        
        if self.tiff_path.exists():
            self.report['file_size_mb'] = self.tiff_path.stat().st_size / (1024 * 1024)
    
    def analyze(self):
        """Run complete analysis"""
        print("="*70)
        print(f"GEOTIFF ANALYZER - {self.tiff_path.name}")
        print("="*70)
        
        if not self.tiff_path.exists():
            print(f"ERROR: File not found: {self.tiff_path}")
            return self.report
        
        print(f"File size: {self.report['file_size_mb']:.2f} MB")
        print()
        
        # Run all analysis steps
        self.analyze_basic_info()
        self.analyze_georeferencing()
        self.analyze_data_characteristics()
        self.check_corruption()
        self.calculate_tile_params()
        self.generate_recommendations()
        
        return self.report
    
    def analyze_basic_info(self):
        """Analyze basic file information"""
        print("1. BASIC INFORMATION")
        print("-" * 40)
        
        try:
            with rasterio.open(self.tiff_path) as src:
                self.report['basic_info'] = {
                    'width': src.width,
                    'height': src.height,
                    'total_pixels': src.width * src.height,
                    'count_bands': src.count,
                    'dtype': str(src.dtypes[0]),
                    'driver': src.driver,
                    'compression': src.compression.name if src.compression else 'none',
                    'interleave': src.interleaving.name if src.interleaving else 'none',
                    'photometric': src.photometric.name if src.photometric else 'none',
                    'tiled': src.is_tiled,
                    'block_shape': src.block_shapes[0] if src.block_shapes else None,
                    'nodata': src.nodata,
                    'has_overviews': len(src.overviews(1)) > 0,
                    'overview_levels': src.overviews(1) if src.overviews(1) else [],
                    'profile': {k: str(v) for k, v in src.profile.items()}
                }
                
                print(f"Dimensions: {src.width} x {src.height} pixels")
                print(f"Total pixels: {src.width * src.height:,}")
                print(f"Bands: {src.count}")
                print(f"Data type: {src.dtypes[0]}")
                print(f"Compression: {self.report['basic_info']['compression']}")
                print(f"Tiled: {src.is_tiled}")
                if src.is_tiled:
                    print(f"Tile size: {src.block_shapes[0]}")
                print(f"Overviews: {len(src.overviews(1))} levels - {src.overviews(1)}")
                
        except Exception as e:
            print(f"ERROR reading basic info: {e}")
            self.report['basic_info']['error'] = str(e)
        
        print()
    
    def analyze_georeferencing(self):
        """Analyze georeferencing information"""
        print("2. GEOREFERENCING")
        print("-" * 40)
        
        try:
            with rasterio.open(self.tiff_path) as src:
                # Get CRS info
                crs_info = {
                    'crs': str(src.crs) if src.crs else None,
                    'crs_wkt': src.crs.wkt if src.crs else None,
                    'is_geographic': src.crs.is_geographic if src.crs else None,
                    'is_projected': src.crs.is_projected if src.crs else None,
                }
                
                # Get bounds
                bounds = src.bounds
                bounds_info = {
                    'left': bounds.left,
                    'bottom': bounds.bottom,
                    'right': bounds.right,
                    'top': bounds.top,
                    'width_degrees': bounds.right - bounds.left,
                    'height_degrees': bounds.top - bounds.bottom
                }
                
                # Get transform
                transform = src.transform
                transform_info = {
                    'transform': str(transform),
                    'pixel_width': transform.a,
                    'pixel_height': abs(transform.e),
                    'rotation_x': transform.b,
                    'rotation_y': transform.d,
                    'origin_x': transform.c,
                    'origin_y': transform.f,
                    'is_identity': transform.is_identity,
                    'is_rectilinear': transform.is_rectilinear if hasattr(transform, 'is_rectilinear') else None
                }
                
                # Calculate WGS84 bounds if needed
                wgs84_bounds = None
                if src.crs and str(src.crs) != 'EPSG:4326':
                    try:
                        wgs84_bounds = transform_bounds(src.crs, 'EPSG:4326', *bounds)
                        wgs84_info = {
                            'west': wgs84_bounds[0],
                            'south': wgs84_bounds[1],
                            'east': wgs84_bounds[2],
                            'north': wgs84_bounds[3]
                        }
                    except:
                        wgs84_info = None
                else:
                    wgs84_info = bounds_info.copy()
                
                self.report['georeferencing'] = {
                    'crs': crs_info,
                    'bounds': bounds_info,
                    'transform': transform_info,
                    'wgs84_bounds': wgs84_info,
                    'resolution_meters': None
                }
                
                # Try to calculate resolution in meters
                if src.crs and src.crs.is_projected:
                    self.report['georeferencing']['resolution_meters'] = {
                        'x': abs(transform.a),
                        'y': abs(transform.e)
                    }
                
                print(f"CRS: {crs_info['crs']}")
                print(f"Bounds: ({bounds.left:.6f}, {bounds.bottom:.6f}, {bounds.right:.6f}, {bounds.top:.6f})")
                print(f"Pixel size: {transform.a:.10f} x {abs(transform.e):.10f}")
                print(f"Transform identity: {transform.is_identity}")
                if wgs84_info and str(src.crs) != 'EPSG:4326':
                    print(f"WGS84 bounds: ({wgs84_info['west']:.6f}, {wgs84_info['south']:.6f}, "
                          f"{wgs84_info['east']:.6f}, {wgs84_info['north']:.6f})")
                
        except Exception as e:
            print(f"ERROR reading georeferencing: {e}")
            self.report['georeferencing']['error'] = str(e)
        
        print()
    
    def analyze_data_characteristics(self):
        """Analyze data characteristics by sampling"""
        print("3. DATA CHARACTERISTICS")
        print("-" * 40)
        
        try:
            with rasterio.open(self.tiff_path) as src:
                data_info = {
                    'bands': [],
                    'has_alpha': False,
                    'sample_successful': False,
                    'estimated_memory_mb': 0
                }
                
                # Calculate memory requirement
                dtype_size = np.dtype(src.dtypes[0]).itemsize
                data_info['estimated_memory_mb'] = (src.width * src.height * src.count * dtype_size) / (1024 * 1024)
                
                print(f"Estimated memory requirement: {data_info['estimated_memory_mb']:.2f} MB")
                
                # Sample each band
                sample_size = min(1000, src.width, src.height)
                sample_window = Window(0, 0, sample_size, sample_size)
                
                print(f"Sampling {sample_size}x{sample_size} pixels from each band...")
                
                for band_idx in range(1, src.count + 1):
                    try:
                        sample_data = src.read(band_idx, window=sample_window)
                        
                        band_info = {
                            'index': band_idx,
                            'min': float(np.min(sample_data)),
                            'max': float(np.max(sample_data)),
                            'mean': float(np.mean(sample_data)),
                            'std': float(np.std(sample_data)),
                            'has_data': np.any(sample_data != 0),
                            'unique_values': min(len(np.unique(sample_data)), 100),
                            'sample_successful': True
                        }
                        
                        # Check if this might be alpha channel
                        if band_idx == src.count and band_idx == 4:
                            unique_vals = np.unique(sample_data)
                            if len(unique_vals) <= 2 and 255 in unique_vals:
                                data_info['has_alpha'] = True
                                band_info['is_alpha'] = True
                        
                        data_info['bands'].append(band_info)
                        print(f"  Band {band_idx}: min={band_info['min']:.1f}, "
                              f"max={band_info['max']:.1f}, mean={band_info['mean']:.1f}")
                        
                    except Exception as e:
                        print(f"  Band {band_idx}: ERROR - {e}")
                        data_info['bands'].append({
                            'index': band_idx,
                            'error': str(e),
                            'sample_successful': False
                        })
                
                data_info['sample_successful'] = all(b.get('sample_successful', False) for b in data_info['bands'])
                self.report['data_info'] = data_info
                
        except Exception as e:
            print(f"ERROR analyzing data: {e}")
            self.report['data_info']['error'] = str(e)
        
        print()
    
    def check_corruption(self):
        """Check for file corruption"""
        print("4. CORRUPTION CHECK")
        print("-" * 40)
        
        corruption_info = {
            'quick_read_test': False,
            'random_tile_test': False,
            'corrupted_areas': [],
            'error_messages': [],
            'is_corrupted': False
        }
        
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                
                with rasterio.open(self.tiff_path) as src:
                    # Test 1: Quick read of small area
                    try:
                        test_window = Window(0, 0, min(100, src.width), min(100, src.height))
                        test_data = src.read(window=test_window)
                        corruption_info['quick_read_test'] = True
                        print("✓ Quick read test: PASSED")
                    except Exception as e:
                        corruption_info['quick_read_test'] = False
                        corruption_info['error_messages'].append(f"Quick read: {str(e)}")
                        print(f"✗ Quick read test: FAILED - {e}")
                    
                    # Test 2: Random tile reads
                    print("Testing random tiles...")
                    num_tests = min(10, (src.width // 512) * (src.height // 512))
                    failed_tiles = 0
                    
                    for i in range(num_tests):
                        try:
                            # Random position
                            col = np.random.randint(0, max(1, src.width - 512))
                            row = np.random.randint(0, max(1, src.height - 512))
                            test_window = Window(col, row, min(512, src.width - col), min(512, src.height - row))
                            test_data = src.read(1, window=test_window)
                        except Exception as e:
                            failed_tiles += 1
                            if 'LZW' in str(e) or 'TIFFRead' in str(e):
                                corruption_info['corrupted_areas'].append({
                                    'col': col,
                                    'row': row,
                                    'error': str(e)[:100]
                                })
                    
                    corruption_info['random_tile_test'] = failed_tiles == 0
                    if failed_tiles > 0:
                        print(f"✗ Random tile test: {failed_tiles}/{num_tests} tiles failed")
                        corruption_info['is_corrupted'] = True
                    else:
                        print(f"✓ Random tile test: PASSED ({num_tests} tiles)")
                    
                    # Check warnings
                    if w:
                        for warning in w:
                            if 'LZW' in str(warning.message) or 'TIFF' in str(warning.message):
                                corruption_info['error_messages'].append(str(warning.message)[:200])
                
                self.report['corruption_check'] = corruption_info
                
        except Exception as e:
            print(f"ERROR during corruption check: {e}")
            corruption_info['error_messages'].append(str(e))
            corruption_info['is_corrupted'] = True
            self.report['corruption_check'] = corruption_info
        
        print()
    
    def calculate_tile_params(self):
        """Calculate optimal tile generation parameters"""
        print("5. TILE GENERATION PARAMETERS")
        print("-" * 40)
        
        try:
            with rasterio.open(self.tiff_path) as src:
                params = {}
                
                # Get bounds for tile calculation
                if src.crs and str(src.crs) == 'EPSG:4326':
                    bounds = src.bounds
                elif src.crs:
                    try:
                        bounds = transform_bounds(src.crs, 'EPSG:4326', *src.bounds)
                    except:
                        # Fallback to approximate Kochi bounds
                        bounds = (76.2371, 9.8927, 76.3399, 10.0496)
                else:
                    # No CRS, use Kochi bounds
                    bounds = (76.2371, 9.8927, 76.3399, 10.0496)
                
                params['wgs84_bounds'] = {
                    'west': bounds[0],
                    'south': bounds[1],
                    'east': bounds[2],
                    'north': bounds[3]
                }
                
                # Calculate tiles needed for different zoom levels
                params['tiles_per_zoom'] = {}
                total_tiles = 0
                
                print("Tiles needed per zoom level:")
                for zoom in [8, 10, 12, 14, 16, 18]:
                    if mercantile:
                        min_tile = mercantile.tile(bounds[0], bounds[1], zoom)
                        max_tile = mercantile.tile(bounds[2], bounds[3], zoom)
                        tiles_x = max_tile.x - min_tile.x + 1
                        tiles_y = min_tile.y - max_tile.y + 1
                        tiles_count = tiles_x * tiles_y
                        params['tiles_per_zoom'][zoom] = {
                            'count': tiles_count,
                            'x_range': [min_tile.x, max_tile.x],
                            'y_range': [max_tile.y, min_tile.y]
                        }
                        total_tiles += tiles_count
                        print(f"  Zoom {zoom}: {tiles_count:,} tiles ({tiles_x}x{tiles_y})")
                
                params['total_tiles_8_18'] = total_tiles
                
                # Memory strategy recommendation
                mem_mb = self.report['data_info'].get('estimated_memory_mb', 0)
                if mem_mb < 500:
                    params['recommended_strategy'] = 'memory'
                elif mem_mb < 2000:
                    params['recommended_strategy'] = 'windowed'
                else:
                    params['recommended_strategy'] = 'windowed_large'
                
                # Worker recommendation
                import multiprocessing
                cpu_count = multiprocessing.cpu_count()
                if mem_mb > 2000:
                    params['recommended_workers'] = min(4, cpu_count - 1)
                else:
                    params['recommended_workers'] = min(8, cpu_count - 1)
                
                params['recommended_batch_size'] = 100 if mem_mb < 2000 else 50
                
                self.report['tile_generation_params'] = params
                
                print(f"\nRecommended settings:")
                print(f"  Strategy: {params['recommended_strategy']}")
                print(f"  Workers: {params['recommended_workers']}")
                print(f"  Batch size: {params['recommended_batch_size']}")
                
        except Exception as e:
            print(f"ERROR calculating tile params: {e}")
            self.report['tile_generation_params']['error'] = str(e)
        
        print()
    
    def generate_recommendations(self):
        """Generate recommendations based on analysis"""
        print("6. RECOMMENDATIONS")
        print("-" * 40)
        
        recs = []
        
        # Check compression
        if self.report['basic_info'].get('compression') == 'lzw':
            if self.report['corruption_check'].get('is_corrupted'):
                recs.append({
                    'priority': 'HIGH',
                    'issue': 'LZW compression with corruption detected',
                    'action': 'Recompress file with DEFLATE or repair corruption',
                    'command': 'gdal_translate -co COMPRESS=DEFLATE -co TILED=YES -co BIGTIFF=YES input.tif output.tif'
                })
        
        # Check overviews
        if not self.report['basic_info'].get('has_overviews'):
            recs.append({
                'priority': 'MEDIUM',
                'issue': 'No overviews found',
                'action': 'Build overviews for faster tile generation',
                'command': 'gdaladdo -r average input.tif 2 4 8 16 32'
            })
        
        # Check tiling
        if not self.report['basic_info'].get('tiled'):
            recs.append({
                'priority': 'MEDIUM',
                'issue': 'File is not tiled',
                'action': 'Convert to tiled format for better performance',
                'command': 'gdal_translate -co TILED=YES -co BLOCKXSIZE=512 -co BLOCKYSIZE=512 input.tif output.tif'
            })
        
        # Check CRS
        if not self.report['georeferencing'].get('crs', {}).get('crs'):
            recs.append({
                'priority': 'HIGH',
                'issue': 'No CRS defined',
                'action': 'Assign EPSG:4326 if data is in WGS84',
                'command': 'gdal_translate -a_srs EPSG:4326 input.tif output.tif'
            })
        
        # Check transform
        if self.report['georeferencing'].get('transform', {}).get('is_identity'):
            recs.append({
                'priority': 'HIGH',
                'issue': 'Transform is identity (no georeferencing)',
                'action': 'Set proper georeferencing with bounds',
                'command': 'gdal_translate -a_ullr <west> <north> <east> <south> input.tif output.tif'
            })
        
        # Memory recommendations
        mem_mb = self.report['data_info'].get('estimated_memory_mb', 0)
        if mem_mb > 4000:
            recs.append({
                'priority': 'MEDIUM',
                'issue': f'Large file ({mem_mb:.0f}MB in memory)',
                'action': 'Use windowed reading strategy and limit workers to 4',
                'command': '--strategy windowed_large --workers 4'
            })
        
        self.report['recommendations'] = recs
        
        if recs:
            for rec in recs:
                print(f"[{rec['priority']}] {rec['issue']}")
                print(f"  → {rec['action']}")
                if rec.get('command'):
                    print(f"  $ {rec['command']}")
                print()
        else:
            print("✓ No critical issues found!")
        
        print()
    
    def save_report(self, output_path=None):
        """Save report to JSON file"""
        if output_path is None:
            output_path = self.tiff_path.parent / f"{self.tiff_path.stem}_analysis.json"
        
        with open(output_path, 'w') as f:
            json.dump(self.report, f, indent=2, default=str)
        
        print(f"Report saved to: {output_path}")
        return output_path

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python analyze_tiff.py <path_to_tiff>")
        print("\nThis script will analyze your GeoTIFF and generate a detailed report")
        print("to help fix tile generation issues.")
        sys.exit(1)
    
    tiff_path = sys.argv[1]
    
    analyzer = GeoTIFFAnalyzer(tiff_path)
    report = analyzer.analyze()
    
    # Save report
    report_path = analyzer.save_report()
    
    print("="*70)
    print("ANALYSIS COMPLETE!")
    print("="*70)
    print("\nSummary:")
    
    # Quick summary
    if report['corruption_check'].get('is_corrupted'):
        print("⚠️  FILE IS CORRUPTED - Repair needed")
    else:
        print("✓ File integrity OK")
    
    if report['basic_info'].get('compression') == 'lzw':
        print("⚠️  LZW compression detected - May cause issues")
    
    if not report['basic_info'].get('has_overviews'):
        print("⚠️  No overviews - Will be slow for low zoom levels")
    
    if report['georeferencing'].get('transform', {}).get('is_identity'):
        print("⚠️  No georeferencing - Coordinates may be wrong")
    
    print(f"\n📄 Full report saved to: {report_path}")
    print("\n" + "="*70)
    print("NEXT STEPS:")
    print("1. Share the generated JSON report")
    print("2. If corruption detected, run repair script")
    print("3. Follow recommendations in report")
    print("="*70)

if __name__ == "__main__":
    main()