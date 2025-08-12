# maps/config.py
"""
Complete configuration with Telangana (Hyderabad & Warangal) support
Preserves all existing Karnataka Bengaluru functionality without changes
"""

from django.contrib.gis.geos import GEOSGeometry
import json

# ================================
# LAYER CATEGORY MAPPINGS (UNCHANGED + EXTENDED)
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
    'MIXED_USE': {
        'name': 'Mixed Use',
        'description': 'Mixed land use and development areas',
        'default_color': '#FFB347',
        'default_opacity': 0.7
    },
    'BOUNDARIES': {
        'name': 'Administrative Boundaries',
        'description': 'Administrative and development authority boundaries',
        'default_color': '#FF6347',
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
# BENGALURU LAYER CONFIGURATIONS (UNCHANGED)
# ================================

# Master Plan Layers (from your paste.txt with exact colors)
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

# Highway Layer Configuration (separate STRR)
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
    'TumakuruRoad_NH48': {
        'name': 'Tumakuru Road (NH-48)',
        'color': '#00CED1',
        'category': 'TRANSPORT',
        'file_pattern': 'TumakuruRoad_NH48.geojson',
        'description': 'National Highway 48 - Tumakuru Road'
    }
}

# STRR as separate layer group (matches your folder structure)
BENGALURU_STRR_LAYERS = {
    'STRR': {
        'name': 'Satellite Town Ring Road (STRR)',
        'color': '#FF1493',
        'category': 'TRANSPORT',
        'file_pattern': 'STRR.geojson',
        'description': 'Satellite Town Regional Ring Road'
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

# Workspace/Industrial Areas (matches your "workspace" folder)
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
# BENGALURU LAYER GROUPS (UNCHANGED)
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
        'description': 'National highways and major road network (excluding STRR)',
        'display_order': 2,
        'layers': BENGALURU_HIGHWAY_LAYERS
    },
    'strr': {
        'name': 'STRR (Satellite Town Ring Road)',
        'description': 'Satellite Town Regional Ring Road',
        'display_order': 3,
        'layers': BENGALURU_STRR_LAYERS
    },
    'metro': {
        'name': 'Metro Network',
        'description': 'Bengaluru Metro rail network',
        'display_order': 4,
        'layers': BENGALURU_METRO_LAYERS
    },
    'workspace': {
        'name': 'Industrial Workspaces',
        'description': 'Industrial areas and business workspaces',
        'display_order': 5,
        'layers': BENGALURU_WORKSPACE_LAYERS
    }
}

# ================================
# NEW: HYDERABAD LAYER CONFIGURATIONS
# ================================

# Future City Development Areas (nested folder structure - FIXED to skip shapefile)
HYDERABAD_FUTURE_CITY_LAYERS = {
    'HMDA_Boundary': {
        'name': 'HMDA Boundary',
        'color': '#FF6347',
        'category': 'BOUNDARIES',
        'file_pattern': 'FCDA_Boundary_Villages/HMDA_Boundary.geojson',
        'description': 'Hyderabad Metropolitan Development Authority boundary'
    },
    'HMDA_Villages_Clip': {
        'name': 'HMDA Villages',
        'color': '#FF7F50',
        'category': 'BOUNDARIES',
        'file_pattern': 'FCDA_Boundary_Villages/HMDA_Villages_Clip.geojson',
        'description': 'HMDA village boundaries and administrative areas'
    }
    # NOTE: Removed FutureCityHyderabad_Boundary shapefile - system doesn't support shapefiles
    # If needed, convert to GeoJSON: ogr2ogr -f GeoJSON output.geojson input.shp
}

# Highway Layers
HYDERABAD_HIGHWAY_LAYERS = {
    'hyd_highways_merged': {
        'name': 'Hyderabad Highways',
        'color': '#708090',
        'category': 'TRANSPORT',
        'file_pattern': 'hyd_highways_merged.geojson',
        'description': 'Major highways including NH 163 Warangal Highway'
    }
}

