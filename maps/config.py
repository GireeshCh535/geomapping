# maps/config.py
"""
Clean configuration for Karnataka Bengaluru layers only
Contains layer definitions with specific colors for master plan, highways, metro, and workspaces
"""

from django.contrib.gis.geos import GEOSGeometry
import json

# ================================
# LAYER CATEGORY MAPPINGS
# ================================

LAYER_CATEGORIES = {
    'AGRICULTURAL': {
        'name': 'Agricultural',
        'description': 'Agricultural and farming areas',
        'default_color': '#9DC1CB',
        'default_opacity': 0.7
    },
    'COMMERCIAL': {
        'name': 'Commercial',
        'description': 'Commercial and business areas',
        'default_color': '#73B2FF',
        'default_opacity': 0.7
    },
    'GOVERNMENT': {
        'name': 'Government',
        'description': 'Government and public facilities',
        'default_color': '#E60000',
        'default_opacity': 0.7
    },
    'INDUSTRIAL': {
        'name': 'Industrial',
        'description': 'Industrial and manufacturing areas',
        'default_color': '#AA66B2',
        'default_opacity': 0.7
    },
    'RESIDENTIAL': {
        'name': 'Residential',
        'description': 'Residential areas',
        'default_color': '#FFEBAF',
        'default_opacity': 0.7
    },
    'TRANSPORT': {
        'name': 'Transport',
        'description': 'Transportation infrastructure',
        'default_color': '#828282',
        'default_opacity': 0.7
    },
    'WATER_BODIES': {
        'name': 'Water Bodies',
        'description': 'Lakes, tanks, drains, and water features',
        'default_color': '#BEE8FF',
        'default_opacity': 0.7
    },
    'PARKS_GREEN': {
        'name': 'Parks & Green Spaces',
        'description': 'Parks, playgrounds, and green spaces',
        'default_color': '#98E600',
        'default_opacity': 0.7
    },
    'UTILITIES': {
        'name': 'Utilities',
        'description': 'Power, water, and utility facilities',
        'default_color': '#D79E9E',
        'default_opacity': 0.7
    },
    'PROTECTED': {
        'name': 'Protected Areas',
        'description': 'Protected forests and conservation areas',
        'default_color': '#70A800',
        'default_opacity': 0.7
    },
    'UNCLASSIFIED': {
        'name': 'Unclassified',
        'description': 'Unclassified land use',
        'default_color': '#E1E1E1',
        'default_opacity': 0.7
    }
}

# ================================
# BENGALURU LAYER CONFIGURATIONS
# ================================

