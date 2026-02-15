"""
Listing–Layer Enrichment Service

For each listing (point), discovers:
- Overlapping layers: listing point falls inside layer geometry (distance_km = 0)
- Nearby layers: shortest distance from point to layer edge in [0.01, 30] km

Excludes DEVELOPER_LISTING category (listing's own TIF layers).
Stores unified enriched_layers: list of { layer_id, layer_slug, layer_type, distance_km }.

Supports:
- DeveloperListing (existing)
- SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot (all 4 Synced* tables).
"""

import logging
import re
from django.utils import timezone
from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.db.models import GeometryField
from django.db.models import Exists, FloatField, OuterRef, Q
from django.db.models.expressions import RawSQL
from django.db.models.functions import Cast

from maps.models import (
    DeveloperListing,
    DataLayer,
    GeoFeature,
    SyncedLand,
    SyncedPlot,
    SyncedDeveloperLand,
    SyncedDeveloperPlot,
)

logger = logging.getLogger(__name__)

# Maximum distance (km) to consider a layer "nearby"; beyond this, layer is excluded
NEARBY_THRESHOLD_KM = 30.0

# Approximate 30 km in degrees (for dwithin: PostGIS geographic expects degrees)
DEGREES_30KM = 30.0 / 111.32

# Minimum non-zero distance to store (avoids floating point noise for overlapping)
MIN_NEARBY_KM = 0.01

# Bbox delta in degrees (~30 km) to pre-filter layers that could possibly touch the point
_DEGREES_BUFFER = NEARBY_THRESHOLD_KM / 111.0

# Batch size for bulk_update when enriching synced tables (fewer round-trips)
ENRICH_BULK_BATCH_SIZE = 250


def _get_state_name_from_payload(payload):
    """
    Extract state name from listing payload (division_info or state field).
    Returns None if not found. Used to restrict enrichment to layers in the same state.
    """
    if not payload or not isinstance(payload, dict):
        return None
    # division_info: [ {"division_type": "state", "name": "Andhra Pradesh"}, ... ]
    division_info = payload.get('division_info') or payload.get('lgd_division_info')
    if isinstance(division_info, list):
        for d in division_info:
            if isinstance(d, dict) and (d.get('division_type') or '').lower() == 'state':
                name = (d.get('name') or '').strip()
                if name:
                    return name
    # Fallback: top-level state
    state = (payload.get('state') or '').strip()
    if state:
        return state
    return None


def _layer_ids_near_point(point: Point, state_name=None):
    """
    Return list of DataLayer IDs whose bbox intersects (point ± 30km).
    Only processed, active-city layers, excluding DEVELOPER_LISTING.
    When state_name is set, only layers from that state (city.state_ref or city.state) are included,
    so we never return e.g. Hyderabad layers for an Andhra Pradesh listing.
    """
    if not point or point.empty:
        return []
    x, y = point.x, point.y
    qs = DataLayer.objects.filter(
        is_processed=True,
        city__is_active=True,
        bbox_xmin__isnull=False,
        bbox_ymin__isnull=False,
        bbox_xmax__isnull=False,
        bbox_ymax__isnull=False,
        bbox_xmax__gte=x - _DEGREES_BUFFER,
        bbox_xmin__lte=x + _DEGREES_BUFFER,
        bbox_ymax__gte=y - _DEGREES_BUFFER,
        bbox_ymin__lte=y + _DEGREES_BUFFER,
    )
    if state_name:
        qs = qs.filter(
            Q(city__state_ref__name__iexact=state_name) | Q(city__state__iexact=state_name)
        )
    return list(
        qs.exclude(category__code='DEVELOPER_LISTING').values_list('id', flat=True)
    )


def get_listing_point(listing: DeveloperListing):
    """Return Point (srid=4326) for DeveloperListing, or None if no coordinates."""
    point = listing.get_listing_point()
    if point is None:
        return None
    if point.srid != 4326:
        point.transform(4326)
    return point


def _parse_lat_lng(lat, lng):
    """Return (lat_f, lng_f) as floats or (None, None)."""
    try:
        lat_f = float(lat) if lat is not None else None
        lng_f = float(lng) if lng is not None else None
        return lat_f, lng_f
    except (TypeError, ValueError):
        return None, None


def _parse_location_string(s):
    """Parse 'lat,lng' or 'lat, lng' string; return (lat, lng) or (None, None)."""
    if not s or not isinstance(s, str):
        return None, None
    match = re.match(r'^\s*([-\d.]+)\s*,\s*([-\d.]+)\s*$', s.strip())
    if not match:
        return None, None
    try:
        return float(match.group(1)), float(match.group(2))
    except (ValueError, TypeError):
        return None, None


