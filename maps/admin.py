from django.contrib import admin
from django.contrib.gis.admin import OSMGeoAdmin
from .models import City, LayerCategory, DataLayer, GeoFeature, VectorTileLayer
from .models import (
    State, City, LayerCategory, DataLayer, GeoFeature, 
    VectorTileLayer, LayerGroup, LayerConfig
)

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'state_ref', 'is_active', 'created_at']
    list_filter = ['state_ref', 'is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(LayerGroup)
class LayerGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'category', 'is_visible', 'display_order']
    list_filter = ['city', 'category', 'is_visible']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(LayerCategory)
class LayerCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'default_color', 'is_active']
    list_filter = ['code', 'is_active']
    search_fields = ['name', 'code']

@admin.register(DataLayer)
class DataLayerAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'category', 'feature_count', 'is_processed', 'tiles_generated']
    list_filter = ['city', 'category', 'is_processed', 'tiles_generated']
    search_fields = ['name', 'slug']

@admin.register(GeoFeature)
class GeoFeatureAdmin(OSMGeoAdmin):
    list_display = ['id', 'layer', 'land_use_type', 'calculated_area']  # Fixed: changed 'area_value' to 'calculated_area'
    list_filter = ['layer__city', 'layer__category', 'land_use_type']
    search_fields = ['name', 'land_use_type']

@admin.register(VectorTileLayer)
class VectorTileLayerAdmin(admin.ModelAdmin):
    list_display = ['layer', 'is_generated', 'total_tiles', 'cache_size_mb']
    list_filter = ['is_generated']


@admin.register(LayerConfig)
class LayerConfigAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'state_name', 'city_name', 'scope', 'status', 
        'access', 'sort_order', 'is_active'
    ]
    list_filter = ['state', 'scope', 'status', 'access', 'is_active']
    search_fields = ['title', 'description', 'state__name', 'city__name']
    prepopulated_fields = {'slug': ('title',)}
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'description')
        }),
        ('Classification', {
            'fields': ('scope', 'status', 'access', 'sort_order', 'is_active')
        }),
        ('Location', {
            'fields': ('state', 'city'),
            'description': 'City is required only for urban_area scope'
        }),
        ('Data Layer Link', {
            'fields': ('data_layer',),
            'classes': ('collapse',),
            'description': 'Optional: Link to actual geospatial data layer'
        }),
        ('Info Popup Content', {
            'fields': ('data_accuracy', 'information_use', 'source_name', 'source_url'),
            'classes': ('collapse',)
        })
    )
    
    def state_name(self, obj):
        return obj.state.name
    state_name.short_description = 'State'
    
    def city_name(self, obj):
        return obj.city.name if obj.city else '-'
    city_name.short_description = 'City'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('state', 'city', 'data_layer')
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "city":
            # Filter cities based on selected state (requires JavaScript for dynamic filtering)
            pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)