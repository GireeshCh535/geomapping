# Comprehensive Validation and Fix Command
# File: maps/management/commands/validate_and_fix_city_data.py

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from maps.models import City, DataLayer, GeoFeature, CityLayerStyle, ImportJob
from maps.config import get_city_config
from collections import Counter, defaultdict
import json


class Command(BaseCommand):
    help = 'Comprehensive validation and fixing of city data with detailed reporting'

    def add_arguments(self, parser):
        parser.add_argument('--city', type=str, required=True, help='City slug (warangal, visakhapatnam, amaravati)')
        parser.add_argument('--fix-issues', action='store_true', help='Attempt to fix found issues')
        parser.add_argument('--export-report', action='store_true', help='Export detailed report to JSON')
        parser.add_argument('--missing-only', action='store_true', help='Only show missing data issues')

    def handle(self, *args, **options):
        city_slug = options['city']
        fix_issues = options.get('fix_issues', False)
        export_report = options.get('export_report', False)
        missing_only = options.get('missing_only', False)
        
        self.stdout.write(f"\n🔍 Comprehensive validation for {city_slug}")
        
        # Run validation
        validation_result = self._run_comprehensive_validation(city_slug, missing_only)
        
        # Display results
        self._display_validation_results(validation_result)
        
        # Fix issues if requested
        if fix_issues and validation_result['issues']:
            self._fix_issues(city_slug, validation_result['issues'])
        
        # Export report if requested
        if export_report:
            self._export_detailed_report(city_slug, validation_result)
        
        # Provide recommendations
        self._provide_recommendations(validation_result)

    def _run_comprehensive_validation(self, city_slug, missing_only=False):
        """Run comprehensive validation on city data"""
        
        try:
            city = City.objects.get(slug=city_slug)
        except City.DoesNotExist:
            return {'error': f"City not found: {city_slug}", 'issues': []}
        
        # Get city configuration
        config = get_city_config(city_slug)
        if not config:
            return {'error': f"No configuration found for {city_slug}", 'issues': []}
        
        # Initialize validation result
        result = {
            'city': city_slug,
            'timestamp': timezone.now().isoformat(),
            'config_found': True,
            'layers': {},
            'features': {},
            'styles': {},
            'issues': [],
            'summary': {}
        }
        
        # Validate layers
        self._validate_layers(city, result, missing_only)
        
        # Validate features
        self._validate_features(city, city_slug, result, missing_only)
        
        # Validate styles
        self._validate_styles(city, city_slug, result, missing_only)
        
        # Generate summary
        self._generate_validation_summary(result)
        
        return result

    def _validate_layers(self, city, result, missing_only):
        """Validate data layers"""
        
        layers = DataLayer.objects.filter(city=city)
        result['layers'] = {
            'total': layers.count(),
            'processed': layers.filter(is_processed=True).count(),
            'unprocessed': layers.filter(is_processed=False).count(),
            'with_features': layers.filter(feature_count__gt=0).count(),
            'empty': layers.filter(feature_count=0).count(),
            'details': []
        }
        
        for layer in layers:
            layer_info = {
                'name': layer.name,
                'slug': layer.slug,
                'category': layer.category.name if layer.category else 'No Category',
                'feature_count': layer.feature_count,
                'is_processed': layer.is_processed,
                'geometry_type': layer.geometry_type,
                'file_format': layer.file_format,
                'issues': []
            }
            
            # Check for issues
            if not layer.is_processed:
                layer_info['issues'].append('Layer not processed')
                result['issues'].append({
                    'type': 'layer_unprocessed',
                    'severity': 'high',
                    'layer': layer.name,
                    'message': f"Layer '{layer.name}' has not been processed"
                })
            
            if layer.feature_count == 0:
                layer_info['issues'].append('No features')
                result['issues'].append({
                    'type': 'layer_empty',
                    'severity': 'medium',
                    'layer': layer.name,
                    'message': f"Layer '{layer.name}' contains no features"
                })
            
            if not layer.category:
                layer_info['issues'].append('No category assigned')
                result['issues'].append({
                    'type': 'layer_no_category',
                    'severity': 'high',
                    'layer': layer.name,
                    'message': f"Layer '{layer.name}' has no category assigned"
                })
            
            result['layers']['details'].append(layer_info)

    def _validate_features(self, city, city_slug, result, missing_only):
        """Validate features with city-specific field requirements"""
        
        # Get field mappings for this city
        field_mappings = {
            'warangal': {
                'category_field': 'PLU',
                'name_field': 'PLU_NAME',
                'authority_field': 'KUDA',
                'area_field': 'Area',
                'required_fields': ['PLU', 'PLU_NAME', 'OBJECTID']
            },
            'visakhapatnam': {
                'category_field': 'Category',
                'name_field': 'Category',
                'district_field': 'DISTRICT',
                'mandal_field': 'MANDAL',
                'required_fields': ['Category', 'FID']
            },
            'amaravati': {
                'category_field': 'symbology',
                'name_field': 'plot_categ',
                'plot_field': 'plot_no',
                'township_field': 'township',
                'required_fields': ['symbology', 'plot_categ', 'OBJECTID']
            }
        }
        
        mapping = field_mappings.get(city_slug, {})
        
        features = GeoFeature.objects.filter(layer__city=city)
        result['features'] = {
            'total': features.count(),
            'valid_geometry': features.exclude(geometry__isnull=True).count(),
            'missing_geometry': features.filter(geometry__isnull=True).count(),
            'with_attributes': features.exclude(source_attributes__isnull=True).count(),
            'missing_attributes': features.filter(source_attributes__isnull=True).count(),
            'field_analysis': {},
            'sample_attributes': []
        }
        
        # Analyze required fields
        if mapping and mapping.get('required_fields'):
            for field in mapping['required_fields']:
                field_stats = self._analyze_field_presence(features, field)
                result['features']['field_analysis'][field] = field_stats
                
                if field_stats['missing_count'] > 0:
                    result['issues'].append({
                        'type': 'missing_required_field',
                        'severity': 'high',
                        'field': field,
                        'missing_count': field_stats['missing_count'],
                        'total_features': field_stats['total_count'],
                        'message': f"Field '{field}' missing in {field_stats['missing_count']} features"
                    })
        
        # Sample attributes for analysis
        sample_features = features.exclude(source_attributes__isnull=True)[:10]
        for feature in sample_features:
            result['features']['sample_attributes'].append({
                'layer': feature.layer.name,
                'attributes': feature.source_attributes
            })
        
        # Check geometry issues
        if result['features']['missing_geometry'] > 0:
            result['issues'].append({
                'type': 'missing_geometry',
                'severity': 'critical',
                'count': result['features']['missing_geometry'],
                'message': f"{result['features']['missing_geometry']} features missing geometry"
            })

    def _analyze_field_presence(self, features, field_name):
        """Analyze presence of a specific field in features"""
        total_count = 0
        present_count = 0
        missing_count = 0
        sample_values = []
        
        for feature in features.iterator():
            total_count += 1
            if feature.source_attributes and field_name in feature.source_attributes:
                present_count += 1
                value = feature.source_attributes[field_name]
                if value and len(sample_values) < 5:
                    sample_values.append(str(value)[:50])
            else:
                missing_count += 1
        
        return {
            'total_count': total_count,
            'present_count': present_count,
            'missing_count': missing_count,
            'presence_rate': (present_count / total_count * 100) if total_count > 0 else 0,
            'sample_values': list(set(sample_values))
        }

    def _validate_styles(self, city, city_slug, result, missing_only):
        """Validate styling configuration"""
        
        styles = CityLayerStyle.objects.filter(city=city)
        layers = DataLayer.objects.filter(city=city, is_processed=True)
        
        result['styles'] = {
            'total_styles': styles.count(),
            'layers_with_styles': 0,
            'layers_without_styles': 0,
            'no_border_compliance': 0,
            'pattern_support': 0,
            'color_compliance': 0,
            'details': []
        }
        
        layers_with_styles = 0
        layers_without_styles = 0
        
        for layer in layers:
            layer_style_info = {
                'layer_name': layer.name,
                'category': layer.category.name if layer.category else 'No Category',
                'has_style': False,
                'style_details': {},
                'issues': []
            }
            
            # Check if layer has a style
            try:
                style = CityLayerStyle.objects.get(city=city, category=layer.category)
                layer_style_info['has_style'] = True
                layers_with_styles += 1
                
                layer_style_info['style_details'] = {
                    'fill_color': style.fill_color,
                    'stroke_width': style.stroke_width,
                    'opacity': style.opacity,
                    'pattern': getattr(style, 'fill_pattern', 'SOLID'),
                    'pattern_color': getattr(style, 'pattern_color', None)
                }
                
                # Validate no-border requirement
                if style.stroke_width == 0:
                    result['styles']['no_border_compliance'] += 1
                else:
                    layer_style_info['issues'].append(f'Border width: {style.stroke_width} (should be 0)')
                    result['issues'].append({
                        'type': 'border_not_zero',
                        'severity': 'medium',
                        'layer': layer.name,
                        'current_width': style.stroke_width,
                        'message': f"Layer '{layer.name}' has border width {style.stroke_width}, should be 0"
                    })
                
                # Check pattern support
                if hasattr(style, 'fill_pattern') and style.fill_pattern != 'SOLID':
                    result['styles']['pattern_support'] += 1
                
            except CityLayerStyle.DoesNotExist:
                layers_without_styles += 1
                layer_style_info['issues'].append('No style configured')
                result['issues'].append({
                    'type': 'no_style',
                    'severity': 'high',
                    'layer': layer.name,
                    'category': layer.category.name if layer.category else 'No Category',
                    'message': f"Layer '{layer.name}' has no style configuration"
                })
            
            result['styles']['details'].append(layer_style_info)
        
        result['styles']['layers_with_styles'] = layers_with_styles
        result['styles']['layers_without_styles'] = layers_without_styles

    def _generate_validation_summary(self, result):
        """Generate validation summary"""
        
        total_issues = len(result['issues'])
        critical_issues = len([i for i in result['issues'] if i.get('severity') == 'critical'])
        high_issues = len([i for i in result['issues'] if i.get('severity') == 'high'])
        medium_issues = len([i for i in result['issues'] if i.get('severity') == 'medium'])
        
        issue_types = Counter(issue['type'] for issue in result['issues'])
        
        result['summary'] = {
            'total_issues': total_issues,
            'critical_issues': critical_issues,
            'high_issues': high_issues,
            'medium_issues': medium_issues,
            'issue_breakdown': dict(issue_types),
            'data_completeness': {
                'processed_layers': result['layers']['processed'] / result['layers']['total'] * 100 if result['layers']['total'] > 0 else 0,
                'layers_with_features': result['layers']['with_features'] / result['layers']['total'] * 100 if result['layers']['total'] > 0 else 0,
                'features_with_geometry': result['features']['valid_geometry'] / result['features']['total'] * 100 if result['features']['total'] > 0 else 0,
                'layers_with_styles': result['styles']['layers_with_styles'] / result['layers']['processed'] * 100 if result['layers']['processed'] > 0 else 0
            }
        }

    def _display_validation_results(self, result):
        """Display validation results in a user-friendly format"""
        
        if result.get('error'):
            self.stdout.write(self.style.ERROR(f"❌ {result['error']}"))
            return
        
        summary = result['summary']
        
        self.stdout.write(f"\n📊 Validation Summary for {result['city']}")
        self.stdout.write(f"   Timestamp: {result['timestamp']}")
        
        # Issues summary
        if summary['total_issues'] == 0:
            self.stdout.write(self.style.SUCCESS("✅ No issues found!"))
        else:
            self.stdout.write(f"\n⚠️  Found {summary['total_issues']} issues:")
            if summary['critical_issues'] > 0:
                self.stdout.write(self.style.ERROR(f"   🔴 Critical: {summary['critical_issues']}"))
            if summary['high_issues'] > 0:
                self.stdout.write(self.style.WARNING(f"   🟠 High: {summary['high_issues']}"))
            if summary['medium_issues'] > 0:
                self.stdout.write(f"   🟡 Medium: {summary['medium_issues']}")
        
        # Data completeness
        self.stdout.write(f"\n📈 Data Completeness:")
        completeness = summary['data_completeness']
        self.stdout.write(f"   • Processed layers: {completeness['processed_layers']:.1f}%")
        self.stdout.write(f"   • Layers with features: {completeness['layers_with_features']:.1f}%")
        self.stdout.write(f"   • Features with geometry: {completeness['features_with_geometry']:.1f}%")
        self.stdout.write(f"   • Layers with styles: {completeness['layers_with_styles']:.1f}%")
        
        # Issue breakdown
        if summary['issue_breakdown']:
            self.stdout.write(f"\n🔍 Issue Breakdown:")
            for issue_type, count in summary['issue_breakdown'].items():
                self.stdout.write(f"   • {issue_type}: {count}")
        
        # Detailed issues (first 10)
        if result['issues']:
            self.stdout.write(f"\n📝 Detailed Issues (showing first 10):")
            for issue in result['issues'][:10]:
                severity_icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡'}.get(issue.get('severity'), '🔵')
                self.stdout.write(f"   {severity_icon} {issue['message']}")
            
            if len(result['issues']) > 10:
                self.stdout.write(f"   ... and {len(result['issues']) - 10} more issues")

    def _fix_issues(self, city_slug, issues):
        """Attempt to fix identified issues"""
        
        self.stdout.write(f"\n🔧 Attempting to fix issues for {city_slug}")
        
        fixed_count = 0
        
        with transaction.atomic():
            city = City.objects.get(slug=city_slug)
            
            for issue in issues:
                if issue['type'] == 'border_not_zero':
                    # Fix border width
                    try:
                        layer = DataLayer.objects.get(city=city, name=issue['layer'])
                        style = CityLayerStyle.objects.get(city=city, category=layer.category)
                        style.stroke_width = 0
                        style.save()
                        self.stdout.write(f"   ✅ Fixed border width for {issue['layer']}")
                        fixed_count += 1
                    except Exception as e:
                        self.stdout.write(f"   ❌ Could not fix border for {issue['layer']}: {e}")
                
                elif issue['type'] == 'no_style':
                    # Create basic style
                    try:
                        layer = DataLayer.objects.get(city=city, name=issue['layer'])
                        if layer.category:
                            CityLayerStyle.objects.get_or_create(
                                city=city,
                                category=layer.category,
                                defaults={
                                    'fill_color': '#666666',
                                    'stroke_color': '#666666',
                                    'stroke_width': 0,
                                    'opacity': 0.8,
                                    'is_visible': True
                                }
                            )
                            self.stdout.write(f"   ✅ Created basic style for {issue['layer']}")
                            fixed_count += 1
                    except Exception as e:
                        self.stdout.write(f"   ❌ Could not create style for {issue['layer']}: {e}")
        
        self.stdout.write(f"\n📊 Fixed {fixed_count} out of {len(issues)} issues")

    def _export_detailed_report(self, city_slug, result):
        """Export detailed validation report to JSON"""
        
        report_filename = f"/tmp/{city_slug}_validation_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(report_filename, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            
            self.stdout.write(f"\n💾 Detailed report exported to: {report_filename}")
            
        except Exception as e:
            self.stdout.write(f"❌ Could not export report: {e}")

    def _provide_recommendations(self, result):
        """Provide recommendations based on validation results"""
        
        self.stdout.write(f"\n💡 Recommendations:")
        
        summary = result['summary']
        
        if summary['critical_issues'] > 0:
            self.stdout.write("   🔴 URGENT: Fix critical issues first (missing geometry, etc.)")
        
        if summary['data_completeness']['processed_layers'] < 100:
            self.stdout.write("   📥 Process unprocessed layers")
        
        if summary['data_completeness']['layers_with_styles'] < 100:
            self.stdout.write("   🎨 Set up styles for all layers")
        
        if result['styles']['no_border_compliance'] < result['styles']['layers_with_styles']:
            self.stdout.write("   📐 Set stroke_width=0 for all styles (no borders requirement)")
        
        # Provide specific commands
        self.stdout.write(f"\n🛠️  Suggested Commands:")
        self.stdout.write(f"   • Fix issues: python manage.py validate_and_fix_city_data --city={result['city']} --fix-issues")
        self.stdout.write(f"   • Setup styles: python manage.py setup_enhanced_cities --city={result['city']} --force-update")
        self.stdout.write(f"   • Generate tiles: python manage.py generate_direct_s3_tiles --city={result['city']}")
        self.stdout.write(f"   • Re-validate: python manage.py validate_and_fix_city_data --city={result['city']}")


# Usage examples:
# python manage.py validate_and_fix_city_data --city=warangal
# python manage.py validate_and_fix_city_data --city=visakhapatnam --fix-issues
# python manage.py validate_and_fix_city_data --city=amaravati --export-report
# python manage.py validate_and_fix_city_data --city=warangal --missing-only