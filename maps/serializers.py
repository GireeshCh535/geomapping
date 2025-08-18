# serializers.py - Enhanced with PLU and ESRI support

from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import *

class StateSerializer(serializers.ModelSerializer):
    city_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = State
        fields = [
            'id', 'name', 'slug', 'code', 'center_lat', 'center_lng',
            'default_zoom', 'is_active', 'city_count', 'created_at'
        ]

class LayerGroupSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    layer_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = LayerGroup
        fields = [
            'id', 'name', 'slug', 'description', 'category_name',
            'directory_path', 'default_color', 'default_stroke',
            'default_opacity', 'display_order', 'is_visible',
            'min_zoom', 'max_zoom', 'layer_count'
        ]

class CitySerializer(serializers.ModelSerializer):
    state_name = serializers.CharField(source='state_ref.name', read_only=True)
    state_code = serializers.CharField(source='state_ref.code', read_only=True)
    layer_count = serializers.IntegerField(read_only=True)
    total_features = serializers.IntegerField(read_only=True)
    layer_groups = LayerGroupSerializer(many=True, read_only=True)
    
    class Meta:
        model = City
        fields = [
            'id', 'name', 'slug', 'state_name', 'state_code',
            'center_lat', 'center_lng', 'min_zoom', 'max_zoom',
            'is_active', 'layer_count', 'total_features',
            'layer_groups', 'created_at'
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
            'default_stroke', 'default_opacity', 'display_order', 
            'is_active', 'layer_count'
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
    layer_group_name = serializers.CharField(source='layer_group.name', read_only=True)
    
    class Meta:
        model = DataLayer
        fields = [
            'id', 'name', 'slug', 'city_name', 'category_name', 'category_code',
            'description', 'file_format', 'categorization_method', 'geometry_type',
            'feature_count', 'is_processed', 'has_tiles', 'primary_plu_codes',
            'plu_codes_summary', 'bbox', 'style', 'data_source', 'created_at',
            'layer_group', 'layer_group_name',
            'is_directory', 'file_pattern'
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
    color = serializers.SerializerMethodField()
    
    class Meta:
        model = GeoFeature
        geo_field = 'geometry'
        fields = [
            'id', 'layer_name', 'city_name', 'category_name',
            'name', 'zone_category', 'zone_subcategory',
            'plu_primary_code', 'plu_secondary_1', 'plu_secondary_2',
            'plu_proposed_use', 'plu_authority',
            'area', 'shape_length', 'shape_area', 'objectid', 'fid',
            'is_valid', 'created_at', 'color'
        ]
    
    def get_color(self, obj):
        """Get the correct color for this feature based on city config"""
        from .config import get_city_config
        
        city_slug = obj.layer.city.slug
        state_slug = obj.layer.city.state_ref.slug if obj.layer.city.state_ref else None
        category_code = obj.zone_category or obj.layer.category.code if obj.layer.category else None
        
        # Get city-specific color
        if state_slug:
            try:
                city_config = get_city_config(state_slug, city_slug)
                if city_config and 'colors' in city_config and category_code:
                    return city_config['colors'].get(category_code, '#666666')
            except:
                pass
        
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
    centroid = serializers.SerializerMethodField()
    
    class Meta:
        model = GeoFeature
        fields = [
            'id', 'layer_name', 'name', 'zone_category',
            'plu_primary_code', 'area', 'is_valid'
        ]
    
    def get_centroid(self, obj):
        """Get feature centroid coordinates"""
        # For now, return None since we don't have calculated centroid fields
        # This can be enhanced later if needed
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
