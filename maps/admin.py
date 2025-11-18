from django.contrib import admin
from django.contrib.gis import admin as gis_admin
from django.db.models import Count, Q
from django.utils.html import format_html
from django.urls import reverse
import json

from .models import (
    City,
    CityLayerStyle,
    CityZoneMapping,
    DataLayer,
    GeoFeature,
    LayerCategory,
    LayerGroup,
    PLUCodeMapping,
    State,
    ValidationLog,
    VectorTileLayer,
)


class AuditFieldsMixin:
    """Make created/updated fields read-only whenever they exist on the model."""

    readonly_fields = ()

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        model_field_names = {field.name for field in self.model._meta.get_fields()}
        for audit_field in ("created_at", "updated_at"):
            if audit_field in model_field_names and audit_field not in fields:
                fields.append(audit_field)
        return tuple(fields)


@admin.register(State)
class StateAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "code",
        "slug",
        "is_active",
        "cities_link",
        "layers_count",
        "created_at",
    )
    search_fields = ("name", "code", "slug")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            cities_count=Count("cities", distinct=True),
            layers_count=Count("cities__layers", distinct=True),
        )

    @admin.display(ordering="cities_count", description="Cities")
    def cities_link(self, obj):
        count = obj.cities_count
        url = reverse("admin:maps_city_changelist") + f"?state_ref__id__exact={obj.id}"
        return format_html('<a href="{}">{} Cities</a>', url, count)
    cities_link.short_description = "Cities"

    @admin.display(ordering="layers_count", description="Layers")
    def layers_count(self, obj):
        return obj.layers_count


@admin.register(City)
class CityAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "slug",
        "state_name",
        "is_active",
        "layers_link",
        "processed_layers",
        "features_count",
        "created_at",
    )
    search_fields = ("name", "slug", "state", "state_ref__name")
    list_filter = ("state_ref", "is_active")
    autocomplete_fields = ("state_ref",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("state_ref").annotate(
            layers_count=Count("layers", distinct=True),
            processed_layers=Count(
                "layers", filter=Q(layers__is_processed=True), distinct=True
            ),
            features_count=Count("layers__geofeature_set", distinct=True),
        )

    @admin.display(description="State", ordering="state_ref__name")
    def state_name(self, obj):
        if obj.state_ref:
            return obj.state_ref.name
        return obj.state

    @admin.display(ordering="layers_count", description="Layers")
    def layers_link(self, obj):
        count = obj.layers_count
        url = reverse("admin:maps_datalayer_changelist") + f"?city__id__exact={obj.id}"
        return format_html('<a href="{}">{} Layers</a>', url, count)
    layers_link.short_description = "Layers"

    @admin.display(ordering="processed_layers", description="Processed")
    def processed_layers(self, obj):
        return obj.processed_layers

    @admin.display(ordering="features_count", description="Features")
    def features_count(self, obj):
        return obj.features_count


@admin.register(LayerCategory)
class LayerCategoryAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "code",
        "display_order",
        "is_active",
    )
    search_fields = ("name", "code")
    list_filter = ("is_active",)
    ordering = ("display_order", "name")

@admin.register(CityLayerStyle)
class CityLayerStyleAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "city",
        "category",
        "fill_pattern",
        "is_visible",
        "min_zoom",
        "max_zoom",
    )
    list_filter = ("city", "category", "fill_pattern", "is_visible")
    search_fields = ("city__name", "category__name")
    autocomplete_fields = ("city", "category")
    fieldsets = (
        (
            "Relationships",
            {"fields": ("city", "category")},
        ),
        (
            "Fill",
            {"fields": ("fill_color", "secondary_fill_color", "fill_pattern")},
        ),
        (
            "Stroke & Pattern",
            {
                "fields": (
                    "stroke_color",
                    "opacity",
                    "stroke_width",
                    "pattern_color",
                    "pattern_spacing",
                    "pattern_angle",
                    "pattern_size",
                )
            },
        ),
        (
            "Visibility",
            {"fields": ("is_visible", "min_zoom", "max_zoom")},
        ),
    )

