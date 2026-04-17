"""
Shared logic for feature "data" and "fill_color" display (CoordinateSearchTestView-style).
Used by enrichment API so layer enrichment returns the same data string and distance.
"""
from urllib.parse import quote

from .feature_legend_display import (
    HIGHWAY_INFRASTRUCTURE_POPUP_SLUGS,
    _highway_infra_legend_popup_text,
)

# SVG template for fill color indicator (same as feature_legend_display.MASTERPLAN_FILL_COLOR_SVG)
_FILL_COLOR_SVG = (
    '<svg width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">'
    '<rect x="0" y="0" width="16" height="16" rx="4" ry="4" fill="{color}"/>'
    '</svg>'
)


def _fill_color_svg_data_uri(hex_color):
    if not hex_color:
        return ''
    svg_str = _FILL_COLOR_SVG.format(color=hex_color)
    return f"data:image/svg+xml,{quote(svg_str)}"


def _get_fill_color(properties):
    if not properties:
        return ''
    return (
        properties.get('fill_color') or properties.get('fillColor') or
        properties.get('FillColor') or properties.get('color')
    ) or ''


def get_feature_display_data(layer, feature):
    """
    Return {"data": str, "fill_color": str} for a GeoFeature in a DataLayer,
    matching the format used by CoordinateSearchTestView (same human-readable
    "data" string and fill_color SVG data URI per layer type).

    layer: DataLayer instance
    feature: GeoFeature instance (with .properties, .name, .plot_category, etc.)
    """
    if not layer or not feature:
        return {'data': '', 'fill_color': ''}
    props = getattr(feature, 'properties', None) or {}
    slug = getattr(layer, 'slug', '') or ''
    layer_name = getattr(layer, 'name', None) or ''
    fill_color = _get_fill_color(props)
    fill_uri = _fill_color_svg_data_uri(fill_color)

    if slug in HIGHWAY_INFRASTRUCTURE_POPUP_SLUGS:
        return {
            'data': _highway_infra_legend_popup_text(props),
            'fill_color': _fill_color_svg_data_uri('#000000'),
        }

    # hyderabad_masterplan
    if slug == 'hyderabad_masterplan':
        name = props.get('Name', '')
        return {'data': name, 'fill_color': fill_uri}

    # amaravati_master_plan
    if slug == 'amaravati_master_plan':
        feature_name = (
            (feature.name if getattr(feature, 'name', None) else '') or
            (getattr(feature, 'plot_category', None) or '') or
            props.get('symbology') or props.get('plot_categ') or
            props.get('Name') or props.get('name', '') or
            'Unknown'
        )
        return {'data': feature_name, 'fill_color': fill_uri}

    # hyderabad_future_city
    if slug == 'hyderabad_future_city':
        name = props.get('Name', '') or 'Unknown'
        return {'data': name, 'fill_color': fill_uri}

    # hyderabad_hmda_extended_area
    if slug == 'hyderabad_hmda_extended_area':
        return {'data': layer_name, 'fill_color': fill_uri}

    # air funnel zones
    air_funnel_slugs = [
        'bhubaneswar_air_funnel_zones', 'bengaluru_air_funnel_zones', 'hyderabad_air_funnel_zones',
        'kozhikode_air_funnel_zones', 'ayodhya_air_funnel_zones', 'raipur_air_funnel_zones',
        'ahmedabad_air_funnel_zones', 'warangal_air_funnel_zones', 'nagpur_air_funnel_zones',
        'bhubaneshwar_air_funnel_zones', 'chennai_air_funnel_zones', 'delhi_air_funnel_zones',
        'diu_air_funnel_zones', 'dholera_air_funnel_zones', 'guwahati_air_funnel_zones',
        'jaipur_air_funnel_zones', 'tirupati_air_funnel_zones', 'kochi_air_funnel_zones',
        'lucknow_air_funnel_zones', 'mumbai_air_funnel_zones', 'noida_air_funnel_zones',
        'patna_air_funnel_zones', 'raigarh_air_funnel_zones',
    ]
    if slug in air_funnel_slugs:
        height_value = props.get('Pemissible Height', '') or props.get('Permissible Height', '')
        data_str = f"Permissible Height : {height_value}" if height_value else "Permissible Height : "
        return {'data': data_str, 'fill_color': fill_uri}

    # heritage sites
    if slug in ['hyderabad_heritage_sites', 'bengaluru_heritage_sites']:
        mon_name = props.get('mon_name', '')
        boundary_type = props.get('boundary_type', '')
        data_string = f"{mon_name}, {boundary_type}".strip()
        return {'data': data_string, 'fill_color': fill_uri}

    # BMRDA / many masterplans: just layer slug
    bmrda_like = [
        'bengaluru_anekal_masterplan', 'bengaluru_chikkaballapura_masterplan', 'bengaluru_hosakote_masterplan',
        'bengaluru_nelamangala_masterplan', 'coimbatore_master_plan', 'hosur_master_plan', 'kochi_master_plan',
        'chennai_master_plan', 'tirupati_masterplan', 'cuttack_masterplan', 'vgtm_masterplan', 'kakinada_masterplan',
        'mandideep_masterplan', 'ajmer_masterplan', 'pithampur_masterplan', 'bhopal_masterplan',
        'varanasi_masterplan', 'ahmedabad_masterplan', 'vadodara_masterplan', 'gift_city_masterplan',
        'mohali_sas_nagar_masterplan', 'daman_and_diu_masterplan', 'patna_masterplan', 'ayodhya_masterplan',
        'lucknow_masterplan', 'srinagar_masterplan', 'guwahati_masterplan', 'dadra_and_nagar_haveli_masterplan',
        'kannur_masterplan', 'kollam_masterplan', 'kozhikode_masterplan', 'mumbai_masterplan',
        'pune_city_pmc_masterplan', 'pimpri_chinchwad_masterplan', 'pmrda-masterplan-pmrda_masterplan', 'nagpur_masterplan',
    ]
    if slug in bmrda_like:
        return {'data': slug, 'fill_color': fill_uri}

    # bengaluru_master_plan_2015
    if slug == 'bengaluru_master_plan_2015':
        layer_name_val = props.get('Layer Name', '')
        return {'data': layer_name_val, 'fill_color': fill_uri}

    # warangal_master_plan
    if slug == 'warangal_master_plan':
        layer_val = props.get('PLU_NAME', '') or props.get('PLU', '')
        return {'data': layer_val, 'fill_color': fill_uri}

    # gurugram_masterplan
    if slug == 'gurugram_masterplan':
        layer_val = props.get('LAYER', '')
        return {'data': layer_val, 'fill_color': fill_uri}

    # delhi_masterplan
    if slug == 'delhi_masterplan':
        name = props.get('NAME', '')
        return {'data': name, 'fill_color': fill_uri}

    # bengaluru_strr
    if slug == 'bengaluru_strr':
        notation = props.get('Notation', '')
        current_status = props.get('Current_St', '')
        data_string = f"{notation}, Status: {current_status}"
        return {'data': data_string, 'fill_color': fill_uri}

    # bengaluru_metro
    if slug == 'bengaluru_metro':
        linecolour = props.get('linecolour', '')
        name = props.get('Name ', '') or props.get('Name', '')
        remarks = props.get('remarks', '')
        line_name = f"{linecolour} Line" if linecolour else "Line"
        data_string = f"{line_name}, {name}, Status: {remarks}"
        return {'data': data_string, 'fill_color': fill_uri}

    # hyderabad_metro
    if slug == 'hyderabad_metro':
        name = props.get('name', '')
        status = props.get('Status', '')
        linecolour = props.get('linecolour', '')
        from_junct = props.get('from_junct', '')
        to_junct = props.get('to_junct', '')
        route_parts = []
        if from_junct:
            route_parts.append(from_junct)
        if to_junct:
            if route_parts:
                route_parts.append('to')
            route_parts.append(to_junct)
        route = ' '.join(route_parts)
        parts = [p for p in [name, f"Status: {status}" if status else None, linecolour, route] if p]
        data_string = ', '.join(parts)
        return {'data': data_string, 'fill_color': fill_uri}

    # bengaluru_highways, hyderabad_highways
    if slug in ('bengaluru_highways', 'hyderabad_highways'):
        name = props.get('Name', '')
        notation = props.get('Notation', '')
        data_string = f"{name}, {notation}"
        return {'data': data_string, 'fill_color': fill_uri}

    # hyderabad_rrr
    if slug == 'hyderabad_rrr':
        notation = props.get('Notation', '')
        alignment = props.get('Alignment', '')
        proposed_notation = f"Proposed {notation}" if notation else "Proposed"
        data_string = f"{proposed_notation}, Status: {alignment}"
        return {'data': data_string, 'fill_color': fill_uri}

    # hyderabad_ratan_tata_road
    if slug == 'hyderabad_ratan_tata_road':
        name = props.get('Name', '')
        return {'data': name, 'fill_color': fill_uri}

    # visakhapatnam
    if slug in ('visakhapatnam_master_plan', 'visakhapatnam_masterplan'):
        category = props.get('Category', '')
        return {'data': category, 'fill_color': fill_uri}

    # Generic: feature name or properties Name/name or layer name
    data = (
        (feature.name if getattr(feature, 'name', None) else '') or
        props.get('Name', '') or
        props.get('name', '') or
        layer_name or
        'Unknown'
    )
    return {'data': data or 'Unknown', 'fill_color': fill_uri}
