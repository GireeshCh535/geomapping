#!/usr/bin/env python3
"""
Test script to generate tiles for all layers of a city
Provides sample URLs for testing after generation
"""

import os
import sys
import django
import time
import mercantile

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from maps.models import City, DataLayer, VectorTileLayer
from maps.services import VectorTileService

def generate_city_tiles(city_slug, min_zoom=8, max_zoom=14, force=False):
    """Generate tiles for all layers of a city"""
    
    print(f"🗺️  Generating tiles for city: {city_slug}")
    print(f"📊 Zoom levels: {min_zoom} to {max_zoom}")
    print(f"🔄 Force regenerate: {force}")
    print("=" * 60)
    
    try:
        city = City.objects.get(slug=city_slug, is_active=True)
    except City.DoesNotExist:
        print(f"❌ City not found: {city_slug}")
        return None
    
    # Get layers to process
    layers = DataLayer.objects.filter(
        city=city,
        is_processed=True
    ).select_related('category')
    
    if not layers.exists():
        print("⚠️  No processed layers found")
        return None
    
    print(f"📋 Found {layers.count()} layers to process")
    
    # Initialize tile service
    tile_service = VectorTileService()
    
    # Process each layer
    results = []
    total_tiles_generated = 0
    successful_layers = 0
    failed_layers = 0
    
    start_time = time.time()
    
    for i, layer in enumerate(layers, 1):
        print(f"\n📂 [{i}/{layers.count()}] Processing: {layer.name}")
        print(f"   📊 Features: {layer.feature_count:,}")
        
        layer_result = {
            'layer_slug': layer.slug,
            'layer_name': layer.name,
            'feature_count': layer.feature_count,
            'status': 'pending'
        }
        
        try:
            # Check if tiles already exist
            try:
                vector_tile_layer = VectorTileLayer.objects.get(layer=layer)
                if vector_tile_layer.is_generated and not force:
                    print(f"   ✅ Tiles already exist ({vector_tile_layer.total_tiles:,} tiles)")
                    layer_result.update({
                        'status': 'existing',
                        'tiles_generated': vector_tile_layer.total_tiles,
                        'message': 'Tiles already exist'
                    })
                    successful_layers += 1
                    results.append(layer_result)
                    continue
            except VectorTileLayer.DoesNotExist:
                vector_tile_layer = None
            
            # Generate tiles
            layer_start_time = time.time()
            result = tile_service.generate_layer_tiles(layer, min_zoom, max_zoom)
            layer_duration = time.time() - layer_start_time
            
            tiles_count = result.get('tiles_generated', 0)
            
            # Update or create vector tile layer record
            if vector_tile_layer:
                vector_tile_layer.min_zoom = min_zoom
                vector_tile_layer.max_zoom = max_zoom
                vector_tile_layer.is_generated = True
                vector_tile_layer.total_tiles = tiles_count
                vector_tile_layer.save()
            else:
                VectorTileLayer.objects.create(
                    layer=layer,
                    min_zoom=min_zoom,
                    max_zoom=max_zoom,
                    is_generated=True,
                    total_tiles=tiles_count
                )
            
            # Update layer status
            layer.tiles_generated = True
            layer.save()
            
            layer_result.update({
                'status': 'generated',
                'tiles_generated': tiles_count,
                'duration_seconds': round(layer_duration, 2),
                'performance_tiles_per_second': round(tiles_count / layer_duration, 2) if layer_duration > 0 else 0
            })
            
            total_tiles_generated += tiles_count
            successful_layers += 1
            
            print(f"   ✅ Generated {tiles_count:,} tiles in {layer_duration:.1f}s")
            if tiles_count > 0:
                tiles_per_second = tiles_count / layer_duration if layer_duration > 0 else 0
                print(f"   ⚡ Performance: {tiles_per_second:.1f} tiles/second")
            
        except Exception as e:
            failed_layers += 1
            layer_result.update({
                'status': 'failed',
                'error': str(e),
                'tiles_generated': 0
            })
            print(f"   ❌ Failed: {str(e)}")
        
        results.append(layer_result)
    
    # Calculate total time
    total_duration = time.time() - start_time
    
    # Print summary
    print(f"\n📊 Generation Summary:")
    print(f"   ✅ Successful layers: {successful_layers}")
    print(f"   ❌ Failed layers: {failed_layers}")
    print(f"   🗺️  Total tiles generated: {total_tiles_generated:,}")
    print(f"   ⏱️  Total time: {total_duration:.1f}s")
    
    if total_tiles_generated > 0:
        avg_tiles_per_second = total_tiles_generated / total_duration
        print(f"   ⚡ Average performance: {avg_tiles_per_second:.1f} tiles/second")
    
    return {
        'city_slug': city_slug,
        'results': results,
        'summary': {
            'total_layers': len(results),
            'successful_layers': successful_layers,
            'failed_layers': failed_layers,
            'total_tiles_generated': total_tiles_generated,
            'total_duration_seconds': round(total_duration, 2)
        }
    }

