#!/usr/bin/env python3
"""
Warangal Master Plan - PNG Tile Generator
Converts GeoJSON files to PNG tiles (zoom 7-18) with custom styling
"""

import os
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd
import geopandas as gpd
from shapely.geometry import box
from PIL import Image, ImageDraw
import numpy as np

# Configuration
INPUT_DIR = "/Users/rohitboni/Downloads/All_files/project/1acre/geomapping_full/geomapping/data/Telangana/warangal/master_plan"
OUTPUT_DIR = "./tiles"
MIN_ZOOM = 7
MAX_ZOOM = 18
TILE_SIZE = 256

# Layer styling configuration with colors
LAYER_STYLES = {
    "Agriculture": {"color": "#D3FFBE", "pattern": None},
    "AirStrip": {"color": "#FF00C5", "pattern": "diagonal", "pattern_color": "#FFFFFF"},
    "Commercial": {"color": "#0070FF", "pattern": None},
    "Forest": {"color": "#267300", "pattern": None},
    "Growth Corridor 2": {"color": "#FF73DF", "pattern": None},
    "Growth Corridor": {"color": "#FFBEE8", "pattern": None},
    "Heritage": {"color": "#FFA77F", "pattern": "diagonal", "pattern_color": "#732600"},
    "Hill Buffer": {"color": "#55FF00", "pattern": None},
    "Hillocks": {"color": "#A87000", "pattern": None},
    "Industrial": {"color": "#C500FF", "pattern": None},
    "Mixed Use": {"color": "#FFAA00", "pattern": None},
    "Public and Semi-Public": {"color": "#FF0000", "pattern": None},
    "Public Utilities": {"color": "#E69800", "pattern": "diagonal", "pattern_color": "#FF0000"},
    "Railway Land": {"color": "#CCCCCC", "pattern": None},
    "Recreational": {"color": "#55FF00", "pattern": None},
    "Residential": {"color": "#FFFF00", "pattern": None},
    "ResidentialExpansion": {"color": "#9C9C9C", "pattern": None},
    "Road Buffer": {"color": "#4E4E4E", "pattern": None},
    "Transportation": {"color": "#B2B2B2", "pattern": None},
    "Water Bodies": {"color": "#00C5FF", "pattern": None},
    "Water Bodies Buffer": {"color": "#55FF00", "pattern": None},
    "Zoological Park": {"color": "#38A800", "pattern": None}
}

# Simplification tolerances by zoom level (in degrees)
SIMPLIFICATION = {
    7: 0.01, 8: 0.005, 9: 0.002, 10: 0.001,
    11: 0.0005, 12: 0.0002, 13: 0.0001, 14: 0.00005,
    15: 0.00002, 16: 0.00001, 17: 0.000005, 18: 0
}


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> Tuple[int, int]:
    """Convert latitude/longitude to tile coordinates."""
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 
            1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def tile_to_lat_lon(x: int, y: int, zoom: int) -> Tuple[float, float, float, float]:
    """Convert tile coordinates to bounding box (min_lon, min_lat, max_lon, max_lat)."""
    n = 2 ** zoom
    min_lon = x / n * 360 - 180
    max_lon = (x + 1) / n * 360 - 180
    
    min_lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
    max_lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    
    min_lat = math.degrees(min_lat_rad)
    max_lat = math.degrees(max_lat_rad)
    
    return min_lon, min_lat, max_lon, max_lat


def create_diagonal_pattern(size: int, color: Tuple[int, int, int], 
                           bg_color: Tuple[int, int, int], zoom: int) -> Image.Image:
    """Create a diagonal hatching pattern."""
    # Adjust spacing based on zoom level
    if zoom <= 10:
        spacing = 8
    elif zoom <= 13:
        spacing = 6
    elif zoom <= 15:
        spacing = 4
    else:
        spacing = 3
    
    pattern = Image.new('RGBA', (size, size), bg_color + (255,))
    draw = ImageDraw.Draw(pattern)
    
    # Adjust line width based on zoom
    line_width = 1 if zoom < 14 else 2
    
    # Draw diagonal lines
    for i in range(-size, size * 2, spacing):
        draw.line([(i, 0), (i + size, size)], fill=color + (255,), width=line_width)
    
    return pattern


def load_all_geojson_files(input_dir: str) -> gpd.GeoDataFrame:
    """Load and combine all GeoJSON files into a single GeoDataFrame."""
    print("Loading GeoJSON files...")
    all_gdfs = []
    
    geojson_files = list(Path(input_dir).glob("*.geojson"))
    
    for file_path in geojson_files:
        try:
            layer_name = file_path.stem
            print(f"  Loading {layer_name}...")
            
            gdf = gpd.read_file(file_path)
            gdf['layer'] = layer_name
            
            # Ensure CRS is WGS84
            if gdf.crs is None:
                gdf.set_crs('EPSG:4326', inplace=True)
            elif gdf.crs.to_string() != 'EPSG:4326':
                gdf = gdf.to_crs('EPSG:4326')
            
            all_gdfs.append(gdf)
            
        except Exception as e:
            print(f"  Error loading {file_path.name}: {e}")
    
    if not all_gdfs:
        raise ValueError("No GeoJSON files loaded successfully!")
    
    # Combine all GeoDataFrames
    combined_gdf = gpd.GeoDataFrame(pd.concat(all_gdfs, ignore_index=True))
    print(f"\nTotal features loaded: {len(combined_gdf)}")
    
    return combined_gdf


