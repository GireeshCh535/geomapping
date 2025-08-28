# maps/models.py
# Complete models with all required fields for the entire system

from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.db.models import Extent
from django.utils.text import slugify
import uuid
import json

# ================================
# STATE MODEL
# ================================

class State(models.Model):
    """State model to organize cities (e.g., Telangana, Karnataka, Delhi NCR)"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    code = models.CharField(max_length=2, unique=True)  # State code like TS, AP, KA
    
    # Map center for state-level view
    center_lat = models.FloatField(null=True, blank=True)
    center_lng = models.FloatField(null=True, blank=True)
    default_zoom = models.IntegerField(default=7)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'states'
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_cities_count(self):
        """Get count of cities in this state"""
        return self.cities.filter(is_active=True).count()
    
    def get_layers_count(self):
        """Get total count of layers in all cities of this state"""
        return DataLayer.objects.filter(city__state_ref=self).count()

# ================================
# CITY MODEL
# ================================

class City(models.Model):
    """Universal city model (e.g., Hyderabad, Bangalore)"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    state = models.CharField(max_length=50)  # Legacy field for backward compatibility
    state_ref = models.ForeignKey(
        'State',
        on_delete=models.CASCADE,
        related_name='cities',
        null=True,
        blank=True
    )
    
    # Map center for city-level view
    center_lat = models.FloatField()
    center_lng = models.FloatField()
    
    # Zoom levels for map
    min_zoom = models.IntegerField(default=8)
    max_zoom = models.IntegerField(default=18)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'cities'
        verbose_name_plural = 'Cities'
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
            models.Index(fields=['state_ref']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_state_name(self):
        """Get state name (prioritize state_ref over legacy state field)"""
        if self.state_ref:
            return self.state_ref.name
        return self.state
    
    def get_layers_count(self):
        """Get count of layers in this city"""
        return self.layers.count()
    
    def get_processed_layers_count(self):
        """Get count of processed layers in this city"""
        return self.layers.filter(is_processed=True).count()
    
    def get_features_count(self):
        """Get total count of features in this city"""
        return GeoFeature.objects.filter(layer__city=self).count()

# ================================
# LAYER CATEGORY MODEL
# ================================

class LayerCategory(models.Model):
    """Universal categories that work across all cities"""
    CATEGORY_TYPES = [
        ('RESIDENTIAL', 'Residential'),
        ('COMMERCIAL', 'Commercial'),
        ('MIXED_USE', 'Mixed Use'),
        ('INDUSTRIAL', 'Industrial'),
        ('HIGH_TECH', 'High Tech'),
        ('GOVERNMENT', 'Government'),
        ('PUBLIC', 'Public/Semi-Public'),
        ('EDUCATION', 'Education'),
        ('HEALTH', 'Health'),
        ('DEFENSE', 'Defense'),
        ('PROTECTED', 'Protected/Forest'),
        ('PARKS_GREEN', 'Parks & Green Spaces'),
        ('WATER_BODIES', 'Water Bodies'),
        ('TRANSPORT', 'Transportation'),
        ('UTILITIES', 'Utilities'),
        ('AGRICULTURAL', 'Agricultural'),
        ('UNCLASSIFIED', 'Unclassified'),
        ('BOUNDARIES', 'Administrative Boundaries'),
        ('BURIAL', 'Burial/Cemetery'),
        ('RELIGIOUS', 'Religious'),
        ('CULTURAL', 'Cultural'),
    ]
    
    code = models.CharField(max_length=50, unique=True, choices=CATEGORY_TYPES)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Default styling
    default_color = models.CharField(max_length=7, default='#CCCCCC')
    default_stroke = models.CharField(max_length=7, default='#333333')
    default_opacity = models.FloatField(default=0.7)
    
    # Display settings
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'layer_categories'
        verbose_name_plural = 'Layer Categories'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_layers_count(self):
        """Get count of layers using this category"""
        return self.layers.count()

# ================================
# CITY LAYER STYLE MODEL (WITH PATTERN SUPPORT)
# ================================

class CityLayerStyle(models.Model):
    """City-specific colors and styling with pattern support"""
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='layer_styles')
    category = models.ForeignKey(LayerCategory, on_delete=models.CASCADE, related_name='city_styles')
    
    # Basic style fields
    fill_color = models.CharField(max_length=7)
    stroke_color = models.CharField(max_length=7, default='#333333')
    opacity = models.FloatField(default=0.7)
    stroke_width = models.IntegerField(default=1)
    
    # Pattern support fields
    FILL_PATTERN_CHOICES = [
        ('SOLID', 'Solid Fill'),
        ('HATCHED', 'Hatched Pattern'),
        ('DOTTED', 'Dotted Pattern'),
        ('STRIPED', 'Striped Pattern'),
        ('CROSS_HATCHED', 'Cross-Hatched Pattern'),
    ]
    
    fill_pattern = models.CharField(
        max_length=20,
        choices=FILL_PATTERN_CHOICES,
        default='SOLID',
        help_text='Type of fill pattern to use'
    )
    
    pattern_color = models.CharField(
        max_length=7,
        blank=True,
        help_text='Secondary color for patterns'
    )
    pattern_spacing = models.IntegerField(
        default=10,
        help_text='Spacing between pattern elements in pixels'
    )
    pattern_angle = models.IntegerField(
        default=45,
        help_text='Angle for hatched/striped patterns in degrees'
    )
    pattern_size = models.IntegerField(
        default=3,
        help_text='Size of dots or line width for patterns'
    )
    secondary_fill_color = models.CharField(
        max_length=7,
        blank=True,
        help_text='Background solid fill color when using patterns'
    )
    
    # Visibility controls
    is_visible = models.BooleanField(default=True)
    min_zoom = models.IntegerField(null=True, blank=True)
    max_zoom = models.IntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'city_layer_styles'
        unique_together = ('city', 'category')
        indexes = [
            models.Index(fields=['city', 'category']),
        ]
    
    def __str__(self):
        return f"{self.city.name} - {self.category.name} ({self.fill_pattern})"
    
    def get_pattern_config(self):
        """Get pattern configuration as a dict"""
        return {
            'pattern_type': self.fill_pattern,
            'pattern_color': self.pattern_color or self.fill_color,
            'pattern_spacing': self.pattern_spacing,
            'pattern_angle': self.pattern_angle,
            'pattern_size': self.pattern_size,
            'secondary_fill': self.secondary_fill_color
        }