# Master Plan Layers (FLEXIBLE PATTERNS to find your 16 files)
BENGALURU_MASTER_PLAN_LAYERS = {
    'Agricultural_Land': {
        'name': 'Agricultural Land',
        'color': '#9DC1CB',
        'category': 'AGRICULTURAL',
        'file_pattern': '*gricultural*.json',  # Flexible pattern
        'description': 'Agricultural and farming lands'
    },
    'CommercialBusiness': {
        'name': 'Commercial Business',
        'color': '#73B2FF',
        'category': 'COMMERCIAL',
        'file_pattern': 'Commercial_Business_.json',
        'description': 'Commercial business areas'
    },
    'CommercialCentral': {
        'name': 'Commercial Central',
        'color': '#004DA8',
        'category': 'COMMERCIAL',
        'file_pattern': 'Commercial_Central_.json',
        'description': 'Central commercial districts'
    },
    'Defense': {
        'name': 'Defense',
        'color': '#E0B8FC',
        'category': 'GOVERNMENT',
        'file_pattern': 'Defense.json',
        'description': 'Defense establishments'
    },
    'Drains': {
        'name': 'Drains',
        'color': '#267300',
        'category': 'WATER_BODIES',
        'file_pattern': 'Drains.json',
        'description': 'Drainage systems and channels'
    },
    'HighTech': {
        'name': 'High Tech',
        'color': '#C29ED7',
        'category': 'INDUSTRIAL',
        'file_pattern': 'HighTech.json',
        'description': 'High-tech industrial areas'
    },
    'Industrial': {
        'name': 'Industrial',
        'color': '#AA66B2',
        'category': 'INDUSTRIAL',
        'file_pattern': 'Industrial.json',
        'description': 'Industrial zones'
    },
    'Lake_Tank': {
        'name': 'Lakes & Tanks',
        'color': '#BEE8FF',
        'category': 'WATER_BODIES',
        'file_pattern': 'Lake_Tank.json',
        'description': 'Lakes, tanks, and water bodies'
    },
    'Parks_GreenSpaces_Sports_Playgrounds_Cemetery_BurialGrounds': {
        'name': 'Parks & Green Spaces',
        'color': '#98E600',
        'category': 'PARKS_GREEN',
        'file_pattern': 'Parks_GreenSpaces_Sports_Playgrounds_Cemetery_BurialGrounds.json',
        'description': 'Parks, green spaces, sports facilities, and cemeteries'
    },
    'Power_Water_GarbageFacility_TreatmentPlant': {
        'name': 'Utilities & Infrastructure',
        'color': '#D79E9E',
        'category': 'UTILITIES',
        'file_pattern': 'Power_Water_GarbageFacility_TreatmentPlant.json',
        'description': 'Power, water, and waste treatment facilities'
    },
    'Public_SemiPublic': {
        'name': 'Public & Semi-Public',
        'color': '#E60000',
        'category': 'GOVERNMENT',
        'file_pattern': 'Public_SemiPublic.json',
        'description': 'Public and semi-public facilities'
    },
    'ResidentialMain': {
        'name': 'Residential Main',
        'color': '#FFEBAF',
        'category': 'RESIDENTIAL',
        'file_pattern': 'Residential_Main_.json',
        'description': 'Primary residential areas'
    },
    'ResidentialMixed': {
        'name': 'Residential Mixed',
        'color': '#FFC400',
        'category': 'RESIDENTIAL',
        'file_pattern': 'Residential_Mixed_.json',
        'description': 'Mixed residential areas'
    },
    'Road_Rail_Airport_Transport': {
        'name': 'Transport Infrastructure',
        'color': '#828282',
        'category': 'TRANSPORT',
        'file_pattern': 'Road_Rail_Airport_Transport.json',
        'description': 'Roads, railways, airports, and transport infrastructure'
    },
    'StateForest_ValleyProtectedLand': {
        'name': 'Protected Forest & Valley',
        'color': '#70A800',
        'category': 'PROTECTED',
        'file_pattern': 'StateForest_Valley_ProtectedLand_.json',
        'description': 'State forests and protected valley lands'
    },
    'Unclassified_Use': {
        'name': 'Unclassified Use',
        'color': '#E1E1E1',
        'category': 'UNCLASSIFIED',
        'file_pattern': 'Unclassified_Use.json',
        'description': 'Unclassified land use areas'
    }
}

