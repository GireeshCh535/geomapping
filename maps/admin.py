# maps/admin.py - Clean and enhanced admin interface

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from .models import *

# ================================
# STATE ADMIN
# ================================

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'slug', 'city_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'code')
        }),
        ('Map Center', {
            'fields': ('center_lat', 'center_lng', 'default_zoom'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('is_active', 'created_at')
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            city_count=Count('cities')
        )
    
    def city_count(self, obj):
        return obj.city_count
    city_count.short_description = 'Cities'
    city_count.admin_order_field = 'city_count'

# ================================
# CITY ADMIN
# ================================

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'state_display', 'layer_count', 'feature_count', 'is_active']
    list_filter = ['state_ref', 'is_active', 'created_at']
    search_fields = ['name', 'slug', 'state_ref__name']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'state_ref')
        }),
        ('Legacy State Field', {
            'fields': ('state',),
            'classes': ('collapse',),
            'description': 'Legacy field - use state_ref instead'
        }),
        ('Map Center', {
            'fields': ('center_lat', 'center_lng')
        }),
        ('Zoom Settings', {
            'fields': ('min_zoom', 'max_zoom'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('is_active', 'created_at')
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('state_ref').annotate(
            layer_count=Count('layers'),
            feature_count=Count('layers__geofeature_set')
        )
    
    def state_display(self, obj):
        if obj.state_ref:
            return f"{obj.state_ref.name} ({obj.state_ref.code})"
        return obj.state  # Fallback to legacy field
    state_display.short_description = 'State'
    state_display.admin_order_field = 'state_ref__name'
    
    def layer_count(self, obj):
        return obj.layer_count
    layer_count.short_description = 'Layers'
    layer_count.admin_order_field = 'layer_count'
    
    def feature_count(self, obj):
        return f"{obj.feature_count:,}"
    feature_count.short_description = 'Features'
    feature_count.admin_order_field = 'feature_count'

# ================================
# LAYER CATEGORY ADMIN
# ================================

@admin.register(LayerCategory)
class LayerCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'color_display', 'layer_count', 'display_order', 'is_active']
    list_filter = ['code', 'is_active']
    search_fields = ['name', 'code', 'description']
    ordering = ['display_order', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description')
        }),
        ('Styling', {
            'fields': ('default_color', 'default_stroke', 'default_opacity')
        }),
        ('Display Settings', {
            'fields': ('display_order', 'min_zoom', 'max_zoom', 'is_active')
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            layer_count=Count('layers')
        )
    
    def color_display(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc; display: inline-block;"></div> {}',
            obj.default_color, obj.default_color
        )
    color_display.short_description = 'Color'
    
    def layer_count(self, obj):
        return obj.layer_count
    layer_count.short_description = 'Layers Using'
    layer_count.admin_order_field = 'layer_count'

# ================================
# DATA LAYER ADMIN
# ================================

@admin.register(DataLayer)
class DataLayerAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'city_state', 'category', 'feature_count_display', 
        'status_display', 'tiles_display', 'updated_at'
    ]
    list_filter = [
        'city__state_ref', 'city', 'category', 'is_processed', 
        'tiles_generated', 'file_format', 'created_at'
    ]
    search_fields = ['name', 'slug', 'description', 'city__name']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at', 'feature_count']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'city', 'category')
        }),
        ('File Information', {
            'fields': ('original_filename', 'file_format', 'file_path', 'is_directory', 'file_pattern')
        }),
        ('Processing Status', {
            'fields': ('is_processed', 'feature_count', 'processing_errors')
        }),
        ('Categorization', {
            'fields': ('categorization_method', 'primary_plu_codes'),
            'classes': ('collapse',)
        }),
        ('Geometry Info', {
            'fields': ('geometry_type', 'bbox_xmin', 'bbox_ymin', 'bbox_xmax', 'bbox_ymax'),
            'classes': ('collapse',)
        }),
        ('Tiles', {
            'fields': ('tiles_generated', 'tile_cache_size')
        }),
        ('Optional Grouping', {
            'fields': ('layer_group',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('data_source', 'last_updated', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'city', 'city__state_ref', 'category', 'layer_group'
        )
    
    def city_state(self, obj):
        if obj.city.state_ref:
            return f"{obj.city.name} ({obj.city.state_ref.code})"
        return obj.city.name
    city_state.short_description = 'City (State)'
    city_state.admin_order_field = 'city__name'
    
    def feature_count_display(self, obj):
        if obj.feature_count > 0:
            return format_html('<strong>{:,}</strong>', obj.feature_count)
        return '0'
    feature_count_display.short_description = 'Features'
    feature_count_display.admin_order_field = 'feature_count'
    
    def status_display(self, obj):
        if obj.is_processed:
            return format_html('<span style="color: green;">✓ Processed</span>')
        return format_html('<span style="color: orange;">⏳ Pending</span>')
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'is_processed'
    
    def tiles_display(self, obj):
        if obj.tiles_generated:
            return format_html('<span style="color: green;">✓ Generated</span>')
        return format_html('<span style="color: red;">✗ Not Generated</span>')
    tiles_display.short_description = 'Tiles'
    tiles_display.admin_order_field = 'tiles_generated'

# ================================
# GEO FEATURE ADMIN
# ================================

@admin.register(GeoFeature)
class GeoFeatureAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'layer_city', 'name_display', 'land_use_type', 
        'area_display', 'plu_primary_code', 'derived_category'
    ]
    list_filter = [
        'layer__city', 'layer__category', 'land_use_type', 
        'derived_category', 'is_valid', 'created_at'
    ]
    search_fields = [
        'name', 'land_use_type', 'plu_primary_code', 'derived_category',
        'district', 'mandal', 'village'
    ]
    readonly_fields = [
        'calculated_area', 'calculated_perimeter', 
        'calculated_centroid_lat', 'calculated_centroid_lng',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('layer', 'name', 'description')
        }),
        ('Land Use', {
            'fields': ('land_use_type', 'land_use_name', 'derived_category', 'zoning')
        }),
        ('PLU Information', {
            'fields': (
                'plu_primary_code', 'plu_secondary_1', 'plu_secondary_2',
                'plu_proposed_use', 'plu_authority'
            ),
            'classes': ('collapse',)
        }),
        ('Location', {
            'fields': ('state', 'district', 'mandal', 'village', 'ward'),
            'classes': ('collapse',)
        }),
        ('Area & Measurements', {
            'fields': (
                'area_value', 'area_unit', 'calculated_area', 
                'calculated_perimeter', 'calculated_centroid_lat', 'calculated_centroid_lng'
            ),
            'classes': ('collapse',)
        }),
        ('Source Data', {
            'fields': ('source_fid', 'source_object_id', 'source_attributes'),
            'classes': ('collapse',)
        }),
        ('Validation', {
            'fields': ('is_valid', 'validation_notes'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('layer', 'layer__city')
    
    def layer_city(self, obj):
        return f"{obj.layer.city.name} - {obj.layer.name}"
    layer_city.short_description = 'Layer'
    layer_city.admin_order_field = 'layer__city__name'
    
    def name_display(self, obj):
        return obj.get_display_name()
    name_display.short_description = 'Name'
    
    def area_display(self, obj):
        if obj.calculated_area:
            return f"{obj.calculated_area:,.1f}"
        return '-'
    area_display.short_description = 'Area'
    area_display.admin_order_field = 'calculated_area'

# ================================
# LAYER GROUP ADMIN
# ================================

@admin.register(LayerGroup)
class LayerGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'category', 'layer_count', 'is_visible', 'display_order']
    list_filter = ['city', 'category', 'is_visible', 'created_at']
    search_fields = ['name', 'description', 'city__name']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['city', 'display_order', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'city', 'category')
        }),
        ('Directory Path', {
            'fields': ('directory_path',)
        }),
        ('Styling', {
            'fields': ('default_color', 'default_stroke', 'default_opacity'),
            'classes': ('collapse',)
        }),
        ('Display Settings', {
            'fields': ('display_order', 'is_visible', 'min_zoom', 'max_zoom')
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'city', 'category'
        ).annotate(layer_count=Count('layers'))
    
    def layer_count(self, obj):
        return obj.layer_count
    layer_count.short_description = 'Layers'
    layer_count.admin_order_field = 'layer_count'

# ================================
# CITY LAYER STYLE ADMIN
# ================================

@admin.register(CityLayerStyle)
class CityLayerStyleAdmin(admin.ModelAdmin):
    list_display = ['city', 'category', 'color_display', 'opacity', 'is_visible']
    list_filter = ['city', 'category', 'is_visible']
    search_fields = ['city__name', 'category__name']
    
    fieldsets = (
        ('Location', {
            'fields': ('city', 'category')
        }),
        ('Style', {
            'fields': ('fill_color', 'stroke_color', 'opacity', 'stroke_width')
        }),
        ('Visibility', {
            'fields': ('is_visible', 'min_zoom', 'max_zoom')
        })
    )
    
    def color_display(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc; display: inline-block;"></div> {}',
            obj.fill_color, obj.fill_color
        )
    color_display.short_description = 'Color'

# ================================
# PLU CODE MAPPING ADMIN
# ================================

@admin.register(PLUCodeMapping)
class PLUCodeMappingAdmin(admin.ModelAdmin):
    list_display = ['city', 'plu_code', 'mapped_category', 'feature_count', 'is_active', 'last_used']
    list_filter = ['city', 'mapped_category', 'is_active', 'created_at']
    search_fields = ['plu_code', 'plu_description', 'city__name']
    readonly_fields = ['feature_count', 'last_used', 'created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('city', 'plu_code', 'plu_description')
        }),
        ('Mapping', {
            'fields': ('mapped_category', 'notes')
        }),
        ('Additional Codes', {
            'fields': ('secondary_codes',),
            'classes': ('collapse',)
        }),
        ('Usage Statistics', {
            'fields': ('feature_count', 'last_used', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )

# ================================
# IMPORT JOB ADMIN
# ================================

@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = [
        'filename', 'city', 'status_display', 'features_imported_display', 
        'success_rate_display', 'started_at'
    ]
    list_filter = ['city', 'status', 'file_format', 'started_at']
    search_fields = ['filename', 'city__name']
    readonly_fields = [
        'id', 'features_imported', 'features_failed', 'features_skipped',
        'processing_duration', 'started_at', 'completed_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('city', 'filename', 'file_path', 'file_format')
        }),
        ('Processing Results', {
            'fields': (
                'status', 'features_imported', 'features_failed', 'features_skipped',
                'processing_duration'
            )
        }),
        ('Categorization', {
            'fields': ('category_mapped', 'categorization_method', 'plu_codes_detected'),
            'classes': ('collapse',)
        }),
        ('Processing Stats', {
            'fields': ('geometry_conversions', 'coordinate_optimizations'),
            'classes': ('collapse',)
        }),
        ('Errors', {
            'fields': ('error_message', 'error_details'),
            'classes': ('collapse',)
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at')
        })
    )
    
    def status_display(self, obj):
        status_colors = {
            'COMPLETED': 'green',
            'FAILED': 'red',
            'PROCESSING': 'orange',
            'PARTIAL': 'orange',
            'PENDING': 'gray'
        }
        color = status_colors.get(obj.status, 'black')
        return format_html('<span style="color: {};">{}</span>', color, obj.get_status_display())
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def features_imported_display(self, obj):
        return f"{obj.features_imported:,}"
    features_imported_display.short_description = 'Features'
    features_imported_display.admin_order_field = 'features_imported'
    
    def success_rate_display(self, obj):
        rate = obj.get_success_rate()
        if rate >= 90:
            color = 'green'
        elif rate >= 50:
            color = 'orange'
        else:
            color = 'red'
        return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)
    success_rate_display.short_description = 'Success Rate'

