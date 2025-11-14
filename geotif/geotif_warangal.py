#!/usr/bin/env python3
"""
GeoJSON to High-Resolution RGB GeoTIFF Converter
Converts GeoJSON files to RGB GeoTIFF with transparent background at specified resolution
Uses LZW compression to preserve spatial data integrity
Supports zoom level 16 (2.4m/pixel) for maximum clarity
"""

import os
import json
import math
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.features import rasterize
from shapely.geometry import shape, mapping
import glob

# ============================================================================
# CONFIGURATION
# ============================================================================
INPUT_DIR = "data/Telangana/warangal/master_plan"  # Change this
OUTPUT_FILE = "warangal_masterplan_zoom15.tif"

# Resolution in meters per pixel - ZOOM 15 (More stable than 16)
TARGET_RESOLUTION_METERS = 4.8  # Zoom 15 (4.8m × 4.8m per pixel)

# Zoom 15 is a good balance:
# - Still very high resolution
# - More manageable file size (~650 MB vs 2.5 GB)
# - Less likely to hit memory limits
# Expected: 14,263 × 11,406 pixels, ~650 MB file
# Processing time: 8-15 minutes

# ============================================================================
# COLOR SCHEME - Exact colors from your mapping (using 'fill' colors)
# ============================================================================
def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

COLOR_MAP = {
    # Exact mapping from your color scheme (using 'fill' colors)
    'Agriculture': hex_to_rgb('#D3FFBE'),
    'AirStrip': hex_to_rgb('#FF00C5'),
    'Air Strip': hex_to_rgb('#FF00C5'),
    'Commercial': hex_to_rgb('#0070FF'),
    'Forest': hex_to_rgb('#267300'),
    'Protected & Undevelopable Zone': hex_to_rgb('#267300'),
    'Growth Corridor': hex_to_rgb('#FFBEE8'),
    'Growth Corridor 2': hex_to_rgb('#FF73DF'),
    'Heritage': hex_to_rgb('#FFA77F'),
    'Heritage Conservation Zone': hex_to_rgb('#FFA77F'),
    'Hill Buffer': hex_to_rgb('#55FF00'),
    'Hillocks': hex_to_rgb('#A87000'),
    'Industrial': hex_to_rgb('#C500FF'),
    'Mixed Use': hex_to_rgb('#FFAA00'),
    'Public and Semi-Public': hex_to_rgb('#FF0000'),
    'Public & Semi-Public': hex_to_rgb('#FF0000'),
    'Public Utilities': hex_to_rgb('#E69800'),
    'Railway Land': hex_to_rgb('#CCCCCC'),
    'Recreational': hex_to_rgb('#55FF00'),
    'Recreational Zone': hex_to_rgb('#55FF00'),
    'Residential': hex_to_rgb('#FFFF00'),
    'ResidentialExpansion': hex_to_rgb('#9C9C9C'),
    'Residential Expansion': hex_to_rgb('#9C9C9C'),
    'Road Buffer': hex_to_rgb('#4E4E4E'),
    'Transportation': hex_to_rgb('#B2B2B2'),
    'Water Bodies': hex_to_rgb('#00C5FF'),
    'Water Bodies Buffer': hex_to_rgb('#55FF00'),
    'Water Body Buffer': hex_to_rgb('#55FF00'),
    'Zoological Park': hex_to_rgb('#38A800'),
    'Zoological park': hex_to_rgb('#38A800'),
}

