#!/usr/bin/env python3
"""
Comprehensive Analysis of Visakhapatnam Master Plan GeoJSON Files for Tile Generation
Analyzes all layers to determine optimal tile generation parameters.
"""

import json
import os
import sys
from pathlib import Path
from collections import defaultdict
import math

def calculate_bbox(coordinates, geom_type):
    """Calculate bounding box from coordinates"""
    def flatten_coords(coords, depth=0):
        """Recursively flatten coordinates"""
        flat = []
        if isinstance(coords[0], (int, float)):
            return [coords]
        for item in coords:
            if isinstance(item[0], (int, float)):
                flat.append(item)
            else:
                flat.extend(flatten_coords(item, depth + 1))
        return flat
    
    flat_coords = flatten_coords(coordinates)
    if not flat_coords:
        return None
    
    lons = [c[0] for c in flat_coords]
    lats = [c[1] for c in flat_coords]
    
    return {
        'min_lon': min(lons),
        'max_lon': max(lons),
        'min_lat': min(lats),
        'max_lat': max(lats)
    }

def merge_bbox(bbox1, bbox2):
    """Merge two bounding boxes"""
    if bbox1 is None:
        return bbox2
    if bbox2 is None:
        return bbox1
    
    return {
        'min_lon': min(bbox1['min_lon'], bbox2['min_lon']),
        'max_lon': max(bbox1['max_lon'], bbox2['max_lon']),
        'min_lat': min(bbox1['min_lat'], bbox2['min_lat']),
        'max_lat': max(bbox1['max_lat'], bbox2['max_lat'])
    }

def lat_lon_to_tile(lat, lon, zoom):
    """Convert latitude/longitude to tile coordinates"""
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(math.radians(lat)) + 
            (1 / math.cos(math.radians(lat)))) / math.pi) / 2.0 * n)
    return x, y

