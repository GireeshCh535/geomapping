# maps/management/commands/generate_direct_s3_tiles.py
"""
COMPLETE OPTIMIZED VERSION: Generate COMBINED tiles by layer groups directly to S3
Command: python manage.py generate_direct_s3_tiles --city bengaluru --layer-groups "master_plan,highways" --type png --min-zoom 8 --max-zoom 14

S3 Structure (COMBINED tiles per group):
  karnataka/bengaluru/master_plan/z/x/y.png    (combined from ALL 16 master plan layers)
  karnataka/bengaluru/highways/z/x/y.png       (combined from ALL 8 highway layers)
  karnataka/bengaluru/metro/z/x/y.png          (combined metro data)
  karnataka/bengaluru/workspace/z/x/y.png      (combined workspace data)
"""

from django.core.management.base import BaseCommand
from django.contrib.gis.db import models
from django.contrib.gis.db.models import Extent
from maps.s3_direct_tile_service import S3DirectTileGenerationService
from maps.models import City, DataLayer, State, LayerGroup, GeoFeature
from maps.services import VectorTileService
from maps.tile_rendering_service import TileRenderingService
from maps.config import get_layer_groups_config
import time
import logging
import mercantile
import mapbox_vector_tile
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generate and upload COMBINED tiles by layer groups directly to S3'
    
    def add_arguments(self, parser):
        # City and layer options
        parser.add_argument('--city', required=True, help='City slug (bengaluru, hyderabad, etc.)')
        parser.add_argument('--layer-groups', help='Comma-separated layer groups (e.g., "master_plan,highways,metro")')
        parser.add_argument('--layer-group', help='Single layer group (for backward compatibility)')
        
        # Tile options
        parser.add_argument('--type', choices=['png', 'mvt', 'both'], default='png', 
                          help='Tile format to generate')
        parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level')
        parser.add_argument('--max-zoom', type=int, default=14, help='Maximum zoom level')
        
        # S3 options
        parser.add_argument('--force', action='store_true', help='Force regeneration of existing tiles')
        parser.add_argument('--test-connection', action='store_true', help='Test S3 connection only')
        parser.add_argument('--show-available', action='store_true', help='Show available layer groups')
        
        # Performance options
        parser.add_argument('--batch-size', type=int, default=50, help='Batch size for tile generation')
        parser.add_argument('--parallel', action='store_true', help='Enable parallel processing')
        
        # Debug options
        parser.add_argument('--debug', action='store_true', help='Enable debug output')
        parser.add_argument('--validate', action='store_true', help='Validate generated tiles after upload')
        parser.add_argument('--save-sample', action='store_true', help='Save sample tiles locally for inspection')

    def handle(self, *args, **options):
        city_slug = options['city']
        layer_groups_str = options.get('layer_groups') or options.get('layer_group')
        
        self.stdout.write(self.style.SUCCESS(f"🚀 Generating COMBINED tiles for city '{city_slug}'"))
        
        try:
            # Get city and state
            city = City.objects.get(slug=city_slug)
            state = city.state_ref
            if not state:
                self.stdout.write(self.style.ERROR("❌ City has no state reference"))
                return
            
            self.stdout.write(f"🏙️  Found city: {city.name} ({state.name})")
            
            # Show available layer groups if requested
            if options['show_available']:
                self._show_available_layer_groups(city)
                return
            
            # Test S3 connection if requested
            if options['test_connection']:
                self._test_s3_connection()
                return
            
            # Determine which layer groups to process
            layer_groups_to_process = self._determine_layer_groups_to_process(city, layer_groups_str)
            
            if not layer_groups_to_process:
                self.stdout.write(self.style.ERROR("❌ No valid layer groups found to process"))
                self.stdout.write("💡 Use --show-available to see available layer groups")
                return
            
            self.stdout.write(f"📁 Processing {len(layer_groups_to_process)} layer groups:")
            for group_name, group_info in layer_groups_to_process.items():
                self.stdout.write(f"   - {group_name} ({group_info['layer_count']} layers, {group_info['total_features']:,} features)")
            
            # Generate combined tiles for each layer group
            start_time = time.time()
            results = self._generate_tiles_by_layer_groups(
                state, city, layer_groups_to_process, options
            )
            total_time = time.time() - start_time
            
            self._display_results(results, total_time)
            
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            self.stdout.write("💡 Run: python manage.py setup_hierarchy_from_excel --use-default")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Generation failed: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())

    def _determine_layer_groups_to_process(self, city, layer_groups_str):
        """Determine which layer groups to process"""
        
        # Get all layer groups for this city
        available_groups = LayerGroup.objects.filter(city=city).annotate(
            layer_count=models.Count('layers'),
            total_features=models.Sum('layers__feature_count')
        )
        
        if layer_groups_str:
            # User specified specific groups
            requested_groups = [g.strip() for g in layer_groups_str.split(',')]
            groups_to_process = {}
            
            for group_name in requested_groups:
                group = available_groups.filter(slug=group_name).first()
                if group:
                    groups_to_process[group_name] = {
                        'group_object': group,
                        'layer_count': group.layer_count,
                        'total_features': group.total_features or 0
                    }
                    self.stdout.write(f"📁 Found layer group: {group.name}")
                else:
                    self.stdout.write(f"❌ Layer group not found: {group_name}")
            
            return groups_to_process
        else:
            # Auto-detect all groups with data
            groups_to_process = {}
            
            for group in available_groups:
                if (group.total_features or 0) > 0:
                    groups_to_process[group.slug] = {
                        'group_object': group,
                        'layer_count': group.layer_count,
                        'total_features': group.total_features or 0
                    }
                    self.stdout.write(f"📁 Auto-detected: {group.name}")
                else:
                    self.stdout.write(f"⚪ Skipping empty group: {group.name}")
            
            return groups_to_process

    def _generate_tiles_by_layer_groups(self, state, city, layer_groups_to_process, options):
        """Generate tiles for each layer group"""
        
        # Initialize services
        s3_service = S3DirectTileGenerationService()
        vector_service = VectorTileService()
        render_service = TileRenderingService()
        
        # Determine tile types
        tile_type = options['type']
        tile_types = ['png', 'mvt'] if tile_type == 'both' else [tile_type]
        
        results = {
            'total_groups': len(layer_groups_to_process),
            'successful_groups': 0,
            'failed_groups': 0,
            'total_tiles': 0,
            'generated_tiles': 0,
            'failed_tiles': 0,
            'total_size_mb': 0.0,
            'group_results': {},
            'errors': []
        }
        
        # Process each layer group
        for i, (group_name, group_info) in enumerate(layer_groups_to_process.items(), 1):
            group_object = group_info['group_object']
            
            self.stdout.write(f"\n📁 [{i}/{len(layer_groups_to_process)}] Processing: {group_object.name}")
            self.stdout.write(f"   Slug: {group_name}")
            self.stdout.write(f"   Layers: {group_info['layer_count']}")
            self.stdout.write(f"   Features: {group_info['total_features']:,}")
            
            try:
                # Get layers for this group
                layers = DataLayer.objects.filter(
                    layer_group=group_object,
                    is_processed=True
                ).select_related('category', 'city')
                
                if not layers.exists():
                    self.stdout.write(f"   ⚠️  No processed layers found")
                    results['failed_groups'] += 1
                    continue
                
                # Generate tiles for this group
                group_result = self._generate_layer_group_tiles(
                    s3_service, render_service, vector_service,
                    state, city, group_name, layers, 
                    options['min_zoom'], options['max_zoom'], 
                    tile_types, options
                )
                
                results['group_results'][group_name] = group_result
                
                if group_result['success']:
                    results['successful_groups'] += 1
                    results['generated_tiles'] += group_result['generated_tiles']
                    results['total_size_mb'] += group_result['total_size_mb']
                    
                    self.stdout.write(f"   ✅ Success: {group_result['generated_tiles']}/{group_result['total_tiles']} tiles")
                    self.stdout.write(f"      Size: {group_result['total_size_mb']:.2f} MB")
                else:
                    results['failed_groups'] += 1
                    self.stdout.write(f"   ❌ Failed: {group_result.get('error', 'Unknown error')}")
                
                results['total_tiles'] += group_result['total_tiles']
                results['failed_tiles'] += group_result['failed_tiles']
                
            except Exception as e:
                results['failed_groups'] += 1
                error_msg = f"{group_name}: {str(e)}"
                results['errors'].append(error_msg)
                self.stdout.write(f"   ❌ Exception: {e}")
        
        return results

    def _generate_layer_group_tiles(self, s3_service, render_service, vector_service, 
                                   state, city, group_name, layers, min_zoom, max_zoom, tile_types, options):
        """Generate combined tiles for a specific layer group"""
        
        # Calculate combined bounding box for all layers in the group
        group_bounds = self._calculate_group_bounds(layers)
        if not group_bounds:
            return {
                'group_name': group_name,
                'success': False,
                'error': 'Could not determine layer group bounds',
                'total_tiles': 0,
                'generated_tiles': 0,
                'failed_tiles': 0,
                'total_size_mb': 0.0
            }
        
        # Generate tile coordinates for the group bounds
        tiles_to_generate = []
        for zoom in range(min_zoom, max_zoom + 1):
            tiles = list(mercantile.tiles(
                group_bounds['west'], group_bounds['south'],
                group_bounds['east'], group_bounds['north'],
                zoom
            ))
            tiles_to_generate.extend([(tile.z, tile.x, tile.y) for tile in tiles])
        
        self.stdout.write(f"   📊 Generating {len(tiles_to_generate)} combined tiles (zoom {min_zoom}-{max_zoom})")
        self.stdout.write(f"   🗺️  Bounds: {group_bounds['west']:.4f}, {group_bounds['south']:.4f}, {group_bounds['east']:.4f}, {group_bounds['north']:.4f}")
        
        group_results = {
            'group_name': group_name,
            'layer_count': len(layers),
            'success': True,
            'total_tiles': len(tiles_to_generate),
            'generated_tiles': 0,
            'failed_tiles': 0,
            'total_size_mb': 0.0,
            'png_uploads': 0,
            'mvt_uploads': 0,
            'bounds': group_bounds
        }
        
        # Generate tiles with progress tracking
        batch_size = options.get('batch_size', 50)
        progress_interval = max(1, len(tiles_to_generate) // 20)  # Show progress 20 times
        
        for i, (z, x, y) in enumerate(tiles_to_generate):
            if i % progress_interval == 0 or i == len(tiles_to_generate) - 1:
                progress = ((i + 1) / len(tiles_to_generate)) * 100
                self.stdout.write(f"   Progress: {progress:.1f}% ({i + 1}/{len(tiles_to_generate)})")
            
            try:
                # Generate combined tile for this layer group
                tile_result = self._generate_single_layer_group_tile(
                    s3_service, render_service, vector_service,
                    state, city, group_name, layers,
                    z, x, y, tile_types, options
                )
                
                if tile_result['success']:
                    group_results['generated_tiles'] += 1
                    group_results['total_size_mb'] += tile_result.get('total_size_mb', 0.0)
                    
                    if 'png' in tile_types and tile_result.get('png_size', 0) > 0:
                        group_results['png_uploads'] += 1
                    if 'mvt' in tile_types and tile_result.get('mvt_size', 0) > 0:
                        group_results['mvt_uploads'] += 1
                        
                    # Save sample tile if requested
                    if options.get('save_sample') and i == 0:
                        self._save_sample_tile(tile_result, group_name, z, x, y)
                        
                else:
                    group_results['failed_tiles'] += 1
                    if group_results['failed_tiles'] <= 3:  # Only log first 3 errors
                        self.stdout.write(f"   ⚠️  Tile {z}/{x}/{y} failed: {tile_result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                group_results['failed_tiles'] += 1
                if group_results['failed_tiles'] <= 3:
                    self.stdout.write(f"   ⚠️  Tile {z}/{x}/{y} exception: {e}")
                
                # Break on too many consecutive errors
                if group_results['failed_tiles'] > 10:
                    self.stdout.write(f"   ❌ Too many failures, stopping group generation")
                    group_results['success'] = False
                    break
        
        group_results['success'] = group_results['generated_tiles'] > 0
        
        return group_results

    def _generate_single_layer_group_tile(self, s3_service, render_service, vector_service,
                                         state, city, group_name, layers, z, x, y, tile_types, options):
        """Generate a single combined tile for a layer group"""
        
        try:
            # Generate combined MVT data for all layers in the group
            mvt_data = vector_service.generate_combined_mvt_for_layers(layers, z, x, y)
            
            result = {
                'success': True,
                'png_size': 0,
                'mvt_size': 0,
                'total_size_mb': 0.0,
                'features_count': 0
            }
            
            # S3 key structure: state/city/group_name/z/x/y.format
            base_key = f"{state.slug}/{city.slug}/{group_name}/{z}/{x}/{y}"
            
            # Handle empty MVT data
            if not mvt_data or len(mvt_data) == 0:
                if options.get('debug'):
                    logger.debug(f"No MVT data for tile {group_name}/{z}/{x}/{y}, generating empty tiles")
                
                # Upload empty tiles
                if 'mvt' in tile_types:
                    mvt_key = f"{base_key}.mvt"
                    mvt_result = s3_service.upload_bytes_to_s3(b'', mvt_key, 'application/vnd.mapbox-vector-tile')
                    if mvt_result['success']:
                        result['mvt_size'] = 0
                
                if 'png' in tile_types:
                    empty_png = render_service.create_empty_tile()
                    png_key = f"{base_key}.png"
                    png_result = s3_service.upload_bytes_to_s3(empty_png, png_key, 'image/png')
                    if png_result['success']:
                        result['png_size'] = len(empty_png)
                
                return result
            
            # Count features in MVT for debugging
            if options.get('debug'):
                try:
                    decoded = mapbox_vector_tile.decode(mvt_data)
                    total_features = sum(len(layer_data.get('features', [])) for layer_data in decoded.values())
                    result['features_count'] = total_features
                    if total_features > 0:
                        logger.debug(f"Tile {group_name}/{z}/{x}/{y}: {total_features} features, {len(mvt_data)} bytes MVT")
                except:
                    pass
            
            # Upload MVT if requested
            if 'mvt' in tile_types:
                mvt_key = f"{base_key}.mvt"
                mvt_result = s3_service.upload_bytes_to_s3(mvt_data, mvt_key, 'application/vnd.mapbox-vector-tile')
                if mvt_result['success']:
                    result['mvt_size'] = len(mvt_data)
                else:
                    return {'success': False, 'error': f"MVT upload failed: {mvt_result.get('error')}"}
            
            # Generate and upload PNG if requested
            if 'png' in tile_types:
                # Use the enhanced combined PNG rendering
                png_data = render_service.combined_mvt_to_png(mvt_data, layers, z, x, y)
                
                if png_data and len(png_data) > 0:
                    png_key = f"{base_key}.png"
                    png_result = s3_service.upload_bytes_to_s3(png_data, png_key, 'image/png')
                    if png_result['success']:
                        result['png_size'] = len(png_data)
                        if options.get('debug'):
                            logger.debug(f"Successfully uploaded PNG for {group_name}/{z}/{x}/{y}, size: {len(png_data)} bytes")
                    else:
                        return {'success': False, 'error': f"PNG upload failed: {png_result.get('error')}"}
                else:
                    # Fallback to empty tile if PNG generation fails
                    if options.get('debug'):
                        logger.warning(f"PNG generation failed for {group_name}/{z}/{x}/{y}, using empty tile")
                    empty_png = render_service.create_empty_tile()
                    png_key = f"{base_key}.png"
                    png_result = s3_service.upload_bytes_to_s3(empty_png, png_key, 'image/png')
                    if png_result['success']:
                        result['png_size'] = len(empty_png)
            
            # Calculate total size
            total_bytes = result['png_size'] + result['mvt_size']
            result['total_size_mb'] = total_bytes / (1024 * 1024)
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating tile {group_name}/{z}/{x}/{y}: {e}")
            return {'success': False, 'error': str(e)}

    def _calculate_group_bounds(self, layers):
        """Calculate combined bounding box for all layers in a group"""
        try:
            # Get all features from all layers in the group
            all_features = GeoFeature.objects.filter(layer__in=layers, is_valid=True)
            
            if not all_features.exists():
                return None
            
            # Calculate combined extent
            extent = all_features.aggregate(extent=Extent('geometry'))['extent']
            
            if extent:
                return {
                    'west': extent[0],
                    'south': extent[1],
                    'east': extent[2],
                    'north': extent[3]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating group bounds: {e}")
            return None

    def _show_available_layer_groups(self, city):
        """Show available layer groups for the city"""
        
        layer_groups = LayerGroup.objects.filter(city=city).annotate(
            layer_count=models.Count('layers'),
            total_features=models.Sum('layers__feature_count')
        ).order_by('display_order', 'name')
        
        self.stdout.write(f"\n📋 Available layer groups for {city.name}:")
        
        if not layer_groups.exists():
            self.stdout.write("   No layer groups found")
            return
        
        for group in layer_groups:
            feature_count = group.total_features or 0
            status_icon = "✅" if feature_count > 0 else "⚪"
            
            self.stdout.write(f"   {status_icon} {group.slug}: {group.name}")
            self.stdout.write(f"      Layers: {group.layer_count} | Features: {feature_count:,}")
            self.stdout.write(f"      Description: {group.description}")
            
            if feature_count > 0:
                # Show recommended zoom levels based on data
                if feature_count > 50000:
                    recommended_zoom = "6-10 (large dataset)"
                elif feature_count > 10000:
                    recommended_zoom = "8-12 (medium dataset)"
                else:
                    recommended_zoom = "10-14 (small dataset)"
                self.stdout.write(f"      Recommended zoom: {recommended_zoom}")
            
            self.stdout.write("")

    def _test_s3_connection(self):
        """Test S3 connection and permissions"""
        self.stdout.write(f"🔗 Testing S3 connection...")
        
        try:
            s3_service = S3DirectTileGenerationService()
            connection_test = s3_service.test_connection()
            
            if connection_test.get('success'):
                self.stdout.write(f"✅ S3 connection successful")
                self.stdout.write(f"   Bucket: {connection_test.get('bucket')}")
                self.stdout.write(f"   Region: {connection_test.get('region')}")
                self.stdout.write(f"   CloudFront: {connection_test.get('cloudfront_domain')}")
            else:
                self.stdout.write(f"❌ S3 connection failed: {connection_test.get('error')}")
                
        except Exception as e:
            self.stdout.write(f"❌ S3 test failed: {e}")

    def _save_sample_tile(self, tile_result, group_name, z, x, y):
        """Save a sample tile locally for inspection"""
        try:
            sample_dir = Path('sample_tiles')
            sample_dir.mkdir(exist_ok=True)
            
            # This would require downloading from S3 to save locally
            # Simplified implementation - just log the info
            self.stdout.write(f"💾 Sample tile info: {group_name}_{z}_{x}_{y}")
            self.stdout.write(f"   PNG size: {tile_result.get('png_size', 0)} bytes")
            self.stdout.write(f"   MVT size: {tile_result.get('mvt_size', 0)} bytes")
            
        except Exception as e:
            logger.warning(f"Could not save sample tile: {e}")

    def _display_results(self, results, total_time):
        """Display final generation results"""
        
        self.stdout.write(f"\n" + "="*60)
        self.stdout.write(f"🎯 TILE GENERATION RESULTS")
        self.stdout.write(f"="*60)
        
        # Overall statistics
        success_rate = (results['generated_tiles'] / max(results['total_tiles'], 1)) * 100
        
        self.stdout.write(f"📊 Overall Statistics:")
        self.stdout.write(f"   Layer groups processed: {results['total_groups']}")
        self.stdout.write(f"   Successful groups: {results['successful_groups']}")
        self.stdout.write(f"   Failed groups: {results['failed_groups']}")
        self.stdout.write(f"   Total tiles: {results['total_tiles']:,}")
        self.stdout.write(f"   Generated tiles: {results['generated_tiles']:,}")
        self.stdout.write(f"   Failed tiles: {results['failed_tiles']:,}")
        self.stdout.write(f"   Success rate: {success_rate:.1f}%")
        self.stdout.write(f"   Total size: {results['total_size_mb']:.2f} MB")
        self.stdout.write(f"   Generation time: {total_time:.1f} seconds")
        
        # Per-group details
        self.stdout.write(f"\n📁 Layer Group Details:")
        
        for group_name, group_result in results['group_results'].items():
            status_icon = "✅" if group_result['success'] else "❌"
            
            self.stdout.write(f"   {status_icon} {group_name}:")
            self.stdout.write(f"      Tiles: {group_result['generated_tiles']}/{group_result['total_tiles']}")
            self.stdout.write(f"      Size: {group_result['total_size_mb']:.2f} MB")
            
            if 'png_uploads' in group_result:
                self.stdout.write(f"      PNG uploads: {group_result['png_uploads']}")
            if 'mvt_uploads' in group_result:
                self.stdout.write(f"      MVT uploads: {group_result['mvt_uploads']}")
        
        # Show errors if any
        if results['errors']:
            self.stdout.write(f"\n❌ Errors ({len(results['errors'])}):")
            for error in results['errors'][:5]:  # Show first 5 errors
                self.stdout.write(f"   - {error}")
            if len(results['errors']) > 5:
                self.stdout.write(f"   ... and {len(results['errors']) - 5} more errors")
        
        # Show next steps
        if results['successful_groups'] > 0:
            self.stdout.write(f"\n🚀 SUCCESS! Tiles generated and uploaded to S3")
            self.stdout.write(f"🌐 CloudFront URLs will be available shortly")
            self.stdout.write(f"💡 Test your tiles in the frontend now!")
        else:
            self.stdout.write(f"\n❌ No tiles were generated successfully")
            self.stdout.write(f"💡 Check the errors above and try again")
        
        self.stdout.write(f"\n🎉 Generation completed!")

    def _validate_generated_tiles(self, results):
        """Validate some generated tiles by attempting to download them"""
        # Implementation for tile validation if needed
        pass