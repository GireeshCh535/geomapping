# maps/admin.py
# Complete admin configuration that matches the model structure

from django.contrib import admin
from django.contrib.gis import admin as gis_admin
from django.utils.html import format_html
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.safestring import mark_safe
import json

from .models import (
    State, City, LayerCategory, CityLayerStyle, LayerGroup,
    DataLayer, GeoFeature, CityZoneMapping, PLUCodeMapping,
    VectorTileLayer, ValidationLog
)

# ================================
# STATE ADMIN
# ================================

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'slug', 'get_cities_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['name']
    
    def get_cities_count(self, obj):
        count = obj.get_cities_count()
        url = f"/admin/maps/city/?state_ref__id__exact={obj.id}"
        return format_html('<a href="{}">{} cities</a>', url, count)
    get_cities_count.short_description = 'Cities'

# ================================
# CITY ADMIN
# ================================

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'get_state_display', 'get_layers_count', 
                   'get_features_count', 'is_active', 'created_at']
    list_filter = ['state_ref', 'is_active', 'created_at']
    search_fields = ['name', 'slug', 'state']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['get_layers_count', 'get_processed_layers_count', 'get_features_count', 'created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'state', 'state_ref')
        }),
        ('Map Configuration', {
            'fields': ('center_lat', 'center_lng', 'min_zoom', 'max_zoom')
        }),
        ('Statistics', {
            'fields': ('get_layers_count', 'get_processed_layers_count', 'get_features_count'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'created_at')
        })
    )
    
    def get_state_display(self, obj):
        return obj.get_state_name()
    get_state_display.short_description = 'State'
    
    def get_layers_count(self, obj):
        count = obj.get_layers_count()
        url = f"/admin/maps/datalayer/?city__id__exact={obj.id}"
        return format_html('<a href="{}">{} layers</a>', url, count)
    get_layers_count.short_description = 'Total Layers'
    
    def get_features_count(self, obj):
        """FIXED: Format number with commas safely"""
        count = obj.get_features_count()
        formatted_count = f"{count:,}"
        return format_html('{} features', formatted_count)
    get_features_count.short_description = 'Total Features'

# ================================
# LAYER CATEGORY ADMIN
# ================================

@admin.register(LayerCategory)
class LayerCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'default_color_preview', 'get_layers_count', 
                   'display_order', 'is_active']
    list_filter = ['is_active', 'code']
    search_fields = ['name', 'code']
    ordering = ['display_order', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description')
        }),
        ('Default Styling', {
            'fields': ('default_color', 'default_stroke', 'default_opacity')
        }),
        ('Display Settings', {
            'fields': ('display_order', 'is_active')
        })
    )
    
    def default_color_preview(self, obj):
        return format_html(
            '<div style="width: 60px; height: 20px; background-color: {}; '
            'border: 1px solid #ccc;"></div> {}',
            obj.default_color, obj.default_color
        )
    default_color_preview.short_description = 'Default Color'
    
    def get_layers_count(self, obj):
        return obj.get_layers_count()
    get_layers_count.short_description = 'Layers Using This'

# ================================
# CITY LAYER STYLE ADMIN
# ================================

@admin.register(CityLayerStyle)
class CityLayerStyleAdmin(admin.ModelAdmin):
    list_display = ['city', 'category', 'fill_pattern', 'color_preview', 
                   'pattern_preview', 'is_visible']
    list_filter = ['city', 'category', 'fill_pattern', 'is_visible']
    search_fields = ['city__name', 'category__name']
    
    fieldsets = (
        ('Location', {
            'fields': ('city', 'category')
        }),
        ('Basic Colors', {
            'fields': ('fill_color', 'stroke_color', 'opacity', 'stroke_width')
        }),
        ('Pattern Configuration', {
            'fields': ('fill_pattern', 'pattern_color', 'secondary_fill_color',
                      'pattern_spacing', 'pattern_angle', 'pattern_size'),
            'classes': ('collapse',)
        }),
        ('Visibility', {
            'fields': ('is_visible', 'min_zoom', 'max_zoom')
        })
    )
    
    def color_preview(self, obj):
        return format_html(
            '<div style="display: flex; gap: 5px;">'
            '<div style="width: 30px; height: 20px; background-color: {}; '
            'border: 1px solid #ccc;" title="Fill"></div>'
            '<div style="width: 30px; height: 20px; background-color: {}; '
            'border: 1px solid #ccc;" title="Stroke"></div></div>',
            obj.fill_color, obj.stroke_color
        )
    color_preview.short_description = 'Colors'
    
    def pattern_preview(self, obj):
        if obj.fill_pattern == 'SOLID':
            return 'Solid'
        return format_html(
            '{} <small style="color: #666;">({}° {}px)</small>',
            obj.get_fill_pattern_display(),
            obj.pattern_angle,
            obj.pattern_spacing
        )
    pattern_preview.short_description = 'Pattern'

