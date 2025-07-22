# Create: maps/management/commands/generate_real_estate_png_tiles.py

import os
import time
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.gis.db.models import Extent
from maps.models import Plot, Land
import mercantile

class Command(BaseCommand):
    help = 'Generate PNG tiles for real estate data (plots and lands) - Matching existing patterns'

    def add_arguments(self, parser):
        parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=14, help='Maximum zoom level')
        parser.add_argument('--overwrite', action='store_true', help='Overwrite existing tiles')
        parser.add_argument('--output-dir', type=str, default='static/real_estate_tiles_png', help='Output directory')
        parser.add_argument('--type', choices=['plots', 'lands', 'combined'], default='combined', help='Data type to generate')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🏡 Starting Real Estate PNG Tile Generation'))
        
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        overwrite = options['overwrite']
        output_dir = options['output_dir']
        data_type = options['type']
        
        self.stdout.write(f'📊 Configuration:')
        self.stdout.write(f'   Zoom levels: {min_zoom} to {max_zoom}')
        self.stdout.write(f'   Data type: {data_type}')
        self.stdout.write(f'   Output: {output_dir}')
        self.stdout.write(f'   Overwrite existing: {overwrite}')
        
        # Get data bounds
        bounds = self.get_real_estate_bounds(data_type)
        if not bounds:
            self.stdout.write(self.style.ERROR('❌ No real estate data found'))
            return
        
        self.stdout.write(f'📊 Data bounds: {bounds}')
        
        # Import services (matching existing pattern)
        from maps.services import VectorTileService
        from maps.tile_rendering_service import TileRenderingService
        
        # Create services
        vector_service = VectorTileService()
        render_service = TileRenderingService()
        
        # Create output directory
        out_dir = os.path.join(output_dir, data_type)
        os.makedirs(out_dir, exist_ok=True)
        
        # Generate tiles for each zoom level
        total_tiles = 0
        generated_tiles = 0
        skipped_tiles = 0
        
        for zoom in range(min_zoom, max_zoom + 1):
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'],
                zoom
            ))
            
            self.stdout.write(f"Zoom {zoom}: {len(tiles)} tiles")
            
            for tile in tiles:
                png_path = os.path.join(out_dir, f"{tile.z}_{tile.x}_{tile.y}.png")
                total_tiles += 1
                
                # Skip if exists and not overwriting
                if os.path.exists(png_path) and not overwrite:
                    skipped_tiles += 1
                    continue
                
                try:
                    # Generate MVT data first (matching existing pattern)
                    mvt_data = self.generate_real_estate_mvt(data_type, tile.z, tile.x, tile.y, zoom)
                    
                    if not mvt_data:
                        # Save empty/transparent PNG
                        png_data = render_service.create_empty_tile()
                    else:
                        # Convert MVT to PNG using existing service
                        png_data = self.mvt_to_png_real_estate(render_service, mvt_data, data_type, tile.z, tile.x, tile.y)
                    
                    # Save PNG file
                    with open(png_path, 'wb') as f:
                        f.write(png_data)
                    
                    generated_tiles += 1
                    
                    # Progress update (matching existing pattern)
                    if generated_tiles % 100 == 0:
                        self.stdout.write(f"   Generated {generated_tiles} PNGs so far...")
                        
                except Exception as e:
                    self.stdout.write(f'   ❌ Error generating PNG tile {tile.z}/{tile.x}/{tile.y}: {e}')
                    # Create empty tile on error
                    try:
                        png_data = render_service.create_empty_tile()
                        with open(png_path, 'wb') as f:
                            f.write(png_data)
                        generated_tiles += 1
                    except:
                        pass
        
        # Final summary (matching existing pattern)
        self.stdout.write(self.style.SUCCESS(f"\n✅ PNG tile generation complete!"))
        self.stdout.write(f"   Total tiles: {total_tiles}")
        self.stdout.write(f"   Generated: {generated_tiles}")
        self.stdout.write(f"   Skipped (already existed): {skipped_tiles}")
        self.stdout.write(f"   Output folder: {out_dir}")
        
        # Generate sample URLs
        self.generate_sample_urls(data_type, min_zoom, max_zoom, bounds)

    def get_real_estate_bounds(self, data_type):
        """Get bounding box for real estate data (matching existing pattern)"""
        
        bounds = None
        
        if data_type in ['plots', 'combined']:
            plot_extent = Plot.objects.filter(is_active=True).aggregate(
                extent=Extent('location')
            )['extent']
            
            if plot_extent:
                bounds = {
                    'west': plot_extent[0],
                    'south': plot_extent[1],
                    'east': plot_extent[2],
                    'north': plot_extent[3]
                }
        
        if data_type in ['lands', 'combined']:
            land_extent = Land.objects.filter(is_active=True).aggregate(
                extent=Extent('location')
            )['extent']
            
            if land_extent:
                if bounds:
                    # Expand bounds to include both
                    bounds['west'] = min(bounds['west'], land_extent[0])
                    bounds['south'] = min(bounds['south'], land_extent[1])
                    bounds['east'] = max(bounds['east'], land_extent[2])
                    bounds['north'] = max(bounds['north'], land_extent[3])
                else:
                    bounds = {
                        'west': land_extent[0],
                        'south': land_extent[1],
                        'east': land_extent[2],
                        'north': land_extent[3]
                    }
        
        return bounds

    def generate_real_estate_mvt(self, data_type, z, x, y, zoom_level):
        """Generate MVT data for real estate (matching existing pattern)"""
        
        from django.contrib.gis.geos import Polygon
        
        # Get tile bounds
        bounds = mercantile.bounds(x, y, z)
        tile_bounds = Polygon.from_bbox([
            bounds.west, bounds.south,
            bounds.east, bounds.north
        ])
        
        try:
            if data_type == 'plots':
                return self.generate_plots_mvt(tile_bounds, z, x, y, zoom_level)
            elif data_type == 'lands':
                return self.generate_lands_mvt(tile_bounds, z, x, y, zoom_level)
            else:  # combined
                return self.generate_combined_real_estate_mvt(tile_bounds, z, x, y, zoom_level)
                
        except Exception as e:
            return None

    def generate_plots_mvt(self, tile_bounds, z, x, y, zoom_level):
        """Generate MVT for plots only"""
        
        import mapbox_vector_tile
        
        # Query plots in tile
        plots = Plot.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        )
        
        if not plots.exists():
            return None
        
        # Limit features at low zoom levels
        max_features = 50 if zoom_level < 10 else 200 if zoom_level < 12 else 1000
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
        
        # Encode MVT (matching existing pattern)
        layer_data = [{
            'name': 'plots',
            'features': plot_features,
            'version': 2,
            'extent': 4096
        }]
        
        return mapbox_vector_tile.encode(layer_data)

    def generate_lands_mvt(self, tile_bounds, z, x, y, zoom_level):
        """Generate MVT for lands only"""
        
        import mapbox_vector_tile
        
        # Query lands in tile
        lands = Land.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        )
        
        if not lands.exists():
            return None
        
        # Limit features at low zoom levels
        max_features = 50 if zoom_level < 10 else 200 if zoom_level < 12 else 1000
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

    def generate_combined_real_estate_mvt(self, tile_bounds, z, x, y, zoom_level):
        """Generate combined MVT with both plots and lands"""
        
        import mapbox_vector_tile
        
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
        max_features = 25 if zoom_level < 10 else 100 if zoom_level < 12 else 500
        plots = plots[:max_features]
        lands = lands[:max_features]
        
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
                            'type': 'plot'
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
                            'type': 'land'
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

    def mvt_to_png_real_estate(self, render_service, mvt_data, data_type, z, x, y):
        """Convert real estate MVT to PNG using existing TileRenderingService patterns"""
        
        import mapbox_vector_tile
        from PIL import Image, ImageDraw
        import io
        
        try:
            # Decode MVT data
            decoded_data = mapbox_vector_tile.decode(mvt_data)
            if not decoded_data:
                return render_service.create_empty_tile()
            
            # Create blank image (matching existing pattern)
            img = Image.new('RGBA', (256, 256), (255, 255, 255, 0))  # Transparent background
            draw = ImageDraw.Draw(img)
            
            features_drawn = 0
            
            # Draw features for each layer
            for layer_name, layer_data in decoded_data.items():
                features = layer_data.get('features', [])
                
                # Set color based on layer type
                if layer_name == 'plots':
                    color = (255, 120, 0, 200)      # Orange for plots
                    outline_color = (255, 120, 0, 255)
                else:  # lands
                    color = (0, 255, 0, 200)       # Green for lands
                    outline_color = (0, 255, 0, 255)
                
                # Draw each feature
                for feature in features:
                    if self.draw_point_feature(draw, feature, color, outline_color, z):
                        features_drawn += 1
            
            # Convert to PNG bytes (matching existing pattern)
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG', optimize=True)
            return img_buffer.getvalue()
            
        except Exception as e:
            return render_service.create_empty_tile()

    def draw_point_feature(self, draw, feature, fill_color, outline_color, zoom):
        """Draw a point feature on the image"""
        
        try:
            geometry = feature.get('geometry', {})
            if geometry.get('type') != 'Point':
                return False
            
            coordinates = geometry.get('coordinates', [])
            if len(coordinates) != 2:
                return False
            
            # Convert coordinates to pixel position
            # For MVT, coordinates are already in tile space (0-4096)
            # Convert to image space (0-256)
            pixel_x = int((coordinates[0] / 4096.0) * 256)
            pixel_y = int((coordinates[1] / 4096.0) * 256)
            
            # Adjust radius based on zoom level
            radius = 4 if zoom < 10 else 6 if zoom < 12 else 8 if zoom < 14 else 10
            
            # Draw circle marker (matching existing point rendering)
            draw.ellipse(
                [pixel_x - radius, pixel_y - radius, 
                 pixel_x + radius, pixel_y + radius],
                fill=fill_color,
                outline=outline_color,
                width=1
            )
            
            return True
            
        except Exception:
            return False

    def generate_sample_urls(self, data_type, min_zoom, max_zoom, bounds):
        """Generate sample URLs for testing (matching existing pattern)"""
        
        self.stdout.write(f"\n🔗 Sample PNG Tile URLs:")
        
        # Generate center coordinates
        center_lat = (bounds['north'] + bounds['south']) / 2
        center_lng = (bounds['east'] + bounds['west']) / 2
        
        # Test different zoom levels
        test_zooms = [min_zoom, (min_zoom + max_zoom) // 2, max_zoom]
        
        for zoom in test_zooms:
            tile = mercantile.tile(center_lng, center_lat, zoom)
            self.stdout.write(f"   Zoom {zoom}: /api/real-estate-tiles/{data_type}/{tile.z}/{tile.x}/{tile.y}.png")
        
        self.stdout.write(f"\n🧪 Test coordinates:")
        for zoom in test_zooms:
            tile = mercantile.tile(center_lng, center_lat, zoom)
            self.stdout.write(f"   {zoom}/{tile.x}/{tile.y} (lat: {center_lat:.4f}, lng: {center_lng:.4f})")