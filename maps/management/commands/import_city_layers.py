# maps/management/commands/import_city_layers.py
"""
ENHANCED: Batch import multiple layer groups for a city from hierarchical directory structure
Command: python manage.py import_city_layers --city bengaluru --data-dir "data/karnataka/bengaluru" --layer-groups "master_plan,highways,metro"

Expected folder structure:
data/
  ├── karnataka/
      ├── bengaluru/
          ├── master_plan/           # Master plan JSONs
          ├── highways/              # Highway GeoJSONs  
          ├── metro/                 # Metro GeoJSONs
          └── workspaces/            # Workspace GeoJSONs
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from maps.models import City, State, DataLayer
from maps.management.commands.import_layer_data import Command as ImportLayerCommand
from maps.config import get_layer_groups_config
from pathlib import Path
import os

class Command(BaseCommand):
    help = 'Batch import multiple layer groups for a city from hierarchical directory structure'
    
    def add_arguments(self, parser):
        parser.add_argument('--city', required=True, help='City slug (e.g., bengaluru)')
        parser.add_argument('--data-dir', required=True, help='Base data directory for the city')
        parser.add_argument('--layer-groups', help='Comma-separated layer groups (e.g., "master_plan,highways,metro")')
        parser.add_argument('--layer-group', help='Single layer group (for backward compatibility)')
        parser.add_argument('--force', action='store_true', help='Force re-import existing layers')
        parser.add_argument('--validate-only', action='store_true', help='Only validate structure, don\'t import')
        parser.add_argument('--auto-style', action='store_true', help='Automatically create layer styling')
        parser.add_argument('--show-available', action='store_true', help='Show available layer groups and exit')
    
    def handle(self, *args, **options):
        city_slug = options['city']
        data_dir = options['data_dir']
        layer_groups_str = options.get('layer_groups')
        single_layer_group = options.get('layer_group')
        
        self.stdout.write(self.style.SUCCESS(f"🚀 Batch importing layers for city '{city_slug}'"))
        
        try:
            # Get city
            city = City.objects.get(slug=city_slug)
            self.stdout.write(f"🏙️  Found city: {city.name}")
            
            # Get all available layer groups for this city
            all_layer_groups = get_layer_groups_config(city_slug)
            if not all_layer_groups:
                self.stdout.write(self.style.ERROR(f"❌ No layer configuration found for city: {city_slug}"))
                return
            
            # Show available layer groups if requested
            if options['show_available']:
                self._show_available_layer_groups(city_slug, all_layer_groups)
                return
            
            # Determine which layer groups to import
            layer_groups_to_import = self._determine_layer_groups_to_import(
                layer_groups_str, single_layer_group, all_layer_groups
            )
            
            if not layer_groups_to_import:
                self.stdout.write(self.style.ERROR("❌ No valid layer groups specified"))
                self._show_available_layer_groups(city_slug, all_layer_groups)
                return
            
            self.stdout.write(f"📂 Data directory: {data_dir}")
            self.stdout.write(f"📋 Layer groups to import: {', '.join(layer_groups_to_import.keys())}")
            
            # Validate inputs
            if not os.path.exists(data_dir):
                self.stdout.write(self.style.ERROR(f"❌ Directory not found: {data_dir}"))
                return
            
            # Validate directory structure
            validation_result = self._validate_directory_structure(data_dir, layer_groups_to_import)
            self._display_validation_results(validation_result)
            
            if options['validate_only']:
                return
            
            if validation_result['total_missing'] > 0:
                self.stdout.write(f"⚠️  Found {validation_result['total_missing']} missing directories")
                if not self._confirm_continue():
                    return
            
            # Import selected layer groups
            import_results = self._batch_import_layers(
                city, data_dir, layer_groups_to_import, options
            )
            
            self._display_batch_results(import_results)
            
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            self.stdout.write("   Available cities:")
            for city in City.objects.all():
                self.stdout.write(f"   - {city.slug} ({city.name})")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Batch import failed: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())
    
    def _determine_layer_groups_to_import(self, layer_groups_str, single_layer_group, all_layer_groups):
        """Determine which layer groups to import based on parameters"""
        
        if layer_groups_str:
            # Parse comma-separated list
            requested_groups = [group.strip() for group in layer_groups_str.split(',')]
            layer_groups_to_import = {}
            
            for group_name in requested_groups:
                if group_name in all_layer_groups:
                    layer_groups_to_import[group_name] = all_layer_groups[group_name]
                else:
                    self.stdout.write(self.style.WARNING(f"⚠️  Unknown layer group: {group_name}"))
            
            return layer_groups_to_import
            
        elif single_layer_group:
            # Single layer group (backward compatibility)
            if single_layer_group in all_layer_groups:
                return {single_layer_group: all_layer_groups[single_layer_group]}
            else:
                self.stdout.write(self.style.ERROR(f"❌ Unknown layer group: {single_layer_group}"))
                return {}
        
        else:
            # Import all layer groups
            return all_layer_groups
    
    def _show_available_layer_groups(self, city_slug, all_layer_groups):
        """Show available layer groups for the city"""
        self.stdout.write(f"\n📋 Available layer groups for {city_slug}:")
        
        for group_name, group_config in all_layer_groups.items():
            layer_count = len(group_config.get('layers', {}))
            self.stdout.write(f"   📁 {group_name} ({layer_count} layers)")
            self.stdout.write(f"      {group_config.get('description', 'No description')}")
        
        self.stdout.write(f"\n💡 Usage examples:")
        self.stdout.write(f"   # Import all groups:")
        self.stdout.write(f"   --city {city_slug} --data-dir PATH")
        self.stdout.write(f"   ")
        self.stdout.write(f"   # Import specific groups:")
        self.stdout.write(f"   --city {city_slug} --data-dir PATH --layer-groups 'master_plan,highways'")
        self.stdout.write(f"   ")
        self.stdout.write(f"   # Import single group:")  
        self.stdout.write(f"   --city {city_slug} --data-dir PATH --layer-group master_plan")
    
    def _validate_directory_structure(self, data_dir, layer_groups):
        """Validate the directory structure matches expected configuration"""
        base_dir = Path(data_dir)
        
        validation_result = {
            'total_groups': len(layer_groups),
            'total_layers': 0,
            'found_groups': 0,
            'found_layers': 0,
            'missing_groups': [],
            'missing_layers': [],
            'found_files': [],
            'total_missing': 0
        }
        
        for group_name, group_config in layer_groups.items():
            group_dir = base_dir / group_name
            layers = group_config.get('layers', {})
            validation_result['total_layers'] += len(layers)
            
            if group_dir.exists():
                validation_result['found_groups'] += 1
                self.stdout.write(f"📁 Found group directory: {group_name}")
                
                # Check individual layers
                for layer_slug, layer_config in layers.items():
                    layer_files = self._find_layer_files(group_dir, layer_config)
                    
                    if layer_files:
                        validation_result['found_layers'] += 1
                        validation_result['found_files'].extend(layer_files)
                        self.stdout.write(f"   ✅ {layer_slug}: {len(layer_files)} files")
                    else:
                        validation_result['missing_layers'].append(f"{group_name}/{layer_slug}")
                        validation_result['total_missing'] += 1
                        self.stdout.write(f"   ❌ {layer_slug}: No files found")
            else:
                validation_result['missing_groups'].append(group_name)
                validation_result['total_missing'] += len(layers)
                self.stdout.write(f"❌ Missing group directory: {group_name}")
        
        return validation_result
    
    def _find_layer_files(self, group_dir, layer_config):
        """Find files for a specific layer"""
        file_pattern = layer_config.get('file_pattern', '*.geojson')
        
        if file_pattern == '*.geojson':
            return list(group_dir.glob('*.geojson')) + list(group_dir.glob('*.json'))
        else:
            return list(group_dir.glob(file_pattern))
    
    def _display_validation_results(self, result):
        """Display validation results summary"""
        self.stdout.write(f"\n📊 DIRECTORY STRUCTURE VALIDATION:")
        self.stdout.write(f"   Layer Groups: {result['found_groups']}/{result['total_groups']}")
        self.stdout.write(f"   Layers: {result['found_layers']}/{result['total_layers']}")
        self.stdout.write(f"   Total Files: {len(result['found_files'])}")
        
        if result['missing_groups']:
            self.stdout.write(f"\n❌ Missing Group Directories:")
            for group in result['missing_groups']:
                self.stdout.write(f"   - {group}")
        
        if result['missing_layers']:
            self.stdout.write(f"\n❌ Missing Layer Data:")
            for layer in result['missing_layers']:
                self.stdout.write(f"   - {layer}")
    
    def _confirm_continue(self):
        """Ask user if they want to continue with missing data"""
        response = input("\nContinue with partial data? (y/N): ")
        return response.lower() in ['y', 'yes']
    
    def _batch_import_layers(self, city, data_dir, layer_groups, options):
        """Import all layers in selected groups"""
        base_dir = Path(data_dir)
        
        import_results = {
            'total_groups': len(layer_groups),
            'total_layers': 0,
            'successful_groups': 0,
            'successful_layers': 0,
            'failed_layers': 0,
            'total_features': 0,
            'group_results': [],
            'errors': []
        }
        
        # Initialize the import layer command
        import_layer_cmd = ImportLayerCommand()
        
        for group_name, group_config in layer_groups.items():
            self.stdout.write(f"\n📁 Processing group: {group_name}")
            
            group_result = {
                'group_name': group_name,
                'layers_attempted': 0,
                'layers_successful': 0,
                'layers_failed': 0,
                'total_features': 0,
                'layer_results': []
            }
            
            layers = group_config.get('layers', {})
            import_results['total_layers'] += len(layers)
            
            group_dir = base_dir / group_name
            
            if not group_dir.exists():
                self.stdout.write(f"   ⚠️  Group directory not found: {group_dir}")
                continue
            
            # Process each layer in the group
            for layer_slug, layer_config in layers.items():
                group_result['layers_attempted'] += 1
                
                try:
                    # Find layer files
                    layer_files = self._find_layer_files(group_dir, layer_config)
                    
                    if not layer_files:
                        self.stdout.write(f"   ⚠️  No files found for layer: {layer_slug}")
                        group_result['layers_failed'] += 1
                        continue
                    
                    self.stdout.write(f"   📋 Importing layer: {layer_slug}")
                    
                    # Import this layer using the import_layer_data logic
                    layer_result = self._import_single_layer(
                        import_layer_cmd, city, layer_slug, layer_config, 
                        str(group_dir), group_name, options
                    )
                    
                    if layer_result['status'] == 'success':
                        group_result['layers_successful'] += 1
                        group_result['total_features'] += layer_result['total_features']
                        self.stdout.write(f"      ✅ Success: {layer_result['total_features']} features")
                    else:
                        group_result['layers_failed'] += 1
                        self.stdout.write(f"      ❌ Failed: {layer_result.get('error', 'Unknown error')}")
                    
                    group_result['layer_results'].append(layer_result)
                    
                except Exception as e:
                    group_result['layers_failed'] += 1
                    error_msg = f"Error importing {layer_slug}: {str(e)}"
                    import_results['errors'].append(error_msg)
                    self.stdout.write(f"      ❌ Error: {e}")
            
            # Update overall results
            if group_result['layers_successful'] > 0:
                import_results['successful_groups'] += 1
            
            import_results['successful_layers'] += group_result['layers_successful']
            import_results['failed_layers'] += group_result['layers_failed']
            import_results['total_features'] += group_result['total_features']
            import_results['group_results'].append(group_result)
        
        return import_results
    
    def _import_single_layer(self, import_cmd, city, layer_slug, layer_config, 
                           group_dir, group_name, options):
        """Import a single layer using the import_layer_data logic"""
        try:
            # Create fake options for the import command
            fake_options = {
                'city': city.slug,
                'layer': layer_slug,
                'data_dir': group_dir,
                'layer_group': group_name,
                'force': options.get('force', False),
                'validate_only': False,
                'auto_style': options.get('auto_style', False)
            }
            
            # Call the import layer method
            result = import_cmd._import_layer_with_config(
                city, layer_slug, layer_config, 
                import_cmd._find_geojson_files(Path(group_dir), layer_config.get('file_pattern', '*.geojson')),
                fake_options
            )
            
            # Create styling if auto_style is enabled
            if options.get('auto_style') and result['status'] == 'success':
                style_result = import_cmd._create_layer_styling(city, result['layer'], layer_config)
                result['style_created'] = style_result
            
            return result
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'total_features': 0
            }
    
    def _display_batch_results(self, results):
        """Display batch import results"""
        self.stdout.write(f"\n🎯 BATCH IMPORT RESULTS:")
        self.stdout.write(f"   Groups processed: {results['successful_groups']}/{results['total_groups']}")
        self.stdout.write(f"   Layers imported: {results['successful_layers']}/{results['total_layers']}")
        self.stdout.write(f"   Total features: {results['total_features']:,}")
        
        if results['failed_layers'] > 0:
            self.stdout.write(f"   Failed layers: {results['failed_layers']}")
        
        # Show per-group results
        for group_result in results['group_results']:
            if group_result['layers_successful'] > 0 or group_result['layers_failed'] > 0:
                success_rate = (group_result['layers_successful'] / max(1, group_result['layers_attempted'])) * 100
                self.stdout.write(f"\n📁 {group_result['group_name']}: {success_rate:.0f}% success")
                self.stdout.write(f"   Layers: {group_result['layers_successful']}/{group_result['layers_attempted']}")
                self.stdout.write(f"   Features: {group_result['total_features']:,}")
        
        # Show errors
        if results['errors']:
            self.stdout.write(f"\n❌ Errors ({len(results['errors'])}):")
            for error in results['errors'][:5]:  # Show first 5
                self.stdout.write(f"   - {error}")
            if len(results['errors']) > 5:
                self.stdout.write(f"   ... and {len(results['errors']) - 5} more errors")
        
        # Next steps
        self.stdout.write(f"\n🎯 Next Steps:")
        if results['successful_layers'] > 0:
            city_slug = results['group_results'][0]['layer_results'][0].get('city', 'CITY_SLUG') if results['group_results'] and results['group_results'][0]['layer_results'] else 'CITY_SLUG'
            self.stdout.write(f"1. Generate tiles: python manage.py generate_direct_s3_tiles --city {city_slug}")
            self.stdout.write(f"2. View hierarchy: python manage.py show_hierarchy --city {city_slug}")
            self.stdout.write(f"3. Check in admin: /admin/maps/datalayer/")
        else:
            self.stdout.write(f"1. Fix data issues and retry import")
            self.stdout.write(f"2. Check error messages above")