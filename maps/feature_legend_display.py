"""
Legend strings, CRZ property trimming, and masterplan fill-color SVG helpers.

Used by coordinate-search / GeoJSON paths in views and by feature_display for
enrichment. Lives outside views.py so callers avoid importing the full views module.
"""
import json
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
    'amaravati_inner_ring_road',
    'amaravati_outer_ring_road',
    'amaravati_anantapur_greenfield_expressway',
    'amaravati_seed_access_road',
    'mancherial_warangal_expressway',
    'amroor_jagitial_mancherial_expressway',
    'badvel_nellore_highway',
    'bengaluru_vijaywada_expressway',
    'chennai_peripheral_ring_road',
    'chennai_port_maduravoyal_expressway',
    'thatchoor_chittoor_expressway',
    'urukunnu_kadampattukonam_economic_corridor',
    'ahilyanagar_akalkot_expresssway',
    'warangal_khammam_expressway',
    'khammam_vijaywada_expressway',
    'atal_progressway',
    'lucknow_kanpur_expressway',
    'varanasi_kolkata_expressway',
    'ambala_shamli_expressway',
    'ayodhya_ring_road',
    'prayagraj_ring_road',
    'ganga_expressway',
    'kanpur_ring_road',
    'kanpur_kabrai_highway',
    'agra_gwalior_expressway',
    'gorakhpur_siliguri_expressway',
    'ghazipur_ballia_expressway',
    # set30 line-styled roads
    'sardar_patel_ring_road',
    'sohna_elevated_road',
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


def is_default_highway_style_road_layer_slug(slug: str) -> bool:
    """
    True for road / expressway / corridor line layers not explicitly listed in
    HIGHWAY_INFRASTRUCTURE_POPUP_SLUGS (e.g. amaravati_inner_ring_road). Drives the
    same legend popup and black swatch as named highway layers.
    """
    s = (slug or '').strip().lower()
    if not s or s in HIGHWAY_INFRASTRUCTURE_POPUP_SLUGS:
        return False
    if 'metro' in s or 'railway' in s:
        return False
    if ('masterplan' in s or 'master_plan' in s) and 'roads' not in s:
        return False
    return any(
        k in s
        for k in (
            'road',
            'highway',
            'expressway',
            'corridor',
            'bridge',
            'sea_link',
            'sea-link',
            'rrr',
        )
    )


# Masterplan-style airport boundaries: GeoJSON carries `fill`; do not use highway black swatch.
AIRPORT_POLYGON_FILL_FROM_GEOJSON_SLUGS = frozenset({
    'new_parandur_airport',
    'new_purandar_airport_spa',
    'new_purandar_airport',
    'navi_mumbai_international_airport',
})


def fill_hex_from_geojson_properties_for_legend(properties):
    """Hex for legend swatch: prefer GeoJSON polygon ``fill``, then fill_color / HEX."""
    if not isinstance(properties, dict):
        return ''
    for key in ('fill', 'fill_color', 'fillColor', 'FillColor', 'HEX', 'Hex'):
        val = properties.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ''


# data/set31 — ArcGIS exports with ``Layer Name`` + ``fill_color`` / ``HEX`` (same as Bengaluru 2015).
# Haryana Panchkula layers: haryana/panchkula/{layer_slug}
SET31_LAYER_NAME_POPUP_MASTERPLAN_SLUGS = frozenset({
    'jammu_masterplan',
    'panchkula_extension_2_alipur_masterplan',
    'kot_behla_masterplan',
    'mansa_devi_complex_masterplan',
})

LAYER_NAME_POPUP_MASTERPLAN_SLUGS = frozenset({
    'bengaluru_master_plan_2015',
}) | SET31_LAYER_NAME_POPUP_MASTERPLAN_SLUGS


def layer_name_popup_text_from_geojson_properties(properties, fallbacks=None):
    """
    Short popup label for ArcGIS-style masterplans: ``Layer Name`` (or ``Landuse``),
    then zone_subcategory / feature_name from processed feature metadata.
    """
    if not isinstance(properties, dict):
        properties = {}
    fallbacks = fallbacks if isinstance(fallbacks, dict) else {}
    for key in ('Layer Name', 'Landuse'):
        val = properties.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    for key in ('zone_subcategory', 'feature_name'):
        val = fallbacks.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ''


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


def _is_empty_geojson_property_value(val):
    if val is None:
        return True
    if isinstance(val, str) and not val.strip():
        return True
    if isinstance(val, (list, dict)) and len(val) == 0:
        return True
    return False


def _format_geojson_property_value(val):
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    if isinstance(val, bool):
        return 'true' if val else 'false'
    if isinstance(val, float) and val != val:  # NaN
        return ''
    if isinstance(val, str):
        return val.strip()
    return str(val)


IAF_AIR_FUNNEL_ZONES_SLUG_PREFIX = 'iaf_air_funnel_zones_'

# Map paint / legend keys omitted from coordinate-search `data` for set32 IAF air funnel layers.
IAF_AIR_FUNNEL_POPUP_SKIP_KEYS = frozenset({
    'colour', 'hex', 'fill_color', 'fillcolor', 'color', 'stroke', 'fill',
})


def _is_iaf_air_funnel_zones_slug(slug):
    return bool(slug) and str(slug).startswith(IAF_AIR_FUNNEL_ZONES_SLUG_PREFIX)


