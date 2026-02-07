#!/usr/bin/env python3
"""
Amaravati Master Plan - Smallest Feature Analysis for Tile Generation
======================================================================

This script analyzes all GeoJSON files in data/andhra_pradesh/amaravati/master_plan/
and finds the smallest feature in each file. The output is structured for tile generation
planning.

Usage:
    python3 analyze_amaravati_smallest_features.py
"""

import json
import os
import sys
from pathlib import Path
from collections import defaultdict
import math


def calculate_feature_area(feature):
    """
    Calculate approximate area of a feature using bounding box.
    Returns area in square degrees (approximate).
    """
    geometry = feature.get('geometry', {})
    if not geometry:
        return float('inf')
    
    geom_type = geometry.get('type', '')
    coordinates = geometry.get('coordinates', [])
    
    if not coordinates:
        return float('inf')
    
    def flatten_coords(coords):
        """Recursively flatten coordinates"""
        flat = []
        if isinstance(coords[0], (int, float)):
            return [coords]
        for item in coords:
            if isinstance(item[0], (int, float)):
                flat.append(item)
            else:
                flat.extend(flatten_coords(item))
        return flat
    
    def get_bbox_area(coords):
        """Calculate bounding box area"""
        if not coords:
            return float('inf')
        flat_coords = flatten_coords(coords)
        lons = [c[0] for c in flat_coords if len(c) >= 2]
        lats = [c[1] for c in flat_coords if len(c) >= 2]
        if not lons or not lats:
            return float('inf')
        
        width = max(lons) - min(lons)
        height = max(lats) - min(lats)
        return width * height
    
    if geom_type in ['Polygon', 'MultiPolygon']:
        if geom_type == 'Polygon':
            return get_bbox_area(coordinates)
        elif geom_type == 'MultiPolygon':
            # Return minimum area across all polygons
            min_area = float('inf')
            for polygon in coordinates:
                if polygon:
                    area = get_bbox_area(polygon[0] if isinstance(polygon[0][0], (int, float)) else polygon)
                    min_area = min(min_area, area)
            return min_area
    
    # For Point and LineString, return a very small value (they appear in tiles but have no area)
    elif geom_type in ['Point', 'LineString', 'MultiLineString', 'MultiPoint']:
        return get_bbox_area(coordinates)
    
    return float('inf')


def calculate_feature_bbox(feature):
    """Calculate bounding box for a feature"""
    geometry = feature.get('geometry', {})
    if not geometry:
        return None
    
    coordinates = geometry.get('coordinates', [])
    if not coordinates:
        return None
    
    def flatten_coords(coords):
        """Recursively flatten coordinates"""
        flat = []
        if isinstance(coords[0], (int, float)):
            return [coords]
        for item in coords:
            if isinstance(item[0], (int, float)):
                flat.append(item)
            else:
                flat.extend(flatten_coords(item))
        return flat
    
    flat_coords = flatten_coords(coordinates)
    if not flat_coords:
        return None
    
    lons = [c[0] for c in flat_coords if len(c) >= 2]
    lats = [c[1] for c in flat_coords if len(c) >= 2]
    
    if not lons or not lats:
        return None
    
    return {
        'min_lon': min(lons),
        'max_lon': max(lons),
        'min_lat': min(lats),
        'max_lat': max(lats)
    }


def lat_lon_to_tile(lat, lon, zoom):
    """Convert latitude/longitude to tile coordinates"""
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(math.radians(lat)) + 
            (1 / math.cos(math.radians(lat)))) / math.pi) / 2.0 * n)
    return x, y


