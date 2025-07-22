# Create: maps/management/commands/generate_real_estate_mvt_tiles.py

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
    help = 'Generate MVT tiles for real estate data (plots and lands)'

    def add_arguments(self, parser):
        parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=16, help='Maximum zoom level')
        parser.add_argument('--force', action='store_true', help='Overwrite existing tiles')
        parser.add_argument('--output-dir', type=str, default='media/real_estate_tiles', help='Output directory')
        parser.add_argument('--type', choices=['plots', 'lands', 'both'], default='both', help='Data type to generate')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🏡 Starting Real Estate MVT Tile Generation'))
        
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
        
        self.stdout.write(self.style.SUCCESS('\n✅ Real Estate MVT tile generation completed!'))

    def generate_tiles_for_model(self, model, model_name, output_dir, min_zoom, max_zoom, force):
        """Generate tiles for a specific model (Plot or Land)"""
        
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
                    
                    # Generate MVT data
                    mvt_data = self.generate_mvt_tile(model, tile.z, tile.x, tile.y, zoom)
                    
                    if mvt_data:
                        # Save tile
                        with open(tile_path, 'wb') as f:
                            f.write(mvt_data)
                        tiles_generated += 1
                    
                except Exception as e:
                    self.stdout.write(f'   ❌ Error generating {model_name} tile {tile.z}/{tile.x}/{tile.y}: {e}')
        
        elapsed = time.time() - start_time
        self.stdout.write(f'✅ {model_name} tiles: {tiles_generated} generated, {tiles_skipped} skipped in {elapsed:.1f}s')

    def generate_combined_tiles(self, output_dir, min_zoom, max_zoom, force):
        """Generate combined tiles with both plots and lands"""
        
        self.stdout.write(f'\n🏡 Generating combined real estate tiles...')
        
        # Get combined bounds
        plot_bounds = self.get_data_bounds(Plot)
        land_bounds = self.get_data_bounds(Land)
        
        if not plot_bounds and not land_bounds:
            self.stdout.write(self.style.WARNING('⚠️  No real estate data found'))
            return
        
        # Calculate combined bounds
        bounds = {
            'west': min(plot_bounds['west'] if plot_bounds else float('inf'), 
                       land_bounds['west'] if land_bounds else float('inf')),
            'south': min(plot_bounds['south'] if plot_bounds else float('inf'), 
                        land_bounds['south'] if land_bounds else float('inf')),
            'east': max(plot_bounds['east'] if plot_bounds else float('-inf'), 
                       land_bounds['east'] if land_bounds else float('-inf')),
            'north': max(plot_bounds['north'] if plot_bounds else float('-inf'), 
                        land_bounds['north'] if land_bounds else float('-inf'))
        }
        
        # Generate combined tiles
        total_tiles = 0
        tiles_generated = 0
        
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
                    
                    if tile_path.exists() and not force:
                        continue
                    
                    # Generate combined MVT data
                    mvt_data = self.generate_combined_mvt_tile(tile.z, tile.x, tile.y, zoom)
                    
                    if mvt_data:
                        with open(tile_path, 'wb') as f:
                            f.write(mvt_data)
                        tiles_generated += 1
                
                except Exception as e:
                    self.stdout.write(f'   ❌ Error generating combined tile {tile.z}/{tile.x}/{tile.y}: {e}')
        
        self.stdout.write(f'✅ Combined tiles: {tiles_generated} generated')

    def get_data_bounds(self, model):
        """Get bounding box for model data"""
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

    def generate_mvt_tile(self, model, z, x, y, zoom_level):
        """Generate MVT tile for single model"""
        
        # Get tile bounds
        tile_bounds = self.get_tile_bounds(z, x, y)
        
        # Query features in tile
        features = model.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        )
        
        if not features.exists():
            return None
        
        # Cluster points at low zoom levels
        if zoom_level < 12:
            features = self.cluster_features(features, tile_bounds, zoom_level)
        
        # Convert to MVT
        layer_name = model._meta.model_name + 's'  # 'plots' or 'lands'
        return self.features_to_mvt(features, layer_name, z, x, y, model)

    def generate_combined_mvt_tile(self, z, x, y, zoom_level):
        """Generate combined MVT tile with both plots and lands - Fixed encoding"""
        
        tile_bounds = self.get_tile_bounds(z, x, y)
        
        # Get features from both models
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
        
        # Cluster at low zoom levels
        if zoom_level < 12:
            plots = self.cluster_features(plots, tile_bounds, zoom_level)
            lands = self.cluster_features(lands, tile_bounds, zoom_level)
        
        # Create layers list (matching working pattern)
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
        
        # Encode the MVT (matching working pattern)
        return mapbox_vector_tile.encode(layers_list)

    def cluster_features(self, features, tile_bounds, zoom_level):
        """Simple clustering for low zoom levels"""
        # For simplicity, just limit the number of features at low zooms
        max_features = 100 if zoom_level < 10 else 500
        return features[:max_features]

    def get_tile_bounds(self, z, x, y):
        """Get tile bounding box as Polygon"""
        bounds = mercantile.bounds(x, y, z)
        return Polygon.from_bbox([
            bounds.west, bounds.south,
            bounds.east, bounds.north
        ])

    def features_to_mvt(self, features, layer_name, z, x, y, model):
        """Convert features to MVT format - Fixed to match working patterns"""
        
        if not features:
            return None
            
        try:
            mvt_features = []
            
            for feature in features:
                try:
                    # Get coordinates
                    coords = [feature.location.x, feature.location.y]
                    
                    # Prepare properties based on model type (using correct field names)
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
                    
                    mvt_feature = {
                        'geometry': {
                            'type': 'Point',
                            'coordinates': coords
                        },
                        'properties': properties
                    }
                    
                    mvt_features.append(mvt_feature)
                    
                except Exception as e:
                    # Skip problematic features but continue processing
                    continue
            
            if not mvt_features:
                return None
            
            # Format for mapbox-vector-tile (matching working pattern)
            layer_data = [{
                'name': layer_name,
                'features': mvt_features,
                'version': 2,
                'extent': 4096
            }]
            
            # Encode the MVT (matching working approach)
            mvt_tile = mapbox_vector_tile.encode(layer_data)
            
            return mvt_tile
            
        except Exception as e:
            self.stdout.write(f"❌ MVT encoding failed for {layer_name}: {e}")
            return None

    def prepare_features_for_mvt(self, features, model):
        """Prepare features for MVT encoding - Fixed field mapping"""
        
        mvt_features = []
        
        for feature in features:
            try:
                # Get coordinates
                coords = [feature.location.x, feature.location.y]
                
                # Prepare properties based on model type (using correct field names)
                if model == Plot:
                    properties = {
                        'id': feature.plot_id,
                        'name': feature.marker_title or '',  # Using marker_title as name
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
                        'name': feature.marker_title or '',  # Using marker_title as name
                        'title': feature.marker_title or '',
                        'marker_id': feature.marker_id or '',
                        'area_text': feature.area_text or '',
                        'price_text': feature.price_text or '',
                        'type': 'land',
                        'category': 'Real Estate'
                    }
                
                mvt_feature = {
                    'geometry': {
                        'type': 'Point',
                        'coordinates': coords
                    },
                    'properties': properties
                }
                
                mvt_features.append(mvt_feature)
                
            except Exception as e:
                self.stdout.write(f'   ⚠️  Skipping feature {getattr(feature, "plot_id", getattr(feature, "land_id", "unknown"))}: {e}')
                continue
        
        return {
            'features': mvt_features,
            'extent': 4096,
            'version': 2
        }