def _iaf_air_funnel_zones_popup_text(properties):
    """
    Comma-separated popup for set32 IAF air funnel GeoJSON (e.g. iaf_air_funnel_zones_patna).
    Omits Colour, HEX, fill_color and other map paint keys; fill_color SVG is returned separately.
    """
    if not isinstance(properties, dict):
        return ''
    parts = []
    for key in sorted(properties.keys(), key=lambda k: str(k)):
        sk = str(key).strip() if key is not None else ''
        if not sk or sk.lower() in IAF_AIR_FUNNEL_POPUP_SKIP_KEYS:
            continue
        val = properties[key]
        if _is_empty_geojson_property_value(val):
            continue
        formatted = _format_geojson_property_value(val)
        if not formatted:
            continue
        parts.append(f'{sk}: {formatted}')
    return ', '.join(parts)


def _generic_geojson_properties_popup_text(properties):
    """
    Multiline popup from arbitrary feature.properties: each non-empty key as "Key: value".
    New GeoJSON keys need no code change. Dict/list values are JSON-encoded on one line.
    """
    if not isinstance(properties, dict):
        return ''
    lines = []
    for key in sorted(properties.keys(), key=lambda k: str(k)):
        val = properties[key]
        if _is_empty_geojson_property_value(val):
            continue
        formatted = _format_geojson_property_value(val)
        if not formatted:
            continue
        sk = str(key).strip() if key is not None else ''
        if not sk:
            continue
        lines.append(f'{sk}: {formatted}')
    return '\n'.join(lines)


def _is_transit_route_proposed_geojson(properties):
    """
    True for KML/Google-export style metro route features: Name + Connecting Points
    plus structured fields (phase / length_km / stations) as in e.g. vijayawada_metro_actual.geojson.
    Used so these layers are not reduced to highway-only legend lines (ROW/lanes).
    """
    if not isinstance(properties, dict):
        return False
    if not str(properties.get('Name', '')).strip():
        return False
    if not str(properties.get('Connecting Points', '')).strip():
        return False
    if properties.get('phase') is not None and str(properties.get('phase', '')).strip():
        return True
    if properties.get('length_km') is not None:
        return True
    if properties.get('stations') is not None:
        return True
    return False


def _transit_route_proposed_geojson_popup_text(properties):
    """
    Human-readable multiline popup for proposed metro/LRT route GeoJSON:
    Name, connects, phase, length, station count, route mode (properties['type']), status.
    Omits empty fields. Does not echo map paint keys (color, stroke, stroke-width).
    """
    if not isinstance(properties, dict):
        properties = {}
    lines = []
    name = properties.get('Name')
    if name is not None and str(name).strip():
        lines.append(f"Name: {str(name).strip()}")
    cp = properties.get('Connecting Points')
    if cp is not None and str(cp).strip():
        lines.append(f"Connects: {str(cp).strip()}")
    phase = properties.get('phase')
    if phase is not None and str(phase).strip():
        lines.append(f"Phase: {str(phase).strip()}")
    length_km = properties.get('length_km')
    if length_km is not None and str(length_km).strip() != '':
        try:
            lines.append(f"Length: {float(length_km)} km")
        except (TypeError, ValueError):
            lines.append(f"Length: {length_km} km")
    stations = properties.get('stations')
    if stations is not None and str(stations).strip() != '':
        lines.append(f"Stations: {stations}")
    mode = properties.get('type')
    if mode is not None and str(mode).strip():
        lines.append(f"Route type: {str(mode).strip()}")
    status = properties.get('status') or properties.get('Status')
    if status is not None and str(status).strip():
        lines.append(f"Status: {str(status).strip()}")
    return '\n'.join(lines)


def _vijayawada_metro_lrt_coordinate_search_popup_text(properties):
    """
    Coordinate-search `data` for layer vijayawada_metro_lrt only:
    Name, Connecting Points, Status, Length (from length_km). Omits other transit fields.
    """
    if not isinstance(properties, dict):
        properties = {}
    lines = []
    name = properties.get('Name')
    if name is not None and str(name).strip():
        lines.append(f"Name: {str(name).strip()}")
    cp = properties.get('Connecting Points')
    if cp is not None and str(cp).strip():
        lines.append(f"Connecting Points: {str(cp).strip()}")
    status = properties.get('status') or properties.get('Status')
    if status is not None and str(status).strip():
        lines.append(f"Status: {str(status).strip()}")
    length_km = properties.get('length_km')
    if length_km is not None and str(length_km).strip() != '':
        try:
            lines.append(f"Length: {float(length_km)} km")
        except (TypeError, ValueError):
            lines.append(f"Length: {length_km} km")
    return '\n'.join(lines)


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
    if _lane_configuration_omit_from_legend(lanes):
        lanes = properties.get('Lanes')
    if not _lane_configuration_omit_from_legend(lanes):
        lines.append(f'Lane Configuration: {str(lanes).strip()}')
    cp = properties.get('Connecting Points') or properties.get('Cntg_Pts')
    if cp is not None and str(cp).strip():
        lines.append(f'Connects: {str(cp).strip()}')
    length_val = properties.get('Length')
    if length_val is not None and str(length_val).strip():
        lines.append(f'Length: {str(length_val).strip()}')
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