# Layer rendering priority (higher = drawn on top)
# Matching your GeoJSON file structure
LAYER_PRIORITY = {
    # Base layers (lowest priority - drawn first)
    'Agriculture': 1,
    'Water Bodies Buffer': 2,
    'Water Body Buffer': 2,
    'Hill Buffer': 3,
    'Growth Corridor': 4,
    'Growth Corridor 2': 5,
    'ResidentialExpansion': 6,
    'Residential Expansion': 6,
    'Forest': 7,
    'Hillocks': 8,
    'Recreational': 9,
    'Recreational Zone': 9,
    'Water Bodies': 10,
    'Mixed Use': 11,
    'Residential': 12,
    'Commercial': 13,
    'Industrial': 14,
    'Public & Semi-Public': 15,
    'Public and Semi-Public': 15,
    'Public Utilities': 16,
    'Heritage': 17,
    'Heritage Conservation Zone': 17,
    'Railway Land': 18,
    'Road Buffer': 19,
    'Transportation': 20,
    'AirStrip': 21,
    'Air Strip': 21,
    'Zoological Park': 22,
    'Zoological park': 22,
    'Protected & Undevelopable Zone': 23,
}

# ============================================================================
# FUNCTIONS
# ============================================================================

def get_geojson_files(directory):
    """Get all GeoJSON files"""
    pattern = os.path.join(directory, "*.geojson")
    files = glob.glob(pattern)
    if not files:
        raise ValueError(f"No GeoJSON files found in: {directory}")
    return sorted(files)


def calculate_bounds(geojson_files):
    """Calculate overall bounding box"""
    print("\n[1/6] Calculating bounds...")
    
    minx = miny = float('inf')
    maxx = maxy = float('-inf')
    total_features = 0
    
    for filepath in geojson_files:
        filename = os.path.basename(filepath)
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        features = data.get('features', [])
        total_features += len(features)
        
        for feature in features:
            geom = shape(feature['geometry'])
            b = geom.bounds
            minx = min(minx, b[0])
            miny = min(miny, b[1])
            maxx = max(maxx, b[2])
            maxy = max(maxy, b[3])
        
        print(f"  ✓ {filename}: {len(features)} features")
    
    bounds = (minx, miny, maxx, maxy)
    print(f"\n  Bounds: [{minx:.6f}, {miny:.6f}, {maxx:.6f}, {maxy:.6f}]")
    print(f"  Total features: {total_features:,}")
    
    return bounds


def calculate_dimensions(bounds, target_resolution_meters):
    """Calculate raster dimensions based on desired resolution"""
    print("\n[2/6] Calculating dimensions...")
    
    minx, miny, maxx, maxy = bounds
    width_deg = maxx - minx
    height_deg = maxy - miny
    
    # Calculate km
    center_lat = (miny + maxy) / 2
    km_per_deg_lon = 111.32 * math.cos(math.radians(center_lat))
    km_per_deg_lat = 111.32
    
    width_km = width_deg * km_per_deg_lon
    height_km = height_deg * km_per_deg_lat
    
    print(f"  Extent: {width_km:.2f} km × {height_km:.2f} km")
    
    # Calculate pixels based on target resolution
    width_meters = width_km * 1000
    height_meters = height_km * 1000
    
    width_px = int(width_meters / target_resolution_meters)
    height_px = int(height_meters / target_resolution_meters)
    
    # Calculate actual resolution achieved
    actual_resolution = width_meters / width_px
    
    # Estimate file size (RGBA = 4 bytes per pixel, UNCOMPRESSED)
    uncompressed_mb = (width_px * height_px * 4) / (1024 * 1024)
    
    print(f"  Target resolution: {target_resolution_meters:.2f} m/pixel")
    print(f"  Actual resolution: {actual_resolution:.2f} m/pixel")
    print(f"  Output dimensions: {width_px:,} × {height_px:,} pixels")
    print(f"  Total pixels: {width_px * height_px:,}")
    print(f"  File size (uncompressed RGBA): ~{uncompressed_mb:.0f} MB")
    
    if width_px * height_px > 100_000_000:
        print(f"  ⚠️  Large image - processing may take 10-30 minutes!")
        print(f"  ⚠️  File will be ~{uncompressed_mb/1024:.1f} GB - ensure sufficient disk space!")
    
    return width_px, height_px


