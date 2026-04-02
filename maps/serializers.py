# serializers.py - Enhanced with PLU and ESRI support

from django.conf import settings
from rest_framework import serializers

from .tile_path_service import (
    public_https_base_for_s3_tile_prefix,
    tile_proxy_png_template_from_s3_tile_path,
)
from .developer_listing_map_bounds import (
    DEVELOPER_LISTING_DEFAULT_ZOOM,
    recommended_zoom_from_area,
    tighten_bounds_for_map_fit,
)
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
    layer_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = LayerGroup
        fields = [
            'id', 'name', 'slug', 'description',
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

class DataLayerSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    bbox = serializers.SerializerMethodField()
    has_tiles = serializers.BooleanField(source='tiles_generated', read_only=True)
    plu_codes_summary = serializers.SerializerMethodField()
    layer_group_name = serializers.CharField(source='layer_group.name', read_only=True)
    
    class Meta:
        model = DataLayer
        fields = [
            'id', 'name', 'slug', 'city_name',
            'description', 'file_format', 'categorization_method', 'geometry_type',
            'feature_count', 'is_processed', 'has_tiles', 'primary_plu_codes',
            'plu_codes_summary', 'bbox', 'data_source', 'created_at',
            'layer_group', 'layer_group_name',
            'is_directory', 'file_pattern'
        ]
    
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
    city_name = serializers.CharField(source='city.name', read_only=True)
    
    class Meta:
        model = PLUCodeMapping
        fields = [
            'plu_code', 'plu_description',
            'city_name', 'secondary_codes', 'feature_count', 'last_used',
            'notes', 'is_active'
        ]

class GeoFeatureSerializer(GeoFeatureModelSerializer):
    layer_name = serializers.CharField(source='layer.name', read_only=True)
    city_name = serializers.CharField(source='layer.city.name', read_only=True)
    color = serializers.SerializerMethodField()
    
    class Meta:
        model = GeoFeature
        geo_field = 'geometry'
        fields = [
            'id', 'layer_name', 'city_name',
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
    
    class Meta:
        model = DataLayer
        fields = [
            'id', 'name', 'slug', 'city_name',
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


# ================================
# DEVELOPER LISTING SERIALIZERS
# ================================

class TIFMetadataSerializer(serializers.ModelSerializer):
    """Serializer for TIF metadata"""
    bounds = serializers.SerializerMethodField()
    source_bounds = serializers.SerializerMethodField()
    
    class Meta:
        model = TIFMetadata
        fields = [
            'source_crs', 'source_width', 'source_height', 'source_bands',
            'source_bounds', 'reprojected_width', 'reprojected_height',
            'bounds', 'transform_matrix', 'min_zoom', 'max_zoom', 'tile_size',
            'total_tiles_generated', 'tiles_by_zoom', 'processing_time_seconds',
            'file_size_bytes', 'created_at', 'updated_at'
        ]
    
    def get_bounds(self, obj):
        """Get WGS84 bounds"""
        return {
            'west': obj.bounds_west,
            'south': obj.bounds_south,
            'east': obj.bounds_east,
            'north': obj.bounds_north
        }
    
    def get_source_bounds(self, obj):
        """Get source CRS bounds"""
        return {
            'west': obj.source_bounds_west,
            'south': obj.source_bounds_south,
            'east': obj.source_bounds_east,
            'north': obj.source_bounds_north
        }


class DeveloperListingMediaSerializer(serializers.ModelSerializer):
    """Serializer for developer listing media"""
    tif_metadata = TIFMetadataSerializer(read_only=True)
    tile_url_template = serializers.SerializerMethodField()
    tiles_status = serializers.SerializerMethodField()
    
    class Meta:
        model = DeveloperListingMedia
        fields = [
            'id', 'backend_media_id', 'media_type', 'category',
            'file_name', 'file_url', 's3_path', 'is_tif', 's3_tile_path',
            'tiles_generated', 'tiles_generation_started_at',
            'tiles_generation_completed_at', 'tiles_generation_error',
            'total_tiles_generated', 'media_data', 'tif_metadata',
            'tile_url_template', 'tiles_status', 'created_at', 'updated_at'
        ]
    
    def get_tile_url_template(self, obj):
        """Get tile URL template for this media (Django /api/tiles proxy for developer rasters)."""
        if obj.is_tif and obj.tiles_generated and obj.s3_tile_path:
            t = tile_proxy_png_template_from_s3_tile_path(obj.s3_tile_path)
            if t:
                return t
            base = public_https_base_for_s3_tile_prefix(obj.s3_tile_path)
            return f"{base}/{obj.s3_tile_path}/{{z}}/{{x}}/{{y}}.png"
        return None
    
    def get_tiles_status(self, obj):
        """Get human-readable tile status"""
        if not obj.is_tif:
            return 'not_applicable'
        if obj.tiles_generated:
            return 'completed'
        elif obj.tiles_generation_started_at:
            return 'in_progress'
        elif obj.tiles_generation_error:
            return 'error'
        else:
            return 'pending'


class DeveloperListingMediaMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for media (without full metadata)"""
    tiles_status = serializers.SerializerMethodField()
    
    class Meta:
        model = DeveloperListingMedia
        fields = [
            'id', 'backend_media_id', 'media_type', 'category',
            'file_name', 'file_url', 'is_tif', 'tiles_generated',
            'total_tiles_generated', 'tiles_status'
        ]
    
    def get_tiles_status(self, obj):
        """Get human-readable tile status"""
        if not obj.is_tif:
            return 'not_applicable'
        if obj.tiles_generated:
            return 'completed'
        elif obj.tiles_generation_started_at:
            return 'in_progress'
        elif obj.tiles_generation_error:
            return 'error'
        else:
            return 'pending'


class WebhookEventSerializer(serializers.ModelSerializer):
    """Serializer for webhook events"""

    class Meta:
        model = WebhookEvent
        fields = [
            'id', 'event_type', 'action', 'listing_type', 'listing_id',
            'payload', 'processed', 'processed_at', 'processing_error',
            'tiles_generated', 'tif_files_processed', 'processing_result',
            'tile_generation_logs',
            'request_ip', 'received_at', 'created_at'
        ]


class WebhookEventMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for webhook events (without full payload)"""
    
    class Meta:
        model = WebhookEvent
        fields = [
            'id', 'event_type', 'action', 'processed', 'processed_at',
            'tiles_generated', 'tif_files_processed', 'received_at'
        ]


class DeveloperListingSerializer(serializers.ModelSerializer):
    """Serializer for developer listings"""
    media_files = DeveloperListingMediaMinimalSerializer(many=True, read_only=True)
    media_summary = serializers.SerializerMethodField()
    tile_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = DeveloperListing
        fields = [
            'id', 'listing_type', 'backend_listing_id', 'listing_data',
            'name', 'description', 'location', 'city', 'state', 'is_active',
            'last_webhook_event', 'backend_created_at', 'backend_updated_at',
            'created_at', 'updated_at', 'media_files', 'media_summary',
            'enriched_layers', 'enriched_at',
            'tile_summary'
        ]
    
    def get_media_summary(self, obj):
        """Get media file summary"""
        media_files = obj.media_files.all()
        return {
            'total_media': media_files.count(),
            'total_images': media_files.filter(media_type='image').count(),
            'total_videos': media_files.filter(media_type='video').count(),
            'total_files': media_files.filter(media_type='file').count(),
            'total_tif_files': media_files.filter(is_tif=True).count(),
        }
    
    def get_tile_summary(self, obj):
        """Get tile generation summary"""
        tif_media = obj.media_files.filter(is_tif=True)
        tif_generated = tif_media.filter(tiles_generated=True)
        
        return {
            'total_tif_files': tif_media.count(),
            'tiles_generated': tif_generated.count(),
            'tiles_pending': tif_media.filter(tiles_generated=False, tiles_generation_error='').count(),
            'tiles_in_progress': tif_media.filter(tiles_generation_started_at__isnull=False, tiles_generated=False).count(),
            'tiles_failed': tif_media.exclude(tiles_generation_error='').count(),
            'total_tiles_count': sum(m.total_tiles_generated for m in tif_generated)
        }


class DeveloperListingDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for developer listings (with full media details)"""
    media_files = DeveloperListingMediaSerializer(many=True, read_only=True)
    recent_webhook_events = serializers.SerializerMethodField()
    media_summary = serializers.SerializerMethodField()
    tile_summary = serializers.SerializerMethodField()
    bounds = serializers.SerializerMethodField()
    zoom_levels = serializers.SerializerMethodField()
    center = serializers.SerializerMethodField()
    data_layers = serializers.SerializerMethodField()
    
    class Meta:
        model = DeveloperListing
        fields = [
            'id', 'listing_type', 'backend_listing_id', 'listing_data',
            'name', 'description', 'location', 'city', 'state', 'is_active',
            'last_webhook_event', 'backend_created_at', 'backend_updated_at',
            'created_at', 'updated_at', 'media_files', 'recent_webhook_events',
            'media_summary', 'tile_summary', 'bounds', 'zoom_levels', 'center',
            'data_layers', 'enriched_layers', 'enriched_at'
        ]
    
    def get_recent_webhook_events(self, obj):
        """Get recent webhook events for this listing"""
        events = WebhookEvent.objects.filter(
            listing_type=obj.listing_type,
            listing_id=obj.backend_listing_id
        ).order_by('-received_at')[:10]
        return WebhookEventMinimalSerializer(events, many=True).data
    
    def get_media_summary(self, obj):
        """Get media file summary"""
        media_files = obj.media_files.all()
        return {
            'total_media': media_files.count(),
            'total_images': media_files.filter(media_type='image').count(),
            'total_videos': media_files.filter(media_type='video').count(),
            'total_files': media_files.filter(media_type='file').count(),
            'total_tif_files': media_files.filter(is_tif=True).count(),
        }
    
    def get_tile_summary(self, obj):
        """Get tile generation summary"""
        tif_media = obj.media_files.filter(is_tif=True)
        tif_generated = tif_media.filter(tiles_generated=True)
        
        return {
            'total_tif_files': tif_media.count(),
            'tiles_generated': tif_generated.count(),
            'tiles_pending': tif_media.filter(tiles_generated=False, tiles_generation_error='').count(),
            'tiles_in_progress': tif_media.filter(tiles_generation_started_at__isnull=False, tiles_generated=False).count(),
            'tiles_failed': tif_media.exclude(tiles_generation_error='').count(),
            'total_tiles_count': sum(m.total_tiles_generated for m in tif_generated)
        }
    
    def get_bounds(self, obj):
        """
        Combined TIF union bounds, tightened to a mercantile viewport at recommended zoom
        (default 18) when zoom >= 15 so map.fitBounds aligns with zoom_levels.
        """
        from maps.models import TIFMetadata
        
        # Get all TIF metadata for this listing
        tif_metadata_list = TIFMetadata.objects.filter(
            media__listing=obj,
            media__is_tif=True,
            media__tiles_generated=True
        )
        
        if not tif_metadata_list.exists():
            return None
        
        # Calculate combined bounds
        west = min([tm.bounds_west for tm in tif_metadata_list if tm.bounds_west is not None], default=None)
        south = min([tm.bounds_south for tm in tif_metadata_list if tm.bounds_south is not None], default=None)
        east = max([tm.bounds_east for tm in tif_metadata_list if tm.bounds_east is not None], default=None)
        north = max([tm.bounds_north for tm in tif_metadata_list if tm.bounds_north is not None], default=None)
        
        if west is not None and south is not None and east is not None and north is not None:
            zoom_mins = [tm.min_zoom for tm in tif_metadata_list if tm.min_zoom is not None]
            zoom_maxs = [tm.max_zoom for tm in tif_metadata_list if tm.max_zoom is not None]
            min_z = min(zoom_mins) if zoom_mins else 8
            max_z = max(zoom_maxs) if zoom_maxs else 18
            area = (east - west) * (north - south)
            rec = max(min_z, min(recommended_zoom_from_area(area), max_z))
            west, south, east, north = tighten_bounds_for_map_fit(west, south, east, north, rec)
            return {
                'west': west,
                'south': south,
                'east': east,
                'north': north,
                'bbox': [west, south, east, north],  # Format: [minLng, minLat, maxLng, maxLat]
                'leaflet_bounds': [[south, west], [north, east]]  # Format for Leaflet: [[lat, lng], [lat, lng]]
            }
        
        return None
    
    def get_zoom_levels(self, obj):
        """
        Get zoom level information from TIF files
        Returns min/max zoom and calculated appropriate zoom level for viewing
        """
        from maps.models import TIFMetadata
        
        # Get all TIF metadata for this listing
        tif_metadata_list = TIFMetadata.objects.filter(
            media__listing=obj,
            media__is_tif=True,
            media__tiles_generated=True
        )
        
        if not tif_metadata_list.exists():
            return None
        
        zoom_mins = [tm.min_zoom for tm in tif_metadata_list if tm.min_zoom is not None]
        zoom_maxs = [tm.max_zoom for tm in tif_metadata_list if tm.max_zoom is not None]
        min_zoom = min(zoom_mins) if zoom_mins else 8
        max_zoom = max(zoom_maxs) if zoom_maxs else 18

        # Use full union bbox for zoom (same as map-data), not tightened get_bounds() area
        fw = min([tm.bounds_west for tm in tif_metadata_list if tm.bounds_west is not None], default=None)
        fs = min([tm.bounds_south for tm in tif_metadata_list if tm.bounds_south is not None], default=None)
        fe = max([tm.bounds_east for tm in tif_metadata_list if tm.bounds_east is not None], default=None)
        fn = max([tm.bounds_north for tm in tif_metadata_list if tm.bounds_north is not None], default=None)
        if fw is not None and fs is not None and fe is not None and fn is not None:
            area = (fe - fw) * (fn - fs)
            appropriate_zoom = max(
                min_zoom, min(recommended_zoom_from_area(area), max_zoom)
            )
        else:
            appropriate_zoom = max(min_zoom, min(DEVELOPER_LISTING_DEFAULT_ZOOM, max_zoom))
        
        return {
            'min_zoom': min_zoom,
            'max_zoom': max_zoom,
            'default_zoom': appropriate_zoom,
            'recommended_zoom': appropriate_zoom
        }
    
    def get_center(self, obj):
        """
        Get center coordinates from bounds
        Returns the center point of all TIF files
        """
        bounds = self.get_bounds(obj)
        if bounds:
            center_lat = (bounds['south'] + bounds['north']) / 2
            center_lng = (bounds['west'] + bounds['east']) / 2
            return {
                'lat': center_lat,
                'lng': center_lng,
                'coordinates': [center_lng, center_lat]  # [lng, lat] for GeoJSON
            }
        return None
    
    def get_data_layers(self, obj):
        """
        Get DataLayer information for TIF files in this listing
        Returns layer slugs and IDs for accessing via layer APIs
        """
        from maps.models import DataLayer, GeoFeature
        
        # Find data layers created for this listing's TIF files
        # They have slug pattern: {listing_type}-{listing_id}-{filename}
        slug_prefix = f"{obj.listing_type}-{obj.backend_listing_id}-"
        
        layers = DataLayer.objects.filter(
            slug__startswith=slug_prefix,
            category__code='DEVELOPER_LISTING'
        ).select_related('city', 'category')
        
        if not layers.exists():
            return []
        
        result = []
        for layer in layers:
            # Get the GeoFeature to access bounds polygon
            feature = layer.geofeature_set.first()
            
            layer_info = {
                'id': layer.id,
                'name': layer.name,
                'slug': layer.slug,
                'city': {
                    'name': layer.city.name,
                    'slug': layer.city.slug
                },
                'bounds': {
                    'west': layer.bbox_xmin,
                    'south': layer.bbox_ymin,
                    'east': layer.bbox_xmax,
                    'north': layer.bbox_ymax
                } if layer.bbox_xmin else None,
                'geometry_type': layer.geometry_type,
                'is_processed': layer.is_processed,
                'tiles_generated': layer.tiles_generated,
                'is_visible': layer.is_true,
                'feature_count': layer.feature_count
            }
            
            # Add feature properties if available
            if feature and feature.properties:
                layer_info['tile_url_template'] = feature.properties.get('tile_url_template')
                layer_info['s3_tile_path'] = feature.properties.get('s3_tile_path')
            
            result.append(layer_info)
        
        return result