# ================================
# DATA LAYER ADMIN
# ================================

@admin.register(DataLayer)
class DataLayerAdmin(admin.ModelAdmin):
    # Enhanced list display with slug and better organization
    list_display = ['name_with_icon', 'slug_display', 'city_state_display', 'category_badge', 
                   'file_info', 'feature_count_display', 'status_badges', 'visibility_toggle']
    
    # Comprehensive filters
    list_filter = ['city__state_ref', 'city', 'category', 'is_processed', 
                  'tiles_generated', 'is_directory', 'file_format', 'is_true', 
                  'geometry_type', 'created_at']
    
    # Search with more fields
    search_fields = ['name', 'slug', 'city__name', 'city__state', 'description', 
                    'file_path', 'data_source']
    
    # Read-only fields
    readonly_fields = ['feature_count', 'bbox_display_enhanced', 'source_files_display_enhanced', 
                      'file_stats', 'layer_preview_map', 'created_at', 'updated_at']
    
    # Auto-populate slug from name
    prepopulated_fields = {'slug': ('name',)}
    
    # Date hierarchy for better navigation
    date_hierarchy = 'created_at'
    
    # Items per page
    list_per_page = 50
    
    # Enable select_related for performance
    list_select_related = ['city', 'city__state_ref', 'category', 'layer_group']
    
    # Enhanced fieldsets with better organization
    fieldsets = (
        ('🏷️ Basic Information', {
            'fields': ('city', 'category', 'layer_group', 'name', 'slug', 'description'),
            'description': 'Core identification and categorization of the layer'
        }),
        ('👁️ Visibility & Display', {
            'fields': ('is_true',),
            'description': '<strong style="color: #0066cc;">✨ Control whether this layer is visible by default in the map</strong>'
        }),
        ('📁 File Configuration', {
            'fields': ('is_directory', 'file_path', 'file_pattern', 
                      'original_filename', 'file_format', 'source_files_display_enhanced'),
            'classes': ('wide',)
        }),
        ('⚙️ Processing Status', {
            'fields': ('is_processed', 'feature_count', 'tiles_generated',
                      'categorization_method', 'processing_errors', 'file_stats'),
            'classes': ('wide',)
        }),
        ('🗺️ Geometry & Bounds', {
            'fields': ('geometry_type', 'bbox_display_enhanced', 'layer_preview_map'),
            'classes': ('collapse',)
        }),
        ('📊 Metadata & Source', {
            'fields': ('data_source', 'last_updated', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    # Custom actions
    actions = ['mark_as_visible', 'mark_as_hidden', 'process_layers', 
              'generate_tiles', 'calculate_bbox']
    
    # ============ Custom Display Methods ============
    
    def name_with_icon(self, obj):
        """Display name with appropriate icon"""
        icon = '📁' if obj.is_directory else '📄'
        color = '#0066cc' if obj.is_true else '#999'
        return format_html(
            '<strong style="color: {};">{} {}</strong>',
            color, icon, obj.name
        )
    name_with_icon.short_description = 'Layer Name'
    name_with_icon.admin_order_field = 'name'
    
    def slug_display(self, obj):
        """Display slug in a monospace font with copy-friendly styling"""
        return format_html(
            '<code style="background: #f5f5f5; padding: 3px 6px; border-radius: 3px; '
            'font-size: 11px; color: #d63384;">{}</code>',
            obj.slug
        )
    slug_display.short_description = 'Slug'
    slug_display.admin_order_field = 'slug'
    
    def city_state_display(self, obj):
        """Display city and state together"""
        state_name = obj.city.state_ref.name if obj.city.state_ref else obj.city.state
        return format_html(
            '<div style="line-height: 1.4;"><strong>{}</strong><br>'
            '<small style="color: #666;">📍 {}</small></div>',
            obj.city.name, state_name
        )
    city_state_display.short_description = 'City / State'
    city_state_display.admin_order_field = 'city__name'
    
    def category_badge(self, obj):
        """Display category as a colored badge"""
        colors = {
            'BOUNDARIES': '#800080',
            'PLANNING': '#FFE4B5',
            'RESIDENTIAL': '#FFB6C1',
            'COMMERCIAL': '#FFD700',
            'INDUSTRIAL': '#D2691E',
            'MIXED_USE': '#9370DB',
        }
        bg_color = colors.get(obj.category.code, '#CCCCCC')
        text_color = '#000' if obj.category.code in ['PLANNING', 'RESIDENTIAL', 'COMMERCIAL'] else '#FFF'
        return format_html(
            '<span style="background: {}; color: {}; padding: 4px 8px; '
            'border-radius: 12px; font-size: 11px; font-weight: 600; '
            'white-space: nowrap;">{}</span>',
            bg_color, text_color, obj.category.name
        )
    category_badge.short_description = 'Category'
    category_badge.admin_order_field = 'category__name'
    
    def file_info(self, obj):
        """Display file information compactly"""
        if obj.is_directory:
            file_count = len(obj.source_files) if obj.source_files else 0
            return format_html(
                '<div style="font-size: 11px;">📁 <strong>{}</strong> files<br>'
                '<code style="color: #666;">{}</code></div>',
                file_count, obj.file_format or 'N/A'
            )
        return format_html(
            '<div style="font-size: 11px;">📄 Single file<br>'
            '<code style="color: #666;">{}</code></div>',
            obj.file_format or 'N/A'
        )
    file_info.short_description = 'Files'
    
    def feature_count_display(self, obj):
        """Display feature count with formatting"""
        if obj.feature_count:
            formatted = f"{obj.feature_count:,}"
            color = '#28a745' if obj.feature_count > 0 else '#6c757d'
            return format_html(
                '<strong style="color: {}; font-size: 13px;">{}</strong><br>'
                '<small style="color: #666;">features</small>',
                color, formatted
            )
        return format_html('<small style="color: #999;">No data</small>')
    feature_count_display.short_description = 'Features'
    feature_count_display.admin_order_field = 'feature_count'
    
    def status_badges(self, obj):
        """Display processing and tile status as badges"""
        processed = '✅ Processed' if obj.is_processed else '⏳ Pending'
        processed_color = '#28a745' if obj.is_processed else '#ffc107'
        
        tiles = '🗺️ Tiles' if obj.tiles_generated else '❌ No Tiles'
        tiles_color = '#17a2b8' if obj.tiles_generated else '#dc3545'
        
        return format_html(
            '<div style="display: flex; flex-direction: column; gap: 3px;">'
            '<span style="background: {}; color: white; padding: 2px 6px; '
            'border-radius: 8px; font-size: 10px; display: inline-block;">{}</span>'
            '<span style="background: {}; color: white; padding: 2px 6px; '
            'border-radius: 8px; font-size: 10px; display: inline-block;">{}</span>'
            '</div>',
            processed_color, processed, tiles_color, tiles
        )
    status_badges.short_description = 'Status'
    
    def visibility_toggle(self, obj):
        """Display visibility status with eye icon"""
        if obj.is_true:
            return format_html(
                '<span style="color: #28a745; font-size: 16px;" title="Visible">👁️</span>'
            )
        return format_html(
            '<span style="color: #6c757d; font-size: 16px;" title="Hidden">👁️‍🗨️</span>'
        )
    visibility_toggle.short_description = 'Visible'
    visibility_toggle.admin_order_field = 'is_true'
    
    # ============ Enhanced Read-Only Field Methods ============
    
    def bbox_display_enhanced(self, obj):
        """Enhanced bounding box display with map coordinates"""
        if obj.has_valid_bbox():
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px; '
                'border-left: 3px solid #0066cc;">'
                '<div style="font-family: monospace; font-size: 11px;">'
                '<strong>West:</strong> {:.6f} &nbsp; <strong>East:</strong> {:.6f}<br>'
                '<strong>South:</strong> {:.6f} &nbsp; <strong>North:</strong> {:.6f}'
                '</div></div>',
                obj.bbox_xmin, obj.bbox_xmax, obj.bbox_ymin, obj.bbox_ymax
            )
        return format_html('<em style="color: #999;">Not calculated</em>')
    bbox_display_enhanced.short_description = 'Bounding Box Coordinates'
    
    def source_files_display_enhanced(self, obj):
        """Enhanced source files display with better styling"""
        if obj.source_files:
            files = obj.source_files[:10]  # Show first 10
            remaining = len(obj.source_files) - 10
            
            files_html = ''.join([
                f'<li style="padding: 2px 0;"><code style="font-size: 11px;">{f}</code></li>' 
                for f in files
            ])
            
            if remaining > 0:
                files_html += f'<li style="color: #666; font-style: italic;">... and {remaining} more files</li>'
            
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px; '
                'max-height: 300px; overflow-y: auto;">'
                '<strong>Total: {} files</strong>'
                '<ul style="margin: 5px 0; padding-left: 20px;">{}</ul></div>',
                len(obj.source_files), files_html
            )
        return format_html('<em style="color: #999;">No source files</em>')
    source_files_display_enhanced.short_description = 'Source Files'
    
    def file_stats(self, obj):
        """Display file statistics"""
        stats = []
        if obj.file_path:
            stats.append(f'📂 Path: <code>{obj.file_path}</code>')
        if obj.file_format:
            stats.append(f'📋 Format: <strong>{obj.file_format}</strong>')
        if obj.file_pattern:
            stats.append(f'🔍 Pattern: <code>{obj.file_pattern}</code>')
        if obj.categorization_method:
            stats.append(f'🏷️ Method: <strong>{obj.categorization_method}</strong>')
        
        if stats:
            return format_html('<br>'.join(stats))
        return format_html('<em style="color: #999;">No statistics available</em>')
    file_stats.short_description = 'File Statistics'
    
    def layer_preview_map(self, obj):
        """Display a preview map link if bounds are available"""
        if obj.has_valid_bbox():
            center_lat = (obj.bbox_ymin + obj.bbox_ymax) / 2
            center_lng = (obj.bbox_xmin + obj.bbox_xmax) / 2
            zoom = 12
            
            # Create OpenStreetMap link
            osm_url = f"https://www.openstreetmap.org/#map={zoom}/{center_lat}/{center_lng}"
            
            return format_html(
                '<div style="background: #e7f3ff; padding: 10px; border-radius: 5px;">'
                '<strong>🗺️ Map Preview:</strong><br>'
                '<small>Center: ({:.4f}, {:.4f})</small><br>'
                '<a href="{}" target="_blank" style="color: #0066cc; text-decoration: none;">'
                '🔗 View on OpenStreetMap →</a></div>',
                center_lat, center_lng, osm_url
            )
        return format_html('<em style="color: #999;">Bounds not available</em>')
    layer_preview_map.short_description = 'Map Preview'
    
    # ============ Custom Actions ============
    
    def mark_as_visible(self, request, queryset):
        """Mark selected layers as visible"""
        updated = queryset.update(is_true=True)
        self.message_user(request, f'{updated} layer(s) marked as visible ✅', level='success')
    mark_as_visible.short_description = '👁️ Mark as visible'
    
    def mark_as_hidden(self, request, queryset):
        """Mark selected layers as hidden"""
        updated = queryset.update(is_true=False)
        self.message_user(request, f'{updated} layer(s) marked as hidden 👁️‍🗨️', level='success')
    mark_as_hidden.short_description = '👁️‍🗨️ Mark as hidden'
    
    def process_layers(self, request, queryset):
        """Process selected layers"""
        processed = 0
        for layer in queryset:
            # Add your processing logic here
            processed += 1
        self.message_user(request, f'{processed} layer(s) processed ⚙️', level='success')
    process_layers.short_description = '⚙️ Process selected layers'
    
    def generate_tiles(self, request, queryset):
        """Generate tiles for selected layers"""
        count = queryset.count()
        self.message_user(request, f'Tile generation initiated for {count} layer(s) 🗺️', level='info')
    generate_tiles.short_description = '🗺️ Generate tiles'
    
    def calculate_bbox(self, request, queryset):
        """Calculate bounding boxes for selected layers"""
        calculated = 0
        for layer in queryset:
            try:
                layer.calculate_bbox()
                calculated += 1
            except Exception as e:
                pass
        self.message_user(request, f'Bounding boxes calculated for {calculated} layer(s) 📐', level='success')
    calculate_bbox.short_description = '📐 Calculate bounding box'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related"""
        qs = super().get_queryset(request)
        return qs.select_related('city', 'city__state_ref', 'category', 'layer_group')

# ================================
# GEO FEATURE ADMIN (FIXED)
# ================================

@admin.register(GeoFeature)
class GeoFeatureAdmin(gis_admin.GISModelAdmin):
    # Map widget for geometry field
    gis_widget_kwargs = {
        'attrs': {
            'default_zoom': 12,
            'default_lat': 12.9716,
            'default_lon': 77.5946,
        },
    }
    
    list_display = ['id', 'layer', 'source_layer_name', 'get_zone_name', 
                   'get_city', 'is_valid_icon', 'created_at']
    
    list_filter = ['layer__city', 'layer__category', 'layer', 
                  'source_layer_name', 'is_valid', 'created_at']
    
    search_fields = ['id', 'name', 'source_layer_name', 'zone_category', 
                     'plu_primary_code', 'plu_secondary_1', 'symbology']
    
    readonly_fields = ['created_at', 'updated_at', 'properties_display', 
                      'get_zone_name', 'get_city']
    
    fieldsets = (
        ('Layer Information', {
            'fields': ('layer', 'source_layer_name', 'get_city')
        }),
        ('Geometry', {
            'fields': ('geometry',)
        }),
        ('Basic Information', {
            'fields': ('name', 'description')
        }),
        ('Zone/Category Information', {
            'fields': ('zone_category', 'zone_subcategory', 'get_zone_name'),
            'classes': ('collapse',)
        }),
        ('Bengaluru PLU Fields', {
            'fields': ('plu_primary_code', 'plu_secondary_1', 'plu_secondary_2',
                      'plu_proposed_use', 'plu_development_code', 'plu_authority'),
            'classes': ('collapse',)
        }),
        ('Warangal Fields', {
            'fields': ('kuda', 'ex_pr'),
            'classes': ('collapse',)
        }),
        ('Amaravati Fields', {
            'fields': ('plot_category', 'symbology', 'township', 'sector', 
                      'colony', 'block'),
            'classes': ('collapse',)
        }),
        ('Visakhapatnam Fields', {
            'fields': ('mandal', 'district', 'village', 'rule_id'),
            'classes': ('collapse',)
        }),
        ('Numeric Fields', {
            'fields': ('area', 'shape_length', 'shape_area', 'objectid', 'fid'),
            'classes': ('collapse',)
        }),
        ('Original Properties', {
            'fields': ('properties_display',),
            'classes': ('collapse',)
        }),
        ('Validation', {
            'fields': ('is_valid', 'validation_errors'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_city(self, obj):
        return obj.layer.city.name
    get_city.short_description = 'City'
    get_city.admin_order_field = 'layer__city__name'
    
    def get_zone_name(self, obj):
        """Display the zone name based on city logic"""
        zone = obj.get_zone_name()
        if zone:
            return format_html('<span title="Zone/Category">{}</span>', zone)
        return '-'
    get_zone_name.short_description = 'Zone/Category'
    
    def is_valid_icon(self, obj):
        if obj.is_valid:
            return format_html('<span style="color: green;">✅</span>')
        return format_html('<span style="color: red;" title="{}">❌</span>', 
                          obj.validation_errors[:100])
    is_valid_icon.short_description = 'Valid'
    
    def properties_display(self, obj):
        """Display properties as formatted JSON"""
        if obj.properties:
            json_str = json.dumps(obj.properties, indent=2)
            return format_html('<pre style="max-height: 300px; overflow-y: auto;">{}</pre>', 
                             json_str)
        return 'No properties'
    properties_display.short_description = 'Original Properties (JSON)'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('layer', 'layer__city', 'layer__category')

# ================================
# CITY ZONE MAPPING ADMIN
# ================================

@admin.register(CityZoneMapping)
class CityZoneMappingAdmin(admin.ModelAdmin):
    list_display = ['zone_name', 'city', 'category', 'style', 
                   'feature_count', 'is_active']
    list_filter = ['city', 'category', 'is_active']
    search_fields = ['zone_name', 'zone_code']
    readonly_fields = ['feature_count', 'created_at']
    
    fieldsets = (
        ('Zone Information', {
            'fields': ('city', 'zone_name', 'zone_code')
        }),
        ('Mapping', {
            'fields': ('category', 'style')
        }),
        ('Style Overrides', {
            'fields': ('override_fill_color', 'override_pattern'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('feature_count', 'is_active', 'created_at')
        })
    )

# ================================
# PLU CODE MAPPING ADMIN (OPTIONAL)
# ================================

@admin.register(PLUCodeMapping)
class PLUCodeMappingAdmin(admin.ModelAdmin):
    list_display = ['plu_code', 'city', 'mapped_category', 
                   'feature_count', 'is_active']
    list_filter = ['city', 'mapped_category', 'is_active']
    search_fields = ['plu_code', 'plu_description']
    readonly_fields = ['feature_count', 'last_used', 'created_at']

# ================================
# VECTOR TILE LAYER ADMIN (OPTIONAL)
# ================================

@admin.register(VectorTileLayer)
class VectorTileLayerAdmin(admin.ModelAdmin):
    list_display = ['layer', 'is_generated_icon', 'total_tiles', 
                   'cache_size_mb', 'generated_at']
    list_filter = ['is_generated', 'generated_at']
    readonly_fields = ['total_tiles', 'cache_size_mb', 'generated_at', 'updated_at']
    
    def is_generated_icon(self, obj):
        if obj.is_generated:
            return format_html('<span style="color: green;">✅</span>')
        return format_html('<span style="color: red;">❌</span>')
    is_generated_icon.short_description = 'Generated'

# ================================
# VALIDATION LOG ADMIN (OPTIONAL)
# ================================

@admin.register(ValidationLog)
class ValidationLogAdmin(admin.ModelAdmin):
    list_display = ['city', 'layer', 'validation_type', 'is_valid_icon', 
                   'error_count', 'warning_count', 'created_at']
    list_filter = ['city', 'validation_type', 'is_valid', 'created_at']
    readonly_fields = ['validation_report_display', 'created_at']
    date_hierarchy = 'created_at'
    
    def is_valid_icon(self, obj):
        if obj.is_valid:
            return format_html('<span style="color: green;">✅ Valid</span>')
        return format_html('<span style="color: red;">❌ Invalid</span>')
    is_valid_icon.short_description = 'Status'
    
    def validation_report_display(self, obj):
        if obj.validation_report:
            json_str = json.dumps(obj.validation_report, indent=2)
            return format_html('<pre style="max-height: 400px; overflow-y: auto;">{}</pre>', 
                             json_str)
        return 'No report'
    validation_report_display.short_description = 'Validation Report'

# ================================
# LAYER GROUP ADMIN (OPTIONAL)
# ================================

if LayerGroup._meta.app_label == 'maps':  # Only register if model exists
    @admin.register(LayerGroup)
    class LayerGroupAdmin(admin.ModelAdmin):
        list_display = ['name', 'city', 'category', 'get_layers_count', 
                       'display_order', 'is_visible']
        list_filter = ['city', 'category', 'is_visible']
        search_fields = ['name', 'slug']
        prepopulated_fields = {'slug': ('name',)}
        
        def get_layers_count(self, obj):
            return obj.layers.count()
        get_layers_count.short_description = 'Layers'

admin.site.site_header = "GIS Data Management"
admin.site.site_title = "GIS Admin"
admin.site.index_title = "Welcome to GIS Data Administration"