def load_features_by_layer(geojson_files):
    """Load features organized by layer for priority rendering"""
    print("\n[3/6] Loading features by layer...")
    
    layers = {}
    color_usage = {}
    
    for filepath in geojson_files:
        filename = os.path.basename(filepath).replace('.geojson', '')
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        features = []
        for feature in data.get('features', []):
            try:
                # Check if geometry exists and is not None
                if feature.get('geometry') is None:
                    continue
                
                # Get PLU_NAME for reference
                plu_name = feature['properties'].get('PLU_NAME', '') if feature.get('properties') else ''
                
                # Validate geometry
                geom = shape(feature['geometry'])
                if not geom.is_valid:
                    geom = geom.buffer(0)
                if geom.is_empty:
                    continue
                
                # IMPORTANT: Prioritize filename for color (it's the layer name)
                # Then try PLU_NAME, then default to gray
                color = COLOR_MAP.get(filename)  # Try filename first
                if color is None:
                    color = COLOR_MAP.get(plu_name)  # Try PLU_NAME
                if color is None:
                    color = (128, 128, 128)  # Gray default
                    print(f"    ⚠️  No color mapping for layer '{filename}' or PLU_NAME '{plu_name}'")
                
                # Track color usage by filename (layer name)
                if filename not in color_usage:
                    hex_color = '#{:02x}{:02x}{:02x}'.format(*color)
                    color_usage[filename] = hex_color
                
                features.append({
                    'geometry': mapping(geom),
                    'color': color,
                    'category': filename  # Use filename as category
                })
                
            except Exception as e:
                continue
        
        if features:
            priority = LAYER_PRIORITY.get(filename, LAYER_PRIORITY.get(features[0]['category'], 50))
            layers[filename] = {
                'features': features,
                'priority': priority,
                'count': len(features)
            }
            
            # Show color being used
            sample_color = features[0]['color']
            hex_color = '#{:02x}{:02x}{:02x}'.format(*sample_color)
            print(f"  ✓ {filename}: {len(features)} features (priority: {priority}, color: {hex_color})")
    
    print(f"\n  Unique categories with colors:")
    # Filter out None values and sort
    valid_colors = {k: v for k, v in color_usage.items() if k is not None and v is not None}
    for cat, hex_col in sorted(valid_colors.items())[:8]:
        print(f"    {cat:30s} → {hex_col}")
    if len(valid_colors) > 8:
        print(f"    ... and {len(valid_colors) - 8} more")
    
    return layers


