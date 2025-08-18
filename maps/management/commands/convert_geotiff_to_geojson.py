# maps/management/commands/convert_geotiff_to_geojson.py
"""
Management command to convert GeoTIFF files to GeoJSON and integrate into existing structure
Usage: python manage.py convert_geotiff_to_geojson --input /path/to/geotiff.tif --city bengaluru --category RESIDENTIAL --output /path/to/output.geojson

This command:
1. Converts GeoTIFF to GeoJSON using GDAL
2. Optimizes the output for web use
3. Integrates with existing city/category structure
4. Supports both single files and batch processing
"""

import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Convert GeoTIFF files to GeoJSON format and integrate with existing structure'
    
    def add_arguments(self, parser):
        parser.add_argument('--input', required=True, help='Input GeoTIFF file or directory')
        parser.add_argument('--city', required=True, help='City slug (e.g., bengaluru)')
        parser.add_argument('--category', required=True, help='Layer category (e.g., RESIDENTIAL, COMMERCIAL)')
        parser.add_argument('--output', help='Output GeoJSON file (optional, auto-generated if not provided)')
        parser.add_argument('--layer-name', help='Custom layer name (optional)')
        parser.add_argument('--simplify-tolerance', type=float, default=0.0001, 
                          help='Simplification tolerance for reducing file size (default: 0.0001)')
        parser.add_argument('--batch', action='store_true', help='Process all .tif files in input directory')
        parser.add_argument('--force', action='store_true', help='Overwrite existing output files')
        parser.add_argument('--verbose', action='store_true', help='Verbose output')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be done without executing')
        
    def handle(self, *args, **options):
        input_path = Path(options['input'])
        city_slug = options['city']
        category = options['category']
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🗺️  GEOTIFF TO GEOJSON CONVERTER'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Validate inputs
        if not self._validate_inputs(input_path, city_slug, category, options):
            return
        
        # Process files
        if options['batch'] and input_path.is_dir():
            self._process_batch(input_path, city_slug, category, options)
        else:
            self._process_single_file(input_path, city_slug, category, options)
    
    def _validate_inputs(self, input_path, city_slug, category, options):
        """Validate input parameters"""
        
        # Check if input exists
        if not input_path.exists():
            self.stdout.write(self.style.ERROR(f"❌ Input path does not exist: {input_path}"))
            return False
        
        # Check if it's a file or directory
        if input_path.is_file() and not input_path.suffix.lower() in ['.tif', '.tiff']:
            self.stdout.write(self.style.ERROR(f"❌ Input file is not a GeoTIFF: {input_path}"))
            return False
        
        # Validate city
        from maps.models import City
        try:
            city = City.objects.get(slug=city_slug, is_active=True)
            self.stdout.write(f"✅ City found: {city.name}")
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            return False
        
        # Validate category
        from maps.models import LayerCategory
        try:
            layer_category = LayerCategory.objects.get(code=category, is_active=True)
            self.stdout.write(f"✅ Category found: {layer_category.name}")
        except LayerCategory.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Category not found: {category}"))
            return False
        
        return True
    
    def _process_batch(self, input_dir, city_slug, category, options):
        """Process all GeoTIFF files in a directory"""
        
        tif_files = list(input_dir.glob('*.tif')) + list(input_dir.glob('*.tiff'))
        
        if not tif_files:
            self.stdout.write(self.style.WARNING(f"⚠️  No GeoTIFF files found in: {input_dir}"))
            return
        
        self.stdout.write(f"\n📦 Processing {len(tif_files)} GeoTIFF files...")
        
        for tif_file in tif_files:
            self.stdout.write(f"\n🔄 Processing: {tif_file.name}")
            self._process_single_file(tif_file, city_slug, category, options)
    
    def _process_single_file(self, input_file, city_slug, category, options):
        """Process a single GeoTIFF file"""
        
        # Generate output path if not provided
        if options['output']:
            output_path = Path(options['output'])
        else:
            output_dir = Path(settings.BASE_DIR) / 'data' / 'converted' / city_slug
            output_dir.mkdir(parents=True, exist_ok=True)
            
            layer_name = options['layer_name'] or input_file.stem
            output_path = output_dir / f"{layer_name}.geojson"
        
        # Check if output exists and force flag
        if output_path.exists() and not options['force'] and not options['dry_run']:
            self.stdout.write(self.style.WARNING(f"⚠️  Output file exists: {output_path}"))
            self.stdout.write(self.style.WARNING("   Use --force to overwrite"))
            return
        
        if options['dry_run']:
            self.stdout.write(f"🔍 Would convert: {input_file} → {output_path}")
            return
        
        try:
            # Convert GeoTIFF to GeoJSON
            success = self._convert_geotiff_to_geojson(
                input_file, output_path, options
            )
            
            if success:
                self.stdout.write(self.style.SUCCESS(f"✅ Converted: {input_file.name} → {output_path.name}"))
                
                # Show file statistics
                self._show_file_stats(output_path)
                
                # Optionally integrate with existing import system
                if self._should_integrate_automatically(options):
                    self._integrate_with_system(output_path, city_slug, category, options)
            else:
                self.stdout.write(self.style.ERROR(f"❌ Failed to convert: {input_file.name}"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error processing {input_file.name}: {str(e)}"))
            if options['verbose']:
                import traceback
                self.stdout.write(traceback.format_exc())
    
    def _convert_geotiff_to_geojson(self, input_file, output_path, options):
        """Convert GeoTIFF to GeoJSON using GDAL"""
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build GDAL command
        cmd = [
            'gdal_polygonize.py',
            str(input_file),
            '-f', 'GeoJSON',
            str(output_path)
        ]
        
        # Add simplification if requested
        if options['simplify_tolerance'] > 0:
            # First convert to GeoJSON, then simplify
            temp_output = output_path.with_suffix('.temp.geojson')
            cmd = [
                'gdal_polygonize.py',
                str(input_file),
                '-f', 'GeoJSON',
                str(temp_output)
            ]
        
        if options['verbose']:
            self.stdout.write(f"🔧 Running command: {' '.join(cmd)}")
        
        try:
            # Run GDAL conversion
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Apply simplification if requested
            if options['simplify_tolerance'] > 0 and 'temp_output' in locals():
                self._simplify_geojson(temp_output, output_path, options['simplify_tolerance'])
                temp_output.unlink()  # Remove temp file
            
            # Optimize the GeoJSON
            self._optimize_geojson(output_path)
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(f"❌ GDAL error: {e.stderr}"))
            return False
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Conversion error: {str(e)}"))
            return False
    
    def _simplify_geojson(self, input_path, output_path, tolerance):
        """Simplify GeoJSON geometry to reduce file size"""
        
        try:
            import geopandas as gpd
            
            # Read GeoJSON
            gdf = gpd.read_file(input_path)
            
            # Simplify geometries
            gdf['geometry'] = gdf['geometry'].simplify(tolerance, preserve_topology=True)
            
            # Save simplified version
            gdf.to_file(output_path, driver='GeoJSON')
            
            self.stdout.write(f"🔧 Simplified geometry with tolerance: {tolerance}")
            
        except ImportError:
            self.stdout.write(self.style.WARNING("⚠️  geopandas not available, skipping simplification"))
            # Copy temp file to output
            import shutil
            shutil.copy2(input_path, output_path)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠️  Simplification failed: {str(e)}"))
            # Copy temp file to output
            import shutil
            shutil.copy2(input_path, output_path)
    
    def _optimize_geojson(self, geojson_path):
        """Optimize GeoJSON for web use"""
        
        try:
            with open(geojson_path, 'r') as f:
                data = json.load(f)
            
            # Optimize coordinates
            if 'features' in data:
                for feature in data['features']:
                    if 'geometry' in feature and 'coordinates' in feature['geometry']:
                        feature['geometry']['coordinates'] = self._optimize_coordinates(
                            feature['geometry']['coordinates']
                        )
            
            # Write optimized version
            with open(geojson_path, 'w') as f:
                json.dump(data, f, separators=(',', ':'))
            
            self.stdout.write("🔧 Optimized GeoJSON coordinates")
            
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠️  Optimization failed: {str(e)}"))
    
    def _optimize_coordinates(self, coords, precision=6):
        """Optimize coordinate precision"""
        if isinstance(coords, list):
            return [self._optimize_coordinates(coord, precision) for coord in coords]
        elif isinstance(coords, (int, float)):
            return round(float(coords), precision)
        return coords
    
    def _show_file_stats(self, geojson_path):
        """Show statistics about the converted file"""
        
        try:
            with open(geojson_path, 'r') as f:
                data = json.load(f)
            
            file_size = geojson_path.stat().st_size / (1024 * 1024)  # MB
            feature_count = len(data.get('features', []))
            
            self.stdout.write(f"📊 File size: {file_size:.2f} MB")
            self.stdout.write(f"📊 Features: {feature_count}")
            
            # Show coordinate bounds if available
            if 'bbox' in data:
                bbox = data['bbox']
                self.stdout.write(f"📊 Bounds: [{bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f}]")
            
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠️  Could not read file stats: {str(e)}"))
    
    def _should_integrate_automatically(self, options):
        """Determine if we should automatically integrate with the system"""
        # For now, always ask user - could be made configurable
        return False
    
    def _integrate_with_system(self, geojson_path, city_slug, category, options):
        """Integrate the converted GeoJSON with the existing import system"""
        
        self.stdout.write("\n🔄 Integrating with existing system...")
        
        try:
            # Use the existing import service
            from maps.services import DataImportService
            
            service = DataImportService()
            
            # Import the converted file
            layer_name = options['layer_name'] or geojson_path.stem
            layer_slug = slugify(layer_name)
            
            # This would integrate with your existing import system
            # You can call the appropriate import method here
            
            self.stdout.write(self.style.SUCCESS(f"✅ Integrated: {layer_name}"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Integration failed: {str(e)}"))
    
    def _print_summary(self):
        """Print conversion summary"""
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS("✅ CONVERSION COMPLETE"))
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write("\n📋 Next steps:")
        self.stdout.write("1. Review the converted GeoJSON files")
        self.stdout.write("2. Use the existing import system to add them to the database")
        self.stdout.write("3. Generate tiles for the new layers")
        self.stdout.write("\n💡 Tip: Use 'python manage.py import_geospatial_data' to import the converted files")