# Metro Lines (metro-lines folder)
HYDERABAD_METRO_LINES_LAYERS = {
    'metro_lines': {
        'name': 'Hyderabad Metro Lines',
        'color': '#4169E1',
        'category': 'TRANSPORT', 
        'file_pattern': 'Hyd_metro_lines_ph_1*2_Final.geojson',
        'description': 'Hyderabad Metro Phase 1 & 2 lines'
    },
    'metro_stations': {
        'name': 'Hyderabad Metro Stations',
        'color': '#0000CD',
        'category': 'TRANSPORT',
        'file_pattern': 'Hyd_metro_stations_ph1*2.geojson', 
        'description': 'Hyderabad Metro Phase 1 & 2 stations'
    }
}

# Master Plan Roads (master-plan-roads folder)
HYDERABAD_MASTER_PLAN_ROADS_LAYERS = {
    'masterplan_roads': {
        'name': 'HMDA Master Plan Roads',
        'color': '#696969',
        'category': 'TRANSPORT',
        'file_pattern': 'HMDA_masterplan_roads_merged.geojson',
        'description': 'HMDA master plan proposed roads'
    }
}

# Regional Ring Road
HYDERABAD_RRR_LAYERS = {
    'regional_ring_road': {
        'name': 'Regional Ring Road (RRR)',
        'color': '#B22222',
        'category': 'TRANSPORT',
        'file_pattern': 'RRR_Final.geojson',
        'description': 'Hyderabad Regional Ring Road (North & South parts)'
    }
}

# Workspaces/SEZ
HYDERABAD_WORKSPACE_LAYERS = {
    'sez_areas': {
        'name': 'Special Economic Zones',
        'color': '#9370DB',
        'category': 'INDUSTRIAL',
        'file_pattern': 'Hyd_SEZs_Final.geojson',
        'description': 'Special Economic Zones and industrial workspaces'
    }
}

# ================================
# NEW: WARANGAL LAYER CONFIGURATIONS  
# ================================