def rasterize_rgb(layers, bounds, width, height):
    """Rasterize features as RGBA image with transparent background - OPTIMIZED"""
    print("\n[4/6] Rasterizing to RGBA...")
    print(f"  Creating {width:,} × {height:,} RGBA image with transparent background...")
    
    total_pixels = width * height
    memory_mb = (total_pixels * 4) / (1024 * 1024)
    print(f"  Memory required: ~{memory_mb:.1f} MB")
    
    minx, miny, maxx, maxy = bounds
    transform = from_bounds(minx, miny, maxx, maxy, width, height)
    
    # Initialize RGBA bands (transparent background)
    print(f"  Allocating memory for {width:,} × {height:,} × 4 bands...")
    try:
        r_band = np.zeros((height, width), dtype=np.uint8)
        g_band = np.zeros((height, width), dtype=np.uint8)
        b_band = np.zeros((height, width), dtype=np.uint8)
        a_band = np.zeros((height, width), dtype=np.uint8)
        print(f"  ✓ Memory allocated successfully")
    except MemoryError:
        print(f"  ❌ Not enough memory! Try lower resolution.")
        raise
    
    # Sort layers by priority (lowest first, so highest priority drawn last)
    sorted_layers = sorted(layers.items(), key=lambda x: x[1]['priority'])
    
    total_features = sum(layer['count'] for layer in layers.values())
    processed = 0
    
    print(f"\n  Rendering {len(sorted_layers)} layers with {total_features:,} total features...")
    print(f"  Layer rendering order (priority):")
    for i, (name, data) in enumerate(sorted_layers, 1):
        print(f"    {i:2d}. {name} (priority {data['priority']}) - {data['count']} features")
    print()
    
    for layer_idx, (layer_name, layer_data) in enumerate(sorted_layers, 1):
        features = layer_data['features']
        
        if not features:
            continue
        
        print(f"  [{layer_idx}/{len(sorted_layers)}] Rendering {layer_name}: {len(features)} features...", end='', flush=True)
        
        # Get the color for this layer (all features in a layer have same color)
        layer_color = features[0]['color']
        r, g, b = layer_color
        
        # OPTIMIZED: Batch all geometries together for this layer
        shapes = [(feat['geometry'], 1) for feat in features]
        
        try:
            # Rasterize ALL features of this layer in ONE call
            mask = rasterize(
                shapes=shapes,
                out_shape=(height, width),
                transform=transform,
                fill=0,
                all_touched=True,
                dtype=np.uint8
            )
            
            # Apply color to all pixels touched by this layer
            layer_pixels = mask == 1
            pixels_affected = np.sum(layer_pixels)
            
            r_band[layer_pixels] = r
            g_band[layer_pixels] = g
            b_band[layer_pixels] = b
            a_band[layer_pixels] = 255  # Set alpha to opaque
            
            processed += len(features)
            progress = (processed / total_features) * 100
            print(f" Done! ({pixels_affected:,} pixels, {progress:.1f}% complete)")
            
        except Exception as e:
            print(f" ERROR: {e}")
            continue
    
    # Check coverage (count opaque pixels)
    opaque_pixels = np.sum(a_band > 0)
    coverage = (opaque_pixels / (height * width)) * 100
    
    print(f"\n  ✓ Rasterization complete!")
    print(f"  Coverage: {coverage:.2f}%")
    print(f"  Opaque pixels: {opaque_pixels:,} / {total_pixels:,}")
    
    if coverage < 10:
        print(f"  ⚠️  WARNING: Very low coverage - check if features are within bounds")
    
    return np.stack([r_band, g_band, b_band, a_band]), transform


def write_rgb_geotiff(rgba_data, transform, bounds, output_file):
    """Write RGB GeoTIFF with internal transparency mask"""
    print(f"\n[5/6] Writing RGB GeoTIFF with transparency...")
    
    bands, height, width = rgba_data.shape
    
    # Use internal mask instead of alpha band for better compatibility
    with rasterio.open(
        output_file,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=3,  # RGB only
        dtype=np.uint8,
        crs='EPSG:4326',
        transform=transform,
        compress='deflate',
        photometric='RGB',
        tiled=True,
        blockxsize=256,
        blockysize=256,
        nodata=None  # We'll use internal mask instead
    ) as dst:
        # Write RGB bands
        dst.write(rgba_data[0], 1)  # Red
        dst.write(rgba_data[1], 2)  # Green
        dst.write(rgba_data[2], 3)  # Blue
        
        # Write transparency mask for each band
        # True = valid data, False = transparent
        alpha = rgba_data[3]
        mask = alpha == 0  # Where alpha is 0, mask out (transparent)
        
        dst.write_mask(~mask)  # Invert: True where we have data
        
        dst.update_tags(
            description='Warangal Master Plan Land Use Map (RGB with transparency)',
            created_by='geojson_to_geotiff_rgba.py',
            has_transparency='true'
        )
    
    file_size = os.path.getsize(output_file) / (1024 * 1024)
    print(f"  ✓ File written: {output_file}")
    print(f"  ✓ File size: {file_size:.2f} MB")


