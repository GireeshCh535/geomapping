#!/usr/bin/env python3
"""
MVT (Mapbox Vector Tile) Validation Script
Validates MVT files using mapbox-vector-tile library
"""

import sys
import os
import mapbox_vector_tile
from pathlib import Path

def validate_mvt_file(file_path):
    """
    Validate an MVT file and provide detailed information about its contents.
    
    Args:
        file_path (str): Path to the MVT file
        
    Returns:
        dict: Validation results and tile information
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return {
                'valid': False,
                'error': f'File not found: {file_path}'
            }
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Read the MVT file
        with open(file_path, 'rb') as f:
            tile_data = f.read()
        
        if not tile_data:
            return {
                'valid': False,
                'error': 'File is empty'
            }
        
        # Try to decode the MVT
        try:
            decoded_tile = mapbox_vector_tile.decode(tile_data)
        except Exception as e:
            return {
                'valid': False,
                'error': f'Failed to decode MVT: {str(e)}',
                'file_size': file_size
            }
        
        # Analyze the decoded tile
        layers_info = {}
        total_features = 0
        
        for layer_name, layer_data in decoded_tile.items():
            features = layer_data.get('features', [])
            layer_info = {
                'feature_count': len(features),
                'extent': layer_data.get('extent', 'unknown'),
                'version': layer_data.get('version', 'unknown')
            }
            
            # Analyze feature types
            feature_types = {}
            for feature in features:
                geom_type = feature.get('geometry', {}).get('type', 'unknown')
                feature_types[geom_type] = feature_types.get(geom_type, 0) + 1
            
            layer_info['feature_types'] = feature_types
            layers_info[layer_name] = layer_info
            total_features += len(features)
        
        return {
            'valid': True,
            'file_size': file_size,
            'layer_count': len(decoded_tile),
            'total_features': total_features,
            'layers': layers_info,
            'layer_names': list(decoded_tile.keys())
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': f'Unexpected error: {str(e)}'
        }

def print_validation_results(results):
    """Print validation results in a formatted way."""
    print("=" * 60)
    print("MVT FILE VALIDATION RESULTS")
    print("=" * 60)
    
    if not results['valid']:
        print(f"❌ VALIDATION FAILED")
        print(f"Error: {results['error']}")
        if 'file_size' in results:
            print(f"File size: {results['file_size']} bytes")
        return
    
    print(f"✅ VALIDATION SUCCESSFUL")
    print(f"📁 File size: {results['file_size']:,} bytes")
    print(f"📊 Layers: {results['layer_count']}")
    print(f"📍 Total features: {results['total_features']:,}")
    print()
    
    print("📋 LAYER DETAILS:")
    print("-" * 40)
    
    for layer_name, layer_info in results['layers'].items():
        print(f"\n🔹 Layer: {layer_name}")
        print(f"   Features: {layer_info['feature_count']:,}")
        print(f"   Extent: {layer_info['extent']}")
        print(f"   Version: {layer_info['version']}")
        
        if layer_info['feature_types']:
            print(f"   Geometry types:")
            for geom_type, count in layer_info['feature_types'].items():
                print(f"     - {geom_type}: {count:,}")
    
    print("\n" + "=" * 60)

def main():
    """Main function to validate MVT file."""
    if len(sys.argv) != 2:
        print("Usage: python validate_mvt.py <path_to_mvt_file>")
        print("Example: python validate_mvt.py C:\\Users\\ADMIN\\Downloads\\30408.mvt")
        sys.exit(1)
    
    file_path = sys.argv[1]
    print(f"🔍 Validating MVT file: {file_path}")
    print()
    
    results = validate_mvt_file(file_path)
    print_validation_results(results)
    
    if results['valid']:
        print("🎉 The MVT file is valid and ready to use!")
    else:
        print("💡 The MVT file has issues that need to be addressed.")
        sys.exit(1)

if __name__ == "__main__":
    main() 