# Warangal Master Plan (all files in master_plan folder)
WARANGAL_MASTER_PLAN_LAYERS = {
    'Agriculture': {
        'name': 'Agricultural Areas',
        'color': '#9DC1CB',
        'category': 'AGRICULTURAL',
        'file_pattern': 'Agriculture.geojson',
        'description': 'Agricultural and farming areas in Warangal'
    },
    'AirStrip': {
        'name': 'Air Strip',
        'color': '#FFB6C1',
        'category': 'TRANSPORT',
        'file_pattern': 'AirStrip.geojson',
        'description': 'Airport and airstrip facilities'
    },
    'Commercial': {
        'name': 'Commercial Areas',
        'color': '#73B2FF',
        'category': 'COMMERCIAL',
        'file_pattern': 'Commercial.geojson',
        'description': 'Commercial and business areas'
    },
    'Forest': {
        'name': 'Forest Areas',
        'color': '#228B22',
        'category': 'PROTECTED',
        'file_pattern': 'Forest.geojson',
        'description': 'Forest and protected green areas'
    },
    'GrowthCorridor': {
        'name': 'Growth Corridor',
        'color': '#FF8C00',
        'category': 'MIXED_USE',
        'file_pattern': 'GrowthCorridor.geojson',
        'description': 'Development growth corridors'
    },
    'GrowthCorridor2': {
        'name': 'Growth Corridor 2',
        'color': '#FFA500',
        'category': 'MIXED_USE',
        'file_pattern': 'GrowthCorridor2.geojson',
        'description': 'Secondary development growth corridors'
    },
    'Heritage': {
        'name': 'Heritage Areas',
        'color': '#DEB887',
        'category': 'PROTECTED',
        'file_pattern': 'Heritage.geojson',
        'description': 'Heritage and historically significant areas'
    },
    'HillBuffer': {
        'name': 'Hill Buffer Zones',
        'color': '#8FBC8F',
        'category': 'PROTECTED',
        'file_pattern': 'HillBuffer.geojson',
        'description': 'Hill buffer and conservation zones'
    },
    'Hillocks': {
        'name': 'Hillocks',
        'color': '#A0522D',
        'category': 'PROTECTED',
        'file_pattern': 'Hillocks.geojson',
        'description': 'Natural hillocks and elevated areas'
    },
    'Industrial': {
        'name': 'Industrial Areas',
        'color': '#AA66B2',
        'category': 'INDUSTRIAL',
        'file_pattern': 'Industrial.geojson',
        'description': 'Industrial zones and manufacturing areas'
    },
    'MixedUse': {
        'name': 'Mixed Use Areas',
        'color': '#FFB347',
        'category': 'MIXED_USE',
        'file_pattern': 'MixedUse.geojson',
        'description': 'Mixed-use development areas'
    },
    'Public_and_SemiPublic': {
        'name': 'Public & Semi-Public',
        'color': '#E60000',
        'category': 'GOVERNMENT',
        'file_pattern': 'Public_and_SemiPublic.geojson',
        'description': 'Public and semi-public facilities'
    },
    'PublicUtilities': {
        'name': 'Public Utilities',
        'color': '#D79E9E',
        'category': 'UTILITIES',
        'file_pattern': 'PublicUtilities.geojson',
        'description': 'Public utility infrastructure'
    },
    'RailwayLand': {
        'name': 'Railway Land',
        'color': '#2F4F4F',
        'category': 'TRANSPORT',
        'file_pattern': 'RailwayLand.geojson',
        'description': 'Railway land and corridors'
    },
    'Recreational': {
        'name': 'Recreational Areas',
        'color': '#98E600',
        'category': 'PARKS_GREEN',
        'file_pattern': 'Recreational.geojson',
        'description': 'Parks, recreational, and leisure areas'
    },
    'Residential': {
        'name': 'Residential Areas',
        'color': '#FFEBAF',
        'category': 'RESIDENTIAL',
        'file_pattern': 'Residential.geojson',
        'description': 'Existing residential areas'
    },
    'ResidentialExpansion': {
        'name': 'Residential Expansion',
        'color': '#FFDEAD',
        'category': 'RESIDENTIAL',
        'file_pattern': 'ResidentialExpansion.geojson',
        'description': 'Planned residential expansion areas'
    },
    'RoadBuffer': {
        'name': 'Road Buffer Zones',
        'color': '#708090',
        'category': 'TRANSPORT',
        'file_pattern': 'RoadBuffer.geojson',
        'description': 'Road buffer and setback zones'
    },
    'Transportation': {
        'name': 'Transportation Infrastructure',
        'color': '#828282',
        'category': 'TRANSPORT',
        'file_pattern': 'Transportation.geojson',
        'description': 'Transportation infrastructure and corridors'
    },
    'Water_Bodies': {
        'name': 'Water Bodies',
        'color': '#87CEEB',
        'category': 'WATER_BODIES',
        'file_pattern': 'Water_Bodies.geojson',
        'description': 'Rivers, lakes, and water bodies'
    },
    'WaterBodyBuffer': {
        'name': 'Water Body Buffer',
        'color': '#B0E0E6',
        'category': 'WATER_BODIES',
        'file_pattern': 'WaterBodyBuffer.geojson',
        'description': 'Water body buffer and protection zones'
    },
    'ZoologicalPark': {
        'name': 'Zoological Park',
        'color': '#90EE90',
        'category': 'PARKS_GREEN',
        'file_pattern': 'ZoologicalPark.geojson',
        'description': 'Zoological park and wildlife areas'
    }
}

# ================================
# NEW: HYDERABAD LAYER GROUPS
# ================================

