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
        "feature_count",
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
    fieldsets = (
        ("Basic information", {"fields": ("city", "category", "layer_group", "name", "slug", "description")}),
        ("Files", {"fields": ("is_directory", "file_format", "file_path", "file_pattern", "original_filename")}),
        ("Processing", {"fields": ("is_true", "is_processed", "tiles_generated", "feature_count", "categorization_method", "processing_errors")}),
        ("Geometry", {"fields": ("geometry_type", "bbox_xmin", "bbox_ymin", "bbox_xmax", "bbox_ymax")}),
        ("Metadata", {"fields": ("data_source", "last_updated")}),
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
