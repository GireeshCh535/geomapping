# management/commands/generate_city_tiles.py - Generate vector tiles for city layers

from django.core.management.base import BaseCommand
from django.utils import timezone
from maps.models import City, DataLayer, VectorTileLayer
from maps.services import VectorTileService
import time

class Command(BaseCommand):
    help = 'Generate vector tiles for all layers in a city'
    
    def add_arguments(self, parser):
        parser.add_argument('--city', required=True, help='City slug')
        parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=14, help='Maximum zoom level')
        parser.add_argument('--layer', help='Specific layer slug (optional)')
        parser.add_argument('--force', action='store_true', help='Force regeneration of existing tiles')
        parser.add_argument('--parallel', action='store_true', help='Generate tiles in parallel (if supported)')
    
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
                if vector_tile_layer:
                    vector_tile_layer.min_zoom = min_zoom
                    vector_tile_layer.max_zoom = max_zoom
                    vector_tile_layer.is_generated = True
                    vector_tile_layer.total_tiles = result.get('tiles_generated', 0)
                    vector_tile_layer.generated_at = timezone.now()
                    vector_tile_layer.save()
                else:
                    VectorTileLayer.objects.create(
                        layer=layer,
                        min_zoom=min_zoom,
                        max_zoom=max_zoom,
                        is_generated=True,
                        total_tiles=result.get('tiles_generated', 0),
                        generated_at=timezone.now()
                    )
                
                # Update layer status
                layer.tiles_generated = True
                layer.save()
                
                tiles_count = result.get('tiles_generated', 0)
                total_tiles_generated += tiles_count
                successful_layers += 1
                
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
        
        # Show next steps
        if successful_layers > 0:
            self.stdout.write(f"\n🎯 Next Steps:")
            self.stdout.write(f"   1. Test tiles: GET /api/tiles/{city_slug}/{{layer}}/{{z}}/{{x}}/{{y}}.mvt")
            self.stdout.write(f"   2. View layers: GET /api/cities/{city_slug}/layers/")
            self.stdout.write(f"   3. Validate tiles: python manage.py validate_tiles --city={city_slug}")
        
        if failed_layers > 0:
            self.stdout.write(f"\n⚠️  {failed_layers} layers failed to generate tiles")
            self.stdout.write("   Check layer data and try regenerating individual layers")
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Tile generation completed!"))