HYDERABAD_LAYER_GROUPS = {
    'future-city': {
        'name': 'Future City Development',
        'description': 'Future City Hyderabad boundaries and administrative areas (FCDA)',
        'display_order': 1,
        'layers': HYDERABAD_FUTURE_CITY_LAYERS
    },
    'highways': {
        'name': 'Highways & Major Roads',
        'description': 'National highways and major road network',
        'display_order': 2,
        'layers': HYDERABAD_HIGHWAY_LAYERS
    },
    'metro-lines': {
        'name': 'Metro Network',
        'description': 'Hyderabad Metro lines and stations (Phase 1 & 2)',
        'display_order': 3,
        'layers': HYDERABAD_METRO_LINES_LAYERS
    },
    'master-plan-roads': {
        'name': 'Master Plan Roads',
        'description': 'HMDA master plan proposed roads',
        'display_order': 4,
        'layers': HYDERABAD_MASTER_PLAN_ROADS_LAYERS
    },
    'rrr': {
        'name': 'Regional Ring Road',
        'description': 'Hyderabad Regional Ring Road (RRR)',
        'display_order': 5,
        'layers': HYDERABAD_RRR_LAYERS
    },
    'workspaces': {
        'name': 'Special Economic Zones',
        'description': 'SEZs and industrial workspaces',
        'display_order': 6,
        'layers': HYDERABAD_WORKSPACE_LAYERS
    }
}

# ================================
# NEW: WARANGAL LAYER GROUPS
# ================================

WARANGAL_LAYER_GROUPS = {
    'master_plan': {
        'name': 'Warangal Master Plan',
        'description': 'Complete Warangal urban master plan with all land use categories',
        'display_order': 1,
        'layers': WARANGAL_MASTER_PLAN_LAYERS
    }
}

# ================================
# UPDATED CITY CONFIGURATIONS
# ================================

CITY_CONFIGS = {
    # Existing Bengaluru config (UNCHANGED)
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
    },
    
    # NEW: Hyderabad config
    'hyderabad': {
        'city_info': {
            'name': 'Hyderabad',
            'slug': 'hyderabad',
            'state_ref_id': None,
            'description': 'Cyberabad - City of Pearls',
            'center_lat': 17.3850,
            'center_lng': 78.4867,
            'zoom_level': 11
        },
        'layer_groups': HYDERABAD_LAYER_GROUPS,
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
            'MIXED_USE': '#FFB347',
            'BOUNDARIES': '#FF6347',
            'UNCLASSIFIED': '#E1E1E1'
        }
    },
    
    # NEW: Warangal config
    'warangal': {
        'city_info': {
            'name': 'Warangal',
            'slug': 'warangal',
            'state_ref_id': None,
            'description': 'Historic city and urban development center',
            'center_lat': 17.9784,
            'center_lng': 79.6003,
            'zoom_level': 12
        },
        'layer_groups': WARANGAL_LAYER_GROUPS,
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
            'MIXED_USE': '#FFB347',
            'UNCLASSIFIED': '#E1E1E1'
        }
    }
}

# Alternative slug for Bengaluru (UNCHANGED)
CITY_CONFIGS['bengaluru'] = CITY_CONFIGS['bengaluru']

# ================================
# UPDATED STATE CONFIGURATIONS  
# ================================

STATE_CONFIGS = {
    # Existing Karnataka (UNCHANGED)
    'karnataka': {
        'name': 'Karnataka',
        'code': 'KA',
        'cities': ['bengaluru']
    },
    
    # NEW: Telangana state
    'telangana': {
        'name': 'Telangana', 
        'code': 'TS',
        'cities': ['hyderabad', 'warangal']
    }
}

# ================================
# HELPER FUNCTIONS (UNCHANGED + EXTENDED)
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
# COMPATIBILITY FUNCTIONS (UNCHANGED)
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

