#!/usr/bin/env python3
"""
Debug script to analyze RRR tile generation issues
"""

import os
import sys
import django
import mercantile
from PIL import Image
import io

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from maps.models import DataLayer, GeoFeature
from maps.services import VectorTileService
from maps.tile_rendering_service import TileRenderingService

def debug_rrr_tiles():
    """Debug RRR tile generation issues"""
    
    print("🔍 Debugging RRR Tile Generation Issues")
    print("=" * 60)
    
    # Get RRR layer and features
    layer = DataLayer.objects.get(slug='hyderabad_rrr')
    features = GeoFeature.objects.filter(layer=layer)
    
    print(f"📊 Layer: {layer.name}")
    print(f"📊 Features: {features.count()}")
    
    # Analyze each feature
    for i, feature in enumerate(features):
        print(f"\n📍 Feature {i}:")
        print(f"   Type: {feature.geometry.geom_type}")
        print(f"   Length: {feature.geometry.length:.6f}")
        print(f"   Bounds: {feature.geometry.extent}")
        
        # Check tile coverage at different zoom levels
        for zoom in [8, 9, 10, 11]:
            tiles = list(mercantile.tiles(*feature.geometry.extent, zoom))
            print(f"   Zoom {zoom}: {len(tiles)} tiles")
    
    # Test specific problematic tiles
    print(f"\n🔍 Testing Specific Tiles:")
    
    # Initialize services
    vector_service = VectorTileService()
    render_service = TileRenderingService()
    
    # Test tiles at zoom 10 where we saw issues
    test_tiles = [
        (10, 733, 460), (10, 733, 461), (10, 733, 462), (10, 733, 463),
        (10, 734, 460), (10, 734, 461), (10, 734, 462), (10, 734, 463),
        (10, 735, 460), (10, 735, 461), (10, 735, 462), (10, 735, 463),
        (10, 736, 460), (10, 736, 461), (10, 736, 462), (10, 736, 463)
    ]
    
    for z, x, y in test_tiles:
        print(f"\n📍 Tile {z}/{x}/{y}:")
        
        try:
            # Generate MVT
            mvt_data = vector_service.generate_tile(layer, z, x, y)
            if mvt_data:
                print(f"   ✅ MVT generated: {len(mvt_data)} bytes")
                
                # Decode MVT to check features
                import mapbox_vector_tile
                decoded = mapbox_vector_tile.decode(mvt_data)
                
                for layer_name, layer_data in decoded.items():
                    features_in_tile = layer_data.get('features', [])
                    print(f"   📊 Features in tile: {len(features_in_tile)}")
                    
                    for j, feat in enumerate(features_in_tile):
                        geom = feat.get('geometry', {})
                        coords = geom.get('coordinates', [])
                        print(f"     Feature {j}: {geom.get('type')} - {len(coords)} coordinate sets")
                        
                        # Check if coordinates are too small after transformation
                        if geom.get('type') == 'LineString' and coords:
                            # Calculate the pixel extent of the line
                            min_x = min(c[0] for c in coords)
                            max_x = max(c[0] for c in coords)
                            min_y = min(c[1] for c in coords)
                            max_y = max(c[1] for c in coords)
                            
                            extent_x = max_x - min_x
                            extent_y = max_y - min_y
                            
                            print(f"       Pixel extent: {extent_x:.2f} x {extent_y:.2f}")
                            
                            # If extent is too small, it won't render
                            if extent_x < 1.0 or extent_y < 1.0:
                                print(f"       ⚠️  EXTENT TOO SMALL - won't render!")
                
                # Render to PNG
                png_data = render_service.combined_mvt_to_png(mvt_data, [layer], z, x, y)
                if png_data:
                    img = Image.open(io.BytesIO(png_data))
                    
                    # Count non-transparent pixels
                    non_transparent = 0
                    for px in range(img.width):
                        for py in range(img.height):
                            pixel = img.getpixel((px, py))
                            if pixel[3] > 10:  # Non-transparent
                                non_transparent += 1
                    
                    print(f"   🎨 PNG rendered: {len(png_data)} bytes, {non_transparent} non-transparent pixels")
                    
                    if non_transparent == 0:
                        print(f"   ❌ TILE IS BLANK!")
                    elif non_transparent < 100:
                        print(f"   ⚠️  TILE HAS VERY LITTLE DATA")
                else:
                    print(f"   ❌ PNG rendering failed")
            else:
                print(f"   ❌ MVT generation failed")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

def analyze_geometry_simplification():
    """Analyze geometry simplification issues"""
    
    print(f"\n🔍 Analyzing Geometry Simplification")
    print("=" * 60)
    
    layer = DataLayer.objects.get(slug='hyderabad_rrr')
    features = GeoFeature.objects.filter(layer=layer)
    
    for i, feature in enumerate(features):
        print(f"\n📍 Feature {i} Original:")
        print(f"   Points: {len(feature.geometry.coords)}")
        print(f"   Length: {feature.geometry.length:.6f}")
        
        # Test different simplification tolerances
        for tolerance in [0.0001, 0.0005, 0.001, 0.005]:
            simplified = feature.geometry.simplify(tolerance)
            print(f"   Tolerance {tolerance}: {len(simplified.coords)} points, length: {simplified.length:.6f}")
            
            # Check if simplification is too aggressive
            if len(simplified.coords) < 2:
                print(f"     ⚠️  OVER-SIMPLIFIED - not enough points!")
            elif simplified.length < feature.geometry.length * 0.5:
                print(f"     ⚠️  OVER-SIMPLIFIED - length reduced by >50%!")

if __name__ == "__main__":
    debug_rrr_tiles()
    analyze_geometry_simplification()
