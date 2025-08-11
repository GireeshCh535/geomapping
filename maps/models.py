# models.py - Enhanced with PLU support and ESRI compatibility

from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry
import uuid
import json

# -----------------------------
# State: Organizes cities by state
# -----------------------------
class State(models.Model):
    """State model to organize cities (e.g., Telangana, Andhra Pradesh)"""
    name = models.CharField(max_length=100, unique=True)  # State name
    slug = models.SlugField(max_length=100, unique=True)  # URL-friendly identifier
    code = models.CharField(max_length=2, unique=True)    # State code like TS, AP
    
    # Map center for state-level view
    center_lat = models.FloatField(null=True, blank=True)
    center_lng = models.FloatField(null=True, blank=True)
    default_zoom = models.IntegerField(default=7)
    
    is_active = models.BooleanField(default=True)         # Is this state active?
    created_at = models.DateTimeField(auto_now_add=True)   # Creation timestamp
    
    class Meta:
        db_table = 'states'
        ordering = ['name']
    
    def __str__(self):
        return self.name

# -----------------------------
# City: Represents a city and its metadata
# -----------------------------
class City(models.Model):
    """Universal city model (e.g., Hyderabad, Bangalore)"""
    name = models.CharField(max_length=100, unique=True)   # City name
    slug = models.SlugField(max_length=100, unique=True)   # URL-friendly identifier
    state = models.CharField(max_length=50)                # State name (legacy)
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
    
    def __str__(self):
        return self.name

# -----------------------------
# LayerCategory: Universal land use/feature categories
# -----------------------------
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
    
    def __str__(self):
        return self.name

# -----------------------------
# CityLayerStyle: Per-city, per-category style overrides
# -----------------------------
class CityLayerStyle(models.Model):
    """City-specific colors and styling for each category with pattern support"""

    FILL_PATTERN_CHOICES = [
        ('solid', 'Solid Fill'),
        ('hatch', 'Hatch Fill'),
        ('dot', 'Dot Fill'),
        ('diagonal_hatch', 'Diagonal Hatch'),
        ('cross_hatch', 'Cross Hatch'),
    ]

    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='layer_styles')
    category = models.ForeignKey(LayerCategory, on_delete=models.CASCADE, related_name='city_styles')
    
    # Basic style fields
    fill_color = models.CharField(max_length=7)            # Fill color (hex)
    stroke_color = models.CharField(max_length=7, default='#333333')
    opacity = models.FloatField(default=0.7)
    stroke_width = models.IntegerField(default=1)

    # Pattern support fields
    fill_pattern = models.CharField(max_length=20, choices=FILL_PATTERN_CHOICES, default='solid')
    pattern_color = models.CharField(max_length=7, blank=True)
    pattern_density = models.IntegerField(default=5, help_text='Pattern density (1-10, lower = denser)')
    pattern_size = models.IntegerField(default=3, help_text='Pattern element size in pixels')
    pattern_rotation = models.FloatField(default=0.0)
    render_notes = models.TextField(blank=True)

    # Visibility controls
    is_visible = models.BooleanField(default=True)
    min_zoom = models.IntegerField(null=True, blank=True)
    max_zoom = models.IntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'city_layer_styles'
        unique_together = ('city', 'category')
    
    def __str__(self):
        return f"{self.city.name} - {self.category.name}"

    def get_pattern_info(self):
        """Get pattern information for rendering"""
        return {
            'type': self.fill_pattern,
            'primary_color': self.fill_color,
            'secondary_color': self.pattern_color or self.stroke_color,
            'density': self.pattern_density,
            'size': self.pattern_size,
            'stroke_width': self.stroke_width,
            'opacity': self.opacity,
            'notes': self.render_notes,
            'rotation': self.pattern_rotation,
        }

    def to_mapbox_style(self):
        """Convert to MapBox style format"""
        style = {
            'fill-color': self.fill_color,
            'fill-opacity': self.opacity,
        }
        if self.stroke_width > 0:
            style.update({
                'fill-outline-color': self.stroke_color,
                'line-width': self.stroke_width,
                'line-color': self.stroke_color,
            })
        return style

# -----------------------------
# LayerGroup: Groups related layers (e.g., all lakes, all masterplan files)
# -----------------------------
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
    
    def __str__(self):
        return f"{self.city.name} - {self.name}"

