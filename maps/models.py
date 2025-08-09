# maps/models.py - Complete enhanced models with hierarchical layer support
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
    name = models.CharField(max_length=100, unique=True)   # State name
    slug = models.SlugField(max_length=100, unique=True)   # URL-friendly identifier
    code = models.CharField(max_length=2, unique=True)     # State code like TS, AP, KA
    
    # Map center for state-level view
    center_lat = models.FloatField(null=True, blank=True)
    center_lng = models.FloatField(null=True, blank=True)
    default_zoom = models.IntegerField(default=7)
    
    is_active = models.BooleanField(default=True)          # Is this state active?
    created_at = models.DateTimeField(auto_now_add=True)   # Creation timestamp
    
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
    name = models.CharField(max_length=100, unique=True)   # City name
    slug = models.SlugField(max_length=100, unique=True)   # URL-friendly identifier
    state = models.CharField(max_length=50)                # State name (legacy field)
    state_ref = models.ForeignKey(
        'State',
        on_delete=models.CASCADE,
        related_name='cities',
        null=True,  # Allow null temporarily during migration
        blank=True
    )
    
    # Map center for city-level view
    center_lat = models.FloatField()
    center_lng = models.FloatField()
    
    # Zoom levels for map
    min_zoom = models.IntegerField(default=8)
    max_zoom = models.IntegerField(default=18)
    
    is_active = models.BooleanField(default=True)          # Is this city active?
    created_at = models.DateTimeField(auto_now_add=True)   # Creation timestamp
    
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
    """Universal categories that work across all cities (e.g., Residential, Commercial)"""
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
    
    name = models.CharField(max_length=100)                # Human-readable name
    code = models.CharField(max_length=30, choices=CATEGORY_TYPES, unique=True)  # Unique code
    description = models.TextField(blank=True)             # Description of the category
    
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
# CITY LAYER STYLE MODEL
# ================================

class CityLayerStyle(models.Model):
    """City-specific colors and styling for each category"""
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='layer_styles')
    category = models.ForeignKey(LayerCategory, on_delete=models.CASCADE, related_name='city_styles')
    
    # Style fields
    fill_color = models.CharField(max_length=7)            # Fill color (hex)
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
        indexes = [
            models.Index(fields=['city', 'category']),
        ]
    
    def __str__(self):
        return f"{self.city.name} - {self.category.name}"

# ================================
# LAYER GROUP MODEL
# ================================

class LayerGroup(models.Model):
    """Group of related layers (e.g., all lakes, all masterplan files)"""
    name = models.CharField(max_length=200)                # Group name
    slug = models.SlugField(max_length=200)                # URL-friendly identifier
    description = models.TextField(blank=True)             # Description
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='layer_groups')
    category = models.ForeignKey(LayerCategory, on_delete=models.CASCADE, related_name='layer_groups')
    directory_path = models.CharField(max_length=500)      # Directory for this group's files
    
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
    
    def get_layers_count(self):
        """Get count of layers in this group"""
        return self.layers.count()

# ================================
# DATA LAYER MODEL
# ================================

class DataLayer(models.Model):
    """Universal data layer model (e.g., a GeoJSON file, Shapefile, etc.)"""
    
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
    name = models.CharField(max_length=200)                   # Human-readable name
    slug = models.SlugField(max_length=200)                   # Unique slug
    description = models.TextField(blank=True)                # Description
    
    # File info
    original_filename = models.CharField(max_length=300)      # Original file name
    file_format = models.CharField(max_length=20, choices=FILE_FORMATS)  # File format
    file_path = models.CharField(max_length=500, blank=True)  # Path to file
    
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
    is_processed = models.BooleanField(default=False)         # Has this layer been processed?
    feature_count = models.IntegerField(default=0)            # Number of features
    processing_errors = models.TextField(blank=True)          # Any errors during processing
    
    # Vector tiles
    tiles_generated = models.BooleanField(default=False)      # Have tiles been generated?
    tile_cache_size = models.BigIntegerField(default=0)       # Size in bytes
    
    # Metadata
    data_source = models.CharField(max_length=200, blank=True)
    last_updated = models.DateTimeField(null=True, blank=True)
    
    # Optional link to LayerGroup (for backward compatibility)
    layer_group = models.ForeignKey(
        LayerGroup, 
        on_delete=models.SET_NULL,  # Don't delete layer if group is deleted
        related_name='layers',
        null=True,
        blank=True
    )
    
    # Directory support
    is_directory = models.BooleanField(default=False)
    file_pattern = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="Pattern to match files in directory (e.g., *.geojson)"
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
            models.Index(fields=['categorization_method']),
        ]
    
    def __str__(self):
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
            return {'lat': center_lat, 'lng': center_lng}
        return None
    
    def get_zoom_level_suggestion(self):
        """Suggest appropriate zoom level based on layer bounds"""
        if not self.has_valid_bbox():
            return 10  # Default zoom
        
        # Calculate approximate zoom based on bounding box size
        lat_diff = abs(self.bbox_ymax - self.bbox_ymin)
        lng_diff = abs(self.bbox_xmax - self.bbox_xmin)
        
        # Simple zoom calculation
        max_diff = max(lat_diff, lng_diff)
        
        if max_diff > 1.0:
            return 8   # Very large area
        elif max_diff > 0.1:
            return 10  # Large area
        elif max_diff > 0.01:
            return 12  # Medium area
        else:
            return 14  # Small area
    
    def get_tile_url_template(self, tile_type='png'):
        """Get CloudFront URL template for this layer's tiles"""
        # Replace with your actual CloudFront domain
        base_url = "https://d17yosovmfjm4.cloudfront.net"
        return f"{base_url}/{self.city.slug}/{self.slug}/{{z}}_{{x}}_{{y}}.{tile_type}"
    
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
    
    def get_files(self):
        """Get all files for this layer"""
        if not self.is_directory:
            return [self.file_path] if self.file_path else []
        
        import glob
        import os
        
        pattern = os.path.join(self.file_path, self.file_pattern or '*.geojson')
        return glob.glob(pattern)

