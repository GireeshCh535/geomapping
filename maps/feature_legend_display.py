"""
Legend strings, CRZ property trimming, and masterplan fill-color SVG helpers.

Used by coordinate-search / GeoJSON paths in views and by feature_display for
enrichment. Lives outside views.py so callers avoid importing the full views module.
"""
from urllib.parse import quote

# SVG template for master plan fill color indicator (use {color} placeholder)
MASTERPLAN_FILL_COLOR_SVG = (
    '<svg width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">'
    '<rect x="0" y="0" width="16" height="16" rx="4" ry="4" fill="{color}"/>'
    '</svg>'
)


def _masterplan_fill_color_svg_data_uri(hex_color):
    """Return SVG as a data URI so frontend can use in <img src={fill_color} /> without JSON escaping issues."""
    if not hex_color:
        return ''
    svg_str = MASTERPLAN_FILL_COLOR_SVG.format(color=hex_color)
    return f"data:image/svg+xml,{quote(svg_str)}"


# CRZ layers: no search buffer; order by ascending area so overlapping zones return the smallest/most specific polygon.
# 12 slugs aligned with data/crz/* (AndhraPradesh … TamilNadu). Tamil Nadu CRZ uses tamil_nadu_crz_layer, not crz_layer.
CRZ_SEARCH_LAYER_SLUGS = frozenset({
    'andhra_pradesh_crz_layer',
    'diu_crz_layers',
    'gujarat_crz_layer',
    'karaikal_crz_layer',
    'karnataka_crz_layer',
    'kerela_crz_layer',
    'maharashtra_crz_layer',
    'mahe_crz_layer',
    'odisha_crz_layer',
    'puducherry_crz_layer',
    'tamil_nadu_crz_layer',
    'yanam_crz_layer',
})

# Highway / economic corridor layers (plus coastal/expressway slugs in HIGHWAY_INFRASTRUCTURE_EXTRA_POPUP_SLUGS):
# coordinate-search `data` is multiline legend text — Name, Right of Way, Lane Configuration, Connects.
HIGHWAY_CORRIDOR_PROPERTY_SLUGS = frozenset({
    'mancherial_warangal_expressway',
    'amroor_jagitial_mancherial_expressway',
    'badvel_nellore_highway',
    'bengaluru_vijaywada_expressway',
    'thatchoor_chittoor_expressway',
    'urukunnu_kadampattukonam_economic_corridor',
    'ahilyanagar_akalkot_expresssway',
    'warangal_khammam_expressway',
    'khammam_vijaywada_expressway',
})

# Coastal roads, expressways, sea links, bridges, corridors — same legend popup as greenfield corridors
HIGHWAY_INFRASTRUCTURE_EXTRA_POPUP_SLUGS = frozenset({
    'kharghar_coastal_road', 'versova_bhayander_coastal_road', 'pune_ring_roads',
    'nagpur_chandrapur_expressway', 'nagpur_gondia_expressway',
    'virar_alibaug_multimodal_corridor', 'shaktipeeth_expressway',
    'madh_versova_bridge', 'uttan_virar_sea_link', 'vadhvan_tawa_connector_expressway',
    'revas_karanja_bridge', 'bandra_versova_sea_link', 'thane_coastal_road',
    'pune_bengaluru_expressway', 'konkan_expressway', 'talegaon_chakan_shikrapur_corridor',
})

HIGHWAY_INFRASTRUCTURE_POPUP_SLUGS = (
    HIGHWAY_CORRIDOR_PROPERTY_SLUGS | HIGHWAY_INFRASTRUCTURE_EXTRA_POPUP_SLUGS
)


def _lane_configuration_omit_from_legend(lanes):
    """Skip lane line in legend when missing or explicitly not specified."""
    if lanes is None:
        return True
    s = str(lanes).strip().lower()
    return s == '' or s == 'not specified'


def _format_right_of_way_for_legend(row_val):
    """Display ROW like '45m' for legend (append m when absent)."""
    if row_val is None:
        return ''
    s = str(row_val).strip()
    if not s:
        return ''
    if s.lower().endswith('m'):
        return s
    return f'{s}m'


def _highway_infra_legend_popup_text(properties):
    """
    Multiline legend popup: Name, Right of Way, Lane Configuration, Connects.
    Omits Lane Configuration when value is 'not specified'; omits empty fields.
    """
    if not isinstance(properties, dict):
        properties = {}
    lines = []
    name = properties.get('Name')
    if name is not None and str(name).strip():
        lines.append(f"Name: {str(name).strip()}")
    row_disp = _format_right_of_way_for_legend(properties.get('ROW'))
    if row_disp:
        lines.append(f'Right of Way: {row_disp}')
    lanes = properties.get('Lane Configuration')
    if not _lane_configuration_omit_from_legend(lanes):
        lines.append(f'Lane Configuration: {str(lanes).strip()}')
    cp = properties.get('Connecting Points')
    if cp is not None and str(cp).strip():
        lines.append(f'Connects: {str(cp).strip()}')
    return '\n'.join(lines)


def _filter_crz_geojson_properties(feature_data):
    """Expose only HEX, Name, Regulation Type in detailed_category.properties (all CRZ GeoJSON layers)."""
    if not isinstance(feature_data, dict):
        return
    dc = feature_data.get('detailed_category')
    if not isinstance(dc, dict):
        dc = {}
    p = dc.get('properties') if isinstance(dc.get('properties'), dict) else {}
    hex_val = p.get('HEX')
    if hex_val is None:
        hex_val = p.get('Hex')
    dc['properties'] = {
        'HEX': hex_val,
        'Name': p.get('Name'),
        'Regulation Type': p.get('Regulation Type'),
    }
    feature_data['detailed_category'] = dc


# Alias for call sites that refer to Karnataka explicitly
_filter_karnataka_crz_properties = _filter_crz_geojson_properties
