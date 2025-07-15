from django.contrib import admin
from django.contrib.gis.admin import OSMGeoAdmin
from .models import (
    State, City, LayerCategory, DataLayer, GeoFeature, 
    VectorTileLayer, LayerGroup
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