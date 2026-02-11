"""
Shared helpers for syncing Land, Plot, Developer Land and Developer Plot data
from 1acre-be API or webhook payloads into SyncedLand, SyncedPlot,
SyncedDeveloperLand, SyncedDeveloperPlot.

Used by:
  - maps.management.commands.pull_land_plot_from_api (bulk pull)
  - maps.views.LandPlotWebhookView (land/plot webhook)
  - maps.views.DeveloperListingMediaWebhookView (developer listing webhook)
"""

from django.utils.dateparse import parse_datetime


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


def defaults_for_land(item):
    """Build SyncedLand defaults from API item or webhook listing_data."""
    p = item if isinstance(item, dict) else {}
    return {
        'payload': item,
        'lat': _f(p.get('lat')),
        'long': _f(p.get('long')),
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
    }


def defaults_for_plot(item):
    """Build SyncedPlot defaults from API item or webhook listing_data."""
    p = item if isinstance(item, dict) else {}
    return {
        'payload': item,
        'lat': _f(p.get('lat')),
        'long': _f(p.get('long')),
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
    }


def defaults_for_developer_land(item):
    """Build SyncedDeveloperLand defaults from API item or webhook listing_data."""
    p = item if isinstance(item, dict) else {}
    return {
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
    }


def defaults_for_developer_plot(item):
    """Build SyncedDeveloperPlot defaults from API item or webhook listing_data."""
    p = item if isinstance(item, dict) else {}
    return {
        'payload': item,
        'status': _str_trunc(p.get('status'), 20),
        'location': _str_trunc(p.get('location'), 200),
        'deal_type': _str_trunc(p.get('deal_type'), 50),
        'total_plot_size': _f(p.get('total_plot_size')),
        'total_price': _f(p.get('total_price')),
        'price_per_square_yard': _f(p.get('price_per_square_yard')),
        'created_at': _dt(p.get('created_at')),
        'updated_at': _dt(p.get('updated_at')),
        'exposure_type': _str_trunc(p.get('exposure_type'), 20),
        'marker_title': _str_trunc(p.get('marker_title'), 500),
        'description': _str_trunc(p.get('description'), 10000),
    }
