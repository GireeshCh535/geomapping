# Enhanced City Setup Command with Pattern Support and Validation
# File: maps/management/commands/setup_enhanced_cities.py

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from maps.models import City, LayerCategory, CityLayerStyle, DataLayer, GeoFeature, ImportJob
from collections import defaultdict, Counter
from maps.config import get_city_config
import json


class Command(BaseCommand):
    help = 'Setup enhanced city styles with patterns, no borders, exact colors, and validation'

    def add_arguments(self, parser):
        parser.add_argument('--city', type=str, help='City slug (warangal, visakhapatnam, amaravati)')
        parser.add_argument('--validate-only', action='store_true', help='Only run validation without applying styles')
        parser.add_argument('--generate-report', action='store_true', help='Generate detailed validation report')
        parser.add_argument('--force-update', action='store_true', help='Force update existing styles')

    def handle(self, *args, **options):
        city_slug = options.get('city')
        
        if city_slug:
            if options.get('validate_only'):
                self._validate_city_features(city_slug)
            else:
                self._setup_enhanced_city_styles(city_slug, options.get('force_update', False))
                if options.get('generate_report'):
                    self._generate_validation_report(city_slug)
        else:
            self.stdout.write("Setting up all supported cities...")
            for slug in ['warangal', 'visakhapatnam', 'amaravati']:
                self._setup_enhanced_city_styles(slug, options.get('force_update', False))

    def _setup_enhanced_city_styles(self, city_slug, force_update=False):
        """Setup enhanced styles with patterns, no borders, and exact colors"""
        self.stdout.write(f"\n🎨 Setting up enhanced styles for {city_slug}")
        
        # Get city configuration
        config = get_city_config(city_slug)
        if not config:
            self.stdout.write(self.style.ERROR(f"❌ No configuration found for {city_slug}"))
            return
        
        try:
            city = City.objects.get(slug=city_slug)
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            return
        
        # Get enhanced color specifications with patterns
        enhanced_specs = self._get_enhanced_color_specifications(city_slug, config)
        
        validation_issues = []
        styles_created = 0
        styles_updated = 0
        
        with transaction.atomic():
            for spec in enhanced_specs:
                layer_name = spec['name']
                
                # Find or create category
                category = self._find_or_create_category(layer_name, spec.get('category_code'))
                if not category:
                    validation_issues.append({
                        'type': 'category_not_found',
                        'layer': layer_name,
                        'message': f"Could not find or create category for {layer_name}"
                    })
                    continue
                
                # Create or update style with enhanced pattern support
                style, created = CityLayerStyle.objects.get_or_create(
                    city=city,
                    category=category,
                    defaults={
                        'fill_color': spec['color'],
                        'stroke_color': spec['color'],  # Same as fill for seamless look
                        'stroke_width': 0,  # NO BORDERS as requested
                        'opacity': spec.get('opacity', 0.8),
                        'is_visible': True,
                        'min_zoom': 8,
                        'max_zoom': 18,
                        # Pattern support
                        'fill_pattern': spec.get('pattern', 'SOLID'),
                        'pattern_color': spec.get('pattern_color', spec['color']),
                        'pattern_density': spec.get('pattern_density', 10),
                        'pattern_rotation': spec.get('pattern_rotation', 0.0),
                    }
                )
                
                if not created and force_update:
                    # Update existing style
                    style.fill_color = spec['color']
                    style.stroke_color = spec['color']
                    style.stroke_width = 0  # Ensure no borders
                    style.opacity = spec.get('opacity', 0.8)
                    style.fill_pattern = spec.get('pattern', 'SOLID')
                    style.pattern_color = spec.get('pattern_color', spec['color'])
                    style.pattern_density = spec.get('pattern_density', 10)
                    style.pattern_rotation = spec.get('pattern_rotation', 0.0)
                    style.save()
                    styles_updated += 1
                    self.stdout.write(f"   🔄 Updated: {layer_name} → {spec['color']} ({spec.get('pattern', 'solid')})")
                elif created:
                    styles_created += 1
                    pattern_info = f" ({spec.get('pattern', 'solid')})" if spec.get('pattern') != 'SOLID' else ""
                    self.stdout.write(f"   ✅ Created: {layer_name} → {spec['color']}{pattern_info}")
                else:
                    self.stdout.write(f"   ⏭️  Skipped (exists): {layer_name}")
        
        # Validate feature coverage and styling
        missing_features = self._validate_feature_coverage(city, city_slug)
        validation_issues.extend(missing_features)
        
        # Display results
        self.stdout.write(f"\n📊 Enhanced Style Setup Results for {city_slug}:")
        self.stdout.write(f"   • Styles created: {styles_created}")
        self.stdout.write(f"   • Styles updated: {styles_updated}")
        self.stdout.write(f"   • Total specifications: {len(enhanced_specs)}")
        self.stdout.write(f"   • Validation issues: {len(validation_issues)}")
        
        if validation_issues:
            self.stdout.write(f"\n⚠️  Validation Issues Found:")
            issue_summary = Counter(issue['type'] for issue in validation_issues)
            for issue_type, count in issue_summary.items():
                self.stdout.write(f"   • {issue_type}: {count}")
            
            # Show first few detailed issues
            for issue in validation_issues[:5]:
                self.stdout.write(f"     - {issue['message']}")
            
            if len(validation_issues) > 5:
                self.stdout.write(f"     ... and {len(validation_issues) - 5} more issues")
        
        # Save validation report
        self._save_validation_report(city_slug, validation_issues, {
            'styles_created': styles_created,
            'styles_updated': styles_updated,
            'total_specs': len(enhanced_specs)
        })

    def _get_enhanced_color_specifications(self, city_slug, config):
        """Get enhanced color specifications with pattern support from config"""
        specs = []
        
        if city_slug == 'warangal':
            # Warangal specifications based on your requirements and config
            warangal_specs = [
                {'name': 'Agriculture', 'color': '#D3FFBE', 'pattern': 'HATCH', 'pattern_color': '#FFFFFF', 'category_code': 'AGRICULTURAL'},
                {'name': 'Air Strip', 'color': '#FFFFFF', 'pattern': 'SOLID', 'pattern_color': '#FF00C5', 'category_code': 'TRANSPORT'},
                {'name': 'Commercial', 'color': '#0070FF', 'category_code': 'COMMERCIAL'},
                {'name': 'Forest', 'color': '#267300', 'category_code': 'PROTECTED'},
                {'name': 'Growth Corridor', 'color': '#FFBEE8', 'category_code': 'SPECIAL'},
                {'name': 'Growth Corridor 2', 'color': '#FF73DF', 'category_code': 'SPECIAL'},
                {'name': 'Heritage', 'color': '#732600', 'pattern': 'HATCH', 'pattern_color': '#FFA77F', 'category_code': 'CULTURAL'},
                {'name': 'Hill Buffer', 'color': '#55FF00', 'category_code': 'PARKS_GREEN'},
                {'name': 'Hillocks', 'color': '#A87000', 'category_code': 'PROTECTED'},
                {'name': 'Industrial', 'color': '#C500FF', 'category_code': 'INDUSTRIAL'},
                {'name': 'Mixed Use', 'color': '#FFAA00', 'category_code': 'MIXED_USE'},
                {'name': 'Public & Semi-Public', 'color': '#FF0000', 'category_code': 'PUBLIC'},
                {'name': 'Public Utilities', 'color': '#FF0000', 'pattern': 'HATCH', 'pattern_color': '#E69800', 'category_code': 'UTILITIES'},
                {'name': 'Railway Land', 'color': '#CCCCCC', 'category_code': 'TRANSPORT'},
                {'name': 'Recreational', 'color': '#55FF00', 'category_code': 'PARKS_GREEN'},
                {'name': 'Residential', 'color': '#FFFF00', 'category_code': 'RESIDENTIAL'},
                {'name': 'Residential Expansion', 'color': '#9C9C9C', 'category_code': 'RESIDENTIAL'},
                {'name': 'Road Buffer', 'color': '#4E4E4E', 'category_code': 'TRANSPORT'},
                {'name': 'Transportation', 'color': '#B2B2B2', 'category_code': 'TRANSPORT'},
                {'name': 'Water Bodies', 'color': '#00C5FF', 'category_code': 'WATER_BODIES'},
                {'name': 'Water Body Buffer', 'color': '#55FF00', 'category_code': 'PARKS_GREEN'},
                {'name': 'Zoological park', 'color': '#38A800', 'category_code': 'PARKS_GREEN'},
            ]
            specs.extend(warangal_specs)
            
        elif city_slug == 'visakhapatnam':
            # Visakhapatnam specifications
            vizag_specs = [
                {'name': 'Agricultural Use Zone', 'color': '#D3FFBE', 'category_code': 'AGRICULTURAL'},
                {'name': 'Blue Zone Water Bodies', 'color': '#73FFDF', 'category_code': 'WATER_BODIES'},
                {'name': 'Brown Zone Hills', 'color': '#A87000', 'category_code': 'PROTECTED'},
                {'name': 'Commercial Use Zone', 'color': '#004DA8', 'category_code': 'COMMERCIAL'},
                {'name': 'Existing Crematorium / Burial Ground / Graveyard', 'color': '#FFFFFF', 'pattern': 'HATCH', 'pattern_color': '#FF0000', 'category_code': 'CEMETERY'},
                {'name': 'Existing Educational Facilities', 'color': '#FF0000', 'pattern': 'HATCH', 'pattern_color': '#000000', 'category_code': 'EDUCATION'},
                {'name': 'Existing Government / Semi Government Facilities', 'color': '#FF0000', 'category_code': 'GOVERNMENT'},
                {'name': 'Existing Health Facilities', 'color': '#FF0000', 'pattern': 'DOT', 'pattern_color': '#CCCCCC', 'category_code': 'HEALTHCARE'},
                {'name': 'Proposed Industrial Use Zone', 'color': '#C500FF', 'pattern': 'HATCH', 'pattern_color': '#FFFFFF', 'category_code': 'INDUSTRIAL'},
                {'name': 'Existing Industrial Area', 'color': '#C500FF', 'category_code': 'INDUSTRIAL'},
                {'name': 'Existing Public Utilities', 'color': '#FF7F7F', 'pattern': 'HATCH', 'pattern_color': '#E60000', 'category_code': 'UTILITIES'},
                {'name': 'Existing Recreational / Playgrounds / Parks / Layout Open Space', 'color': '#55FF00', 'category_code': 'PARKS_GREEN'},
                {'name': 'Existing Religious Facilities', 'color': '#FF0000', 'pattern': 'HATCH', 'pattern_color': '#55FF00', 'category_code': 'RELIGIOUS'},
                {'name': 'Existing Road / Railway Line Area', 'color': '#828282', 'pattern': 'HATCH', 'category_code': 'TRANSPORT'},
                {'name': 'Existing Transportation Facility', 'color': '#686868', 'category_code': 'TRANSPORT'},
                {'name': 'Green Zone Forest', 'color': '#00734C', 'category_code': 'PROTECTED'},
                {'name': 'Kambalakonda Eco Sensitive Zone / NAOB Buffer / Zoological Park', 'color': '#D7C29E', 'category_code': 'PROTECTED'},
                {'name': 'Kambalakonda WildLife Sanctuary / Biodiversity Area', 'color': '#38A800', 'category_code': 'PROTECTED'},
                {'name': 'Mixed Use Zone 1', 'color': '#FFAA00', 'category_code': 'MIXED_USE'},
                {'name': 'Mixed Use Zone 2', 'color': '#FFD37F', 'category_code': 'MIXED_USE'},
                {'name': 'Mixed Use Zone 3', 'color': '#E69800', 'pattern': 'HATCH', 'pattern_color': '#E1E1E1', 'category_code': 'MIXED_USE'},
                {'name': 'Mixed Use Zone 4', 'color': '#FFAA00', 'pattern': 'DOT', 'pattern_color': '#000000', 'category_code': 'MIXED_USE'},
                {'name': 'Proposed PSP Use Zone', 'color': '#FF0000', 'pattern': 'HATCH', 'category_code': 'PUBLIC'},
                {'name': 'Proposed Public Utilities Use Zone', 'color': '#F57A7A', 'pattern': 'HATCH', 'pattern_color': '#FFFFFF', 'category_code': 'UTILITIES'},
                {'name': 'Proposed Recreational Use Zone', 'color': '#4C7300', 'category_code': 'PARKS_GREEN'},
                {'name': 'Proposed Road Network', 'color': '#000000', 'category_code': 'TRANSPORT'},
                {'name': 'Proposed Transportation Facility Use Zone', 'color': '#343434', 'pattern': 'HATCH', 'pattern_color': '#FFFFFF', 'category_code': 'TRANSPORT'},
                {'name': 'Residential Use Zone', 'color': '#FFFF73', 'category_code': 'RESIDENTIAL'},
                {'name': 'Sea / River / Accreted Land', 'color': '#D7C29E', 'pattern': 'DOT', 'pattern_color': '#E39E00', 'category_code': 'WATER_BODIES'},
                {'name': 'Special Area Use Zone', 'color': '#FFFFFF', 'pattern': 'HATCH', 'pattern_color': '#002673', 'category_code': 'SPECIAL'},
                {'name': 'Water Body Buffer', 'color': '#4CE600', 'pattern': 'DOT', 'pattern_color': '#267300', 'category_code': 'PARKS_GREEN'},
            ]
            specs.extend(vizag_specs)
            
        elif city_slug == 'amaravati':
            # Amaravati specifications
            amaravati_specs = [
                {'name': 'Burial Ground', 'color': '#FFFFFF', 'pattern': 'DOT', 'pattern_color': '#E39E00', 'category_code': 'CEMETERY'},
                {'name': 'C1 - Mixed Use Zone', 'color': '#73B2FF', 'category_code': 'MIXED_USE'},
                {'name': 'C2 - General Commercial Zone', 'color': '#00C5FF', 'stroke_override': '#000000', 'category_code': 'COMMERCIAL'},
                {'name': 'C3 - Neighbourhood Centre Zone', 'color': '#00C5FF', 'category_code': 'COMMERCIAL'},
                {'name': 'C4 - Town Centre Zone', 'color': '#00A9E6', 'category_code': 'COMMERCIAL'},
                {'name': 'C5 - Regional Centre Zone', 'color': '#0070FF', 'category_code': 'COMMERCIAL'},
                {'name': 'C6 - Central Business District Zone', 'color': '#005CE6', 'category_code': 'COMMERCIAL'},
                {'name': 'Commercial Vacant', 'color': '#C5E2FF', 'category_code': 'COMMERCIAL'},
                {'name': 'I1 - Business Park Zone', 'color': '#FFBEE8', 'category_code': 'INDUSTRIAL'},
                {'name': 'I2 - Logistics Zone', 'color': '#FF73DF', 'category_code': 'INDUSTRIAL'},
                {'name': 'I3 - Non Polluting Industry Zone', 'color': '#A900E6', 'category_code': 'INDUSTRIAL'},
                {'name': 'P1 - Passive Zone', 'color': '#267300', 'category_code': 'PROTECTED'},
                {'name': 'P2 - Active Zone', 'color': '#38A800', 'category_code': 'PARKS_GREEN'},
                {'name': 'P3 - Protected Zone', 'color': '#BEE8FF', 'category_code': 'PROTECTED'},
                {'name': 'P3 - Protected Zone Hills', 'color': '#4C7300', 'category_code': 'PROTECTED'},
                {'name': 'PGN-G', 'color': '#4C7300', 'category_code': 'PARKS_GREEN'},
                {'name': 'PGN-V', 'color': '#897044', 'category_code': 'PARKS_GREEN'},
                {'name': 'R1 - Village Planning Zone', 'color': '#FFFFFF', 'pattern': 'HATCH', 'pattern_color': '#000000', 'category_code': 'RESIDENTIAL'},
                {'name': 'R3 - Medium to High Density Zone', 'color': '#F5CA7A', 'category_code': 'RESIDENTIAL'},
                {'name': 'R4 - High Density Zone', 'color': '#E69800', 'category_code': 'RESIDENTIAL'},
                {'name': 'RAA', 'color': '#FFAA00', 'category_code': 'RESIDENTIAL'},
                {'name': 'Residential Vacant', 'color': '#FFD37F', 'category_code': 'RESIDENTIAL'},
                {'name': 'S2 - Education Zone', 'color': '#FF7F7F', 'category_code': 'EDUCATION'},
                {'name': 'S3 - Special Zone', 'color': '#D7B09E', 'category_code': 'SPECIAL'},
                {'name': 'SC1a - Mixed Use', 'color': '#0070FF', 'category_code': 'MIXED_USE'},
                {'name': 'SC1b - Mixed Use', 'color': '#73B2FF', 'category_code': 'MIXED_USE'},
                {'name': 'SP1 - Passive Zone', 'color': '#267300', 'category_code': 'PROTECTED'},
                {'name': 'SP2 - Active Zone', 'color': '#38A800', 'category_code': 'PARKS_GREEN'},
                {'name': 'SP3 - Protected Zone', 'color': '#00C5FF', 'category_code': 'PROTECTED'},
                {'name': 'SR2 - Low Density Housing', 'color': '#FFFFBE', 'category_code': 'RESIDENTIAL'},
                {'name': 'SR4 - High Density Private', 'color': '#FFAA00', 'category_code': 'RESIDENTIAL'},
                {'name': 'SS1 - Government Zone', 'color': '#E60000', 'category_code': 'GOVERNMENT'},
                {'name': 'SS2a - Education Zone', 'color': '#FF7F7F', 'category_code': 'EDUCATION'},
                {'name': 'SS2b - Cultural Zone', 'color': '#C500FF', 'category_code': 'CULTURAL'},
                {'name': 'SS2c - Health Zone', 'color': '#D3FFBE', 'category_code': 'HEALTHCARE'},
                {'name': 'SS3 - Special Zone', 'color': '#A83800', 'category_code': 'SPECIAL'},
                {'name': 'SU1 - Reserve Zone', 'color': '#E1E1E1', 'category_code': 'UTILITIES'},
                {'name': 'SU2 - Road Network', 'color': '#FFFFFF', 'stroke_override': '#000000', 'category_code': 'TRANSPORT'},
                {'name': 'U1 - Reserve Zone', 'color': '#CCCCCC', 'category_code': 'UTILITIES'},
                {'name': 'U2 - Road Reserve Zone', 'color': '#000000', 'category_code': 'TRANSPORT'},
            ]
            specs.extend(amaravati_specs)
        
        return specs

    def _find_or_create_category(self, layer_name, category_code=None):
        """Find or create appropriate category for a layer"""
        if category_code:
            try:
                return LayerCategory.objects.get(code=category_code)
            except LayerCategory.DoesNotExist:
                # Create the category if it doesn't exist
                category = LayerCategory.objects.create(
                    code=category_code,
                    name=layer_name,
                    description=f"Auto-created for {layer_name}",
                    default_color='#666666'
                )
                self.stdout.write(f"✅ Created new category: {category_code}")
                return category
        
        # Fallback to name-based mapping
        name_to_category = {
            'Agriculture': 'AGRICULTURAL', 'Agricultural Use Zone': 'AGRICULTURAL',
            'Commercial': 'COMMERCIAL', 'Commercial Use Zone': 'COMMERCIAL',
            'Industrial': 'INDUSTRIAL', 'Existing Industrial Area': 'INDUSTRIAL',
            'Residential': 'RESIDENTIAL', 'Residential Use Zone': 'RESIDENTIAL',
            # ... add more mappings as needed
        }
        
        category_code = name_to_category.get(layer_name)
        if category_code:
            try:
                return LayerCategory.objects.get(code=category_code)
            except LayerCategory.DoesNotExist:
                pass
        
        self.stdout.write(f"⚠️  Could not find/create category for: {layer_name}")
        return None

    def _validate_feature_coverage(self, city, city_slug):
        """Validate that all features have proper styling and data"""
        validation_issues = []
        
        # Get data field mappings based on city
        field_mappings = {
            'warangal': {'category_field': 'PLU', 'name_field': 'PLU_NAME'},
            'visakhapatnam': {'category_field': 'Category', 'name_field': 'Category'},
            'amaravati': {'category_field': 'symbology', 'name_field': 'plot_categ'},
        }
        
        mapping = field_mappings.get(city_slug)
        if not mapping:
            validation_issues.append({
                'type': 'unsupported_city',
                'message': f"No field mapping defined for city: {city_slug}"
            })
            return validation_issues
        
        # Check layers and features
        layers = DataLayer.objects.filter(city=city, is_processed=True)
        
        for layer in layers:
            # Check if layer has a style
            try:
                layer.get_style()
            except:
                validation_issues.append({
                    'type': 'layer_no_style',
                    'layer': layer.name,
                    'message': f"Layer {layer.name} has no associated style"
                })
            
            # Sample some features to check data quality
            features = GeoFeature.objects.filter(layer=layer)[:100]  # Sample first 100
            
            missing_category_field = 0
            missing_geometry = 0
            
            for feature in features:
                # Check if category field exists in source_attributes
                if mapping['category_field'] not in (feature.source_attributes or {}):
                    missing_category_field += 1
                
                # Check geometry
                if not feature.geometry:
                    missing_geometry += 1
            
            if missing_category_field > 0:
                validation_issues.append({
                    'type': 'missing_category_field',
                    'layer': layer.name,
                    'message': f"Layer {layer.name}: {missing_category_field} features missing {mapping['category_field']} field"
                })
            
            if missing_geometry > 0:
                validation_issues.append({
                    'type': 'missing_geometry',
                    'layer': layer.name,
                    'message': f"Layer {layer.name}: {missing_geometry} features missing geometry"
                })
        
        return validation_issues

    def _validate_city_features(self, city_slug):
        """Validate city features and report issues"""
        self.stdout.write(f"\n🔍 Validating features for {city_slug}")
        
        try:
            city = City.objects.get(slug=city_slug)
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            return
        
        validation_issues = self._validate_feature_coverage(city, city_slug)
        
        if not validation_issues:
            self.stdout.write(self.style.SUCCESS("✅ No validation issues found!"))
        else:
            self.stdout.write(f"⚠️  Found {len(validation_issues)} validation issues:")
            
            issue_summary = Counter(issue['type'] for issue in validation_issues)
            for issue_type, count in issue_summary.items():
                self.stdout.write(f"   • {issue_type}: {count}")
            
            # Show detailed issues
            for issue in validation_issues:
                self.stdout.write(f"     - {issue['message']}")

    def _save_validation_report(self, city_slug, validation_issues, stats):
        """Save validation report using existing ImportJob fields"""
        try:
            city = City.objects.get(slug=city_slug)
            
            # Use existing error_details field to store validation info
            validation_data = {
                'validation_issues': validation_issues,
                'stats': stats,
                'timestamp': timezone.now().isoformat(),
                'type': 'style_setup_validation'
            }
            
            # Create record using ONLY existing fields
            ImportJob.objects.create(
                city=city,
                filename=f'style_setup_{timezone.now().strftime("%Y%m%d_%H%M%S")}',
                file_format='VALIDATION',
                status='COMPLETED',
                features_imported=stats.get('styles_created', 0),
                features_failed=len(validation_issues),
                error_details=[validation_data],  # Use existing JSONField
                completed_at=timezone.now(),
                category_mapped='STYLE_SETUP'
            )
            
            self.stdout.write(f"💾 Validation report saved for {city_slug}")
        except Exception as e:
            # If saving fails, just skip it - the main functionality still works
            self.stdout.write(f"⚠️  Skipped saving validation report: {e}")

    def _generate_validation_report(self, city_slug):
        """Generate detailed validation report"""
        self.stdout.write(f"\n📋 Generating validation report for {city_slug}")
        
        try:
            city = City.objects.get(slug=city_slug)
            
            # Collect comprehensive statistics
            layers = DataLayer.objects.filter(city=city)
            features = GeoFeature.objects.filter(layer__city=city)
            styles = CityLayerStyle.objects.filter(city=city)
            
            report = {
                'city': city_slug,
                'timestamp': timezone.now().isoformat(),
                'summary': {
                    'total_layers': layers.count(),
                    'processed_layers': layers.filter(is_processed=True).count(),
                    'total_features': features.count(),
                    'total_styles': styles.count(),
                },
                'layer_details': [],
                'validation_issues': []
            }
            
            # Detailed layer analysis
            for layer in layers:
                layer_features = features.filter(layer=layer)
                layer_info = {
                    'name': layer.name,
                    'feature_count': layer_features.count(),
                    'has_style': CityLayerStyle.objects.filter(city=city, category=layer.category).exists(),
                    'geometry_type': layer.geometry_type,
                    'is_processed': layer.is_processed
                }
                report['layer_details'].append(layer_info)
            
            # Validation issues
            validation_issues = self._validate_feature_coverage(city, city_slug)
            report['validation_issues'] = validation_issues
            
            # Save report as JSON
            report_path = f"/tmp/{city_slug}_validation_report.json"
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            self.stdout.write(f"📄 Validation report saved to: {report_path}")
            
            # Display summary
            self.stdout.write(f"\n📊 Validation Report Summary:")
            self.stdout.write(f"   • Total layers: {report['summary']['total_layers']}")
            self.stdout.write(f"   • Processed layers: {report['summary']['processed_layers']}")
            self.stdout.write(f"   • Total features: {report['summary']['total_features']}")
            self.stdout.write(f"   • Style configurations: {report['summary']['total_styles']}")
            self.stdout.write(f"   • Validation issues: {len(validation_issues)}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error generating report: {e}"))