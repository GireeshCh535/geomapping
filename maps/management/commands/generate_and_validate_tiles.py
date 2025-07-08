from django.core.management.base import BaseCommand
from django.utils import timezone
from maps.models import City, DataLayer, VectorTileLayer
from maps.services import VectorTileService
import time
import os
import mapbox_vector_tile
import tempfile
from pathlib import Path
import mercantile

class Command(BaseCommand):
    help = 'Generate and validate vector tiles for all layers in a city'
    
    def add_arguments(self, parser):
        parser.add_argument('--city', required=True, help='City slug')
        parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=14, help='Maximum zoom level')
        parser.add_argument('--layer', help='Specific layer slug (optional)')
        parser.add_argument('--force', action='store_true', help='Force regeneration of existing tiles')
        parser.add_argument('--parallel', action='store_true', help='Generate tiles in parallel (if supported)')
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
            
            return True, "Valid MVT with " + ", ".join(validation_details) if validation_details else "Valid MVT"
            
        except Exception as e:
            return False, f"MVT validation error: {str(e)}"
    
    def generate_and_validate_layer_tiles(self, layer, min_zoom, max_zoom):
        """Generate and validate all tiles for a layer within zoom range"""
        tile_service = VectorTileService()
        
        bounds = tile_service._get_layer_bounds(layer)
        if not bounds:
            return {'error': 'No bounds available for layer'}
        
        total_tiles = 0
        validated_tiles = 0
        failed_tiles = 0
        validation_errors = []
        
        for zoom in range(min_zoom, max_zoom + 1):
            # Get tiles that intersect with layer bounds
            tiles = list(mercantile.tiles(
                bounds['west'], bounds['south'],
                bounds['east'], bounds['north'],
                zoom
            ))
            
            self.stdout.write(f"   🗺️  Zoom {zoom}: Processing {len(tiles)} tiles")
            zoom_tiles = 0
            
            for tile in tiles:
                try:
                    # Generate tile
                    mvt_data = tile_service.generate_tile(layer, tile.z, tile.x, tile.y)
                    if not mvt_data:
                        continue
                    
                    total_tiles += 1
                    zoom_tiles += 1
                    
                    # Validate tile
                    is_valid, validation_msg = self.validate_tile(mvt_data)
                    if not is_valid:
                        failed_tiles += 1
                        validation_errors.append(f"z{tile.z}/{tile.x}/{tile.y}: {validation_msg}")
                        continue
                    
                    validated_tiles += 1
                    
                    # Save valid tile
                    tile_dir = Path(f"media/tiles/{layer.city.slug}/{layer.slug}/{tile.z}/{tile.x}")
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    tile_path = tile_dir / f"{tile.y}.mvt"
                    
                    with open(tile_path, 'wb') as f:
                        f.write(mvt_data)
                    
                    # Log progress every 100 tiles
                    if zoom_tiles % 100 == 0:
                        self.stdout.write(f"      Generated {zoom_tiles} tiles...")
                    
                except Exception as e:
                    failed_tiles += 1
                    validation_errors.append(f"z{tile.z}/{tile.x}/{tile.y}: Generation error - {str(e)}")
            
            if zoom_tiles > 0:
                self.stdout.write(f"      ✅ Zoom {zoom}: Generated {zoom_tiles} tiles")
        
        return {
            'layer_id': layer.id,
            'tiles_generated': total_tiles,
            'tiles_validated': validated_tiles,
            'tiles_failed': failed_tiles,
            'validation_errors': validation_errors[:10],  # First 10 errors
            'status': 'success' if total_tiles > 0 else 'no_tiles',
            'zoom_range': {'min': min_zoom, 'max': max_zoom},
            'bounds': bounds
        }
    
    def handle(self, *args, **options):
        city_slug = options['city']
        min_zoom = options['min_zoom']
        max_zoom = options['max_zoom']
        layer_slug = options.get('layer')
        skip_validation = options.get('skip_validation', False)
        
        try:
            city = City.objects.get(slug=city_slug)
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            return
        
        # Validate zoom levels
        if min_zoom < 0 or max_zoom > 18 or min_zoom > max_zoom:
            self.stdout.write(self.style.ERROR(f"❌ Invalid zoom levels: {min_zoom}-{max_zoom}"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"🗺️  Generating tiles for {city.name}"))
        self.stdout.write(f"📊 Zoom levels: {min_zoom} to {max_zoom}")
        
        # Get layers to process
        layers = DataLayer.objects.filter(city=city, is_processed=True)
        if layer_slug:
            layers = layers.filter(slug=layer_slug)
            if not layers.exists():
                self.stdout.write(self.style.ERROR(f"❌ Layer not found: {layer_slug}"))
                return
        
        if not layers.exists():
            self.stdout.write(self.style.WARNING("⚠️  No processed layers found"))
            return
        
        self.stdout.write(f"📋 Processing {layers.count()} layers...")
        
        # Statistics
        total_tiles_generated = 0
        total_tiles_validated = 0
        total_tiles_failed = 0
        successful_layers = 0
        failed_layers = 0
        validation_errors = []
        
        start_time = time.time()
        
        for i, layer in enumerate(layers, 1):
            self.stdout.write(f"\n📂 [{i}/{layers.count()}] Processing: {layer.name}")
            self.stdout.write(f"   📊 Features: {layer.feature_count:,}")
            
            # Check if tiles already exist
            try:
                vector_tile_layer = VectorTileLayer.objects.get(layer=layer)
                if vector_tile_layer.is_generated and not options['force']:
                    self.stdout.write(f"   ✅ Tiles already exist (use --force to regenerate)")
                    successful_layers += 1
                    continue
            except VectorTileLayer.DoesNotExist:
                vector_tile_layer = None
            
            try:
                layer_start_time = time.time()
                
                # Generate and validate tiles for this layer
                result = self.generate_and_validate_layer_tiles(layer, min_zoom, max_zoom)
                
                layer_end_time = time.time()
                layer_duration = layer_end_time - layer_start_time
                
                if result.get('error'):
                    raise Exception(result['error'])
                
                # Update statistics
                total_tiles_generated += result['tiles_generated']
                total_tiles_validated += result['tiles_validated']
                total_tiles_failed += result['tiles_failed']
                validation_errors.extend([f"{layer.slug} {err}" for err in result.get('validation_errors', [])])
                
                # Update or create vector tile layer record
                if vector_tile_layer:
                    vector_tile_layer.min_zoom = min_zoom
                    vector_tile_layer.max_zoom = max_zoom
                    vector_tile_layer.is_generated = True
                    vector_tile_layer.total_tiles = result['tiles_validated']
                    vector_tile_layer.generated_at = timezone.now()
                    vector_tile_layer.save()
                else:
                    VectorTileLayer.objects.create(
                        layer=layer,
                        min_zoom=min_zoom,
                        max_zoom=max_zoom,
                        is_generated=True,
                        total_tiles=result['tiles_validated'],
                        generated_at=timezone.now()
                    )
                
                # Update layer status
                layer.tiles_generated = True
                layer.save()
                
                successful_layers += 1
                
                # Show layer summary
                self.stdout.write(
                    self.style.SUCCESS(
                        f"   ✅ Layer completed in {layer_duration:.1f}s"
                    )
                )
                self.stdout.write(f"      Generated: {result['tiles_generated']:,} tiles")
                self.stdout.write(f"      Validated: {result['tiles_validated']:,} tiles")
                self.stdout.write(f"      Failed: {result['tiles_failed']:,} tiles")
                
                # Show performance
                if result['tiles_generated'] > 0:
                    tiles_per_second = result['tiles_generated'] / layer_duration
                    self.stdout.write(f"      ⚡ Performance: {tiles_per_second:.1f} tiles/second")
                
            except Exception as e:
                failed_layers += 1
                self.stdout.write(
                    self.style.ERROR(f"   ❌ Layer failed: {str(e)}")
                )
                
                # Log detailed error for debugging
                import traceback
                self.stdout.write(f"   🔍 Error details: {traceback.format_exc()}")
        
        # Final summary
        end_time = time.time()
        total_duration = end_time - start_time
        
        self.stdout.write(f"\n📊 Generation Summary:")
        self.stdout.write(f"   ✅ Successful layers: {successful_layers}")
        self.stdout.write(f"   ❌ Failed layers: {failed_layers}")
        self.stdout.write(f"   🗺️  Total tiles generated: {total_tiles_generated:,}")
        self.stdout.write(f"   ✅ Tiles validated: {total_tiles_validated:,}")
        self.stdout.write(f"   ❌ Tiles failed validation: {total_tiles_failed:,}")
        self.stdout.write(f"   ⏱️  Total time: {total_duration:.1f}s")
        
        if total_tiles_generated > 0:
            avg_tiles_per_second = total_tiles_generated / total_duration
            self.stdout.write(f"   ⚡ Average performance: {avg_tiles_per_second:.1f} tiles/second")
        
        # Show validation errors if any
        if validation_errors:
            self.stdout.write(f"\n⚠️  Validation Errors:")
            for error in validation_errors[:10]:  # Show first 10 errors
                self.stdout.write(f"   - {error}")
            if len(validation_errors) > 10:
                self.stdout.write(f"   ... and {len(validation_errors) - 10} more errors")
        
        # Show next steps
        if successful_layers > 0:
            self.stdout.write(f"\n🎯 Next Steps:")
            self.stdout.write(f"   1. Test tiles: GET /api/tiles/{city_slug}/{{layer}}/{{z}}/{{x}}/{{y}}.mvt")
            self.stdout.write(f"   2. View layers: GET /api/cities/{city_slug}/layers/")
            self.stdout.write(f"   3. Check tile validation results above")
        
        if failed_layers > 0:
            self.stdout.write(f"\n⚠️  {failed_layers} layers failed to generate tiles")
            self.stdout.write("   Check layer data and try regenerating individual layers")
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Tile generation completed!")) 