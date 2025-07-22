# Create: maps/management/commands/generate_real_estate_png_tiles.py

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
    help = 'Generate and validate PNG tiles for real estate data (plots and lands)'

    def add_arguments(self, parser):
        parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=14, help='Maximum zoom level')
        parser.add_argument('--force', action='store_true', help='Force regeneration of existing tiles')
        parser.add_argument('--output-dir', type=str, default='media/real_estate_tiles_png', help='Output directory')
        parser.add_argument('--type', choices=['plots', 'lands', 'combined'], default='combined', help='Data type to generate')
        parser.add_argument('--mvt-source-dir', type=str, default='media/real_estate_tiles', help='Source directory for MVT tiles')

    def validate_png_tile(self, png_data):
        """
        Validate a PNG tile
        Returns (is_valid, details) tuple
        """
        try:
            if not png_data or len(png_data) == 0:
                return False, "Empty PNG data"
            
            # Try to load as image
            img = Image.open(io.BytesIO(png_data))
            
            # Check dimensions
            if img.size != (256, 256):
                return False, f"Invalid tile size: {img.size} (expected 256x256)"
            
            # Check mode
            if img.mode not in ['RGBA', 'RGB', 'L']:
                return False, f"Invalid image mode: {img.mode}"
            
            return True, f"Valid PNG tile ({img.mode}, {img.size})"
            
        except Exception as e:
            return False, f"PNG validation error: {str(e)}"

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

    def create_empty_tile(self):
        """Create a transparent empty tile"""
        img = Image.new('RGBA', (256, 256), (255, 255, 255, 0))
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG', optimize=True)
        return img_buffer.getvalue()

    def mvt_to_png(self, mvt_data, data_type, z):
        """Convert MVT data to PNG"""
        try:
            # Decode MVT data
            decoded_data = mapbox_vector_tile.decode(mvt_data)
            if not decoded_data:
                return self.create_empty_tile()
            
            # Create blank image
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
                    color = (0, 200, 0, 200)       # Green for lands
                    outline_color = (0, 200, 0, 255)
                
                # Draw each feature
                for feature in features:
                    if self.draw_point_feature(draw, feature, color, outline_color, z):
                        features_drawn += 1
            
            # If no features drawn, return empty tile
            if features_drawn == 0:
                return self.create_empty_tile()
            
            # Convert to PNG bytes
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG', optimize=True)
            return img_buffer.getvalue()
            
        except Exception as e:
            return self.create_empty_tile()

    def draw_point_feature(self, draw, feature, color, outline_color, zoom):
        """Draw a point feature on the image"""
        try:
            geometry = feature.get('geometry', {})
            if geometry.get('type') != 'Point':
                return False
            
            coordinates = geometry.get('coordinates', [])
            if len(coordinates) != 2:
                return False
            
            # Convert geographic coordinates to tile pixel coordinates
            # This is a simplified conversion - for production use proper projection
            x_pixel = int((coordinates[0] + 180) / 360 * 256)
            y_pixel = int((90 - coordinates[1]) / 180 * 256)
            
            # Ensure coordinates are within tile bounds
            if 0 <= x_pixel <= 256 and 0 <= y_pixel <= 256:
                # Draw point size based on zoom level
                radius = max(2, min(8, zoom - 5))
                
                # Draw filled circle
                draw.ellipse(
                    [(x_pixel - radius, y_pixel - radius), 
                     (x_pixel + radius, y_pixel + radius)],
                    fill=color,
                    outline=outline_color
                )
                return True
            
            return False
            
        except Exception:
            return False

    def generate_png_from_mvt(self, mvt_path, data_type, z, x, y):
        """Generate PNG from existing MVT file"""
        try:
            if not mvt_path.exists():
                return None
            
            with open(mvt_path, 'rb') as f:
                mvt_data = f.read()
            
            return self.mvt_to_png(mvt_data, data_type, z)
            
        except Exception as e:
            return None

    def generate_png_directly(self, data_type, z, x, y):
        """Generate PNG directly from database (fallback if no MVT)"""
        try:
            # Get tile bounds
            bounds = mercantile.bounds(x, y, z)
            tile_bounds = Polygon.from_bbox([
                bounds.west, bounds.south,
                bounds.east, bounds.north
            ])
            
            # Query data
            if data_type == 'plots':
                features = Plot.objects.filter(
                    location__intersects=tile_bounds,
                    is_active=True
                )[:100]  # Limit features
            elif data_type == 'lands':
                features = Land.objects.filter(
                    location__intersects=tile_bounds,
                    is_active=True
                )[:100]  # Limit features
            else:  # combined
                plot_features = Plot.objects.filter(
                    location__intersects=tile_bounds,
                    is_active=True
                )[:50]
                land_features = Land.objects.filter(
                    location__intersects=tile_bounds,
                    is_active=True
                )[:50]
                features = list(plot_features) + list(land_features)
            
            if not features:
                return self.create_empty_tile()
            
            # Create image
            img = Image.new('RGBA', (256, 256), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            
            for feature in features:
                # Convert world coordinates to tile pixel coordinates
                lat, lng = feature.location.y, feature.location.x
                
                # Simple tile coordinate conversion
                x_pixel = int((lng - bounds.west) / (bounds.east - bounds.west) * 256)
                y_pixel = int((bounds.north - lat) / (bounds.north - bounds.south) * 256)
                
                if 0 <= x_pixel <= 256 and 0 <= y_pixel <= 256:
                    # Set color based on feature type
                    if isinstance(feature, Plot):
                        color = (255, 120, 0, 200)      # Orange for plots
                        outline_color = (255, 120, 0, 255)
                    else:  # Land
                        color = (0, 200, 0, 200)       # Green for lands
                        outline_color = (0, 200, 0, 255)
                    
                    radius = max(2, min(8, z - 5))
                    
                    draw.ellipse(
                        [(x_pixel - radius, y_pixel - radius), 
                         (x_pixel + radius, y_pixel + radius)],
                        fill=color,
                        outline=outline_color
                    )
            
            # Convert to PNG bytes
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG', optimize=True)
            return img_buffer.getvalue()
            
        except Exception as e:
            return self.create_empty_tile()

    def generate_and_validate_png_tiles(self, data_type, min_zoom, max_zoom, output_dir, mvt_source_dir, force):
        """Generate and validate all PNG tiles for the specified data type within zoom range"""
        
        bounds = self.get_data_bounds(data_type)
        if not bounds:
            return {'error': f'No bounds available for {data_type}'}
        
        self.stdout.write(f"📊 Data bounds: {bounds}")
        
        total_tiles = 0
        validated_tiles = 0
        failed_tiles = 0
        validation_errors = []
        
        mvt_source_path = Path(mvt_source_dir)
        
        for zoom in range(min_zoom, max_zoom + 1):
            # Get tiles that intersect with data bounds
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'],
                zoom
            ))
            
            self.stdout.write(f"   🖼️  Zoom {zoom}: Processing {len(tiles)} PNG tiles")
            zoom_tiles = 0
            
            for tile in tiles:
                try:
                    # Check if PNG tile already exists and force is not set
                    png_dir = output_dir / data_type / str(tile.z) / str(tile.x)
                    png_path = png_dir / f'{tile.y}.png'
                    
                    if png_path.exists() and not force:
                        continue
                    
                    # Try to generate from MVT first
                    mvt_path = mvt_source_path / data_type / str(tile.z) / str(tile.x) / f'{tile.y}.mvt'
                    
                    if mvt_path.exists():
                        png_data = self.generate_png_from_mvt(mvt_path, data_type, tile.z, tile.x, tile.y)
                    else:
                        # Fallback: generate directly from database
                        png_data = self.generate_png_directly(data_type, tile.z, tile.x, tile.y)
                    
                    if not png_data:
                        continue
                    
                    total_tiles += 1
                    zoom_tiles += 1
                    
                    # Validate PNG
                    is_valid, validation_msg = self.validate_png_tile(png_data)
                    if not is_valid:
                        failed_tiles += 1
                        validation_errors.append(f"z{tile.z}/{tile.x}/{tile.y}: {validation_msg}")
                        continue
                    
                    validated_tiles += 1
                    
                    # Save valid PNG tile
                    png_dir.mkdir(parents=True, exist_ok=True)
                    
                    with open(png_path, 'wb') as f:
                        f.write(png_data)
                    
                    # Log progress every 50 tiles
                    if zoom_tiles % 50 == 0:
                        self.stdout.write(f"      Generated {zoom_tiles} PNG tiles...")
                    
                except Exception as e:
                    failed_tiles += 1
                    validation_errors.append(f"z{tile.z}/{tile.x}/{tile.y}: Generation error - {str(e)}")
            
            if zoom_tiles > 0:
                self.stdout.write(f"      ✅ Zoom {zoom}: Generated {zoom_tiles} PNG tiles")
        
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
        mvt_source_dir = Path(options['mvt_source_dir'])
        
        # Validate zoom levels
        if min_zoom < 0 or max_zoom > 20 or min_zoom > max_zoom:
            self.stdout.write(self.style.ERROR('❌ Invalid zoom levels'))
            return
        
        self.stdout.write(self.style.SUCCESS('🖼️  Starting Real Estate PNG Tile Generation with Validation'))
        self.stdout.write(f'📊 Configuration:')
        self.stdout.write(f'   Data type: {data_type}')
        self.stdout.write(f'   Zoom levels: {min_zoom} to {max_zoom}')
        self.stdout.write(f'   Output: {output_dir}')
        self.stdout.write(f'   MVT source: {mvt_source_dir}')
        self.stdout.write(f'   Force overwrite: {force}')
        
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
        
        # Check MVT source directory
        if mvt_source_dir.exists():
            self.stdout.write(f'✅ MVT source directory found: {mvt_source_dir}')
        else:
            self.stdout.write(f'⚠️  MVT source directory not found: {mvt_source_dir}')
            self.stdout.write(f'   Will generate PNG tiles directly from database')
        
        # Statistics
        total_tiles_generated = 0
        total_tiles_validated = 0
        total_tiles_failed = 0
        all_validation_errors = []
        
        start_time = time.time()
        
        # Generate PNG tiles
        self.stdout.write(f"\n🖼️  Generating PNG tiles for: {data_type}")
        result = self.generate_and_validate_png_tiles(
            data_type, min_zoom, max_zoom, output_dir, mvt_source_dir, force
        )
        
        total_tiles_generated += result['tiles_generated']
        total_tiles_validated += result['tiles_validated']
        total_tiles_failed += result['tiles_failed']
        all_validation_errors.extend(result['validation_errors'])
        
        # Final statistics
        end_time = time.time()
        duration = end_time - start_time
        
        self.stdout.write(f'\n📊 PNG GENERATION SUMMARY')
        self.stdout.write('=' * 50)
        self.stdout.write(f'✅ PNG tiles generated: {total_tiles_generated:,}')
        self.stdout.write(f'✅ PNG tiles validated: {total_tiles_validated:,}')
        self.stdout.write(f'❌ PNG tiles failed: {total_tiles_failed:,}')
        self.stdout.write(f'⏱️  Duration: {duration:.2f} seconds')
        
        if total_tiles_generated > 0:
            self.stdout.write(f'🚀 Speed: {total_tiles_generated / duration:.1f} PNG tiles/second')
        
        # Show validation errors (first 5)
        if all_validation_errors:
            self.stdout.write(f'\n❌ VALIDATION ERRORS (showing first 5):')
            for i, error in enumerate(all_validation_errors[:5], 1):
                self.stdout.write(f'   {i}. {error}')
            
            if len(all_validation_errors) > 5:
                self.stdout.write(f'   ... and {len(all_validation_errors) - 5} more errors')
        
        if total_tiles_generated > 0:
            self.stdout.write(self.style.SUCCESS('\n✅ Real Estate PNG tile generation completed successfully!'))
            
            # Sample URLs
            self.stdout.write(f'\n🔗 Sample PNG tile URLs:')
            self.stdout.write(f'   /api/real-estate-tiles/{data_type}/10/512/512.png')
        else:
            self.stdout.write(self.style.WARNING('\n⚠️  No PNG tiles were generated. Check your data and bounds.'))