# Highway Layers (from your paste.txt)
BENGALURU_HIGHWAY_LAYERS = {
    'BellaryRoad_NH44': {
        'name': 'Bellary Road (NH-44)',
        'color': '#FF6B35',
        'category': 'TRANSPORT',
        'file_pattern': 'BellaryRoad_NH44.geojson',
        'description': 'National Highway 44 - Bellary Road'
    },
    'BengaluruChennaiExpressway_NE7': {
        'name': 'Bengaluru-Chennai Expressway (NE-7)',
        'color': '#F7931E',
        'category': 'TRANSPORT',
        'file_pattern': 'BengaluruChennaiExpressway_NE7.geojson',
        'description': 'Bengaluru to Chennai Expressway'
    },
    'BengaluruMysuruRoad_NH275': {
        'name': 'Bengaluru-Mysuru Road (NH-275)',
        'color': '#FFD700',
        'category': 'TRANSPORT',
        'file_pattern': 'BengaluruMysuruRoad_NH275.geojson',
        'description': 'National Highway 275 - Bengaluru to Mysuru Road'
    },
    'HosurRoad_NH48': {
        'name': 'Hosur Road (NH-48)',
        'color': '#32CD32',
        'category': 'TRANSPORT',
        'file_pattern': 'HosurRoad_NH48.geojson',
        'description': 'National Highway 48 - Hosur Road'
    },
    'KanakpuraRoad_NH948': {
        'name': 'Kanakpura Road (NH-948)',
        'color': '#1E90FF',
        'category': 'TRANSPORT',
        'file_pattern': 'KanakpuraRoad_NH948.geojson',
        'description': 'National Highway 948 - Kanakpura Road'
    },
    'MadrasRoad_NH75': {
        'name': 'Madras Road (NH-75)',
        'color': '#8A2BE2',
        'category': 'TRANSPORT',
        'file_pattern': 'MadrasRoad_NH75.geojson',
        'description': 'National Highway 75 - Madras Road'
    },
    'NICE_Road': {
        'name': 'NICE Road',
        'color': '#DC143C',
        'category': 'TRANSPORT',
        'file_pattern': 'NICE_Road.geojson',
        'description': 'Nandi Infrastructure Corridor Enterprises Road'
    },
    'STRR': {
        'name': 'Satellite Town Ring Road (STRR)',
        'color': '#FF1493',
        'category': 'TRANSPORT',
        'file_pattern': 'STRR.geojson',
        'description': 'Satellite Town Regional Ring Road'
    },
    'TumakuruRoad_NH48': {
        'name': 'Tumakuru Road (NH-48)',
        'color': '#00CED1',
        'category': 'TRANSPORT',
        'file_pattern': 'TumakuruRoad_NH48.geojson',
        'description': 'National Highway 48 - Tumakuru Road'
    }
}

# Metro Layers
BENGALURU_METRO_LAYERS = {
    'metro_lines': {
        'name': 'Bengaluru Metro Lines',
        'color': '#0066CC',
        'category': 'TRANSPORT',
        'file_pattern': '*.geojson',
        'description': 'Bengaluru Metro Phases 1, 2, 2A & 2B'
    }
}

# Workspace/Industrial Areas
BENGALURU_WORKSPACE_LAYERS = {
    'industrial_areas': {
        'name': 'Industrial Areas & Workspaces',
        'color': '#8B4513',
        'category': 'INDUSTRIAL',
        'file_pattern': 'Blr_Industrial_Area_processed.geojson',
        'description': 'Industrial areas and business workspaces'
    }
}

# ================================
# BENGALURU LAYER GROUPS
# ================================

BENGALURU_LAYER_GROUPS = {
    'master_plan': {
        'name': 'Master Plan 2015',
        'description': 'Bengaluru Master Plan 2015 - Land Use Categories',
        'display_order': 1,
        'layers': BENGALURU_MASTER_PLAN_LAYERS
    },
    'highways': {
        'name': 'Highways & Major Roads',
        'description': 'National highways and major road network',
        'display_order': 2,
        'layers': BENGALURU_HIGHWAY_LAYERS
    },
    'metro': {
        'name': 'Metro Network',
        'description': 'Bengaluru Metro rail network',
        'display_order': 3,
        'layers': BENGALURU_METRO_LAYERS
    },
    'workspaces': {
        'name': 'Industrial Workspaces',
        'description': 'Industrial areas and business workspaces',
        'display_order': 4,
        'layers': BENGALURU_WORKSPACE_LAYERS
    }
}

# ================================
# CITY CONFIGURATIONS
# ================================

