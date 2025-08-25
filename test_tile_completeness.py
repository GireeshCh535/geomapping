#!/usr/bin/env python3
"""
Comprehensive test to verify tile completeness and data integrity
"""

import os
import sys
import django
import mercantile
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'geo_mapping.settings')
django.setup()

from maps.models import City, DataLayer, GeoFeature
from maps.services import VectorTileService
from django.contrib.gis.geos import Polygon
from django.contrib.gis.db.models import Extent

def test_tile_completeness():
    """Test that all tiles have complete data"""
    
    print("🧪 COMPREHENSIVE TILE COMPLETENESS TEST")
    print("=" * 60)
    
    # Test parameters
    target_lng, target_lat = 80.45215550279937, 16.518144085425448
    test_zoom_levels = [8, 10, 12, 14, 16, 18]
    radius = 0.01
    
    try:
        # Get Amaravati data
        city = City.objects.get(slug='amaravati')
        layer = DataLayer.objects.get(slug='amaravati_master_plan')
        
        print(f"📍 Testing coordinates: [{target_lng}, {target_lat}]")
        print(f"🏙️  City: {city.name}")
        print(f"📂 Layer: {layer.name}")
        print(f"📊 Total features in layer: {layer.geofeature_set.filter(is_valid=True).count()}")
        print()
        
        # Initialize tile service
        tile_service = VectorTileService()
        
        # Test each zoom level
        for zoom in test_zoom_levels:
            print(f"🔍 Testing Zoom Level {zoom}")
            print("-" * 40)
            
            # Get tiles for this zoom level
            tiles = list(mercantile.tiles(
                target_lng - radius, 
                target_lat - radius, 
                target_lng + radius, 
                target_lat + radius, 
                zoom
            ))
            
            print(f"   📋 Found {len(tiles)} tiles for zoom {zoom}")
            
            for tile in tiles:
                print(f"   🧩 Testing tile: {tile.z}/{tile.x}/{tile.y}")
                
                # Get tile bounds
                bounds = mercantile.bounds(tile)
                bbox_polygon = Polygon.from_bbox([
                    bounds.west, bounds.south, bounds.east, bounds.north
                ])
                
                # Count features in this tile
                features_in_tile = GeoFeature.objects.filter(
                    layer=layer,
                    geometry__intersects=bbox_polygon,
                    is_valid=True
                )
                feature_count = features_in_tile.count()
                
                print(f"      📊 Features in tile: {feature_count}")
                
                if feature_count == 0:
                    print(f"      ❌ WARNING: No features found in tile {tile.z}/{tile.x}/{tile.y}")
                    continue
                
                # Test tile generation
                try:
                    mvt_data = tile_service.generate_tile(layer, tile.z, tile.x, tile.y)
                    
                    if mvt_data:
                        # Decode MVT to check content
                        import mapbox_vector_tile
                        decoded = mapbox_vector_tile.decode(mvt_data)
                        
                        if 'amaravati_master_plan' in decoded:
                            layer_data = decoded['amaravati_master_plan']
                            mvt_features = len(layer_data['features'])
                            
                            print(f"      ✅ MVT generated: {mvt_features} features")
                            
                            # Check for colors/symbology
                            has_colors = False
                            for feature in layer_data['features']:
                                if 'properties' in feature and feature['properties']:
                                    has_colors = True
                                    break
                            
                            if has_colors:
                                print(f"      🎨 Colors/symbology: ✅ Present")
                            else:
                                print(f"      ⚠️  Colors/symbology: Missing")
                            
                            # Check geometry completeness
                            valid_geometries = 0
                            for feature in layer_data['features']:
                                if 'geometry' in feature and feature['geometry']:
                                    if feature['geometry']['type'] in ['Polygon', 'MultiPolygon']:
                                        if feature['geometry']['coordinates']:
                                            valid_geometries += 1
                            
                            print(f"      📐 Valid geometries: {valid_geometries}/{mvt_features}")
                            
                            if mvt_features == 0:
                                print(f"      ❌ ERROR: MVT has 0 features despite {feature_count} features in tile")
                            elif mvt_features < feature_count * 0.8:  # Allow some loss due to simplification
                                print(f"      ⚠️  WARNING: MVT has fewer features ({mvt_features}) than expected ({feature_count})")
                            else:
                                print(f"      ✅ Feature count: Good ({mvt_features}/{feature_count})")
                                
                        else:
                            print(f"      ❌ ERROR: No layer data in MVT")
                            
                    else:
                        print(f"      ❌ ERROR: Failed to generate MVT")
                        
                except Exception as e:
                    print(f"      ❌ ERROR: {e}")
                
                print()
            
            print()
        
        # Test specific problematic tile
        print("🎯 TESTING SPECIFIC PROBLEMATIC TILE")
        print("-" * 40)
        problematic_tile = mercantile.tile(target_lng, target_lat, 8)
        print(f"   🧩 Tile: {problematic_tile.z}/{problematic_tile.x}/{problematic_tile.y}")
        
        bounds = mercantile.bounds(problematic_tile)
        bbox_polygon = Polygon.from_bbox([
            bounds.west, bounds.south, bounds.east, bounds.north
        ])
        
        features_in_tile = GeoFeature.objects.filter(
            layer=layer,
            geometry__intersects=bbox_polygon,
            is_valid=True
        )
        feature_count = features_in_tile.count()
        
        print(f"   📊 Features in problematic tile: {feature_count}")
        
        if feature_count > 0:
            print(f"   ✅ PROBLEMATIC TILE HAS DATA!")
            
            # Test MVT generation for this specific tile
            try:
                mvt_data = tile_service.generate_tile(layer, problematic_tile.z, problematic_tile.x, problematic_tile.y)
                if mvt_data:
                    import mapbox_vector_tile
                    decoded = mapbox_vector_tile.decode(mvt_data)
                    
                    if 'amaravati_master_plan' in decoded:
                        layer_data = decoded['amaravati_master_plan']
                        mvt_features = len(layer_data['features'])
                        print(f"   ✅ MVT generated successfully: {mvt_features} features")
                        print(f"   🎯 PROBLEMATIC TILE IS NOW WORKING!")
                    else:
                        print(f"   ❌ MVT generated but no layer data")
                else:
                    print(f"   ❌ Failed to generate MVT for problematic tile")
            except Exception as e:
                print(f"   ❌ Error generating MVT: {e}")
        else:
            print(f"   ❌ PROBLEMATIC TILE STILL HAS NO DATA!")
        
        print()
        print("=" * 60)
        print("🧪 TEST COMPLETE")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

