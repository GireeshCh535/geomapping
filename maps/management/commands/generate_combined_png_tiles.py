from django.core.management.base import BaseCommand
from maps.models import City, DataLayer
from maps.services import VectorTileService
from maps.tile_rendering_service import TileRenderingService
import mercantile
import os

class Command(BaseCommand):
    help = 'Pre-generate and save combined PNG tiles for a city (all layers) for a given zoom range.'

    def add_arguments(self, parser):
        parser.add_argument('--city', required=True, help='City slug')
        parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=14, help='Maximum zoom level')
        parser.add_argument('--overwrite', action='store_true', help='Overwrite existing PNGs')

    def handle(self, *args, **options):
        city_slug = options['city']
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        overwrite = options['overwrite']

        try:
            city = City.objects.get(slug=city_slug)
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            return

        layers = DataLayer.objects.filter(city=city, is_processed=True)
        if not layers.exists():
            self.stdout.write(self.style.ERROR(f"❌ No processed layers found for city: {city_slug}"))
            return

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

        for zoom in range(min_zoom, max_zoom + 1):
            tiles = list(mercantile.tiles(bounds['west'], bounds['south'], bounds['east'], bounds['north'], zoom))
            self.stdout.write(f"Zoom {zoom}: {len(tiles)} tiles")
            for tile in tiles:
                png_path = os.path.join(out_dir, f"{tile.z}_{tile.x}_{tile.y}.png")
                total_tiles += 1
                if os.path.exists(png_path) and not overwrite:
                    skipped_tiles += 1
                    continue
                mvt_data = tile_service.generate_combined_tile(layers, tile.z, tile.x, tile.y)
                if not mvt_data:
                    # Save a transparent/empty PNG
                    png_data = render_service.create_empty_tile()
                else:
                    png_data = render_service.combined_mvt_to_png(mvt_data, layers, tile.z, tile.x, tile.y)
                with open(png_path, 'wb') as f:
                    f.write(png_data)
                generated_tiles += 1
                if generated_tiles % 100 == 0:
                    self.stdout.write(f"   Generated {generated_tiles} PNGs so far...")
        self.stdout.write(self.style.SUCCESS(f"\n✅ PNG tile generation complete!"))
        self.stdout.write(f"   Total tiles: {total_tiles}")
        self.stdout.write(f"   Generated: {generated_tiles}")
        self.stdout.write(f"   Skipped (already existed): {skipped_tiles}")
        self.stdout.write(f"   Output folder: {out_dir}") 