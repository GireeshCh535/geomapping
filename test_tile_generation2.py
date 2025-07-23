# test_tile_generation.py
# Quick test script to verify tile generation fixes

import os
import sys
import django

# Setup Django
sys.path.append('/app')  # Adjust path as needed
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from maps.models import Plot, Land
from django.contrib.gis.geos import Polygon
from django.contrib.gis.db.models import Extent
import mercantile

def test_data_distribution():
    """Test how data is distributed across zoom levels"""
    
    print("🔍 Testing Real Estate Data Distribution")
    print("=" * 50)
    
    # Get total counts
    plot_count = Plot.objects.filter(is_active=True).count()
    land_count = Land.objects.filter(is_active=True).count()
    
    print(f"📊 Total Data:")
    print(f"   Plots: {plot_count:,}")
    print(f"   Lands: {land_count:,}")
    print(f"   Total: {(plot_count + land_count):,}")
    
    # Get bounds
    plot_extent = Plot.objects.filter(is_active=True).aggregate(extent=Extent('location'))['extent']
    land_extent = Land.objects.filter(is_active=True).aggregate(extent=Extent('location'))['extent']
    
    # Calculate combined bounds
    if plot_extent and land_extent:
        bounds = {
            'west': min(plot_extent[0], land_extent[0]),
            'south': min(plot_extent[1], land_extent[1]),
            'east': max(plot_extent[2], land_extent[2]),
            'north': max(plot_extent[3], land_extent[3])
        }
    elif plot_extent:
        bounds = {'west': plot_extent[0], 'south': plot_extent[1], 'east': plot_extent[2], 'north': plot_extent[3]}
    else:
        bounds = {'west': land_extent[0], 'south': land_extent[1], 'east': land_extent[2], 'north': land_extent[3]}
    
    print(f"\n📍 Geographic Bounds:")
    print(f"   West: {bounds['west']:.4f}")
    print(f"   South: {bounds['south']:.4f}")
    print(f"   East: {bounds['east']:.4f}")
    print(f"   North: {bounds['north']:.4f}")
    print(f"   Width: {bounds['east'] - bounds['west']:.4f} degrees")
    print(f"   Height: {bounds['north'] - bounds['south']:.4f} degrees")
    
    # Test specific tiles
    print(f"\n🎯 Testing Specific Tiles:")
    print("-" * 30)
    
    # Test zoom levels 4, 6, 8, 10
    test_zooms = [4, 6, 8, 10]
    
    for zoom in test_zooms:
        # Calculate total tiles at this zoom
        tiles = list(mercantile.tiles(
            bounds['west'], bounds['south'],
            bounds['east'], bounds['north'],
            zoom
        ))
        
        print(f"\nZoom {zoom}: {len(tiles)} total tiles")
        
        # Test center tile
        center_lng = (bounds['west'] + bounds['east']) / 2
        center_lat = (bounds['south'] + bounds['north']) / 2
        center_tile = mercantile.tile(center_lng, center_lat, zoom)
        
        # Get tile bounds
        tile_bounds_merc = mercantile.bounds(center_tile.x, center_tile.y, center_tile.z)
        tile_bounds = Polygon.from_bbox([
            tile_bounds_merc.west, tile_bounds_merc.south,
            tile_bounds_merc.east, tile_bounds_merc.north
        ])
        
        # Count features in center tile
        plots_in_tile = Plot.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        ).count()
        
        lands_in_tile = Land.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        ).count()
        
        print(f"   Center tile ({center_tile.x}, {center_tile.y}):")
        print(f"     Plots: {plots_in_tile}")
        print(f"     Lands: {lands_in_tile}")
        print(f"     Total: {plots_in_tile + lands_in_tile}")
        
        # Test a few random tiles
        import random
        sample_tiles = random.sample(tiles, min(3, len(tiles)))
        
        for i, tile in enumerate(sample_tiles):
            tile_bounds_merc = mercantile.bounds(tile.x, tile.y, tile.z)
            tile_bounds = Polygon.from_bbox([
                tile_bounds_merc.west, tile_bounds_merc.south,
                tile_bounds_merc.east, tile_bounds_merc.north
            ])
            
            plots_in_tile = Plot.objects.filter(
                location__intersects=tile_bounds,
                is_active=True
            ).count()
            
            lands_in_tile = Land.objects.filter(
                location__intersects=tile_bounds,
                is_active=True
            ).count()
            
            print(f"   Sample tile {i+1} ({tile.x}, {tile.y}):")
            print(f"     Plots: {plots_in_tile}")
            print(f"     Lands: {lands_in_tile}")
            print(f"     Total: {plots_in_tile + lands_in_tile}")