@admin.register(DataLayer)
class DataLayerAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "city",
        "category",
        "is_true",
        "is_processed",
        "tiles_generated",
        "actual_feature_count",
        "files_info",
        "geometry_type",
        "created_at",
    )
    search_fields = (
        "name",
        "slug",
        "description",
        "city__name",
        "category__name",
        "data_source",
        "file_path",
    )
    list_filter = (
        "city",
        "category",
        "is_true",
        "is_processed",
        "tiles_generated",
        "geometry_type",
        "file_format",
        "is_directory",
    )
    autocomplete_fields = ("city", "category", "layer_group")
    list_select_related = ("city", "category", "layer_group")
    prepopulated_fields = {"slug": ("name",)}
    actions = ("mark_as_visible", "mark_as_hidden", "mark_as_processed")
    readonly_fields = ("actual_feature_count_display", "files_list_display", "file_breakdown_display")
    fieldsets = (
        ("Basic information", {"fields": ("city", "category", "layer_group", "name", "slug", "description")}),
        ("Files", {"fields": ("is_directory", "file_format", "file_path", "file_pattern", "original_filename", "files_list_display", "file_breakdown_display")}),
        ("Processing", {"fields": ("is_true", "is_processed", "tiles_generated", "feature_count", "actual_feature_count_display", "categorization_method", "processing_errors")}),
        ("Geometry", {"fields": ("geometry_type", "bbox_xmin", "bbox_ymin", "bbox_xmax", "bbox_ymax")}),
        ("Metadata", {"fields": ("data_source", "last_updated")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            actual_features=Count("geofeature_set", distinct=True)
        )

    @admin.display(ordering="actual_features", description="Features")
    def actual_feature_count(self, obj):
        """Display actual feature count from database with color coding"""
        count = getattr(obj, 'actual_features', None)
        if count is None:
            count = obj.geofeature_set.count()
        
        stored_count = obj.feature_count or 0
        
        # Color code based on match
        if count == stored_count:
            color = "green"
        elif stored_count == 0:
            color = "orange"
        else:
            color = "red"
        
        # Format numbers with commas
        count_str = f"{count:,}"
        stored_str = f"{stored_count:,}"
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span> '
            '<span style="color: #666; font-size: 0.9em;">(stored: {})</span>',
            color, count_str, stored_str
        )

    @admin.display(description="Files")
    def files_info(self, obj):
        """Display file information clearly in list view"""
        if obj.is_directory:
            # Directory-based layer
            try:
                files = obj.get_files()
                file_count = len(files)
                
                if obj.source_files:
                    source_count = len(obj.source_files)
                    return format_html(
                        '<span style="color: #0066cc; font-weight: bold;">📁 Directory</span><br/>'
                        '<span style="color: #666;">{} files</span> '
                        '<span style="color: #999;">({} in DB)</span>',
                        file_count, source_count
                    )
                else:
                    return format_html(
                        '<span style="color: #0066cc; font-weight: bold;">📁 Directory</span><br/>'
                        '<span style="color: #666;">{} files</span>',
                        file_count
                    )
            except Exception as e:
                return format_html(
                    '<span style="color: red;">Error: {}</span>',
                    str(e)[:50]
                )
        else:
            # Single file layer
            if obj.file_path:
                filename = obj.file_path.split('/')[-1] if '/' in obj.file_path else obj.file_path
                return format_html(
                    '<span style="color: #0066cc;">📄 {}</span>',
                    filename[:50] + ('...' if len(filename) > 50 else '')
                )
            elif obj.original_filename:
                return format_html(
                    '<span style="color: #0066cc;">📄 {}</span>',
                    obj.original_filename[:50] + ('...' if len(obj.original_filename) > 50 else '')
                )
            else:
                return format_html('<span style="color: #999;">No file</span>')

    @admin.display(description="Actual Feature Count")
    def actual_feature_count_display(self, obj):
        """Display actual feature count in detail view"""
        if obj.pk:
            count = obj.geofeature_set.count()
            stored_count = obj.feature_count or 0
            
            if count == stored_count:
                status = format_html('<span style="color: green;">✓ Match</span>')
            elif stored_count == 0:
                status = format_html('<span style="color: orange;">⚠ Not stored</span>')
            else:
                status = format_html('<span style="color: red;">✗ Mismatch</span>')
            
            # Format numbers with commas
            count_str = f"{count:,}"
            stored_str = f"{stored_count:,}"
            
            return format_html(
                '<div style="font-size: 1.1em; margin: 10px 0;">'
                '<strong>Actual Count:</strong> <span style="color: #0066cc; font-size: 1.2em;">{}</span><br/>'
                '<strong>Stored Count:</strong> <span style="color: #666;">{}</span><br/>'
                '<strong>Status:</strong> {}'
                '</div>',
                count_str, stored_str, status
            )
        return "Save the layer first to see feature count"

    @admin.display(description="Files List")
    def files_list_display(self, obj):
        """Display all files for this layer in detail view"""
        if not obj.pk:
            return "Save the layer first to see files"
        
        try:
            files = obj.get_files()
            
            if obj.is_directory:
                if not files:
                    return format_html('<span style="color: #999;">No files found in directory</span>')
                
                file_list_html = '<div style="max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; background: #f9f9f9;">'
                file_list_html += f'<strong style="color: #0066cc;">Directory: {obj.file_path or "N/A"}</strong><br/>'
                file_list_html += f'<strong>Pattern: {obj.file_pattern or "*.*"}</strong><br/>'
                file_list_html += f'<strong>Total Files: {len(files)}</strong><hr/>'
                
                for i, file_path in enumerate(files[:50], 1):  # Show first 50 files
                    filename = file_path.split('/')[-1] if '/' in file_path else file_path
                    file_list_html += f'<div style="padding: 2px 0; font-family: monospace; font-size: 0.9em;">{i}. {filename}</div>'
                
                if len(files) > 50:
                    file_list_html += f'<div style="color: #999; margin-top: 10px;">... and {len(files) - 50} more files</div>'
                
                file_list_html += '</div>'
                return format_html(file_list_html)
            else:
                # Single file
                if obj.file_path:
                    return format_html(
                        '<div style="padding: 10px; background: #f9f9f9; border: 1px solid #ddd;">'
                        '<strong style="color: #0066cc;">File Path:</strong><br/>'
                        '<code style="word-break: break-all;">{}</code>'
                        '</div>',
                        obj.file_path
                    )
                elif obj.original_filename:
                    return format_html(
                        '<div style="padding: 10px; background: #f9f9f9; border: 1px solid #ddd;">'
                        '<strong style="color: #0066cc;">Original Filename:</strong><br/>'
                        '<code>{}</code>'
                        '</div>',
                        obj.original_filename
                    )
                else:
                    return format_html('<span style="color: #999;">No file path specified</span>')
        except Exception as e:
            return format_html(
                '<div style="color: red; padding: 10px; background: #ffe6e6; border: 1px solid #ff9999;">'
                '<strong>Error loading files:</strong><br/>{}'
                '</div>',
                str(e)
            )

    @admin.display(description="File Breakdown")
    def file_breakdown_display(self, obj):
        """Display feature count breakdown by source file"""
        if not obj.pk:
            return "Save the layer first to see file breakdown"
        
        if not obj.is_directory:
            return format_html('<span style="color: #999;">Single file layer - no breakdown available</span>')
        
        try:
            breakdown = obj.get_file_features_breakdown()
            
            if not breakdown:
                return format_html('<span style="color: #999;">No features found</span>')
            
            total_features = sum(breakdown.values())
            total_features_str = f"{total_features:,}"
            breakdown_html = '<div style="max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; background: #f9f9f9;">'
            breakdown_html += f'<strong style="color: #0066cc;">Total Features: {total_features_str}</strong><hr/>'
            
            # Sort by count descending
            sorted_breakdown = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)
            
            for filename, count in sorted_breakdown[:30]:  # Show top 30
                percentage = (count / total_features * 100) if total_features > 0 else 0
                count_str = f"{count:,}"
                percentage_str = f"{percentage:.1f}"
                filename_display = filename[:80] + ('...' if len(filename) > 80 else '')
                
                breakdown_html += format_html(
                    '<div style="padding: 5px 0; border-bottom: 1px solid #eee;">'
                    '<span style="font-weight: bold;">{}</span><br/>'
                    '<span style="color: #0066cc; font-size: 1.1em;">{} features</span> '
                    '<span style="color: #999;">({}%)</span>'
                    '</div>',
                    filename_display,
                    count_str,
                    percentage_str
                )
            
            if len(sorted_breakdown) > 30:
                breakdown_html += f'<div style="color: #999; margin-top: 10px;">... and {len(sorted_breakdown) - 30} more files</div>'
            
            breakdown_html += '</div>'
            return format_html(breakdown_html)
        except Exception as e:
            return format_html(
                '<div style="color: red; padding: 10px; background: #ffe6e6; border: 1px solid #ff9999;">'
                '<strong>Error loading breakdown:</strong><br/>{}'
                '</div>',
                str(e)
            )

    @admin.action(description="Mark selected layers as visible")
    def mark_as_visible(self, request, queryset):
        queryset.update(is_true=True)

    @admin.action(description="Mark selected layers as hidden")
    def mark_as_hidden(self, request, queryset):
        queryset.update(is_true=False)

    @admin.action(description="Mark selected layers as processed")
    def mark_as_processed(self, request, queryset):
        queryset.update(is_processed=True)

