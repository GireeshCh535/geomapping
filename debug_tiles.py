#!/usr/bin/env python3
"""
Debug script to understand tile generation issues
"""

import geopandas as gpd
import mercantile
from pathlib import Path

def debug_tile_generation():
    # Load a sample zone
    data_dir = Path("data/andhra_pradesh/amaravati/msater_plan")
    sample_file = data_dir / "R1-Village planning zone.geojson"
    
    print(f"Loading sample file: {sample_file}")
    gdf = gpd.read_file(sample_file)
    print(f"Loaded {len(gdf)} features")
    print(f"CRS: {gdf.crs}")
    print(f"Bounds: {gdf.total_bounds}")
    
    # Check a specific tile
    x, y, z = 23702, 0, 15  # Sample tile coordinates
    tile_bounds = mercantile.bounds(x, y, z)
    print(f"\nTile bounds for {x}/{y}/{z}: {tile_bounds}")
    
    # Check if any features intersect with this tile
    from shapely.geometry import box
    tile_geom = box(tile_bounds.west, tile_bounds.south, tile_bounds.east, tile_bounds.north)
    print(f"Tile geometry bounds: {tile_geom.bounds}")
    
    # Check intersections
    intersecting = gdf[gdf.geometry.intersects(tile_geom)]
    print(f"Features intersecting tile: {len(intersecting)}")
    
    if len(intersecting) > 0:
        print("Sample intersecting feature:")
        sample_feature = intersecting.iloc[0]
        print(f"  Geometry type: {sample_feature.geometry.geom_type}")
        print(f"  Geometry bounds: {sample_feature.geometry.bounds}")
        
        # Test coordinate conversion
        def coord_to_pixel(lon, lat):
            tile_x = (lon - tile_bounds.west) / (tile_bounds.east - tile_bounds.west) * 256
            tile_y = (tile_bounds.north - lat) / (tile_bounds.north - tile_bounds.south) * 256
            return tile_x, tile_y
        
        # Test with a few coordinates
        if sample_feature.geometry.geom_type == 'Polygon':
            coords = list(sample_feature.geometry.exterior.coords)[:5]
            print("Sample coordinate conversions:")
            for i, coord in enumerate(coords):
                if len(coord) >= 2:
                    lon, lat = coord[0], coord[1]
                    px, py = coord_to_pixel(lon, lat)
                    print(f"  {i}: ({lon:.6f}, {lat:.6f}) -> ({px:.1f}, {py:.1f})")
    else:
        print("No features intersect with this tile")
        
        # Check if data is in the right area
        print(f"\nData bounds: {gdf.total_bounds}")
        print(f"Tile bounds: {tile_bounds}")
        
        # Check if we need different tile coordinates
        center_lon = (gdf.total_bounds[0] + gdf.total_bounds[2]) / 2
        center_lat = (gdf.total_bounds[1] + gdf.total_bounds[3]) / 2
        print(f"Data center: ({center_lon:.6f}, {center_lat:.6f})")
        
        # Find the correct tile for the data center
        correct_tile = mercantile.tile(center_lon, center_lat, z)
        print(f"Correct tile for data center: {correct_tile}")

if __name__ == "__main__":
    debug_tile_generation()
