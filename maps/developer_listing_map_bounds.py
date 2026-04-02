"""
Developer listing map: recommended zoom from bbox area and bounds tightening for fitBounds.

Clients often call map.fitBounds(bounds) while also using zoom.recommended. A loose union
bbox makes fitBounds zoom out (~13–14) even when recommended is 16–17. Tightening to a
mercantile tile window at the recommended zoom aligns the bbox with typical fitBounds results.
"""
from __future__ import annotations

import mercantile


def recommended_zoom_from_area(area: float) -> int:
    if area < 0.0001:
        return 18
    if area < 0.001:
        return 17
    if area < 0.01:
        return 17
    if area < 0.1:
        return 16
    return 12


def mercantile_viewport_wsen(
    center_lng: float, center_lat: float, zoom: int, tile_radius: int = 2
) -> tuple[float, float, float, float]:
    """Union of (2*tile_radius+1)^2 tile bounds in WGS84 at zoom around center."""
    z = max(0, min(int(zoom), 30))
    t = mercantile.tile(float(center_lng), float(center_lat), z)
    max_xy = 2**z
    west = south = float("inf")
    east = north = float("-inf")
    for dx in range(-tile_radius, tile_radius + 1):
        for dy in range(-tile_radius, tile_radius + 1):
            x, y = t.x + dx, t.y + dy
            if x < 0 or y < 0 or x >= max_xy or y >= max_xy:
                continue
            b = mercantile.bounds(mercantile.Tile(x=x, y=y, z=z))
            west = min(west, b.west)
            south = min(south, b.south)
            east = max(east, b.east)
            north = max(north, b.north)
    return west, south, east, north


def _intersect_wsen(
    w1: float, s1: float, e1: float, n1: float, w2: float, s2: float, e2: float, n2: float
) -> tuple[float, float, float, float] | None:
    w, s = max(w1, w2), max(s1, s2)
    e, n = min(e1, e2), min(n1, n2)
    if w >= e or s >= n:
        return None
    return w, s, e, n


def tighten_bounds_for_map_fit(
    west: float,
    south: float,
    east: float,
    north: float,
    recommended_zoom: int,
    *,
    min_zoom_to_tighten: int = 15,
    tile_radius: int = 2,
) -> tuple[float, float, float, float]:
    """
    If recommended zoom is high, replace bbox with intersection of data extent and a
    mercantile viewport at that zoom (center = data center). Preserves small parcels
    unchanged when already smaller than the viewport.
    """
    if recommended_zoom < min_zoom_to_tighten:
        return west, south, east, north

    center_lng = (west + east) / 2
    center_lat = (south + north) / 2
    vw, vs, ve, vn = mercantile_viewport_wsen(center_lng, center_lat, recommended_zoom, tile_radius)
    inter = _intersect_wsen(west, south, east, north, vw, vs, ve, vn)
    if inter is None:
        return west, south, east, north
    return inter