def detect_data_format(data):
    """
    FIXED: Detect data format based on content structure (not file path)
    
    Args:
        data: Loaded JSON data object (dict)
        
    Returns:
        str: 'ESRI_JSON', 'GEOJSON', or 'UNKNOWN'
    """
    if not isinstance(data, dict):
        return 'UNKNOWN'
    
    # Check for ESRI JSON indicators
    esri_indicators = [
        'displayFieldName',
        'fieldAliases', 
        'geometryType',
        'spatialReference'
    ]
    
    # If it has multiple ESRI indicators, it's ESRI JSON
    esri_count = sum(1 for indicator in esri_indicators if indicator in data)
    if esri_count >= 2:
        return 'ESRI_JSON'
    
    # Check for GeoJSON format
    if data.get('type') in ['FeatureCollection', 'Feature']:
        return 'GEOJSON'
    
    # Check features structure to differentiate
    features = data.get('features', [])
    if features and isinstance(features, list) and features[0]:
        first_feature = features[0]
        
        # ESRI JSON features have 'attributes' instead of 'properties'
        if 'attributes' in first_feature and 'geometry' in first_feature:
            # Check if geometry has ESRI-style structure
            geometry = first_feature.get('geometry', {})
            if 'rings' in geometry or 'paths' in geometry or ('x' in geometry and 'y' in geometry):
                return 'ESRI_JSON'
        
        # GeoJSON features have 'properties' and standard geometry
        if 'properties' in first_feature and 'geometry' in first_feature:
            geometry = first_feature.get('geometry', {})
            if 'type' in geometry and 'coordinates' in geometry:
                return 'GEOJSON'
    
    return 'UNKNOWN'

def detect_data_format_from_file_path(file_path):
    """Detect data format from file extension (fallback method)"""
    file_path = str(file_path).lower()
    if file_path.endswith('.geojson'):
        return 'GEOJSON'
    elif file_path.endswith('.json'):
        return 'JSON'  # Needs content-based detection
    elif file_path.endswith('.shp'):
        return 'SHP'
    else:
        return 'GEOJSON'  # Default

def optimize_coordinates(coords, precision=8):
    """
    FIXED - Optimize coordinate precision for coordinate arrays (not geometry objects)
    
    Args:
        coords: Coordinate array or nested arrays
        precision: Decimal precision to round to
        
    Returns:
        Optimized coordinate array
    """
    if isinstance(coords, list):
        return [optimize_coordinates(coord, precision) for coord in coords]
    elif isinstance(coords, (int, float)):
        return round(float(coords), precision)
    return coords

def optimize_geojson_geometry(geojson_geom, precision=8):
    """
    NEW - Optimize a GeoJSON geometry object's coordinates
    
    Args:
        geojson_geom: GeoJSON geometry dict
        precision: Decimal precision
        
    Returns:
        Optimized GeoJSON geometry dict
    """
    if not isinstance(geojson_geom, dict) or 'coordinates' not in geojson_geom:
        return geojson_geom
    
    optimized_geom = geojson_geom.copy()
    optimized_geom['coordinates'] = optimize_coordinates(geojson_geom['coordinates'], precision)
    
    return optimized_geom

def convert_esri_to_geojson_geometry(esri_geometry):
    """
    ENHANCED - Convert ESRI geometry to GeoJSON format with better error handling
    
    Args:
        esri_geometry: ESRI geometry object
        
    Returns:
        GeoJSON geometry dict or None if conversion fails
    """
    if not isinstance(esri_geometry, dict):
        return None
    
    try:
        # Handle ESRI Polygon (has 'rings')
        if 'rings' in esri_geometry:
            rings = esri_geometry['rings']
            if not rings or not isinstance(rings, list):
                return None
                
            # Ensure proper polygon structure
            if len(rings) == 1:
                # Simple polygon
                return {
                    'type': 'Polygon',
                    'coordinates': rings
                }
            else:
                # MultiPolygon or polygon with holes
                return {
                    'type': 'Polygon',
                    'coordinates': rings
                }
        
        # Handle ESRI LineString/MultiLineString (has 'paths')
        elif 'paths' in esri_geometry:
            paths = esri_geometry['paths']
            if not paths or not isinstance(paths, list):
                return None
                
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
        
        # Handle ESRI Point (has 'x' and 'y')
        elif 'x' in esri_geometry and 'y' in esri_geometry:
            return {
                'type': 'Point',
                'coordinates': [esri_geometry['x'], esri_geometry['y']]
            }
        
        # Handle already converted geometry
        elif 'type' in esri_geometry and 'coordinates' in esri_geometry:
            return esri_geometry
        
        return None
        
    except Exception as e:
        print(f"    ❌ Geometry conversion error: {e}")
        return None

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
    'detect_data_format_from_file_path',
    'optimize_geojson_geometry',
    'get_city_style_config'
]