# ================================
# GEO FEATURE MODEL
# ================================

class GeoFeature(models.Model):
    """Enhanced feature model with full PLU support and standardized fields"""
    
    layer = models.ForeignKey(DataLayer, on_delete=models.CASCADE, related_name='geofeature_set')
    geometry = models.GeometryField()
    
    # ================================
    # BASIC IDENTIFICATION FIELDS
    # ================================
    name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    source_layer_name = models.CharField(max_length=200, blank=True)
    
    # ================================
    # PLU (PLANNED LAND USE) FIELDS - Bangalore specific
    # ================================
    plu_primary_code = models.CharField(max_length=50, blank=True)           # PLU (main code)
    plu_secondary_1 = models.CharField(max_length=100, blank=True)           # PLU_NAME
    plu_secondary_2 = models.CharField(max_length=50, blank=True)            # Secondary codes
    plu_proposed_use = models.CharField(max_length=100, blank=True)          # PLU_prop_l
    plu_development_code = models.IntegerField(null=True, blank=True)        # PLU_F_PD_C
    plu_authority = models.CharField(max_length=50, blank=True)              # PLU_BDA (Ta, Q, etc.)
    plu_ktc_code = models.CharField(max_length=50, blank=True)               # PLU_Tp_KTC
    plu_survey_code = models.CharField(max_length=50, blank=True)            # PLU_Tp_sur
    
    # ================================
    # DERIVED/COMPUTED FIELDS
    # ================================
    derived_category = models.CharField(max_length=50, blank=True)           # Mapped from PLU codes
    land_use_type = models.CharField(max_length=100, blank=True)             # General land use
    land_use_code = models.CharField(max_length=50, blank=True)              # PLU_Cd or similar
    land_use_name = models.CharField(max_length=200, blank=True)             # Descriptive name
    zoning = models.CharField(max_length=100, blank=True)                    # Zoning classification
    
    # ================================
    # AREA/SIZE ATTRIBUTES
    # ================================
    area_value = models.FloatField(null=True, blank=True)                    # General area field
    area_unit = models.CharField(max_length=20, blank=True)                  # Unit of area
    perimeter_value = models.FloatField(null=True, blank=True)               # Perimeter
    
    # Source data area fields (from original data)
    source_area_value = models.FloatField(null=True, blank=True)             # Shape_Leng or area
    source_length_value = models.FloatField(null=True, blank=True)           # SHAPE.STArea()
    source_perimeter_value = models.FloatField(null=True, blank=True)        # SHAPE.STLength()
    
    # Auto-calculated geometry properties (optimized precision)
    calculated_area = models.FloatField(null=True, blank=True)
    calculated_perimeter = models.FloatField(null=True, blank=True)
    calculated_centroid_lat = models.FloatField(null=True, blank=True)
    calculated_centroid_lng = models.FloatField(null=True, blank=True)
    
    # ================================
    # ADMINISTRATIVE FIELDS
    # ================================
    state = models.CharField(max_length=50, blank=True)
    district = models.CharField(max_length=100, blank=True)
    mandal = models.CharField(max_length=100, blank=True)                    # Mandal/Tehsil
    village = models.CharField(max_length=100, blank=True)
    ward = models.CharField(max_length=50, blank=True)
    survey_number = models.CharField(max_length=50, blank=True)
    
    # Authority information
    authority_name = models.CharField(max_length=100, blank=True)            # HMDA, HUDA, etc.
    
    # ================================
    # URBAN PLANNING FIELDS
    # ================================
    township = models.CharField(max_length=100, blank=True)
    sector = models.CharField(max_length=50, blank=True)
    plot_number = models.CharField(max_length=50, blank=True)
    plot_category = models.CharField(max_length=50, blank=True)
    colony = models.CharField(max_length=100, blank=True)
    
    # ================================
    # SOURCE DATA TRACKING
    # ================================
    source_fid = models.IntegerField(null=True, blank=True)                  # Original FID
    source_object_id = models.IntegerField(null=True, blank=True)            # OBJECTID from source
    
    # ================================
    # PROCESSING METADATA
    # ================================
    is_valid = models.BooleanField(default=True)
    validation_notes = models.TextField(blank=True)
    geometry_simplified = models.BooleanField(default=False)
    original_precision = models.IntegerField(null=True, blank=True)          # Track original decimal places
    
    # Special fields for specific cities
    rule_id = models.IntegerField(null=True, blank=True)                     # RuleID from Vizag data
    override_value = models.CharField(max_length=100, blank=True)            # Override from Vizag data
    original_color = models.CharField(max_length=20, blank=True)             # Original color from data
    
    # Store all other attributes as JSON (flexible storage)
    source_attributes = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'geo_features'
        indexes = [
            models.Index(fields=['layer']),
            models.Index(fields=['layer', 'plu_primary_code']),
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
        """Auto-calculate geometry properties with optimized precision"""
        if self.geometry:
            try:
                # Calculate area
                if hasattr(self.geometry, 'area'):
                    self.calculated_area = round(self.geometry.area, 6)  # 6 decimal places
                
                # Calculate perimeter
                if hasattr(self.geometry, 'length'):
                    self.calculated_perimeter = round(self.geometry.length, 6)
                
                # Calculate centroid
                centroid = self.geometry.centroid
                self.calculated_centroid_lat = round(centroid.y, 8)  # 8 decimals for coordinates
                self.calculated_centroid_lng = round(centroid.x, 8)
            except Exception:
                # If geometry calculation fails, continue without setting values
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
    
    def get_admin_location(self):
        """Get administrative location string"""
        parts = []
        if self.village:
            parts.append(self.village)
        if self.mandal:
            parts.append(self.mandal)
        if self.district:
            parts.append(self.district)
        if self.state:
            parts.append(self.state)
        return ", ".join(parts)
    
    def __str__(self):
        return f"Feature {self.source_fid or self.id} - {self.get_display_name()}"

# ================================
# PLU CODE MAPPING MODEL
# ================================

class PLUCodeMapping(models.Model):
    """Store PLU code mappings for different cities"""
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='plu_mappings')
    
    # PLU code info
    plu_code = models.CharField(max_length=100)
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

