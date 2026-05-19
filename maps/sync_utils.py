"""
Shared helpers for syncing Land, Plot, Developer Land and Developer Plot data
from 1acre-be API or webhook payloads into SyncedLand, SyncedPlot,
SyncedDeveloperLand, SyncedDeveloperPlot.

Used by:
  - maps.management.commands.pull_land_plot_from_api (bulk pull)
  - maps.views.LandPlotWebhookView (land/plot webhook)
  - maps.views.DeveloperListingMediaWebhookView (developer listing webhook)

All data is stored: each defaults_* function sets payload=<full item> so the
complete API response or webhook listing_data is persisted in the Synced* payload JSONField.

Each defaults_* also sets order_total_price_in_lakhs, order_total_size_in_acres, and
order_price_per_acre_in_lakhs (see maps.listing_order_metrics) for cheap API ordering.
"""

from django.utils.dateparse import parse_datetime
from django.contrib.gis.geos import Point

from maps.listing_order_metrics import land_order_metrics, plot_order_metrics


def _f(v, default=None):
    if v is None:
        return default
    if isinstance(v, bool):
        return default
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except (ValueError, TypeError):
            return default
    return default


def _dt(s):
    if not s or not isinstance(s, str):
        return None
    return parse_datetime(s)


def _str_trunc(s, max_len):
    if s is None:
        return ''
    return (str(s) or '')[:max_len]


def _point_from_lat_lng(lat, lng):
    """Return Point(srid=4326) if both lat and lng are valid numbers, else None."""
    lat_f = _f(lat)
    lng_f = _f(lng)
    if lat_f is None or lng_f is None:
        return None
    try:
        return Point(float(lng_f), float(lat_f), srid=4326)
    except (TypeError, ValueError):
        return None


def _lat_lng_from_location(location):
    """
    Extract (lat, lng) from webhook/API location when lat/long are missing.
    Handles:
    - GeoJSON Point: {"type": "Point", "coordinates": [lng, lat]}
    - String: "lat,lng" or "lat, lng"
    Returns (lat, lng) or (None, None).
    """
    if location is None:
        return None, None
    # GeoJSON Point from 1acre-be PointField serialization
    if isinstance(location, dict):
        if location.get('type') == 'Point':
            coords = location.get('coordinates')
            if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                try:
                    lng_f = _f(coords[0])
                    lat_f = _f(coords[1])
                    if lng_f is not None and lat_f is not None:
                        return lat_f, lng_f
                except (TypeError, ValueError):
                    pass
        return None, None
    # "lat,lng" string (e.g. developer listing style)
    if isinstance(location, str) and location.strip():
        import re
        m = re.match(r'^\s*([-\d.]+)\s*,\s*([-\d.]+)\s*$', location.strip())
        if m:
            try:
                lat_f = float(m.group(1))
                lng_f = float(m.group(2))
                return lat_f, lng_f
            except (ValueError, TypeError):
                pass
    return None, None


def defaults_for_land(item):
    """Build SyncedLand defaults from API item or webhook listing_data. Full item stored in payload."""
    p = item if isinstance(item, dict) else {}
    lat, lng = _f(p.get('lat')), _f(p.get('long'))
    if lat is None or lng is None:
        loc_lat, loc_lng = _lat_lng_from_location(p.get('location'))
        if loc_lat is not None and loc_lng is not None:
            lat = loc_lat if lat is None else lat
            lng = loc_lng if lng is None else lng
    out = {
        'payload': item,
        'lat': lat,
        'long': lng,
        'slug': _str_trunc(p.get('slug'), 500),
        'status': _str_trunc(p.get('status'), 20),
        'price_per_acre': _f(p.get('price_per_acre')),
        'total_land_size': _f(p.get('total_land_size')),
        'total_price': _f(p.get('total_price')),
        'created_at': _dt(p.get('created_at')),
        'updated_at': _dt(p.get('updated_at')),
        'exposure_type': _str_trunc(p.get('exposure_type'), 20),
        'seller_type': _str_trunc(p.get('seller_type'), 30),
        'zone_type': (p.get('zone_type') or '')[:50] if p.get('zone_type') is not None else None,
        'is_exact': bool(p.get('is_exact')),
        'approach_road_length': _f(p.get('approach_road_length')),
        'lgd_slug': _str_trunc(p.get('lgd_slug'), 500),
        'marker_title': _str_trunc(p.get('marker_title'), 500),
        'marker_id': _str_trunc(p.get('marker_id'), 80),
    }
    pt = _point_from_lat_lng(lat, lng)
    if pt is not None:
        out['location_point'] = pt
    out.update(land_order_metrics(out.get('total_price'), out.get('total_land_size')))
    return out


