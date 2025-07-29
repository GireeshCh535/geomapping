# maps/management/commands/generate_and_upload_tiles.py

import os
import time
import tempfile
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.gis.db.models import Extent
from django.contrib.gis.geos import Polygon
from maps.models import City, DataLayer, Plot, Land
from maps.services import VectorTileService
from maps.tile_rendering_service import TileRenderingService
from maps.s3_upload_service import S3TileUploadService
import mercantile
import io

class Command(BaseCommand):
    help = 'Generate tiles and upload directly to S3 (no local storage) - PRODUCTION OPTIMIZED'

    def add_arguments(self, parser):
        parser.add_argument('--city', type=str, help='City slug (e.g., bangalore, hyderabad)')
        parser.add_argument('--type', choices=['city', 'real-estate', 'both'], default='city', 
                          help='Type of tiles to generate')
        parser.add_argument('--format', choices=['png', 'mvt', 'both'], default='png',
                          help='Tile format to generate')
        parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=14, help='Maximum zoom level')
        parser.add_argument('--real-estate-type', choices=['plots', 'lands', 'combined'], 
                          default='combined', help='Real estate data type')
        parser.add_argument('--batch-size', type=int, default=50, 
                          help='Number of tiles to process in each batch')
        parser.add_argument('--test-connection', action='store_true', 
                          help='Test S3 connection before starting')
        parser.add_argument('--dry-run', action='store_true', 
                          help='Generate tiles but do not upload to S3')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 DIRECT-TO-S3 TILE GENERATION STARTED'))
        
        # Validate arguments
        if not options['city'] and options['type'] in ['city', 'both']:
            self.stdout.write(self.style.ERROR('❌ --city is required for city tiles'))
            return
            
        # Initialize services
        self.tile_service = VectorTileService()
        self.render_service = TileRenderingService()
        self.s3_service = S3TileUploadService()
        
        # Test S3 connection
        if options['test_connection'] or not options['dry_run']:
            connection_test = self.s3_service.test_connection()
            if not connection_test['success']:
                self.stdout.write(self.style.ERROR(f"❌ S3 Connection failed: {connection_test['error']}"))
                return
            self.stdout.write(self.style.SUCCESS(f"✅ S3 Connected: {connection_test['bucket']}"))
        
        # Process based on type
        start_time = time.time()
        total_generated = 0
        total_uploaded = 0
        
        if options['type'] in ['city', 'both']:
            city_stats = self._process_city_tiles(options)
            total_generated += city_stats['generated']
            total_uploaded += city_stats['uploaded']
        
        if options['type'] in ['real-estate', 'both']:
            re_stats = self._process_real_estate_tiles(options)
            total_generated += re_stats['generated']
            total_uploaded += re_stats['uploaded']
        
        # Summary
        elapsed_time = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(f'\n🎉 TILE GENERATION COMPLETE!'))
        self.stdout.write(f'⏱️  Total time: {elapsed_time:.1f} seconds')
        self.stdout.write(f'📊 Tiles generated: {total_generated:,}')
        self.stdout.write(f'☁️  Tiles uploaded to S3: {total_uploaded:,}')
        self.stdout.write(f'🌐 Tiles available via CloudFront: https://{self.s3_service.cloudfront_domain}/')

    def _process_city_tiles(self, options):
        """Generate and upload city tiles directly to S3"""
        city_slug = options['city']
        tile_format = options['format']
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        
        self.stdout.write(f'\n🏙️  PROCESSING CITY TILES: {city_slug}')
        
        try:
            city = City.objects.get(slug=city_slug)
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            return {'generated': 0, 'uploaded': 0}
        
        layers = DataLayer.objects.filter(city=city, is_processed=True)
        if not layers.exists():
            self.stdout.write(self.style.ERROR(f"❌ No processed layers found for {city_slug}"))
            return {'generated': 0, 'uploaded': 0}
        
        # Get city bounds
        bounds = self._get_city_bounds(layers)
        if not bounds:
            self.stdout.write(self.style.ERROR(f"❌ Could not determine bounds for {city_slug}"))
            return {'generated': 0, 'uploaded': 0}
        
        self.stdout.write(f'📊 City bounds: {bounds}')
        
        generated_count = 0
        uploaded_count = 0
        
        # Generate tiles by zoom level
        for zoom in range(min_zoom, max_zoom + 1):
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'],
                zoom
            ))
            
            self.stdout.write(f'🔄 Zoom {zoom}: Processing {len(tiles)} tiles...')
            
            # Process tiles in batches
            for i in range(0, len(tiles), batch_size):
                batch = tiles[i:i + batch_size]
                batch_generated, batch_uploaded = self._process_city_tile_batch(
                    batch, layers, city_slug, tile_format, dry_run
                )
                generated_count += batch_generated
                uploaded_count += batch_uploaded
                
                # Progress update
                progress = min(i + batch_size, len(tiles))
                self.stdout.write(f'   Progress: {progress}/{len(tiles)} tiles')
        
        return {'generated': generated_count, 'uploaded': uploaded_count}
    
    def _process_city_tile_batch(self, tiles, layers, city_slug, tile_format, dry_run):
        """Process a batch of city tiles"""
        generated = 0
        uploaded = 0
        
        for tile in tiles:
            try:
                # Generate tile data (in memory)
                if tile_format in ['png', 'both']:
                    png_data = self._generate_city_png_tile(layers, tile.z, tile.x, tile.y)
                    if png_data:
                        generated += 1
                        
                        if not dry_run:
                            # Upload directly to S3
                            s3_key = f"{city_slug}/combined/{tile.z}_{tile.x}_{tile.y}.png"
                            upload_result = self._upload_tile_data(png_data, s3_key, 'image/png')
                            
                            if upload_result['success']:
                                uploaded += 1
                            else:
                                self.stderr.write(f"❌ Upload failed: {s3_key}")
                
                if tile_format in ['mvt', 'both']:
                    mvt_data = self._generate_city_mvt_tile(layers, tile.z, tile.x, tile.y)
                    if mvt_data:
                        generated += 1
                        
                        if not dry_run:
                            # Upload directly to S3
                            s3_key = f"{city_slug}/combined/{tile.z}_{tile.x}_{tile.y}.mvt"
                            upload_result = self._upload_tile_data(mvt_data, s3_key, 'application/vnd.mapbox-vector-tile')
                            
                            if upload_result['success']:
                                uploaded += 1
                            else:
                                self.stderr.write(f"❌ Upload failed: {s3_key}")
                                
            except Exception as e:
                self.stderr.write(f"❌ Error processing tile {tile.z}/{tile.x}/{tile.y}: {e}")
        
        return generated, uploaded
    
    def _process_real_estate_tiles(self, options):
        """Generate and upload real estate tiles directly to S3"""
        tile_format = options['format']
        real_estate_type = options['real_estate_type']
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        
        self.stdout.write(f'\n🏠 PROCESSING REAL ESTATE TILES: {real_estate_type}')
        
        # Get real estate bounds
        bounds = self._get_real_estate_bounds(real_estate_type)
        if not bounds:
            self.stdout.write(self.style.ERROR('❌ No real estate data found'))
            return {'generated': 0, 'uploaded': 0}
        
        self.stdout.write(f'📊 Real estate bounds: {bounds}')
        
        generated_count = 0
        uploaded_count = 0
        
        # Generate tiles by zoom level
        for zoom in range(min_zoom, max_zoom + 1):
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'],
                zoom
            ))
            
            self.stdout.write(f'🔄 Zoom {zoom}: Processing {len(tiles)} tiles...')
            
            # Process tiles in batches
            for i in range(0, len(tiles), batch_size):
                batch = tiles[i:i + batch_size]
                batch_generated, batch_uploaded = self._process_real_estate_tile_batch(
                    batch, real_estate_type, tile_format, dry_run
                )
                generated_count += batch_generated
                uploaded_count += batch_uploaded
                
                # Progress update
                progress = min(i + batch_size, len(tiles))
                self.stdout.write(f'   Progress: {progress}/{len(tiles)} tiles')
        
        return {'generated': generated_count, 'uploaded': uploaded_count}
    
    def _process_real_estate_tile_batch(self, tiles, real_estate_type, tile_format, dry_run):
        """Process a batch of real estate tiles"""
        generated = 0
        uploaded = 0
        
        for tile in tiles:
            try:
                # Generate tile data (in memory)
                if tile_format in ['png', 'both']:
                    png_data = self._generate_real_estate_png_tile(real_estate_type, tile.z, tile.x, tile.y)
                    if png_data:
                        generated += 1
                        
                        if not dry_run:
                            # Upload directly to S3
                            s3_key = f"real_estate/{real_estate_type}/{tile.z}_{tile.x}_{tile.y}.png"
                            upload_result = self._upload_tile_data(png_data, s3_key, 'image/png')
                            
                            if upload_result['success']:
                                uploaded += 1
                
                if tile_format in ['mvt', 'both']:
                    mvt_data = self._generate_real_estate_mvt_tile(real_estate_type, tile.z, tile.x, tile.y)
                    if mvt_data:
                        generated += 1
                        
                        if not dry_run:
                            # Upload directly to S3
                            s3_key = f"real_estate/{real_estate_type}/{tile.z}_{tile.x}_{tile.y}.mvt"
                            upload_result = self._upload_tile_data(mvt_data, s3_key, 'application/vnd.mapbox-vector-tile')
                            
                            if upload_result['success']:
                                uploaded += 1
                                
            except Exception as e:
                self.stderr.write(f"❌ Error processing real estate tile {tile.z}/{tile.x}/{tile.y}: {e}")
        
        return generated, uploaded
    
    def _generate_city_png_tile(self, layers, z, x, y):
        """Generate PNG tile for city data (in memory)"""
        try:
            # Generate MVT data first
            mvt_data = self.tile_service.generate_combined_tile(layers, z, x, y)
            
            if not mvt_data:
                # Return empty/transparent tile
                return self.render_service.create_empty_tile()
            
            # Convert MVT to PNG
            png_data = self.render_service.combined_mvt_to_png(mvt_data, layers, z, x, y)
            return png_data
            
        except Exception as e:
            self.stderr.write(f"Error generating city PNG tile {z}/{x}/{y}: {e}")
            return None
    
    def _generate_city_mvt_tile(self, layers, z, x, y):
        """Generate MVT tile for city data (in memory)"""
        try:
            return self.tile_service.generate_combined_tile(layers, z, x, y)
        except Exception as e:
            self.stderr.write(f"Error generating city MVT tile {z}/{x}/{y}: {e}")
            return None
    
    def _generate_real_estate_png_tile(self, real_estate_type, z, x, y):
        """Generate PNG tile for real estate data (in memory)"""
        try:
            # Get tile bounds
            tile = mercantile.Tile(x, y, z)
            bbox = mercantile.bounds(tile)
            tile_geom = Polygon.from_bbox(bbox)
            
            # Query data based on type
            features = []
            
            if real_estate_type in ['plots', 'combined']:
                plots = Plot.objects.filter(geometry__intersects=tile_geom)[:1000]  # Limit features
                features.extend([{
                    'geometry': plot.geometry,
                    'properties': {
                        'type': 'plot',
                        'id': plot.id,
                        'area': plot.area_sqft if hasattr(plot, 'area_sqft') else None
                    }
                } for plot in plots])
            
            if real_estate_type in ['lands', 'combined']:
                lands = Land.objects.filter(geometry__intersects=tile_geom)[:1000]  # Limit features
                features.extend([{
                    'geometry': land.geometry,
                    'properties': {
                        'type': 'land',
                        'id': land.id,
                        'area': land.area_sqft if hasattr(land, 'area_sqft') else None
                    }
                } for land in lands])
            
            if not features:
                return self.render_service.create_empty_tile()
            
            # Render to PNG
            return self.render_service.render_real_estate_png(features, z, x, y)
            
        except Exception as e:
            self.stderr.write(f"Error generating real estate PNG tile {z}/{x}/{y}: {e}")
            return None
    
    def _generate_real_estate_mvt_tile(self, real_estate_type, z, x, y):
        """Generate MVT tile for real estate data (in memory)"""
        try:
            # Implementation similar to PNG but returns MVT data
            # This would use mapbox_vector_tile library
            pass
        except Exception as e:
            self.stderr.write(f"Error generating real estate MVT tile {z}/{x}/{y}: {e}")
            return None
    
    def _upload_tile_data(self, tile_data, s3_key, content_type):
        """Upload tile data directly to S3"""
        try:
            # Create temporary file for upload
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(tile_data)
                temp_file.flush()
                
                # Upload to S3
                result = self.s3_service.upload_file(temp_file.name, s3_key)
                
                # Clean up temp file
                os.unlink(temp_file.name)
                
                return result
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _get_city_bounds(self, layers):
        """Get bounds for city layers"""
        bounds = None
        for layer in layers:
            layer_bounds = self.tile_service._get_layer_bounds(layer)
            if layer_bounds:
                if not bounds:
                    bounds = layer_bounds.copy()
                else:
                    bounds['west'] = min(bounds['west'], layer_bounds['west'])
                    bounds['south'] = min(bounds['south'], layer_bounds['south'])
                    bounds['east'] = max(bounds['east'], layer_bounds['east'])
                    bounds['north'] = max(bounds['north'], layer_bounds['north'])
        return bounds
    
    def _get_real_estate_bounds(self, real_estate_type):
        """Get bounds for real estate data"""
        bounds = {}
        
        if real_estate_type in ['plots', 'combined']:
            plot_extent = Plot.objects.aggregate(extent=Extent('geometry'))['extent']
            if plot_extent:
                bounds['plots'] = {
                    'west': plot_extent[0],
                    'south': plot_extent[1], 
                    'east': plot_extent[2],
                    'north': plot_extent[3]
                }
        
        if real_estate_type in ['lands', 'combined']:
            land_extent = Land.objects.aggregate(extent=Extent('geometry'))['extent']
            if land_extent:
                bounds['lands'] = {
                    'west': land_extent[0],
                    'south': land_extent[1],
                    'east': land_extent[2], 
                    'north': land_extent[3]
                }
        
        if not bounds:
            return None
        
        # Combine bounds if multiple types
        if len(bounds) > 1:
            all_bounds = list(bounds.values())
            return {
                'west': min(b['west'] for b in all_bounds),
                'south': min(b['south'] for b in all_bounds),
                'east': max(b['east'] for b in all_bounds),
                'north': max(b['north'] for b in all_bounds)
            }
        else:
            return list(bounds.values())[0]