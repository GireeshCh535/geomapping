# maps/admin.py
# Developer-friendly admin configuration with prominent IDs, technical details, and easy copy-paste

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
# HELPER FUNCTIONS
# ================================

def copyable_id(obj_id, label="ID"):
    """Display ID in a copy-friendly format"""
    return format_html(
        '<code style="background: #2c3e50; color: #2ecc71; padding: 4px 8px; '
        'border-radius: 3px; font-weight: bold; font-size: 12px; '
        'cursor: pointer; user-select: all;" title="Click to select, Ctrl+C to copy">{}: {}</code>',
        label, obj_id
    )

def copyable_text(text, label=""):
    """Display text in a copy-friendly format"""
    return format_html(
        '<code style="background: #f5f5f5; padding: 3px 6px; border-radius: 3px; '
        'font-size: 11px; color: #333; cursor: pointer; user-select: all;" '
        'title="Click to select">{}{}</code>',
        f"{label}: " if label else "", text
    )

def api_link(endpoint, label="API"):
    """Display API endpoint link"""
    return format_html(
        '<a href="{}" target="_blank" style="background: #3498db; color: white; '
        'padding: 3px 8px; border-radius: 3px; text-decoration: none; '
        'font-size: 10px; font-weight: bold;">🔗 {}</a>',
        endpoint, label
    )