def analyze_file_for_smallest_feature(filepath):
    """
    Analyze a GeoJSON file and find the smallest feature.
    Returns analysis result with smallest feature sample.
    """
    print(f"\n{'='*80}")
    print(f"Analyzing: {filepath.name}")
    print(f"{'='*80}")
    
    file_size_mb = filepath.stat().st_size / (1024 * 1024)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        features = data.get('features', [])
        feature_count = len(features)
        
        print(f"File Size: {file_size_mb:.2f} MB")
        print(f"Feature Count: {feature_count:,}")
        
        if feature_count == 0:
            print("  ⚠️  No features found!")
            return None
        
        # Find smallest feature
        smallest_feature = None
        smallest_area = float('inf')
        smallest_index = -1
        
        print(f"Scanning {feature_count:,} features for smallest...")
        
        for idx, feature in enumerate(features):
            area = calculate_feature_area(feature)
            if area < smallest_area:
                smallest_area = area
                smallest_feature = feature
                smallest_index = idx
        
        if smallest_feature is None:
            print("  ⚠️  Could not find smallest feature!")
            return None
        
        # Calculate bbox for smallest feature
        bbox = calculate_feature_bbox(smallest_feature)
        
        # Calculate tile info
        tile_info = {}
        if bbox:
            center_lon = (bbox['min_lon'] + bbox['max_lon']) / 2
            center_lat = (bbox['min_lat'] + bbox['max_lat']) / 2
            width_deg = bbox['max_lon'] - bbox['min_lon']
            height_deg = bbox['max_lat'] - bbox['min_lat']
            
            # Estimate which zoom levels this feature appears in
            # Feature should appear in tiles where its size is visible
            # Rough estimate: feature should be at least 1 pixel in tile
            
            tile_info = {
                'center': [center_lon, center_lat],
                'bbox': bbox,
                'width_deg': width_deg,
                'height_deg': height_deg,
                'width_km': width_deg * 111,
                'height_km': height_deg * 111,
            }
            
            # Calculate tiles for different zoom levels
            zoom_tiles = {}
            for zoom in [10, 12, 14, 16, 18]:
                min_x, max_y = lat_lon_to_tile(bbox['min_lat'], bbox['min_lon'], zoom)
                max_x, min_y = lat_lon_to_tile(bbox['max_lat'], bbox['max_lon'], zoom)
                zoom_tiles[zoom] = {
                    'tile_x': (min_x + max_x) // 2,
                    'tile_y': (min_y + max_y) // 2,
                    'tile_range': {
                        'x': [min_x, max_x],
                        'y': [min_y, max_y]
                    }
                }
            tile_info['tiles'] = zoom_tiles
        
        geometry_type = smallest_feature.get('geometry', {}).get('type', 'Unknown')
        properties = smallest_feature.get('properties', {})
        
        print(f"\nSmallest Feature Found (Index: {smallest_index}):")
        print(f"  Geometry Type: {geometry_type}")
        print(f"  Approximate Area: {smallest_area:.10f} square degrees")
        if bbox:
            print(f"  BBox: [{bbox['min_lon']:.6f}, {bbox['min_lat']:.6f}, "
                  f"{bbox['max_lon']:.6f}, {bbox['max_lat']:.6f}]")
            print(f"  Size: {tile_info['width_km']:.4f} km × {tile_info['height_km']:.4f} km")
            print(f"  Center: [{tile_info['center'][0]:.6f}, {tile_info['center'][1]:.6f}]")
        
        print(f"\nProperties:")
        for key, value in list(properties.items())[:10]:
            print(f"  {key}: {value}")
        
        result = {
            'filename': filepath.name,
            'file_size_mb': file_size_mb,
            'total_features': feature_count,
            'smallest_feature': {
                'index': smallest_index,
                'geometry_type': geometry_type,
                'area_approx_sq_deg': smallest_area,
                'feature_sample': {
                    'type': smallest_feature.get('type', 'Feature'),
                    'geometry': smallest_feature.get('geometry'),
                    'properties': properties
                },
                'bbox': bbox,
                'tile_info': tile_info
            }
        }
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON format - {e}")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_tile_generation_config(all_results):
    """Generate configuration useful for tile generation"""
    print(f"\n\n{'#'*80}")
    print(f"{'TILE GENERATION CONFIGURATION'}")
    print(f"{'#'*80}\n")
    
    valid_results = [r for r in all_results if r is not None]
    
    if not valid_results:
        print("No valid results to generate configuration.")
        return
    
    # Calculate overall bounds
    all_min_lon = min(r['smallest_feature']['bbox']['min_lon'] 
                      for r in valid_results if r['smallest_feature']['bbox'])
    all_max_lon = max(r['smallest_feature']['bbox']['max_lon'] 
                      for r in valid_results if r['smallest_feature']['bbox'])
    all_min_lat = min(r['smallest_feature']['bbox']['min_lat'] 
                      for r in valid_results if r['smallest_feature']['bbox'])
    all_max_lat = max(r['smallest_feature']['bbox']['max_lat'] 
                      for r in valid_results if r['smallest_feature']['bbox'])
    
    print("1. OVERALL BOUNDING BOX:")
    print(f"   BBOX = [{all_min_lon:.6f}, {all_min_lat:.6f}, {all_max_lon:.6f}, {all_max_lat:.6f}]")
    
    center_lon = (all_min_lon + all_max_lon) / 2
    center_lat = (all_min_lat + all_max_lat) / 2
    print(f"   CENTER = [{center_lon:.6f}, {center_lat:.6f}]")
    
    print("\n2. SMALLEST FEATURES SUMMARY:")
    print(f"   Total Files: {len(valid_results)}")
    
    # Find overall smallest feature
    overall_smallest = min(valid_results, 
                          key=lambda x: x['smallest_feature']['area_approx_sq_deg'])
    
    print(f"\n   Overall Smallest Feature:")
    print(f"   - File: {overall_smallest['filename']}")
    print(f"   - Area: {overall_smallest['smallest_feature']['area_approx_sq_deg']:.10f} sq deg")
    print(f"   - Size: {overall_smallest['smallest_feature']['tile_info']['width_km']:.4f} km × "
          f"{overall_smallest['smallest_feature']['tile_info']['height_km']:.4f} km")
    
    print("\n3. RECOMMENDED MINIMUM ZOOM LEVELS:")
    # Estimate minimum zoom where smallest features are visible
    min_feature_width_km = min(r['smallest_feature']['tile_info']['width_km'] 
                               for r in valid_results 
                               if r['smallest_feature']['tile_info'])
    
    # At zoom 18, 1 tile ≈ 0.15 km
    # At zoom 16, 1 tile ≈ 0.6 km
    # At zoom 14, 1 tile ≈ 2.4 km
    
    if min_feature_width_km < 0.1:
        print("   - Minimum Zoom: 18 (for smallest features)")
    elif min_feature_width_km < 0.5:
        print("   - Minimum Zoom: 16-17 (for smallest features)")
    elif min_feature_width_km < 2.0:
        print("   - Minimum Zoom: 14-15 (for smallest features)")
    else:
        print("   - Minimum Zoom: 12-13 (for smallest features)")
    
    print("\n4. FEATURE SAMPLES BY FILE:")
    for result in sorted(valid_results, key=lambda x: x['filename']):
        sf = result['smallest_feature']
        print(f"\n   {result['filename']}:")
        print(f"      - Index: {sf['index']}")
        print(f"      - Type: {sf['geometry_type']}")
        print(f"      - Area: {sf['area_approx_sq_deg']:.10f} sq deg")
        if sf['bbox']:
            print(f"      - BBox: [{sf['bbox']['min_lon']:.6f}, {sf['bbox']['min_lat']:.6f}, "
                  f"{sf['bbox']['max_lon']:.6f}, {sf['bbox']['max_lat']:.6f}]")


