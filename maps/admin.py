import hashlib
import secrets
from django.contrib import admin
from django.contrib import messages
from django.contrib.gis import admin as gis_admin
from django.db.models import Count, Q
from django.utils.html import format_html
from django.urls import reverse
import json

from .models import (
    ApiKey,
    City,
    CityLayerStyle,
    CityZoneMapping,
    DataLayer,
    DeveloperListing,
    DeveloperListingMedia,
    GeoFeature,
    LandPlotWebhookEvent,
    LayerCategory,
    LayerGroup,
    LayerListingLink,
    LayerPointCountCache,
    LayerPointCountDetail,
    LgdDivision,
    RelevantLayer,
    State,
    SyncedLandPlot,
    SyncedLand,
    SyncedPlot,
    SyncedDeveloperLand,
    SyncedDeveloperPlot,
    TIFMetadata,
    WebhookEvent,
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


# Skip live GeoFeature aggregations in admin above this stored count (avoids 504 on large layers).
ADMIN_HEAVY_LAYER_FEATURE_THRESHOLD = 50_000


class FastAdminMixin:
    """Avoid expensive changelist COUNT(*) and keep pages responsive."""

    show_full_result_count = False
    list_per_page = 25
    list_max_show_all = 50


@admin.register(State)
class StateAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "code",
        "slug",
        "center_lat",
        "center_lng",
        "default_zoom",
        "is_active",
        "cities_link",
        "layers_count",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "code", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    fieldsets = (
        ("Identity", {"fields": ("name", "slug", "code")}),
        ("Map view", {"fields": ("center_lat", "center_lng", "default_zoom")}),
        ("Status", {"fields": ("is_active", "created_at")}),
    )

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
        "center_lat",
        "center_lng",
        "min_zoom",
        "max_zoom",
        "is_active",
        "layers_link",
        "processed_layers",
        "features_count",
        "created_at",
    )
    list_filter = ("state_ref", "is_active")
    search_fields = ("name", "slug", "state", "state_ref__name")
    autocomplete_fields = ("state_ref",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    fieldsets = (
        ("Identity", {"fields": ("name", "slug", "state", "state_ref")}),
        ("Map view", {"fields": ("center_lat", "center_lng", "min_zoom", "max_zoom")}),
        ("Status", {"fields": ("is_active", "created_at")}),
    )

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
        "default_color",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "code", "description")
    ordering = ("display_order", "name")
    fieldsets = (
        ("Identity", {"fields": ("code", "name", "description")}),
        ("Display", {"fields": ("display_order", "default_color", "default_stroke", "default_opacity", "is_active")}),
    )

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

@admin.register(LayerPointCountCache)
class LayerPointCountCacheAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "layer",
        "within_km",
        "overlapping_count",
        "nearby_count",
        "total_count",
        "updated_at",
    )
    list_filter = ("within_km",)
    search_fields = ("layer__name", "layer__slug", "layer__city__name")
    list_select_related = ("layer", "layer__city", "layer__category")
    autocomplete_fields = ("layer",)
    readonly_fields = ("overlapping_count", "nearby_count", "total_count", "by_source", "updated_at")
    fieldsets = (
        (None, {"fields": ("layer", "within_km")}),
        ("Counts", {"fields": ("overlapping_count", "nearby_count", "total_count", "by_source")}),
        ("Metadata", {"fields": ("updated_at",)}),
    )

    def has_add_permission(self, request):
        return False  # Cache is populated by refresh_layer_point_count_cache or management command


@admin.register(LayerPointCountDetail)
class LayerPointCountDetailAdmin(admin.ModelAdmin):
    list_display = ("id", "layer", "source", "point_id", "backend_id", "lat", "lng", "is_overlapping")
    list_filter = ("layer", "source", "is_overlapping")
    search_fields = ("layer__name", "layer__slug", "source")
    list_select_related = ("layer",)
    autocomplete_fields = ("layer",)
    readonly_fields = ("layer", "source", "point_id", "backend_id", "lat", "lng", "is_overlapping")

    def has_add_permission(self, request):
        return False  # Details are populated by refresh_layer_point_count_cache


@admin.register(LayerListingLink)
class LayerListingLinkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "layer",
        "layer_slug",
        "source",
        "listing_pk",
        "backend_id",
        "order_total_price_in_lakhs",
        "order_total_size_in_acres",
        "order_price_per_acre_in_lakhs",
        "listing_created_at",
        "listing_updated_at",
        "status",
        "exposure_type",
        "distance_km",
        "enriched_at",
    )
    list_filter = ("source", "status", "exposure_type")
    search_fields = ("layer__slug", "layer__name", "layer_slug")
    list_select_related = ("layer",)
    autocomplete_fields = ("layer",)
    readonly_fields = (
        "layer",
        "source",
        "listing_pk",
        "backend_id",
        "status",
        "exposure_type",
        "layer_slug",
        "distance_km",
        "nearest_point",
        "enriched_at",
        "order_total_price_in_lakhs",
        "order_total_size_in_acres",
        "order_price_per_acre_in_lakhs",
        "listing_created_at",
        "listing_updated_at",
    )
    ordering = ("-listing_updated_at", "-id")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "layer",
                    "source",
                    "listing_pk",
                    "backend_id",
                    "status",
                    "exposure_type",
                    "layer_slug",
                    "distance_km",
                    "nearest_point",
                    "enriched_at",
                )
            },
        ),
        (
            "API ordering (denormalized from listing)",
            {
                "fields": (
                    "order_total_price_in_lakhs",
                    "order_total_size_in_acres",
                    "order_price_per_acre_in_lakhs",
                    "listing_created_at",
                    "listing_updated_at",
                ),
                "description": "Used by listing-links ordering. Filled on sync / enrichment; backfill with backfill_listing_order_metrics.",
            },
        ),
    )

    def has_add_permission(self, request):
        return False  # Populated by enrichment / materialize_layer_listing_links


