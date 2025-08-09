# maps/management/commands/import_layer_data.py
"""
Enhanced Import specific layer data for a city
Command: python manage.py import_layer_data --city city_slug --layer layer_name --data-dir "Path"

UPDATED to handle:
- Folder structure: data -> state_slug -> city_slug -> layer_slug -> geojson files  
- Layer-specific colors from configuration
- Different layer types (master_plan, highways, metro, workspaces)
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.utils.text import slugify
from maps.models import City, State, DataLayer, LayerCategory, LayerGroup, CityLayerStyle
from maps.services import DataImportService
from maps.config import get_layer_groups_config, get_all_layers_for_city  # Import our new config functions
from pathlib import Path
import os
import json

class Command(BaseCommand):
    help = 'Import specific layer data for a city from hierarchical directory structure'
    
    def add_arguments(self, parser):
        parser.add_argument('--city', required=True, help='City slug (e.g., bengaluru, hyderabad)')
        parser.add_argument('--layer', required=True, help='Layer slug (e.g., "Agricultural_Land", "BellaryRoad_NH44", "metro_lines")')
        parser.add_argument('--data-dir', required=True, help='Directory containing layer GeoJSON files')
        parser.add_argument('--layer-group', help='Layer group type (master_plan, highways, metro, workspaces)')
        parser.add_argument('--force', action='store_true', help='Force re-import existing layer')
        parser.add_argument('--validate-only', action='store_true', help='Only validate files, don\'t import')
        parser.add_argument('--auto-style', action='store_true', help='Automatically create layer styling from config')
    
    def handle(self, *args, **options):
        city_slug = options['city']
        layer_slug = options['layer']
        data_dir = options['data_dir']
        layer_group_type = options.get('layer_group')
        
        self.stdout.write(self.style.SUCCESS(f"🚀 Importing layer '{layer_slug}' for city '{city_slug}'"))
        self.stdout.write(f"📂 Data directory: {data_dir}")
        
        # Validate inputs
        if not os.path.exists(data_dir):
            self.stdout.write(self.style.ERROR(f"❌ Directory not found: {data_dir}"))
            return
        
        try:
            # Get city
            city = City.objects.get(slug=city_slug)
            self.stdout.write(f"🏙️  Found city: {city.name}")
            
            # Get layer configuration
            layer_config = self._get_layer_config(city_slug, layer_slug, layer_group_type)
            if not layer_config:
                self.stdout.write(self.style.ERROR(f"❌ Layer configuration not found for: {layer_slug}"))
                self.stdout.write("Available layers:")
                self._show_available_layers(city_slug)
                return
            
            self.stdout.write(f"🎨 Layer config: {layer_config['name']} (Color: {layer_config['color']})")
            
            # Find GeoJSON files in directory
            layer_dir = Path(data_dir)
            geojson_files = self._find_geojson_files(layer_dir, layer_config.get('file_pattern', '*.geojson'))
            
            if not geojson_files:
                self.stdout.write(self.style.ERROR(f"❌ No GeoJSON files found in {layer_dir}"))
                return
            
            self.stdout.write(f"📄 Found {len(geojson_files)} GeoJSON files:")
            for file in geojson_files:
                self.stdout.write(f"   - {file.name}")
            
            if options['validate_only']:
                self._validate_layer_files(geojson_files)
                return
            
            # Import the layer
            with transaction.atomic():
                result = self._import_layer_with_config(
                    city, layer_slug, layer_config, geojson_files, options
                )
            
            # Create styling if requested
            if options['auto_style'] and result['status'] == 'success':
                style_result = self._create_layer_styling(city, result['layer'], layer_config)
                self.stdout.write(f"🎨 Created styling: {style_result}")
            
            self._display_import_results(result)
            
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            self.stdout.write("   Available cities:")
            for city in City.objects.all():
                self.stdout.write(f"   - {city.slug} ({city.name})")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Import failed: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())
    
    def _get_layer_config(self, city_slug, layer_slug, layer_group_type=None):
        """Get layer configuration from config.py"""
        
        # Get layer groups for this city
        layer_groups = get_layer_groups_config(city_slug)
        if not layer_groups:
            return None
        
        # If layer group is specified, search in that group only
        if layer_group_type:
            group = layer_groups.get(layer_group_type, {})
            layers = group.get('layers', {})
            return layers.get(layer_slug)
        
        # Search all groups
        for group_name, group_config in layer_groups.items():
            layers = group_config.get('layers', {})
            if layer_slug in layers:
                config = layers[layer_slug].copy()
                config['layer_group'] = group_name
                return config
        
        return None
    
    def _show_available_layers(self, city_slug):
        """Show available layers for the city"""
        layer_groups = get_layer_groups_config(city_slug)
        if layer_groups:
            for group_name, group_config in layer_groups.items():
                self.stdout.write(f"  📁 {group_name}:")
                for layer_slug, layer_config in group_config.get('layers', {}).items():
                    self.stdout.write(f"     - {layer_slug} ({layer_config['name']})")
        else:
            self.stdout.write(f"  No layer configuration found for {city_slug}")
    
    def _find_geojson_files(self, layer_dir, file_pattern):
        """Find GeoJSON files matching the pattern"""
        if file_pattern == '*.geojson':
            return list(layer_dir.glob('*.geojson')) + list(layer_dir.glob('*.json'))
        else:
            return list(layer_dir.glob(file_pattern))
    
    def _validate_layer_files(self, geojson_files):
        """Validate GeoJSON files structure"""
        self.stdout.write("\n🔍 Validating GeoJSON files...")
        
        for file_path in geojson_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Basic GeoJSON validation
                if data.get('type') == 'FeatureCollection':
                    features = data.get('features', [])
                    self.stdout.write(f"   ✅ {file_path.name}: Valid ({len(features)} features)")
                    
                    # Sample properties for ESRI JSON format
                    if features and 'attributes' in features[0]:
                        props = features[0]['attributes']
                        prop_keys = list(props.keys())[:5]
                        self.stdout.write(f"      ESRI Properties: {', '.join(prop_keys)}")
                    elif features and 'properties' in features[0]:
                        props = features[0]['properties']
                        prop_keys = list(props.keys())[:5]
                        self.stdout.write(f"      GeoJSON Properties: {', '.join(prop_keys)}")
                        
                elif data.get('type') == 'Feature':
                    self.stdout.write(f"   ✅ {file_path.name}: Valid single feature")
                else:
                    # Check for ESRI JSON format
                    if 'features' in data and 'geometryType' in data:
                        features = data.get('features', [])
                        self.stdout.write(f"   ✅ {file_path.name}: Valid ESRI JSON ({len(features)} features)")
                    else:
                        self.stdout.write(f"   ⚠️  {file_path.name}: Unknown format")
                
            except json.JSONDecodeError as e:
                self.stdout.write(f"   ❌ {file_path.name}: Invalid JSON - {str(e)}")
            except Exception as e:
                self.stdout.write(f"   ❌ {file_path.name}: Validation error - {str(e)}")
    
    def _import_layer_with_config(self, city, layer_slug, layer_config, geojson_files, options):
        """Import the layer using configuration and color info"""
        import_service = DataImportService()
        
        # Get or create category
        category = self._get_or_create_category(layer_config)
        
        # Check if layer already exists
        existing_layer = DataLayer.objects.filter(
            city=city, 
            slug=layer_slug
        ).first()
        
        if existing_layer and not options['force']:
            self.stdout.write(f"⚠️  Layer already exists: {layer_config['name']}")
            self.stdout.write("   Use --force to re-import")
            return {
                'status': 'skipped',
                'layer': existing_layer,
                'reason': 'already_exists'
            }
        
        # Delete existing layer if force is true
        if existing_layer and options['force']:
            self.stdout.write(f"🗑️  Removing existing layer: {layer_config['name']}")
            existing_layer.delete()
        
        # Create new DataLayer
        data_layer = DataLayer.objects.create(
            city=city,
            category=category,
            name=layer_config['name'],
            slug=layer_slug,
            description=f"{layer_config['name']} - {layer_config.get('layer_group', 'Unknown')} layer",
            file_format='GEOJSON',
            categorization_method='MANUAL',
            file_path=str(geojson_files[0].parent),  # Store directory path
            is_processed=False
        )
        
        self.stdout.write(f"📋 Created layer: {data_layer.name}")
        
        # Import all GeoJSON files into this layer
        total_features = 0
        successful_files = 0
        failed_files = []
        
        for file_path in geojson_files:
            try:
                self.stdout.write(f"📄 Processing: {file_path.name}")
                
                # Use import service to import this file
                file_result = import_service.import_geojson_to_layer(str(file_path), data_layer)
                
                if file_result.get('status') == 'success':
                    features_count = file_result.get('features_imported', 0)
                    total_features += features_count
                    successful_files += 1
                    self.stdout.write(f"   ✅ Imported {features_count} features")
                else:
                    failed_files.append({
                        'file': file_path.name,
                        'error': file_result.get('error', 'Unknown error')
                    })
                    self.stdout.write(f"   ❌ Failed: {file_result.get('error')}")
                    
            except Exception as e:
                failed_files.append({
                    'file': file_path.name,
                    'error': str(e)
                })
                self.stdout.write(f"   ❌ Error: {e}")
        
        # Update layer metadata
        data_layer.feature_count = total_features
        data_layer.is_processed = successful_files > 0
        data_layer.calculate_bbox()  # Calculate bounding box
        data_layer.save()
        
        return {
            'status': 'success' if successful_files > 0 else 'failed',
            'layer': data_layer,
            'layer_name': layer_config['name'],
            'layer_slug': layer_slug,
            'category': category.name,
            'total_files': len(geojson_files),
            'successful_files': successful_files,
            'failed_files': failed_files,
            'total_features': total_features,
            'color': layer_config['color']
        }
    
    def _get_or_create_category(self, layer_config):
        """Get or create LayerCategory based on config"""
        category_code = layer_config.get('category', 'UNCLASSIFIED')
        
        category, created = LayerCategory.objects.get_or_create(
            code=category_code,
            defaults={
                'name': category_code.replace('_', ' ').title(),
                'description': f'{category_code.replace("_", " ").title()} related layers',
                'default_color': layer_config.get('color', '#CCCCCC'),
                'default_opacity': 0.7
            }
        )
        
        if created:
            self.stdout.write(f"📂 Created category: {category.name}")
        
        return category
    
    def _create_layer_styling(self, city, data_layer, layer_config):
        """Create CityLayerStyle for this layer"""
        style, created = CityLayerStyle.objects.get_or_create(
            city=city,
            category=data_layer.category,
            defaults={
                'fill_color': layer_config['color'],
                'stroke_color': '#333333',
                'opacity': 0.7,
                'stroke_width': 1,
                'is_visible': True
            }
        )
        
        if not created:
            # Update existing style with layer-specific color
            style.fill_color = layer_config['color']
            style.save()
            return f"Updated existing style with color {layer_config['color']}"
        else:
            return f"Created new style with color {layer_config['color']}"
    
    def _display_import_results(self, result):
        """Display import results summary"""
        if result['status'] == 'success':
            self.stdout.write(f"\n✅ IMPORT SUCCESSFUL")
            self.stdout.write(f"   Layer: {result['layer_name']}")
            self.stdout.write(f"   Category: {result['category']}")
            self.stdout.write(f"   Color: {result['color']}")
            self.stdout.write(f"   Files processed: {result['successful_files']}/{result['total_files']}")
            self.stdout.write(f"   Features imported: {result['total_features']}")
            
            if result['failed_files']:
                self.stdout.write(f"\n⚠️  Failed files ({len(result['failed_files'])}):")
                for failed in result['failed_files'][:3]:  # Show first 3
                    self.stdout.write(f"   - {failed['file']}: {failed['error']}")
                if len(result['failed_files']) > 3:
                    self.stdout.write(f"   ... and {len(result['failed_files']) - 3} more")
            
            self.stdout.write(f"\n🎯 Next Steps:")
            self.stdout.write(f"1. Generate tiles: python manage.py generate_direct_s3_tiles --city {result['layer'].city.slug}")
            self.stdout.write(f"2. View in admin: /admin/maps/datalayer/{result['layer'].id}/")
            
        elif result['status'] == 'skipped':
            self.stdout.write(f"\n⏭️  IMPORT SKIPPED")
            self.stdout.write(f"   Reason: {result['reason']}")
            
        else:
            self.stdout.write(f"\n❌ IMPORT FAILED")
            self.stdout.write(f"   Check the errors above for details")