# ================================
# VECTOR TILE LAYER MODEL
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
        return f"Tiles for {self.layer.name if self.layer else 'Combined Layer'}"

# ================================
# IMPORT JOB MODEL
# ================================

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
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='import_jobs')
    
    # Import details
    filename = models.CharField(max_length=300)
    file_path = models.CharField(max_length=500, blank=True)
    file_format = models.CharField(max_length=20, blank=True)
    
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
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.city.name} - {self.filename} ({self.status})"
    
    def get_success_rate(self):
        """Calculate success rate percentage"""
        total = self.features_imported + self.features_failed
        if total > 0:
            return (self.features_imported / total) * 100
        return 0

# ================================
# REAL ESTATE MODELS (existing)
# ================================

class Plot(models.Model):
    """Plot data - independent of city layers"""
    plot_id = models.IntegerField(unique=True)
    location = models.PointField()  # Point geometry
    
    # Pricing info
    area_sq_yards = models.IntegerField(null=True, blank=True)
    price_per_sq_yard = models.IntegerField(null=True, blank=True)
    total_price = models.BigIntegerField(null=True, blank=True)  # Calculated
    
    # Display info
    marker_title = models.CharField(max_length=200)
    marker_id = models.CharField(max_length=100)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'plots'
        indexes = [
            models.Index(fields=['plot_id']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"Plot {self.plot_id}: {self.marker_title}"

class Land(models.Model):
    """Land data - independent of city layers"""
    land_id = models.IntegerField(unique=True)
    location = models.PointField()  # Point geometry
    
    area_text = models.CharField(max_length=100)  # "12 Acres", "1 Acre 27 Guntas"
    price_text = models.CharField(max_length=100)  # "₹80 Lakhs/Acre", "₹1.6 Cr/Acre"
    
    # Display info
    marker_title = models.CharField(max_length=200)
    marker_id = models.CharField(max_length=100)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'lands'
        indexes = [
            models.Index(fields=['land_id']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"Land {self.land_id}: {self.marker_title}"