def get_point_for_synced(record, update_location_point: bool = True):
    """
    Return Point (srid=4326) for a SyncedLand, SyncedPlot, SyncedDeveloperLand, or SyncedDeveloperPlot.
    Priority: payload lat/long -> record lat/long -> location string -> location_point.
    If update_location_point is True, sets record.location_point when coords are resolved.
    """
    lat, lng = None, None
    payload = getattr(record, 'payload', None) or {}

    if isinstance(record, (SyncedLand, SyncedPlot)):
        # Priority: (1) payload lat/long, (2) record.lat/long, (3) record.location if present (SyncedLand/Plot have no location field)
        lat = payload.get('lat') or payload.get('latitude')
        lng = payload.get('long') or payload.get('longitude') or payload.get('lng') or payload.get('lon')
        if lat is None or lng is None:
            lat, lng = getattr(record, 'lat', None), getattr(record, 'long', None)
        loc_str = getattr(record, 'location', None)
        if (lat is None or lng is None) and loc_str:
            lat, lng = _parse_location_string(loc_str)
    elif isinstance(record, (SyncedDeveloperLand, SyncedDeveloperPlot)):
        # Priority: (1) record.location_point, (2) payload lat/long, (3) record.location string
        if record.location_point:
            p = record.location_point
            if p.srid != 4326:
                p = p.clone()
                p.transform(4326)
            return p
        lat = payload.get('lat') or payload.get('latitude')
        lng = payload.get('long') or payload.get('longitude') or payload.get('lng') or payload.get('lon')
        loc_str = getattr(record, 'location', None)
        if (lat is None or lng is None) and loc_str:
            lat, lng = _parse_location_string(loc_str)

    lat, lng = _parse_lat_lng(lat, lng)
    if lat is None or lng is None:
        return None
    try:
        point = Point(float(lng), float(lat), srid=4326)
    except (TypeError, ValueError):
        return None
    if update_location_point and (record.location_point is None or record.location_point.wkt != point.wkt):
        record.location_point = point
        record.save(update_fields=['location_point'])
    return point


def compute_enriched_layers_for_point(point: Point, state_name=None):
    """
    Compute list of relevant layers for a given point (overlapping + nearby up to 30 km).

    Returns list of dicts: { "layer_id", "layer_slug", "layer_type", "distance_km" }.
    distance_km = 0 means overlap; (0.01, 30] means nearby.
    When state_name is set, only layers from that state are returned (avoids wrong-state results
    e.g. Hyderabad layers for an Andhra Pradesh listing).
    Uses PostGIS geography for meter-based distance where available.
    Pre-filters layers by bbox so only layers that could touch the point are queried (faster).
    """
    if not point or point.empty:
        return []

    # Only consider layers whose bbox intersects point ± 30km (drastically reduces GeoFeature rows)
    layer_ids = _layer_ids_near_point(point, state_name=state_name)
    if not layer_ids:
        return []

    overlapping_layer_ids = set(
        GeoFeature.objects.filter(
            geometry__contains=point,
            is_valid=True,
            layer_id__in=layer_ids,
        ).values_list('layer_id', flat=True).distinct()
    )

    # Nearby: features within 30 km that are not overlapping (min distance per layer)
    nearby_qs = (
        GeoFeature.objects.filter(
            geometry__dwithin=(point, DEGREES_30KM),
            is_valid=True,
            layer_id__in=layer_ids,
        )
        .exclude(layer_id__in=overlapping_layer_ids)
        .annotate(
            dist_m=RawSQL(
                'ST_Distance(geometry::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography)',
                (point.x, point.y),
                output_field=FloatField(),
            )
        )
        .values('layer_id', 'layer__slug', 'layer__category__code', 'dist_m')
    )

    # Group by layer_id, keep min distance
    layer_min_dist = {}
    for row in nearby_qs:
        lid = row['layer_id']
        dist_km = row['dist_m'] / 1000.0 if row['dist_m'] is not None else None
        if dist_km is None or dist_km > NEARBY_THRESHOLD_KM:
            continue
        if lid not in layer_min_dist or dist_km < layer_min_dist[lid][0]:
            layer_min_dist[lid] = (dist_km, row['layer__slug'], row['layer__category__code'] or 'UNCLASSIFIED')

    # Build layer_id -> (slug, category_code) for overlapping
    overlapping_info = {}
    if overlapping_layer_ids:
        for row in DataLayer.objects.filter(id__in=overlapping_layer_ids).values('id', 'slug', 'category__code'):
            overlapping_info[row['id']] = (row['slug'], row['category__code'] or 'UNCLASSIFIED')

    result = []
    seen = set()

    for layer_id in overlapping_layer_ids:
        if layer_id in seen:
            continue
        seen.add(layer_id)
        slug, code = overlapping_info.get(layer_id, ('', 'UNCLASSIFIED'))
        result.append({
            'layer_id': layer_id,
            'layer_slug': slug,
            'layer_type': code,
            'distance_km': 0.0,
        })

    for layer_id, (dist_km, slug, code) in layer_min_dist.items():
        if layer_id in seen:
            continue
        seen.add(layer_id)
        if dist_km < MIN_NEARBY_KM:
            dist_km = MIN_NEARBY_KM
        result.append({
            'layer_id': layer_id,
            'layer_slug': slug,
            'layer_type': code,
            'distance_km': round(dist_km, 4),
        })

    # Sort by distance_km then layer_id for stable ordering
    result.sort(key=lambda x: (x['distance_km'], x['layer_id']))
    return result