def get_visakhapatnam_styles():
    """Get Visakhapatnam layer styles with pattern support"""
    return {
        'Agricultural Use Zone': {
            'fill_color': '#D3FFBE',
            'pattern': 'SOLID'
        },
        'Blue Zone Water Bodies': {
            'fill_color': '#73FFDF',
            'pattern': 'SOLID'
        },
        'Brown Zone Hills': {
            'fill_color': '#A87000',
            'pattern': 'SOLID'
        },
        'Commercial Use Zone': {
            'fill_color': '#004DA8',
            'pattern': 'SOLID'
        },
        'Existing Crematorium / Burial Ground / Graveyard': {
            'pattern': 'HATCHED',
            'pattern_color': '#FF0000',
            'fill_color': '#FFFFFF',
            'secondary_fill': '#FFFFFF'
        },
        'Existing Educational Facilities': {
            'pattern': 'HATCHED',
            'pattern_color': '#000000',
            'fill_color': '#FF0000',
            'secondary_fill': '#FF0000'
        },
        'Existing Government / Semi Government Facilities': {
            'fill_color': '#FF0000',
            'pattern': 'SOLID'
        },
        'Existing Health Facilities': {
            'pattern': 'DOTTED',
            'pattern_color': '#CCCCCC',
            'fill_color': '#FF0000',
            'secondary_fill': '#FF0000'
        },
        'Proposed Industrial Use Zone': {
            'pattern': 'HATCHED',
            'pattern_color': '#FFFFFF',
            'fill_color': '#C500FF',
            'secondary_fill': '#C500FF'
        },
        'Existing Industrial Area': {
            'fill_color': '#C500FF',
            'pattern': 'SOLID'
        },
        'Existing Public Utilities': {
            'pattern': 'HATCHED',
            'pattern_color': '#E60000',
            'fill_color': '#FF7F7F',
            'secondary_fill': '#FF7F7F'
        },
        'Existing Recreational / Playgrounds / Parks / Layout Open Space': {
            'fill_color': '#55FF00',
            'pattern': 'SOLID'
        },
        'Existing Religious Facilities': {
            'pattern': 'HATCHED',
            'pattern_color': '#55FF00',
            'fill_color': '#FF0000',
            'secondary_fill': '#FF0000'
        },
        'Existing Road / Railway Line Area': {
            'pattern': 'HATCHED',
            'pattern_color': '#828282',
            'fill_color': '#FFFFFF',
            'secondary_fill': '#FFFFFF'
        },
        'Existing Transportation Facility': {
            'fill_color': '#686868',
            'pattern': 'SOLID'
        },
        'Green Zone Forest': {
            'fill_color': '#00734C',
            'pattern': 'SOLID'
        },
        'Kambalakonda Eco Sensitive Zone / NAOB Buffer / Zoological Park': {
            'fill_color': '#D7C29E',
            'pattern': 'SOLID'
        },
        'Kambalakonda WildLife Sanctuary / Biodiversity Area': {
            'fill_color': '#38A800',
            'pattern': 'SOLID'
        },
        'Mixed Use Zone 1': {
            'fill_color': '#FFAA00',
            'pattern': 'SOLID'
        },
        'Mixed Use Zone 2': {
            'fill_color': '#FFD37F',
            'pattern': 'SOLID'
        },
        'Mixed Use Zone 3': {
            'pattern': 'HATCHED',
            'pattern_color': '#E1E1E1',
            'fill_color': '#E69800',
            'secondary_fill': '#E69800'
        },
        'Mixed Use Zone 4': {
            'pattern': 'DOTTED',
            'pattern_color': '#000000',
            'fill_color': '#FFAA00',
            'secondary_fill': '#FFAA00'
        },
        'Proposed PSP Use Zone': {
            'pattern': 'HATCHED',
            'pattern_color': '#FF0000',
            'fill_color': '#FFFFFF',
            'secondary_fill': '#FFFFFF'
        },
        'Proposed Public Utilities Use Zone': {
            'pattern': 'HATCHED',
            'pattern_color': '#FFFFFF',
            'fill_color': '#F57A7A',
            'secondary_fill': '#F57A7A'
        },
        'Proposed Recreational Use Zone': {
            'fill_color': '#4C7300',
            'pattern': 'SOLID'
        },
        'Proposed Road Network': {
            'fill_color': '#000000',
            'pattern': 'SOLID'
        },
        'Proposed Transportation Facility Use Zone': {
            'pattern': 'HATCHED',
            'pattern_color': '#FFFFFF',
            'fill_color': '#343434',
            'secondary_fill': '#343434'
        },
        'Residential Use Zone': {
            'fill_color': '#FFFF73',
            'pattern': 'SOLID'
        },
        'Sea / River / Accreted Land': {
            'pattern': 'DOTTED',
            'pattern_color': '#E39E00',
            'fill_color': '#D7C29E',
            'secondary_fill': '#D7C29E'
        },
        'Special Area Use Zone': {
            'pattern': 'HATCHED',
            'pattern_color': '#002673',
            'fill_color': '#FFFFFF',
            'secondary_fill': '#FFFFFF'
        },
        'Water Body Buffer': {
            'pattern': 'DOTTED',
            'pattern_color': '#267300',
            'fill_color': '#4CE600',
            'secondary_fill': '#4CE600'
        }
    }

