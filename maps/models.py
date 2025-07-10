# models.py - Enhanced with PLU support and ESRI compatibility

from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry
import uuid
import json

class City(models.Model):
    """Universal city model"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    state = models.CharField(max_length=50)
    
    # Map center
    center_lat = models.FloatField()
    center_lng = models.FloatField()
    
    # Zoom levels
    min_zoom = models.IntegerField(default=8)
    max_zoom = models.IntegerField(default=18)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'cities'
        verbose_name_plural = 'Cities'
    
    def __str__(self):
        return self.name

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
        ('HEALTHCARE', 'Healthcare'),
        ('CULTURAL', 'Cultural'),
        ('DEFENSE', 'Defense'),
        ('TRANSPORT', 'Transportation'),
        ('UTILITIES', 'Utilities/Infrastructure'),
        ('PROTECTED', 'Protected/Forest'),
        ('PARKS_GREEN', 'Parks/Green Spaces'),
        ('WATER_BODIES', 'Water Bodies'),
        ('AGRICULTURAL', 'Agricultural'),
        ('CEMETERY', 'Cemetery'),
        ('DRAINS', 'Drains'),
        ('HILLS', 'Hills/Topographic'),
        ('SPECIAL', 'Special Use'),
        ('UNCLASSIFIED', 'Unclassified'),
    ]
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30, choices=CATEGORY_TYPES, unique=True)
    description = models.TextField(blank=True)
    
    # Default styling (can be overridden per city)
    default_color = models.CharField(max_length=7, default='#666666')
    default_stroke = models.CharField(max_length=7, default='#333333')
    default_opacity = models.FloatField(default=0.7)
    
    # Display properties
    min_zoom = models.IntegerField(default=8)
    max_zoom = models.IntegerField(default=18)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'layer_categories'
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name

class CityLayerStyle(models.Model):
    """City-specific colors and styling"""
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='layer_styles')
    category = models.ForeignKey(LayerCategory, on_delete=models.CASCADE, related_name='city_styles')
    
    # City-specific styling
    fill_color = models.CharField(max_length=7)
    stroke_color = models.CharField(max_length=7, default='#333333')
    opacity = models.FloatField(default=0.7)
    stroke_width = models.IntegerField(default=1)
    
    # Visibility controls
    is_visible = models.BooleanField(default=True)
    min_zoom = models.IntegerField(null=True, blank=True)
    max_zoom = models.IntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'city_layer_styles'
        unique_together = ('city', 'category')
    
    def __str__(self):
        return f"{self.city.name} - {self.category.name}"

class DataLayer(models.Model):
    """Universal data layer model"""
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
    
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='layers')
    category = models.ForeignKey(LayerCategory, on_delete=models.CASCADE, related_name='layers')
    
    # Basic info
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    description = models.TextField(blank=True)
    
    # File info
    original_filename = models.CharField(max_length=300)
    file_format = models.CharField(max_length=20, choices=FILE_FORMATS)
    file_path = models.CharField(max_length=500, blank=True)
    
    # Categorization info
    categorization_method = models.CharField(max_length=20, choices=CATEGORIZATION_METHODS, default='FILENAME')
    primary_plu_codes = models.JSONField(default=list, blank=True)  # Store detected PLU codes
    
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
    
    # Vector tiles
    tiles_generated = models.BooleanField(default=False)
    tile_cache_size = models.BigIntegerField(default=0)  # Size in bytes
    
    # Metadata
    data_source = models.CharField(max_length=200, blank=True)
    last_updated = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'data_layers'
        unique_together = ('city', 'slug')
        indexes = [
            models.Index(fields=['city', 'category']),
            models.Index(fields=['is_processed']),
            models.Index(fields=['tiles_generated']),
            models.Index(fields=['categorization_method']),
        ]
    
    def calculate_bbox(self):
        """Auto-calculate layer bounds"""
        from django.contrib.gis.db.models import Extent
        extent = self.features.aggregate(extent=Extent('geometry'))['extent']
        if extent:
            self.bbox_xmin, self.bbox_ymin, self.bbox_xmax, self.bbox_ymax = extent
            self.save(update_fields=['bbox_xmin', 'bbox_ymin', 'bbox_xmax', 'bbox_ymax'])
    
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
    
    def __str__(self):
        return f"{self.city.name} - {self.name}"

class GeoFeature(models.Model):
    """Enhanced feature model with full PLU support"""
    layer = models.ForeignKey(DataLayer, on_delete=models.CASCADE, related_name='features')
    
    # Original identifiers
    source_fid = models.BigIntegerField(null=True, blank=True)
    source_object_id = models.BigIntegerField(null=True, blank=True)
    
    # Main geometry (with optimized precision)
    geometry = models.GeometryField(srid=4326)
    
    # Universal attributes (present in most datasets)
    name = models.CharField(max_length=200, blank=True)
    category_name = models.CharField(max_length=100, blank=True)
    
    # Administrative divisions
    state = models.CharField(max_length=50, blank=True)
    district = models.CharField(max_length=50, blank=True)
    mandal = models.CharField(max_length=50, blank=True)
    village = models.CharField(max_length=100, blank=True)

    township = models.CharField(max_length=50, blank=True)      # Amaravati township
    sector = models.CharField(max_length=50, blank=True)        # Amaravati sector
    colony = models.CharField(max_length=100, blank=True)       # Amaravati colony
    plot_number = models.CharField(max_length=50, blank=True)
    plot_category = models.CharField(max_length=100, blank=True)
    
    # Enhanced PLU fields (Bangalore-specific but flexible)
    plu_primary_code = models.CharField(max_length=10, blank=True)          # E, M, D, P, Q, I, C, R
    plu_secondary_1 = models.CharField(max_length=50, blank=True)           # Ea, Mt, Dc, etc.
    plu_secondary_2 = models.CharField(max_length=50, blank=True)           # Eaa, Mtg, Dc, etc.
    plu_proposed_use = models.CharField(max_length=100, blank=True)         # PLU_prop_l
    plu_development_code = models.IntegerField(null=True, blank=True)       # PLU_F_PD_C
    plu_authority = models.CharField(max_length=50, blank=True)             # PLU_BDA (Ta, Q, etc.)
    plu_ktc_code = models.CharField(max_length=50, blank=True)              # PLU_Tp_KTC
    plu_survey_code = models.CharField(max_length=50, blank=True)           # PLU_Tp_sur
    
    # Derived/computed fields
    derived_category = models.CharField(max_length=50, blank=True)          # Mapped from PLU codes
    land_use_type = models.CharField(max_length=100, blank=True)            # General land use
    land_use_code = models.CharField(max_length=50, blank=True)             # PLU_Cd
    zoning = models.CharField(max_length=100, blank=True)                   # Zoning classification
    
    # Area/size attributes (from source)
    source_area_value = models.FloatField(null=True, blank=True)            # Shape_Leng or area
    source_length_value = models.FloatField(null=True, blank=True)          # SHAPE.STArea()
    source_perimeter_value = models.FloatField(null=True, blank=True)       # SHAPE.STLength()
    
    # Auto-calculated geometry properties (optimized precision)
    calculated_area = models.FloatField(null=True, blank=True)
    calculated_perimeter = models.FloatField(null=True, blank=True)
    calculated_centroid_lat = models.FloatField(null=True, blank=True)
    calculated_centroid_lng = models.FloatField(null=True, blank=True)
    
    # Store all other attributes as JSON
    source_attributes = models.JSONField(default=dict, blank=True)
    
    # Processing info
    is_valid = models.BooleanField(default=True)
    validation_notes = models.TextField(blank=True)
    geometry_simplified = models.BooleanField(default=False)
    original_precision = models.IntegerField(null=True, blank=True)         # Track original decimal places
    rule_id = models.IntegerField(null=True, blank=True)          # RuleID from Vizag data
    override_value = models.CharField(max_length=100, blank=True) # Override from Vizag data
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'geo_features'
        indexes = [
            models.Index(fields=['layer']),
            models.Index(fields=['plu_primary_code']),
            models.Index(fields=['derived_category']),
            models.Index(fields=['land_use_type']),
            models.Index(fields=['district', 'mandal']),
            models.Index(fields=['source_fid']),
            models.Index(fields=['is_valid']),
            models.Index(fields=['plu_authority']),
            models.Index(fields=['township', 'sector']),
            models.Index(fields=['plot_category']),
            models.Index(fields=['colony']),
        ]
    
    def save(self, *args, **kwargs):
        # Auto-calculate geometry properties with optimized precision
        if self.geometry:
            if hasattr(self.geometry, 'area'):
                self.calculated_area = round(self.geometry.area, 6)  # 6 decimal places
            if hasattr(self.geometry, 'length'):
                self.calculated_perimeter = round(self.geometry.length, 6)
            
            # Calculate centroid
            try:
                centroid = self.geometry.centroid
                self.calculated_centroid_lat = round(centroid.y, 8)  # 8 decimals for coordinates
                self.calculated_centroid_lng = round(centroid.x, 8)
            except:
                pass
        
        super().save(*args, **kwargs)
    
    def get_display_name(self):
        """Get best available name for display"""
        if self.name:
            return self.name
        elif self.plu_proposed_use:
            return self.plu_proposed_use
        elif self.derived_category:
            return self.derived_category
        else:
            return f"Feature {self.source_fid or self.id}"
    
    def get_plu_description(self):
        """Get human-readable PLU description"""
        parts = []
        if self.plu_primary_code:
            parts.append(f"Primary: {self.plu_primary_code}")
        if self.plu_secondary_1:
            parts.append(f"Secondary: {self.plu_secondary_1}")
        if self.plu_proposed_use:
            parts.append(f"Proposed: {self.plu_proposed_use}")
        return " | ".join(parts) if parts else "No PLU data"
    
    def __str__(self):
        return f"Feature {self.source_fid or self.id} - {self.get_display_name()}"

class PLUCodeMapping(models.Model):
    """Store PLU code mappings for different cities"""
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='plu_mappings')
    
    # PLU code info
    plu_code = models.CharField(max_length=10)                      # E, M, D, P, Q, etc.
    plu_description = models.CharField(max_length=200, blank=True)  # Human description
    
    # Mapping to standard category
    mapped_category = models.ForeignKey(LayerCategory, on_delete=models.CASCADE)
    
    # Additional context
    secondary_codes = models.JSONField(default=list, blank=True)    # Associated secondary codes
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
    
    def __str__(self):
        return f"Tiles for {self.layer.name if self.layer else 'Combined Layer'}"

class ImportJob(models.Model):
    """Track data import processes with enhanced logging"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('PARTIAL', 'Partially Completed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    city = models.ForeignKey(City, on_delete=models.CASCADE)
    
    # Import details
    filename = models.CharField(max_length=300)
    file_path = models.CharField(max_length=500)
    file_format = models.CharField(max_length=20)
    
    # Mapping info
    category_mapped = models.CharField(max_length=30, blank=True)
    categorization_method = models.CharField(max_length=20, blank=True)
    
    # PLU processing
    plu_codes_detected = models.JSONField(default=list, blank=True)
    plu_mapping_applied = models.BooleanField(default=False)
    
    # Results
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    features_imported = models.IntegerField(default=0)
    features_failed = models.IntegerField(default=0)
    features_skipped = models.IntegerField(default=0)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=list, blank=True)  # Detailed error log
    
    # Processing statistics
    geometry_conversions = models.IntegerField(default=0)      # ESRI → GeoJSON conversions
    coordinate_optimizations = models.IntegerField(default=0)  # Precision reductions
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    processing_duration = models.DurationField(null=True, blank=True)
    
    class Meta:
        db_table = 'import_jobs'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['city', 'status']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        return f"{self.city.name} - {self.filename} ({self.status})"