def get_place_for_point_in_layer(point: Point, layer_id: int, distance_km: float):
    """
    Resolve the specific place (feature) for a point in a layer: the containing feature
    when distance_km=0, or the nearest feature when distance_km>0. Same idea as
    CoordinateSearchTestView: which feature/polygon the point is inside or closest to.

    Returns a dict with feature_id, feature_name, layer_slug, layer_name, category,
    distance_meters, and optional area, zone_category, plot_category, properties;
    or None if no feature found.
    """
    if not point or point.empty:
        return None
    try:
        layer = DataLayer.objects.filter(id=layer_id).select_related('category', 'city', 'city__state_ref').first()
        if not layer:
            return None
        layer_slug = layer.slug
        layer_name = layer.name or ''
        category = (layer.category.code if layer.category else '') or 'UNCLASSIFIED'

        if distance_km == 0:
            # Point is inside: get containing feature(s), pick largest by area
            feature = (
                GeoFeature.objects.filter(
                    layer_id=layer_id,
                    geometry__contains=point,
                    is_valid=True,
                )
                .select_related('layer', 'layer__category')
                .order_by('-area')
                .first()
            )
            distance_meters = 0.0
        else:
            # Nearby: get nearest feature within 30 km (distance in meters via geography)
            qs = (
                GeoFeature.objects.filter(
                    layer_id=layer_id,
                    geometry__dwithin=(point, DEGREES_30KM),
                    is_valid=True,
                )
                .select_related('layer', 'layer__category')
                .annotate(
                    dist_m=RawSQL(
                        'ST_Distance(geometry::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography)',
                        (point.x, point.y),
                        output_field=FloatField(),
                    )
                )
                .order_by('dist_m')
            )
            feature = qs.first()
            if feature is None:
                return None
            dist_m = getattr(feature, 'dist_m', None)
            distance_meters = round(float(dist_m) or distance_km * 1000, 2)
        if feature is None:
            return None

        area_sq_m = float(feature.area) if feature.area else None
        from .feature_display import get_feature_display_data
        display = get_feature_display_data(layer, feature)
        place = {
            'feature_id': feature.id,
            'feature_name': feature.name or 'Unnamed',
            'layer_slug': layer_slug,
            'layer_name': layer_name,
            'category': category,
            'distance': distance_meters,
            'distance_meters': distance_meters,
            'data': display.get('data', ''),
            'fill_color': display.get('fill_color', ''),
            'area_square_meters': area_sq_m,
            'zone_category': feature.zone_category or '',
            'plot_category': feature.plot_category or '',
            'symbology': feature.symbology or '',
            'plu_code': feature.plu_primary_code or '',
            'plu_name': feature.plu_secondary_1 or '',
        }
        if getattr(feature, 'properties', None):
            place['properties'] = feature.properties
        return place
    except Exception as e:
        logger.debug("get_place_for_point_in_layer: %s", e)
        return None


