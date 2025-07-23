# maps/management/commands/generate_real_estate_png_tiles.py
# FIXED VERSION - Better feature limits and rendering

import os
import time
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.gis.db.models import Extent
from django.contrib.gis.geos import Polygon
from maps.models import Plot, Land
import mercantile
import mapbox_vector_tile
from PIL import Image, ImageDraw
import io

class Command(BaseCommand):
    help = 'Generate PNG tiles for real estate data (plots and lands) - FIXED'

    def add_arguments(self, parser):
        parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=14, help='Maximum zoom level')
        parser.add_argument('--overwrite', action='store_true', help='Overwrite existing tiles')
        parser.add_argument('--output-dir', type=str, default='media/real_estate_tiles_png', help='Output directory')
        parser.add_argument('--type', choices=['plots', 'lands', 'combined'], default='combined', help='Data type to generate')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🏡 Starting FIXED Real Estate PNG Tile Generation'))
        
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
                    # Generate PNG data directly (no MVT conversion)
                    png_data = self.generate_real_estate_png(data_type, tile.z, tile.x, tile.y, zoom)
                    
                    if not png_data:
                        # Save empty/transparent PNG
                        png_data = self.create_empty_tile()
                    
                    # Save PNG file
                    with open(png_path, 'wb') as f:
                        f.write(png_data)
                    
                    generated_tiles += 1
                    
                    # Progress update
                    if generated_tiles % 100 == 0:
                        self.stdout.write(f"   Generated {generated_tiles} PNGs so far...")
                        
                except Exception as e:
                    self.stdout.write(f'   ❌ Error generating PNG tile {tile.z}/{tile.x}/{tile.y}: {e}')
                    # Create empty tile on error
                    try:
                        png_data = self.create_empty_tile()
                        with open(png_path, 'wb') as f:
                            f.write(png_data)
                        generated_tiles += 1
                    except:
                        pass
        
        # Final summary
        self.stdout.write(self.style.SUCCESS(f"\n✅ FIXED PNG tile generation complete!"))
        self.stdout.write(f"   Total tiles: {total_tiles}")
        self.stdout.write(f"   Generated: {generated_tiles}")
        self.stdout.write(f"   Skipped (already existed): {skipped_tiles}")
        self.stdout.write(f"   Output folder: {out_dir}")
        
        # Generate sample URLs
        self.generate_sample_urls(data_type, min_zoom, max_zoom, bounds)

    def get_real_estate_bounds(self, data_type):
        """Get bounding box for real estate data"""
        
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

    def generate_real_estate_png(self, data_type, z, x, y, zoom_level):
        """Generate PNG data for real estate - FIXED LIMITS"""
        
        from django.contrib.gis.geos import Polygon
        
        # Get tile bounds
        bounds = mercantile.bounds(x, y, z)
        tile_bounds = Polygon.from_bbox([
            bounds.west, bounds.south,
            bounds.east, bounds.north
        ])
        
        # Query plots and lands in tile
        plots = Plot.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        ) if data_type in ['plots', 'combined'] else Plot.objects.none()
        
        lands = Land.objects.filter(
            location__intersects=tile_bounds,
            is_active=True
        ) if data_type in ['lands', 'combined'] else Land.objects.none()
        
        if not plots.exists() and not lands.exists():
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
        
        # Apply limits
        plots = plots[:max_features]
        lands = lands[:max_features]
        
        # Create image
        tile_size = 256
        img = Image.new('RGBA', (tile_size, tile_size), (0, 0, 0, 0))  # Transparent background
        draw = ImageDraw.Draw(img)
        
        features_drawn = 0
        
        # Draw plots (orange)
        if plots.exists():
            for plot in plots:
                try:
                    pixel_x, pixel_y = self.latlng_to_pixel(
                        plot.location.y, plot.location.x,
                        bounds, tile_size
                    )
                    
                    # Adjust point size based on zoom level
                    if zoom_level <= 6:
                        radius = 4
                    elif zoom_level <= 10:
                        radius = 6
                    else:
                        radius = 8
                    
                    # Draw orange circle for plots
                    color = (255, 120, 0, 200)      # Orange with transparency
                    outline_color = (255, 120, 0, 255)  # Solid orange outline
                    
                    draw.ellipse(
                        [pixel_x - radius, pixel_y - radius, 
                         pixel_x + radius, pixel_y + radius],
                        fill=color,
                        outline=outline_color,
                        width=2
                    )
                    features_drawn += 1
                    
                except Exception:
                    continue
        
        # Draw lands (green)
        if lands.exists():
            for land in lands:
                try:
                    pixel_x, pixel_y = self.latlng_to_pixel(
                        land.location.y, land.location.x,
                        bounds, tile_size
                    )
                    
                    # Adjust point size based on zoom level
                    if zoom_level <= 6:
                        radius = 4
                    elif zoom_level <= 10:
                        radius = 6
                    else:
                        radius = 8
                    
                    # Draw green circle for lands
                    color = (0, 255, 0, 200)      # Green with transparency
                    outline_color = (0, 255, 0, 255)  # Solid green outline
                    
                    draw.ellipse(
                        [pixel_x - radius, pixel_y - radius, 
                         pixel_x + radius, pixel_y + radius],
                        fill=color,
                        outline=outline_color,
                        width=2
                    )
                    features_drawn += 1
                    
                except Exception:
                    continue
        
        if features_drawn == 0:
            return None
        
        # Convert to PNG bytes
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG', optimize=True)
        return img_buffer.getvalue()

    def latlng_to_pixel(self, lat, lng, bounds, tile_size):
        """Convert lat/lng to pixel coordinates within tile"""
        
        # Calculate relative position within tile bounds
        x_ratio = (lng - bounds.west) / (bounds.east - bounds.west)
        y_ratio = (bounds.north - lat) / (bounds.north - bounds.south)  # Flip Y axis
        
        # Convert to pixel coordinates
        pixel_x = int(x_ratio * tile_size)
        pixel_y = int(y_ratio * tile_size)
        
        # Clamp to tile boundaries
        pixel_x = max(0, min(tile_size - 1, pixel_x))
        pixel_y = max(0, min(tile_size - 1, pixel_y))
        
        return pixel_x, pixel_y

    def create_empty_tile(self):
        """Create empty transparent PNG tile"""
        img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG', optimize=True)
        return img_buffer.getvalue()

    def generate_sample_urls(self, data_type, min_zoom, max_zoom, bounds):
        """Generate sample URLs for testing"""
        
        self.stdout.write(f'\n📋 Sample URLs for testing:')
        
        # Calculate center tile for middle zoom level
        center_zoom = (min_zoom + max_zoom) // 2
        center_lng = (bounds['west'] + bounds['east']) / 2
        center_lat = (bounds['south'] + bounds['north']) / 2
        
        # Get tile containing center point
        center_tile = mercantile.tile(center_lng, center_lat, center_zoom)
        
        # Generate sample URLs
        sample_urls = [
            f'http://localhost:8000/api/real-estate-tiles/{data_type}/{center_zoom}/{center_tile.x}/{center_tile.y}.png',
            f'http://localhost:8000/api/real-estate-tiles/{data_type}/{min_zoom}/{center_tile.x >> (center_zoom - min_zoom)}/{center_tile.y >> (center_zoom - min_zoom)}.png',
            f'http://localhost:8000/api/real-estate-tiles/{data_type}/{max_zoom}/{center_tile.x << (max_zoom - center_zoom)}/{center_tile.y << (max_zoom - center_zoom)}.png'
        ]
        
        for url in sample_urls:
            self.stdout.write(f'   {url}')
        
        self.stdout.write(f'\n📍 Data center: {center_lat:.4f}, {center_lng:.4f}')
        self.stdout.write(f'📊 Bounds: {bounds}')
        
        # Show file locations
        self.stdout.write(f'\n📁 Tile files location:')
        out_dir = os.path.join(self.options.get('output_dir', 'media/real_estate_tiles_png'), data_type)
        self.stdout.write(f'   Directory: {out_dir}')
        self.stdout.write(f'   Pattern: {center_zoom}_{center_tile.x}_{center_tile.y}.png')