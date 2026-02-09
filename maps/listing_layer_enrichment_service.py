"""
Listing–Layer Enrichment Service

For each developer listing (point), discovers:
- Overlapping layers: listing point falls inside layer geometry (distance_km = 0)
- Nearby layers: shortest distance from point to layer edge in [0.01, 30] km

Excludes DEVELOPER_LISTING category (listing's own TIF layers).
Stores unified enriched_layers on DeveloperListing: list of
{ layer_id, layer_slug, layer_type, distance_km }.
"""

import logging
from django.utils import timezone
from django.contrib.gis.geos import Point, Polygon
from django.db.models import FloatField
from django.db.models.expressions import RawSQL

from maps.models import DeveloperListing, DataLayer, GeoFeature

logger = logging.getLogger(__name__)

# Maximum distance (km) to consider a layer "nearby"; beyond this, layer is excluded
NEARBY_THRESHOLD_KM = 30.0

# Approximate 30 km in degrees (for dwithin: PostGIS geographic expects degrees)
DEGREES_30KM = 30.0 / 111.32

# Minimum non-zero distance to store (avoids floating point noise for overlapping)
MIN_NEARBY_KM = 0.01


def get_listing_point(listing: DeveloperListing):
    """Return Point (srid=4326) for listing, or None if no coordinates."""
    point = listing.get_listing_point()
    if point is None:
        return None
    if point.srid != 4326:
        point.transform(4326)
    return point


def compute_enriched_layers_for_point(point: Point):
    """
    Compute list of relevant layers for a given point (overlapping + nearby up to 30 km).

    Returns list of dicts: { "layer_id", "layer_slug", "layer_type", "distance_km" }.
    distance_km = 0 means overlap; (0.01, 30] means nearby.
    Uses PostGIS geography for meter-based distance where available.
    """
    if not point or point.empty:
        return []

    # Exclude listing-owned TIF layers
    base_layer_qs = DataLayer.objects.filter(
        is_processed=True,
        city__is_active=True,
    ).exclude(category__code='DEVELOPER_LISTING').select_related('category')

    overlapping_layer_ids = set(
        GeoFeature.objects.filter(
            geometry__contains=point,
            is_valid=True,
            layer__in=base_layer_qs,
        ).values_list('layer_id', flat=True).distinct()
    )

    # Nearby: features within 30 km that are not overlapping (min distance per layer)
    # Use degrees for dwithin (PostGIS geographic DWithin expects degree units)
    nearby_qs = (
        GeoFeature.objects.filter(
            geometry__dwithin=(point, DEGREES_30KM),
            is_valid=True,
            layer__in=base_layer_qs,
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


def enrich_listing(listing: DeveloperListing, update_location_point: bool = True) -> bool:
    """
    Compute and save enriched_layers for one listing. Optionally sync location_point from listing_data.

    Returns True if enrichment was run and saved, False if listing has no point (skipped).
    """
    if update_location_point:
        _sync_listing_location_point(listing)

    point = get_listing_point(listing)
    if point is None:
        logger.debug("Listing %s has no coordinates; skipping enrichment", listing.id)
        return False

    enriched = compute_enriched_layers_for_point(point)
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


def get_listings_near_layer(layer: DataLayer, within_km: float = NEARBY_THRESHOLD_KM):
    """
    Return listings that have a location point within `within_km` of the layer's geometry.
    Used when a new layer is added to re-enrich affected listings.
    """
    # Layer extent (bbox) for quick filter; then exact distance
    if layer.bbox_xmin is None or layer.bbox_ymin is None or layer.bbox_ymax is None or layer.bbox_xmax is None:
        return DeveloperListing.objects.none()
    # Expand bbox by within_km (approx 1 deg ~ 111 km)
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
