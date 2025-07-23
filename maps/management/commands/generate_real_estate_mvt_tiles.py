# maps/management/commands/generate_real_estate_mvt_tiles.py
# FIXED VERSION - Better feature limits and clustering

import os
import time
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Polygon
from django.contrib.gis.db.models import Extent
from maps.models import Plot, Land
import mercantile
import mapbox_vector_tile

class Command(BaseCommand):
    help = 'Generate MVT tiles for real estate data (plots and lands) - FIXED'

    def add_arguments(self, parser):
        parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=16, help='Maximum zoom level')
        parser.add_argument('--force', action='store_true', help='Overwrite existing tiles')
        parser.add_argument('--output-dir', type=str, default='media/real_estate_tiles', help='Output directory')
        parser.add_argument('--type', choices=['plots', 'lands', 'both'], default='both', help='Data type to generate')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🏡 Starting FIXED Real Estate MVT Tile Generation'))
        
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        force = options['force']
        output_dir = Path(options['output_dir'])
        data_type = options['type']
        
        # Validate zoom levels
        if min_zoom < 0 or max_zoom > 20 or min_zoom > max_zoom:
            self.stdout.write(self.style.ERROR('❌ Invalid zoom levels'))
            return
        
        self.stdout.write(f'📊 Configuration:')
        self.stdout.write(f'   Zoom levels: {min_zoom} to {max_zoom}')
        self.stdout.write(f'   Data type: {data_type}')
        self.stdout.write(f'   Output: {output_dir}')
        self.stdout.write(f'   Force overwrite: {force}')
        
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate tiles based on type
        if data_type in ['plots', 'both']:
            self.generate_tiles_for_model(Plot, 'plots', output_dir, min_zoom, max_zoom, force)
        
        if data_type in ['lands', 'both']:
            self.generate_tiles_for_model(Land, 'lands', output_dir, min_zoom, max_zoom, force)
        
        # Generate combined tiles if both types requested
        if data_type == 'both':
            self.generate_combined_tiles(output_dir, min_zoom, max_zoom, force)
        
        self.stdout.write(self.style.SUCCESS('\n✅ FIXED Real Estate MVT tile generation completed!'))

    def generate_tiles_for_model(self, model, model_name, output_dir, min_zoom, max_zoom, force):
        """Generate tiles for a specific model (Plot or Land) - FIXED LIMITS"""
        
        self.stdout.write(f'\n📍 Generating {model_name} tiles...')
        
        # Get data bounds
        bounds = self.get_data_bounds(model)
        if not bounds:
            self.stdout.write(self.style.WARNING(f'⚠️  No {model_name} data found'))
            return
        
        self.stdout.write(f'📊 Data bounds: {bounds}')
        
        # Calculate total tiles
        total_tiles = 0
        for zoom in range(min_zoom, max_zoom + 1):
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'],
                zoom
            ))
            total_tiles += len(tiles)
            self.stdout.write(f'   Zoom {zoom}: {len(tiles)} tiles')
        
        self.stdout.write(f'📊 Total {model_name} tiles to generate: {total_tiles:,}')
        
        # Generate tiles
        start_time = time.time()
        tiles_generated = 0
        tiles_skipped = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'],
                zoom
            ))
            
            self.stdout.write(f'🔄 Zoom {zoom}: Processing {len(tiles)} {model_name} tiles...')
            
            for tile in tiles:
                try:
                    # Create tile directory: model_name/z/x/y.mvt
                    tile_dir = output_dir / model_name / str(tile.z) / str(tile.x)
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    tile_path = tile_dir / f'{tile.y}.mvt'
                    
                    # Skip if exists and not forcing
                    if tile_path.exists() and not force:
                        tiles_skipped += 1
                        continue
                    
                    # Generate MVT data - FIXED LIMITS
                    mvt_data = self.generate_mvt_tile(model, tile.z, tile.x, tile.y, zoom)
                    
                    if mvt_data:
                        # Save tile
                        with open(tile_path, 'wb') as f:
                            f.write(mvt_data)
                        tiles_generated += 1
                    else:
                        # Save empty tile
                        with open(tile_path, 'wb') as f:
                            f.write(b'')
                        tiles_generated += 1
                    
                    # Progress update
                    if tiles_generated % 100 == 0:
                        self.stdout.write(f'   Generated {tiles_generated} tiles so far...')
                        
                except Exception as e:
                    self.stdout.write(f'   ❌ Error generating tile {tile.z}/{tile.x}/{tile.y}: {e}')
                    continue
        
        # Summary
        elapsed = time.time() - start_time
        self.stdout.write(f'✅ {model_name} tiles completed in {elapsed:.2f}s')
        self.stdout.write(f'   Generated: {tiles_generated}')
        self.stdout.write(f'   Skipped: {tiles_skipped}')

    def generate_mvt_tile(self, model, z, x, y, zoom_level):
        """Generate MVT data for a single tile - FIXED FEATURE LIMITS"""
        
        # Get tile bounds
        bounds = mercantile.bounds(x, y, z)
        tile_bounds = Polygon.from_bbox([
            bounds.west, bounds.south,
            bounds.east, bounds.north
        ])
        
        # Query features in tile
        features = model.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        )
        
        if not features.exists():
            return None
        
        # FIXED: Much more generous feature limits
        if zoom_level <= 4:
            max_features = 1000   # Show up to 1000 features at zoom 4
        elif zoom_level <= 6:
            max_features = 2000   # Show up to 2000 features at zoom 6
        elif zoom_level <= 8:
            max_features = 3000   # Show up to 3000 features at zoom 8
        elif zoom_level <= 10:
            max_features = 5000   # Show up to 5000 features at zoom 10
        else:
            max_features = 10000  # Show up to 10000 features at high zoom
        
        # Apply limit
        features = features[:max_features]
        
        self.stdout.write(f'   Tile {z}/{x}/{y}: {features.count()} features (max: {max_features})')
        
        # Convert to MVT
        return self.features_to_mvt(features, model.__name__.lower(), z, x, y, model)

    def features_to_mvt(self, features, layer_name, z, x, y, model):
        """Convert features to MVT format"""
        
        if not features:
            return None
            
        try:
            mvt_features = []
            
            for feature in features:
                try:
                    # Get coordinates
                    coords = [feature.location.x, feature.location.y]
                    
                    # Prepare properties based on model type
                    if model == Plot:
                        properties = {
                            'id': feature.plot_id,
                            'name': feature.marker_title or '',
                            'title': feature.marker_title or '',
                            'marker_id': feature.marker_id or '',
                            'area_sq_yards': feature.area_sq_yards or 0,
                            'price_per_sq_yard': feature.price_per_sq_yard or 0,
                            'total_price': feature.total_price or 0,
                            'type': 'plot',
                            'category': 'Real Estate'
                        }
                    else:  # Land
                        properties = {
                            'id': feature.land_id,
                            'name': feature.marker_title or '',
                            'title': feature.marker_title or '',
                            'marker_id': feature.marker_id or '',
                            'area_text': feature.area_text or '',
                            'price_text': feature.price_text or '',
                            'type': 'land',
                            'category': 'Real Estate'
                        }
                    
                    mvt_features.append({
                        'geometry': {
                            'type': 'Point',
                            'coordinates': coords
                        },
                        'properties': properties
                    })
                    
                except Exception as e:
                    continue
            
            if not mvt_features:
                return None
            
            # Encode MVT
            layer_data = [{
                'name': layer_name,
                'features': mvt_features,
                'version': 2,
                'extent': 4096
            }]
            
            return mapbox_vector_tile.encode(layer_data)
            
        except Exception as e:
            self.stdout.write(f'   ❌ Error encoding MVT: {e}')
            return None

    def get_data_bounds(self, model):
        """Get bounding box for data"""
        extent = model.objects.filter(is_active=True).aggregate(
            extent=Extent('location')
        )['extent']
        
        if extent:
            return {
                'west': extent[0],
                'south': extent[1],
                'east': extent[2],
                'north': extent[3]
            }
        return None

    def generate_combined_tiles(self, output_dir, min_zoom, max_zoom, force):
        """Generate combined tiles with both plots and lands"""
        
        self.stdout.write(f'\n🔄 Generating combined tiles...')
        
        # Get combined bounds
        plot_extent = Plot.objects.filter(is_active=True).aggregate(extent=Extent('location'))['extent']
        land_extent = Land.objects.filter(is_active=True).aggregate(extent=Extent('location'))['extent']
        
        if not plot_extent and not land_extent:
            self.stdout.write(self.style.WARNING('⚠️  No data found for combined tiles'))
            return
        
        # Calculate combined bounds
        if plot_extent and land_extent:
            bounds = {
                'west': min(plot_extent[0], land_extent[0]),
                'south': min(plot_extent[1], land_extent[1]),
                'east': max(plot_extent[2], land_extent[2]),
                'north': max(plot_extent[3], land_extent[3])
            }
        elif plot_extent:
            bounds = {'west': plot_extent[0], 'south': plot_extent[1], 'east': plot_extent[2], 'north': plot_extent[3]}
        else:
            bounds = {'west': land_extent[0], 'south': land_extent[1], 'east': land_extent[2], 'north': land_extent[3]}
        
        self.stdout.write(f'📊 Combined bounds: {bounds}')
        
        # Generate combined tiles for each zoom level
        for zoom in range(min_zoom, max_zoom + 1):
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'],
                zoom
            ))
            
            self.stdout.write(f'🔄 Zoom {zoom}: Processing {len(tiles)} combined tiles...')
            
            for tile in tiles:
                try:
                    # Create tile directory: combined/z/x/y.mvt
                    tile_dir = output_dir / 'combined' / str(tile.z) / str(tile.x)
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    tile_path = tile_dir / f'{tile.y}.mvt'
                    
                    # Skip if exists and not forcing
                    if tile_path.exists() and not force:
                        continue
                    
                    # Generate combined MVT data
                    mvt_data = self.generate_combined_mvt_tile(tile.z, tile.x, tile.y, zoom)
                    
                    if mvt_data:
                        with open(tile_path, 'wb') as f:
                            f.write(mvt_data)
                    else:
                        with open(tile_path, 'wb') as f:
                            f.write(b'')
                            
                except Exception as e:
                    self.stdout.write(f'   ❌ Error generating combined tile {tile.z}/{tile.x}/{tile.y}: {e}')
                    continue

    def generate_combined_mvt_tile(self, z, x, y, zoom_level):
        """Generate combined MVT with both plots and lands"""
        
        # Get tile bounds
        bounds = mercantile.bounds(x, y, z)
        tile_bounds = Polygon.from_bbox([
            bounds.west, bounds.south,
            bounds.east, bounds.north
        ])
        
        # Get both plots and lands
        plots = Plot.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        )
        
        lands = Land.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        )
        
        if not plots.exists() and not lands.exists():
            return None
        
        # FIXED: More generous combined limits
        if zoom_level <= 4:
            max_features_per_type = 500   # 500 plots + 500 lands = 1000 total
        elif zoom_level <= 6:
            max_features_per_type = 1000  # 1000 plots + 1000 lands = 2000 total
        elif zoom_level <= 8:
            max_features_per_type = 1500  # 1500 plots + 1500 lands = 3000 total
        elif zoom_level <= 10:
            max_features_per_type = 2500  # 2500 plots + 2500 lands = 5000 total
        else:
            max_features_per_type = 5000  # 5000 plots + 5000 lands = 10000 total
        
        # Apply limits
        plots = plots[:max_features_per_type]
        lands = lands[:max_features_per_type]
        
        # Create layers list
        layers_list = []
        
        # Add plots layer
        if plots.exists():
            plot_features = []
            for plot in plots:
                try:
                    plot_features.append({
                        'geometry': {
                            'type': 'Point',
                            'coordinates': [plot.location.x, plot.location.y]
                        },
                        'properties': {
                            'id': plot.plot_id,
                            'name': plot.marker_title or '',
                            'title': plot.marker_title or '',
                            'marker_id': plot.marker_id or '',
                            'area_sq_yards': plot.area_sq_yards or 0,
                            'price_per_sq_yard': plot.price_per_sq_yard or 0,
                            'total_price': plot.total_price or 0,
                            'type': 'plot',
                            'category': 'Real Estate'
                        }
                    })
                except Exception:
                    continue
            
            if plot_features:
                layers_list.append({
                    'name': 'plots',
                    'features': plot_features,
                    'version': 2,
                    'extent': 4096
                })
        
        # Add lands layer
        if lands.exists():
            land_features = []
            for land in lands:
                try:
                    land_features.append({
                        'geometry': {
                            'type': 'Point',
                            'coordinates': [land.location.x, land.location.y]
                        },
                        'properties': {
                            'id': land.land_id,
                            'name': land.marker_title or '',
                            'title': land.marker_title or '',
                            'marker_id': land.marker_id or '',
                            'area_text': land.area_text or '',
                            'price_text': land.price_text or '',
                            'type': 'land',
                            'category': 'Real Estate'
                        }
                    })
                except Exception:
                    continue
            
            if land_features:
                layers_list.append({
                    'name': 'lands',
                    'features': land_features,
                    'version': 2,
                    'extent': 4096
                })
        
        if not layers_list:
            return None
        
        return mapbox_vector_tile.encode(layers_list)