# -----------------------------
# DataLayer: Represents a single data layer (e.g., a GeoJSON file)
# -----------------------------
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
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='layers')  # Which city this layer belongs to
    category = models.ForeignKey(LayerCategory, on_delete=models.CASCADE, related_name='layers')  # Category
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
    # Add link to LayerGroup (optional, for backward compatibility)
    layer_group = models.ForeignKey(
        LayerGroup, 
        on_delete=models.SET_NULL,  # Don't delete layer if group is deleted
        related_name='layers',
        null=True,
        blank=True
    )
    # Update file_path to handle both files and directories
    is_directory = models.BooleanField(default=False)
    file_pattern = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="Pattern to match files in directory (e.g., *.shp)"
    )
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
    
    def get_files(self):
        """Get all files for this layer"""
        if not self.is_directory:
            return [self.file_path] if self.file_path else []
            
        import glob
        import os
        
        pattern = os.path.join(self.file_path, self.file_pattern or '*')
        return glob.glob(pattern)
    
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
    plu_primary_code = models.CharField(max_length=100, blank=True)          # E, M, D, P, Q, I, C, R
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

    # Validation and quality tracking
    validation_status = models.CharField(
        max_length=20,
        choices=[
            ('valid', 'Valid'),
            ('warning', 'Has Warnings'),
            ('error', 'Has Errors'),
            ('missing_data', 'Missing Required Data'),
        ],
        default='valid'
    )
    validation_messages = models.JSONField(default=list, blank=True)
    quality_score = models.FloatField(null=True, blank=True, help_text='Data quality score 0-100')
    data_completeness = models.FloatField(default=100.0, help_text='Percentage of required fields present')
    geometry_quality = models.CharField(
        max_length=20,
        choices=[
            ('excellent', 'Excellent'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('poor', 'Poor'),
        ],
        default='good'
    )
    
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
            models.Index(fields=['validation_status']),
            models.Index(fields=['layer', 'validation_status']),
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

    def validate_feature_data(self):
        """Validate feature data completeness and quality"""
        issues = []
        completeness_score = 0
        total_fields = 0

        # Basic required fields
        required_fields = ['geometry', 'layer']
        for field in required_fields:
            total_fields += 1
            if getattr(self, field, None):
                completeness_score += 1
            else:
                issues.append(f"Missing required field: {field}")

        # City-specific required attributes
        city_slug = self.layer.city.slug if self.layer and self.layer.city else ''
        if city_slug == 'warangal':
            required_attrs = ['PLU', 'PLU_NAME', 'Area']
        elif city_slug == 'visakhapatnam':
            required_attrs = ['Category', 'Shape_Area']
        elif city_slug == 'amaravati':
            required_attrs = ['symbology', 'plot_categ']
        else:
            required_attrs = []

        source_attrs = self.source_attributes or {}
        for attr in required_attrs:
            total_fields += 1
            if attr in source_attrs and source_attrs[attr]:
                completeness_score += 1
            else:
                issues.append(f"Missing {city_slug} required attribute: {attr}")

        completeness = (completeness_score / total_fields * 100) if total_fields > 0 else 100

        if not issues:
            status = 'valid'
        elif completeness >= 80:
            status = 'warning'
        else:
            status = 'missing_data'

        self.validation_status = status
        self.validation_messages = issues
        self.data_completeness = completeness

        return {
            'status': status,
            'issues': issues,
            'completeness': completeness
        }

class ValidationReport(models.Model):
    """Track validation reports for cities and layers"""
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='validation_reports')
    layer = models.ForeignKey(DataLayer, on_delete=models.CASCADE, null=True, blank=True, related_name='validation_reports')

    report_type = models.CharField(
        max_length=30,
        choices=[
            ('city_overview', 'City Overview'),
            ('layer_specific', 'Layer Specific'),
            ('missing_features', 'Missing Features'),
            ('style_coverage', 'Style Coverage'),
        ]
    )

    total_features = models.IntegerField(default=0)
    valid_features = models.IntegerField(default=0)
    features_with_warnings = models.IntegerField(default=0)
    features_with_errors = models.IntegerField(default=0)
    missing_data_features = models.IntegerField(default=0)

    issues_summary = models.JSONField(default=list)
    detailed_issues = models.JSONField(default=dict)

    styled_categories = models.IntegerField(default=0)
    unstyled_categories = models.IntegerField(default=0)
    missing_patterns = models.JSONField(default=list)

    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'validation_reports'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['city', 'report_type']),
            models.Index(fields=['generated_at']),
        ]

    def __str__(self):
        layer_info = f" - {self.layer.name}" if self.layer else ""
        return f"{self.city.name} {self.report_type}{layer_info} ({self.generated_at.date()})"

    @property
    def overall_score(self):
        if self.total_features == 0:
            return 100.0
        score = (self.valid_features / self.total_features) * 100
        return round(score, 1)

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
    