def enrich_listing(listing: DeveloperListing, update_location_point: bool = True) -> bool:
    """
    Compute and save enriched_layers for one listing. Optionally sync location_point from listing_data.

    Returns True if enrichment was run and saved, False if listing has no point (skipped).
    When no coordinates: sets enriched_layers=[], enriched_at=None so API can return null/false.
    Only layers from the listing's state (from listing_data.division_info or .state) are included.
    """
    if update_location_point:
        _sync_listing_location_point(listing)

    point = get_listing_point(listing)
    if point is None:
        logger.debug("Listing %s has no coordinates; clearing enrichment", listing.id)
        listing.enriched_layers = []
        listing.enriched_at = None
        listing.save(update_fields=['enriched_layers', 'enriched_at'])
        return False

    state_name = _get_state_name_from_payload(listing.listing_data or {})
    enriched = compute_enriched_layers_for_point(point, state_name=state_name)
    listing.enriched_layers = enriched
    listing.enriched_at = timezone.now()
    listing.save(update_fields=['enriched_layers', 'enriched_at'])
    logger.debug("Enriched listing %s: %d layers", listing.id, len(enriched))
    return True


def _sync_listing_location_point(listing: DeveloperListing) -> None:
    """Set listing.location_point from listing_data lat/lng if present."""
    point = listing.get_listing_point()
    if point is not None and (listing.location_point is None or listing.location_point != point):
        listing.location_point = point
        listing.save(update_fields=['location_point'])


def enrich_listings_queryset(queryset, update_location_point: bool = True):
    """Enrich all listings in queryset that have (or can derive) a point. Returns (processed, skipped)."""
    processed = 0
    skipped = 0
    for listing in queryset.iterator():
        if enrich_listing(listing, update_location_point=update_location_point):
            processed += 1
        else:
            skipped += 1
    return processed, skipped


def enrich_synced_record(record, update_location_point: bool = True) -> bool:
    """
    Compute and save enriched_layers for one SyncedLand, SyncedPlot, SyncedDeveloperLand, or SyncedDeveloperPlot.
    Returns True if enrichment was run and saved, False if record has no point (skipped).
    When no coordinates: sets enriched_layers=[], enriched_at=None so API can return null/false.
    Only layers from the listing's state (from payload.division_info or .state) are included.
    """
    point = get_point_for_synced(record, update_location_point=update_location_point)
    if point is None:
        logger.debug("Synced record %s %s has no coordinates; clearing enrichment", type(record).__name__, getattr(record, 'backend_id', record.pk))
        record.enriched_layers = []
        record.enriched_at = None
        record.save(update_fields=['enriched_layers', 'enriched_at'])
        return False
    payload = getattr(record, 'payload', None) or {}
    state_name = _get_state_name_from_payload(payload)
    enriched = compute_enriched_layers_for_point(point, state_name=state_name)
    record.enriched_layers = enriched
    record.enriched_at = timezone.now()
    record.save(update_fields=['enriched_layers', 'enriched_at'])
    logger.debug("Enriched %s backend_id=%s: %d layers", type(record).__name__, getattr(record, 'backend_id', record.pk), len(enriched))
    return True


def enrich_synced_queryset(queryset, update_location_point: bool = True):
    """
    Enrich all records in queryset (SyncedLand, SyncedPlot, etc.) that have a point.
    Records with no coordinates get enriched_layers=[], enriched_at=None (cleared).
    Uses bulk_update in batches. Returns (processed, skipped).
    """
    processed = 0
    skipped = 0
    batch = []
    clear_batch = []
    now = timezone.now()
    for record in queryset.iterator():
        point = get_point_for_synced(record, update_location_point=update_location_point)
        if point is None:
            record.enriched_layers = []
            record.enriched_at = None
            clear_batch.append(record)
            skipped += 1
            if len(clear_batch) >= ENRICH_BULK_BATCH_SIZE:
                type(record).objects.bulk_update(clear_batch, ['enriched_layers', 'enriched_at'])
                clear_batch = []
            continue
        payload = getattr(record, 'payload', None) or {}
        state_name = _get_state_name_from_payload(payload)
        enriched = compute_enriched_layers_for_point(point, state_name=state_name)
        record.enriched_layers = enriched
        record.enriched_at = now
        batch.append(record)
        processed += 1
        if len(batch) >= ENRICH_BULK_BATCH_SIZE:
            type(record).objects.bulk_update(batch, ['enriched_layers', 'enriched_at'])
            batch = []
    if batch:
        type(batch[0]).objects.bulk_update(batch, ['enriched_layers', 'enriched_at'])
    if clear_batch:
        type(clear_batch[0]).objects.bulk_update(clear_batch, ['enriched_layers', 'enriched_at'])
    return processed, skipped


