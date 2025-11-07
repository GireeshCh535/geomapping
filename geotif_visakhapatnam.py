#!/usr/bin/env python3
"""
Visakhapatnam GeoJSON to High-Resolution RGB GeoTIFF Converter
Converts Visakhapatnam master plan GeoJSON files to RGB GeoTIFF with transparent background
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
from collections import defaultdict

# ============================================================================
# CONFIGURATION
# ============================================================================
INPUT_DIR = "data/andhra_pradesh/visakhapatnam/master_plan"
OUTPUT_FILE = "visakhapatnam_masterplan_zoom16.tif"

# Resolution in meters per pixel - ZOOM 16 for maximum clarity
TARGET_RESOLUTION_METERS = 2.4  # Zoom 16 (2.4m × 2.4m per pixel)

# ============================================================================
# COLOR SCHEME - Visakhapatnam Master Plan (using 'fill' colors)
# ============================================================================
def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

COLOR_MAP = {
    'Agricultural_Use_Zone': hex_to_rgb('#D3FFBE'),
    'Blue_Zone_Water_Bodies': hex_to_rgb('#73FFDF'),
    'Brown_Zone_Hills': hex_to_rgb('#A87000'),
    'Commercial_Use_Zone': hex_to_rgb('#004DA8'),
    'Existing_Crematorium_Burial_Ground_Graveyard': hex_to_rgb('#FF8080'),
    'Existing_Educational_Facilities': hex_to_rgb('#CC0000'),
    'Existing_Government_Semi_Government_Facilities': hex_to_rgb('#FF0000'),
    'Existing_Health_Facilities': hex_to_rgb('#FF6666'),
    'Proposed_Industrial_Use_Zone': hex_to_rgb('#D966FF'),
    'Existing_Industrial_Area': hex_to_rgb('#C500FF'),
    'Existing_Public_Utilities': hex_to_rgb('#FF9999'),
    'Existing_Recreational_Playgrounds_Parks_Layout_OpenSpace': hex_to_rgb('#55FF00'),
    'Existing_Religious_Facilities': hex_to_rgb('#FF6666'),
    'Existing_Road_Railway_Line_Area': hex_to_rgb('#828282'),
    'Existing_Transportation_Facility': hex_to_rgb('#686868'),
    'Green_Zone_Forest': hex_to_rgb('#00734C'),
    'Kambalakonda_Eco_Sensitive_Zone_NAOB_Buffer_Zoological_Park': hex_to_rgb('#D7C29E'),
    'Kambalakonda_WildLife_Sanctuary_Biodiversity_Area': hex_to_rgb('#38A800'),
    'Mixed_Use_Zone_1': hex_to_rgb('#FFAA00'),
    'Mixed_Use_Zone_2_BAIA': hex_to_rgb('#FFD37F'),
    'Mixed_Use_Zone_3_BAIA': hex_to_rgb('#F0B000'),
    'Mixed_Use_Zone_4_BAIA': hex_to_rgb('#FFBB33'),
    'Proposed_PSP_Use_Zone': hex_to_rgb('#FFCCCC'),
    'Proposed_Public_Utilities_Use_Zone': hex_to_rgb('#FF9999'),
    'Proposed_Recreational_Use_Zone': hex_to_rgb('#4C7300'),
    'Proposed_Road_Network': hex_to_rgb('#000000'),
    'Proposed_Transportation_Facility_Use_Zone': hex_to_rgb('#555555'),
    'Residential_Use_Zone': hex_to_rgb('#FFFF73'),
    'Sea_River_Accreted_Land': hex_to_rgb('#E0D0B0'),
    'Special_Area_Use_Zone': hex_to_rgb('#CCE0FF'),
    'Water_Body_Buffer': hex_to_rgb('#66FF33'),
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
    total_skipped = 0
    
    for filepath in geojson_files:
        filename = os.path.basename(filepath)
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        features = data.get('features', [])
        valid_count = 0
        skipped_count = 0
        
        for feature in features:
            try:
                if feature.get('geometry') is None:
                    skipped_count += 1
                    continue
                
                geom = shape(feature['geometry'])
                
                if geom.is_empty:
                    skipped_count += 1
                    continue
                
                b = geom.bounds
                minx = min(minx, b[0])
                miny = min(miny, b[1])
                maxx = max(maxx, b[2])
                maxy = max(maxy, b[3])
                valid_count += 1
            except Exception as e:
                skipped_count += 1
                continue
        
        total_features += valid_count
        total_skipped += skipped_count
        
        if skipped_count > 0:
            print(f"  ✓ {filename}: {valid_count} features ({skipped_count} skipped)")
        else:
            print(f"  ✓ {filename}: {valid_count} features")
    
    bounds = (minx, miny, maxx, maxy)
    print(f"\n  Bounds: [{minx:.6f}, {miny:.6f}, {maxx:.6f}, {maxy:.6f}]")
    print(f"  Total features: {total_features:,}")
    if total_skipped > 0:
        print(f"  Total skipped: {total_skipped}")
    
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
    unmapped_categories = set()
    
    for filepath in geojson_files:
        filename = os.path.basename(filepath).replace('.geojson', '')
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        features = []
        for feature in data.get('features', []):
            try:
                if feature.get('geometry') is None:
                    continue
                
                plu_name = feature['properties'].get('PLU_NAME', '') if feature.get('properties') else ''
                
                geom = shape(feature['geometry'])
                if not geom.is_valid:
                    geom = geom.buffer(0)
                if geom.is_empty:
                    continue
                
                # EXACT color lookup - try multiple variations
                color = None
                
                # Try exact filename match first
                color = COLOR_MAP.get(filename)
                
                # Try PLU_NAME if filename didn't match
                if color is None and plu_name:
                    color = COLOR_MAP.get(plu_name)
                
                # Default to gray if no match
                if color is None:
                    color = (128, 128, 128)
                    unmapped_categories.add(filename if not plu_name else plu_name)
                
                if filename not in color_usage:
                    hex_color = '#{:02x}{:02x}{:02x}'.format(*color)
                    color_usage[filename] = hex_color
                
                features.append({
                    'geometry': mapping(geom),
                    'color': color,
                    'category': filename
                })
                
            except Exception as e:
                continue
        
        if features:
            layers[filename] = {
                'features': features,
                'priority': 50,
                'count': len(features)
            }
            
            sample_color = features[0]['color']
            hex_color = '#{:02x}{:02x}{:02x}'.format(*sample_color)
            print(f"  ✓ {filename}: {len(features)} features (color: {hex_color})")
    
    # Show unmapped categories if any
    if unmapped_categories:
        print(f"\n  ⚠️  Categories without color mapping (using gray):")
        for cat in sorted(unmapped_categories):
            print(f"    - {cat}")
    
    print(f"\n  Unique categories with colors:")
    valid_colors = {k: v for k, v in color_usage.items() if k is not None and v is not None}
    for cat, hex_col in sorted(valid_colors.items())[:8]:
        print(f"    {cat:50s} → {hex_col}")
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
    
    sorted_layers = sorted(layers.items(), key=lambda x: x[1]['priority'])
    total_features = sum(layer['count'] for layer in layers.values())
    processed = 0
    
    print(f"\n  Rendering {len(sorted_layers)} layers with {total_features:,} total features...")
    
    for layer_idx, (layer_name, layer_data) in enumerate(sorted_layers, 1):
        features = layer_data['features']
        
        if not features:
            continue
        
        print(f"  [{layer_idx}/{len(sorted_layers)}] Rendering {layer_name}: {len(features)} features...", end='', flush=True)
        
        layer_color = features[0]['color']
        r, g, b = layer_color
        
        shapes = [(feat['geometry'], 1) for feat in features]
        
        try:
            mask = rasterize(
                shapes=shapes,
                out_shape=(height, width),
                transform=transform,
                fill=0,
                all_touched=True,
                dtype=np.uint8
            )
            
            layer_pixels = mask == 1
            pixels_affected = np.sum(layer_pixels)
            
            r_band[layer_pixels] = r
            g_band[layer_pixels] = g
            b_band[layer_pixels] = b
            a_band[layer_pixels] = 255
            
            processed += len(features)
            progress = (processed / total_features) * 100
            print(f" Done! ({pixels_affected:,} pixels, {progress:.1f}% complete)")
            
        except Exception as e:
            print(f" ERROR: {e}")
            continue
    
    opaque_pixels = np.sum(a_band > 0)
    coverage = (opaque_pixels / (height * width)) * 100
    
    print(f"\n  ✓ Rasterization complete!")
    print(f"  Coverage: {coverage:.2f}%")
    print(f"  Opaque pixels: {opaque_pixels:,} / {total_pixels:,}")
    
    return np.stack([r_band, g_band, b_band, a_band]), transform


def write_rgb_geotiff(rgba_data, transform, bounds, output_file):
    """Write RGB GeoTIFF with transparency - UNCOMPRESSED"""
    print(f"\n[5/6] Writing RGB GeoTIFF with transparency...")
    print(f"  Writing UNCOMPRESSED for maximum data integrity...")
    
    bands, height, width = rgba_data.shape
    
    print(f"\n  Pre-write data check:")
    for i, band_name in enumerate(['Red', 'Green', 'Blue', 'Alpha']):
        non_zero = np.count_nonzero(rgba_data[i])
        pct = (non_zero / (height * width)) * 100
        print(f"    {band_name} band: {non_zero:,} non-zero pixels ({pct:.2f}%)")
    
    with rasterio.open(
        output_file,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=4,
        dtype=np.uint8,
        crs='EPSG:4326',
        transform=transform,
        tiled=False,
        BIGTIFF='YES'
    ) as dst:
        for band_idx in range(4):
            band_names = ['Red', 'Green', 'Blue', 'Alpha']
            print(f"  Writing band {band_idx + 1} ({band_names[band_idx]})...", end='', flush=True)
            dst.write(rgba_data[band_idx], band_idx + 1)
            print(f" Done!")
        
        dst.update_tags(
            description='Visakhapatnam Master Plan Land Use Map (RGBA)',
            created_by='geotiff_visakhapatnam.py',
            alpha_band='4',
            compression='none'
        )
    
    file_size = os.path.getsize(output_file) / (1024 * 1024)
    expected_size = (height * width * 4) / (1024 * 1024)
    
    print(f"\n  ✓ File written: {output_file}")
    print(f"  ✓ File size: {file_size:.2f} MB")
    print(f"  Expected uncompressed size: {expected_size:.2f} MB")
    print(f"  Difference: {abs(file_size - expected_size):.2f} MB")
    
    if abs(file_size - expected_size) > expected_size * 0.05:
        print(f"  ⚠️  WARNING: File size mismatch! Data may be incomplete.")
    else:
        print(f"  ✓ File size matches expected - data write successful!")


def verify_output(output_file):
    """Verify output with detailed checks"""
    print(f"\n[6/6] Verifying output...")
    
    with rasterio.open(output_file) as src:
        print(f"  Dimensions: {src.width} × {src.height}")
        print(f"  Bands: {src.count}")
        print(f"  CRS: {src.crs}")
        print(f"  Compression: {src.compression}")
        
        if src.count == 4:
            r = src.read(1)
            g = src.read(2)
            b = src.read(3)
            a = src.read(4)
            
            opaque_pixels = np.sum(a > 0)
            transparent_pixels = np.sum(a == 0)
            
            print(f"  Alpha channel:")
            print(f"    Opaque pixels: {opaque_pixels:,}")
            print(f"    Transparent pixels: {transparent_pixels:,}")
            
            print(f"  Spatial distribution check:")
            h, w = a.shape
            quadrants = [
                (0, h//2, 0, w//2, "Top-Left"),
                (0, h//2, w//2, w, "Top-Right"),
                (h//2, h, 0, w//2, "Bottom-Left"),
                (h//2, h, w//2, w, "Bottom-Right")
            ]
            
            all_good = True
            for y1, y2, x1, x2, name in quadrants:
                quad_opaque = np.sum(a[y1:y2, x1:x2] > 0)
                quad_total = (y2-y1) * (x2-x1)
                pct = (quad_opaque / quad_total) * 100
                status = "✓" if pct > 5 else "❌"
                print(f"    {status} {name}: {pct:.1f}% coverage")
                if pct < 5:
                    all_good = False
            
            if all_good:
                print(f"\n  ✓ All quadrants have data - FULL MAP!")
            else:
                print(f"\n  ⚠️  Some quadrants have low coverage")
        
        print(f"  ✓ Verification complete")
        return True


def main():
    """Main execution"""
    print("=" * 70)
    print("Visakhapatnam GeoJSON to High-Resolution RGB GeoTIFF")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Input: {INPUT_DIR}")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Target resolution: {TARGET_RESOLUTION_METERS}m/pixel")
    print(f"  Equivalent zoom level: ~16")
    
    if not os.path.exists(INPUT_DIR):
        print(f"\n❌ ERROR: Directory not found: {INPUT_DIR}")
        return 1
    
    try:
        geojson_files = get_geojson_files(INPUT_DIR)
        print(f"\nFound {len(geojson_files)} GeoJSON files")
        
        bounds = calculate_bounds(geojson_files)
        width, height = calculate_dimensions(bounds, TARGET_RESOLUTION_METERS)
        layers = load_features_by_layer(geojson_files)
        
        if not layers:
            print("\n❌ ERROR: No valid features found!")
            return 1
        
        rgba_data, transform = rasterize_rgb(layers, bounds, width, height)
        write_rgb_geotiff(rgba_data, transform, bounds, OUTPUT_FILE)
        
        if not verify_output(OUTPUT_FILE):
            return 1
        
        print("\n" + "=" * 70)
        print("✓ SUCCESS: Visakhapatnam GeoTIFF created!")
        print("=" * 70)
        print(f"\nThe file contains the complete Visakhapatnam master plan map!")
        print(f"File: {OUTPUT_FILE}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())