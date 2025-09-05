#!/usr/bin/env python3
"""
Comprehensive Analysis Script for Amaravati Master Plan Data
===========================================================
Analyzes all GeoJSON files to detect format, CRS, features, and zoning attributes.
"""

import os
import sys
import json
import warnings
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import geopandas as gpd
import fiona
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.validation import explain_validity
import numpy as np
from collections import defaultdict, Counter

warnings.filterwarnings('ignore')

class AmaravatiDataAnalyzer:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.analysis_results = {}
        self.zoning_attributes = defaultdict(set)
        self.all_zoning_values = set()
        self.file_errors = []
        
    def analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a single GeoJSON file"""
        result = {
            'file_name': file_path.name,
            'file_path': str(file_path),
            'file_size': file_path.stat().st_size,
            'format': 'GeoJSON',
            'driver': 'GeoJSON',
            'encoding': 'UTF-8',
            'crs': None,
            'crs_string': None,
            'feature_count': 0,
            'geometry_types': [],
            'bounds': None,
            'total_extent': None,
            'zoning_attributes': [],
            'unique_zoning_values': [],
            'sample_attributes': {},
            'geometry_validation': {
                'valid_count': 0,
                'invalid_count': 0,
                'empty_count': 0,
                'fixed_count': 0,
                'invalid_reasons': []
            },
            'duplicates': 0,
            'small_geometries': 0,
            'multipart_issues': 0,
            'errors': []
        }
        
        try:
            # Read with fiona to get metadata
            with fiona.open(file_path) as src:
                result['crs'] = src.crs
                result['crs_string'] = str(src.crs) if src.crs else None
                result['driver'] = src.driver
                result['encoding'] = src.encoding
                
                # Read with geopandas for analysis
                gdf = gpd.read_file(file_path)
                result['feature_count'] = len(gdf)
                
                if gdf.empty:
                    result['errors'].append("Empty file")
                    return result
                
                # Analyze CRS
                if gdf.crs is None:
                    result['errors'].append("No CRS defined")
                else:
                    result['crs'] = gdf.crs
                    result['crs_string'] = str(gdf.crs)
                
                # Calculate bounds
                if not gdf.empty:
                    bounds = gdf.total_bounds
                    result['bounds'] = {
                        'minx': float(bounds[0]),
                        'miny': float(bounds[1]),
                        'maxx': float(bounds[2]),
                        'maxy': float(bounds[3])
                    }
                    result['total_extent'] = {
                        'width': float(bounds[2] - bounds[0]),
                        'height': float(bounds[3] - bounds[1])
                    }
                
                # Analyze geometry types
                geom_types = gdf.geometry.geom_type.value_counts().to_dict()
                result['geometry_types'] = list(geom_types.keys())
                
                # Analyze attributes
                if not gdf.empty:
                    # Get sample attributes from first feature
                    sample_row = gdf.iloc[0]
                    result['sample_attributes'] = {
                        col: str(sample_row[col])[:100]  # Truncate long values
                        for col in gdf.columns
                        if col != 'geometry'
                    }
                    
                    # Find zoning-related attributes
                    zoning_cols = []
                    for col in gdf.columns:
                        if col.lower() in ['zone', 'zoning', 'zone_code', 'zone_code', 'symbology', 'plot_categ']:
                            zoning_cols.append(col)
                            unique_vals = gdf[col].dropna().unique()
                            result['unique_zoning_values'].extend([str(v) for v in unique_vals])
                            self.zoning_attributes[col].update(unique_vals)
                            self.all_zoning_values.update(unique_vals)
                    
                    result['zoning_attributes'] = zoning_cols
                
                # Geometry validation
                valid_count = 0
                invalid_count = 0
                empty_count = 0
                fixed_count = 0
                invalid_reasons = []
                
                for idx, geom in enumerate(gdf.geometry):
                    if geom is None or geom.is_empty:
                        empty_count += 1
                        continue
                    
                    if geom.is_valid:
                        valid_count += 1
                    else:
                        invalid_count += 1
                        reason = explain_validity(geom)
                        invalid_reasons.append(f"Feature {idx}: {reason}")
                        
                        # Try to fix
                        try:
                            fixed_geom = geom.buffer(0)
                            if fixed_geom.is_valid:
                                fixed_count += 1
                        except:
                            pass
                
                result['geometry_validation'] = {
                    'valid_count': valid_count,
                    'invalid_count': invalid_count,
                    'empty_count': empty_count,
                    'fixed_count': fixed_count,
                    'invalid_reasons': invalid_reasons[:10]  # Limit to first 10
                }
                
                # Check for duplicates
                geom_hashes = []
                for geom in gdf.geometry:
                    if geom is not None and not geom.is_empty:
                        geom_hashes.append(geom.wkt)
                
                unique_geoms = set(geom_hashes)
                result['duplicates'] = len(geom_hashes) - len(unique_geoms)
                
                # Check for small geometries
                small_count = 0
                for geom in gdf.geometry:
                    if geom is not None and not geom.is_empty:
                        try:
                            area = geom.area
                            if area < 1e-10:  # Very small area threshold
                                small_count += 1
                        except:
                            pass
                
                result['small_geometries'] = small_count
                
                # Check multipart issues
                multipart_count = 0
                for geom in gdf.geometry:
                    if geom is not None and not geom.is_empty:
                        if hasattr(geom, 'geoms') and len(geom.geoms) > 1:
                            multipart_count += 1
                
                result['multipart_issues'] = multipart_count
                
        except Exception as e:
            result['errors'].append(f"Error reading file: {str(e)}")
            self.file_errors.append(f"{file_path.name}: {str(e)}")
        
        return result
    
    def analyze_all_files(self):
        """Analyze all GeoJSON files in the directory"""
        print("🔍 Analyzing Amaravati Master Plan Data Files")
        print("=" * 60)
        
        geojson_files = list(self.data_dir.glob("*.geojson"))
        
        if not geojson_files:
            print("❌ No GeoJSON files found!")
            return
        
        print(f"📁 Found {len(geojson_files)} GeoJSON files")
        print()
        
        for i, file_path in enumerate(geojson_files, 1):
            print(f"[{i:2d}/{len(geojson_files)}] Analyzing: {file_path.name}")
            
            result = self.analyze_file(file_path)
            self.analysis_results[file_path.name] = result
            
            # Print summary
            if result['errors']:
                print(f"    ❌ Errors: {', '.join(result['errors'])}")
            else:
                print(f"    ✅ {result['feature_count']} features, CRS: {result['crs_string']}")
                if result['zoning_attributes']:
                    print(f"    🏷️  Zoning attributes: {', '.join(result['zoning_attributes'])}")
                if result['unique_zoning_values']:
                    print(f"    📋 Unique values: {len(result['unique_zoning_values'])}")
        
        print()
        print("📊 Analysis Summary")
        print("=" * 60)
        
        # Overall statistics
        total_files = len(self.analysis_results)
        total_features = sum(r['feature_count'] for r in self.analysis_results.values())
        files_with_errors = sum(1 for r in self.analysis_results.values() if r['errors'])
        
        print(f"Total files analyzed: {total_files}")
        print(f"Total features: {total_features:,}")
        print(f"Files with errors: {files_with_errors}")
        print()
        
        # CRS analysis
        crs_counts = Counter(r['crs_string'] for r in self.analysis_results.values() if r['crs_string'])
        print("CRS Distribution:")
        for crs, count in crs_counts.most_common():
            print(f"  {crs}: {count} files")
        print()
        
        # Zoning attributes analysis
        print("Zoning Attributes Found:")
        for attr, values in self.zoning_attributes.items():
            print(f"  {attr}: {len(values)} unique values")
            # Show first few values
            sample_values = list(values)[:5]
            print(f"    Sample: {', '.join(str(v) for v in sample_values)}")
            if len(values) > 5:
                print(f"    ... and {len(values) - 5} more")
        print()
        
        # All unique zoning values
        print(f"All Unique Zoning Values ({len(self.all_zoning_values)}):")
        for value in sorted(self.all_zoning_values):
            print(f"  - {value}")
        print()
        
        # Geometry validation summary
        total_valid = sum(r['geometry_validation']['valid_count'] for r in self.analysis_results.values())
        total_invalid = sum(r['geometry_validation']['invalid_count'] for r in self.analysis_results.values())
        total_empty = sum(r['geometry_validation']['empty_count'] for r in self.analysis_results.values())
        total_fixed = sum(r['geometry_validation']['fixed_count'] for r in self.analysis_results.values())
        
        print("Geometry Validation Summary:")
        print(f"  Valid geometries: {total_valid:,}")
        print(f"  Invalid geometries: {total_invalid:,}")
        print(f"  Empty geometries: {total_empty:,}")
        print(f"  Auto-fixable: {total_fixed:,}")
        print()
        
        # Files with issues
        if self.file_errors:
            print("Files with Errors:")
            for error in self.file_errors:
                print(f"  ❌ {error}")
            print()
    
    def save_analysis_report(self, output_path: str = "analysis_report.json"):
        """Save detailed analysis report to JSON"""
        report = {
            'analysis_metadata': {
                'total_files': len(self.analysis_results),
                'total_features': sum(r['feature_count'] for r in self.analysis_results.values()),
                'analysis_timestamp': str(pd.Timestamp.now()),
                'data_directory': str(self.data_dir)
            },
            'file_analysis': self.analysis_results,
            'zoning_analysis': {
                'zoning_attributes': {k: list(v) for k, v in self.zoning_attributes.items()},
                'all_unique_values': list(self.all_zoning_values),
                'value_counts': dict(Counter(self.all_zoning_values))
            },
            'summary_statistics': {
                'crs_distribution': dict(Counter(r['crs_string'] for r in self.analysis_results.values() if r['crs_string'])),
                'geometry_types': dict(Counter(geom_type for r in self.analysis_results.values() for geom_type in r['geometry_types'])),
                'total_valid_geometries': sum(r['geometry_validation']['valid_count'] for r in self.analysis_results.values()),
                'total_invalid_geometries': sum(r['geometry_validation']['invalid_count'] for r in self.analysis_results.values()),
                'total_empty_geometries': sum(r['geometry_validation']['empty_count'] for r in self.analysis_results.values()),
                'total_duplicates': sum(r['duplicates'] for r in self.analysis_results.values()),
                'total_small_geometries': sum(r['small_geometries'] for r in self.analysis_results.values())
            },
            'errors': self.file_errors
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Analysis report saved to: {output_path}")
        return report

def main():
    """Main execution function"""
    # Default data directory
    data_dir = "/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping/data/andhra_pradesh/amaravati/msater_plan"
    
    if len(sys.argv) > 1:
        data_dir = sys.argv[1]
    
    if not Path(data_dir).exists():
        print(f"❌ Data directory not found: {data_dir}")
        sys.exit(1)
    
    # Create analyzer and run analysis
    analyzer = AmaravatiDataAnalyzer(data_dir)
    analyzer.analyze_all_files()
    
    # Save detailed report
    report = analyzer.save_analysis_report()
    
    # Print human-readable summary
    print("\n" + "=" * 60)
    print("🎯 KEY FINDINGS FOR TILE GENERATION")
    print("=" * 60)
    
    # Check for unmapped zoning values
    all_values = analyzer.all_zoning_values
    expected_zones = {
        'Burial Ground', 'C1 -Mixed use zone', 'C2- General commercial zone',
        'C3-Neighbourhood centre zone', 'C4-Town centre zone', 'C5-Regional centre zone',
        'C6-Central business district zone', 'Commercial Vacant', 'I1-Business park zone',
        'I2-Logistics zone', 'I3-Non polluting industry zone', 'Not Available',
        'P1-Passive zone', 'P2-Active zone', 'P3-Protected zone Hills',
        'P3-Protected zone', 'PGN-G', 'PGN-V', 'R1-Village planning zone',
        'R3-Medium to high density zone', 'R4-High density zone', 'RAA',
        'Residential Vacant', 'S2-Education zone', 'S3-Special zone',
        'SC1a-Mixed Use', 'SC1b - Mixed Use', 'SP1- Passive Zone',
        'SP2- Active Zone', 'SP3-Protected Zone', 'SR2 Low Density Housing',
        'SR4 - High Density Private', 'SS1 - Government Zone',
        'SS2a- Education Zone', 'SS2b Cultural Zone', 'SS2c Health Zone',
        'SS3 - Special Zone', 'SU1-Reserve Zone', 'SU2 - Road Network',
        'U1-Reserve zone', 'U2- Road Reserve Zone'
    }
    
    unmapped_values = all_values - expected_zones
    if unmapped_values:
        print("⚠️  UNMAPPED ZONING VALUES FOUND:")
        for value in sorted(unmapped_values):
            print(f"   - {value}")
        print("\n❌ GENERATION MUST BE ABORTED - UNMAPPED VALUES EXIST")
    else:
        print("✅ All zoning values are mapped to expected styles")
    
    # CRS analysis
    crs_info = report['summary_statistics']['crs_distribution']
    print(f"\n📍 CRS Analysis:")
    for crs, count in crs_info.items():
        print(f"   {crs}: {count} files")
    
    if 'EPSG:4326' in str(crs_info) or 'CRS84' in str(crs_info):
        print("   ✅ Files are in WGS84 - will need reprojection to EPSG:3857")
    else:
        print("   ⚠️  Unexpected CRS - check reprojection requirements")
    
    # Geometry issues
    total_invalid = report['summary_statistics']['total_invalid_geometries']
    total_features = report['analysis_metadata']['total_features']
    invalid_percentage = (total_invalid / total_features * 100) if total_features > 0 else 0
    
    print(f"\n🔧 Geometry Issues:")
    print(f"   Invalid geometries: {total_invalid:,} ({invalid_percentage:.1f}%)")
    
    if invalid_percentage > 1.0:
        print("   ⚠️  High percentage of invalid geometries - may need extensive fixing")
    else:
        print("   ✅ Geometry quality is acceptable")
    
    print(f"\n📊 Ready for tile generation: {'NO' if unmapped_values else 'YES'}")

if __name__ == "__main__":
    import pandas as pd
    main()