CITY_CONFIGS = {
    'bengaluru': {
        'city_info': {
            'name': 'Bengaluru',
            'slug': 'bengaluru',
            'state_ref_id': None,  # Will be set when state is created
            'description': 'Silicon Valley of India - Garden City',
            'center_lat': 12.9716,
            'center_lng': 77.5946,
            'zoom_level': 11
        },
        'layer_groups': BENGALURU_LAYER_GROUPS,
        'coordinate_precision': 8,
        'default_colors': {
            'AGRICULTURAL': '#9DC1CB',
            'COMMERCIAL': '#73B2FF', 
            'GOVERNMENT': '#E60000',
            'INDUSTRIAL': '#AA66B2',
            'RESIDENTIAL': '#FFEBAF',
            'TRANSPORT': '#828282',
            'WATER_BODIES': '#BEE8FF',
            'PARKS_GREEN': '#98E600',
            'UTILITIES': '#D79E9E',
            'PROTECTED': '#70A800',
            'UNCLASSIFIED': '#E1E1E1'
        }
    }
}

# Alternative slug for Bengaluru
CITY_CONFIGS['bangalore'] = CITY_CONFIGS['bengaluru']

# ================================
# STATE CONFIGURATIONS  
# ================================

STATE_CONFIGS = {
    'karnataka': {
        'name': 'Karnataka',
        'code': 'KA',
        'cities': ['bengaluru']
    }
}

# ================================
# HELPER FUNCTIONS
# ================================

def get_city_config(city_slug):
    """Get configuration for a specific city"""
    return CITY_CONFIGS.get(city_slug)

def get_layer_groups_config(city_slug):
    """Get layer groups configuration for a city"""
    config = get_city_config(city_slug)
    if config:
        return config.get('layer_groups', {})
    return {}

def get_layer_config(city_slug, layer_group, layer_slug):
    """Get specific layer configuration"""
    layer_groups = get_layer_groups_config(city_slug)
    if layer_group in layer_groups:
        layers = layer_groups[layer_group].get('layers', {})
        return layers.get(layer_slug)
    return None

def get_all_layers_for_city(city_slug):
    """Get all layers across all groups for a city"""
    all_layers = {}
    layer_groups = get_layer_groups_config(city_slug)
    
    for group_name, group_config in layer_groups.items():
        layers = group_config.get('layers', {})
        for layer_slug, layer_config in layers.items():
            # Add group info to layer config
            layer_with_group = layer_config.copy()
            layer_with_group['layer_group'] = group_name
            layer_with_group['group_name'] = group_config.get('name', group_name)
            all_layers[layer_slug] = layer_with_group
    
    return all_layers

def get_layer_color(city_slug, layer_slug, layer_group=None):
    """Get color for a specific layer"""
    if layer_group:
        layer_config = get_layer_config(city_slug, layer_group, layer_slug)
    else:
        # Search all groups
        all_layers = get_all_layers_for_city(city_slug)
        layer_config = all_layers.get(layer_slug)
    
    if layer_config:
        return layer_config.get('color', '#CCCCCC')
    
    return '#CCCCCC'  # Default gray

def get_category_color(city_slug, category_code):
    """Get default color for a category in a city"""
    config = get_city_config(city_slug)
    if config and 'default_colors' in config:
        return config['default_colors'].get(category_code, '#CCCCCC')
    
    # Fallback to global category colors
    category_info = LAYER_CATEGORIES.get(category_code, {})
    return category_info.get('default_color', '#CCCCCC')

# ================================
# COMPATIBILITY FUNCTIONS
# (For existing code that might reference these)
# ================================

def get_plu_mapping(city_slug):
    """Get PLU mappings for a city (compatibility function)"""
    # For now, return empty dict since we're using layer-based approach
    # This can be enhanced later if PLU mapping is needed
    return {}