@admin.register(DataLayer)
class DataLayerAdmin(FastAdminMixin, AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "layer_id_display",
        "name",
        "city",
        "is_true",
        "is_processed",
        "tiles_generated",
        "stored_feature_count",
        "file_summary",
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
    readonly_fields = ("stored_feature_count_display", "files_list_display", "file_breakdown_display")
    fieldsets = (
        ("Basic information", {"fields": ("city", "category", "layer_group", "name", "slug", "description")}),
        ("Files", {"fields": ("is_directory", "file_format", "file_path", "file_pattern", "original_filename", "files_list_display", "file_breakdown_display"), "classes": ("collapse",)}),
        ("Processing", {"fields": ("is_true", "is_processed", "tiles_generated", "feature_count", "stored_feature_count_display", "categorization_method", "processing_errors")}),
        ("Geometry", {"fields": ("geometry_type", "bbox_xmin", "bbox_ymin", "bbox_xmax", "bbox_ymax")}),
        ("Metadata", {"fields": ("data_source", "last_updated")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("city", "category", "layer_group")

    @admin.display(description="Features (stored)", ordering="feature_count")
    def stored_feature_count(self, obj):
        count = obj.feature_count or 0
        return f"{count:,}"

    @admin.display(description="Files")
    def file_summary(self, obj):
        if obj.is_directory:
            file_count = len(obj.source_files or [])
            return format_html(
                '<span style="color: #0066cc;">📁 {} file(s)</span>',
                file_count,
            )
        if obj.file_path:
            filename = obj.file_path.rsplit("/", 1)[-1]
            return format_html('<span style="color: #0066cc;">📄 {}</span>', filename[:50])
        if obj.original_filename:
            return format_html('<span style="color: #0066cc;">📄 {}</span>', obj.original_filename[:50])
        return format_html('<span style="color: #999;">—</span>')

    @admin.display(description="Stored feature count")
    def stored_feature_count_display(self, obj):
        if not obj.pk:
            return "Save the layer first"
        count = obj.feature_count or 0
        return format_html(
            '<div style="font-size: 1.1em; margin: 10px 0;">'
            '<strong>Stored count:</strong> <span style="color: #0066cc;">{:,}</span><br/>'
            '<span style="color: #666;">Live DB counts are skipped in admin for large layers. '
            'Use management commands to refresh <code>feature_count</code>.</span>'
            '</div>',
            count,
        )

    def _layer_too_heavy_for_live_queries(self, obj):
        return (obj.feature_count or 0) >= ADMIN_HEAVY_LAYER_FEATURE_THRESHOLD

    @admin.display(description="Actual Feature Count")
    def actual_feature_count_display(self, obj):
        return self.stored_feature_count_display(obj)

    @admin.display(description="Files List")
    def files_list_display(self, obj):
        if not obj.pk:
            return "Save the layer first to see files"

        if obj.is_directory:
            files = obj.source_files or []
            if not files:
                return format_html('<span style="color: #999;">No files listed in source_files</span>')

            file_list_html = (
                '<div style="max-height: 300px; overflow-y: auto; border: 1px solid #ddd; '
                'padding: 10px; background: #f9f9f9;">'
                f'<strong>Directory:</strong> {obj.file_path or "N/A"}<br/>'
                f'<strong>Pattern:</strong> {obj.file_pattern or "*.*"}<br/>'
                f'<strong>Total files (DB):</strong> {len(files)}<hr/>'
            )
            for i, file_path in enumerate(files[:50], 1):
                filename = file_path.rsplit("/", 1)[-1]
                file_list_html += f'<div style="font-family: monospace; font-size: 0.9em;">{i}. {filename}</div>'
            if len(files) > 50:
                file_list_html += f'<div style="color: #999; margin-top: 10px;">... and {len(files) - 50} more</div>'
            file_list_html += "</div>"
            return format_html(file_list_html)

        if obj.file_path:
            return format_html(
                '<div style="padding: 10px; background: #f9f9f9; border: 1px solid #ddd;">'
                '<strong>File path:</strong><br/><code style="word-break: break-all;">{}</code></div>',
                obj.file_path,
            )
        if obj.original_filename:
            return format_html(
                '<div style="padding: 10px; background: #f9f9f9; border: 1px solid #ddd;">'
                '<strong>Original filename:</strong><br/><code>{}</code></div>',
                obj.original_filename,
            )
        return format_html('<span style="color: #999;">No file path specified</span>')

    @admin.display(description="File Breakdown")
    def file_breakdown_display(self, obj):
        if not obj.pk:
            return "Save the layer first to see file breakdown"
        if not obj.is_directory:
            return format_html('<span style="color: #999;">Single file layer — no breakdown</span>')
        if self._layer_too_heavy_for_live_queries(obj):
            return format_html(
                '<span style="color: #999;">Skipped (stored feature_count ≥ {:,}). '
                'Use a management command or SQL for breakdown.</span>',
                ADMIN_HEAVY_LAYER_FEATURE_THRESHOLD,
            )

        try:
            breakdown = obj.get_file_features_breakdown()
            if not breakdown:
                return format_html('<span style="color: #999;">No features found</span>')

            total_features = sum(breakdown.values())
            breakdown_html = (
                '<div style="max-height: 300px; overflow-y: auto; border: 1px solid #ddd; '
                'padding: 10px; background: #f9f9f9;">'
                f'<strong>Total features:</strong> {total_features:,}<hr/>'
            )
            sorted_breakdown = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)
            for filename, count in sorted_breakdown[:30]:
                percentage = (count / total_features * 100) if total_features > 0 else 0
                filename_display = filename[:80] + ("..." if len(filename) > 80 else "")
                breakdown_html += (
                    f'<div style="padding: 5px 0; border-bottom: 1px solid #eee;">'
                    f'<span style="font-weight: bold;">{filename_display}</span><br/>'
                    f'<span style="color: #0066cc;">{count:,} features</span> '
                    f'<span style="color: #999;">({percentage:.1f}%)</span></div>'
                )
            if len(sorted_breakdown) > 30:
                breakdown_html += f'<div style="color: #999; margin-top: 10px;">... and {len(sorted_breakdown) - 30} more files</div>'
            breakdown_html += "</div>"
            return format_html(breakdown_html)
        except Exception as e:
            return format_html(
                '<div style="color: red; padding: 10px; background: #ffe6e6; border: 1px solid #ff9999;">'
                '<strong>Error loading breakdown:</strong><br/>{}</div>',
                str(e),
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

    @admin.display(description="Layer ID", ordering="id")
    def layer_id_display(self, obj):
        return obj.id

@admin.register(GeoFeature)
class GeoFeatureAdmin(FastAdminMixin, AuditFieldsMixin, gis_admin.GISModelAdmin):
    gis_widget_kwargs = {
        "attrs": {
            "default_zoom": 12,
        }
    }

    list_display = (
        "id",
        "layer_id",
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
    list_select_related = ("layer", "layer__city")
    ordering = ("-id",)
    fieldsets = (
        ("Layer", {"fields": ("layer", "source_layer_name")}),
        ("Names", {"fields": ("name", "description")}),
        ("Zone information", {"fields": ("zone_category", "zone_subcategory")}),
        ("City specific", {"fields": ("plu_primary_code", "plu_secondary_1", "plu_secondary_2", "plu_proposed_use", "plu_development_code", "plu_authority", "kuda", "ex_pr", "plot_category", "symbology", "township", "sector", "colony", "block", "mandal", "district", "village", "rule_id")}),
        ("Geometry", {"fields": ("geometry", "area", "shape_length", "shape_area", "objectid", "fid")}),
        ("Validation", {"fields": ("is_valid", "validation_errors")}),
        ("Properties", {"fields": ("formatted_properties",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("layer", "layer__city")
        if request.resolver_match and request.resolver_match.url_name.endswith("_changelist"):
            return qs.defer("geometry", "properties")
        return qs

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        if not request.GET.get("layer__id__exact") and not request.GET.get("q"):
            extra_context["title"] = (
                "Geo features — filter by Layer (sidebar) or search to avoid loading huge tables"
            )
        return super().changelist_view(request, extra_context=extra_context)

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


# ================================
# DEVELOPER LISTING ADMIN
# ================================

class DeveloperListingMediaInline(admin.TabularInline):
    """Inline admin for media files"""
    model = DeveloperListingMedia
    extra = 0
    readonly_fields = ("backend_media_id", "media_type", "file_name", "file_url", "is_tif", "tiles_generated", "total_tiles_generated")
    fields = ("backend_media_id", "media_type", "category", "file_name", "is_tif", "tiles_generated", "total_tiles_generated")
    can_delete = False
    show_change_link = True


@admin.register(DeveloperListing)
class DeveloperListingAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "listing_type",
        "backend_listing_id",
        "name",
        "city",
        "state",
        "is_active",
        "media_count",
        "tif_count",
        "created_at",
    )
    search_fields = ("name", "description", "backend_listing_id", "city", "state", "location")
    list_filter = ("listing_type", "is_active", "city", "state", "created_at")
    readonly_fields = ("backend_listing_id", "listing_data_display", "media_count_display", "tif_count_display")
    inlines = [DeveloperListingMediaInline]
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("listing_type", "backend_listing_id", "name", "description")
        }),
        ("Location", {
            "fields": ("location", "city", "state")
        }),
        ("Status", {
            "fields": ("is_active", "last_webhook_event")
        }),
        ("Media Summary", {
            "fields": ("media_count_display", "tif_count_display")
        }),
        ("Timestamps", {
            "fields": ("backend_created_at", "backend_updated_at", "created_at", "updated_at")
        }),
        ("Raw Data", {
            "fields": ("listing_data_display",),
            "classes": ("collapse",)
        }),
    )
    
    @admin.display(description="Media Files")
    def media_count(self, obj):
        count = obj.get_media_count()
        return format_html(
            '<span style="color: #0066cc; font-weight: bold;">{}</span>',
            count
        )
    
    @admin.display(description="TIF Files")
    def tif_count(self, obj):
        count = obj.get_tif_count()
        if count > 0:
            return format_html(
                '<span style="color: #009900; font-weight: bold;">{}</span>',
                count
            )
        return count
    
    @admin.display(description="Media Files")
    def media_count_display(self, obj):
        if obj.pk:
            total = obj.get_media_count()
            tif = obj.get_tif_count()
            return format_html(
                '<div style="font-size: 1.1em;">'
                '<strong>Total Media:</strong> <span style="color: #0066cc;">{}</span><br/>'
                '<strong>TIF Files:</strong> <span style="color: #009900;">{}</span>'
                '</div>',
                total, tif
            )
        return "Save to see media count"
    
    @admin.display(description="TIF Files")
    def tif_count_display(self, obj):
        if obj.pk:
            tif_media = obj.media_files.filter(is_tif=True)
            generated = tif_media.filter(tiles_generated=True).count()
            pending = tif_media.filter(tiles_generated=False).count()
            
            return format_html(
                '<div style="font-size: 1.1em;">'
                '<strong>Generated:</strong> <span style="color: #009900;">{}</span><br/>'
                '<strong>Pending:</strong> <span style="color: #ff9900;">{}</span>'
                '</div>',
                generated, pending
            )
        return "Save to see TIF status"
    
    @admin.display(description="Listing Data (JSON)")
    def listing_data_display(self, obj):
        if not obj.listing_data:
            return "—"
        return format_html(
            '<pre style="max-height: 400px; overflow-y: auto; background: #f5f5f5; padding: 10px; border: 1px solid #ddd;">{}</pre>',
            json.dumps(obj.listing_data, indent=2)
        )


@admin.register(DeveloperListingMedia)
class DeveloperListingMediaAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "listing_info",
        "media_type",
        "category",
        "file_name_short",
        "is_tif",
        "tiles_status",
        "total_tiles_generated",
        "created_at",
    )
    search_fields = ("file_name", "listing__name", "listing__backend_listing_id", "category")
    list_filter = ("media_type", "is_tif", "tiles_generated", "category", "created_at")
    readonly_fields = (
        "backend_media_id",
        "file_url_link",
        "s3_path",
        "tiles_generated",
        "total_tiles_generated",
        "tiles_generation_started_at",
        "tiles_generation_completed_at",
        "media_data_display",
    )
    autocomplete_fields = ("listing",)
    
    fieldsets = (
        ("Listing", {
            "fields": ("listing", "backend_media_id")
        }),
        ("Media Information", {
            "fields": ("media_type", "category", "file_name", "file_url_link", "s3_path")
        }),
        ("TIF & Tiles", {
            "fields": (
                "is_tif",
                "s3_tile_path",
                "tiles_generated",
                "total_tiles_generated",
                "tiles_generation_started_at",
                "tiles_generation_completed_at",
                "tiles_generation_error",
            )
        }),
        ("Raw Data", {
            "fields": ("media_data_display",),
            "classes": ("collapse",)
        }),
    )
    
    @admin.display(description="Listing")
    def listing_info(self, obj):
        return format_html(
            '<a href="{}">{} - {}</a>',
            reverse("admin:maps_developerlisting_change", args=[obj.listing.pk]),
            obj.listing.get_listing_type_display(),
            obj.listing.backend_listing_id
        )
    
    @admin.display(description="File Name")
    def file_name_short(self, obj):
        if obj.file_name:
            name = obj.file_name[:50] + ('...' if len(obj.file_name) > 50 else '')
            if obj.is_tif:
                return format_html('<span style="color: #009900; font-weight: bold;">🗺️ {}</span>', name)
            return name
        return "—"
    
    @admin.display(description="Tiles Status")
    def tiles_status(self, obj):
        if not obj.is_tif:
            return format_html('<span style="color: #999;">N/A</span>')
        
        if obj.tiles_generated:
            return format_html('<span style="color: #009900; font-weight: bold;">✓ Generated</span>')
        elif obj.tiles_generation_started_at:
            return format_html('<span style="color: #ff9900;">⏳ In Progress</span>')
        elif obj.tiles_generation_error:
            return format_html('<span style="color: #cc0000;">✗ Error</span>')
        else:
            return format_html('<span style="color: #666;">⏸ Pending</span>')
    
    @admin.display(description="File URL")
    def file_url_link(self, obj):
        if obj.file_url:
            return format_html(
                '<a href="{}" target="_blank" style="color: #0066cc;">{}</a>',
                obj.file_url,
                obj.file_url[:80] + ('...' if len(obj.file_url) > 80 else '')
            )
        return "—"
    
    @admin.display(description="Media Data (JSON)")
    def media_data_display(self, obj):
        if not obj.media_data:
            return "—"
        return format_html(
            '<pre style="max-height: 400px; overflow-y: auto; background: #f5f5f5; padding: 10px; border: 1px solid #ddd;">{}</pre>',
            json.dumps(obj.media_data, indent=2)
        )


@admin.register(TIFMetadata)
class TIFMetadataAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "media_file",
        "source_crs",
        "source_dimensions",
        "bounds_display",
        "zoom_range",
        "total_tiles_generated",
        "created_at",
    )
    search_fields = ("media__file_name", "source_crs")
    list_filter = ("source_crs", "min_zoom", "max_zoom", "created_at")
    readonly_fields = (
        "source_info_display",
        "reprojected_info_display",
        "bounds_map_display",
        "tiles_breakdown_display",
        "transform_matrix_display",
        "tif_data_display",
    )
    autocomplete_fields = ("media",)
    
    fieldsets = (
        ("Media File", {
            "fields": ("media",)
        }),
        ("Source TIF Information", {
            "fields": ("source_info_display", "source_crs", "source_width", "source_height", "source_bands")
        }),
        ("Source Bounds", {
            "fields": (
                "source_bounds_west",
                "source_bounds_south",
                "source_bounds_east",
                "source_bounds_north",
            )
        }),
        ("Reprojected Information (WGS84)", {
            "fields": ("reprojected_info_display", "reprojected_width", "reprojected_height")
        }),
        ("Reprojected Bounds (WGS84)", {
            "fields": (
                "bounds_west",
                "bounds_south",
                "bounds_east",
                "bounds_north",
                "bounds_map_display",
            )
        }),
        ("Tile Configuration", {
            "fields": ("min_zoom", "max_zoom", "tile_size")
        }),
        ("Tile Statistics", {
            "fields": ("total_tiles_generated", "tiles_breakdown_display", "processing_time_seconds", "file_size_bytes")
        }),
        ("Transform Matrix", {
            "fields": ("transform_matrix_display",),
            "classes": ("collapse",)
        }),
        ("Raw TIF Data", {
            "fields": ("tif_data_display",),
            "classes": ("collapse",)
        }),
    )
    
    @admin.display(description="Media File")
    def media_file(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse("admin:maps_developerlistingmedia_change", args=[obj.media.pk]),
            obj.media.file_name or f"Media #{obj.media.backend_media_id}"
        )
    
    @admin.display(description="Dimensions")
    def source_dimensions(self, obj):
        if obj.source_width and obj.source_height:
            return f"{obj.source_width} × {obj.source_height}"
        return "—"
    
    @admin.display(description="Bounds")
    def bounds_display(self, obj):
        if all([obj.bounds_west, obj.bounds_south, obj.bounds_east, obj.bounds_north]):
            return format_html(
                '<span style="font-family: monospace; font-size: 0.9em;">'
                '{}, {}<br/>{}, {}'
                '</span>',
                f"{obj.bounds_west:.4f}", f"{obj.bounds_north:.4f}",
                f"{obj.bounds_east:.4f}", f"{obj.bounds_south:.4f}"
            )
        return "—"
    
    @admin.display(description="Zoom Range")
    def zoom_range(self, obj):
        return f"{obj.min_zoom} - {obj.max_zoom}"
    
    @admin.display(description="Source Information")
    def source_info_display(self, obj):
        return format_html(
            '<div style="font-size: 1.1em; padding: 10px; background: #f5f5f5; border: 1px solid #ddd;">'
            '<strong>CRS:</strong> <span style="color: #0066cc;">{}</span><br/>'
            '<strong>Dimensions:</strong> {} × {} pixels<br/>'
            '<strong>Bands:</strong> {}'
            '</div>',
            obj.source_crs or "Unknown",
            obj.source_width or "?",
            obj.source_height or "?",
            obj.source_bands or "?"
        )
    
    @admin.display(description="Reprojected Information")
    def reprojected_info_display(self, obj):
        return format_html(
            '<div style="font-size: 1.1em; padding: 10px; background: #f5f5f5; border: 1px solid #ddd;">'
            '<strong>CRS:</strong> <span style="color: #009900;">WGS84 (EPSG:4326)</span><br/>'
            '<strong>Dimensions:</strong> {} × {} pixels'
            '</div>',
            obj.reprojected_width or "?",
            obj.reprojected_height or "?"
        )
    
    @admin.display(description="Bounds Map")
    def bounds_map_display(self, obj):
        if all([obj.bounds_west, obj.bounds_south, obj.bounds_east, obj.bounds_north]):
            center_lat = (obj.bounds_south + obj.bounds_north) / 2
            center_lng = (obj.bounds_west + obj.bounds_east) / 2
            
            return format_html(
                '<div style="padding: 10px; background: #f5f5f5; border: 1px solid #ddd;">'
                '<strong>Center:</strong> {}, {}<br/>'
                '<strong>West:</strong> {}<br/>'
                '<strong>South:</strong> {}<br/>'
                '<strong>East:</strong> {}<br/>'
                '<strong>North:</strong> {}'
                '</div>',
                f"{center_lat:.6f}", f"{center_lng:.6f}",
                f"{obj.bounds_west:.6f}",
                f"{obj.bounds_south:.6f}",
                f"{obj.bounds_east:.6f}",
                f"{obj.bounds_north:.6f}"
            )
        return "—"
    
    @admin.display(description="Tiles by Zoom Level")
    def tiles_breakdown_display(self, obj):
        if not obj.tiles_by_zoom:
            return "—"
        
        breakdown_html = '<div style="padding: 10px; background: #f5f5f5; border: 1px solid #ddd;">'
        breakdown_html += f'<strong>Total: {obj.total_tiles_generated:,} tiles</strong><hr/>'
        
        for zoom, count in sorted(obj.tiles_by_zoom.items(), key=lambda x: int(x[0])):
            breakdown_html += f'<div>Zoom {zoom}: {count:,} tiles</div>'
        
        breakdown_html += '</div>'
        return format_html(breakdown_html)
    
    @admin.display(description="Transform Matrix")
    def transform_matrix_display(self, obj):
        if not obj.transform_matrix:
            return "—"
        return format_html(
            '<pre style="max-height: 300px; overflow-y: auto; background: #f5f5f5; padding: 10px; border: 1px solid #ddd;">{}</pre>',
            json.dumps(obj.transform_matrix, indent=2)
        )
    
    @admin.display(description="TIF Data (JSON)")
    def tif_data_display(self, obj):
        if not obj.tif_data:
            return "—"
        return format_html(
            '<pre style="max-height: 400px; overflow-y: auto; background: #f5f5f5; padding: 10px; border: 1px solid #ddd;">{}</pre>',
            json.dumps(obj.tif_data, indent=2)
        )


@admin.register(WebhookEvent)
class WebhookEventAdmin(AuditFieldsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "event_type_badge",
        "action_badge",
        "listing_type",
        "listing_id",
        "processed_status",
        "tiles_info",
        "received_at",
    )
    search_fields = ("event_type", "listing_type", "listing_id", "action", "processing_error")
    list_filter = (
        "event_type",
        "action",
        "listing_type",
        "processed",
        "received_at",
        "tiles_generated",
    )
    readonly_fields = (
        "event_type",
        "action",
        "listing_type",
        "listing_id",
        "payload_display",
        "raw_body",
        "processing_result_display",
        "tile_generation_logs_display",
        "request_headers_display",
        "deletion_summary",
        "received_at",
        "processed_at",
    )
    
    fieldsets = (
        ("Event Information", {
            "fields": ("event_type", "action", "listing_type", "listing_id", "received_at")
        }),
        ("Processing Status", {
            "fields": ("processed", "processed_at", "tiles_generated", "tif_files_processed", "processing_error")
        }),
        ("Deletion Summary", {
            "fields": ("deletion_summary",),
            "classes": ("collapse",),
            "description": "Summary of deletions (only shown for deletion events)"
        }),
        ("Request Metadata", {
            "fields": ("request_ip", "request_headers_display")
        }),
        ("Webhook Payload (full request body saved)", {
            "fields": ("payload_display", "raw_body"),
            "classes": ("collapse",)
        }),
        ("Processing Result", {
            "fields": ("processing_result_display",),
            "classes": ("collapse",)
        }),
        ("Tile generation logs (tile worker callback)", {
            "fields": ("tile_generation_logs_display",),
            "classes": ("collapse",),
            "description": "Log lines from tile worker when it POSTs to tile-generation-result"
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by("-received_at")
    
    @admin.display(description="Event Type", ordering="event_type")
    def event_type_badge(self, obj):
        """Display event type with color-coded badge"""
        colors = {
            "developer_listing_created": "#28a745",  # Green
            "developer_listing_updated": "#17a2b8",  # Blue
            "developer_listing_media_uploaded": "#007bff",  # Primary blue
            "developer_listing_media_updated": "#0056b3",  # Darker blue
            "developer_listing_media_deleted": "#dc3545",  # Red
            "developer_listing_listing_deleted": "#721c24",  # Dark red
        }
        color = colors.get(obj.event_type, "#6c757d")
        icon = "🗑️" if "deleted" in obj.event_type else "📥"
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em;">{} {}</span>',
            color,
            icon,
            obj.get_event_type_display()
        )
    
    @admin.display(description="Action", ordering="action")
    def action_badge(self, obj):
        """Display action with badge"""
        if not obj.action:
            return "—"
        colors = {
            "created": "#28a745",
            "updated": "#17a2b8",
            "media_uploaded": "#007bff",
            "media_updated": "#0056b3",
            "media_deleted": "#dc3545",
            "listing_deleted": "#721c24",
        }
        color = colors.get(obj.action, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>',
            color,
            obj.action.replace("_", " ").title()
        )
    
    @admin.display(description="Status", ordering="processed")
    def processed_status(self, obj):
        """Display processed status with icon (HTML; do not use boolean=True)."""
        if obj.processed:
            if obj.processing_error:
                return format_html(
                    '<span style="color: #dc3545;" title="{}">⚠️ Error</span>',
                    obj.processing_error[:100]
                )
            return format_html('<span style="color: #28a745;">✅ Processed</span>')
        return format_html('<span style="color: #ffc107;">⏳ Pending</span>')
    
    @admin.display(description="Tiles Info")
    def tiles_info(self, obj):
        """Display tiles information based on event type"""
        if obj.action in ["media_deleted", "listing_deleted"]:
            # For deletion events, show tiles deleted
            tiles_deleted = obj.processing_result.get("tiles_deleted", 0) if obj.processing_result else 0
            if tiles_deleted > 0:
                return format_html(
                    '<span style="color: #dc3545; font-weight: bold;">🗑️ {} tiles deleted</span>',
                    tiles_deleted
                )
            return format_html('<span style="color: #6c757d;">—</span>')
        else:
            # For creation/update events, show tiles generated
            if obj.tiles_generated > 0:
                return format_html(
                    '<span style="color: #28a745; font-weight: bold;">✅ {} tiles</span>',
                    obj.tiles_generated
                )
            return format_html('<span style="color: #6c757d;">—</span>')
    
    @admin.display(description="Deletion Summary")
    def deletion_summary(self, obj):
        """Show summary for deletion events"""
        if obj.action not in ["media_deleted", "listing_deleted"]:
            return format_html('<em>Not a deletion event</em>')
        
        if not obj.processing_result:
            return "—"
        
        result = obj.processing_result
        summary_parts = []
        
        if obj.action == "listing_deleted":
            summary_parts.append(f"<strong>Listing Deleted:</strong> {obj.listing_type} #{obj.listing_id}")
            tiles_deleted = result.get("tiles_deleted", 0)
            media_deleted = result.get("media_records_deleted", 0)
            summary_parts.append(f"<strong>Tiles Deleted:</strong> {tiles_deleted}")
            summary_parts.append(f"<strong>Media Records Deleted:</strong> {media_deleted}")
        
        elif obj.action == "media_deleted":
            tiles_deleted = result.get("tiles_deleted", 0)
            media_deleted = result.get("media_records_deleted", 0)
            remaining = result.get("remaining_media_count", 0)
            summary_parts.append(f"<strong>Tiles Deleted:</strong> {tiles_deleted}")
            summary_parts.append(f"<strong>Media Records Deleted:</strong> {media_deleted}")
            summary_parts.append(f"<strong>Remaining Media:</strong> {remaining}")
        
        if not summary_parts:
            return "—"
        
        return format_html(
            '<div style="background: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin: 10px 0;">{}</div>',
            "<br>".join(summary_parts)
        )
    
    @admin.display(description="Webhook Payload (JSON)")
    def payload_display(self, obj):
        if not obj.payload:
            return "—"
        
        # Highlight deletion-related fields
        payload_str = json.dumps(obj.payload, indent=2)
        if obj.action in ["media_deleted", "listing_deleted"]:
            # Add warning style for deletion events
            return format_html(
                '<div style="border: 2px solid #dc3545; padding: 5px; margin-bottom: 10px; background: #fff3cd;">'
                '<strong style="color: #dc3545;">⚠️ DELETION EVENT</strong></div>'
                '<pre style="max-height: 500px; overflow-y: auto; background: #f5f5f5; padding: 10px; border: 1px solid #ddd; font-size: 0.9em;">{}</pre>',
                payload_str
            )
        
        return format_html(
            '<pre style="max-height: 500px; overflow-y: auto; background: #f5f5f5; padding: 10px; border: 1px solid #ddd; font-size: 0.9em;">{}</pre>',
            payload_str
        )
    
    @admin.display(description="Processing Result (JSON)")
    def processing_result_display(self, obj):
        if not obj.processing_result:
            return "—"
        
        result_str = json.dumps(obj.processing_result, indent=2)
        
        # Highlight deletion results
        if obj.action in ["media_deleted", "listing_deleted"]:
            return format_html(
                '<div style="border: 2px solid #dc3545; padding: 5px; margin-bottom: 10px; background: #f8d7da;">'
                '<strong style="color: #721c24;">🗑️ DELETION RESULTS</strong></div>'
                '<pre style="max-height: 400px; overflow-y: auto; background: #f5f5f5; padding: 10px; border: 1px solid #ddd; font-size: 0.9em;">{}</pre>',
                result_str
            )
        
        return format_html(
            '<pre style="max-height: 400px; overflow-y: auto; background: #f5f5f5; padding: 10px; border: 1px solid #ddd; font-size: 0.9em;">{}</pre>',
            result_str
        )
    
    @admin.display(description="Tile generation logs")
    def tile_generation_logs_display(self, obj):
        if not obj.tile_generation_logs:
            return "—"
        lines = []
        for entry in obj.tile_generation_logs[:500]:
            ts = entry.get("ts", "")
            level = entry.get("level", "info")
            msg = entry.get("msg", "")
            lines.append(f"[{ts}] [{level}] {msg}")
        log_text = "\n".join(lines)
        if len(obj.tile_generation_logs) > 500:
            log_text += f"\n... and {len(obj.tile_generation_logs) - 500} more lines"
        return format_html(
            '<pre style="max-height: 400px; overflow-y: auto; background: #f0f8ff; padding: 10px; border: 1px solid #ddd; font-size: 0.85em;">{}</pre>',
            log_text
        )
    
    @admin.display(description="Request Headers (JSON)")
    def request_headers_display(self, obj):
        if not obj.request_headers:
            return "—"
        return format_html(
            '<pre style="max-height: 300px; overflow-y: auto; background: #f5f5f5; padding: 10px; border: 1px solid #ddd; font-size: 0.9em;">{}</pre>',
            json.dumps(obj.request_headers, indent=2)
        )
    
    actions = ["mark_as_processed", "retry_failed_webhooks"]
    
    @admin.action(description="Mark selected webhooks as processed")
    def mark_as_processed(self, request, queryset):
        """Manually mark webhooks as processed"""
        from django.utils import timezone
        updated = queryset.filter(processed=False).update(
            processed=True,
            processed_at=timezone.now()
        )
        self.message_user(
            request,
            f"Successfully marked {updated} webhook(s) as processed.",
            level="success"
        )
    
    @admin.action(description="Retry failed webhooks (for debugging)")
    def retry_failed_webhooks(self, request, queryset):
        """Mark failed webhooks for retry by clearing error"""
        updated = queryset.filter(
            processing_error__isnull=False,
            processing_error__gt=""
        ).update(
            processing_error="",
            processed=False,
            processed_at=None
        )
        self.message_user(
            request,
            f"Cleared errors for {updated} webhook(s). They will be retried on next processing.",
            level="info"
        )
    
    def changelist_view(self, request, extra_context=None):
        """Add custom context for changelist"""
        extra_context = extra_context or {}
        
        # Get statistics (alias names must not match model field names e.g. 'processed')
        from django.db.models import Count, Q, Sum
        stats = WebhookEvent.objects.aggregate(
            total=Count("id"),
            processed_count=Count("id", filter=Q(processed=True)),
            pending_count=Count("id", filter=Q(processed=False)),
            deletion_count=Count("id", filter=Q(action__in=["media_deleted", "listing_deleted"])),
            error_count=Count("id", filter=Q(processing_error__isnull=False, processing_error__gt="")),
            total_tiles_generated=Sum("tiles_generated", filter=Q(tiles_generated__gt=0)),
        )
        
        # Get deletion-specific stats
        deletion_events = WebhookEvent.objects.filter(
            action__in=["media_deleted", "listing_deleted"]
        )
        deletion_stats = {
            "media_deleted": deletion_events.filter(action="media_deleted").count(),
            "listing_deleted": deletion_events.filter(action="listing_deleted").count(),
            "total_tiles_deleted": sum(
                e.processing_result.get("tiles_deleted", 0) 
                for e in deletion_events 
                if e.processing_result
            ),
        }
        
        extra_context["stats"] = stats
        extra_context["deletion_stats"] = deletion_stats
        return super().changelist_view(request, extra_context)


@admin.register(LandPlotWebhookEvent)
class LandPlotWebhookEventAdmin(admin.ModelAdmin):
    """Land/Plot webhook events – full payload and raw body saved."""
    list_display = ("id", "event_type", "action", "listing_type", "listing_id", "received_at")
    list_filter = ("event_type", "action", "listing_type", "received_at")
    search_fields = ("listing_type", "listing_id", "action")
    readonly_fields = ("event_type", "action", "listing_type", "listing_id", "payload", "raw_body", "request_headers", "request_ip", "received_at")
    fieldsets = (
        ("Event", {"fields": ("event_type", "action", "listing_type", "listing_id", "received_at")}),
        ("Payload (full webhook body)", {"fields": ("payload", "raw_body")}),
        ("Request", {"fields": ("request_ip", "request_headers")}),
    )
    ordering = ("-received_at",)


@admin.register(SyncedLandPlot)
class SyncedLandPlotAdmin(admin.ModelAdmin):
    """Legacy: single table for all listing types. Prefer per-type tables below."""
    list_display = ("id", "listing_type", "backend_id", "synced_at")
    list_filter = ("listing_type", "synced_at")
    search_fields = ("listing_type", "backend_id")
    readonly_fields = ("listing_type", "backend_id", "payload", "synced_at")
    fieldsets = (
        ("Identity", {"fields": ("listing_type", "backend_id", "synced_at")}),
        ("API payload", {"fields": ("payload",)}),
    )
    ordering = ("-synced_at",)


@admin.register(SyncedLand)
class SyncedLandAdmin(admin.ModelAdmin):
    """Land data from GET /lands/. Columns + payload + enrichment."""
    list_display = (
        "id", "backend_id", "lat", "long", "status", "total_land_size", "total_price",
        "order_total_price_in_lakhs", "order_total_size_in_acres", "order_price_per_acre_in_lakhs",
        "updated_at", "enriched_at", "synced_at",
    )
    list_filter = ("status", "synced_at", "enriched_at")
    search_fields = ("backend_id", "slug", "status")
    readonly_fields = (
        "backend_id", "lat", "long", "slug", "status", "price_per_acre", "total_land_size", "total_price",
        "created_at", "updated_at", "exposure_type", "seller_type", "zone_type", "is_exact", "approach_road_length",
        "order_total_price_in_lakhs", "order_total_size_in_acres", "order_price_per_acre_in_lakhs",
        "payload", "synced_at", "location_point", "enriched_layers", "enriched_at",
    )
    fieldsets = (
        ("Identity", {"fields": ("backend_id", "synced_at")}),
        ("Columns", {"fields": ("lat", "long", "slug", "status", "price_per_acre", "total_land_size", "total_price", "created_at", "updated_at", "exposure_type", "seller_type", "zone_type", "is_exact", "approach_road_length")}),
        (
            "API ordering (denormalized)",
            {
                "fields": ("order_total_price_in_lakhs", "order_total_size_in_acres", "order_price_per_acre_in_lakhs"),
                "description": "Lakhs / acres / lakhs-per-acre for listing-links sort. Set on sync; run backfill_listing_order_metrics for legacy rows.",
            },
        ),
        ("Enrichment", {"fields": ("location_point", "enriched_layers", "enriched_at"), "description": "Layer overlap/nearby (0–30 km). Filled by enrich_listing_layers."}),
        ("API payload", {"fields": ("payload",)}),
    )
    ordering = ("-synced_at",)


@admin.register(SyncedPlot)
class SyncedPlotAdmin(admin.ModelAdmin):
    """Plot data from GET /plots/. Columns + payload + enrichment."""
    list_display = (
        "id", "backend_id", "lat", "long", "status", "total_plot_size", "total_price",
        "order_total_price_in_lakhs", "order_total_size_in_acres", "order_price_per_acre_in_lakhs",
        "updated_at", "enriched_at", "synced_at",
    )
    list_filter = ("status", "synced_at", "enriched_at")
    search_fields = ("backend_id", "slug", "status")
    readonly_fields = (
        "backend_id", "lat", "long", "slug", "status", "total_plot_size", "total_price", "price_per_square_yard",
        "created_at", "updated_at", "exposure_type", "seller_type", "zone_type", "is_exact", "abutting_road_length",
        "order_total_price_in_lakhs", "order_total_size_in_acres", "order_price_per_acre_in_lakhs",
        "payload", "synced_at", "location_point", "enriched_layers", "enriched_at",
    )
    fieldsets = (
        ("Identity", {"fields": ("backend_id", "synced_at")}),
        ("Columns", {"fields": ("lat", "long", "slug", "status", "total_plot_size", "total_price", "price_per_square_yard", "created_at", "updated_at", "exposure_type", "seller_type", "zone_type", "is_exact", "abutting_road_length")}),
        (
            "API ordering (denormalized)",
            {
                "fields": ("order_total_price_in_lakhs", "order_total_size_in_acres", "order_price_per_acre_in_lakhs"),
                "description": "Normalized to lakhs / acres / lakhs-per-acre for listing-links sort. Set on sync; run backfill_listing_order_metrics for legacy rows.",
            },
        ),
        ("Enrichment", {"fields": ("location_point", "enriched_layers", "enriched_at"), "description": "Layer overlap/nearby (0–30 km). Filled by enrich_listing_layers."}),
        ("API payload", {"fields": ("payload",)}),
    )
    ordering = ("-synced_at",)


@admin.register(SyncedDeveloperLand)
class SyncedDeveloperLandAdmin(admin.ModelAdmin):
    """Developer Land from GET /developer-lands-listings/. Columns + payload + enrichment."""
    list_display = (
        "id", "backend_id", "status", "deal_type", "total_land_size", "total_price",
        "order_total_price_in_lakhs", "order_total_size_in_acres", "order_price_per_acre_in_lakhs",
        "updated_at", "enriched_at", "synced_at",
    )
    list_filter = ("status", "deal_type", "synced_at", "enriched_at")
    search_fields = ("backend_id", "marker_title", "location", "status")
    readonly_fields = (
        "backend_id", "status", "location", "deal_type", "total_land_size", "total_price", "price_per_acre",
        "created_at", "updated_at", "exposure_type", "marker_title", "description",
        "order_total_price_in_lakhs", "order_total_size_in_acres", "order_price_per_acre_in_lakhs",
        "payload", "synced_at", "location_point", "enriched_layers", "enriched_at",
    )
    fieldsets = (
        ("Identity", {"fields": ("backend_id", "synced_at")}),
        ("Columns", {"fields": ("status", "location", "deal_type", "total_land_size", "total_price", "price_per_acre", "created_at", "updated_at", "exposure_type", "marker_title", "description")}),
        (
            "API ordering (denormalized)",
            {
                "fields": ("order_total_price_in_lakhs", "order_total_size_in_acres", "order_price_per_acre_in_lakhs"),
                "description": "Lakhs / acres / lakhs-per-acre for listing-links sort. Set on sync; run backfill_listing_order_metrics for legacy rows.",
            },
        ),
        ("Enrichment", {"fields": ("location_point", "enriched_layers", "enriched_at"), "description": "Layer overlap/nearby (0–30 km). Filled by enrich_listing_layers."}),
        ("API payload", {"fields": ("payload",)}),
    )
    ordering = ("-synced_at",)


@admin.register(SyncedDeveloperPlot)
class SyncedDeveloperPlotAdmin(admin.ModelAdmin):
    """Developer Plot from GET /developer-plots-listings/. Columns + payload + enrichment."""
    list_display = (
        "id", "backend_id", "status", "deal_type", "total_plot_size", "total_price",
        "order_total_price_in_lakhs", "order_total_size_in_acres", "order_price_per_acre_in_lakhs",
        "updated_at", "enriched_at", "synced_at",
    )
    list_filter = ("status", "deal_type", "synced_at", "enriched_at")
    search_fields = ("backend_id", "marker_title", "location", "status")
    readonly_fields = (
        "backend_id", "status", "location", "deal_type", "total_plot_size", "total_price", "price_per_square_yard",
        "created_at", "updated_at", "exposure_type", "marker_title", "description",
        "order_total_price_in_lakhs", "order_total_size_in_acres", "order_price_per_acre_in_lakhs",
        "payload", "synced_at", "location_point", "enriched_layers", "enriched_at",
    )
    fieldsets = (
        ("Identity", {"fields": ("backend_id", "synced_at")}),
        ("Columns", {"fields": ("status", "location", "deal_type", "total_plot_size", "total_price", "price_per_square_yard", "created_at", "updated_at", "exposure_type", "marker_title", "description")}),
        (
            "API ordering (denormalized)",
            {
                "fields": ("order_total_price_in_lakhs", "order_total_size_in_acres", "order_price_per_acre_in_lakhs"),
                "description": "Normalized to lakhs / acres / lakhs-per-acre for listing-links sort. Set on sync; run backfill_listing_order_metrics for legacy rows.",
            },
        ),
        ("Enrichment", {"fields": ("location_point", "enriched_layers", "enriched_at"), "description": "Layer overlap/nearby (0–30 km). Filled by enrich_listing_layers."}),
        ("API payload", {"fields": ("payload",)}),
    )
    ordering = ("-synced_at",)


@admin.register(LgdDivision)
class LgdDivisionAdmin(gis_admin.GISModelAdmin):
    """Mirror of 1acre-be LgdDivision rows used for relevance overlap."""
    list_display = (
        "id", "backend_id", "name", "division_type", "state_backend_id",
        "parent_backend_id", "synced_at",
    )
    list_filter = ("division_type", "state_backend_id")
    search_fields = ("name", "slug", "code", "backend_id")
    readonly_fields = ("synced_at",)
    autocomplete_fields = ("parent",)
    ordering = ("division_type", "name")


@admin.register(RelevantLayer)
class RelevantLayerAdmin(admin.ModelAdmin):
    """Computed (DataLayer, LgdDivision) overlap pairs."""
    list_display = (
        "id", "layer", "lgddivision", "matched_level",
        "source_state_backend_id", "updated_at",
    )
    list_filter = ("matched_level", "source_state_backend_id")
    search_fields = ("layer__slug", "layer__name", "lgddivision__name", "lgddivision__backend_id")
    autocomplete_fields = ("layer", "lgddivision")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-updated_at",)


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "key_prefix", "is_active", "created_at", "last_used_at")
    list_filter = ("is_active",)
    search_fields = ("name", "key_prefix")
    readonly_fields = ("key_hash", "key_prefix", "created_at", "last_used_at")
    fieldsets = (
        (None, {"fields": ("name", "is_active", "allowed_domains")}),
        ("Key (auto-generated on create)", {"fields": ("key_prefix", "key_hash", "created_at", "last_used_at")}),
    )

    def get_readonly_fields(self, request, obj=None):
        # When adding, only name and is_active are editable; key fields are set in save_model
        if obj is None:
            return ("key_hash", "key_prefix", "created_at", "last_used_at")
        return super().get_readonly_fields(request, obj)

    def add_view(self, request, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_key_instructions"] = True
        return super().add_view(request, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        raw_key = None
        if not change:  # Creating new key: prefix geom_ + random, total 256 chars
            prefix = "geom_"
            # 251 random chars after prefix; token_urlsafe(189) yields ~252 chars
            random_part = secrets.token_urlsafe(189)[:251]
            raw_key = prefix + random_part
            assert len(raw_key) == 256, "API key must be 256 chars"
            obj.key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
            obj.key_prefix = raw_key[:12]  # e.g. geom_xxxxxxx for display
            if getattr(obj, 'user_id', None) is None:
                obj.user = request.user
        super().save_model(request, obj, form, change)
        if raw_key:
            messages.success(
                request,
                f"API Key created. Copy it now — it won't be shown again: {raw_key}",
            )


admin.site.site_header = "GIS Data Management"
admin.site.site_title = "GIS Admin"
admin.site.index_title = "GIS Data Administration"