@admin.register(GeoFeature)
class GeoFeatureAdmin(AuditFieldsMixin, gis_admin.GISModelAdmin):
    gis_widget_kwargs = {
        "attrs": {
            "default_zoom": 12,
        }
    }

    list_display = (
        "id",
        "layer",
        "city_name",
        "source_layer_name",
        "zone_category",
        "is_valid",
        "created_at",
    )
    search_fields = (
        "id",
        "layer__name",
        "layer__slug",
        "source_layer_name",
        "zone_category",
        "plu_primary_code",
        "plu_secondary_1",
        "symbology",
    )
    list_filter = (
        "layer__city",
        "layer__category",
        "is_valid",
    )
    autocomplete_fields = ("layer",)
    readonly_fields = ("formatted_properties",)
    fieldsets = (
        ("Layer", {"fields": ("layer", "source_layer_name")}),
        ("Names", {"fields": ("name", "description")}),
        ("Zone information", {"fields": ("zone_category", "zone_subcategory")}),
        ("City specific", {"fields": ("plu_primary_code", "plu_secondary_1", "plu_secondary_2", "plu_proposed_use", "plu_development_code", "plu_authority", "kuda", "ex_pr", "plot_category", "symbology", "township", "sector", "colony", "block", "mandal", "district", "village", "rule_id")}),
        ("Geometry", {"fields": ("geometry", "area", "shape_length", "shape_area", "objectid", "fid")}),
        ("Validation", {"fields": ("is_valid", "validation_errors")}),
        ("Properties", {"fields": ("formatted_properties",)}),
    )

    @admin.display(description="City", ordering="layer__city__name")
    def city_name(self, obj):
        return obj.layer.city.name

    @admin.display(description="Properties")
    def formatted_properties(self, obj):
        if not obj.properties:
            return "—"
        return json.dumps(obj.properties, indent=2)


