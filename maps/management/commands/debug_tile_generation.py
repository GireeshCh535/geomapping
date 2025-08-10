# maps/management/commands/debug_tile_generation.py
"""
Debug tile generation to identify why tiles are white
Command: python manage.py debug_tile_generation --city bengaluru --layer-group master_plan --zoom 10 --test-tile
"""

from django.core.management.base import BaseCommand
from django.contrib.gis.db.models import Extent
from maps.models import City, DataLayer, LayerGroup, GeoFeature
from maps.services import VectorTileService
from maps.tile_rendering_service import TileRenderingService
import mercantile
import mapbox_vector_tile
import tempfile
import os
from pathlib import Path

class Command(BaseCommand):
    help = 'Debug tile generation to identify white tile issues'
    
    def add_arguments(self, parser):
        parser.add_argument('--city', required=True, help='City slug (e.g., bengaluru)')
        parser.add_argument('--layer-group', required=True, help='Layer group to test (e.g., master_plan)')
        parser.add_argument('--zoom', type=int, default=10, help='Zoom level to test')
        parser.add_argument('--test-tile', action='store_true', help='Generate a test tile')
        parser.add_argument('--save-local', action='store_true', help='Save test files locally')
    
    def handle(self, *args, **options):
        city_slug = options['city']
        layer_group_slug = options['layer_group']
        zoom = options['zoom']
        
        self.stdout.write(self.style.SUCCESS(f"🔍 DEBUGGING TILE GENERATION"))
        self.stdout.write(f"City: {city_slug} | Layer Group: {layer_group_slug} | Zoom: {zoom}")
        
        try:
            # Get city and layer group
            city = City.objects.get(slug=city_slug)
            layer_group = LayerGroup.objects.get(city=city, slug=layer_group_slug)
            
            self.stdout.write(f"\n🏙️  City: {city.name}")
            self.stdout.write(f"📁 Layer Group: {layer_group.name}")
            
            # Get layers in this group
            layers = DataLayer.objects.filter(layer_group=layer_group)
            self.stdout.write(f"📋 Layers in group: {layers.count()}")
            
            # Check layer data
            total_features = 0
            layers_with_data = 0
            
            for layer in layers:
                feature_count = layer.feature_count or 0
                total_features += feature_count
                if feature_count > 0:
                    layers_with_data += 1
                    
                self.stdout.write(f"   📄 {layer.name}: {feature_count:,} features")
            
            self.stdout.write(f"\n📊 Data Summary:")
            self.stdout.write(f"   Layers with data: {layers_with_data}/{layers.count()}")
            self.stdout.write(f"   Total features: {total_features:,}")
            
            if total_features == 0:
                self.stdout.write("❌ No features found - this explains white tiles!")
                return
            
            # Calculate bounds for the layer group
            bounds = self._calculate_group_bounds(layers)
            if not bounds:
                self.stdout.write("❌ Could not calculate bounds")
                return
                
            self.stdout.write(f"\n🗺️  Group Bounds:")
            self.stdout.write(f"   West: {bounds['west']:.6f}")
            self.stdout.write(f"   South: {bounds['south']:.6f}")  
            self.stdout.write(f"   East: {bounds['east']:.6f}")
            self.stdout.write(f"   North: {bounds['north']:.6f}")
            
            # Find a tile that should contain data
            center_lng = (bounds['west'] + bounds['east']) / 2
            center_lat = (bounds['south'] + bounds['north']) / 2
            
            # Get tile coordinates for center point
            tile = mercantile.tile(center_lng, center_lat, zoom)
            
            self.stdout.write(f"\n🎯 Test Tile Coordinates:")
            self.stdout.write(f"   Zoom: {tile.z}")
            self.stdout.write(f"   X: {tile.x}")
            self.stdout.write(f"   Y: {tile.y}")
            self.stdout.write(f"   Center: ({center_lng:.6f}, {center_lat:.6f})")
            
            if options['test_tile']:
                self._test_tile_generation(city, layer_group, layers, tile.z, tile.x, tile.y, options)
                
        except City.DoesNotExist:
            self.stdout.write(f"❌ City not found: {city_slug}")
        except LayerGroup.DoesNotExist:
            self.stdout.write(f"❌ Layer group not found: {layer_group_slug}")
            available_groups = LayerGroup.objects.filter(city__slug=city_slug).values_list('slug', 'name')
            self.stdout.write("   Available layer groups:")
            for slug, name in available_groups:
                self.stdout.write(f"   - {slug} ({name})")
        except Exception as e:
            self.stdout.write(f"❌ Debug failed: {e}")
            import traceback
            self.stdout.write(traceback.format_exc())
    
    def _calculate_group_bounds(self, layers):
        """Calculate bounding box for all layers in the group"""
        try:
            # Get extent from all features in all layers
            all_features = GeoFeature.objects.filter(layer__in=layers)
            
            if not all_features.exists():
                return None
                
            extent = all_features.aggregate(extent=Extent('geometry'))['extent']
            
            if extent:
                return {
                    'west': extent[0],
                    'south': extent[1], 
                    'east': extent[2],
                    'north': extent[3]
                }
            
            return None
            
        except Exception as e:
            self.stdout.write(f"❌ Error calculating bounds: {e}")
            return None
    
    def _test_tile_generation(self, city, layer_group, layers, z, x, y, options):
        """Test generating a single tile with detailed debugging"""
        
        self.stdout.write(f"\n🧪 TESTING TILE GENERATION:")
        self.stdout.write(f"   Tile: {z}/{x}/{y}")
        
        try:
            # Initialize services
            vector_service = VectorTileService()
            render_service = TileRenderingService()
            
            # Step 1: Generate MVT data
            self.stdout.write(f"\n📦 Step 1: Generating MVT data...")
            
            mvt_data = vector_service.generate_combined_mvt_for_layers(layers, z, x, y)
            
            if mvt_data and len(mvt_data) > 0:
                self.stdout.write(f"   ✅ MVT generated: {len(mvt_data)} bytes")
                
                # Decode and inspect MVT
                decoded = mapbox_vector_tile.decode(mvt_data)
                total_mvt_features = 0
                
                self.stdout.write(f"   📊 MVT layers: {list(decoded.keys())}")
                
                for layer_name, layer_data in decoded.items():
                    features = layer_data.get('features', [])
                    total_mvt_features += len(features)
                    self.stdout.write(f"      {layer_name}: {len(features)} features")
                
                self.stdout.write(f"   📈 Total MVT features: {total_mvt_features}")
                
                if total_mvt_features == 0:
                    self.stdout.write("   ❌ MVT has no features - this explains white tiles!")
                    self.stdout.write("   💡 Try a different zoom level or check feature bounds")
                    return
                    
            else:
                self.stdout.write(f"   ❌ MVT generation failed - no data")
                return
            
            # Step 2: Test PNG rendering
            self.stdout.write(f"\n🎨 Step 2: Testing PNG rendering...")
            
            png_data = render_service.combined_mvt_to_png(mvt_data, layers, z, x, y)
            
            if png_data and len(png_data) > 0:
                self.stdout.write(f"   ✅ PNG generated: {len(png_data)} bytes")
                
                # Save test files if requested
                if options['save_local']:
                    self._save_test_files(mvt_data, png_data, z, x, y, layer_group.slug)
                    
            else:
                self.stdout.write(f"   ❌ PNG generation failed")
                return
            
            # Step 3: Check colors and styling
            self.stdout.write(f"\n🎨 Step 3: Checking colors and styling...")
            
            for layer in layers:
                color = render_service._get_layer_color_simple(layer)
                self.stdout.write(f"   🎨 {layer.name}: {color}")
            
            self.stdout.write(f"\n✅ TILE GENERATION TEST COMPLETED!")
            self.stdout.write(f"   MVT Size: {len(mvt_data)} bytes")
            self.stdout.write(f"   PNG Size: {len(png_data)} bytes") 
            self.stdout.write(f"   Features: {total_mvt_features}")
            
            if total_mvt_features > 0 and len(png_data) > 1000:  # PNG should be substantial if it has data
                self.stdout.write(f"✅ Tile generation is working properly!")
                self.stdout.write(f"💡 The issue might be:")
                self.stdout.write(f"   - Wrong zoom level (try zoom 8-12)")
                self.stdout.write(f"   - S3 upload issues")  
                self.stdout.write(f"   - CloudFront caching")
            else:
                self.stdout.write(f"❌ Issue identified:")
                if total_mvt_features == 0:
                    self.stdout.write(f"   - No features in this tile area")
                if len(png_data) <= 1000:
                    self.stdout.write(f"   - PNG rendering failed (too small)")
                    
        except Exception as e:
            self.stdout.write(f"❌ Test failed: {e}")
            import traceback
            self.stdout.write(traceback.format_exc())
    
    def _save_test_files(self, mvt_data, png_data, z, x, y, group_slug):
        """Save test files locally for inspection"""
        
        try:
            # Create test directory
            test_dir = Path('test_tiles')
            test_dir.mkdir(exist_ok=True)
            
            # Save MVT file
            mvt_path = test_dir / f"{group_slug}_{z}_{x}_{y}.mvt"
            with open(mvt_path, 'wb') as f:
                f.write(mvt_data)
            
            # Save PNG file  
            png_path = test_dir / f"{group_slug}_{z}_{x}_{y}.png"
            with open(png_path, 'wb') as f:
                f.write(png_data)
                
            self.stdout.write(f"💾 Test files saved:")
            self.stdout.write(f"   MVT: {mvt_path}")
            self.stdout.write(f"   PNG: {png_path}")
            
        except Exception as e:
            self.stdout.write(f"❌ Error saving test files: {e}")