def save_results_json(all_results, output_path):
    """Save analysis results to JSON file"""
    output_file = Path(output_path)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Results saved to: {output_file}")


def save_feature_samples_json(all_results, output_path):
    """Save only the smallest feature samples to a JSON file"""
    samples = {}
    for result in all_results:
        if result and result['smallest_feature']:
            samples[result['filename']] = result['smallest_feature']['feature_sample']
    
    output_file = Path(output_path)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"✅ Feature samples saved to: {output_file}")


def main():
    """Main analysis function"""
    # Get the script directory and project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent if script_dir.name == 'scripts' else script_dir.parent
    
    data_path = project_root / "data" / "andhra_pradesh" / "amaravati" / "master_plan"
    
    if not data_path.exists():
        print(f"ERROR: Directory not found: {data_path}")
        sys.exit(1)
    
    print(f"{'='*80}")
    print(f"AMARAVATI MASTER PLAN - SMALLEST FEATURE ANALYSIS")
    print(f"{'='*80}")
    print(f"\nAnalyzing GeoJSON files in: {data_path}")
    print(f"{'='*80}\n")
    
    # Find all GeoJSON files
    geojson_files = sorted(data_path.glob("*.geojson"))
    
    if not geojson_files:
        print("No GeoJSON files found!")
        sys.exit(1)
    
    print(f"Found {len(geojson_files)} GeoJSON files:\n")
    for i, filepath in enumerate(geojson_files, 1):
        print(f"{i:2d}. {filepath.name}")
    
    # Analyze each file
    all_results = []
    for filepath in geojson_files:
        result = analyze_file_for_smallest_feature(filepath)
        all_results.append(result)
    
    # Generate tile generation configuration
    generate_tile_generation_config(all_results)
    
    # Save results
    output_dir = project_root
    save_results_json(all_results, output_dir / "amaravati_smallest_features_analysis.json")
    save_feature_samples_json(all_results, output_dir / "amaravati_smallest_features_samples.json")
    
    print(f"\n{'='*80}")
    print("Analysis Complete!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
