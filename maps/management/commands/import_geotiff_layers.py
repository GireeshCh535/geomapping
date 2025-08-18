# maps/management/commands/import_geotiff_layers.py
"""
Management command to import GeoTIFF files directly into the geospatial system
Usage: python manage.py import_geotiff_layers --input /path/to/geotiff.tif --city bengaluru --category RESIDENTIAL

This command:
1. Converts GeoTIFF to GeoJSON using GDAL
2. Imports the data directly into the database
3. Creates layers in the existing hierarchy
4. Supports batch processing and optimization
"""

import os
import sys
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.conf import settings
import logging

from maps.geotiff_service import GeoTIFFService

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Import GeoTIFF files directly into the geospatial data system'
    
    def add_arguments(self, parser):
        parser.add_argument('--input', required=True, help='Input GeoTIFF file or directory')
        parser.add_argument('--city', required=True, help='City slug (e.g., bengaluru)')
        parser.add_argument('--category', required=True, help='Layer category (e.g., RESIDENTIAL, COMMERCIAL)')
        parser.add_argument('--layer-name', help='Custom layer name (optional)')
        parser.add_argument('--simplify-tolerance', type=float, default=0.0001, 
                          help='Simplification tolerance for reducing file size (default: 0.0001)')
        parser.add_argument('--batch', action='store_true', help='Process all .tif files in input directory')
        parser.add_argument('--file-pattern', default='*.tif', help='File pattern for batch processing')
        parser.add_argument('--optimize-coordinates', action='store_true', default=True,
                          help='Optimize coordinate precision (default: True)')
        parser.add_argument('--generate-tiles', action='store_true', 
                          help='Generate tiles directly to S3 after import (default: False)')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be done without executing')
        parser.add_argument('--verbose', action='store_true', help='Verbose output')
        
    def handle(self, *args, **options):
        input_path = Path(options['input'])
        city_slug = options['city']
        category_code = options['category']
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🗺️  GEOTIFF LAYER IMPORT'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Initialize service
        self.geotiff_service = GeoTIFFService()
        
        # Set logging level
        if options['verbose']:
            logging.getLogger('maps.geotiff_service').setLevel(logging.DEBUG)
        
        try:
            # Process files
            if options['batch'] and input_path.is_dir():
                results = self._process_batch(input_path, city_slug, category_code, options)
            else:
                results = [self._process_single_file(input_path, city_slug, category_code, options)]
            
            # Print summary
            self._print_summary(results, options)
            
            # Generate tiles if requested
            if options['generate_tiles'] and not options['dry_run']:
                self._generate_tiles_for_imported_layers(results, options)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Import failed: {str(e)}"))
            if options['verbose']:
                import traceback
                self.stdout.write(traceback.format_exc())
        finally:
            # Cleanup
            if not options['dry_run']:
                self.geotiff_service.cleanup_temp_files()
    
    def _process_batch(self, input_dir, city_slug, category_code, options):
        """Process all GeoTIFF files in a directory"""
        
        if not input_dir.exists() or not input_dir.is_dir():
            self.stdout.write(self.style.ERROR(f"❌ Directory not found: {input_dir}"))
            return []
        
        # Find matching files
        tif_files = list(input_dir.glob(options['file_pattern'])) + list(input_dir.glob('*.tiff'))
        
        if not tif_files:
            self.stdout.write(self.style.WARNING(f"⚠️  No GeoTIFF files found in: {input_dir}"))
            return []
        
        self.stdout.write(f"\n📦 Processing {len(tif_files)} GeoTIFF files...")
        
        results = []
        for tif_file in tif_files:
            self.stdout.write(f"\n🔄 Processing: {tif_file.name}")
            result = self._process_single_file(tif_file, city_slug, category_code, options)
            results.append(result)
        
        return results
    
    def _process_single_file(self, input_path, city_slug, category_code, options):
        """Process a single GeoTIFF file"""
        
        if options['dry_run']:
            layer_name = options['layer_name'] or input_path.stem
            self.stdout.write(f"🔍 Would import: {input_path.name} → {layer_name}")
            return {
                'success': True,
                'input_file': str(input_path),
                'layer_name': layer_name,
                'dry_run': True
            }
        
        # Generate layer name if not provided
        layer_name = options['layer_name'] or input_path.stem
        
        # Process the file
        result = self.geotiff_service.process_geotiff_file(
            input_path=str(input_path),
            city_slug=city_slug,
            category_code=category_code,
            layer_name=layer_name,
            simplify_tolerance=options['simplify_tolerance'],
            optimize_coordinates=options['optimize_coordinates']
        )
        
        # Print results
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f"✅ Successfully imported: {layer_name}"))
            self.stdout.write(f"   📊 Features: {result['features_imported']}")
            self.stdout.write(f"   ⏱️  Time: {result['processing_time']:.2f}s")
            
            if result['output_file']:
                # Show file stats
                stats = self.geotiff_service.get_conversion_stats(Path(result['output_file']))
                self.stdout.write(f"   📁 File size: {stats['file_size_mb']:.2f} MB")
                self.stdout.write(f"   🔷 Geometry types: {', '.join(stats['geometry_types'])}")
        else:
            self.stdout.write(self.style.ERROR(f"❌ Failed to import: {layer_name}"))
            for error in result['errors']:
                self.stdout.write(f"   ❌ Error: {error}")
        
        return result
    
    def _print_summary(self, results, options):
        """Print import summary"""
        
        successful = [r for r in results if r.get('success', False)]
        failed = [r for r in results if not r.get('success', False)]
        
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS("📊 IMPORT SUMMARY"))
        self.stdout.write(self.style.SUCCESS("=" * 70))
        
        self.stdout.write(f"\n✅ Successful imports: {len(successful)}")
        self.stdout.write(f"❌ Failed imports: {len(failed)}")
        
        if successful:
            total_features = sum(r.get('features_imported', 0) for r in successful)
            total_time = sum(r.get('processing_time', 0) for r in successful)
            self.stdout.write(f"📊 Total features imported: {total_features}")
            self.stdout.write(f"⏱️  Total processing time: {total_time:.2f}s")
            
            self.stdout.write("\n📋 Successfully imported layers:")
            for result in successful:
                layer = result.get('layer_created')
                if layer:
                    self.stdout.write(f"   • {layer.name} ({result.get('features_imported', 0)} features)")
        
        if failed:
            self.stdout.write("\n❌ Failed imports:")
            for result in failed:
                input_file = result.get('input_file', 'Unknown')
                errors = result.get('errors', [])
                self.stdout.write(f"   • {Path(input_file).name}: {', '.join(errors)}")
        
        if not options['dry_run']:
            self.stdout.write("\n💡 Next steps:")
            self.stdout.write("1. Review the imported layers in the admin interface")
            self.stdout.write("2. Generate tiles for the new layers if needed")
            self.stdout.write("3. Configure styling for the new layers")
    
    def _generate_tiles_for_imported_layers(self, results, options):
        """Generate tiles for successfully imported layers"""
        
        successful_layers = [r for r in results if r.get('success', False) and r.get('layer_created')]
        
        if not successful_layers:
            self.stdout.write(self.style.WARNING("⚠️  No successful imports to generate tiles for"))
            return
        
        self.stdout.write(f"\n🔄 Generating tiles for {len(successful_layers)} layers...")
        
        for result in successful_layers:
            layer = result['layer_created']
            city_slug = layer.city.slug
            
            self.stdout.write(f"   🎯 Generating tiles for: {layer.name}")
            
            try:
                # Generate PNG tiles
                self._run_tile_generation_command(city_slug, layer.slug, 'png', options)
                
                # Generate MVT tiles
                self._run_tile_generation_command(city_slug, layer.slug, 'mvt', options)
                
                self.stdout.write(self.style.SUCCESS(f"   ✅ Tiles generated for: {layer.name}"))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ Tile generation failed for {layer.name}: {str(e)}"))
    
    def _run_tile_generation_command(self, city_slug, layer_slug, tile_type, options):
        """Run tile generation command directly to S3"""
        
        if tile_type == 'png':
            cmd = [
                'python', 'manage.py', 'generate_direct_s3_tiles',
                '--city', city_slug,
                '--layer', layer_slug,
                '--min-zoom', '10',
                '--max-zoom', '14'
            ]
        else:  # mvt
            cmd = [
                'python', 'manage.py', 'generate_combined_mvt_tiles',
                '--city', city_slug,
                '--layer', layer_slug,
                '--min-zoom', '10',
                '--max-zoom', '14'
            ]
        
        if options['verbose']:
            cmd.append('--verbose')
        
        # Run the command
        import subprocess
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Tile generation failed: {result.stderr}")
    
    def _validate_inputs(self, input_path, city_slug, category_code):
        """Validate input parameters"""
        
        # Check if input exists
        if not input_path.exists():
            self.stdout.write(self.style.ERROR(f"❌ Input path does not exist: {input_path}"))
            return False
        
        # Check if it's a file or directory
        if input_path.is_file() and not input_path.suffix.lower() in ['.tif', '.tiff']:
            self.stdout.write(self.style.ERROR(f"❌ Input file is not a GeoTIFF: {input_path}"))
            return False
        
        # Validate city and category (these will be validated by the service)
        return True