def get_amaravati_styles():
    """Get Amaravati layer styles with pattern support"""
    return {
        'Burial Ground': {
            'pattern': 'DOTTED',
            'pattern_color': '#E39E00',
            'fill_color': '#FFFFFF',
            'secondary_fill': '#FFFFFF'
        },
        'C1 - Mixed Use Zone': {
            'fill_color': '#73B2FF',
            'pattern': 'SOLID'
        },
        'C2 - General Commercial Zone': {
            'fill_color': '#00C5FF',
            'pattern': 'SOLID',
            'stroke_color': '#000000',
            'stroke_width': 1
        },
        'C3 - Neighbourhood Centre Zone': {
            'fill_color': '#00C5FF',
            'pattern': 'SOLID'
        },
        'C4 - Town Centre Zone': {
            'fill_color': '#00A9E6',
            'pattern': 'SOLID'
        },
        'C5 - Regional Centre Zone': {
            'fill_color': '#0070FF',
            'pattern': 'SOLID'
        },
        'C6 - Central Business District Zone': {
            'fill_color': '#005CE6',
            'pattern': 'SOLID'
        },
        'Commercial Vacant': {
            'fill_color': '#C5E2FF',
            'pattern': 'SOLID'
        },
        'I1 - Business Park Zone': {
            'fill_color': '#FFBEE8',
            'pattern': 'SOLID'
        },
        'I2 - Logistics Zone': {
            'fill_color': '#FF73DF',
            'pattern': 'SOLID'
        },
        'I3 - Non Polluting Industry Zone': {
            'fill_color': '#A900E6',
            'pattern': 'SOLID'
        },
        'P1 - Passive Zone': {
            'fill_color': '#267300',
            'pattern': 'SOLID'
        },
        'P2 - Active Zone': {
            'fill_color': '#38A800',
            'pattern': 'SOLID'
        },
        'P3 - Protected Zone': {
            'fill_color': '#BEE8FF',
            'pattern': 'SOLID'
        },
        'P3 - Protected Zone Hills': {
            'fill_color': '#4C7300',
            'pattern': 'SOLID'
        },
        'PGN-G': {
            'fill_color': '#4C7300',
            'pattern': 'SOLID'
        },
        'PGN-V': {
            'fill_color': '#897044',
            'pattern': 'SOLID'
        },
        'R1 - Village Planning Zone': {
            'pattern': 'HATCHED',
            'pattern_color': '#000000',
            'fill_color': '#FFFFFF',
            'secondary_fill': '#FFFFFF'
        },
        'R3 - Medium to High Density Zone': {
            'fill_color': '#F5CA7A',
            'pattern': 'SOLID'
        },
        'R4 - High Density Zone': {
            'fill_color': '#E69800',
            'pattern': 'SOLID'
        },
        'RAA': {
            'fill_color': '#FFAA00',
            'pattern': 'SOLID'
        },
        'Residential Vacant': {
            'fill_color': '#FFD37F',
            'pattern': 'SOLID'
        },
        'S2 - Education Zone': {
            'fill_color': '#FF7F7F',
            'pattern': 'SOLID'
        },
        'S3 - Special Zone': {
            'fill_color': '#D7B09E',
            'pattern': 'SOLID'
        },
        'SC1a - Mixed Use': {
            'fill_color': '#0070FF',
            'pattern': 'SOLID'
        },
        'SC1b - Mixed Use': {
            'fill_color': '#73B2FF',
            'pattern': 'SOLID'
        },
        'SP1 - Passive Zone': {
            'fill_color': '#267300',
            'pattern': 'SOLID'
        },
        'SP2 - Active Zone': {
            'fill_color': '#38A800',
            'pattern': 'SOLID'
        },
        'SP3 - Protected Zone': {
            'fill_color': '#00C5FF',
            'pattern': 'SOLID'
        },
        'SR2 - Low Density Housing': {
            'fill_color': '#FFFFBE',
            'pattern': 'SOLID'
        },
        'SR4 - High Density Private': {
            'fill_color': '#FFAA00',
            'pattern': 'SOLID'
        },
        'SS1 - Government Zone': {
            'fill_color': '#E60000',
            'pattern': 'SOLID'
        },
        'SS2a - Education Zone': {
            'fill_color': '#FF7F7F',
            'pattern': 'SOLID'
        },
        'SS2b - Cultural Zone': {
            'fill_color': '#C500FF',
            'pattern': 'SOLID'
        },
        'SS2c - Health Zone': {
            'fill_color': '#D3FFBE',
            'pattern': 'SOLID'
        },
        'SS3 - Special Zone': {
            'fill_color': '#A83800',
            'pattern': 'SOLID'
        },
        'SU1 - Reserve Zone': {
            'fill_color': '#E1E1E1',
            'pattern': 'SOLID'
        },
        'SU2 - Road Network': {
            'fill_color': '#FFFFFF',
            'pattern': 'SOLID',
            'stroke_color': '#000000',
            'stroke_width': 1
        },
        'U1 - Reserve Zone': {
            'fill_color': '#CCCCCC',
            'pattern': 'SOLID'
        },
        'U2 - Road Reserve Zone': {
            'fill_color': '#000000',
            'pattern': 'SOLID'
        }
    }