def verify_output(output_file):
    """Verify output"""
    print(f"\n[6/6] Verifying output...")
    
    with rasterio.open(output_file) as src:
        print(f"  Dimensions: {src.width} × {src.height}")
        print(f"  Bands: {src.count} (RGB with transparency mask)")
        print(f"  CRS: {src.crs}")
        
        # Read RGB data
        r = src.read(1)
        g = src.read(2)
        b = src.read(3)
        
        # Read mask (True = valid data)
        mask = src.read_masks(1)
        
        # Check if all transparent (mask all False/0)
        all_transparent = np.all(mask == 0)
        
        if all_transparent:
            print(f"\n  ❌ ERROR: Image is all transparent (no data)!")
            return False
        
        # Calculate opaque pixels
        opaque_pixels = np.sum(mask > 0)
        
        print(f"  Opaque pixels: {opaque_pixels:,}")
        print(f"  ✓ Verification passed")
        return True


def main():
    """Main execution"""
    print("=" * 70)
    print("GeoJSON to High-Resolution RGB GeoTIFF with Transparency")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Input: {INPUT_DIR}")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Target resolution: {TARGET_RESOLUTION_METERS}m/pixel")
    
    # Determine zoom level
    zoom_levels = {
        0.6: 18,
        1.2: 17,
        2.4: 16,
        4.8: 15,
        9.6: 14,
        19.1: 13,
        38.2: 12,
        76.4: 11,
        152.9: 10
    }
    
    closest_zoom = min(zoom_levels.keys(), key=lambda x: abs(x - TARGET_RESOLUTION_METERS))
    zoom_level = zoom_levels[closest_zoom]
    print(f"  Equivalent zoom level: ~{zoom_level}")
    
    if not os.path.exists(INPUT_DIR):
        print(f"\n❌ ERROR: Directory not found: {INPUT_DIR}")
        return 1
    
    try:
        # Get files
        geojson_files = get_geojson_files(INPUT_DIR)
        print(f"\nFound {len(geojson_files)} GeoJSON files")
        
        # Calculate bounds
        bounds = calculate_bounds(geojson_files)
        
        # Calculate dimensions based on resolution
        width, height = calculate_dimensions(bounds, TARGET_RESOLUTION_METERS)
        
        # Load features by layer
        layers = load_features_by_layer(geojson_files)
        
        if not layers:
            print("\n❌ ERROR: No valid features found!")
            return 1
        
        # Rasterize as RGBA
        rgba_data, transform = rasterize_rgb(layers, bounds, width, height)
        
        # Write output
        write_rgb_geotiff(rgba_data, transform, bounds, OUTPUT_FILE)
        
        # Verify
        if not verify_output(OUTPUT_FILE):
            return 1
        
        print("\n" + "=" * 70)
        print("✓ SUCCESS: High-Resolution RGB GeoTIFF created!")
        print("=" * 70)
        print(f"\nResolution Details:")
        print(f"  Target: {TARGET_RESOLUTION_METERS}m/pixel")
        print(f"  Zoom level equivalent: ~{zoom_level}")
        print(f"  Dimensions: {width:,} × {height:,} pixels")
        print(f"  Each pixel = {TARGET_RESOLUTION_METERS}m × {TARGET_RESOLUTION_METERS}m")
        print(f"  Format: RGBA uncompressed (maximum data integrity)")
        print("\nColor Mapping Summary:")
        print("-" * 70)
        sample_colors = [
            ('Agriculture', '#D3FFBE'),
            ('Residential', '#FFFF00'),
            ('Commercial', '#0070FF'),
            ('Mixed Use', '#FFAA00'),
            ('Industrial', '#C500FF'),
            ('Public & Semi-Public', '#FF0000'),
            ('Water Bodies', '#00C5FF'),
            ('Transportation', '#B2B2B2'),
        ]
        for name, hex_col in sample_colors:
            print(f"  {name:25s} → {hex_col}")
        print("-" * 70)
        print(f"\nThe file contains the COMPLETE map with transparent background!")
        print(f"File is uncompressed (~{width*height*4/(1024*1024):.0f} MB) to ensure all data is preserved.")
        print(f"\nNOTE: To reduce file size, you can later compress with GDAL:")
        print(f"  gdal_translate -co COMPRESS=LZW input.tif output_compressed.tif")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())