class LayerConfig(models.Model):
    """
    Frontend layer configuration - matches your API structure exactly
    """
    
    STATUS_CHOICES = [
        ('live', 'Live'),
        ('upcoming', 'Upcoming'),
        ('maintenance', 'Under Maintenance'),
    ]
    
    ACCESS_CHOICES = [
        ('free', 'Free'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise'),
    ]
    
    SCOPE_CHOICES = [
        ('state', 'State Level'),
        ('urban_area', 'Urban Area Level'),
    ]
    
    # Basic Info
    title = models.CharField(max_length=200, help_text="Layer title shown in frontend")
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(help_text="Layer description")
    
    # Classification
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='live')
    access = models.CharField(max_length=20, choices=ACCESS_CHOICES, default='free')
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='urban_area')
    
    # Relationships
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='layer_configs')
    city = models.ForeignKey(City, on_delete=models.CASCADE, null=True, blank=True, 
                           related_name='layer_configs',
                           help_text="Required if scope is 'urban_area'")
    
    # Optional: Link to actual data layer
    data_layer = models.OneToOneField(DataLayer, on_delete=models.SET_NULL, 
                                    null=True, blank=True,
                                    related_name='frontend_config')
    
    # Display Settings
    sort_order = models.IntegerField(default=1, help_text="Display order in frontend")
    is_active = models.BooleanField(default=True)
    
    # Info Popup Data
    data_accuracy = models.TextField(blank=True, help_text="Data accuracy information")
    information_use = models.TextField(blank=True, help_text="Usage guidelines")
    source_name = models.CharField(max_length=200, blank=True, help_text="Source name (e.g., 'hmda.gov')")
    source_url = models.URLField(blank=True, help_text="Source URL (optional)")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'layer_configs'
        ordering = ['state__name', 'scope', 'sort_order', 'title']
        indexes = [
            models.Index(fields=['state', 'scope', 'is_active']),
            models.Index(fields=['city', 'is_active']),
            models.Index(fields=['status', 'access']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(scope='state') | models.Q(city__isnull=False),
                name='city_required_for_urban_area'
            )
        ]
    
    def __str__(self):
        if self.scope == 'state':
            return f"{self.state.name} (State) - {self.title}"
        else:
            city_name = self.city.name if self.city else "No City"
            return f"{self.state.name} > {city_name} - {self.title}"
    
    def clean(self):
        """Validate that city is provided for urban_area scope"""
        from django.core.exceptions import ValidationError
        if self.scope == 'urban_area' and not self.city:
            raise ValidationError("City is required when scope is 'urban_area'")
        if self.scope == 'state' and self.city:
            raise ValidationError("City should not be set when scope is 'state'")
    
    def get_info_popup(self):
        """Generate info_popup structure for API"""
        popup = {}
        
        if self.data_accuracy:
            popup['data_accuracy'] = self.data_accuracy
        
        if self.information_use:
            popup['information_use'] = self.information_use
        
        if self.source_name and self.source_url:
            popup['source'] = {
                'title': self.source_name,
                'url': self.source_url
            }
        elif self.source_name:
            popup['source'] = self.source_name
        
        return popup
    
    def to_api_format(self):
        """Convert to API format"""
        return {
            'id': self.id,
            'title': self.title,
            'slug': self.slug,
            'description': self.description,
            'status': self.status,
            'access': self.access,
            'scope': self.scope,
            'sort_order': self.sort_order,
            'info_popup': self.get_info_popup(),
        }

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