# ================================
# VECTOR TILE LAYER ADMIN
# ================================

@admin.register(VectorTileLayer)
class VectorTileLayerAdmin(admin.ModelAdmin):
    list_display = ['layer', 'is_generated', 'total_tiles', 'cache_size_display', 'generated_at']
    list_filter = ['is_generated', 'generated_at']
    search_fields = ['layer__name', 'layer__city__name']
    readonly_fields = ['total_tiles', 'cache_size_mb', 'generated_at', 'updated_at']
    
    fieldsets = (
        ('Layer Information', {
            'fields': ('layer',)
        }),
        ('Tile Configuration', {
            'fields': ('min_zoom', 'max_zoom', 'tile_size')
        }),
        ('Generation Status', {
            'fields': ('is_generated', 'total_tiles', 'cache_size_mb', 'generated_at')
        }),
        ('File Paths', {
            'fields': ('tiles_directory', 'mbtiles_file'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        })
    )
    
    def cache_size_display(self, obj):
        if obj.cache_size_mb > 1024:
            return f"{obj.cache_size_mb/1024:.1f} GB"
        return f"{obj.cache_size_mb:.1f} MB"
    cache_size_display.short_description = 'Cache Size'
    cache_size_display.admin_order_field = 'cache_size_mb'

# ================================
# REAL ESTATE ADMINS
# ================================

@admin.register(Plot)
class PlotAdmin(admin.ModelAdmin):
    list_display = [
        'plot_id', 'marker_title', 'area_display', 
        'price_display', 'total_price_display', 'is_active'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['plot_id', 'marker_title', 'marker_id']
    readonly_fields = ['total_price', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('plot_id', 'marker_title', 'marker_id', 'is_active')
        }),
        ('Location', {
            'fields': ('location',)
        }),
        ('Pricing', {
            'fields': ('area_sq_yards', 'price_per_sq_yard', 'total_price')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def area_display(self, obj):
        return f"{obj.area_sq_yards:,} sq yards" if obj.area_sq_yards else '-'
    area_display.short_description = 'Area'
    
    def price_display(self, obj):
        return f"₹{obj.price_per_sq_yard:,}/sq yard" if obj.price_per_sq_yard else '-'
    price_display.short_description = 'Price/Sq Yard'
    
    def total_price_display(self, obj):
        return f"₹{obj.total_price:,}" if obj.total_price else '-'
    total_price_display.short_description = 'Total Price'

@admin.register(Land)
class LandAdmin(admin.ModelAdmin):
    list_display = ['land_id', 'marker_title', 'area_text', 'price_text', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['land_id', 'marker_title', 'marker_id', 'area_text']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('land_id', 'marker_title', 'marker_id', 'is_active')
        }),
        ('Location', {
            'fields': ('location',)
        }),
        ('Details', {
            'fields': ('area_text', 'price_text')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

# ================================
# ADMIN SITE CUSTOMIZATION
# ================================

admin.site.site_header = "GIS Data Management"
admin.site.site_title = "GIS Admin"
admin.site.index_title = "Welcome to GIS Data Administration"