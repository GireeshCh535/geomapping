#!/usr/bin/env python3
"""
Django Management Command: Generate Combined Tiles
Generates combined MVT tiles for all layers of a city
"""

import os
import time
import mercantile
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from pathlib import Path
from maps.models import City, DataLayer, VectorTileLayer
from maps.services import VectorTileService


class Command(BaseCommand):
    help = 'Generate combined MVT tiles for all layers of a city'

    def add_arguments(self, parser):
        parser.add_argument(
            '--city',
            type=str,
            required=True,
            help='City slug (e.g., bangalore, vizag, amaravati)'
        )
        parser.add_argument(
            '--min-zoom',
            type=int,
            default=8,
            help='Minimum zoom level (default: 8)'
        )
        parser.add_argument(
            '--max-zoom',
            type=int,
            default=14,
            help='Maximum zoom level (default: 14)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force regeneration of existing tiles'
        )
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Validate generated tiles after creation'
        )

    def handle(self, *args, **options):
        city_slug = options['city']
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        force = options['force']
        validate = options['validate']

        # Validate zoom levels
        if min_zoom < 0 or max_zoom > 18 or min_zoom > max_zoom:
            raise CommandError(
                f'Invalid zoom levels: min_zoom={min_zoom}, max_zoom={max_zoom}. '
                'Must be between 0-18 and min_zoom <= max_zoom'
            )

        self.stdout.write(
            self.style.SUCCESS(f'🚀 Starting combined tile generation for {city_slug}')
        )
        self.stdout.write(f'📊 Zoom range: {min_zoom} to {max_zoom}')
        self.stdout.write(f'🔄 Force regenerate: {force}')
        self.stdout.write(f'✅ Validation: {validate}')
        self.stdout.write('=' * 60)

        try:
            # Get city and validate
            city = City.objects.get(slug=city_slug, is_active=True)
            self.stdout.write(f'✅ Found city: {city.name}')
        except City.DoesNotExist:
            raise CommandError(f'City not found: {city_slug}')

        # Get all processed layers
        layers = DataLayer.objects.filter(
            city=city,
            is_processed=True
        ).select_related('category')

        if not layers.exists():
            raise CommandError(f'No processed layers found for {city_slug}')

        self.stdout.write(f'📂 Found {layers.count()} processed layers:')
        total_features = 0
        for layer in layers:
            feature_count = layer.feature_count or 0
            total_features += feature_count
            self.stdout.write(f'   • {layer.name} ({feature_count:,} features)')

        self.stdout.write(f'📊 Total features across all layers: {total_features:,}')
        self.stdout.write('')

        # Create output directory
        output_dir = Path(settings.MEDIA_ROOT) / 'tiles' / city_slug / 'combined'
        output_dir.mkdir(parents=True, exist_ok=True)
        self.stdout.write(f'📁 Output directory: {output_dir}')

        # Initialize tile service
        tile_service = VectorTileService()

        # Calculate total tiles to generate
        bounds = self._get_city_bounds(layers)
        if not bounds:
            raise CommandError('Could not determine city bounds from layers')
        
        total_tiles = 0
        for zoom in range(min_zoom, max_zoom + 1):
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'],
                zoom
            ))
            total_tiles += len(tiles)
            self.stdout.write(f'   Zoom {zoom}: {len(tiles)} tiles')

        self.stdout.write(f'📊 Total tiles to generate: {total_tiles:,}')
        self.stdout.write('')

        # Generate tiles
        start_time = time.time()
        tiles_generated = 0
        tiles_skipped = 0
        tiles_failed = 0

        self.stdout.write('🔄 Starting tile generation...')
        
        for zoom in range(min_zoom, max_zoom + 1):
            # Get tiles for this zoom level
            bounds = self._get_city_bounds(layers)
            if not bounds:
                self.stdout.write(self.style.ERROR(f'❌ Could not determine bounds for city'))
                continue
                
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'],
                zoom
            ))
            
            self.stdout.write(f'🔄 Zoom {zoom}: Processing {len(tiles)} tiles...')
            zoom_start_time = time.time()
            zoom_generated = 0
            
            for tile in tiles:
                try:
                    # Create tile directory structure: z/x/y.mvt
                    tile_dir = output_dir / str(tile.z) / str(tile.x)
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Check if tile already exists
                    tile_path = tile_dir / f'{tile.y}.mvt'
                    
                    if tile_path.exists() and not force:
                        tiles_skipped += 1
                        continue

                    # Generate combined tile
                    mvt_data = tile_service.generate_combined_tile(layers, tile.z, tile.x, tile.y)

                    if mvt_data:
                        # Validate tile if requested
                        if validate:
                            is_valid, msg = self._validate_tile_simple(mvt_data)
                            if not is_valid:
                                self.stdout.write(
                                    self.style.WARNING(f'⚠️  Invalid tile {tile.z}/{tile.x}/{tile.y}: {msg}')
                                )
                                tiles_failed += 1
                                continue
                        
                        # Save tile to disk
                        with open(tile_path, 'wb') as f:
                            f.write(mvt_data)
                        tiles_generated += 1
                        zoom_generated += 1
                    else:
                        # Create empty tile file for consistency
                        with open(tile_path, 'wb') as f:
                            f.write(b'')
                        tiles_generated += 1
                        zoom_generated += 1

                except Exception as e:
                    tiles_failed += 1
                    self.stdout.write(
                        self.style.ERROR(f'❌ Failed to generate tile {tile.z}/{tile.x}/{tile.y}: {str(e)}')
                    )
            
            # Zoom level summary
            zoom_time = time.time() - zoom_start_time
            zoom_tiles_per_sec = zoom_generated / zoom_time if zoom_time > 0 else 0
            self.stdout.write(
                f'   ✅ Zoom {zoom}: {zoom_generated}/{len(tiles)} tiles in {zoom_time:.1f}s '
                f'({zoom_tiles_per_sec:.1f} tiles/sec)'
            )

        # Calculate final statistics
        total_time = time.time() - start_time
        avg_tiles_per_second = tiles_generated / total_time if total_time > 0 else 0

        self.stdout.write('')
        self.stdout.write('📊 Generation Summary:')
        self.stdout.write(f'   ✅ Generated: {tiles_generated:,} tiles')
        self.stdout.write(f'   ⏭️  Skipped: {tiles_skipped:,} tiles')
        self.stdout.write(f'   ❌ Failed: {tiles_failed:,} tiles')
        self.stdout.write(f'   ⏱️  Total time: {total_time:.1f}s')
        self.stdout.write(f'   ⚡ Average speed: {avg_tiles_per_second:.1f} tiles/second')

        # Update or create combined tile layer record
        try:
            combined_layer, created = VectorTileLayer.objects.get_or_create(
                layer=None,  # Combined tiles don't belong to a specific layer
                defaults={
                    'min_zoom': min_zoom,
                    'max_zoom': max_zoom,
                    'is_generated': True,
                    'total_tiles': tiles_generated,
                    'tiles_directory': str(output_dir),
                }
            )
            
            if not created:
                combined_layer.min_zoom = min_zoom
                combined_layer.max_zoom = max_zoom
                combined_layer.is_generated = True
                combined_layer.total_tiles = tiles_generated
                combined_layer.tiles_directory = str(output_dir)
                combined_layer.save()
            
            self.stdout.write(f'✅ Updated VectorTileLayer record')
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Could not update VectorTileLayer: {str(e)}')
            )

        # Generate sample URLs for testing
        self.stdout.write('')
        self.stdout.write('🎯 Sample URLs for testing:')
        sample_urls = self._generate_sample_urls(city_slug, city, min_zoom, max_zoom)
        for url in sample_urls:
            self.stdout.write(f'   • {url}')

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(f'🎉 Combined tile generation completed for {city_slug}!')
        )
        self.stdout.write(f'📁 Tiles saved to: {output_dir}')
        self.stdout.write(f'🔗 Access via: /api/tiles/{city_slug}/combined/{{z}}/{{x}}/{{y}}.mvt')

    def _get_city_bounds(self, layers):
        """Calculate bounding box for all layers"""
        bounds = {
            'west': float('inf'),
            'south': float('inf'),
            'east': float('-inf'),
            'north': float('-inf')
        }
        
        valid_bounds = False
        
        for layer in layers:
            if all([layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax]):
                bounds['west'] = min(bounds['west'], layer.bbox_xmin)
                bounds['south'] = min(bounds['south'], layer.bbox_ymin)
                bounds['east'] = max(bounds['east'], layer.bbox_xmax)
                bounds['north'] = max(bounds['north'], layer.bbox_ymax)
                valid_bounds = True
        
        return bounds if valid_bounds else None

    def _validate_tile_simple(self, mvt_data):
        """Simple tile validation"""
        try:
            if len(mvt_data) == 0:
                return False, "Empty tile data"
                
            # Try to decode MVT to ensure it's valid
            import mapbox_vector_tile
            decoded = mapbox_vector_tile.decode(mvt_data)
            
            if not decoded:
                return False, "Could not decode MVT"
                
            # Count features across all layers
            total_features = 0
            for layer_name, layer_data in decoded.items():
                features = layer_data.get('features', [])
                total_features += len(features)
                
            return True, f"Valid MVT with {total_features} features across {len(decoded)} layers"
                
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def _generate_sample_urls(self, city_slug, city, min_zoom, max_zoom):
        """Generate sample URLs for testing"""
        sample_urls = []
        
        # Use city center coordinates
        center_lat = city.center_lat or 12.9716
        center_lng = city.center_lng or 77.5946
        
        # Generate sample tile coordinates
        test_zooms = [min_zoom, (min_zoom + max_zoom) // 2, max_zoom]
        
        for zoom in test_zooms:
            tile = mercantile.tile(center_lng, center_lat, zoom)
            sample_urls.append(
                f'/api/tiles/{city_slug}/combined/{tile.z}/{tile.x}/{tile.y}.mvt'
            )
        
        return sample_urls