def test_specific_tile():
    """Test the specific tile that was showing only 1 point"""
    
    print(f"\n🔍 Testing Specific Tile: zoom 4, tile containing your screenshot")
    print("=" * 60)
    
    # The tile in your screenshot path: /media/real_estate_tiles_png/4/11/6
    # This means zoom=4, x=11, y=6
    zoom, x, y = 4, 11, 6
    
    # Get tile bounds
    tile_bounds_merc = mercantile.bounds(x, y, zoom)
    tile_bounds = Polygon.from_bbox([
        tile_bounds_merc.west, tile_bounds_merc.south,
        tile_bounds_merc.east, tile_bounds_merc.north
    ])
    
    print(f"Tile {zoom}/{x}/{y} bounds:")
    print(f"   West: {tile_bounds_merc.west:.4f}")
    print(f"   South: {tile_bounds_merc.south:.4f}")
    print(f"   East: {tile_bounds_merc.east:.4f}")
    print(f"   North: {tile_bounds_merc.north:.4f}")
    
    # Count all features in this tile
    plots_in_tile = Plot.objects.filter(
        location__intersects=tile_bounds,
        is_active=True
    )
    
    lands_in_tile = Land.objects.filter(
        location__intersects=tile_bounds,
        is_active=True
    )
    
    print(f"\nFeatures in tile {zoom}/{x}/{y}:")
    print(f"   Plots: {plots_in_tile.count()}")
    print(f"   Lands: {lands_in_tile.count()}")
    print(f"   Total: {plots_in_tile.count() + lands_in_tile.count()}")
    
    # Show first few features
    print(f"\nFirst 10 plots in this tile:")
    for i, plot in enumerate(plots_in_tile[:10]):
        print(f"   {i+1}. Plot {plot.plot_id}: {plot.marker_title} at ({plot.location.x:.4f}, {plot.location.y:.4f})")
    
    print(f"\nFirst 10 lands in this tile:")
    for i, land in enumerate(lands_in_tile[:10]):
        print(f"   {i+1}. Land {land.land_id}: {land.marker_title} at ({land.location.x:.4f}, {land.location.y:.4f})")
    
    # Test old vs new limits
    print(f"\n📊 Feature Limiting Analysis:")
    total_features = plots_in_tile.count() + lands_in_tile.count()
    
    # Old limits
    old_limit = 25  # zoom 4 was limited to 25 features
    print(f"   Old limit (zoom {zoom}): {old_limit} features")
    print(f"   Available features: {total_features}")
    print(f"   Would show: {min(old_limit, total_features)} features")
    print(f"   Missing: {max(0, total_features - old_limit)} features")
    
    # New limits
    new_limit = 1000  # our new limit for zoom 4
    print(f"   New limit (zoom {zoom}): {new_limit} features")
    print(f"   Will show: {min(new_limit, total_features)} features")
    print(f"   Missing: {max(0, total_features - new_limit)} features")

if __name__ == "__main__":
    print("🚀 Starting Real Estate Tile Generation Test")
    print("=" * 60)
    
    try:
        test_data_distribution()
        test_specific_tile()
        
        print(f"\n✅ Test completed successfully!")
        print(f"\n💡 Recommendations:")
        print(f"   1. Use the updated management commands with higher feature limits")
        print(f"   2. Consider implementing clustering for zoom levels 4-8")
        print(f"   3. Test tiles at zoom levels 10+ for detailed view")
        print(f"   4. Monitor tile file sizes - they may be larger now")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()