# maps/management/commands/import_city_layers.py
"""
UPDATED: Hierarchical import for city layer groups from directory structure
Command: python manage.py import_city_layers --city bengaluru --data-dir "data/karnataka/bengaluru" --layer-groups "master_plan,highways,metro"

Expected folder structure:
data/
  ├── karnataka/
      ├── bengaluru/
          ├── master_plan/           # Master plan JSONs (Agricultural_Land.json, Industrial.json, etc.)
          ├── highways/              # Highway GeoJSONs (BellaryRoad_NH44.geojson, etc.)
          ├── metro/                 # Metro GeoJSONs (Bangalore Metro Phases.geojson)
          ├── strr/                  # STRR GeoJSONs (STRR.geojson)
          └── workspace/            # Workspace GeoJSONs (Blr_Industrial_Area_processed.geojson)
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from maps.models import City, State, DataLayer, LayerGroup
from maps.services import DataImportService
from maps.config import get_layer_groups_config
from pathlib import Path
import os

class Command(BaseCommand):
    help = 'Import hierarchical city layer groups from directory structure'
    
    def add_arguments(self, parser):
        parser.add_argument('--city', required=True, help='City slug (e.g., bengaluru)')
        parser.add_argument('--data-dir', required=True, help='Base data directory for the city')
        parser.add_argument('--layer-groups', help='Comma-separated layer groups (e.g., "master_plan,highways,metro")')
        parser.add_argument('--layer-group', help='Single layer group (for backward compatibility)')
        parser.add_argument('--force', action='store_true', help='Force re-import existing layers')
        parser.add_argument('--validate-only', action='store_true', help='Only validate structure, don\'t import')
        parser.add_argument('--auto-style', action='store_true', help='Automatically create layer styling')
        parser.add_argument('--show-available', action='store_true', help='Show available layer groups and exit')
        parser.add_argument('--show-structure', action='store_true', help='Show expected directory structure')

    def handle(self, *args, **options):
        city_slug = options['city']
        data_dir = options['data_dir']
        layer_groups_str = options.get('layer_groups') or options.get('layer_group')
        
        self.stdout.write(self.style.SUCCESS(f"📁 Importing layer groups for city '{city_slug}'"))
        
        try:
            # Show structure if requested
            if options['show_structure']:
                self._show_expected_structure(city_slug)
                return
            
            # Show available layer groups if requested
            if options['show_available']:
                self._show_available_layer_groups(city_slug)
                return
            
            # Validate directory structure
            if not self._validate_directory_structure(data_dir, city_slug):
                return
            
            # Get city and state
            city = City.objects.get(slug=city_slug)
            state = city.state_ref
            if not state:
                self.stdout.write(self.style.ERROR("❌ City has no state reference"))
                return
            
            self.stdout.write(f"🏙️  Found city: {city.name} ({state.name})")
            self.stdout.write(f"📂 Data directory: {data_dir}")
            
            # Determine which layer groups to import
            layer_groups_to_import = self._determine_layer_groups_to_import(
                city_slug, layer_groups_str, data_dir
            )
            
            if not layer_groups_to_import:
                self.stdout.write(self.style.ERROR("❌ No valid layer groups found to import"))
                self.stdout.write("💡 Use --show-available to see available layer groups")
                return
            
            # Validate only mode
            if options['validate_only']:
                self._validate_layer_groups(layer_groups_to_import, data_dir)
                return
            
            # Import each layer group
            results = self._import_layer_groups(
                city, layer_groups_to_import, data_dir, options
            )
            
            self._display_import_results(results)
            
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            self.stdout.write("💡 Run: python manage.py setup_hierarchy_from_excel --use-default")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Import failed: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())

    def _show_expected_structure(self, city_slug):
        """Show expected directory structure for the city"""
        self.stdout.write(f"\n📋 Expected directory structure for {city_slug}:")
        self.stdout.write(f"data/")
        self.stdout.write(f"  ├── karnataka/")
        self.stdout.write(f"      ├── {city_slug}/")
        
        layer_groups = get_layer_groups_config(city_slug)
        for group_name, group_config in layer_groups.items():
            layers = group_config.get('layers', {})
            self.stdout.write(f"          ├── {group_name}/")
            
            # Show expected files
            for layer_slug, layer_config in layers.items():
                file_pattern = layer_config.get('file_pattern', f'{layer_slug}.json')
                self.stdout.write(f"          │   ├── {file_pattern}")
        
        self.stdout.write(f"\n💡 Example command:")
        self.stdout.write(f"python manage.py import_city_layers \\")
        self.stdout.write(f"    --city {city_slug} \\")
        self.stdout.write(f"    --data-dir \"data/karnataka/{city_slug}\" \\")
        self.stdout.write(f"    --layer-groups \"master_plan,highways,metro\"")

    def _show_available_layer_groups(self, city_slug):
        """Show available layer groups for the city"""
        self.stdout.write(f"\n📋 Available layer groups for {city_slug}:")
        
        layer_groups = get_layer_groups_config(city_slug)
        if not layer_groups:
            self.stdout.write("   No layer groups configured")
            return
        
        for group_name, group_config in layer_groups.items():
            layer_count = len(group_config.get('layers', {}))
            self.stdout.write(f"   📁 {group_name}")
            self.stdout.write(f"      Name: {group_config.get('name', group_name)}")
            self.stdout.write(f"      Description: {group_config.get('description', 'No description')}")
            self.stdout.write(f"      Layers: {layer_count}")
            
            # Show expected files
            layers = group_config.get('layers', {})
            if layers:
                self.stdout.write(f"      Expected files:")
                for layer_slug, layer_config in list(layers.items())[:3]:  # Show first 3
                    file_pattern = layer_config.get('file_pattern', f'{layer_slug}.json')
                    self.stdout.write(f"        - {file_pattern}")
                if len(layers) > 3:
                    self.stdout.write(f"        ... and {len(layers) - 3} more")
            self.stdout.write("")

    def _validate_directory_structure(self, data_dir, city_slug):
        """Validate that the directory structure exists"""
        data_path = Path(data_dir)
        
        if not data_path.exists():
            self.stdout.write(self.style.ERROR(f"❌ Directory not found: {data_dir}"))
            return False
        
        if not data_path.is_dir():
            self.stdout.write(self.style.ERROR(f"❌ Path is not a directory: {data_dir}"))
            return False
        
        # Check if city directory has subdirectories
        subdirs = [d for d in data_path.iterdir() if d.is_dir()]
        if not subdirs:
            self.stdout.write(self.style.WARNING(f"⚠️  No subdirectories found in: {data_dir}"))
            
        self.stdout.write(f"✅ Directory structure validated")
        return True

    def _determine_layer_groups_to_import(self, city_slug, layer_groups_str, data_dir):
        """Determine which layer groups to import based on available directories"""
        
        layer_groups_config = get_layer_groups_config(city_slug)
        data_path = Path(data_dir)
        
        if layer_groups_str:
            # User specified layer groups
            requested_groups = [group.strip() for group in layer_groups_str.split(',')]
            groups_to_import = {}
            
            for group_name in requested_groups:
                if group_name in layer_groups_config:
                    group_dir = data_path / group_name
                    if group_dir.exists() and group_dir.is_dir():
                        groups_to_import[group_name] = layer_groups_config[group_name]
                        self.stdout.write(f"📁 Found layer group directory: {group_name}")
                    else:
                        self.stdout.write(self.style.WARNING(f"⚠️  Directory not found: {group_dir}"))
                else:
                    self.stdout.write(self.style.WARNING(f"⚠️  Unknown layer group: {group_name}"))
            
            return groups_to_import
        else:
            # Auto-detect available layer groups
            groups_to_import = {}
            
            for group_name, group_config in layer_groups_config.items():
                group_dir = data_path / group_name
                if group_dir.exists() and group_dir.is_dir():
                    # Check if directory has data files
                    data_files = list(group_dir.glob('*.json')) + list(group_dir.glob('*.geojson'))
                    if data_files:
                        groups_to_import[group_name] = group_config
                        self.stdout.write(f"📁 Auto-detected layer group: {group_name} ({len(data_files)} files)")
            
            return groups_to_import

    def _validate_layer_groups(self, layer_groups_to_import, data_dir):
        """Validate layer groups without importing"""
        self.stdout.write(f"\n🔍 VALIDATION MODE - Checking layer groups:")
        
        data_path = Path(data_dir)
        total_files = 0
        total_layers = 0
        
        for group_name, group_config in layer_groups_to_import.items():
            self.stdout.write(f"\n📁 Validating group: {group_name}")
            group_dir = data_path / group_name
            expected_layers = group_config.get('layers', {})
            
            found_files = 0
            missing_files = 0
            
            for layer_slug, layer_config in expected_layers.items():
                file_pattern = layer_config.get('file_pattern', f'*{layer_slug}*.json')
                
                # Look for files matching pattern
                matches = list(group_dir.glob(file_pattern))
                if matches:
                    self.stdout.write(f"   ✅ {layer_slug}: {len(matches)} files found")
                    found_files += len(matches)
                    total_files += len(matches)
                else:
                    self.stdout.write(f"   ❌ {layer_slug}: No files matching '{file_pattern}'")
                    missing_files += 1
                
                total_layers += 1
            
            self.stdout.write(f"   📊 Group summary: {found_files} files found, {missing_files} missing")
        
        self.stdout.write(f"\n📊 VALIDATION SUMMARY:")
        self.stdout.write(f"   Total layer groups: {len(layer_groups_to_import)}")
        self.stdout.write(f"   Total expected layers: {total_layers}")
        self.stdout.write(f"   Total data files found: {total_files}")
        
        if total_files > 0:
            self.stdout.write(f"✅ Ready for import!")
        else:
            self.stdout.write(f"❌ No data files found - check directory structure")

    def _import_layer_groups(self, city, layer_groups_to_import, data_dir, options):
        """Import all specified layer groups"""
        
        results = {
            'city': city.slug,
            'total_groups': len(layer_groups_to_import),
            'successful_groups': 0,
            'failed_groups': 0,
            'total_layers': 0,
            'successful_layers': 0,
            'failed_layers': 0,
            'total_features': 0,
            'group_results': [],
            'errors': []
        }
        
        import_service = DataImportService()
        
        for i, (group_name, group_config) in enumerate(layer_groups_to_import.items(), 1):
            self.stdout.write(f"\n📁 [{i}/{len(layer_groups_to_import)}] Importing layer group: {group_name}")
            self.stdout.write(f"   Name: {group_config.get('name', group_name)}")
            self.stdout.write(f"   Description: {group_config.get('description', 'No description')}")
            
            try:
                # Import this layer group
                group_data_dir = os.path.join(data_dir, group_name)
                
                group_result = import_service.import_layer_group(
                    city_slug=city.slug,
                    group_name=group_name,
                    data_directory=group_data_dir,
                    force=options.get('force', False)
                )
                
                if group_result.get('layers_imported', 0) > 0:
                    results['successful_groups'] += 1
                    results['successful_layers'] += group_result.get('layers_imported', 0)
                    results['total_features'] += group_result.get('total_features', 0)
                    self.stdout.write(f"   ✅ Success: {group_result['layers_imported']} layers, {group_result['total_features']} features")
                else:
                    results['failed_groups'] += 1
                    error_msg = f"{group_name}: {group_result.get('error', 'No layers imported')}"
                    results['errors'].append(error_msg)
                    self.stdout.write(f"   ❌ Failed: {group_result.get('error', 'No layers imported')}")
                
                results['total_layers'] += group_result.get('total_expected_layers', 0)
                results['failed_layers'] += group_result.get('layers_failed', 0)
                results['group_results'].append(group_result)
                
                # Show individual layer results if requested
                if group_result.get('layer_results'):
                    for layer_result in group_result['layer_results']:
                        if layer_result['success']:
                            self.stdout.write(f"     ✅ {layer_result['layer_slug']}: {layer_result['features_imported']} features")
                        else:
                            self.stdout.write(f"     ❌ {layer_result['layer_slug']}: {layer_result.get('error', 'Unknown error')}")
                
            except Exception as e:
                results['failed_groups'] += 1
                error_msg = f"{group_name}: {str(e)}"
                results['errors'].append(error_msg)
                self.stdout.write(f"   ❌ Error: {e}")
                
                results['group_results'].append({
                    'group_name': group_name,
                    'success': False,
                    'error': str(e)
                })
        
        return results

    def _display_import_results(self, results):
        """Display comprehensive import results"""
        self.stdout.write(f"\n📊 LAYER GROUP IMPORT RESULTS:")
        self.stdout.write(f"   City: {results['city']}")
        self.stdout.write(f"   Total layer groups: {results['total_groups']}")
        self.stdout.write(f"   Successful groups: {results['successful_groups']}")
        self.stdout.write(f"   Failed groups: {results['failed_groups']}")
        self.stdout.write(f"   Total layers: {results['total_layers']}")
        self.stdout.write(f"   Successful layers: {results['successful_layers']}")
        self.stdout.write(f"   Failed layers: {results['failed_layers']}")
        self.stdout.write(f"   Total features imported: {results['total_features']:,}")
        
        # Group details
        if results['group_results']:
            self.stdout.write(f"\n📁 Group Details:")
            for group_result in results['group_results']:
                if group_result.get('layers_imported', 0) > 0:
                    self.stdout.write(f"   ✅ {group_result['group_name']}: {group_result['layers_imported']} layers, {group_result['total_features']} features")
                else:
                    self.stdout.write(f"   ❌ {group_result['group_name']}: {group_result.get('error', 'No layers imported')}")
        
        # Errors
        if results['errors']:
            self.stdout.write(f"\n❌ Errors:")
            for error in results['errors'][:5]:  # Show first 5 errors
                self.stdout.write(f"   - {error}")
            if len(results['errors']) > 5:
                self.stdout.write(f"   ... and {len(results['errors']) - 5} more errors")
        
        # Success rate
        if results['total_groups'] > 0:
            success_rate = (results['successful_groups'] / results['total_groups']) * 100
            self.stdout.write(f"\n🎯 Success Rate: {success_rate:.1f}%")
        
        # Next steps
        if results['successful_groups'] > 0:
            self.stdout.write(f"\n🚀 Next Steps:")
            self.stdout.write(f"1. Generate combined tiles:")
            self.stdout.write(f"   python manage.py generate_direct_s3_tiles \\")
            self.stdout.write(f"       --city {results['city']} \\")
            self.stdout.write(f"       --layer-groups \"master_plan,highways,metro\" \\")
            self.stdout.write(f"       --type png \\")
            self.stdout.write(f"       --min-zoom 8 \\")
            self.stdout.write(f"       --max-zoom 12")
            
            self.stdout.write(f"\n2. Check layer status:")
            self.stdout.write(f"   python manage.py show_hierarchy --city {results['city']}")
        
        self.stdout.write(f"\n🎉 Import completed!")