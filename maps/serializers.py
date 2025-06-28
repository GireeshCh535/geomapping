# serializers.py - Enhanced with PLU and ESRI support

from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import (
    City, LayerCategory, DataLayer, GeoFeature, VectorTileLayer, 
    PLUCodeMapping, ImportJob, CityLayerStyle
)

class CitySerializer(serializers.ModelSerializer):
    layer_count = serializers.IntegerField(read_only=True)
    total_features = serializers.IntegerField(read_only=True)
    has_plu_data = serializers.SerializerMethodField()
    
    class Meta:
        model = City
        fields = [
            'name', 'slug', 'state', 'center_lat', 'center_lng', 
            'min_zoom', 'max_zoom', 'is_active', 'layer_count', 
            'total_features', 'has_plu_data', 'created_at'
        ]
    
    def get_has_plu_data(self, obj):
        """Check if city has PLU code mappings"""
        return PLUCodeMapping.objects.filter(city=obj).exists()

class LayerCategorySerializer(serializers.ModelSerializer):
    layer_count = serializers.SerializerMethodField()
    
    class Meta:
        model = LayerCategory
        fields = [
            'name', 'code', 'description', 'default_color', 
            'default_stroke', 'default_opacity', 'min_zoom', 'max_zoom',
            'display_order', 'is_active', 'layer_count'
        ]
    
    def get_layer_count(self, obj):
        """Get number of layers using this category"""
        return DataLayer.objects.filter(category=obj, is_processed=True).count()

class CityLayerStyleSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = CityLayerStyle
        fields = [
            'category_name', 'fill_color', 'stroke_color', 
            'opacity', 'stroke_width', 'is_visible', 'min_zoom', 'max_zoom'
        ]

class DataLayerSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_code = serializers.CharField(source='category.code', read_only=True)
    style = serializers.SerializerMethodField()
    bbox = serializers.SerializerMethodField()
    has_tiles = serializers.BooleanField(source='tiles_generated', read_only=True)
    plu_codes_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = DataLayer
        fields = [
            'id', 'name', 'slug', 'city_name', 'category_name', 'category_code',
            'description', 'file_format', 'categorization_method', 'geometry_type',
            'feature_count', 'is_processed', 'has_tiles', 'primary_plu_codes',
            'plu_codes_summary', 'bbox', 'style', 'data_source', 'created_at'
        ]
    
    def get_style(self, obj):
        """Get city-specific style for this layer"""
        style_obj = obj.get_style()
        if isinstance(style_obj, dict):
            return style_obj
        
        # If it's a CityLayerStyle object
        return CityLayerStyleSerializer(style_obj).data
    
    def get_bbox(self, obj):
        """Get layer bounding box"""
        if all([obj.bbox_xmin, obj.bbox_ymin, obj.bbox_xmax, obj.bbox_ymax]):
            return {
                'min_lng': obj.bbox_xmin,
                'min_lat': obj.bbox_ymin,
                'max_lng': obj.bbox_xmax,
                'max_lat': obj.bbox_ymax
            }
        return None
    
    def get_plu_codes_summary(self, obj):
        """Get summary of PLU codes in this layer"""
        if obj.primary_plu_codes:
            return {
                'total_codes': len(obj.primary_plu_codes),
                'codes': obj.primary_plu_codes[:5],  # Show first 5
                'has_more': len(obj.primary_plu_codes) > 5
            }
        return None

class PLUCodeMappingSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='mapped_category.name', read_only=True)
    category_code = serializers.CharField(source='mapped_category.code', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    
    class Meta:
        model = PLUCodeMapping
        fields = [
            'plu_code', 'plu_description', 'category_name', 'category_code',
            'city_name', 'secondary_codes', 'feature_count', 'last_used',
            'notes', 'is_active'
        ]

class GeoFeatureSerializer(GeoFeatureModelSerializer):
    layer_name = serializers.CharField(source='layer.name', read_only=True)
    city_name = serializers.CharField(source='layer.city.name', read_only=True)
    category_name = serializers.CharField(source='layer.category.name', read_only=True)
    display_name = serializers.CharField(source='get_display_name', read_only=True)
    plu_description = serializers.CharField(source='get_plu_description', read_only=True)
    color = serializers.SerializerMethodField()
    
    class Meta:
        model = GeoFeature
        geo_field = 'geometry'
        fields = [
            'id', 'layer_name', 'city_name', 'category_name', 'display_name',
            'source_fid', 'name', 'derived_category', 'land_use_type',
            'plu_primary_code', 'plu_secondary_1', 'plu_secondary_2',
            'plu_proposed_use', 'plu_authority', 'plu_description',
            'calculated_area', 'calculated_perimeter', 'source_area_value',
            'is_valid', 'geometry_simplified', 'created_at', 'color'
        ]
    
    def get_color(self, obj):
        """Get the correct color for this feature based on city config"""
        from .config import get_city_config
        
        city_slug = obj.layer.city.slug
        category_code = obj.derived_category
        
        # Get city-specific color
        city_config = get_city_config(city_slug)
        if city_config and 'colors' in city_config:
            return city_config['colors'].get(category_code, '#666666')
        
        # Fallback to layer style
        try:
            style = obj.layer.get_style()
            if isinstance(style, dict):
                return style.get('fill_color', '#666666')
            elif hasattr(style, 'fill_color'):
                return style.fill_color
        except:
            pass
        
        return '#666666'
    

class GeoFeatureListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing features without geometry"""
    layer_name = serializers.CharField(source='layer.name', read_only=True)
    display_name = serializers.CharField(source='get_display_name', read_only=True)
    centroid = serializers.SerializerMethodField()
    
    class Meta:
        model = GeoFeature
        fields = [
            'id', 'layer_name', 'display_name', 'derived_category',
            'plu_primary_code', 'calculated_area', 'centroid', 'is_valid'
        ]
    
    def get_centroid(self, obj):
        """Get feature centroid coordinates"""
        if obj.calculated_centroid_lat and obj.calculated_centroid_lng:
            return {
                'lat': obj.calculated_centroid_lat,
                'lng': obj.calculated_centroid_lng
            }
        return None

class VectorTileLayerSerializer(serializers.ModelSerializer):
    layer_name = serializers.CharField(source='layer.name', read_only=True)
    layer_slug = serializers.CharField(source='layer.slug', read_only=True)
    city_name = serializers.CharField(source='layer.city.name', read_only=True)
    
    class Meta:
        model = VectorTileLayer
        fields = [
            'layer_name', 'layer_slug', 'city_name', 'min_zoom', 'max_zoom',
            'tile_size', 'is_generated', 'total_tiles', 'cache_size_mb',
            'generated_at', 'updated_at'
        ]

class ImportJobSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    duration_seconds = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = ImportJob
        fields = [
            'id', 'city_name', 'filename', 'file_format', 'category_mapped',
            'categorization_method', 'status', 'features_imported', 
            'features_failed', 'features_skipped', 'plu_codes_detected',
            'plu_mapping_applied', 'geometry_conversions', 'coordinate_optimizations',
            'duration_seconds', 'success_rate', 'error_message', 
            'started_at', 'completed_at'
        ]
    
    def get_duration_seconds(self, obj):
        """Get processing duration in seconds"""
        if obj.processing_duration:
            return obj.processing_duration.total_seconds()
        return None
    
    def get_success_rate(self, obj):
        """Calculate import success rate"""
        total = obj.features_imported + obj.features_failed + obj.features_skipped
        if total > 0:
            return round((obj.features_imported / total) * 100, 1)
        return 0

class ImportJobDetailSerializer(ImportJobSerializer):
    """Detailed serializer with error details"""
    
    class Meta(ImportJobSerializer.Meta):
        fields = ImportJobSerializer.Meta.fields + ['error_details']

# Specialized serializers for different use cases

class LayerSummarySerializer(serializers.ModelSerializer):
    """Lightweight layer summary for listings"""
    city_name = serializers.CharField(source='city.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = DataLayer
        fields = [
            'id', 'name', 'slug', 'city_name', 'category_name',
            'feature_count', 'is_processed', 'tiles_generated'
        ]

class FeatureStatsSerializer(serializers.Serializer):
    """Serializer for feature statistics"""
    total_features = serializers.IntegerField()
    valid_features = serializers.IntegerField()
    invalid_features = serializers.IntegerField()
    avg_area = serializers.FloatField()
    total_area = serializers.FloatField()
    unique_plu_codes = serializers.IntegerField(required=False)
    top_categories = serializers.ListField(required=False)

class PLUStatsSerializer(serializers.Serializer):
    """Serializer for PLU statistics"""
    total_plu_features = serializers.IntegerField()
    unique_plu_codes = serializers.IntegerField()
    plu_distribution = serializers.DictField()
    mapping_coverage = serializers.FloatField()
    unmapped_codes = serializers.ListField()

class CityStatsSerializer(serializers.Serializer):
    """Comprehensive city statistics"""
    city = CitySerializer()
    layers = serializers.DictField()
    features = FeatureStatsSerializer()
    plu_codes = PLUStatsSerializer(required=False)
    area_statistics = serializers.DictField()

# API response serializers

class LayerListResponseSerializer(serializers.Serializer):
    """Response serializer for layer lists"""
    city = serializers.CharField()
    total_layers = serializers.IntegerField()
    layers = LayerSummarySerializer(many=True)

class FeatureListResponseSerializer(serializers.Serializer):
    """Response serializer for paginated feature lists"""
    layer = serializers.DictField()
    pagination = serializers.DictField()
    features = GeoFeatureListSerializer(many=True)

class TileInfoSerializer(serializers.Serializer):
    """Serializer for tile endpoint information"""
    city = serializers.CharField()
    layer = serializers.CharField()
    zoom_range = serializers.DictField()
    tile_url_template = serializers.CharField()
    style = serializers.DictField()

# Configuration serializers

class CityConfigSerializer(serializers.Serializer):
    """Serializer for city configuration"""
    city_info = serializers.DictField()
    total_files = serializers.IntegerField()
    categories = serializers.ListField()
    colors = serializers.DictField()
    data_format = serializers.CharField()
    has_plu_mapping = serializers.BooleanField()
    statistics = serializers.DictField()

class FileStatusSerializer(serializers.Serializer):
    """Serializer for file import status"""
    category = serializers.CharField()
    imported = serializers.BooleanField()
    color = serializers.CharField()

class CityConfigDetailSerializer(serializers.Serializer):
    """Detailed city configuration serializer"""
    city_info = serializers.DictField()
    file_mappings = serializers.DictField()
    colors = serializers.DictField()
    file_status = serializers.DictField(child=FileStatusSerializer())
    data_format = serializers.CharField()
    coordinate_precision = serializers.IntegerField()
    plu_mapping = serializers.DictField(required=False)