def test_data_integrity():
    """Test data integrity and color mapping"""
    
    print("🔍 DATA INTEGRITY TEST")
    print("=" * 40)
    
    try:
        city = City.objects.get(slug='amaravati')
        layer = DataLayer.objects.get(slug='amaravati_master_plan')
        
        # Check feature properties
        features = GeoFeature.objects.filter(layer=layer, is_valid=True)[:10]
        
        print(f"📊 Sample features properties:")
        for i, feature in enumerate(features):
            print(f"   Feature {i+1}:")
            print(f"      Plot Category: {getattr(feature, 'plot_category', 'N/A')}")
            print(f"      Symbology: {getattr(feature, 'symbology', 'N/A')}")
            print(f"      Geometry Type: {feature.geometry.geom_type}")
            print(f"      Coordinates: {len(feature.geometry.coords) if hasattr(feature.geometry, 'coords') else 'N/A'}")
            print()
        
        # Check color mapping
        print("🎨 Color mapping test:")
        unique_categories = GeoFeature.objects.filter(
            layer=layer, 
            is_valid=True
        ).values_list('plot_category', flat=True).distinct()
        
        print(f"   Unique plot categories: {list(unique_categories)}")
        
        # Test color generation for each category
        from maps.config import get_city_style_config
        style_config = get_city_style_config(city)
        
        print(f"   Style config available: {style_config is not None}")
        if style_config:
            print(f"   Color schemes: {list(style_config.keys())}")
        
    except Exception as e:
        print(f"❌ Data integrity test failed: {e}")

if __name__ == "__main__":
    test_tile_completeness()
    print()
    test_data_integrity()