def analyze_geojson_file(filepath):
    """Analyze a single GeoJSON file"""
    print(f"\n{'='*80}")
    print(f"Analyzing: {filepath.name}")
    print(f"{'='*80}")
    
    file_size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"File Size: {file_size_mb:.2f} MB")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            print("Loading GeoJSON data...")
            data = json.load(f)
        
        # Basic info
        feature_collection_type = data.get('type', 'N/A')
        name = data.get('name', filepath.stem)
        crs = data.get('crs', {})
        crs_name = crs.get('properties', {}).get('name', 'N/A')
        
        print(f"\nBasic Information:")
        print(f"  Type: {feature_collection_type}")
        print(f"  Name: {name}")
        print(f"  CRS: {crs_name}")
        
        # Features analysis
        features = data.get('features', [])
        feature_count = len(features)
        print(f"\nFeature Count: {feature_count:,}")
        
        if feature_count == 0:
            print("  No features found!")
            return None
        
        # Analyze features
        geometry_types = defaultdict(int)
        property_keys = set()
        total_coordinates = 0
        overall_bbox = None
        
        print(f"\nAnalyzing all {feature_count:,} features...")
        
        for idx, feature in enumerate(features):
            if (idx + 1) % 1000 == 0:
                print(f"  Processed {idx + 1:,} features...")
            
            # Geometry type
            geometry = feature.get('geometry', {})
            geom_type = geometry.get('type', 'Unknown')
            geometry_types[geom_type] += 1
            
            # Properties
            properties = feature.get('properties', {})
            property_keys.update(properties.keys())
            
            # Bounding box
            coordinates = geometry.get('coordinates', [])
            if coordinates:
                feature_bbox = calculate_bbox(coordinates, geom_type)
                overall_bbox = merge_bbox(overall_bbox, feature_bbox)
                
                # Count coordinates
                def count_coords(coords):
                    if isinstance(coords[0], (int, float)):
                        return 1
                    return sum(count_coords(c) for c in coords)
                total_coordinates += count_coords(coordinates)
        
        print(f"\nGeometry Types:")
        for geom_type, count in sorted(geometry_types.items()):
            percentage = (count / feature_count) * 100
            print(f"  {geom_type}: {count:,} ({percentage:.1f}%)")
        
        print(f"\nTotal Coordinate Points: {total_coordinates:,}")
        print(f"Average Points per Feature: {total_coordinates / feature_count:.1f}")
        
        print(f"\nProperties/Attributes ({len(property_keys)} unique):")
        for key in sorted(property_keys)[:15]:
            print(f"  - {key}")
        if len(property_keys) > 15:
            print(f"  ... and {len(property_keys) - 15} more")
        
        if overall_bbox:
            print(f"\nBounding Box:")
            print(f"  Min Longitude: {overall_bbox['min_lon']:.6f}")
            print(f"  Max Longitude: {overall_bbox['max_lon']:.6f}")
            print(f"  Min Latitude: {overall_bbox['min_lat']:.6f}")
            print(f"  Max Latitude: {overall_bbox['max_lat']:.6f}")
            
            width = overall_bbox['max_lon'] - overall_bbox['min_lon']
            height = overall_bbox['max_lat'] - overall_bbox['min_lat']
            print(f"  Width: {width:.6f} degrees ({width * 111:.2f} km approx)")
            print(f"  Height: {height:.6f} degrees ({height * 111:.2f} km approx)")
            
            center_lon = (overall_bbox['min_lon'] + overall_bbox['max_lon']) / 2
            center_lat = (overall_bbox['min_lat'] + overall_bbox['max_lat']) / 2
            print(f"  Center: [{center_lon:.6f}, {center_lat:.6f}]")
            
            # Calculate tile ranges for different zoom levels
            print(f"\nTile Ranges for Different Zoom Levels:")
            for zoom in [10, 12, 14, 16, 18]:
                min_x, max_y = lat_lon_to_tile(overall_bbox['min_lat'], overall_bbox['min_lon'], zoom)
                max_x, min_y = lat_lon_to_tile(overall_bbox['max_lat'], overall_bbox['max_lon'], zoom)
                
                tile_count_x = max_x - min_x + 1
                tile_count_y = max_y - min_y + 1
                total_tiles = tile_count_x * tile_count_y
                
                print(f"  Zoom {zoom:2d}: X=[{min_x:5d}-{max_x:5d}], Y=[{min_y:5d}-{max_y:5d}] " +
                      f"→ {tile_count_x}×{tile_count_y} = {total_tiles:,} tiles")
        
        # Sample feature properties
        if features:
            print(f"\nSample Feature Properties (first feature):")
            sample_props = features[0].get('properties', {})
            for key, value in list(sample_props.items())[:10]:
                print(f"  {key}: {value}")
        
        return {
            'filename': filepath.name,
            'file_size_mb': file_size_mb,
            'feature_count': feature_count,
            'geometry_types': dict(geometry_types),
            'property_keys': sorted(property_keys),
            'total_coordinates': total_coordinates,
            'bbox': overall_bbox,
            'crs': crs_name
        }
        
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON format - {e}")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_summary_report(all_results):
    """Generate a summary report of all files"""
    print(f"\n\n{'#'*80}")
    print(f"{'#'*80}")
    print(f"{'VISAKHAPATNAM MASTER PLAN - COMPREHENSIVE SUMMARY':^80}")
    print(f"{'#'*80}")
    print(f"{'#'*80}\n")
    
    valid_results = [r for r in all_results if r is not None]
    
    if not valid_results:
        print("No valid results to summarize.")
        return
    
    # Overall statistics
    total_features = sum(r['feature_count'] for r in valid_results)
    total_size = sum(r['file_size_mb'] for r in valid_results)
    total_files = len(valid_results)
    
    print(f"Total Files Analyzed: {total_files}")
    print(f"Total File Size: {total_size:.2f} MB")
    print(f"Total Features: {total_features:,}")
    print(f"Average Features per File: {total_features / total_files:,.0f}")
    
    # Calculate overall bounding box
    overall_bbox = None
    for result in valid_results:
        if result['bbox']:
            overall_bbox = merge_bbox(overall_bbox, result['bbox'])
    
    if overall_bbox:
        print(f"\nOverall Coverage Area:")
        print(f"  Min Longitude: {overall_bbox['min_lon']:.6f}")
        print(f"  Max Longitude: {overall_bbox['max_lon']:.6f}")
        print(f"  Min Latitude: {overall_bbox['min_lat']:.6f}")
        print(f"  Max Latitude: {overall_bbox['max_lat']:.6f}")
        
        center_lon = (overall_bbox['min_lon'] + overall_bbox['max_lon']) / 2
        center_lat = (overall_bbox['min_lat'] + overall_bbox['max_lat']) / 2
        print(f"  Center: [{center_lon:.6f}, {center_lat:.6f}]")
        
        width = overall_bbox['max_lon'] - overall_bbox['min_lon']
        height = overall_bbox['max_lat'] - overall_bbox['min_lat']
        print(f"  Area: {width:.4f}° × {height:.4f}° (~{width*111:.1f}km × {height*111:.1f}km)")
    
    # Files by size
    print(f"\nFiles by Size (Top 15):")
    sorted_by_size = sorted(valid_results, key=lambda x: x['file_size_mb'], reverse=True)
    for i, result in enumerate(sorted_by_size[:15], 1):
        print(f"  {i:2d}. {result['filename']:60s} - {result['file_size_mb']:8.2f} MB - {result['feature_count']:8,} features")
    
    # Files by feature count
    print(f"\nFiles by Feature Count (Top 15):")
    sorted_by_features = sorted(valid_results, key=lambda x: x['feature_count'], reverse=True)
    for i, result in enumerate(sorted_by_features[:15], 1):
        print(f"  {i:2d}. {result['filename']:60s} - {result['feature_count']:8,} features")
    
    # All geometry types
    all_geom_types = defaultdict(int)
    for result in valid_results:
        for geom_type, count in result['geometry_types'].items():
            all_geom_types[geom_type] += count
    
    print(f"\nGeometry Types Across All Files:")
    for geom_type, count in sorted(all_geom_types.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_features) * 100
        print(f"  {geom_type}: {count:,} ({percentage:.1f}%)")
    
    # Categorize layers
    print(f"\n{'='*80}")
    print(f"LAYER CATEGORIES")
    print(f"{'='*80}\n")
    
    categories = {
        'Existing Facilities': [],
        'Proposed Development': [],
        'Environmental/Protected': [],
        'Use Zones': [],
        'Infrastructure': []
    }
    
    for result in valid_results:
        name = result['filename'].replace('.geojson', '')
        if name.startswith('Existing_'):
            categories['Existing Facilities'].append(name)
        elif name.startswith('Proposed_'):
            categories['Proposed Development'].append(name)
        elif any(x in name for x in ['Blue_Zone', 'Brown_Zone', 'Green_Zone', 'Sanctuary', 'Eco_Sensitive', 'Forest', 'Water_Body_Buffer']):
            categories['Environmental/Protected'].append(name)
        elif name.endswith('_Use_Zone') or 'Mixed_Use' in name:
            categories['Use Zones'].append(name)
        else:
            categories['Infrastructure'].append(name)
    
    for category, layers in categories.items():
        if layers:
            print(f"{category} ({len(layers)} layers):")
            for layer in sorted(layers):
                print(f"  - {layer}")
            print()
    
    # Tile generation recommendations
    print(f"\n{'='*80}")
    print(f"TILE GENERATION RECOMMENDATIONS")
    print(f"{'='*80}\n")
    
    if overall_bbox:
        print(f"1. BOUNDING BOX:")
        print(f"   BBOX = [{overall_bbox['min_lon']:.6f}, {overall_bbox['min_lat']:.6f}, " +
              f"{overall_bbox['max_lon']:.6f}, {overall_bbox['max_lat']:.6f}]")
        
        print(f"\n2. CENTER COORDINATES:")
        print(f"   CENTER = [{center_lon:.6f}, {center_lat:.6f}]")
        
        print(f"\n3. RECOMMENDED ZOOM LEVELS:")
        print(f"   - Overview: Zoom 10-12 (city-wide view)")
        print(f"   - Standard: Zoom 13-15 (neighborhood detail)")
        print(f"   - Detailed: Zoom 16-18 (plot/parcel level)")
        
        print(f"\n4. ESTIMATED TILE COUNTS:")
        for zoom in [10, 12, 14, 16, 18]:
            min_x, max_y = lat_lon_to_tile(overall_bbox['min_lat'], overall_bbox['min_lon'], zoom)
            max_x, min_y = lat_lon_to_tile(overall_bbox['max_lat'], overall_bbox['max_lon'], zoom)
            tile_count = (max_x - min_x + 1) * (max_y - min_y + 1)
            print(f"   Zoom {zoom}: ~{tile_count:,} tiles")
        
        print(f"\n5. LAYER ORGANIZATION:")
        print(f"   Total Layers: {len(valid_results)}")
        print(f"   Existing facilities: {len(categories['Existing Facilities'])}")
        print(f"   Proposed development: {len(categories['Proposed Development'])}")
        print(f"   Environmental: {len(categories['Environmental/Protected'])}")
        print(f"   Use zones: {len(categories['Use Zones'])}")
        
        print(f"\n6. DATA CHARACTERISTICS:")
        print(f"   - Total Features: {total_features:,}")
        print(f"   - Average Complexity: {sum(r['total_coordinates'] for r in valid_results) / total_features:.1f} coords/feature")
        
        print(f"\n7. COMPLEXITY NOTES:")
        complexity_high = [r for r in valid_results if r['total_coordinates'] / max(r['feature_count'], 1) > 100]
        if complexity_high:
            print(f"   High-complexity layers ({len(complexity_high)} files):")
            for r in sorted(complexity_high, key=lambda x: x['total_coordinates'] / x['feature_count'], reverse=True)[:10]:
                avg_pts = r['total_coordinates'] / r['feature_count']
                print(f"     - {r['filename']}: {avg_pts:.0f} pts/feature")
        
        print(f"\n8. COASTAL CITY CONSIDERATIONS:")
        print(f"   - Sea/River boundaries may have complex coastlines")
        print(f"   - Eco-sensitive zones require careful rendering")
        print(f"   - Wildlife sanctuary needs special attention")
        print(f"   - Port and coastal infrastructure present")

def main():
    """Main analysis function"""
    base_path = Path("/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping")
    data_path = base_path / "data" / "andhra_pradesh" / "visakhapatnam" / "master_plan"
    
    if not data_path.exists():
        print(f"ERROR: Directory not found: {data_path}")
        sys.exit(1)
    
    print(f"Analyzing GeoJSON files in: {data_path}")
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
        result = analyze_geojson_file(filepath)
        all_results.append(result)
    
    # Generate summary report
    generate_summary_report(all_results)
    
    print(f"\n{'='*80}")
    print("Analysis Complete!")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()