def generate_sample_urls(city_slug, results, min_zoom, max_zoom):
    """Generate sample URLs for testing"""
    
    print(f"\n🎯 Sample URLs for Testing:")
    print("=" * 60)
    
    # Get city center coordinates
    try:
        city = City.objects.get(slug=city_slug)
        if city.center_lat and city.center_lng:
            center_lat, center_lng = city.center_lat, city.center_lng
        else:
            center_lat, center_lng = 12.9716, 77.5946
    except:
        center_lat, center_lng = 12.9716, 77.5946
    
    # Generate sample tile coordinates
    sample_zooms = [min_zoom, (min_zoom + max_zoom) // 2, max_zoom]
    
    for zoom in sample_zooms:
        # Get tile coordinates for the center point
        tile = mercantile.tile(center_lng, center_lat, zoom)
        
        print(f"\n📍 Zoom {zoom} (tile {tile.z}/{tile.x}/{tile.y}):")
        
        # Individual layer tiles
        for result in results:
            if result['status'] in ['generated', 'existing'] and result['tiles_generated'] > 0:
                layer_slug = result['layer_slug']
                print(f"   • {layer_slug}: /api/tiles/{city_slug}/{layer_slug}/{tile.z}/{tile.x}/{tile.y}.mvt")
        
        # Combined tile
        print(f"   • Combined: /api/tiles/{city_slug}/combined/{tile.z}/{tile.x}/{tile.y}.mvt")
        
        # PNG versions
        if zoom <= 14:
            print(f"   • PNG Combined: /api/tiles/{city_slug}/combined/{tile.z}/{tile.x}/{tile.y}.png")
    
    # Additional test URLs
    print(f"\n🔗 Additional Test URLs:")
    print(f"   • City layers: GET /api/cities/{city_slug}/layers/")
    print(f"   • City complete: GET /api/cities/{city_slug}/complete/")
    print(f"   • Progressive loading: GET /api/cities/{city_slug}/progressive/")
    
    # Show sample coordinates
    print(f"\n🧪 Sample Tile Coordinates for Testing:")
    additional_coords = [
        (12.9716, 77.5946, 12),  # Bangalore center
        (12.9716, 77.5946, 10),  # Lower zoom
        (12.9716, 77.5946, 14),  # Higher zoom
    ]
    
    for lat, lng, z in additional_coords:
        tile = mercantile.tile(lng, lat, z)
        print(f"   • {z}/{tile.x}/{tile.y} (lat: {lat:.4f}, lng: {lng:.4f})")

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python test_city_tiles.py <city_slug> [min_zoom] [max_zoom] [--force]")
        print("Example: python test_city_tiles.py bangalore 8 14 --force")
        return
    
    city_slug = sys.argv[1]
    min_zoom = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    max_zoom = int(sys.argv[3]) if len(sys.argv) > 3 else 14
    force = '--force' in sys.argv
    
    # Generate tiles
    result = generate_city_tiles(city_slug, min_zoom, max_zoom, force)
    
    if result and result['summary']['successful_layers'] > 0:
        # Generate sample URLs
        generate_sample_urls(city_slug, result['results'], min_zoom, max_zoom)
        
        print(f"\n✅ Tile generation completed for {city_slug}!")
        print(f"🎯 You can now test the tiles using the sample URLs above.")
    else:
        print(f"\n❌ Tile generation failed or no successful layers.")

if __name__ == '__main__':
    main() 