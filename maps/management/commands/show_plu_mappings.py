 # management/commands/show_plu_mappings.py - Display and manage PLU mappings

from django.core.management.base import BaseCommand
from django.db.models import Count
from maps.models import City, PLUCodeMapping, GeoFeature, LayerCategory
from maps.config import get_plu_mapping, map_plu_code_to_category
from collections import Counter
import json

class Command(BaseCommand):
    help = 'Display and analyze PLU code mappings'
    
    def add_arguments(self, parser):
        parser.add_argument('--city', required=True, help='City slug to analyze')
        parser.add_argument('--detailed', action='store_true', help='Show detailed analysis')
        parser.add_argument('--unused', action='store_true', help='Show unused PLU codes')
        parser.add_argument('--conflicts', action='store_true', help='Check for mapping conflicts')
        parser.add_argument('--export', help='Export mappings to JSON file')
        parser.add_argument('--create-missing', action='store_true', help='Create mappings for unmapped codes')
    
    def handle(self, *args, **options):
        city_slug = options['city']
        
        try:
            city = City.objects.get(slug=city_slug)
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ City not found: {city_slug}"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"🏷️  PLU Mappings for {city.name}"))
        
        # Show current mappings
        self._show_current_mappings(city, options)
        
        # Analyze actual data
        self._analyze_actual_data(city, options)
        
        # Check for conflicts
        if options['conflicts']:
            self._check_conflicts(city)
        
        # Show unused codes
        if options['unused']:
            self._show_unused_codes(city)
        
        # Create missing mappings
        if options['create_missing']:
            self._create_missing_mappings(city)
        
        # Export mappings
        if options['export']:
            self._export_mappings(city, options['export'])
    
    def _show_current_mappings(self, city, options):
        """Show current PLU mappings from database"""
        
        mappings = PLUCodeMapping.objects.filter(city=city).select_related('mapped_category')
        
        if not mappings.exists():
            self.stdout.write("📋 No PLU mappings found in database")
            
            # Show configuration mappings
            config_mappings = get_plu_mapping(city.slug)
            if config_mappings:
                self.stdout.write(f"\n🔧 Configuration has {len(config_mappings)} PLU mappings")
                self.stdout.write("   Run with --create-missing to create database mappings")
            return
        
        self.stdout.write(f"\n📋 Database PLU Mappings ({mappings.count()}):")
        
        for mapping in mappings.order_by('plu_code'):
            feature_count = mapping.feature_count
            last_used = mapping.last_used.strftime('%Y-%m-%d') if mapping.last_used else 'Never'
            
            self.stdout.write(f"   🏷️  {mapping.plu_code} → {mapping.mapped_category.name}")
            self.stdout.write(f"      📊 {feature_count:,} features | Last used: {last_used}")
            
            if options['detailed']:
                self.stdout.write(f"      📝 {mapping.plu_description}")
                if mapping.secondary_codes:
                    self.stdout.write(f"      🔗 Secondary: {', '.join(mapping.secondary_codes)}")
                if mapping.notes:
                    self.stdout.write(f"      💡 {mapping.notes}")
    
    def _analyze_actual_data(self, city, options):
        """Analyze PLU codes found in actual data"""
        
        # Get all PLU codes from features
        plu_codes = GeoFeature.objects.filter(
            layer__city=city,
            plu_primary_code__isnull=False
        ).exclude(plu_primary_code='').values('plu_primary_code').annotate(
            count=Count('id')
        ).order_by('-count')
        
        if not plu_codes:
            self.stdout.write("\n📊 No PLU codes found in imported data")
            return
        
        self.stdout.write(f"\n📊 PLU Codes in Data ({len(plu_codes)}):")
        
        # Get mapped codes for comparison
        mapped_codes = set(PLUCodeMapping.objects.filter(city=city).values_list('plu_code', flat=True))
        
        mapped_count = 0
        unmapped_count = 0
        total_features = 0
        
        for plu_data in plu_codes:
            plu_code = plu_data['plu_primary_code']
            count = plu_data['count']
            total_features += count
            
            if plu_code in mapped_codes:
                status = "✅"
                mapped_count += 1
            else:
                status = "❌"
                unmapped_count += 1
            
            # Get suggested category from config
            suggested_category = map_plu_code_to_category(city.slug, plu_code)
            
            self.stdout.write(f"   {status} {plu_code}: {count:,} features")
            if options['detailed']:
                self.stdout.write(f"      🎯 Suggested: {suggested_category}")
        
        # Summary
        self.stdout.write(f"\n📈 Summary:")
        self.stdout.write(f"   Total PLU codes: {len(plu_codes)}")
        self.stdout.write(f"   Mapped: {mapped_count} | Unmapped: {unmapped_count}")
        self.stdout.write(f"   Total features: {total_features:,}")
        
        coverage = (mapped_count / len(plu_codes)) * 100 if plu_codes else 0
        self.stdout.write(f"   Coverage: {coverage:.1f}%")
    
    def _check_conflicts(self, city):
        """Check for mapping conflicts"""
        
        self.stdout.write(f"\n🔍 Checking for conflicts...")
        
        conflicts_found = False
        
        # Check for PLU codes mapping to different categories than configuration
        config_mapping = get_plu_mapping(city.slug)
        db_mappings = PLUCodeMapping.objects.filter(city=city).select_related('mapped_category')
        
        for db_mapping in db_mappings:
            plu_code = db_mapping.plu_code
            db_category = db_mapping.mapped_category.code
            
            if plu_code in config_mapping:
                config_category = config_mapping[plu_code]['category']
                
                if db_category != config_category:
                    conflicts_found = True
                    self.stdout.write(f"   ⚠️  Conflict for {plu_code}:")
                    self.stdout.write(f"      Database: {db_category}")
                    self.stdout.write(f"      Config: {config_category}")
        
        # Check for features with conflicting categorization
        features_with_conflicts = GeoFeature.objects.filter(
            layer__city=city,
            plu_primary_code__isnull=False
        ).exclude(plu_primary_code='').exclude(
            derived_category=''
        ).values('plu_primary_code', 'derived_category').annotate(
            count=Count('id')
        )
        
        plu_category_map = {}
        for feature_data in features_with_conflicts:
            plu_code = feature_data['plu_primary_code']
            category = feature_data['derived_category']
            
            if plu_code not in plu_category_map:
                plu_category_map[plu_code] = set()
            plu_category_map[plu_code].add(category)
        
        # Find PLU codes mapped to multiple categories
        for plu_code, categories in plu_category_map.items():
            if len(categories) > 1:
                conflicts_found = True
                self.stdout.write(f"   ⚠️  PLU {plu_code} maps to multiple categories: {', '.join(categories)}")
        
        if not conflicts_found:
            self.stdout.write("   ✅ No conflicts found")
    
    def _show_unused_codes(self, city):
        """Show PLU codes that are mapped but not used"""
        
        self.stdout.write(f"\n🔍 Checking for unused mappings...")
        
        # Get mapped codes
        mapped_codes = set(PLUCodeMapping.objects.filter(city=city).values_list('plu_code', flat=True))
        
        # Get used codes
        used_codes = set(GeoFeature.objects.filter(
            layer__city=city,
            plu_primary_code__isnull=False
        ).exclude(plu_primary_code='').values_list('plu_primary_code', flat=True))
        
        unused_codes = mapped_codes - used_codes
        
        if unused_codes:
            self.stdout.write(f"   📝 Mapped but unused ({len(unused_codes)}):")
            for code in sorted(unused_codes):
                mapping = PLUCodeMapping.objects.get(city=city, plu_code=code)
                self.stdout.write(f"      {code} → {mapping.mapped_category.name}")
        else:
            self.stdout.write("   ✅ All mappings are used")
    
    def _create_missing_mappings(self, city):
        """Create mappings for unmapped PLU codes"""
        
        self.stdout.write(f"\n🔧 Creating missing PLU mappings...")
        
        # Get unmapped codes from data
        used_codes = set(GeoFeature.objects.filter(
            layer__city=city,
            plu_primary_code__isnull=False
        ).exclude(plu_primary_code='').values_list('plu_primary_code', flat=True))
        
        mapped_codes = set(PLUCodeMapping.objects.filter(city=city).values_list('plu_code', flat=True))
        unmapped_codes = used_codes - mapped_codes
        
        if not unmapped_codes:
            self.stdout.write("   ✅ No missing mappings to create")
            return
        
        config_mapping = get_plu_mapping(city.slug)
        created_count = 0
        
        for plu_code in sorted(unmapped_codes):
            if plu_code in config_mapping:
                # Create from configuration
                plu_info = config_mapping[plu_code]
                
                try:
                    category = LayerCategory.objects.get(code=plu_info['category'])
                    
                    # Count features with this PLU code
                    feature_count = GeoFeature.objects.filter(
                        layer__city=city,
                        plu_primary_code=plu_code
                    ).count()
                    
                    mapping = PLUCodeMapping.objects.create(
                        city=city,
                        plu_code=plu_code,
                        mapped_category=category,
                        plu_description=plu_info['description'],
                        secondary_codes=plu_info.get('secondary_codes', []),
                        feature_count=feature_count,
                        notes=f"Auto-created from config. Examples: {', '.join(plu_info.get('examples', []))}"
                    )
                    
                    created_count += 1
                    self.stdout.write(f"   ✅ Created: {plu_code} → {category.name} ({feature_count:,} features)")
                    
                except LayerCategory.DoesNotExist:
                    self.stdout.write(f"   ❌ Category not found for {plu_code}: {plu_info['category']}")
            else:
                # No configuration mapping available
                feature_count = GeoFeature.objects.filter(
                    layer__city=city,
                    plu_primary_code=plu_code
                ).count()
                
                self.stdout.write(f"   ⚠️  No config mapping for {plu_code} ({feature_count:,} features)")
                self.stdout.write(f"      Add to config.py or create manually")
        
        self.stdout.write(f"\n📊 Created {created_count} new mappings")
    
    def _export_mappings(self, city, filename):
        """Export PLU mappings to JSON file"""
        
        try:
            mappings = PLUCodeMapping.objects.filter(city=city).select_related('mapped_category')
            
            export_data = {
                'city': {
                    'name': city.name,
                    'slug': city.slug
                },
                'mappings': [],
                'statistics': {}
            }
            
            for mapping in mappings:
                export_data['mappings'].append({
                    'plu_code': mapping.plu_code,
                    'description': mapping.plu_description,
                    'category_code': mapping.mapped_category.code,
                    'category_name': mapping.mapped_category.name,
                    'secondary_codes': mapping.secondary_codes,
                    'feature_count': mapping.feature_count,
                    'last_used': mapping.last_used.isoformat() if mapping.last_used else None,
                    'notes': mapping.notes
                })
            
            # Add statistics
            total_features = sum(m.feature_count for m in mappings)
            export_data['statistics'] = {
                'total_mappings': mappings.count(),
                'total_features': total_features,
                'export_date': city.created_at.isoformat()
            }
            
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            self.stdout.write(f"📄 Mappings exported to: {filename}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Export failed: {e}"))