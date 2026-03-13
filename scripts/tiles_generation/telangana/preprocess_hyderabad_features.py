#!/usr/bin/env python3
"""
Pre-process Hyderabad Master Plan GeoJSON files
Splits large MultiPolygons into smaller individual features for better spatial indexing
This dramatically improves tile generation performance at high zoom levels
"""

import argparse
import json
import sys
from pathlib import Path
from shapely.geometry import shape, mapping
from shapely.ops import transform

try:
    from pyproj import Transformer
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False


def split_multipolygon_to_features(multipolygon, category, filename, subdir, properties, feature_id_base):
    """
    Split a MultiPolygon into individual Polygon features
    
    Args:
        multipolygon: Shapely MultiPolygon geometry
        category: Category name
        filename: Source filename
        subdir: Source subdirectory (HMDA/HUDA)
        properties: Original feature properties
        feature_id_base: Base ID for feature numbering
        
    Returns:
        List of GeoJSON feature dictionaries
    """
    features = []
    
    if not hasattr(multipolygon, 'geoms'):
        # Single polygon, return as-is
        feature = {
            'type': 'Feature',
            'geometry': mapping(multipolygon),
            'properties': {
                **properties,
                'ORIGINAL_CATEGORY': category,
                'ORIGINAL_FILENAME': filename,
                'ORIGINAL_SUBDIR': subdir,
                'FEATURE_INDEX': 0
            }
        }
        features.append(feature)
        return features
    
    # Split MultiPolygon into individual polygons
    for idx, polygon in enumerate(multipolygon.geoms):
        if polygon.is_empty or polygon.area < 1e-10:
            continue
            
        feature = {
            'type': 'Feature',
            'geometry': mapping(polygon),
            'properties': {
                **properties,
                'ORIGINAL_CATEGORY': category,
                'ORIGINAL_FILENAME': filename,
                'ORIGINAL_SUBDIR': subdir,
                'FEATURE_INDEX': idx,
                'SPLIT_FROM_MULTIPOLYGON': True
            }
        }
        features.append(feature)
    
    return features


def process_geojson_file(input_file, output_file, subdir):
    """Process a single GeoJSON file and split MultiPolygons"""
    print(f"Processing: {input_file.name}...", end=" ", flush=True)
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Detect CRS
        crs_info = data.get('crs', {})
        source_crs = None
        needs_transform = False
        transformer = None
        
        if crs_info:
            crs_name = crs_info.get('properties', {}).get('name', '')
            if 'EPSG:3857' in crs_name or '3857' in crs_name:
                source_crs = 'EPSG:3857'
            elif 'EPSG:4326' in crs_name or '4326' in crs_name:
                source_crs = 'EPSG:4326'
        
        if source_crs and source_crs != 'EPSG:4326' and HAS_PYPROJ:
            try:
                transformer = Transformer.from_crs(source_crs, 'EPSG:4326', always_xy=True)
                needs_transform = True
            except:
                needs_transform = False
        
        # Process features
        original_features = data.get('features', [])
        new_features = []
        total_split = 0
        
        for orig_feat in original_features:
            try:
                geom = shape(orig_feat['geometry'])
                
                # Transform if needed
                if needs_transform and transformer:
                    def transform_func(x, y, z=None):
                        result = transformer.transform(x, y)
                        if z is not None:
                            return (result[0], result[1], z)
                        return result
                    geom = transform(transform_func, geom)
                
                if not geom.is_valid:
                    geom = geom.buffer(0)
                
                if geom.is_empty:
                    continue
                
                # Get category
                props = orig_feat.get('properties', {})
                category = (
                    props.get("LANDUSE_CATEGORY")
                    or props.get("CATEGORY")
                    or props.get("Name")
                    or props.get("name")
                    or props.get("LAYER")
                    or input_file.stem.upper()
                )
                
                filename = input_file.stem
                
                # Split MultiPolygon into individual features
                split_features = split_multipolygon_to_features(
                    geom, category, filename, subdir, props, len(new_features)
                )
                
                new_features.extend(split_features)
                if len(split_features) > 1:
                    total_split += len(split_features) - 1
                
            except Exception as e:
                print(f"\n⚠️  Error processing feature: {e}")
                continue
        
        # Create output GeoJSON
        output_data = {
            'type': 'FeatureCollection',
            'crs': {
                'type': 'name',
                'properties': {'name': 'urn:ogc:def:crs:EPSG::4326'}
            },
            'features': new_features
        }
        
        # Write output
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, separators=(',', ':'))
        
        print(f"✓ {len(original_features)} → {len(new_features)} features (+{total_split} split)")
        return len(new_features), total_split
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return 0, 0


def main():
    """Main preprocessing function"""
    parser = argparse.ArgumentParser(description='Preprocess Hyderabad master plan GeoJSON (split MultiPolygons)')
    parser.add_argument(
        '--input-dir', '-i',
        default='data/telangana/hyderabad/masterplan',
        help='Input directory containing HMDA/ and HUDA/ with .geojson and legend.csv',
    )
    parser.add_argument(
        '--output-dir', '-o',
        default='data/telangana/hyderabad/master_plan_split',
        help='Output directory for pre-split GeoJSON and copied legends',
    )
    args = parser.parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        print(f"✗ Input directory not found: {input_dir}")
        sys.exit(1)
    
    print("="*80)
    print("HYDERABAD MASTER PLAN - FEATURE PREPROCESSING")
    print("Splitting MultiPolygons into individual features")
    print("="*80)
    print(f"Input:  {input_dir}")
    print(f"Output: {output_dir}\n")
    
    total_files = 0
    total_features_before = 0
    total_features_after = 0
    total_split = 0
    
    for subdir in ['HMDA', 'HUDA']:
        input_subdir = input_dir / subdir
        output_subdir = output_dir / subdir
        
        if not input_subdir.exists():
            print(f"⚠️  Subdirectory not found: {input_subdir}")
            continue
        
        # Copy legend.csv if it exists
        legend_file = input_subdir / 'legend.csv'
        if legend_file.exists():
            output_subdir.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(legend_file, output_subdir / 'legend.csv')
            print(f"📋 Copied {subdir}/legend.csv")
        
        # Process GeoJSON files
        geojson_files = sorted(input_subdir.glob('*.geojson'))
        
        for geojson_file in geojson_files:
            total_files += 1
            output_file = output_subdir / geojson_file.name
            
            # Count original features
            try:
                with open(geojson_file, 'r', encoding='utf-8') as f:
                    orig_data = json.load(f)
                    orig_count = len(orig_data.get('features', []))
                    total_features_before += orig_count
            except:
                orig_count = 0
            
            new_count, split_count = process_geojson_file(
                geojson_file, output_file, subdir
            )
            total_features_after += new_count
            total_split += split_count
    
    print(f"\n{'='*80}")
    print(f"PREPROCESSING COMPLETE")
    print(f"{'='*80}")
    print(f"Files processed: {total_files}")
    print(f"Features before: {total_features_before:,}")
    print(f"Features after:  {total_features_after:,}")
    print(f"Features created: {total_split:,}")
    print(f"Improvement: {total_features_after/total_features_before:.1f}x more features")
    print(f"\n✓ Preprocessed files saved to: {output_dir}")
    print(f"\n💡 Next step: Use hyderabad_masterplan_tile_generator_optimized.py")
    print(f"   with data_dir='{output_dir}'")


if __name__ == '__main__':
    main()