def render_tile(gdf: gpd.GeoDataFrame, x: int, y: int, zoom: int) -> Image.Image:
    """Render a single tile as PNG."""
    # Get tile bounds
    min_lon, min_lat, max_lon, max_lat = tile_to_lat_lon(x, y, zoom)
    tile_bbox = box(min_lon, min_lat, max_lon, max_lat)
    
    # Filter features that intersect with tile
    tile_gdf = gdf[gdf.intersects(tile_bbox)].copy()
    
    if tile_gdf.empty:
        return None
    
    # Clip geometries to tile bounds
    tile_gdf['geometry'] = tile_gdf.geometry.intersection(tile_bbox)
    tile_gdf = tile_gdf[~tile_gdf.geometry.is_empty]
    
    if tile_gdf.empty:
        return None
    
    # Simplify geometries based on zoom level
    tolerance = SIMPLIFICATION.get(zoom, 0)
    if tolerance > 0:
        tile_gdf['geometry'] = tile_gdf.geometry.simplify(tolerance, preserve_topology=True)
    
    # Create image
    img = Image.new('RGBA', (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Calculate coordinate transformation
    lon_scale = TILE_SIZE / (max_lon - min_lon)
    lat_scale = TILE_SIZE / (max_lat - min_lat)
    
    def transform_coords(coords):
        """Transform lon/lat to pixel coordinates."""
        pixels = []
        for lon, lat in coords:
            x_pix = int((lon - min_lon) * lon_scale)
            y_pix = int((max_lat - lat) * lat_scale)
            pixels.append((x_pix, y_pix))
        return pixels
    
    # Render each feature
    for _, feature in tile_gdf.iterrows():
        layer_name = feature.get('layer', '')
        style = LAYER_STYLES.get(layer_name, {"color": "#808080", "pattern": None})
        
        geom = feature.geometry
        if geom is None or geom.is_empty:
            continue
        
        # Handle MultiPolygon and Polygon
        if geom.geom_type == 'MultiPolygon':
            polygons = list(geom.geoms)
        elif geom.geom_type == 'Polygon':
            polygons = [geom]
        else:
            continue
        
        base_color = hex_to_rgb(style['color'])
        
        for poly in polygons:
            # Draw exterior
            if poly.exterior is not None:
                exterior_coords = list(poly.exterior.coords)
                pixel_coords = transform_coords(exterior_coords)
                
                if len(pixel_coords) >= 3:
                    # Fill with base color
                    draw.polygon(pixel_coords, fill=base_color + (255,), outline=None)
                    
                    # Apply pattern if needed
                    if style.get('pattern') == 'diagonal':
                        pattern_color = hex_to_rgb(style.get('pattern_color', '#000000'))
                        pattern = create_diagonal_pattern(TILE_SIZE, pattern_color, base_color, zoom)
                        
                        # Create mask for this polygon
                        mask = Image.new('L', (TILE_SIZE, TILE_SIZE), 0)
                        mask_draw = ImageDraw.Draw(mask)
                        mask_draw.polygon(pixel_coords, fill=255)
                        
                        # Composite pattern onto image
                        img.paste(pattern, (0, 0), mask)
            
            # Draw holes (if any)
            for interior in poly.interiors:
                interior_coords = list(interior.coords)
                pixel_coords = transform_coords(interior_coords)
                if len(pixel_coords) >= 3:
                    draw.polygon(pixel_coords, fill=(0, 0, 0, 0))
    
    return img


def generate_tiles(gdf: gpd.GeoDataFrame, output_dir: str):
    """Generate all tiles for zoom levels 7-18."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Get overall bounds
    bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
    min_lon, min_lat, max_lon, max_lat = bounds
    
    print(f"\nData bounds: [{min_lon:.6f}, {min_lat:.6f}, {max_lon:.6f}, {max_lat:.6f}]")
    print(f"\nGenerating tiles from zoom {MIN_ZOOM} to {MAX_ZOOM}...")
    
    total_tiles = 0
    
    for zoom in range(MIN_ZOOM, MAX_ZOOM + 1):
        # Calculate tile range for this zoom level
        # Note: Y coordinates increase from north to south
        min_x, min_y = lat_lon_to_tile(min_lat, min_lon, zoom)
        max_x, max_y = lat_lon_to_tile(max_lat, max_lon, zoom)
        
        # Swap min_y and max_y since Y increases southward
        min_y, max_y = max_y, min_y
        
        zoom_tiles = 0
        zoom_dir = os.path.join(output_dir, str(zoom))
        
        print(f"\nZoom {zoom}: Tile range X[{min_x}-{max_x}] Y[{min_y}-{max_y}]")
        
        for x in range(min_x, max_x + 1):
            x_dir = os.path.join(zoom_dir, str(x))
            
            for y in range(min_y, max_y + 1):
                tile_img = render_tile(gdf, x, y, zoom)
                
                if tile_img is not None:
                    os.makedirs(x_dir, exist_ok=True)
                    tile_path = os.path.join(x_dir, f"{y}.png")
                    tile_img.save(tile_path, 'PNG')
                    zoom_tiles += 1
        
        print(f"  Generated {zoom_tiles} tiles")
        total_tiles += zoom_tiles
    
    print(f"\n{'='*60}")
    print(f"Total tiles generated: {total_tiles}")
    print(f"Output directory: {output_dir}")
    print(f"{'='*60}")


def main():
    """Main execution function."""
    print("="*60)
    print("Warangal Master Plan - Tile Generator")
    print("="*60)
    
    try:
        # Load all GeoJSON files
        gdf = load_all_geojson_files(INPUT_DIR)
        
        # Generate tiles
        generate_tiles(gdf, OUTPUT_DIR)
        
        print("\n✓ Tile generation complete!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()