def get_listings_near_layer(layer: DataLayer, within_km: float = NEARBY_THRESHOLD_KM):
    """
    Return DeveloperListings that have a location point within `within_km` of the layer's geometry.
    Used when a new layer is added to re-enrich affected listings.
    """
    if layer.bbox_xmin is None or layer.bbox_ymin is None or layer.bbox_ymax is None or layer.bbox_xmax is None:
        return DeveloperListing.objects.none()
    delta = within_km / 111.0
    expanded = Polygon.from_bbox((
        layer.bbox_xmin - delta,
        layer.bbox_ymin - delta,
        layer.bbox_xmax + delta,
        layer.bbox_ymax + delta,
    ))
    expanded.srid = 4326
    return DeveloperListing.objects.filter(
        location_point__within=expanded,
        is_active=True,
    ).exclude(location_point__isnull=True)


def get_synced_listings_near_layer(layer: DataLayer, within_km: float = NEARBY_THRESHOLD_KM):
    """
    Return (land_qs, plot_qs, dev_land_qs, dev_plot_qs) of Synced* records with location_point
    within `within_km` of the layer's bbox. Used to re-enrich when a new layer is added.
    """
    if layer.bbox_xmin is None or layer.bbox_ymin is None or layer.bbox_ymax is None or layer.bbox_xmax is None:
        return (
            SyncedLand.objects.none(),
            SyncedPlot.objects.none(),
            SyncedDeveloperLand.objects.none(),
            SyncedDeveloperPlot.objects.none(),
        )
    delta = within_km / 111.0
    expanded = Polygon.from_bbox((
        layer.bbox_xmin - delta,
        layer.bbox_ymin - delta,
        layer.bbox_xmax + delta,
        layer.bbox_ymax + delta,
    ))
    expanded.srid = 4326
    land_qs = SyncedLand.objects.filter(location_point__within=expanded).exclude(location_point__isnull=True)
    plot_qs = SyncedPlot.objects.filter(location_point__within=expanded).exclude(location_point__isnull=True)
    dev_land_qs = SyncedDeveloperLand.objects.filter(location_point__within=expanded).exclude(location_point__isnull=True)
    dev_plot_qs = SyncedDeveloperPlot.objects.filter(location_point__within=expanded).exclude(location_point__isnull=True)
    return land_qs, plot_qs, dev_land_qs, dev_plot_qs


def _serialize_point_detail(record, source):
    """Build a small detail dict for a listing record: source, id, backend_id/backend_listing_id, lat, lng."""
    out = {'source': source, 'id': record.pk}
    if hasattr(record, 'backend_id') and record.backend_id is not None:
        out['backend_id'] = record.backend_id
    if hasattr(record, 'backend_listing_id') and record.backend_listing_id is not None:
        out['backend_listing_id'] = record.backend_listing_id
    pt = getattr(record, 'location_point', None)
    if pt:
        out['lat'] = pt.y
        out['lng'] = pt.x
    elif hasattr(record, 'lat') and record.lat is not None and hasattr(record, 'long') and record.long is not None:
        out['lat'] = float(record.lat)
        out['lng'] = float(record.long)
    return out


