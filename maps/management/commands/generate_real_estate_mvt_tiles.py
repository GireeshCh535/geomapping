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
    help = 'Generate and validate MVT tiles for real estate data (plots and lands)'

    def add_arguments(self, parser):
        parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=16, help='Maximum zoom level')
        parser.add_argument('--force', action='store_true', help='Force regeneration of existing tiles')
        parser.add_argument('--output-dir', type=str, default='media/real_estate_tiles', help='Output directory')
        parser.add_argument('--type', choices=['plots', 'lands', 'combined'], default='combined', help='Data type to generate')
        parser.add_argument('--skip-validation', action='store_true', help='Skip tile validation')

    def validate_tile(self, tile_data):
        """
        Validate a tile's MVT structure and content
        Returns (is_valid, details) tuple
        """
        try:
            # Try to decode as MVT
            decoded_tile = mapbox_vector_tile.decode(tile_data)
            
            if not decoded_tile:
                return False, "Decoded tile has no layers"
            
            validation_details = []
            
            # Validate each layer
            for layer_name, layer_data in decoded_tile.items():
                # Check version
                version = layer_data.get('version')
                if not version or version < 1:
                    return False, f"Invalid layer version: {version}"
                
                # Check extent
                extent = layer_data.get('extent')
                if not extent or extent != 4096:  # Standard MVT extent
                    return False, f"Invalid extent: {extent}"
                
                # Validate features
                features = layer_data.get('features', [])
                if not features:
                    validation_details.append(f"Layer {layer_name} has no features (may be valid for empty areas)")
                    continue
                
                # Check feature structure
                for feature in features:
                    if 'geometry' not in feature:
                        return False, "Feature missing geometry"
                    if 'properties' not in feature:
                        return False, "Feature missing properties"
                    
                    # Validate geometry type
                    geom_type = feature['geometry'].get('type')
                    if geom_type not in ['Point', 'LineString', 'Polygon', 'MultiPoint', 'MultiLineString', 'MultiPolygon']:
                        return False, f"Invalid geometry type: {geom_type}"
                
                validation_details.append(f"Layer {layer_name}: {len(features)} features")
            
            return True, "Valid MVT with " + ", ".join(validation_details) if validation_details else "Valid MVT"
            
        except Exception as e:
            return False, f"MVT validation error: {str(e)}"

    def get_data_bounds(self, data_type):
        """Get bounding box for the specified data type"""
        if data_type == 'plots':
            extent = Plot.objects.filter(is_active=True).aggregate(
                extent=Extent('location')
            )['extent']
        elif data_type == 'lands':
            extent = Land.objects.filter(is_active=True).aggregate(
                extent=Extent('location')
            )['extent']
        else:  # combined
            # Get combined extent from both models
            plot_extent = Plot.objects.filter(is_active=True).aggregate(
                extent=Extent('location')
            )['extent']
            land_extent = Land.objects.filter(is_active=True).aggregate(
                extent=Extent('location')
            )['extent']
            
            if plot_extent and land_extent:
                extent = [
                    min(plot_extent[0], land_extent[0]),  # west
                    min(plot_extent[1], land_extent[1]),  # south
                    max(plot_extent[2], land_extent[2]),  # east
                    max(plot_extent[3], land_extent[3])   # north
                ]
            else:
                extent = plot_extent or land_extent
        
        if extent:
            return {
                'west': extent[0],
                'south': extent[1],
                'east': extent[2],
                'north': extent[3]
            }
        return None

    def get_tile_bounds(self, z, x, y):
        """Get tile bounds as Polygon"""
        bounds = mercantile.bounds(x, y, z)
        return Polygon.from_bbox([
            bounds.west, bounds.south,
            bounds.east, bounds.north
        ])

    def generate_mvt_tile(self, data_type, z, x, y):
        """Generate MVT tile for the specified data type and coordinates"""
        tile_bounds = self.get_tile_bounds(z, x, y)
        
        try:
            if data_type == 'plots':
                return self.generate_plots_mvt(tile_bounds, z, x, y)
            elif data_type == 'lands':
                return self.generate_lands_mvt(tile_bounds, z, x, y)
            else:  # combined
                return self.generate_combined_mvt(tile_bounds, z, x, y)
                
        except Exception as e:
            return None

    def generate_plots_mvt(self, tile_bounds, z, x, y):
        """Generate MVT for plots only"""
        # Query plots in tile
        plots = Plot.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        )
        
        if not plots.exists():
            return None
        
        # Limit features at low zoom levels
        max_features = 50 if z < 10 else 200 if z < 12 else 1000
        plots = plots[:max_features]
        
        # Create MVT features
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
        
        if not plot_features:
            return None
        
        # Encode MVT
        layer_data = [{
            'name': 'plots',
            'features': plot_features,
            'version': 2,
            'extent': 4096
        }]
        
        return mapbox_vector_tile.encode(layer_data)

    def generate_lands_mvt(self, tile_bounds, z, x, y):
        """Generate MVT for lands only"""
        # Query lands in tile
        lands = Land.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        )
        
        if not lands.exists():
            return None
        
        # Limit features at low zoom levels
        max_features = 50 if z < 10 else 200 if z < 12 else 1000
        lands = lands[:max_features]
        
        # Create MVT features
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
        
        if not land_features:
            return None
        
        # Encode MVT
        layer_data = [{
            'name': 'lands',
            'features': land_features,
            'version': 2,
            'extent': 4096
        }]
        
        return mapbox_vector_tile.encode(layer_data)

    def generate_combined_mvt(self, tile_bounds, z, x, y):
        """Generate combined MVT with both plots and lands"""
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
        
        # Limit features
        max_features = 25 if z < 10 else 100 if z < 12 else 500  # Split between both types
        plots = plots[:max_features]
        lands = lands[:max_features]
        
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

    def generate_and_validate_tiles(self, data_type, min_zoom, max_zoom, output_dir, force, skip_validation):
        """Generate and validate all tiles for the specified data type within zoom range"""
        
        bounds = self.get_data_bounds(data_type)
        if not bounds:
            return {'error': f'No bounds available for {data_type}'}
        
        self.stdout.write(f"📊 Data bounds: {bounds}")
        
        total_tiles = 0
        validated_tiles = 0
        failed_tiles = 0
        validation_errors = []
        
        for zoom in range(min_zoom, max_zoom + 1):
            # Get tiles that intersect with data bounds
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'],
                zoom
            ))
            
            self.stdout.write(f"   🗺️  Zoom {zoom}: Processing {len(tiles)} tiles")
            zoom_tiles = 0
            
            for tile in tiles:
                try:
                    # Check if tile already exists and force is not set
                    tile_dir = output_dir / data_type / str(tile.z) / str(tile.x)
                    tile_path = tile_dir / f'{tile.y}.mvt'
                    
                    if tile_path.exists() and not force:
                        continue
                    
                    # Generate tile
                    mvt_data = self.generate_mvt_tile(data_type, tile.z, tile.x, tile.y)
                    if not mvt_data:
                        continue
                    
                    total_tiles += 1
                    zoom_tiles += 1
                    
                    # Validate tile (if not skipped)
                    if not skip_validation:
                        is_valid, validation_msg = self.validate_tile(mvt_data)
                        if not is_valid:
                            failed_tiles += 1
                            validation_errors.append(f"z{tile.z}/{tile.x}/{tile.y}: {validation_msg}")
                            continue
                        
                        validated_tiles += 1
                    else:
                        validated_tiles += 1
                    
                    # Save valid tile
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    
                    with open(tile_path, 'wb') as f:
                        f.write(mvt_data)
                    
                    # Log progress every 50 tiles
                    if zoom_tiles % 50 == 0:
                        self.stdout.write(f"      Generated {zoom_tiles} tiles...")
                    
                except Exception as e:
                    failed_tiles += 1
                    validation_errors.append(f"z{tile.z}/{tile.x}/{tile.y}: Generation error - {str(e)}")
            
            if zoom_tiles > 0:
                self.stdout.write(f"      ✅ Zoom {zoom}: Generated {zoom_tiles} tiles")
        
        return {
            'data_type': data_type,
            'tiles_generated': total_tiles,
            'tiles_validated': validated_tiles,
            'tiles_failed': failed_tiles,
            'validation_errors': validation_errors[:10],  # First 10 errors
            'status': 'success' if total_tiles > 0 else 'no_tiles',
            'zoom_range': {'min': min_zoom, 'max': max_zoom},
            'bounds': bounds
        }

    def handle(self, *args, **options):
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        force = options['force']
        output_dir = Path(options['output_dir'])
        data_type = options['type']
        skip_validation = options['skip_validation']
        
        # Validate zoom levels
        if min_zoom < 0 or max_zoom > 20 or min_zoom > max_zoom:
            self.stdout.write(self.style.ERROR('❌ Invalid zoom levels'))
            return
        
        self.stdout.write(self.style.SUCCESS('🏡 Starting Real Estate MVT Tile Generation with Validation'))
        self.stdout.write(f'📊 Configuration:')
        self.stdout.write(f'   Data type: {data_type}')
        self.stdout.write(f'   Zoom levels: {min_zoom} to {max_zoom}')
        self.stdout.write(f'   Output: {output_dir}')
        self.stdout.write(f'   Force overwrite: {force}')
        self.stdout.write(f'   Skip validation: {skip_validation}')
        
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Check data availability
        plot_count = Plot.objects.filter(is_active=True).count()
        land_count = Land.objects.filter(is_active=True).count()
        
        self.stdout.write(f'\n📊 Data availability:')
        self.stdout.write(f'   Plots: {plot_count:,}')
        self.stdout.write(f'   Lands: {land_count:,}')
        
        if plot_count == 0 and land_count == 0:
            self.stdout.write(self.style.ERROR('❌ No real estate data found. Import data first.'))
            return
        
        # Statistics
        total_tiles_generated = 0
        total_tiles_validated = 0
        total_tiles_failed = 0
        all_validation_errors = []
        
        start_time = time.time()
        
        # Generate tiles based on type
        if data_type == 'plots' and plot_count > 0:
            self.stdout.write(f"\n📂 Generating tiles for: plots")
            result = self.generate_and_validate_tiles('plots', min_zoom, max_zoom, output_dir, force, skip_validation)
            total_tiles_generated += result['tiles_generated']
            total_tiles_validated += result['tiles_validated']
            total_tiles_failed += result['tiles_failed']
            all_validation_errors.extend(result['validation_errors'])
            
        elif data_type == 'lands' and land_count > 0:
            self.stdout.write(f"\n📂 Generating tiles for: lands")
            result = self.generate_and_validate_tiles('lands', min_zoom, max_zoom, output_dir, force, skip_validation)
            total_tiles_generated += result['tiles_generated']
            total_tiles_validated += result['tiles_validated']
            total_tiles_failed += result['tiles_failed']
            all_validation_errors.extend(result['validation_errors'])
            
        elif data_type == 'combined':
            self.stdout.write(f"\n📂 Generating tiles for: combined (plots + lands)")
            result = self.generate_and_validate_tiles('combined', min_zoom, max_zoom, output_dir, force, skip_validation)
            total_tiles_generated += result['tiles_generated']
            total_tiles_validated += result['tiles_validated']
            total_tiles_failed += result['tiles_failed']
            all_validation_errors.extend(result['validation_errors'])
        
        # Final statistics
        end_time = time.time()
        duration = end_time - start_time
        
        self.stdout.write(f'\n📊 GENERATION SUMMARY')
        self.stdout.write('=' * 50)
        self.stdout.write(f'✅ Tiles generated: {total_tiles_generated:,}')
        self.stdout.write(f'✅ Tiles validated: {total_tiles_validated:,}')
        self.stdout.write(f'❌ Tiles failed: {total_tiles_failed:,}')
        self.stdout.write(f'⏱️  Duration: {duration:.2f} seconds')
        
        if total_tiles_generated > 0:
            self.stdout.write(f'🚀 Speed: {total_tiles_generated / duration:.1f} tiles/second')
        
        # Show validation errors (first 5)
        if all_validation_errors:
            self.stdout.write(f'\n❌ VALIDATION ERRORS (showing first 5):')
            for i, error in enumerate(all_validation_errors[:5], 1):
                self.stdout.write(f'   {i}. {error}')
            
            if len(all_validation_errors) > 5:
                self.stdout.write(f'   ... and {len(all_validation_errors) - 5} more errors')
        
        if total_tiles_generated > 0:
            self.stdout.write(self.style.SUCCESS('\n✅ Real Estate MVT tile generation completed successfully!'))
            
            # Sample URLs
            self.stdout.write(f'\n🔗 Sample tile URLs:')
            self.stdout.write(f'   Vector: /api/real-estate-tiles/{data_type}/10/512/512.mvt')
            self.stdout.write(f'   Raster: /api/real-estate-tiles/{data_type}/10/512/512.png')
        else:
            self.stdout.write(self.style.WARNING('\n⚠️  No tiles were generated. Check your data and bounds.'))