@admin.register(CityZoneMapping)
class CityZoneMappingAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "zone_name",
        "city",
        "category",
        "style",
        "feature_count",
        "is_active",
        "created_at",
    )
    search_fields = ("zone_name", "zone_code", "city__name")
    list_filter = ("city", "category", "is_active")
    autocomplete_fields = ("city", "category", "style")


@admin.register(PLUCodeMapping)
class PLUCodeMappingAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "plu_code",
        "city",
        "mapped_category",
        "feature_count",
        "is_active",
        "created_at",
    )
    search_fields = ("plu_code", "plu_description", "city__name")
    list_filter = ("city", "mapped_category", "is_active")
    autocomplete_fields = ("city", "mapped_category")


@admin.register(VectorTileLayer)
class VectorTileLayerAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "layer",
        "is_generated",
        "total_tiles",
        "cache_size_mb",
        "generated_at",
    )
    list_filter = ("is_generated", "generated_at")
    autocomplete_fields = ("layer",)


@admin.register(ValidationLog)
class ValidationLogAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "city",
        "layer",
        "validation_type",
        "is_valid",
        "error_count",
        "warning_count",
        "created_at",
    )
    search_fields = ("validation_type", "city__name", "layer__name")
    list_filter = ("city", "validation_type", "is_valid")
    autocomplete_fields = ("city", "layer")
    readonly_fields = ("formatted_report",)
    fieldsets = (
        ("Scope", {"fields": ("city", "layer", "validation_type", "is_valid")}),
        ("Counts", {"fields": ("total_features", "valid_features", "error_count", "warning_count")}),
        ("Report", {"fields": ("formatted_report",)}),
    )

    @admin.display(description="Validation report")
    def formatted_report(self, obj):
        if not obj.validation_report:
            return "—"
        return json.dumps(obj.validation_report, indent=2)


@admin.register(LayerGroup)
class LayerGroupAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "city",
        "category",
        "display_order",
        "is_visible",
        "created_at",
    )
    search_fields = ("name", "slug", "city__name")
    list_filter = ("city", "category", "is_visible")
    autocomplete_fields = ("city", "category")
    prepopulated_fields = {"slug": ("name",)}


admin.site.site_header = "GIS Data Management"
admin.site.site_title = "GIS Admin"
admin.site.index_title = "GIS Data Administration"