def get_city_style_config(city_slug: str, zone_name: str) -> dict:
    """
    Get style configuration for a specific zone in a city.
    This includes pattern information if applicable.
    """
    if city_slug == 'visakhapatnam':
        styles = get_visakhapatnam_styles()
    elif city_slug == 'amaravati':
        styles = get_amaravati_styles()
    else:
        # Default solid styles for other cities
        return {
            'fill_color': '#CCCCCC',
            'pattern': 'SOLID',
            'stroke_width': 0
        }
    
    # Get the style for the specific zone
    style = styles.get(zone_name, {
        'fill_color': '#CCCCCC',
        'pattern': 'SOLID',
        'stroke_width': 0
    })
    
    # Ensure stroke_width is 0 unless explicitly set
    if 'stroke_width' not in style:
        style['stroke_width'] = 0
    
    return style

# Pattern rendering parameters
PATTERN_DEFAULTS = {
    'HATCHED': {
        'spacing': 12,
        'angle': 45,
        'line_width': 2
    },
    'DOTTED': {
        'spacing': 15,
        'dot_size': 3
    },
    'STRIPED': {
        'spacing': 20,
        'angle': 45,
        'stripe_width': 8
    },
    'CROSS_HATCHED': {
        'spacing': 12,
        'angle': 45,
        'line_width': 2
    }
}