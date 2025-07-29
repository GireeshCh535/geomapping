# management/commands/generate_combined_png_tiles_with_metrics.py
from django.core.management.base import BaseCommand
from maps.models import City, DataLayer
from maps.services import VectorTileService
from maps.tile_rendering_service import TileRenderingService
import mercantile
import os
import time
import psutil
import gc
from datetime import datetime
import json

class Command(BaseCommand):
    help = 'Pre-generate and save combined PNG tiles with detailed performance metrics'

    def add_arguments(self, parser):
        parser.add_argument('--city', required=True, help='City slug')
        parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=14, help='Maximum zoom level')
        parser.add_argument('--overwrite', action='store_true', help='Overwrite existing PNGs')
        parser.add_argument('--metrics', action='store_true', help='Enable detailed performance metrics')
        parser.add_argument('--metrics-interval', type=int, default=100, help='Report metrics every N tiles')
        parser.add_argument('--save-metrics', type=str, help='Save metrics to JSON file')

    def handle(self, *args, **options):
        city_slug = options['city']
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        overwrite = options['overwrite']
        enable_metrics = options['metrics']
        metrics_interval = options['metrics_interval']
        save_metrics_path = options.get('save_metrics')

        # Initialize metrics tracking
        metrics = {
            'start_time': datetime.now().isoformat(),
            'city': city_slug,
            'zoom_range': {'min': min_zoom, 'max': max_zoom},
            'system': {
                'cpu_count': psutil.cpu_count(),
                'memory_total_gb': round(psutil.virtual_memory().total / (1024**3), 2)
            },
            'performance': {
                'total_tiles': 0,
                'generated_tiles': 0,
                'skipped_tiles': 0,
                'failed_tiles': 0,
                'zoom_levels': {}
            },
            'timings': {
                'mvt_generation_ms': [],
                'png_rendering_ms': [],
                'file_write_ms': [],
                'total_tile_ms': []
            }
        }

        start_time = time.time()
        process = psutil.Process()

        try:
            city = City.objects.get(slug=city_slug)
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            return

        layers = DataLayer.objects.filter(city=city, is_processed=True)
        if not layers.exists():
            self.stdout.write(self.style.ERROR(f"❌ No processed layers found for city: {city_slug}"))
            return

        self.stdout.write(self.style.SUCCESS(f"🚀 Starting PNG tile generation for {city_slug}"))
        self.stdout.write(f"📊 Found {layers.count()} layers to process")
        
        if enable_metrics:
            self.stdout.write(self.style.WARNING("📈 Performance metrics enabled"))

        tile_service = VectorTileService()
        render_service = TileRenderingService()

        # Get bounds from all layers
        bounds = None
        for layer in layers:
            b = tile_service._get_layer_bounds(layer)
            if b:
                if not bounds:
                    bounds = b.copy()
                else:
                    bounds['west'] = min(bounds['west'], b['west'])
                    bounds['south'] = min(bounds['south'], b['south'])
                    bounds['east'] = max(bounds['east'], b['east'])
                    bounds['north'] = max(bounds['north'], b['north'])
        
        if not bounds:
            self.stdout.write(self.style.ERROR(f"❌ Could not determine bounds for city: {city_slug}"))
            return

        out_dir = os.path.join('static', 'tiles_png', city_slug, 'combined')
        os.makedirs(out_dir, exist_ok=True)

        total_tiles = 0
        generated_tiles = 0
        skipped_tiles = 0
        failed_tiles = 0

        for zoom in range(min_zoom, max_zoom + 1):
            zoom_start = time.time()
            zoom_metrics = {
                'tiles_count': 0,
                'generated': 0,
                'skipped': 0,
                'failed': 0,
                'duration_seconds': 0
            }

            tiles = list(mercantile.tiles(bounds['west'], bounds['south'], bounds['east'], bounds['north'], zoom))
            zoom_metrics['tiles_count'] = len(tiles)
            
            self.stdout.write(f"\n🔍 Zoom {zoom}: {len(tiles)} tiles")
            
            for tile_idx, tile in enumerate(tiles):
                tile_start = time.time()
                png_path = os.path.join(out_dir, f"{tile.z}_{tile.x}_{tile.y}.png")
                total_tiles += 1
                
                # Memory monitoring
                if enable_metrics and tile_idx % metrics_interval == 0:
                    memory_info = process.memory_info()
                    cpu_percent = process.cpu_percent(interval=0.1)
                    self.stdout.write(
                        f"   📊 Progress: {tile_idx}/{len(tiles)} | "
                        f"Memory: {memory_info.rss / (1024**2):.1f}MB | "
                        f"CPU: {cpu_percent:.1f}%"
                    )

                if os.path.exists(png_path) and not overwrite:
                    skipped_tiles += 1
                    zoom_metrics['skipped'] += 1
                    continue

                try:
                    # Time MVT generation
                    mvt_start = time.time()
                    mvt_data = tile_service.generate_combined_tile(layers, tile.z, tile.x, tile.y)
                    mvt_time = (time.time() - mvt_start) * 1000  # Convert to ms
                    
                    # Time PNG rendering
                    png_start = time.time()
                    if not mvt_data:
                        png_data = render_service.create_empty_tile()
                    else:
                        png_data = render_service.combined_mvt_to_png(mvt_data, layers, tile.z, tile.x, tile.y)
                    png_time = (time.time() - png_start) * 1000
                    
                    # Time file write
                    write_start = time.time()
                    with open(png_path, 'wb') as f:
                        f.write(png_data)
                    write_time = (time.time() - write_start) * 1000
                    
                    generated_tiles += 1
                    zoom_metrics['generated'] += 1
                    
                    # Record timings
                    if enable_metrics:
                        total_tile_time = (time.time() - tile_start) * 1000
                        metrics['timings']['mvt_generation_ms'].append(mvt_time)
                        metrics['timings']['png_rendering_ms'].append(png_time)
                        metrics['timings']['file_write_ms'].append(write_time)
                        metrics['timings']['total_tile_ms'].append(total_tile_time)
                        
                        if generated_tiles % metrics_interval == 0:
                            avg_tile_time = sum(metrics['timings']['total_tile_ms'][-metrics_interval:]) / metrics_interval
                            tiles_per_second = 1000 / avg_tile_time if avg_tile_time > 0 else 0
                            self.stdout.write(
                                f"   ⚡ Performance: {tiles_per_second:.1f} tiles/sec | "
                                f"Avg tile time: {avg_tile_time:.1f}ms"
                            )
                    
                except Exception as e:
                    failed_tiles += 1
                    zoom_metrics['failed'] += 1
                    if enable_metrics:
                        self.stdout.write(self.style.ERROR(f"   ❌ Failed tile {tile.z}/{tile.x}/{tile.y}: {str(e)}"))

            zoom_duration = time.time() - zoom_start
            zoom_metrics['duration_seconds'] = round(zoom_duration, 2)
            metrics['performance']['zoom_levels'][f'zoom_{zoom}'] = zoom_metrics
            
            self.stdout.write(
                f"   ✅ Zoom {zoom} complete: "
                f"{zoom_metrics['generated']} generated, "
                f"{zoom_metrics['skipped']} skipped, "
                f"{zoom_metrics['failed']} failed "
                f"in {zoom_duration:.1f}s"
            )

        # Final metrics calculation
        total_duration = time.time() - start_time
        
        metrics['performance']['total_tiles'] = total_tiles
        metrics['performance']['generated_tiles'] = generated_tiles
        metrics['performance']['skipped_tiles'] = skipped_tiles
        metrics['performance']['failed_tiles'] = failed_tiles
        metrics['end_time'] = datetime.now().isoformat()
        metrics['total_duration_seconds'] = round(total_duration, 2)
        
        if enable_metrics and metrics['timings']['total_tile_ms']:
            metrics['performance']['average_timings'] = {
                'mvt_generation_ms': round(sum(metrics['timings']['mvt_generation_ms']) / len(metrics['timings']['mvt_generation_ms']), 2),
                'png_rendering_ms': round(sum(metrics['timings']['png_rendering_ms']) / len(metrics['timings']['png_rendering_ms']), 2),
                'file_write_ms': round(sum(metrics['timings']['file_write_ms']) / len(metrics['timings']['file_write_ms']), 2),
                'total_tile_ms': round(sum(metrics['timings']['total_tile_ms']) / len(metrics['timings']['total_tile_ms']), 2),
                'tiles_per_second': round(generated_tiles / total_duration, 2) if total_duration > 0 else 0
            }
            # Remove raw timing arrays for cleaner output
            del metrics['timings']

        # Display final summary
        self.stdout.write(self.style.SUCCESS(f"\n✅ PNG tile generation complete!"))
        self.stdout.write(f"📊 Final Summary:")
        self.stdout.write(f"   Total tiles: {total_tiles:,}")
        self.stdout.write(f"   Generated: {generated_tiles:,}")
        self.stdout.write(f"   Skipped: {skipped_tiles:,}")
        self.stdout.write(f"   Failed: {failed_tiles:,}")
        self.stdout.write(f"   Total time: {total_duration:.1f}s")
        self.stdout.write(f"   Average speed: {generated_tiles/total_duration:.1f} tiles/second")
        self.stdout.write(f"   Output folder: {out_dir}")

        if enable_metrics and 'average_timings' in metrics['performance']:
            self.stdout.write(f"\n⚡ Performance Breakdown:")
            self.stdout.write(f"   MVT Generation: {metrics['performance']['average_timings']['mvt_generation_ms']:.1f}ms avg")
            self.stdout.write(f"   PNG Rendering: {metrics['performance']['average_timings']['png_rendering_ms']:.1f}ms avg")
            self.stdout.write(f"   File Writing: {metrics['performance']['average_timings']['file_write_ms']:.1f}ms avg")
            self.stdout.write(f"   Total per tile: {metrics['performance']['average_timings']['total_tile_ms']:.1f}ms avg")

        # Save metrics to file if requested
        if save_metrics_path:
            with open(save_metrics_path, 'w') as f:
                json.dump(metrics, f, indent=2)
            self.stdout.write(self.style.SUCCESS(f"\n📈 Metrics saved to: {save_metrics_path}"))

        # Force garbage collection
        gc.collect()