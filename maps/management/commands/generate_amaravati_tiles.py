from django.core.management.base import BaseCommand
from maps.models import City, DataLayer
from maps.services import VectorTileService

class Command(BaseCommand):
    help = 'Generate tiles specifically for Amaravati coordinates to fix low zoom level issue'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-zoom',
            type=int,
            default=8,
            help='Minimum zoom level (default: 8)'
        )
        parser.add_argument(
            '--max-zoom',
            type=int,
            default=18,
            help='Maximum zoom level (default: 18)'
        )
        parser.add_argument(
            '--radius',
            type=float,
            default=0.01,
            help='Radius in degrees around coordinates (default: 0.01)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )

    def handle(self, *args, **options):
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        radius = options['radius']
        verbose = options['verbose']

        # Amaravati coordinates that were having issues
        target_lng, target_lat = 80.45215550279937, 16.518144085425448

        self.stdout.write(f"🗺️  Generating tiles for Amaravati coordinates: [{target_lng}, {target_lat}]")
        self.stdout.write(f"📊 Zoom levels: {min_zoom} to {max_zoom}")
        self.stdout.write(f"📍 Radius: {radius}°")
        self.stdout.write("=" * 80)

        try:
            # Get Amaravati city
            city = City.objects.get(slug='amaravati', is_active=True)
            self.stdout.write(f"✅ Found city: {city.name}")

            # Get all layers for Amaravati
            layers = DataLayer.objects.filter(
                city=city,
                is_processed=True
            ).select_related('category')

            if not layers.exists():
                self.stdout.write(self.style.ERROR("❌ No processed layers found for Amaravati"))
                return

            self.stdout.write(f"📋 Found {layers.count()} processed layers")

            # Initialize tile service
            tile_service = VectorTileService()

            total_tiles_generated = 0
            successful_layers = 0

            # Process each layer
            for layer in layers:
                self.stdout.write(f"\n📂 Processing layer: {layer.name} ({layer.slug})")

                # Check if layer has features
                feature_count = layer.geofeature_set.filter(is_valid=True).count()
                if feature_count == 0:
                    self.stdout.write(f"   ⚠️  Skipping layer with 0 features")
                    continue

                self.stdout.write(f"   📊 Features: {feature_count}")

                # Generate tiles for the specific coordinates
                result = tile_service.generate_tiles_for_coordinates(
                    layer, target_lng, target_lat, radius, min_zoom, max_zoom
                )

                if result['status'] == 'success':
                    tiles_generated = result['tiles_generated']
                    total_tiles_generated += tiles_generated
                    successful_layers += 1
                    self.stdout.write(f"   ✅ Generated {tiles_generated} tiles")
                else:
                    self.stdout.write(f"   ❌ Failed to generate tiles: {result.get('error', 'Unknown error')}")

            # Summary
            self.stdout.write(f"\n" + "=" * 80)
            self.stdout.write(self.style.SUCCESS("📈 GENERATION COMPLETE"))
            self.stdout.write("=" * 80)
            self.stdout.write(f"✅ Successful layers: {successful_layers}/{layers.count()}")
            self.stdout.write(f"✅ Total tiles generated: {total_tiles_generated}")
            self.stdout.write(f"📍 Target coordinates: [{target_lng}, {target_lat}]")
            self.stdout.write(f"🎯 This should fix the low zoom level visibility issue!")

        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR("❌ City 'amaravati' not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {e}"))
            if verbose:
                import traceback
                traceback.print_exc()