def defaults_for_plot(item):
    """Build SyncedPlot defaults from API item or webhook listing_data. Full item stored in payload."""
    p = item if isinstance(item, dict) else {}
    lat, lng = _f(p.get('lat')), _f(p.get('long'))
    if lat is None or lng is None:
        loc_lat, loc_lng = _lat_lng_from_location(p.get('location'))
        if loc_lat is not None and loc_lng is not None:
            lat = loc_lat if lat is None else lat
            lng = loc_lng if lng is None else lng
    out = {
        'payload': item,
        'lat': lat,
        'long': lng,
        'slug': _str_trunc(p.get('slug'), 500),
        'status': _str_trunc(p.get('status'), 20),
        'total_plot_size': _f(p.get('total_plot_size')),
        'total_price': _f(p.get('total_price')),
        'price_per_square_yard': _f(p.get('price_per_square_yard')),
        'created_at': _dt(p.get('created_at')),
        'updated_at': _dt(p.get('updated_at')),
        'exposure_type': _str_trunc(p.get('exposure_type'), 20),
        'seller_type': _str_trunc(p.get('seller_type'), 30),
        'zone_type': (p.get('zone_type') or '')[:50] if p.get('zone_type') is not None else None,
        'is_exact': bool(p.get('is_exact')),
        'abutting_road_length': _f(p.get('abutting_road_length')),
        'lgd_slug': _str_trunc(p.get('lgd_slug'), 500),
        'marker_title': _str_trunc(p.get('marker_title'), 500),
        'marker_id': _str_trunc(p.get('marker_id'), 80),
    }
    pt = _point_from_lat_lng(lat, lng)
    if pt is not None:
        out['location_point'] = pt
    out.update(plot_order_metrics(out.get('total_price'), out.get('total_plot_size')))
    return out


def defaults_for_developer_land(item):
    """Build SyncedDeveloperLand defaults from API item or webhook listing_data. Full item stored in payload."""
    p = item if isinstance(item, dict) else {}
    lat = _f(p.get('lat')) or _f(p.get('latitude'))
    lng = _f(p.get('long')) or _f(p.get('lng')) or _f(p.get('longitude'))
    if lat is None and lng is None and p.get('location'):
        import re
        m = re.match(r'^\s*([-\d.]+)\s*,\s*([-\d.]+)\s*$', (p.get('location') or '').strip())
        if m:
            try:
                lat, lng = float(m.group(1)), float(m.group(2))
            except (ValueError, TypeError):
                pass
    out = {
        'payload': item,
        'status': _str_trunc(p.get('status'), 20),
        'location': _str_trunc(p.get('location'), 200),
        'deal_type': _str_trunc(p.get('deal_type'), 50),
        'total_land_size': _f(p.get('total_land_size')),
        'total_price': _f(p.get('total_price')),
        'price_per_acre': _f(p.get('price_per_acre')),
        'created_at': _dt(p.get('created_at')),
        'updated_at': _dt(p.get('updated_at')),
        'exposure_type': _str_trunc(p.get('exposure_type'), 20),
        'marker_title': _str_trunc(p.get('marker_title'), 500),
        'description': _str_trunc(p.get('description'), 10000),
        'lgd_slug': _str_trunc(p.get('lgd_slug'), 500),
    }
    pt = _point_from_lat_lng(lat, lng)
    if pt is not None:
        out['location_point'] = pt
    out.update(land_order_metrics(out.get('total_price'), out.get('total_land_size')))
    return out


def defaults_for_developer_plot(item):
    """Build SyncedDeveloperPlot defaults from API item or webhook listing_data. Full item stored in payload."""
    p = item if isinstance(item, dict) else {}
    lat = _f(p.get('lat')) or _f(p.get('latitude'))
    lng = _f(p.get('long')) or _f(p.get('lng')) or _f(p.get('longitude'))
    if lat is None and lng is None and p.get('location'):
        import re
        m = re.match(r'^\s*([-\d.]+)\s*,\s*([-\d.]+)\s*$', (p.get('location') or '').strip())
        if m:
            try:
                lat, lng = float(m.group(1)), float(m.group(2))
            except (ValueError, TypeError):
                pass
    # API sometimes sends total_plot_size null and uses plot_size_value + total_plot_size_unit
    total_plot_size = _f(p.get('total_plot_size'))
    if total_plot_size is None and p.get('total_plot_size_unit') == 'square_yard':
        total_plot_size = _f(p.get('plot_size_value'))
    # price_per_square_yard can be null when price_value + price_per_unit (square_yard) are used
    price_per_sqyd = _f(p.get('price_per_square_yard'))
    if price_per_sqyd is None and (p.get('price_per_unit') or p.get('price_unit')) == 'square_yard':
        price_per_sqyd = _f(p.get('price_value'))
    out = {
        'payload': item,
        'status': _str_trunc(p.get('status'), 20),
        'location': _str_trunc(p.get('location'), 200),
        'deal_type': _str_trunc(p.get('deal_type'), 50),
        'total_plot_size': total_plot_size,
        'total_price': _f(p.get('total_price')),
        'price_per_square_yard': price_per_sqyd,
        'created_at': _dt(p.get('created_at')),
        'updated_at': _dt(p.get('updated_at')),
        'exposure_type': _str_trunc(p.get('exposure_type'), 20),
        'marker_title': _str_trunc(p.get('marker_title'), 500),
        'description': _str_trunc(p.get('description'), 10000),
        'lgd_slug': _str_trunc(p.get('lgd_slug'), 500),
    }
    pt = _point_from_lat_lng(lat, lng)
    if pt is not None:
        out['location_point'] = pt
    out.update(plot_order_metrics(out.get('total_price'), out.get('total_plot_size')))
    return out
