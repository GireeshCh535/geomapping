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
    readonly_fields = ['get_layers_count', 'get_processed_layers_count', 'get_features_count']
    
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
        count = obj.get_features_count()
        return format_html('{:,} features', count)
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
    list_display = ['name', 'city', 'category', 'is_directory_icon', 
                   'feature_count', 'is_processed_icon', 'tiles_generated_icon']
    list_filter = ['city', 'category', 'is_processed', 'tiles_generated', 
                  'is_directory', 'file_format']
    search_fields = ['name', 'slug', 'city__name']
    readonly_fields = ['feature_count', 'bbox_display', 'source_files_display', 
                      'created_at', 'updated_at']
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('city', 'category', 'name', 'slug', 'description')
        }),
        ('File Configuration', {
            'fields': ('is_directory', 'file_path', 'file_pattern', 
                      'original_filename', 'file_format', 'source_files_display')
        }),
        ('Processing', {
            'fields': ('is_processed', 'feature_count', 'tiles_generated',
                      'categorization_method', 'processing_errors')
        }),
        ('Geometry', {
            'fields': ('geometry_type', 'bbox_display'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('data_source', 'created_at', 'updated_at', 'last_updated'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['process_layers', 'generate_tiles', 'calculate_bbox']
    
    def is_directory_icon(self, obj):
        if obj.is_directory:
            return format_html('📁 <small>({} files)</small>', 
                             len(obj.source_files) if obj.source_files else 0)
        return '📄'
    is_directory_icon.short_description = 'Type'
    
    def is_processed_icon(self, obj):
        if obj.is_processed:
            return format_html('<span style="color: green;">✅</span>')
        return format_html('<span style="color: orange;">⏳</span>')
    is_processed_icon.short_description = 'Processed'
    
    def tiles_generated_icon(self, obj):
        if obj.tiles_generated:
            return format_html('<span style="color: green;">✅</span>')
        return format_html('<span style="color: red;">❌</span>')
    tiles_generated_icon.short_description = 'Tiles'
    
    def bbox_display(self, obj):
        if obj.has_valid_bbox():
            return format_html(
                'Min: ({:.4f}, {:.4f})<br>Max: ({:.4f}, {:.4f})',
                obj.bbox_xmin, obj.bbox_ymin, obj.bbox_xmax, obj.bbox_ymax
            )
        return 'Not calculated'
    bbox_display.short_description = 'Bounding Box'
    
    def source_files_display(self, obj):
        if obj.source_files:
            files = obj.source_files[:5]  # Show first 5
            if len(obj.source_files) > 5:
                files.append(f'... and {len(obj.source_files) - 5} more')
            return format_html('<ul>{}</ul>', 
                             ''.join([f'<li>{f}</li>' for f in files]))
        return 'No files'
    source_files_display.short_description = 'Source Files'
    
    def process_layers(self, request, queryset):
        # Custom action to process layers
        processed = 0
        for layer in queryset:
            # Add your processing logic here
            processed += 1
        self.message_user(request, f'{processed} layers processed')
    process_layers.short_description = 'Process selected layers'
    
    def generate_tiles(self, request, queryset):
        # Custom action to generate tiles
        for layer in queryset:
            # Add tile generation logic here
            pass
        self.message_user(request, 'Tile generation initiated')
    generate_tiles.short_description = 'Generate tiles for selected layers'
    
    def calculate_bbox(self, request, queryset):
        for layer in queryset:
            layer.calculate_bbox()
        self.message_user(request, 'Bounding boxes calculated')
    calculate_bbox.short_description = 'Calculate bounding box'

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
            return obj.get_layers_count()
        get_layers_count.short_description = 'Layers'

admin.site.site_header = "GIS Data Management"
admin.site.site_title = "GIS Admin"
admin.site.index_title = "Welcome to GIS Data Administration"