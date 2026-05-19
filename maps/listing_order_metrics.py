"""
Denormalized ordering metrics for Synced* and LayerListingLink.

Conventions (match LayerListingLinksAPIView / product):
- Land & developer_land: total_price is lakhs; total_land_size is acres.
- Plot & developer_plot: total_price is rupees; total_plot_size is square yards.

See maps.views.listings.LayerListingLinksAPIView docstring for API ordering.
"""

from __future__ import annotations

LAKHS_TO_RUPEES = 100_000.0
SQ_YARDS_PER_ACRE = 4840.0


def land_order_metrics(total_price, total_land_size):
    """
    Return dict with order_total_price_in_lakhs, order_total_size_in_acres,
    order_price_per_acre_in_lakhs (each float or None).
    """
    out = {
        'order_total_price_in_lakhs': None,
        'order_total_size_in_acres': None,
        'order_price_per_acre_in_lakhs': None,
    }
    if total_price is not None:
        try:
            out['order_total_price_in_lakhs'] = float(total_price)
        except (TypeError, ValueError):
            pass
    if total_land_size is not None:
        try:
            out['order_total_size_in_acres'] = float(total_land_size)
        except (TypeError, ValueError):
            pass
    try:
        sz = float(total_land_size) if total_land_size is not None else None
        pr = float(total_price) if total_price is not None else None
        if sz and pr is not None and sz != 0:
            out['order_price_per_acre_in_lakhs'] = pr / sz
    except (TypeError, ValueError):
        pass
    return out


def plot_order_metrics(total_price, total_plot_size):
    """Plot/developer_plot: rupees and sq yd → lakhs and acres; price/acre in lakhs."""
    out = {
        'order_total_price_in_lakhs': None,
        'order_total_size_in_acres': None,
        'order_price_per_acre_in_lakhs': None,
    }
    if total_price is not None:
        try:
            out['order_total_price_in_lakhs'] = float(total_price) / LAKHS_TO_RUPEES
        except (TypeError, ValueError):
            pass
    if total_plot_size is not None:
        try:
            out['order_total_size_in_acres'] = float(total_plot_size) / SQ_YARDS_PER_ACRE
        except (TypeError, ValueError):
            pass
    try:
        sz = float(total_plot_size) if total_plot_size is not None else None
        pr = float(total_price) if total_price is not None else None
        if sz and pr is not None and sz != 0:
            out['order_price_per_acre_in_lakhs'] = (pr / sz) * SQ_YARDS_PER_ACRE / LAKHS_TO_RUPEES
    except (TypeError, ValueError):
        pass
    return out


def listing_order_metrics_for_synced_record(record) -> dict:
    """
    Compute order_* floats from a SyncedLand, SyncedPlot, SyncedDeveloperLand, or SyncedDeveloperPlot
    instance (uses model fields, not precomputed columns).
    """
    if hasattr(record, 'total_land_size'):
        return land_order_metrics(getattr(record, 'total_price', None), getattr(record, 'total_land_size', None))
    return plot_order_metrics(getattr(record, 'total_price', None), getattr(record, 'total_plot_size', None))


def layer_link_denormalized_order_fields(record) -> dict:
    """Payload for LayerListingLink rows: order floats + listing timestamps from a Synced* record."""
    m = listing_order_metrics_for_synced_record(record)
    return {
        **m,
        'listing_created_at': getattr(record, 'created_at', None),
        'listing_updated_at': getattr(record, 'updated_at', None),
    }
