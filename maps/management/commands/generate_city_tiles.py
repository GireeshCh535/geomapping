# management/commands/generate_city_tiles.py - Generate vector tiles for city layers

from django.core.management.base import BaseCommand
from django.utils import timezone
from maps.models import City, DataLayer, VectorTileLayer
from maps.services import VectorTileService
import time
import mercantile

class Command(BaseCommand):
    help = 'Generate vector tiles for all layers in a city'
    
    def add_arguments(self, parser):
        parser.add_argument('--city', required=True, help='City slug')
        parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=14, help='Maximum zoom level')
        parser.add_argument('--layer', help='Specific layer slug (optional)')
        parser.add_argument('--force', action='store_true', help='Force regeneration of existing tiles')
        parser.add_argument('--parallel', action='store_true', help='Generate tiles in parallel (if supported)')
        parser.add_argument('--validate', action='store_true', help='Validate generated tiles after creation')
        parser.add_argument('--sample-urls', action='store_true', help='Generate sample URLs for testing')
    
    def handle(self, *args, **options):
        city_slug = options['city']
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        layer_slug = options.get('layer')
        
        try:
            city = City.objects.get(slug=city_slug)
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            return
        
        # Validate zoom levels
        if min_zoom < 0 or max_zoom > 18 or min_zoom > max_zoom:
            self.stdout.write(self.style.ERROR(f"❌ Invalid zoom levels: {min_zoom}-{max_zoom}"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"🗺️  Generating tiles for {city.name}"))
        self.stdout.write(f"📊 Zoom levels: {min_zoom} to {max_zoom}")
        
        # Get layers to process
        layers = DataLayer.objects.filter(city=city, is_processed=True)
        if layer_slug:
            layers = layers.filter(slug=layer_slug)
            if not layers.exists():
                self.stdout.write(self.style.ERROR(f"❌ Layer not found: {layer_slug}"))
                return
        
        if not layers.exists():
            self.stdout.write(self.style.WARNING("⚠️  No processed layers found"))
            return
        
        self.stdout.write(f"📋 Processing {layers.count()} layers...")
        
        # Initialize tile service
        tile_service = VectorTileService()
        
        # Process each layer
        total_tiles_generated = 0
        successful_layers = 0
        failed_layers = 0
        layer_results = []
        
        start_time = time.time()
        
        for i, layer in enumerate(layers, 1):
            self.stdout.write(f"\n📂 [{i}/{layers.count()}] Processing: {layer.name}")
            self.stdout.write(f"   📊 Features: {layer.feature_count:,}")
            
            # Check if tiles already exist
            try:
                vector_tile_layer = VectorTileLayer.objects.get(layer=layer)
                if vector_tile_layer.is_generated and not options['force']:
                    self.stdout.write(f"   ✅ Tiles already exist (use --force to regenerate)")
                    successful_layers += 1
                    layer_results.append({
                        'layer': layer.slug,
                        'name': layer.name,
                        'tiles_generated': vector_tile_layer.total_tiles,
                        'status': 'existing'
                    })
                    continue
            except VectorTileLayer.DoesNotExist:
                vector_tile_layer = None
            
            try:
                layer_start_time = time.time()
                
                # Generate tiles for this layer
                result = tile_service.generate_layer_tiles(layer, min_zoom, max_zoom)
                
                layer_end_time = time.time()
                layer_duration = layer_end_time - layer_start_time
                
                # Update or create vector tile layer record
                tiles_count = result.get('tiles_generated', 0)
                if vector_tile_layer:
                    vector_tile_layer.min_zoom = min_zoom
                    vector_tile_layer.max_zoom = max_zoom
                    vector_tile_layer.is_generated = True
                    vector_tile_layer.total_tiles = tiles_count
                    vector_tile_layer.generated_at = timezone.now()
                    vector_tile_layer.save()
                else:
                    VectorTileLayer.objects.create(
                        layer=layer,
                        min_zoom=min_zoom,
                        max_zoom=max_zoom,
                        is_generated=True,
                        total_tiles=tiles_count,
                        generated_at=timezone.now()
                    )
                
                # Update layer status
                layer.tiles_generated = True
                layer.save()
                
                total_tiles_generated += tiles_count
                successful_layers += 1
                
                layer_results.append({
                    'layer': layer.slug,
                    'name': layer.name,
                    'tiles_generated': tiles_count,
                    'duration': layer_duration,
                    'status': 'generated'
                })
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"   ✅ Generated {tiles_count:,} tiles in {layer_duration:.1f}s"
                    )
                )
                
                # Show progress
                if tiles_count > 0:
                    tiles_per_second = tiles_count / layer_duration if layer_duration > 0 else 0
                    self.stdout.write(f"   ⚡ Performance: {tiles_per_second:.1f} tiles/second")
                
            except Exception as e:
                failed_layers += 1
                self.stdout.write(
                    self.style.ERROR(f"   ❌ Failed: {str(e)}")
                )
                
                layer_results.append({
                    'layer': layer.slug,
                    'name': layer.name,
                    'tiles_generated': 0,
                    'status': 'failed',
                    'error': str(e)
                })
                
                # Log detailed error for debugging
                import traceback
                self.stdout.write(f"   🔍 Error details: {traceback.format_exc()}")
        
        # Final summary
        end_time = time.time()
        total_duration = end_time - start_time
        
        self.stdout.write(f"\n📊 Generation Summary:")
        self.stdout.write(f"   ✅ Successful layers: {successful_layers}")
        self.stdout.write(f"   ❌ Failed layers: {failed_layers}")
        self.stdout.write(f"   🗺️  Total tiles generated: {total_tiles_generated:,}")
        self.stdout.write(f"   ⏱️  Total time: {total_duration:.1f}s")
        
        if total_tiles_generated > 0:
            avg_tiles_per_second = total_tiles_generated / total_duration
            self.stdout.write(f"   ⚡ Average performance: {avg_tiles_per_second:.1f} tiles/second")
        
        # Generate sample URLs for testing
        if options['sample_urls'] or successful_layers > 0:
            self.stdout.write(f"\n🎯 Sample URLs for Testing:")
            self._generate_sample_urls(city_slug, layer_results, min_zoom, max_zoom)
        
        # Validate tiles if requested
        if options['validate'] and successful_layers > 0:
            self.stdout.write(f"\n🔍 Validating generated tiles...")
            self._validate_generated_tiles(city_slug, layer_results)
        
        # Show next steps
        if successful_layers > 0:
            self.stdout.write(f"\n🎯 Next Steps:")
            self.stdout.write(f"   1. Test individual layer tiles: GET /api/tiles/{city_slug}/{{layer}}/{{z}}/{{x}}/{{y}}.mvt")
            self.stdout.write(f"   2. Test combined tiles: GET /api/tiles/{city_slug}/combined/{{z}}/{{x}}/{{y}}.mvt")
            self.stdout.write(f"   3. View layers: GET /api/cities/{city_slug}/layers/")
            self.stdout.write(f"   4. Get complete city data: GET /api/cities/{city_slug}/complete/")
        
        if failed_layers > 0:
            self.stdout.write(f"\n⚠️  {failed_layers} layers failed to generate tiles")
            self.stdout.write("   Check layer data and try regenerating individual layers")
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Tile generation completed!"))
    
    def _generate_sample_urls(self, city_slug, layer_results, min_zoom, max_zoom):
        """Generate sample URLs for testing the generated tiles"""
        
        # Get city bounds for sample coordinates
        try:
            city = City.objects.get(slug=city_slug)
            if city.center_lat and city.center_lng:
                # Use city center for sample coordinates
                center_lat, center_lng = city.center_lat, city.center_lng
            else:
                # Fallback to approximate Bangalore coordinates
                center_lat, center_lng = 12.9716, 77.5946
        except:
            center_lat, center_lng = 12.9716, 77.5946  # Bangalore fallback
        
        # Generate sample tile coordinates around the center
        sample_zooms = [min_zoom, (min_zoom + max_zoom) // 2, max_zoom]
        
        for zoom in sample_zooms:
            # Get tile coordinates for the center point
            tile = mercantile.tile(center_lng, center_lat, zoom)
            
            self.stdout.write(f"\n   📍 Zoom {zoom} (tile {tile.z}/{tile.x}/{tile.y}):")
            
            # Individual layer tiles
            for result in layer_results:
                if result['status'] in ['generated', 'existing'] and result['tiles_generated'] > 0:
                    layer_slug = result['layer']
                    self.stdout.write(f"      • {layer_slug}: /api/tiles/{city_slug}/{layer_slug}/{tile.z}/{tile.x}/{tile.y}.mvt")
            
            # Combined tile
            self.stdout.write(f"      • Combined: /api/tiles/{city_slug}/combined/{tile.z}/{tile.x}/{tile.y}.mvt")
            
            # PNG versions (if available)
            if zoom <= 14:  # PNG tiles typically limited to lower zooms
                self.stdout.write(f"      • PNG Combined: /api/tiles/{city_slug}/combined/{tile.z}/{tile.x}/{tile.y}.png")
        
        # Additional test URLs
        self.stdout.write(f"\n   🔗 Additional Test URLs:")
        self.stdout.write(f"      • City layers: GET /api/cities/{city_slug}/layers/")
        self.stdout.write(f"      • City complete: GET /api/cities/{city_slug}/complete/")
        self.stdout.write(f"      • Progressive loading: GET /api/cities/{city_slug}/progressive/")
        
        # Show a few more sample tiles at different locations
        additional_coords = [
            (12.9716, 77.5946, 12),  # Bangalore center
            (12.9716, 77.5946, 10),  # Lower zoom
            (12.9716, 77.5946, 14),  # Higher zoom
        ]
        
        self.stdout.write(f"\n   🧪 Sample Tile Coordinates for Testing:")
        for lat, lng, z in additional_coords:
            tile = mercantile.tile(lng, lat, z)
            self.stdout.write(f"      • {z}/{tile.x}/{tile.y} (lat: {lat:.4f}, lng: {lng:.4f})")
    
    def _validate_generated_tiles(self, city_slug, layer_results):
        """Validate generated tiles by testing a few sample tiles"""
        
        from django.test import Client
        from django.urls import reverse
        
        client = Client()
        validation_results = []
        
        # Test a few sample tiles for each layer
        for result in layer_results:
            if result['status'] in ['generated', 'existing'] and result['tiles_generated'] > 0:
                layer_slug = result['layer']
                
                # Test coordinates (zoom 12, near center)
                test_coords = [
                    (12, 3119, 3222),  # From your coordinates.js
                    (12, 3116, 3224),  # From your coordinates.js
                ]
                
                layer_validation = {
                    'layer': layer_slug,
                    'tests': []
                }
                
                for z, x, y in test_coords:
                    try:
                        # Test MVT tile
                        url = f'/api/tiles/{city_slug}/{layer_slug}/{z}/{x}/{y}.mvt'
                        response = client.get(url)
                        
                        test_result = {
                            'coordinates': f'{z}/{x}/{y}',
                            'status_code': response.status_code,
                            'content_length': len(response.content) if response.content else 0,
                            'content_type': response.get('Content-Type', ''),
                            'success': response.status_code == 200 and len(response.content) > 0
                        }
                        
                        layer_validation['tests'].append(test_result)
                        
                        if test_result['success']:
                            self.stdout.write(f"      ✅ {layer_slug} {z}/{x}/{y}: {len(response.content)} bytes")
                        else:
                            self.stdout.write(f"      ❌ {layer_slug} {z}/{x}/{y}: HTTP {response.status_code}")
                    
                    except Exception as e:
                        test_result = {
                            'coordinates': f'{z}/{x}/{y}',
                            'error': str(e),
                            'success': False
                        }
                        layer_validation['tests'].append(test_result)
                        self.stdout.write(f"      ❌ {layer_slug} {z}/{x}/{y}: {str(e)}")
                
                validation_results.append(layer_validation)
        
        # Summary
        total_tests = sum(len(result['tests']) for result in validation_results)
        successful_tests = sum(
            sum(1 for test in result['tests'] if test.get('success', False))
            for result in validation_results
        )
        
        self.stdout.write(f"\n   📊 Validation Summary:")
        self.stdout.write(f"      • Total tests: {total_tests}")
        self.stdout.write(f"      • Successful: {successful_tests}")
        self.stdout.write(f"      • Failed: {total_tests - successful_tests}")
        
        if successful_tests == total_tests:
            self.stdout.write(self.style.SUCCESS(f"      ✅ All tiles validated successfully!"))
        else:
            self.stdout.write(self.style.WARNING(f"      ⚠️  Some tiles failed validation"))