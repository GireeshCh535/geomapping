#!/usr/bin/env python3
"""
Comprehensive debug script for tile generation issue
Tests the specific Amaravati coordinates and understands why tiles aren't generated at low zoom levels
"""

import os
import sys
import django
import mercantile

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from maps.models import City, DataLayer, GeoFeature
from maps.services import VectorTileService
from django.contrib.gis.geos import Point, Polygon

def test_amaravati_tile_generation():
    """Test tile generation for Amaravati coordinates"""
    
    # Test coordinates
    test_lng, test_lat = 80.45215550279937, 16.518144085425448
    
    print(f"🔍 Testing Amaravati coordinates: [{test_lng}, {test_lat}]")
    print("=" * 80)
    
    try:
        # Get Amaravati city
        city = City.objects.get(slug='amaravati', is_active=True)
        print(f"✅ Found city: {city.name}")
        
        # Get all layers for Amaravati
        layers = DataLayer.objects.filter(
            city=city,
            is_processed=True
        ).select_related('category')
        
        print(f"📋 Found {layers.count()} processed layers")
        
        if not layers.exists():
            print("❌ No processed layers found for Amaravati")
            return
        
        # Initialize tile service
        tile_service = VectorTileService()
        
        # Test each layer
        for layer in layers:
            print(f"\n📂 Layer: {layer.name} ({layer.slug})")
            print("-" * 50)
            
            # Get layer bounds
            layer_bounds = tile_service._get_layer_bounds(layer)
            if not layer_bounds:
                print(f"   ❌ No bounds available for layer")
                continue
            
            print(f"   📐 Layer bounds: {layer_bounds}")
            
            # Test each zoom level
            for zoom in range(8, 19):  # 8 to 18
                print(f"\n   📍 Zoom Level {zoom}")
                
                # Get tile coordinates for the test point
                tile = mercantile.tile(test_lng, test_lat, zoom)
                bounds = mercantile.bounds(tile)
                
                print(f"      Tile: {tile.z}/{tile.x}/{tile.y}")
                print(f"      Tile bounds: {bounds.west:.6f}, {bounds.south:.6f} to {bounds.east:.6f}, {bounds.north:.6f}")
                
                # Check if this tile should be generated based on layer bounds
                tiles_for_zoom = list(mercantile.tiles(
                    layer_bounds['west'], layer_bounds['south'],
                    layer_bounds['east'], layer_bounds['north'],
                    zoom
                ))
                
                # Check if our test tile is in the list
                test_tile_in_list = any(t.z == tile.z and t.x == tile.x and t.y == tile.y for t in tiles_for_zoom)
                
                print(f"      Total tiles for zoom {zoom}: {len(tiles_for_zoom)}")
                print(f"      Test tile in generation list: {'✅ YES' if test_tile_in_list else '❌ NO'}")
                
                if not test_tile_in_list:
                    print(f"      ⚠️  This tile won't be generated because it's outside layer bounds!")
                    continue
                
                # Check if there are features in this tile
                tile_bounds_polygon = tile_service._get_tile_bounds(tile.z, tile.x, tile.y)
                
                intersecting_features = GeoFeature.objects.filter(
                    layer=layer,
                    geometry__intersects=tile_bounds_polygon,
                    is_valid=True
                ).count()
                
                print(f"      Features in tile: {intersecting_features}")
                
                if intersecting_features > 0:
                    print(f"      🔧 Attempting tile generation...")
                    mvt_data = tile_service.generate_tile(layer, tile.z, tile.x, tile.y)
                    
                    if mvt_data:
                        print(f"      ✅ Tile generated: {len(mvt_data)} bytes")
                    else:
                        print(f"      ❌ Tile generation failed")
                else:
                    print(f"      ⚠️  No features intersect with tile bounds")
        
        print(f"\n" + "=" * 80)
        print("🎯 ANALYSIS")
        print("=" * 80)
        print("The issue is likely one of these:")
        print("1. Layer bounds are too small/narrow")
        print("2. Features are outside the calculated layer bounds")
        print("3. Tile generation only happens for tiles within layer bounds")
        print("4. Coordinate system mismatch")
        
    except City.DoesNotExist:
        print(f"❌ City 'amaravati' not found")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_layer_bounds_calculation():
    """Test how layer bounds are calculated"""
    
    print(f"\n🔧 TESTING LAYER BOUNDS CALCULATION")
    print("=" * 80)
    
    try:
        city = City.objects.get(slug='amaravati', is_active=True)
        layers = DataLayer.objects.filter(city=city, is_processed=True).select_related('category')
        
        for layer in layers:
            print(f"\n📂 Layer: {layer.name} ({layer.slug})")
            
            # Check stored bounds
            if all([layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax]):
                print(f"   📐 Stored bounds: {layer.bbox_xmin}, {layer.bbox_ymin} to {layer.bbox_xmax}, {layer.bbox_ymax}")
            else:
                print(f"   ⚠️  No stored bounds")
            
            # Calculate bounds from features
            from django.contrib.gis.db.models import Extent
            extent = GeoFeature.objects.filter(
                layer=layer, 
                is_valid=True
            ).aggregate(extent=Extent('geometry'))['extent']
            
            if extent:
                print(f"   📐 Calculated bounds: {extent[0]}, {extent[1]} to {extent[2]}, {extent[3]}")
                
                # Check if our test point is within these bounds
                test_lng, test_lat = 80.45215550279937, 16.518144085425448
                within_bounds = (extent[0] <= test_lng <= extent[2] and extent[1] <= test_lat <= extent[3])
                print(f"   🎯 Test point within bounds: {'✅ YES' if within_bounds else '❌ NO'}")
            else:
                print(f"   ❌ Could not calculate bounds from features")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_feature_distribution():
    """Test how features are distributed around the test coordinates"""
    
    print(f"\n📊 TESTING FEATURE DISTRIBUTION")
    print("=" * 80)
    
    try:
        city = City.objects.get(slug='amaravati', is_active=True)
        layers = DataLayer.objects.filter(city=city, is_processed=True).select_related('category')
        
        test_lng, test_lat = 80.45215550279937, 16.518144085425448
        test_point = Point(test_lng, test_lat, srid=4326)
        
        for layer in layers:
            print(f"\n📂 Layer: {layer.name} ({layer.slug})")
            
            # Count total features
            total_features = GeoFeature.objects.filter(layer=layer, is_valid=True).count()
            print(f"   Total features: {total_features}")
            
            if total_features == 0:
                continue
            
            # Check features within different distances
            distances = [0.001, 0.01, 0.1, 1.0]  # degrees
            
            for distance in distances:
                buffer = test_point.buffer(distance)
                nearby_features = GeoFeature.objects.filter(
                    layer=layer,
                    geometry__intersects=buffer,
                    is_valid=True
                ).count()
                
                print(f"   Features within {distance}°: {nearby_features}")
            
            # Show some sample features
            sample_features = GeoFeature.objects.filter(
                layer=layer,
                is_valid=True
            )[:5]
            
            print(f"   Sample features:")
            for i, feature in enumerate(sample_features):
                if hasattr(feature.geometry, 'centroid'):
                    centroid = feature.geometry.centroid
                    print(f"     {i+1}. Feature {feature.id}: ({centroid.x:.6f}, {centroid.y:.6f})")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 COMPREHENSIVE TILE GENERATION DEBUG")
    print("=" * 80)
    
    test_amaravati_tile_generation()
    test_layer_bounds_calculation()
    test_feature_distribution()
    
    print(f"\n✅ Debugging complete!")