# ================================
# LAYER GROUP MODEL (OPTIONAL)
# ================================

class LayerGroup(models.Model):
    """Group of related layers (e.g., all master plan files)"""
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    description = models.TextField(blank=True)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='layer_groups')
    category = models.ForeignKey(LayerCategory, on_delete=models.CASCADE, related_name='layer_groups')
    directory_path = models.CharField(max_length=500)
    
    # Group-level styling
    default_color = models.CharField(max_length=7, default='#666666')
    default_stroke = models.CharField(max_length=7, default='#333333')
    default_opacity = models.FloatField(default=0.7)
    
    # Display settings
    display_order = models.IntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    min_zoom = models.IntegerField(null=True, blank=True)
    max_zoom = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'layer_groups'
        unique_together = ('city', 'slug')
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['city', 'slug']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        return f"{self.city.name} - {self.name}"

# ================================
# DATA LAYER MODEL (ENHANCED)
# ================================

class DataLayer(models.Model):
    """Universal data layer model supporting directory-based structure"""
    
    GEOMETRY_TYPES = [
        ('POLYGON', 'Polygon'),
        ('MULTIPOLYGON', 'MultiPolygon'),
        ('POINT', 'Point'),
        ('LINESTRING', 'LineString'),
        ('MULTILINESTRING', 'MultiLineString'),
    ]
    
    FILE_FORMATS = [
        ('JSON', 'JSON'),
        ('GEOJSON', 'GeoJSON'),
        ('ESRI_JSON', 'ESRI JSON'),
        ('SHP', 'Shapefile'),
        ('KML', 'KML'),
        ('CSV', 'CSV'),
    ]
    
    CATEGORIZATION_METHODS = [
        ('FILENAME', 'Filename-based'),
        ('PLU_CODE', 'PLU Code-based'),
        ('ATTRIBUTE', 'Attribute-based'),
        ('MANUAL', 'Manual'),
    ]
    
    # Core relationships
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='layers')
    category = models.ForeignKey(LayerCategory, on_delete=models.CASCADE, related_name='layers')
    
    # Basic info
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    description = models.TextField(blank=True)
    
    # File info
    original_filename = models.CharField(max_length=300, blank=True)
    file_format = models.CharField(max_length=20, choices=FILE_FORMATS, default='GEOJSON')
    file_path = models.CharField(max_length=500, blank=True)
    
    # Directory support for layer groups
    is_directory = models.BooleanField(
        default=False,
        help_text='True if this layer represents a directory of files'
    )
    file_pattern = models.CharField(
        max_length=100,
        blank=True,
        help_text='Pattern to match files in directory (e.g., *.geojson)'
    )
    source_files = models.JSONField(
        default=list,
        blank=True,
        help_text='List of source files in this directory-based layer'
    )
    
    # Categorization info
    categorization_method = models.CharField(max_length=20, choices=CATEGORIZATION_METHODS, default='FILENAME')
    primary_plu_codes = models.JSONField(default=list, blank=True)
    
    # Geometry info
    geometry_type = models.CharField(max_length=20, choices=GEOMETRY_TYPES, null=True, blank=True)
    
    # Bounding box for performance
    bbox_xmin = models.FloatField(null=True, blank=True)
    bbox_ymin = models.FloatField(null=True, blank=True)
    bbox_xmax = models.FloatField(null=True, blank=True)
    bbox_ymax = models.FloatField(null=True, blank=True)
    
    # Processing status
    is_processed = models.BooleanField(default=False)
    feature_count = models.IntegerField(default=0)
    processing_errors = models.TextField(blank=True)
    
    # Layer visibility control
    is_true = models.BooleanField(
        default=False,
        help_text='Controls layer visibility - False by default for all layers'
    )
    
    # Vector tiles
    tiles_generated = models.BooleanField(default=False)
    tile_cache_size = models.BigIntegerField(default=0)
    
    # Metadata
    data_source = models.CharField(max_length=200, blank=True)
    last_updated = models.DateTimeField(null=True, blank=True)
    
    # Optional link to LayerGroup
    layer_group = models.ForeignKey(
        LayerGroup,
        on_delete=models.SET_NULL,
        related_name='layers',
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'data_layers'
        unique_together = ('city', 'slug')
        indexes = [
            models.Index(fields=['city', 'category']),
            models.Index(fields=['city', 'slug']),
            models.Index(fields=['is_processed']),
            models.Index(fields=['tiles_generated']),
            models.Index(fields=['is_directory']),
            models.Index(fields=['is_true']),
        ]
    
    def __str__(self):
        if self.is_directory:
            return f"{self.city.name} - {self.name} (Directory: {len(self.source_files)} files)"
        return f"{self.city.name} - {self.name}"
    
    def calculate_bbox(self):
        """Calculate and save bounding box for this layer from all its features"""
        extent = self.geofeature_set.aggregate(
            extent=Extent('geometry')
        )['extent']
        
        if extent:
            self.bbox_xmin, self.bbox_ymin, self.bbox_xmax, self.bbox_ymax = extent
            self.save(update_fields=['bbox_xmin', 'bbox_ymin', 'bbox_xmax', 'bbox_ymax'])
            return extent
        return None
    
    def has_valid_bbox(self):
        """Check if layer has a valid bounding box"""
        return all([
            self.bbox_xmin is not None,
            self.bbox_ymin is not None,
            self.bbox_xmax is not None,
            self.bbox_ymax is not None
        ])
    
    def get_center_point(self):
        """Get center point of the layer"""
        if self.has_valid_bbox():
            center_lat = (self.bbox_ymin + self.bbox_ymax) / 2
            center_lng = (self.bbox_xmin + self.bbox_xmax) / 2
            return center_lat, center_lng
        return None
    
    def get_files(self):
        """Get all files for this layer"""
        if not self.is_directory:
            return [self.file_path] if self.file_path else []
        
        import glob
        import os
        
        if self.file_path and os.path.exists(self.file_path):
            pattern = os.path.join(self.file_path, self.file_pattern or '*.geojson')
            return glob.glob(pattern)
        
        return self.source_files or []
    
    def get_file_features_breakdown(self):
        """Get feature count breakdown by source file"""
        from django.db.models import Count
        
        if not self.is_directory:
            return {self.name: self.feature_count}
        
        breakdown = self.geofeature_set.values('source_layer_name').annotate(
            count=Count('id')
        ).order_by('source_layer_name')
        
        return {item['source_layer_name']: item['count'] for item in breakdown}
    
    def get_style(self):
        """Get city-specific style for this layer"""
        try:
            return CityLayerStyle.objects.get(city=self.city, category=self.category)
        except CityLayerStyle.DoesNotExist:
            # Return default style
            return {
                'fill_color': self.category.default_color,
                'stroke_color': self.category.default_stroke,
                'opacity': self.category.default_opacity
            }

# ================================
# GEO FEATURE MODEL (COMPLETE)
# ================================

class GeoFeature(models.Model):
    """Enhanced feature model with full support for all cities and data formats"""
    
    layer = models.ForeignKey(DataLayer, on_delete=models.CASCADE, related_name='geofeature_set')
    geometry = models.GeometryField()
    
    # ================================
    # SOURCE TRACKING
    # ================================
    source_layer_name = models.CharField(
        max_length=200,
        blank=True,
        help_text='Original file name this feature came from (e.g., Agricultural_Land)'
    )
    
    # ================================
    # BASIC IDENTIFICATION FIELDS
    # ================================
    name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    
    # ================================
    # GENERIC ZONE/CATEGORY FIELDS (ALL CITIES)
    # ================================
    zone_category = models.CharField(
        max_length=200,
        blank=True,
        help_text='Main zone/category from source data'
    )
    zone_subcategory = models.CharField(
        max_length=200,
        blank=True,
        help_text='Sub-category or secondary classification'
    )
    
    # ================================
    # BENGALURU SPECIFIC PLU FIELDS (ESRI JSON)
    # ================================
    plu_primary_code = models.CharField(
        max_length=50,
        blank=True,
        help_text='PLU_Cd from Bengaluru data'
    )
    plu_secondary_1 = models.CharField(
        max_length=100,
        blank=True,
        help_text='PLU_NAME or PLU_prop_l'
    )
    plu_secondary_2 = models.CharField(
        max_length=50,
        blank=True,
        help_text='Secondary PLU codes'
    )
    plu_proposed_use = models.CharField(
        max_length=100,
        blank=True,
        help_text='PLU_prop_l - Proposed land use'
    )
    plu_development_code = models.IntegerField(
        null=True,
        blank=True,
        help_text='PLU_F_PD_C - Development code'
    )
    plu_authority = models.CharField(
        max_length=50,
        blank=True,
        help_text='PLU_BDA - Authority (Ta, Q, U, etc.)'
    )
    
    # ================================
    # WARANGAL SPECIFIC FIELDS
    # ================================
    kuda = models.CharField(max_length=50, blank=True)
    ex_pr = models.CharField(max_length=10, blank=True)
    
    # ================================
    # AMARAVATI SPECIFIC FIELDS
    # ================================
    plot_category = models.CharField(
        max_length=100,
        blank=True,
        help_text='plot_categ from Amaravati'
    )
    symbology = models.CharField(
        max_length=100,
        blank=True,
        help_text='symbology field from Amaravati'
    )
    township = models.IntegerField(null=True, blank=True)
    sector = models.IntegerField(null=True, blank=True)
    colony = models.IntegerField(null=True, blank=True)
    block = models.IntegerField(null=True, blank=True)
    
    # ================================
    # VISAKHAPATNAM SPECIFIC FIELDS
    # ================================
    mandal = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    village = models.CharField(max_length=100, blank=True)
    rule_id = models.IntegerField(null=True, blank=True)
    
    # ================================
    # NUMERIC FIELDS (COMMON)
    # ================================
    area = models.FloatField(null=True, blank=True)
    shape_length = models.FloatField(null=True, blank=True)
    shape_area = models.FloatField(null=True, blank=True)
    objectid = models.IntegerField(null=True, blank=True)
    fid = models.IntegerField(null=True, blank=True)
    
    # ================================
    # JSON STORAGE FOR ALL PROPERTIES
    # ================================
    properties = models.JSONField(
        default=dict,
        blank=True,
        help_text='Complete original properties from source data'
    )
    
    # ================================
    # VALIDATION AND METADATA
    # ================================
    is_valid = models.BooleanField(default=True)
    validation_errors = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'geo_features'
        indexes = [
            models.Index(fields=['layer', 'source_layer_name']),
            models.Index(fields=['layer', 'zone_category']),
            models.Index(fields=['layer', 'plu_primary_code']),
            models.Index(fields=['is_valid']),
            models.Index(fields=['objectid']),
            models.Index(fields=['fid']),
        ]
    
    def __str__(self):
        if self.source_layer_name:
            return f"{self.layer.name} - {self.source_layer_name} - Feature {self.id}"
        return f"{self.layer.name} - Feature {self.id}"
    
    def get_zone_name(self):
        """Get the appropriate zone name based on city"""
        city_slug = self.layer.city.slug
        
        if city_slug == 'bengaluru':
            return self.plu_secondary_1 or self.plu_proposed_use or self.zone_category
        elif city_slug == 'warangal':
            return self.zone_category or self.properties.get('PLU_NAME', '')
        elif city_slug == 'visakhapatnam':
            return self.zone_category or self.properties.get('Category', '')
        elif city_slug == 'amaravati':
            return self.symbology or self.plot_category or self.zone_category
        else:
            return self.zone_category or self.name
    
    def get_style_config(self):
        """Get style configuration based on zone/category"""
        from maps.config import get_city_style_config
        
        zone_name = self.get_zone_name()
        city_slug = self.layer.city.slug
        
        return get_city_style_config(city_slug, zone_name)

# ================================
# CITY ZONE MAPPING MODEL
# ================================

class CityZoneMapping(models.Model):
    """Map zone names/codes to categories for each city"""
    
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='zone_mappings')
    
    # Zone identification
    zone_name = models.CharField(max_length=200, help_text='Zone name from GEOJSON')
    zone_code = models.CharField(max_length=100, blank=True, help_text='Zone code if different from name')
    
    # Mapping to category and style
    category = models.ForeignKey(LayerCategory, on_delete=models.CASCADE)
    style = models.ForeignKey(CityLayerStyle, on_delete=models.CASCADE)
    
    # Override style for specific zones
    override_fill_color = models.CharField(max_length=7, blank=True)
    override_pattern = models.CharField(
        max_length=20,
        blank=True,
        choices=CityLayerStyle.FILL_PATTERN_CHOICES
    )
    
    # Metadata
    feature_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'city_zone_mappings'
        unique_together = ('city', 'zone_name')
        indexes = [
            models.Index(fields=['city', 'zone_name']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        return f"{self.city.name} - {self.zone_name}"

# ================================
# PLU CODE MAPPING MODEL (OPTIONAL)
# ================================

class PLUCodeMapping(models.Model):
    """Store PLU code mappings for different cities"""
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='plu_mappings')
    
    # PLU code info
    plu_code = models.CharField(max_length=100)
    plu_description = models.CharField(max_length=200, blank=True)
    
    # Mapping to standard category
    mapped_category = models.ForeignKey(LayerCategory, on_delete=models.CASCADE)
    
    # Additional context
    secondary_codes = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    
    # Usage statistics
    feature_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'plu_code_mappings'
        unique_together = ('city', 'plu_code')
        indexes = [
            models.Index(fields=['city', 'plu_code']),
            models.Index(fields=['mapped_category']),
        ]
    
    def __str__(self):
        return f"{self.city.name} - {self.plu_code} → {self.mapped_category.name}"

# ================================
# VECTOR TILE LAYER MODEL (OPTIONAL)
# ================================

class VectorTileLayer(models.Model):
    """Vector tile cache management"""
    layer = models.OneToOneField(DataLayer, on_delete=models.CASCADE, related_name='vector_tiles', null=True, blank=True)
    
    # Tile configuration
    min_zoom = models.IntegerField(default=8)
    max_zoom = models.IntegerField(default=14)
    tile_size = models.IntegerField(default=512)
    
    # Generation status
    is_generated = models.BooleanField(default=False)
    total_tiles = models.IntegerField(default=0)
    cache_size_mb = models.FloatField(default=0.0)
    
    # Paths
    tiles_directory = models.CharField(max_length=500, blank=True)
    mbtiles_file = models.CharField(max_length=500, blank=True)
    
    generated_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vector_tile_layers'
        indexes = [
            models.Index(fields=['layer']),
            models.Index(fields=['is_generated']),
        ]
    
    def __str__(self):
        return f"Vector tiles for {self.layer.name if self.layer else 'Unknown'}"

# ================================
# VALIDATION LOG MODEL (OPTIONAL)
# ================================

class ValidationLog(models.Model):
    """Store validation results for tracking and auditing"""
    
    city = models.ForeignKey('City', on_delete=models.CASCADE, related_name='validation_logs')
    layer = models.ForeignKey('DataLayer', on_delete=models.CASCADE, null=True, blank=True)
    
    validation_type = models.CharField(max_length=50)
    is_valid = models.BooleanField()
    
    # Statistics
    total_features = models.IntegerField(default=0)
    valid_features = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    warning_count = models.IntegerField(default=0)
    
    # Detailed results (JSON)
    validation_report = models.JSONField()
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'validation_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['city', 'validation_type']),
            models.Index(fields=['is_valid']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.city.name} - {self.validation_type} - {'Valid' if self.is_valid else 'Invalid'}"