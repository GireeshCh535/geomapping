#!/usr/bin/env python3
"""
Bangalore Metro Data Analysis Script
Analyzes the GeoJSON data for Bangalore Metro
"""

import json
import geopandas as gpd
import pandas as pd
from pathlib import Path
from shapely.geometry import shape, LineString, MultiLineString
from collections import Counter

def analyze_bangalore_metro():
    """Comprehensive analysis of Bangalore Metro data"""
    
    # Path to the data
    data_path = Path("/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping/data/karnataka/bengaluru/metro/Bangalore Metro Phases 1,2,2A&2B.geojson")
    
    print("=" * 80)
    print("BANGALORE METRO DATA ANALYSIS")
    print("=" * 80)
    print(f"\nData file: {data_path.name}")
    print(f"File size: {data_path.stat().st_size / 1024:.2f} KB\n")
    
    # Load GeoJSON with geopandas
    gdf = gpd.read_file(data_path)
    
    print("=" * 80)
    print("1. BASIC INFORMATION")
    print("=" * 80)
    print(f"Total features: {len(gdf)}")
    print(f"Coordinate Reference System (CRS): {gdf.crs}")
    print(f"Geometry types: {gdf.geometry.geom_type.value_counts().to_dict()}")
    
    # Get bounds
    bounds = gdf.total_bounds
    print(f"\nBounding Box:")
    print(f"  West:  {bounds[0]:.6f}")
    print(f"  South: {bounds[1]:.6f}")
    print(f"  East:  {bounds[2]:.6f}")
    print(f"  North: {bounds[3]:.6f}")
    
    print("\n" + "=" * 80)
    print("2. COLUMN/ATTRIBUTE ANALYSIS")
    print("=" * 80)
    print(f"Columns: {list(gdf.columns)}\n")
    
    # Analyze each column
    for col in gdf.columns:
        if col != 'geometry':
            print(f"\n{col}:")
            if gdf[col].dtype == 'object':
                value_counts = gdf[col].value_counts()
                print(f"  Unique values: {len(value_counts)}")
                if len(value_counts) <= 20:
                    for value, count in value_counts.items():
                        print(f"    - {value}: {count}")
                else:
                    print(f"  Top 10 values:")
                    for value, count in value_counts.head(10).items():
                        print(f"    - {value}: {count}")
            else:
                print(f"  Type: {gdf[col].dtype}")
                print(f"  Non-null count: {gdf[col].count()}")
                if gdf[col].dtype in ['int64', 'float64']:
                    print(f"  Min: {gdf[col].min()}")
                    print(f"  Max: {gdf[col].max()}")
    
    print("\n" + "=" * 80)
    print("3. GEOMETRY ANALYSIS")
    print("=" * 80)
    
    # Calculate lengths
    gdf_metric = gdf.to_crs('EPSG:32643')  # WGS 84 / UTM zone 43N (for Bangalore)
    gdf['length_km'] = gdf_metric.geometry.length / 1000
    
    print(f"\nTotal line length: {gdf['length_km'].sum():.2f} km")
    print(f"Average segment length: {gdf['length_km'].mean():.2f} km")
    print(f"Longest segment: {gdf['length_km'].max():.2f} km")
    print(f"Shortest segment: {gdf['length_km'].min():.2f} km")
    
    # Analyze by phase if available
    phase_columns = [col for col in gdf.columns if 'phase' in col.lower() or 'line' in col.lower() or 'corridor' in col.lower()]
    
    if phase_columns:
        print("\n" + "=" * 80)
        print("4. PHASE/LINE BREAKDOWN")
        print("=" * 80)
        for col in phase_columns:
            print(f"\nBy {col}:")
            for value in gdf[col].unique():
                if pd.notna(value):
                    subset = gdf[gdf[col] == value]
                    total_length = subset['length_km'].sum()
                    print(f"  {value}: {len(subset)} segments, {total_length:.2f} km")
    
    print("\n" + "=" * 80)
    print("5. SAMPLE FEATURES (First 5)")
    print("=" * 80)
    
    # Show sample features
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', 50)
    
    sample_df = gdf.drop(columns=['geometry']).head(5)
    print(sample_df.to_string(index=True))
    
    # Check for stations (if point geometries exist or station attributes)
    print("\n" + "=" * 80)
    print("6. STATION INFORMATION")
    print("=" * 80)
    
    station_columns = [col for col in gdf.columns if 'station' in col.lower()]
    if station_columns:
        print(f"Station-related columns found: {station_columns}")
        for col in station_columns:
            unique_stations = gdf[col].dropna().unique()
            print(f"\n{col}: {len(unique_stations)} unique values")
            if len(unique_stations) <= 50:
                print(f"Stations: {', '.join(map(str, unique_stations))}")
    else:
        print("No explicit station columns found in line data.")
    
    # Color/styling information
    print("\n" + "=" * 80)
    print("7. COLOR/STYLING INFORMATION")
    print("=" * 80)
    
    color_columns = [col for col in gdf.columns if 'color' in col.lower() or 'colour' in col.lower()]
    if color_columns:
        for col in color_columns:
            print(f"\n{col}:")
            for value, count in gdf[col].value_counts().items():
                print(f"  {value}: {count}")
    else:
        print("No color columns found.")
    
    # Save summary to file
    print("\n" + "=" * 80)
    print("8. EXPORTING DETAILED SUMMARY")
    print("=" * 80)
    
    output_file = Path("/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping/bangalore_metro_analysis_output.txt")
    
    with open(output_file, 'w') as f:
        f.write("BANGALORE METRO DATA ANALYSIS - DETAILED SUMMARY\n")
        f.write("=" * 80 + "\n\n")
        
        # Write all feature details
        f.write("COMPLETE FEATURE LIST:\n")
        f.write("-" * 80 + "\n\n")
        
        for idx, row in gdf.iterrows():
            f.write(f"Feature {idx + 1}:\n")
            for col in gdf.columns:
                if col != 'geometry':
                    f.write(f"  {col}: {row[col]}\n")
            
            # Handle both LineString and MultiLineString
            if row.geometry.geom_type == 'MultiLineString':
                total_points = sum(len(list(line.coords)) for line in row.geometry.geoms)
                f.write(f"  Geometry: MultiLineString with {len(row.geometry.geoms)} parts, {total_points} total points\n")
            elif row.geometry.geom_type == 'LineString':
                coords = list(row.geometry.coords)
                f.write(f"  Geometry: LineString with {len(coords)} points\n")
            
            f.write(f"  Length: {row['length_km']:.3f} km\n")
            f.write("\n")
    
    print(f"Detailed summary saved to: {output_file}")
    
    # Export to CSV for easy viewing
    csv_file = Path("/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping/bangalore_metro_analysis.csv")
    gdf.drop(columns=['geometry']).to_csv(csv_file, index=False)
    print(f"CSV export saved to: {csv_file}")
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    try:
        analyze_bangalore_metro()
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()