def get_point_counts_per_layer(layer_ids=None, within_km=None, include_details=False, detail_limit=200):
    """
    For each layer (or all processed layers if layer_ids omitted), return counts of listing
    points (from DeveloperListing + SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot)
    that overlap (point inside layer geometry) or are nearby (within within_km, not overlapping).
    Same spatial rules as enrichment. Counts only records with non-null location_point.
    When include_details is True, also return overlapping_details and nearby_details (list of
    { source, id, backend_id, lat, lng }) per layer, limited to detail_limit items each.
    """
    if within_km is None:
        within_km = NEARBY_THRESHOLD_KM
    deg = within_km / 111.32  # approximate degrees for dwithin

    layers_qs = DataLayer.objects.filter(
        is_processed=True,
        city__is_active=True,
    ).exclude(category__code='DEVELOPER_LISTING').exclude(
        bbox_xmin__isnull=True, bbox_ymin__isnull=True,
        bbox_xmax__isnull=True, bbox_ymax__isnull=True,
    )
    if layer_ids is not None:
        layers_qs = layers_qs.filter(id__in=layer_ids)
    layers = list(layers_qs.select_related('city', 'category').values('id', 'slug', 'category__code', 'city__name'))

    result = []
    for layer in layers:
        layer_id = layer['id']
        slug = layer['slug'] or ''
        layer_type = (layer['category__code'] or 'UNCLASSIFIED')
        city_name = layer['city__name'] or ''

        # Cast location_point (geography) to geometry so ST_Contains(geometry, geometry) works
        location_point_geom = Cast(OuterRef('location_point'), GeometryField())
        # Subquery: any GeoFeature of this layer contains the point
        contained_subq = GeoFeature.objects.filter(
            layer_id=layer_id,
            is_valid=True,
            geometry__contains=location_point_geom,
        )
        # Subquery: any GeoFeature of this layer is within distance of the point
        dwithin_subq = GeoFeature.objects.filter(
            layer_id=layer_id,
            is_valid=True,
            geometry__dwithin=(location_point_geom, deg),
        )

        def overlapping_qs(qs):
            return qs.filter(location_point__isnull=False).annotate(
                contained=Exists(contained_subq),
            ).filter(contained=True)

        def nearby_qs(qs):
            return qs.filter(location_point__isnull=False).annotate(
                contained=Exists(contained_subq),
                within_dist=Exists(dwithin_subq),
            ).filter(within_dist=True, contained=False)

        # Counts
        land_over_q = overlapping_qs(SyncedLand.objects.all())
        land_near_q = nearby_qs(SyncedLand.objects.all())
        plot_over_q = overlapping_qs(SyncedPlot.objects.all())
        plot_near_q = nearby_qs(SyncedPlot.objects.all())
        dev_land_over_q = overlapping_qs(SyncedDeveloperLand.objects.all())
        dev_land_near_q = nearby_qs(SyncedDeveloperLand.objects.all())
        dev_plot_over_q = overlapping_qs(SyncedDeveloperPlot.objects.all())
        dev_plot_near_q = nearby_qs(SyncedDeveloperPlot.objects.all())
        dev_listing_over_q = overlapping_qs(DeveloperListing.objects.filter(is_active=True))
        dev_listing_near_q = nearby_qs(DeveloperListing.objects.filter(is_active=True))

        land_over = land_over_q.count()
        land_near = land_near_q.count()
        plot_over = plot_over_q.count()
        plot_near = plot_near_q.count()
        dev_land_over = dev_land_over_q.count()
        dev_land_near = dev_land_near_q.count()
        dev_plot_over = dev_plot_over_q.count()
        dev_plot_near = dev_plot_near_q.count()
        dev_listing_over = dev_listing_over_q.count()
        dev_listing_near = dev_listing_near_q.count()

        overlapping_total = land_over + plot_over + dev_land_over + dev_plot_over + dev_listing_over
        nearby_total = land_near + plot_near + dev_land_near + dev_plot_near + dev_listing_near

        row = {
            'layer_id': layer_id,
            'layer_slug': slug,
            'layer_type': layer_type,
            'city': city_name,
            'overlapping_count': overlapping_total,
            'nearby_count': nearby_total,
            'total_count': overlapping_total + nearby_total,
            'by_source': {
                'land': land_over + land_near,
                'plot': plot_over + plot_near,
                'developer_land': dev_land_over + dev_land_near,
                'developer_plot': dev_plot_over + dev_plot_near,
                'developer_listing': dev_listing_over + dev_listing_near,
            },
        }

        if include_details and detail_limit > 0:
            overlapping_details = []
            nearby_details = []
            over_queries = [
                (land_over_q, 'land'), (plot_over_q, 'plot'),
                (dev_land_over_q, 'developer_land'), (dev_plot_over_q, 'developer_plot'),
                (dev_listing_over_q, 'developer_listing'),
            ]
            near_queries = [
                (land_near_q, 'land'), (plot_near_q, 'plot'),
                (dev_land_near_q, 'developer_land'), (dev_plot_near_q, 'developer_plot'),
                (dev_listing_near_q, 'developer_listing'),
            ]
            for qs, source in over_queries:
                if len(overlapping_details) >= detail_limit:
                    break
                for rec in qs[: detail_limit - len(overlapping_details)]:
                    overlapping_details.append(_serialize_point_detail(rec, source))
                    if len(overlapping_details) >= detail_limit:
                        break
            for qs, source in near_queries:
                if len(nearby_details) >= detail_limit:
                    break
                for rec in qs[: detail_limit - len(nearby_details)]:
                    nearby_details.append(_serialize_point_detail(rec, source))
                    if len(nearby_details) >= detail_limit:
                        break
            row['overlapping_details'] = overlapping_details
            row['nearby_details'] = nearby_details

        result.append(row)
    return result
