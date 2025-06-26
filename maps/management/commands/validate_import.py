# management/commands/validate_import.py - Validate imported data

from django.core.management.base import BaseCommand
from django.db.models import Count, Q, Avg, Min, Max
from maps.models import City, DataLayer, GeoFeature, PLUCodeMapping, ImportJob
from maps.config import get_city_config
from collections import Counter
import json

class Command(BaseCommand):
    help = 'Validate and analyze imported geographic data'
    
    def add_arguments(self, parser):
        parser.add_argument('--city', required=True, help='City slug to validate')
        parser.add_argument('--detailed', action='store_true', help='Show detailed analysis')
        parser.add_argument('--export-report', help='Export validation report to JSON file')
        parser.add_argument('--check-geometry', action='store_true', help='Validate geometry integrity')
    
    def handle(self, *args, **options):
        city_slug = options['city']
        
        try:
            city = City.objects.get(slug=city_slug)
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"🔍 Validating data for {city.name}"))
        
        # Perform validation
        report = self._generate_validation_report(city, options)
        
        # Display results
        self._display_report(report, options)
        
        # Export report if requested
        if options['export_report']:
            self._export_report(report, options['export_report'])
        
        # Show recommendations
        self._show_recommendations(report)
    
    def _generate_validation_report(self, city, options):
        """Generate comprehensive validation report"""
        
        report = {
            'city': {
                'name': city.name,
                'slug': city.slug,
                'state': city.state
            },
            'summary': {},
            'layers': [],
            'plu_analysis': {},
            'geometry_validation': {},
            'import_history': [],
            'issues': []
        }
        
        # Basic statistics
        layers = DataLayer.objects.filter(city=city)
        total_features = GeoFeature.objects.filter(layer__city=city).count()
        processed_layers = layers.filter(is_processed=True).count()
        
        report['summary'] = {
            'total_layers': layers.count(),
            'processed_layers': processed_layers,
            'total_features': total_features,
            'features_per_layer': round(total_features / max(processed_layers, 1), 2)
        }
        
        # Layer analysis
        for layer in layers:
            layer_info = self._analyze_layer(layer, options)
            report['layers'].append(layer_info)
        
        # PLU analysis (for Bangalore)
        if city.slug == 'bangalore':
            report['plu_analysis'] = self._analyze_plu_codes(city)
        
        # Geometry validation
        if options['check_geometry']:
            report['geometry_validation'] = self._validate_geometries(city)
        
        # Import history
        recent_imports = ImportJob.objects.filter(city=city).order_by('-started_at')[:10]
        for job in recent_imports:
            report['import_history'].append({
                'filename': job.filename,
                'status': job.status,
                'features_imported': job.features_imported,
                'started_at': job.started_at.isoformat(),
                'duration': str(job.processing_duration) if job.processing_duration else None
            })
        
        return report
    
    def _analyze_layer(self, layer, options):
        """Analyze individual layer"""
        
        features = GeoFeature.objects.filter(layer=layer)
        
        layer_info = {
            'name': layer.name,
            'slug': layer.slug,
            'category': layer.category.name,
            'file_format': layer.file_format,
            'categorization_method': layer.categorization_method,
            'feature_count': features.count(),
            'is_processed': layer.is_processed,
            'has_bbox': all([layer.bbox_xmin, layer.bbox_ymin, layer.bbox_xmax, layer.bbox_ymax]),
            'primary_plu_codes': layer.primary_plu_codes
        }
        
        if features.exists():
            # Calculate statistics
            area_stats = features.aggregate(
                avg_area=Avg('calculated_area'),
                min_area=Min('calculated_area'),
                max_area=Max('calculated_area')
            )
            
            layer_info.update({
                'area_statistics': area_stats,
                'valid_features': features.filter(is_valid=True).count(),
                'invalid_features': features.filter(is_valid=False).count(),
                'features_with_names': features.exclude(Q(name='') | Q(name__isnull=True)).count()
            })
            
            # PLU code analysis for this layer
            if layer.city.slug == 'bangalore':
                plu_codes = features.values('plu_primary_code').annotate(
                    count=Count('id')
                ).order_by('-count')
                
                layer_info['plu_codes'] = list(plu_codes)
        
        return layer_info
    
    def _analyze_plu_codes(self, city):
        """Analyze PLU codes for Bangalore"""
        
        plu_analysis = {
            'total_plu_features': 0,
            'unique_plu_codes': 0,
            'plu_distribution': {},
            'category_mapping_accuracy': {},
            'unmapped_codes': []
        }
        
        # Get all features with PLU codes
        plu_features = GeoFeature.objects.filter(
            layer__city=city,
            plu_primary_code__isnull=False
        ).exclude(plu_primary_code='')
        
        plu_analysis['total_plu_features'] = plu_features.count()
        
        if plu_features.exists():
            # PLU code distribution
            plu_distribution = plu_features.values('plu_primary_code').annotate(
                count=Count('id')
            ).order_by('-count')
            
            plu_analysis['unique_plu_codes'] = len(plu_distribution)
            plu_analysis['plu_distribution'] = {
                item['plu_primary_code']: item['count'] 
                for item in plu_distribution
            }
            
            # Check mapping accuracy
            mapped_codes = set(PLUCodeMapping.objects.filter(city=city).values_list('plu_code', flat=True))
            found_codes = set(plu_analysis['plu_distribution'].keys())
            
            plu_analysis['unmapped_codes'] = list(found_codes - mapped_codes)
            plu_analysis['mapping_coverage'] = len(mapped_codes & found_codes) / len(found_codes) * 100
        
        return plu_analysis
    
    def _validate_geometries(self, city):
        """Validate geometry integrity"""
        
        validation = {
            'total_features': 0,
            'valid_geometries': 0,
            'invalid_geometries': 0,
            'empty_geometries': 0,
            'geometry_types': {},
            'coordinate_precision_issues': 0
        }
        
        features = GeoFeature.objects.filter(layer__city=city)
        validation['total_features'] = features.count()
        
        for feature in features.iterator():
            try:
                geom = feature.geometry
                
                if geom is None or geom.empty:
                    validation['empty_geometries'] += 1
                elif geom.valid:
                    validation['valid_geometries'] += 1
                    
                    # Track geometry types
                    geom_type = geom.geom_type
                    validation['geometry_types'][geom_type] = validation['geometry_types'].get(geom_type, 0) + 1
                    
                    # Check coordinate precision (high precision can indicate issues)
                    if feature.original_precision and feature.original_precision > 10:
                        validation['coordinate_precision_issues'] += 1
                else:
                    validation['invalid_geometries'] += 1
                    
            except Exception as e:
                validation['invalid_geometries'] += 1
        
        return validation
    
    def _display_report(self, report, options):
        """Display validation report"""
        
        # Summary
        summary = report['summary']
        self.stdout.write(f"\n📊 Summary:")
        self.stdout.write(f"   Layers: {summary['processed_layers']}/{summary['total_layers']} processed")
        self.stdout.write(f"   Features: {summary['total_features']:,} total")
        self.stdout.write(f"   Average: {summary['features_per_layer']} features per layer")
        
        # Layer details
        self.stdout.write(f"\n📋 Layer Analysis:")
        for layer in report['layers']:
            status = "✅" if layer['is_processed'] else "❌"
            self.stdout.write(f"   {status} {layer['name']}")
            self.stdout.write(f"      📊 {layer['feature_count']:,} features ({layer['category']})")
            self.stdout.write(f"      🔧 Format: {layer['file_format']} | Method: {layer['categorization_method']}")
            
            if layer.get('invalid_features', 0) > 0:
                self.stdout.write(f"      ⚠️  Invalid features: {layer['invalid_features']}")
            
            if options['detailed'] and layer.get('plu_codes'):
                plu_codes = layer['plu_codes'][:5]  # Show top 5
                plu_summary = ', '.join([f"{p['plu_primary_code']}({p['count']})" for p in plu_codes])
                self.stdout.write(f"      🏷️  PLU codes: {plu_summary}")
        
        # PLU analysis
        if 'plu_analysis' in report and report['plu_analysis']:
            plu = report['plu_analysis']
            self.stdout.write(f"\n🏷️  PLU Code Analysis:")
            self.stdout.write(f"   Features with PLU codes: {plu['total_plu_features']:,}")
            self.stdout.write(f"   Unique PLU codes: {plu['unique_plu_codes']}")
            
            if 'mapping_coverage' in plu:
                self.stdout.write(f"   Mapping coverage: {plu['mapping_coverage']:.1f}%")
            
            if plu.get('unmapped_codes'):
                self.stdout.write(f"   ⚠️  Unmapped codes: {', '.join(plu['unmapped_codes'])}")
        
        # Geometry validation
        if 'geometry_validation' in report and report['geometry_validation']:
            geom = report['geometry_validation']
            self.stdout.write(f"\n🗺️  Geometry Validation:")
            self.stdout.write(f"   Valid: {geom['valid_geometries']:,}")
            self.stdout.write(f"   Invalid: {geom['invalid_geometries']:,}")
            self.stdout.write(f"   Empty: {geom['empty_geometries']:,}")
            
            if geom.get('coordinate_precision_issues', 0) > 0:
                self.stdout.write(f"   ⚠️  High precision coordinates: {geom['coordinate_precision_issues']:,}")
        
        # Recent imports
        if report['import_history']:
            self.stdout.write(f"\n📥 Recent Imports:")
            for job in report['import_history'][:5]:
                status_icon = "✅" if job['status'] == 'COMPLETED' else "❌"
                self.stdout.write(f"   {status_icon} {job['filename']}: {job['features_imported']:,} features")
    
    def _export_report(self, report, filename):
        """Export report to JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            self.stdout.write(f"📄 Report exported to: {filename}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to export report: {e}"))
    
    def _show_recommendations(self, report):
        """Show recommendations based on validation results"""
        
        self.stdout.write(f"\n💡 Recommendations:")
        
        # Check for unprocessed layers
        unprocessed = [l for l in report['layers'] if not l['is_processed']]
        if unprocessed:
            self.stdout.write(f"   🔧 Reprocess failed layers:")
            for layer in unprocessed:
                self.stdout.write(f"      - {layer['name']}")
        
        # Check for missing bounding boxes
        no_bbox = [l for l in report['layers'] if not l.get('has_bbox', False)]
        if no_bbox:
            self.stdout.write(f"   📐 Calculate bounding boxes for:")
            for layer in no_bbox:
                self.stdout.write(f"      - {layer['name']}")
        
        # PLU recommendations
        if 'plu_analysis' in report and report['plu_analysis'].get('unmapped_codes'):
            self.stdout.write(f"   🏷️  Add PLU mappings for: {', '.join(report['plu_analysis']['unmapped_codes'])}")
        
        # Geometry issues
        if 'geometry_validation' in report:
            geom = report['geometry_validation']
            if geom.get('invalid_geometries', 0) > 0:
                self.stdout.write(f"   🗺️  Fix {geom['invalid_geometries']} invalid geometries")
            
            if geom.get('coordinate_precision_issues', 0) > 0:
                self.stdout.write(f"   🎯 Consider reducing coordinate precision for {geom['coordinate_precision_issues']} features")
        
        # Next steps
        total_features = report['summary']['total_features']
        if total_features > 0:
            self.stdout.write(f"   🚀 Generate vector tiles: python manage.py generate_city_tiles --city={report['city']['slug']}")
            self.stdout.write(f"   🌐 Test API: curl http://localhost:8000/api/cities/{report['city']['slug']}/layers/")