# ================================
# STATE ADMIN
# ================================

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ['id_display', 'name', 'code_display', 'slug_display', 
                    'get_cities_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['id', 'name', 'code', 'slug']  # Added ID search
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['name']
    readonly_fields = ['id_display', 'created_at', 'get_technical_info']
    
    fieldsets = (
        ('🔑 IDs & Identification', {
            'fields': ('id_display', 'name', 'slug', 'code')
        }),
        ('📍 Map Configuration', {
            'fields': ('center_lat', 'center_lng', 'default_zoom')
        }),
        ('⚙️ Technical Info', {
            'fields': ('get_technical_info',),
            'classes': ('collapse',)
        }),
        ('✅ Status', {
            'fields': ('is_active', 'created_at')
        })
    )
    
    def id_display(self, obj):
        if obj.pk:
            return copyable_id(obj.pk, "State ID")
        return "-"
    id_display.short_description = 'ID'
    
    def code_display(self, obj):
        return copyable_text(obj.code, "Code")
    code_display.short_description = 'Code'
    code_display.admin_order_field = 'code'
    
    def slug_display(self, obj):
        return copyable_text(obj.slug, "Slug")
    slug_display.short_description = 'Slug'
    slug_display.admin_order_field = 'slug'
    
    def get_cities_count(self, obj):
        count = obj.get_cities_count()
        url = f"/admin/maps/city/?state_ref__id__exact={obj.id}"
        return format_html('<a href="{}" style="font-weight: bold; color: #2ecc71;">{} cities</a>', url, count)
    get_cities_count.short_description = 'Cities'
    
    def get_technical_info(self, obj):
        if not obj.pk:
            return "-"
        
        cities = obj.cities.all()
        layers_count = obj.get_layers_count()
        
        info = f"""
        <div style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; font-family: 'Courier New', monospace;">
            <div style="color: #3498db; font-weight: bold; margin-bottom: 10px;">📊 DATABASE INFO</div>
            <div style="line-height: 1.8;">
                <span style="color: #2ecc71;">state_id:</span> {obj.pk}<br>
                <span style="color: #2ecc71;">slug:</span> "{obj.slug}"<br>
                <span style="color: #2ecc71;">code:</span> "{obj.code}"<br>
                <span style="color: #2ecc71;">cities_count:</span> {cities.count()}<br>
                <span style="color: #2ecc71;">total_layers:</span> {layers_count}<br>
            </div>
            <div style="margin-top: 10px; color: #95a5a6; font-size: 11px;">
                💡 Use these values in API calls and database queries
            </div>
        </div>
        """
        return format_html(info)
    get_technical_info.short_description = 'Technical Information'

# ================================
# CITY ADMIN
# ================================

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['id_display', 'name', 'slug_display', 'get_state_with_id', 
                    'get_layers_count', 'get_features_count', 'is_active']
    list_filter = ['state_ref', 'is_active', 'created_at']
    search_fields = ['id', 'name', 'slug', 'state']  # Added ID search
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['id_display', 'get_state_with_id', 'get_layers_count', 
                      'get_processed_layers_count', 'get_features_count', 
                      'created_at', 'get_technical_info', 'get_api_endpoints']
    
    fieldsets = (
        ('🔑 IDs & Identification', {
            'fields': ('id_display', 'name', 'slug', 'state', 'state_ref')
        }),
        ('📍 Map Configuration', {
            'fields': ('center_lat', 'center_lng', 'min_zoom', 'max_zoom')
        }),
        ('📊 Statistics', {
            'fields': ('get_layers_count', 'get_processed_layers_count', 'get_features_count'),
            'classes': ('collapse',)
        }),
        ('🔗 API Endpoints', {
            'fields': ('get_api_endpoints',),
            'classes': ('collapse',)
        }),
        ('⚙️ Technical Info', {
            'fields': ('get_technical_info',),
            'classes': ('collapse',)
        }),
        ('✅ Status', {
            'fields': ('is_active', 'created_at')
        })
    )
    
    def id_display(self, obj):
        if obj.pk:
            return copyable_id(obj.pk, "City ID")
        return "-"
    id_display.short_description = 'ID'
    
    def slug_display(self, obj):
        return copyable_text(obj.slug, "Slug")
    slug_display.short_description = 'Slug'
    slug_display.admin_order_field = 'slug'
    
    def get_state_with_id(self, obj):
        if obj.state_ref:
            state_id = copyable_text(obj.state_ref.pk, "ID")
            state_link = format_html('<a href="/admin/maps/state/{}/change/" style="color: #3498db;">{}</a>', 
                                    obj.state_ref.pk, obj.state_ref.name)
            return format_html('{} {}', state_link, state_id)
        return obj.state
    get_state_with_id.short_description = 'State'
    
    def get_layers_count(self, obj):
        count = obj.get_layers_count()
        url = f"/admin/maps/datalayer/?city__id__exact={obj.id}"
        return format_html('<a href="{}" style="font-weight: bold; color: #2ecc71;">{} layers</a>', url, count)
    get_layers_count.short_description = 'Layers'
    
    def get_features_count(self, obj):
        count = obj.get_features_count()
        formatted_count = f"{count:,}"
        return format_html('<span style="font-weight: bold; color: #e74c3c;">{}</span> features', formatted_count)
    get_features_count.short_description = 'Features'
    
    def get_api_endpoints(self, obj):
        if not obj.pk:
            return "-"
        
        # Use format_html with proper escaping for literal braces
        return format_html(
            '<div style="background: #ecf0f1; padding: 15px; border-radius: 5px;">'
            '<div style="font-weight: bold; margin-bottom: 10px; color: #2c3e50;">🔗 API Endpoints</div>'
            '<div style="font-family: monospace; font-size: 12px; line-height: 2;">'
            '<div>🔍 <code>/api/cities/{}/search-coords-test/?lat=LAT&amp;lng=LNG</code></div>'
            '<div>🗺️ <code>/api/tiles/raster/{}/{{z}}/{{x}}/{{y}}.png</code></div>'
            '<div>📊 <code>/api/layers?city={}</code></div>'
            '</div></div>',
            obj.slug, obj.slug, obj.slug
        )
    get_api_endpoints.short_description = 'API Endpoints'
    
    def get_technical_info(self, obj):
        if not obj.pk:
            return "-"
        
        layers_count = obj.get_layers_count()
        processed_count = obj.get_processed_layers_count()
        features_count = obj.get_features_count()
        
        info = f"""
        <div style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; font-family: 'Courier New', monospace;">
            <div style="color: #3498db; font-weight: bold; margin-bottom: 10px;">📊 DATABASE INFO</div>
            <div style="line-height: 1.8;">
                <span style="color: #2ecc71;">city_id:</span> {obj.pk}<br>
                <span style="color: #2ecc71;">slug:</span> "{obj.slug}"<br>
                <span style="color: #2ecc71;">state_id:</span> {obj.state_ref.pk if obj.state_ref else 'null'}<br>
                <span style="color: #2ecc71;">center:</span> [{obj.center_lat}, {obj.center_lng}]<br>
                <span style="color: #2ecc71;">zoom_range:</span> [{obj.min_zoom}, {obj.max_zoom}]<br>
                <span style="color: #2ecc71;">total_layers:</span> {layers_count}<br>
                <span style="color: #2ecc71;">processed_layers:</span> {processed_count}<br>
                <span style="color: #2ecc71;">total_features:</span> {features_count:,}<br>
            </div>
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #34495e;">
                <div style="color: #e67e22; font-weight: bold; margin-bottom: 5px;">SQL Query:</div>
                <code style="color: #95a5a6; font-size: 11px;">
                    SELECT * FROM cities WHERE id = {obj.pk};
                </code>
            </div>
        </div>
        """
        return format_html(info)
    get_technical_info.short_description = 'Technical Information'

# ================================
# LAYER CATEGORY ADMIN
# ================================

@admin.register(LayerCategory)
class LayerCategoryAdmin(admin.ModelAdmin):
    list_display = ['id_display', 'name', 'code_display', 'default_color_preview', 
                   'get_layers_count', 'display_order', 'is_active']
    list_filter = ['is_active', 'code']
    search_fields = ['id', 'name', 'code']  # Added ID search
    ordering = ['display_order', 'name']
    readonly_fields = ['id_display']
    
    fieldsets = (
        ('🔑 IDs & Basic Information', {
            'fields': ('id_display', 'code', 'name', 'description')
        }),
        ('🎨 Default Styling', {
            'fields': ('default_color', 'default_stroke', 'default_opacity')
        }),
        ('⚙️ Display Settings', {
            'fields': ('display_order', 'is_active')
        })
    )
    
    def id_display(self, obj):
        if obj.pk:
            return copyable_id(obj.pk, "Category ID")
        return "-"
    id_display.short_description = 'ID'
    
    def code_display(self, obj):
        return copyable_text(obj.code, "Code")
    code_display.short_description = 'Code'
    code_display.admin_order_field = 'code'
    
    def default_color_preview(self, obj):
        return format_html(
            '<div style="width: 60px; height: 20px; background-color: {}; '
            'border: 1px solid #ccc;"></div> {}',
            obj.default_color, obj.default_color
        )
    default_color_preview.short_description = 'Default Color'
    
    def get_layers_count(self, obj):
        count = obj.get_layers_count()
        url = f"/admin/maps/datalayer/?category__id__exact={obj.id}"
        return format_html('<a href="{}" style="font-weight: bold; color: #2ecc71;">{} layers</a>', url, count)
    get_layers_count.short_description = 'Layers'

# ================================
# CITY LAYER STYLE ADMIN
# ================================

@admin.register(CityLayerStyle)
class CityLayerStyleAdmin(admin.ModelAdmin):
    list_display = ['id_display', 'get_city_with_id', 'get_category_with_id', 
                    'fill_pattern', 'color_preview', 'pattern_preview', 'is_visible']
    list_filter = ['city', 'category', 'fill_pattern', 'is_visible']
    search_fields = ['id', 'city__id', 'city__name', 'category__id', 'category__name']  # Added ID search
    
    # Use raw_id_fields for faster ID-based selection instead of slow dropdowns
    raw_id_fields = ['city', 'category']
    
    readonly_fields = ['id_display', 'get_technical_info', 'get_quick_reference']
    
    fieldsets = (
        ('🔑 IDs & Configuration', {
            'fields': ('id_display', 'city', 'category'),
            'description': '<strong style="color: #e67e22;">💡 TIP: Enter City ID and Category ID directly, or click 🔍 to search</strong>'
        }),
        ('🎨 Basic Colors', {
            'fields': ('fill_color', 'stroke_color', 'opacity', 'stroke_width')
        }),
        ('🖼️ Pattern Configuration', {
            'fields': ('fill_pattern', 'pattern_color', 'secondary_fill_color',
                      'pattern_spacing', 'pattern_angle', 'pattern_size'),
            'classes': ('collapse',)
        }),
        ('👁️ Visibility', {
            'fields': ('is_visible', 'min_zoom', 'max_zoom')
        }),
        ('📋 Quick Reference', {
            'fields': ('get_quick_reference',),
            'classes': ('collapse',)
        }),
        ('⚙️ Technical Info', {
            'fields': ('get_technical_info',),
            'classes': ('collapse',)
        })
    )
    
    def id_display(self, obj):
        if obj.pk:
            return copyable_id(obj.pk, "Style ID")
        return "-"
    id_display.short_description = 'ID'
    
    def get_city_with_id(self, obj):
        city_id = copyable_text(obj.city.pk, "ID")
        city_link = format_html('<a href="/admin/maps/city/{}/change/" style="color: #3498db;">{}</a>', 
                                obj.city.pk, obj.city.name)
        return format_html('{} {}', city_link, city_id)
    get_city_with_id.short_description = 'City'
    get_city_with_id.admin_order_field = 'city__name'
    
    def get_category_with_id(self, obj):
        cat_id = copyable_text(obj.category.pk, "ID")
        cat_link = format_html('<a href="/admin/maps/layercategory/{}/change/" style="color: #9b59b6;">{}</a>', 
                              obj.category.pk, obj.category.name)
        return format_html('{} {}', cat_link, cat_id)
    get_category_with_id.short_description = 'Category'
    get_category_with_id.admin_order_field = 'category__name'
    
    def get_quick_reference(self, obj):
        if not obj.pk:
            return "-"
        
        # Get common City and Category IDs for quick copy-paste
        cities = City.objects.filter(is_active=True).order_by('name')[:10]
        categories = LayerCategory.objects.filter(is_active=True).order_by('name')[:10]
        
        cities_list = '<br>'.join([f'<span style="color: #2ecc71;">{c.pk}</span>: {c.name}' for c in cities])
        categories_list = '<br>'.join([f'<span style="color: #e74c3c;">{cat.pk}</span>: {cat.name}' for cat in categories])
        
        info = f"""
        <div style="background: #ecf0f1; padding: 15px; border-radius: 5px;">
            <div style="font-weight: bold; margin-bottom: 10px; color: #2c3e50;">📋 Quick ID Reference (Top 10)</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; font-family: monospace; font-size: 11px;">
                <div>
                    <div style="font-weight: bold; color: #2c3e50; margin-bottom: 5px;">🏙️ Cities:</div>
                    {cities_list}
                </div>
                <div>
                    <div style="font-weight: bold; color: #2c3e50; margin-bottom: 5px;">📁 Categories:</div>
                    {categories_list}
                </div>
            </div>
        </div>
        """
        return format_html(info)
    get_quick_reference.short_description = 'Quick ID Reference'
    
    def get_technical_info(self, obj):
        if not obj.pk:
            return "-"
        
        pattern_config = obj.get_pattern_config()
        
        info = f"""
        <div style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; font-family: 'Courier New', monospace;">
            <div style="color: #3498db; font-weight: bold; margin-bottom: 10px;">📊 DATABASE INFO</div>
            <div style="line-height: 1.8;">
                <span style="color: #2ecc71;">style_id:</span> {obj.pk}<br>
                <span style="color: #2ecc71;">city_id:</span> {obj.city.pk}<br>
                <span style="color: #2ecc71;">category_id:</span> {obj.category.pk}<br>
                <span style="color: #2ecc71;">fill_color:</span> "{obj.fill_color}"<br>
                <span style="color: #2ecc71;">stroke_color:</span> "{obj.stroke_color}"<br>
                <span style="color: #2ecc71;">fill_pattern:</span> "{obj.fill_pattern}"<br>
            </div>
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #34495e;">
                <div style="color: #e67e22; font-weight: bold; margin-bottom: 5px;">SQL Query:</div>
                <code style="color: #95a5a6; font-size: 11px;">
                    SELECT * FROM city_layer_styles<br>
                    WHERE city_id = {obj.city.pk} AND category_id = {obj.category.pk};
                </code>
            </div>
        </div>
        """
        return format_html(info)
    get_technical_info.short_description = 'Technical Information'
    
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
    # Enhanced list display with IDs prominently shown
    list_display = ['id_display', 'name_with_icon', 'slug_display', 'city_state_with_ids', 
                   'category_badge', 'feature_count_display', 'status_badges', 'visibility_toggle']
    
    # Comprehensive filters
    list_filter = ['city__state_ref', 'city', 'category', 'is_processed', 
                  'tiles_generated', 'is_directory', 'file_format', 'is_true', 
                  'geometry_type', 'created_at']
    
    # Search with ID fields
    search_fields = ['id', 'name', 'slug', 'city__id', 'city__name', 'city__state', 
                    'category__id', 'description', 'file_path', 'data_source']
    
    # Read-only fields
    readonly_fields = ['id_display', 'feature_count', 'bbox_display_enhanced', 
                      'source_files_display_enhanced', 'file_stats', 'layer_preview_map', 
                      'created_at', 'updated_at', 'get_technical_info', 'get_api_endpoints']
    
    # Auto-populate slug from name
    prepopulated_fields = {'slug': ('name',)}
    
    # Date hierarchy for better navigation
    date_hierarchy = 'created_at'
    
    # Items per page
    list_per_page = 50
    
    # Enable select_related for performance
    list_select_related = ['city', 'city__state_ref', 'category', 'layer_group']
    
    # Use raw_id_fields for foreign keys
    raw_id_fields = ['city', 'category', 'layer_group']
    
    # Enhanced fieldsets with better organization
    fieldsets = (
        ('🔑 IDs & Basic Information', {
            'fields': ('id_display', 'city', 'category', 'layer_group', 'name', 'slug', 'description'),
            'description': '<strong style="color: #e67e22;">💡 TIP: Use raw_id_fields - Enter IDs directly or click 🔍</strong>'
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
        ('🔗 API Endpoints', {
            'fields': ('get_api_endpoints',),
            'classes': ('collapse',)
        }),
        ('⚙️ Technical Info', {
            'fields': ('get_technical_info',),
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
    
    def id_display(self, obj):
        """Display ID in copy-friendly format"""
        if obj.pk:
            return copyable_id(obj.pk, "Layer ID")
        return "-"
    id_display.short_description = 'ID'
    
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
        return copyable_text(obj.slug, "Slug")
    slug_display.short_description = 'Slug'
    slug_display.admin_order_field = 'slug'
    
    def city_state_with_ids(self, obj):
        """Display city and state with IDs"""
        state_name = obj.city.state_ref.name if obj.city.state_ref else obj.city.state
        city_id = copyable_text(obj.city.pk, "CID")
        state_id = copyable_text(obj.city.state_ref.pk, "SID") if obj.city.state_ref else ""
        
        city_link = format_html('<a href="/admin/maps/city/{}/change/" style="color: #3498db;">{}</a>', 
                               obj.city.pk, obj.city.name)
        
        return format_html(
            '<div style="line-height: 1.6;">{} {}<br>'
            '<small style="color: #666;">📍 {} {}</small></div>',
            city_link, city_id, state_name, state_id
        )
    city_state_with_ids.short_description = 'City / State'
    city_state_with_ids.admin_order_field = 'city__name'
    
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
    
    def get_api_endpoints(self, obj):
        """Display relevant API endpoints for this layer"""
        if not obj.pk:
            return "-"
        
        # Use format_html with proper escaping for literal braces
        return format_html(
            '<div style="background: #ecf0f1; padding: 15px; border-radius: 5px;">'
            '<div style="font-weight: bold; margin-bottom: 10px; color: #2c3e50;">🔗 API Endpoints for {}</div>'
            '<div style="font-family: monospace; font-size: 11px; line-height: 2;">'
            '<div>🔍 <code>/api/cities/{}/search-coords-test/?lat=LAT&amp;lng=LNG</code></div>'
            '<div>🗺️ <code>/api/tiles/raster/{}/{{z}}/{{x}}/{{y}}.png</code></div>'
            '<div>📊 <code>/api/layers?city={}&amp;slug={}</code></div>'
            '</div></div>',
            obj.slug, obj.slug, obj.city.slug, obj.city.slug, obj.slug
        )
    get_api_endpoints.short_description = 'API Endpoints'
    
    def get_technical_info(self, obj):
        """Display technical database information"""
        if not obj.pk:
            return "-"
        
        bbox_str = f"[{obj.bbox_xmin:.4f}, {obj.bbox_ymin:.4f}, {obj.bbox_xmax:.4f}, {obj.bbox_ymax:.4f}]" if obj.has_valid_bbox() else "null"
        
        info = f"""
        <div style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; font-family: 'Courier New', monospace;">
            <div style="color: #3498db; font-weight: bold; margin-bottom: 10px;">📊 DATABASE INFO</div>
            <div style="line-height: 1.8; font-size: 12px;">
                <span style="color: #2ecc71;">layer_id:</span> {obj.pk}<br>
                <span style="color: #2ecc71;">slug:</span> "{obj.slug}"<br>
                <span style="color: #2ecc71;">city_id:</span> {obj.city.pk}<br>
                <span style="color: #2ecc71;">category_id:</span> {obj.category.pk}<br>
                <span style="color: #2ecc71;">is_directory:</span> {str(obj.is_directory).lower()}<br>
                <span style="color: #2ecc71;">is_processed:</span> {str(obj.is_processed).lower()}<br>
                <span style="color: #2ecc71;">tiles_generated:</span> {str(obj.tiles_generated).lower()}<br>
                <span style="color: #2ecc71;">is_visible:</span> {str(obj.is_true).lower()}<br>
                <span style="color: #2ecc71;">feature_count:</span> {obj.feature_count:,}<br>
                <span style="color: #2ecc71;">geometry_type:</span> "{obj.geometry_type or 'null'}"<br>
                <span style="color: #2ecc71;">bbox:</span> {bbox_str}<br>
            </div>
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #34495e;">
                <div style="color: #e67e22; font-weight: bold; margin-bottom: 5px;">SQL Queries:</div>
                <code style="color: #95a5a6; font-size: 10px;">
                    -- Get layer details<br>
                    SELECT * FROM data_layers WHERE id = {obj.pk};<br><br>
                    
                    -- Get features for this layer<br>
                    SELECT COUNT(*) FROM geo_features WHERE layer_id = {obj.pk};<br><br>
                    
                    -- Get layer with relationships<br>
                    SELECT l.*, c.name as city_name, cat.name as category_name<br>
                    FROM data_layers l<br>
                    JOIN cities c ON l.city_id = c.id<br>
                    JOIN layer_categories cat ON l.category_id = cat.id<br>
                    WHERE l.id = {obj.pk};
                </code>
            </div>
        </div>
        """
        return format_html(info)
    get_technical_info.short_description = 'Technical Information'
    
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
    
    list_display = ['id_display', 'get_layer_with_id', 'source_layer_name', 'get_zone_name', 
                   'get_city_with_id', 'is_valid_icon', 'geometry_info']
    
    list_filter = ['layer__city', 'layer__category', 'layer', 
                  'source_layer_name', 'is_valid', 'created_at']
    
    search_fields = ['id', 'layer__id', 'layer__slug', 'name', 'source_layer_name', 
                    'zone_category', 'plu_primary_code', 'plu_secondary_1', 'symbology']
    
    readonly_fields = ['id_display', 'created_at', 'updated_at', 'properties_display', 
                      'get_zone_name', 'get_city', 'get_technical_info', 'geometry_details']
    
    raw_id_fields = ['layer']
    
    fieldsets = (
        ('🔑 IDs & Layer Information', {
            'fields': ('id_display', 'layer', 'source_layer_name', 'get_city'),
            'description': '<strong style="color: #e67e22;">💡 TIP: Enter Layer ID directly or click 🔍 to search</strong>'
        }),
        ('🗺️ Geometry', {
            'fields': ('geometry', 'geometry_details')
        }),
        ('📝 Basic Information', {
            'fields': ('name', 'description')
        }),
        ('🏷️ Zone/Category Information', {
            'fields': ('zone_category', 'zone_subcategory', 'get_zone_name'),
            'classes': ('collapse',)
        }),
        ('📊 City-Specific Fields', {
            'description': 'Fields vary by city - only relevant fields will have data',
            'fields': (),
            'classes': ('collapse',)
        }),
        ('🌳 Bengaluru PLU Fields', {
            'fields': ('plu_primary_code', 'plu_secondary_1', 'plu_secondary_2',
                      'plu_proposed_use', 'plu_development_code', 'plu_authority'),
            'classes': ('collapse',)
        }),
        ('🏛️ Warangal Fields', {
            'fields': ('kuda', 'ex_pr'),
            'classes': ('collapse',)
        }),
        ('🏙️ Amaravati Fields', {
            'fields': ('plot_category', 'symbology', 'township', 'sector', 
                      'colony', 'block'),
            'classes': ('collapse',)
        }),
        ('⛰️ Visakhapatnam Fields', {
            'fields': ('mandal', 'district', 'village', 'rule_id'),
            'classes': ('collapse',)
        }),
        ('📐 Numeric Fields', {
            'fields': ('area', 'shape_length', 'shape_area', 'objectid', 'fid'),
            'classes': ('collapse',)
        }),
        ('🗃️ Original Properties (JSON)', {
            'fields': ('properties_display',),
            'classes': ('collapse',)
        }),
        ('⚙️ Technical Info', {
            'fields': ('get_technical_info',),
            'classes': ('collapse',)
        }),
        ('✅ Validation', {
            'fields': ('is_valid', 'validation_errors'),
            'classes': ('collapse',)
        }),
        ('🕒 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def id_display(self, obj):
        """Display feature ID in copy-friendly format"""
        if obj.pk:
            return copyable_id(obj.pk, "Feature ID")
        return "-"
    id_display.short_description = 'ID'
    
    def get_layer_with_id(self, obj):
        """Display layer with ID"""
        layer_id = copyable_text(obj.layer.pk, "LID")
        layer_link = format_html('<a href="/admin/maps/datalayer/{}/change/" style="color: #9b59b6;">{}</a>', 
                                obj.layer.pk, obj.layer.name[:30])
        return format_html('{} {}', layer_link, layer_id)
    get_layer_with_id.short_description = 'Layer'
    get_layer_with_id.admin_order_field = 'layer__name'
    
    def get_city(self, obj):
        return obj.layer.city.name
    get_city.short_description = 'City'
    get_city.admin_order_field = 'layer__city__name'
    
    def get_city_with_id(self, obj):
        """Display city with ID"""
        city_id = copyable_text(obj.layer.city.pk, "CID")
        city_name = obj.layer.city.name
        return format_html('{} {}', city_name, city_id)
    get_city_with_id.short_description = 'City'
    get_city_with_id.admin_order_field = 'layer__city__name'
    
    def get_zone_name(self, obj):
        """Display the zone name based on city logic"""
        zone = obj.get_zone_name()
        if zone:
            return format_html('<span title="Zone/Category">{}</span>', zone)
        return '-'
    get_zone_name.short_description = 'Zone/Category'
    
    def geometry_info(self, obj):
        """Display geometry type and SRID"""
        if obj.geometry:
            geom_type = obj.geometry.geom_type
            srid = obj.geometry.srid
            return format_html(
                '<span style="background: #3498db; color: white; padding: 2px 6px; '
                'border-radius: 3px; font-size: 10px;">{}</span> '
                '<span style="background: #e67e22; color: white; padding: 2px 6px; '
                'border-radius: 3px; font-size: 10px;">SRID:{}</span>',
                geom_type, srid
            )
        return "-"
    geometry_info.short_description = 'Geometry Info'
    
    def geometry_details(self, obj):
        """Display detailed geometry information"""
        if not obj.geometry:
            return format_html('<em style="color: #999;">No geometry</em>')
        
        geom = obj.geometry
        centroid = geom.centroid
        
        info = f"""
        <div style="background: #ecf0f1; padding: 15px; border-radius: 5px; font-family: monospace;">
            <div style="font-weight: bold; margin-bottom: 10px; color: #2c3e50;">🗺️ Geometry Details</div>
            <div style="font-size: 11px; line-height: 1.8;">
                <span style="color: #2ecc71;">type:</span> {geom.geom_type}<br>
                <span style="color: #2ecc71;">srid:</span> {geom.srid}<br>
                <span style="color: #2ecc71;">dims:</span> {geom.dims}<br>
                <span style="color: #2ecc71;">num_geom:</span> {geom.num_geom if hasattr(geom, 'num_geom') else 1}<br>
                <span style="color: #2ecc71;">centroid:</span> [{centroid.y:.6f}, {centroid.x:.6f}]<br>
                <span style="color: #2ecc71;">extent:</span> {geom.extent}<br>
            </div>
        </div>
        """
        return format_html(info)
    geometry_details.short_description = 'Geometry Technical Details'
    
    def is_valid_icon(self, obj):
        if obj.is_valid:
            return format_html('<span style="color: green; font-size: 16px;">✅</span>')
        return format_html('<span style="color: red; font-size: 16px;" title="{}">❌</span>', 
                          obj.validation_errors[:100] if obj.validation_errors else "Invalid")
    is_valid_icon.short_description = 'Valid'
    
    def properties_display(self, obj):
        """Display properties as formatted JSON"""
        if obj.properties:
            json_str = json.dumps(obj.properties, indent=2)
            return format_html(
                '<div style="background: #2c3e50; color: #2ecc71; padding: 10px; '
                'border-radius: 5px;"><pre style="margin: 0; max-height: 400px; '
                'overflow-y: auto; font-size: 11px;">{}</pre></div>', 
                json_str
            )
        return format_html('<em style="color: #999;">No properties</em>')
    properties_display.short_description = 'Original Properties (JSON)'
    
    def get_technical_info(self, obj):
        """Display technical database information"""
        if not obj.pk:
            return "-"
        
        info = f"""
        <div style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; font-family: 'Courier New', monospace;">
            <div style="color: #3498db; font-weight: bold; margin-bottom: 10px;">📊 DATABASE INFO</div>
            <div style="line-height: 1.8; font-size: 12px;">
                <span style="color: #2ecc71;">feature_id:</span> {obj.pk}<br>
                <span style="color: #2ecc71;">layer_id:</span> {obj.layer.pk}<br>
                <span style="color: #2ecc71;">layer_slug:</span> "{obj.layer.slug}"<br>
                <span style="color: #2ecc71;">city_id:</span> {obj.layer.city.pk}<br>
                <span style="color: #2ecc71;">source_layer:</span> "{obj.source_layer_name or 'N/A'}"<br>
                <span style="color: #2ecc71;">zone_category:</span> "{obj.zone_category or 'N/A'}"<br>
                <span style="color: #2ecc71;">geometry_type:</span> "{obj.geometry.geom_type if obj.geometry else 'N/A'}"<br>
                <span style="color: #2ecc71;">srid:</span> {obj.geometry.srid if obj.geometry else 'N/A'}<br>
                <span style="color: #2ecc71;">area:</span> {obj.area or 'null'}<br>
            </div>
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #34495e;">
                <div style="color: #e67e22; font-weight: bold; margin-bottom: 5px;">SQL Queries:</div>
                <code style="color: #95a5a6; font-size: 10px;">
                    -- Get feature<br>
                    SELECT * FROM geo_features WHERE id = {obj.pk};<br><br>
                    
                    -- Get feature with layer<br>
                    SELECT f.*, l.slug as layer_slug, c.name as city_name<br>
                    FROM geo_features f<br>
                    JOIN data_layers l ON f.layer_id = l.id<br>
                    JOIN cities c ON l.city_id = c.id<br>
                    WHERE f.id = {obj.pk};<br><br>
                    
                    -- Check geometry validity<br>
                    SELECT ST_IsValid(geometry) as is_valid,<br>
                           ST_GeometryType(geometry) as geom_type,<br>
                           ST_SRID(geometry) as srid<br>
                    FROM geo_features WHERE id = {obj.pk};
                </code>
            </div>
        </div>
        """
        return format_html(info)
    get_technical_info.short_description = 'Technical Information'
    
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