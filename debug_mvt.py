#!/usr/bin/env python3
"""
Detailed MVT Debugging Script
Analyzes MVT files to understand structure and content issues
"""

import sys
import os
import mapbox_vector_tile
import struct

def hex_dump(data, max_bytes=100):
    """Create a hex dump of the first few bytes of data."""
    hex_str = ' '.join(f'{b:02x}' for b in data[:max_bytes])
    if len(data) > max_bytes:
        hex_str += f' ... (truncated, total {len(data)} bytes)'
    return hex_str

def analyze_mvt_structure(file_path):
    """
    Detailed analysis of MVT file structure and content.
    """
    print("🔍 DETAILED MVT ANALYSIS")
    print("=" * 60)
    
    try:
        # Basic file info
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return
        
        file_size = os.path.getsize(file_path)
        print(f"📁 File: {file_path}")
        print(f"📏 Size: {file_size:,} bytes")
        print()
        
        # Read file
        with open(file_path, 'rb') as f:
            tile_data = f.read()
        
        if not tile_data:
            print("❌ File is completely empty")
            return
        
        print(f"🔢 Raw data (first 50 bytes): {hex_dump(tile_data, 50)}")
        print()
        
        # Try to decode as MVT
        try:
            decoded_tile = mapbox_vector_tile.decode(tile_data)
            print("✅ Successfully decoded as MVT")
            print(f"📊 Number of layers: {len(decoded_tile)}")
            print()
            
            if not decoded_tile:
                print("⚠️  WARNING: Decoded tile has no layers!")
                print("This could indicate:")
                print("  - Empty tile (no features in this area)")
                print("  - Tile generation issue")
                print("  - File corruption")
                return
            
            # Analyze each layer
            for layer_name, layer_data in decoded_tile.items():
                print(f"🔹 LAYER: {layer_name}")
                print(f"   Version: {layer_data.get('version', 'unknown')}")
                print(f"   Extent: {layer_data.get('extent', 'unknown')}")
                
                features = layer_data.get('features', [])
                print(f"   Features: {len(features)}")
                
                if features:
                    print("   Feature details:")
                    for i, feature in enumerate(features[:3]):  # Show first 3 features
                        geom = feature.get('geometry', {})
                        props = feature.get('properties', {})
                        print(f"     Feature {i+1}:")
                        print(f"       Type: {geom.get('type', 'unknown')}")
                        print(f"       Properties: {dict(list(props.items())[:5])}")  # First 5 properties
                    
                    if len(features) > 3:
                        print(f"     ... and {len(features) - 3} more features")
                else:
                    print("   ⚠️  No features found in this layer")
                    print("   Possible reasons:")
                    print("     - Tile is outside data bounds")
                    print("     - Zoom level too high/low")
                    print("     - Data filtering removed all features")
                    print("     - Tile generation error")
                
                print()
            
        except Exception as e:
            print(f"❌ Failed to decode as MVT: {str(e)}")
            print()
            print("🔍 Trying alternative analysis...")
            
            # Check if it might be a different format
            if tile_data.startswith(b'\x1f\x8b'):
                print("📦 File appears to be gzipped")
                print("Try decompressing first: gunzip your_file.mvt")
            elif tile_data.startswith(b'PK'):
                print("📦 File appears to be a ZIP archive")
            elif len(tile_data) < 10:
                print("📏 File is very small - might be empty or corrupted")
            else:
                print("❓ Unknown format - not a valid MVT file")
        
        # Additional checks
        print("🔍 ADDITIONAL CHECKS:")
        print("-" * 30)
        
        # Check for common MVT patterns
        if b'layers' in tile_data:
            print("✅ Contains 'layers' keyword")
        if b'features' in tile_data:
            print("✅ Contains 'features' keyword")
        if b'geometry' in tile_data:
            print("✅ Contains 'geometry' keyword")
        
        # Check file permissions
        try:
            with open(file_path, 'rb') as f:
                f.read(1)
            print("✅ File is readable")
        except PermissionError:
            print("❌ File permission error")
        
        print()
        print("💡 SUGGESTIONS:")
        print("-" * 20)
        print("1. Check tile coordinates (x, y, z) - maybe outside data bounds")
        print("2. Verify tile generation process")
        print("3. Check if tile was properly saved/transferred")
        print("4. Try generating the same tile again")
        print("5. Check tile server logs for errors")
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python debug_mvt.py <path_to_mvt_file>")
        print("Example: python debug_mvt.py C:\\Users\\ADMIN\\Downloads\\30408.mvt")
        sys.exit(1)
    
    file_path = sys.argv[1]
    analyze_mvt_structure(file_path)

if __name__ == "__main__":
    main() 