def map_plu_code_to_category(city_slug, plu_code):
    """Map PLU code to category (compatibility function)"""
    # Basic mapping - can be enhanced based on needs
    plu_lower = str(plu_code).lower() if plu_code else ""
    
    if any(term in plu_lower for term in ['residential', 'r1', 'r2', 'r3', 'r4']):
        return 'RESIDENTIAL'
    elif any(term in plu_lower for term in ['commercial', 'c1', 'c2', 'c3']):
        return 'COMMERCIAL'
    elif any(term in plu_lower for term in ['industrial', 'i1', 'i2', 'i3']):
        return 'INDUSTRIAL'
    elif any(term in plu_lower for term in ['agricultural', 'agriculture']):
        return 'AGRICULTURAL'
    elif any(term in plu_lower for term in ['transport', 'road', 'rail']):
        return 'TRANSPORT'
    elif any(term in plu_lower for term in ['water', 'lake', 'tank', 'drain']):
        return 'WATER_BODIES'
    elif any(term in plu_lower for term in ['park', 'green', 'playground']):
        return 'PARKS_GREEN'
    elif any(term in plu_lower for term in ['government', 'public']):
        return 'GOVERNMENT'
    elif any(term in plu_lower for term in ['utility', 'power', 'treatment']):
        return 'UTILITIES'
    elif any(term in plu_lower for term in ['forest', 'protected']):
        return 'PROTECTED'
    else:
        return 'UNCLASSIFIED'

def get_attribute_mapping(city_slug):
    """Get attribute mappings for a city (compatibility function)"""
    return {
        'name_field': 'name',
        'description_field': 'description',
        'area_field': 'area',
        'calculated_area': 'calculated_area',
    }

def validate_city_configuration(city_slug):
    """Validate that a city configuration is complete"""
    config = get_city_config(city_slug)
    if not config:
        return False, f"No configuration found for city: {city_slug}"
    
    required_fields = ['city_info', 'layer_groups']
    missing_fields = [field for field in required_fields if field not in config]
    
    if missing_fields:
        return False, f"Missing required configuration fields: {missing_fields}"
    
    return True, "Configuration is valid"

# Export commonly used functions for import compatibility
__all__ = [
    'CITY_CONFIGS',
    'STATE_CONFIGS',
    'LAYER_CATEGORIES',
    'get_city_config',
    'get_layer_groups_config',
    'get_layer_config',
    'get_all_layers_for_city',
    'get_layer_color',
    'get_category_color',
    'get_plu_mapping', 
    'map_plu_code_to_category',
    'get_attribute_mapping',
    'optimize_coordinates',
    'detect_data_format',
    'convert_esri_to_geojson_geometry',
    'validate_city_configuration',
]

def detect_data_format(file_path):
    """Detect data format from file extension"""
    file_path = str(file_path).lower()
    if file_path.endswith('.geojson'):
        return 'GEOJSON'
    elif file_path.endswith('.json'):
        return 'JSON'
    elif file_path.endswith('.shp'):
        return 'SHP'
    else:
        return 'GEOJSON'  # Default

def optimize_coordinates(coords, precision=8):
    """Optimize coordinate precision"""
    if isinstance(coords, list):
        return [optimize_coordinates(coord, precision) for coord in coords]
    elif isinstance(coords, (int, float)):
        return round(float(coords), precision)
    return coords

def convert_esri_to_geojson_geometry(esri_geometry):
    """Convert ESRI geometry to GeoJSON format"""
    # Basic conversion - can be enhanced based on needs
    if 'rings' in esri_geometry:
        # Polygon
        return {
            'type': 'Polygon',
            'coordinates': esri_geometry['rings']
        }
    elif 'paths' in esri_geometry:
        # LineString/MultiLineString
        paths = esri_geometry['paths']
        if len(paths) == 1:
            return {
                'type': 'LineString',
                'coordinates': paths[0]
            }
        else:
            return {
                'type': 'MultiLineString',
                'coordinates': paths
            }
    elif 'x' in esri_geometry and 'y' in esri_geometry:
        # Point
        return {
            'type': 'Point',
            'coordinates': [esri_geometry['x'], esri_geometry['y']]
        }
    
    return None