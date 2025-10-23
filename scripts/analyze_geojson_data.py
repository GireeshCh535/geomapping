#!/usr/bin/env python3
"""
GeoJSON Data Analyzer for Tile Generation Planning
===================================================

This script analyzes GeoJSON files to help plan tile generation:
- Counts features and file sizes
- Calculates geographic bounds
- Identifies geometry types
- Lists property fields
- Estimates tile counts and storage needs

Usage:
    python3 analyze_geojson_data.py <directory_path>

Example:
    python3 analyze_geojson_data.py data/Telangana/warangal/master_plan
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any
import geopandas as gpd
from shapely.geometry import box
import mercantile

class GeoJSONAnalyzer:
    def __init__(self, directory: str):
        self.directory = Path(directory)
        self.files = {}
        self.total_features = 0
        self.total_size = 0
        self.bounds = None
        
        if not self.directory.exists():
            print(f"❌ Error: Directory not found: {directory}")
            sys.exit(1)
    
    def analyze(self):
        """Run complete analysis"""
        print("="*70)
        print("🗺️  GeoJSON DATA ANALYZER")
        print("="*70)
        print(f"\n📁 Analyzing: {self.directory.absolute()}\n")
        
        # Find and analyze files
        self._scan_files()
        if not self.files:
            print("❌ No GeoJSON files found!")
            return
        
        # Detailed analysis
        self._analyze_files()
        self._calculate_bounds()
        self._estimate_tiles()
        self._show_summary()
    
    def _scan_files(self):
        """Scan directory for GeoJSON files"""
        geojson_files = list(self.directory.glob("*.geojson"))
        
        print(f"📊 Found {len(geojson_files)} GeoJSON files\n")
        print("-"*70)
        
        for file_path in sorted(geojson_files):
            size = file_path.stat().st_size
            self.total_size += size
            
            # Try to load and get basic info
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                feature_count = len(data.get('features', []))
                self.total_features += feature_count
                
                # Get geometry types
                geom_types = set()
                properties = set()
                
                for feature in data.get('features', [])[:10]:  # Sample first 10
                    geom = feature.get('geometry', {})
                    if geom:
                        geom_types.add(geom.get('type', 'Unknown'))
                    
                    props = feature.get('properties', {})
                    properties.update(props.keys())
                
                self.files[file_path.stem] = {
                    'path': file_path,
                    'size': size,
                    'features': feature_count,
                    'geometry_types': list(geom_types),
                    'properties': list(properties)
                }
                
                # Show progress
                size_str = self._format_size(size)
                density = "🔴 Very Large" if feature_count > 10000 else \
                         "🟠 Large" if feature_count > 1000 else \
                         "🟡 Medium" if feature_count > 100 else \
                         "🟢 Small"
                
                print(f"{density} {file_path.name:35s} {size_str:>10s} {feature_count:>8,} features")
                
            except Exception as e:
                print(f"⚠️  Error reading {file_path.name}: {e}")
        
        print("-"*70)
        print(f"📊 Total: {len(self.files)} files, {self._format_size(self.total_size)}, {self.total_features:,} features\n")
    
    def _analyze_files(self):
        """Detailed analysis of files"""
        print("="*70)
        print("📋 DETAILED FILE ANALYSIS")
        print("="*70)
        
        for name, info in sorted(self.files.items()):
            print(f"\n📄 {name}")
            print(f"   Size: {self._format_size(info['size'])}")
            print(f"   Features: {info['features']:,}")
            print(f"   Geometry types: {', '.join(info['geometry_types'])}")
            print(f"   Property count: {len(info['properties'])} fields")
            if info['properties']:
                print(f"   Sample properties: {', '.join(list(info['properties'])[:5])}")
        
        print()
    
    def _calculate_bounds(self):
        """Calculate geographic bounds"""
        print("="*70)
        print("🗺️  GEOGRAPHIC BOUNDS")
        print("="*70)
        
        try:
            all_bounds = []
            
            for name, info in self.files.items():
                try:
                    gdf = gpd.read_file(info['path'])
                    if not gdf.empty:
                        # Ensure CRS
                        if gdf.crs is None:
                            gdf = gdf.set_crs('EPSG:4326', allow_override=True)
                        elif gdf.crs.to_string() != 'EPSG:4326':
                            gdf = gdf.to_crs('EPSG:4326')
                        
                        all_bounds.append(gdf.total_bounds)
                except Exception as e:
                    print(f"⚠️  Could not process {name}: {e}")
            
            if all_bounds:
                self.bounds = [
                    min(b[0] for b in all_bounds),  # minx
                    min(b[1] for b in all_bounds),  # miny
                    max(b[2] for b in all_bounds),  # maxx
                    max(b[3] for b in all_bounds)   # maxy
                ]
                
                print(f"\n📍 Bounding Box (WGS84):")
                print(f"   West:  {self.bounds[0]:.6f}°")
                print(f"   South: {self.bounds[1]:.6f}°")
                print(f"   East:  {self.bounds[2]:.6f}°")
                print(f"   North: {self.bounds[3]:.6f}°")
                
                # Calculate center and dimensions
                center_lon = (self.bounds[0] + self.bounds[2]) / 2
                center_lat = (self.bounds[1] + self.bounds[3]) / 2
                width_deg = self.bounds[2] - self.bounds[0]
                height_deg = self.bounds[3] - self.bounds[1]
                
                # Rough km conversion (at equator: 1° ≈ 111km)
                width_km = width_deg * 111 * abs(cos_deg(center_lat))
                height_km = height_deg * 111
                
                print(f"\n📏 Dimensions:")
                print(f"   Width:  {width_deg:.4f}° (~{width_km:.1f} km)")
                print(f"   Height: {height_deg:.4f}° (~{height_km:.1f} km)")
                print(f"   Center: {center_lat:.6f}°N, {center_lon:.6f}°E")
                print(f"   Area:   ~{width_km * height_km:.1f} km²")
            else:
                print("\n⚠️  Could not calculate bounds")
        
        except Exception as e:
            print(f"\n⚠️  Error calculating bounds: {e}")
        
        print()
    
    def _estimate_tiles(self):
        """Estimate tile counts for different zoom levels"""
        if not self.bounds:
            return
        
        print("="*70)
        print("🔢 TILE GENERATION ESTIMATES")
        print("="*70)
        
        print(f"\n{'Zoom':<6} {'Tiles':<12} {'Storage':<12} {'Detail Level':<20} {'Time Est.':<12}")
        print("-"*70)
        
        zoom_levels = [0, 5, 8, 10, 12, 14, 16, 18, 20, 22]
        total_by_range = {}
        
        for zoom in zoom_levels:
            # Get tiles in bounds
            tiles = list(mercantile.tiles(
                self.bounds[0], self.bounds[1],
                self.bounds[2], self.bounds[3],
                zooms=[zoom]
            ))
            
            tile_count = len(tiles)
            
            # Estimate storage (assuming 70% tiles have data, avg 40KB per tile)
            tiles_with_data = int(tile_count * 0.7)
            storage_bytes = tiles_with_data * 40 * 1024
            storage = self._format_size(storage_bytes)
            
            # Detail level
            detail_levels = {
                0: "World",
                5: "Country/State",
                8: "City Region",
                10: "District",
                12: "Neighborhood",
                14: "Street Level",
                16: "Building Outline",
                18: "Building Detail",
                20: "Parcel Level",
                22: "Sub-meter"
            }
            detail = detail_levels.get(zoom, "Detail")
            
            # Time estimate (rough: 100 tiles/sec)
            time_seconds = tiles_with_data / 100
            if time_seconds < 60:
                time_est = f"{time_seconds:.0f} sec"
            elif time_seconds < 3600:
                time_est = f"{time_seconds/60:.0f} min"
            elif time_seconds < 86400:
                time_est = f"{time_seconds/3600:.1f} hours"
            else:
                time_est = f"{time_seconds/86400:.1f} days"
            
            print(f"{zoom:<6} {tile_count:<12,} {storage:<12} {detail:<20} {time_est:<12}")
            
            # Track cumulative
            if zoom <= 14:
                total_by_range['dev'] = total_by_range.get('dev', 0) + tiles_with_data
            if zoom <= 18:
                total_by_range['prod'] = total_by_range.get('prod', 0) + tiles_with_data
            total_by_range['full'] = total_by_range.get('full', 0) + tiles_with_data
        
        print("-"*70)
        print(f"\n💾 Storage Estimates (cumulative):")
        print(f"   Development (zoom 0-14):  ~{self._format_size(total_by_range.get('dev', 0) * 40 * 1024)}")
        print(f"   Production (zoom 0-18):   ~{self._format_size(total_by_range.get('prod', 0) * 40 * 1024)}")
        print(f"   Full Detail (zoom 0-22):  ~{self._format_size(total_by_range.get('full', 0) * 40 * 1024)}")
        print()
    
    def _show_summary(self):
        """Show summary and recommendations"""
        print("="*70)
        print("📊 SUMMARY & RECOMMENDATIONS")
        print("="*70)
        
        print(f"\n✅ Data Quality:")
        print(f"   • Total files: {len(self.files)}")
        print(f"   • Total features: {self.total_features:,}")
        print(f"   • Total size: {self._format_size(self.total_size)}")
        
        # Check for large files
        large_files = [name for name, info in self.files.items() if info['size'] > 10*1024*1024]
        if large_files:
            print(f"\n⚠️  Large Files (>10MB): {len(large_files)}")
            print(f"   {', '.join(large_files[:3])}")
            print(f"   → Use spatial indexing for efficient processing")
        
        # Check feature density
        high_density = [name for name, info in self.files.items() if info['features'] > 10000]
        if high_density:
            print(f"\n⚠️  High Feature Density (>10k features): {len(high_density)}")
            print(f"   {', '.join(high_density[:3])}")
            print(f"   → Consider parallel processing for tile generation")
        
        print(f"\n🎯 Recommended Approach:")
        print(f"   1. Start with zoom 10-14 for testing")
        print(f"   2. Verify colors and rendering quality")
        print(f"   3. Generate production tiles (zoom 0-18)")
        print(f"   4. Add higher zooms (19-22) if needed")
        
        if self.bounds:
            print(f"\n🗺️  For Tile Generation Script:")
            print(f"   bounds = {self.bounds}")
            print(f"   center = [{(self.bounds[1]+self.bounds[3])/2:.6f}, {(self.bounds[0]+self.bounds[2])/2:.6f}]")
        
        print(f"\n📚 Next Steps:")
        print(f"   • Review color specifications for each zone")
        print(f"   • Define rendering order (layering)")
        print(f"   • Configure patterns (solid/hatched)")
        print(f"   • Set up tile generation script")
        print(f"   • Test with sample tiles")
        
        print("\n" + "="*70)
    
    def _format_size(self, size_bytes: int) -> str:
        """Format bytes to human-readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"


def cos_deg(degrees: float) -> float:
    """Calculate cosine from degrees"""
    import math
    return math.cos(math.radians(degrees))


def main():
    """Main execution"""
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_geojson_data.py <directory_path>")
        print("\nExample:")
        print("  python3 analyze_geojson_data.py data/Telangana/warangal/master_plan")
        sys.exit(1)
    
    directory = sys.argv[1]
    
    try:
        analyzer = GeoJSONAnalyzer(directory)
        analyzer.analyze()
    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

