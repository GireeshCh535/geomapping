# config.py - Enhanced with accurate PLU mappings from real data

"""
Enhanced city-specific configurations with accurate PLU code mappings
"""

BANGALORE_PLU_MAPPING = {
    # Primary PLU codes found in actual data - fixed to use valid LayerCategory codes
    'E': {
        'category': 'AGRICULTURAL',  # Default fallback, will be overridden by sub-mappings
        'description': 'Environmental/Agricultural/Protected Land',
        'secondary_codes': ['Ea', 'Eb', 'Eaa', 'Eac', 'Ke'],
        'examples': ['Agricultural land', 'Forest areas', 'Protected valleys', 'Lakes']
    },
    'B': {
        'category': 'COMMERCIAL',
        'description': 'Business/Commercial Areas',
        'secondary_codes': ['Ba', 'Bb'],
        'examples': ['Central Business District', 'Business centers']
    },
    'D': {
        'category': 'INDUSTRIAL',  # Default fallback
        'description': 'Development/Industrial/Transport',
        'secondary_codes': ['Da', 'Db', 'Dc'],
        'examples': ['Industrial areas', 'High-tech zones', 'Transportation']
    },
    'C': {
        'category': 'RESIDENTIAL',
        'description': 'Residential Areas',
        'secondary_codes': ['Ca', 'Cb'],
        'examples': ['Residential zones', 'Housing areas']
    },
    'R': {
        'category': 'RESIDENTIAL',
        'description': 'Residential areas',
        'secondary_codes': [],
        'examples': ['Residential zones']
    },
    'J': {
        'category': 'UTILITIES',   
        'description': 'Infrastructure/Utilities',
        'secondary_codes': [],
        'examples': ['Utility infrastructure']
    },
    'P': {
        'category': 'PUBLIC',
        'description': 'Public facilities',
        'secondary_codes': [],
        'examples': ['Public buildings', 'Government facilities']
    },
    'H': {
        'category': 'TRANSPORT',
        'description': 'Transportation/Highways',
        'secondary_codes': [],
        'examples': ['Highways', 'Transportation corridors']
    },
    'O': {
        'category': 'COMMERCIAL',
        'description': 'Commercial/Office',
        'secondary_codes': [],
        'examples': ['Office buildings', 'Commercial complexes']
    },
    'G': {
        'category': 'PARKS_GREEN',
        'description': 'Green spaces',
        'secondary_codes': [],
        'examples': ['Gardens', 'Green areas']
    },
    'T': {
        'category': 'TRANSPORT',
        'description': 'Transportation',
        'secondary_codes': [],
        'examples': ['Transport facilities']
    },
    'I': {
        'category': 'INDUSTRIAL',
        'description': 'Industrial',
        'secondary_codes': [],
        'examples': ['Industrial areas']
    },
    'M': {
        'category': 'UTILITIES',
        'description': 'Municipal/Utilities',
        'secondary_codes': ['Mt', 'Mtg'],
        'examples': ['Power facilities', 'Water treatment', 'Garbage facilities']
    },
    'F': {
        'category': 'PARKS_GREEN',
        'description': 'Parks and Green Spaces',
        'secondary_codes': [],
        'examples': ['Parks', 'Green spaces', 'Sports grounds', 'Cemeteries']
    },
    'N': {
        'category': 'DEFENSE',
        'description': 'Defense/Military Areas',
        'secondary_codes': [],
        'examples': ['Military installations', 'Defense areas']
    },
    'S': {
        'category': 'UNCLASSIFIED',
        'description': 'Unclassified/Special Use',
        'secondary_codes': [],
        'examples': ['Unclassified areas', 'Special use zones']
    },
    # Special PLU_BDA authority codes - simplified structure
    'K': {
        'category': 'PUBLIC',
        'description': 'Public facilities',
        'secondary_codes': ['Ke'],
        'examples': ['Public facilities', 'Government buildings']
    },
    'Q': {
        'category': 'UTILITIES',
        'description': 'Quasi-public utilities',
        'secondary_codes': [],
        'examples': ['Public utilities', 'Treatment facilities']
    },
    'Ta': {
        'category': 'TRANSPORT',
        'description': 'Transportation',
        'secondary_codes': [],
        'examples': ['Transportation networks', 'Transit facilities']
    },
    'U': {
        'category': 'DEFENSE',
        'description': 'Defense authority',
        'secondary_codes': [],
        'examples': ['Defense areas', 'Military zones']
    },
    'Eab': {
        'category': 'DRAINS',
        'description': 'Drainage systems',
        'secondary_codes': [],
        'examples': ['Drains', 'Drainage infrastructure']
    },
    'Ef': {
        'category': 'AGRICULTURAL',
        'description': 'Agricultural authority',
        'secondary_codes': [],
        'examples': ['Agricultural land']
    },
    'Eaa': {
        'category': 'PROTECTED',
        'description': 'Protected land authority',
        'secondary_codes': [],
        'examples': ['Protected areas', 'State forests']
    },
    'Eac': {
        'category': 'WATER_BODIES',
        'description': 'Water bodies authority',
        'secondary_codes': [],
        'examples': ['Lakes', 'Tanks', 'Water bodies']
    },
    'Ca': {
        'category': 'RESIDENTIAL',
        'description': 'Residential authority (mixed)',
        'secondary_codes': [],
        'examples': ['Mixed residential areas']
    },
    'Cb': {
        'category': 'RESIDENTIAL',
        'description': 'Residential authority (main)',
        'secondary_codes': [],
        'examples': ['Main residential areas']
    },
    'Ba': {
        'category': 'COMMERCIAL',
        'description': 'Commercial authority (central)',
        'secondary_codes': [],
        'examples': ['Central commercial areas']
    },
    'Bb': {
        'category': 'COMMERCIAL',
        'description': 'Commercial authority (business)',
        'secondary_codes': [],
        'examples': ['Business commercial areas']
    },
    'Da': {
        'category': 'INDUSTRIAL',
        'description': 'Industrial authority',
        'secondary_codes': [],
        'examples': ['Industrial areas']
    },
    'Db': {
        'category': 'HIGH_TECH',
        'description': 'High-tech authority',
        'secondary_codes': [],
        'examples': ['High-tech zones']
    },
    'Dc': {
        'category': 'TRANSPORT',
        'description': 'Transport authority',
        'secondary_codes': [],
        'examples': ['Transportation infrastructure']
    }
}

# Enhanced PLU mapping function - simplified logic
def map_plu_code_to_category_bangalore(plu_primary, plu_secondary_1=None, plu_secondary_2=None, plu_bda=None):
    """
    Enhanced PLU mapping for Bangalore using real data patterns - simplified
    """
    
    # Clean inputs
    plu_primary = (plu_primary or '').strip()
    plu_secondary_1 = (plu_secondary_1 or '').strip()
    plu_secondary_2 = (plu_secondary_2 or '').strip()
    plu_bda = (plu_bda or '').strip()
    
    # Priority 1: Check PLU_BDA for specific authority mappings
    if plu_bda and plu_bda in BANGALORE_PLU_MAPPING:
        return BANGALORE_PLU_MAPPING[plu_bda]['category']
    
    # Priority 2: Check secondary code 2 (most specific)
    if plu_secondary_2 and plu_secondary_2 in BANGALORE_PLU_MAPPING:
        return BANGALORE_PLU_MAPPING[plu_secondary_2]['category']
    
    # Priority 3: Check secondary code 1
    if plu_secondary_1 and plu_secondary_1 in BANGALORE_PLU_MAPPING:
        return BANGALORE_PLU_MAPPING[plu_secondary_1]['category']
    
    # Priority 4: Check primary code
    if plu_primary and plu_primary in BANGALORE_PLU_MAPPING:
        return BANGALORE_PLU_MAPPING[plu_primary]['category']
    
    # Priority 5: Special combinations for 'E' code (most complex)
    if plu_primary == 'E':
        # E + Ea + Eaa = Protected
        if plu_secondary_1 == 'Ea' and plu_secondary_2 == 'Eaa':
            return 'PROTECTED'
        # E + Ea + Eac = Water Bodies  
        elif plu_secondary_1 == 'Ea' and plu_secondary_2 == 'Eac':
            return 'WATER_BODIES'
        # E + Eb + no secondary = Agricultural
        elif plu_secondary_1 == 'Eb':
            return 'AGRICULTURAL'
        # E + Ke = Public
        elif plu_secondary_1 == 'Ke':
            return 'PUBLIC'
        # E + Ea default = Protected
        elif plu_secondary_1 == 'Ea':
            return 'PROTECTED'
        else:
            return 'AGRICULTURAL'  # Default for E
    
    return 'UNCLASSIFIED'

# Bangalore Configuration (Enhanced with real data patterns)
BANGALORE_CONFIG = {
    'city_info': {
        'name': 'Bangalore',
        'slug': 'bangalore',
        'state': 'Karnataka',
        'center_lat': 12.9716,
        'center_lng': 77.5946,
    },
    'data_format': 'ESRI_JSON',
    'coordinate_precision': 8,
    'plu_mapping': BANGALORE_PLU_MAPPING,
    'file_mappings': {
        # Updated with your actual files
        'Agricultural_land.json': 'AGRICULTURAL',
        'Commercial_Business_.json': 'COMMERCIAL',
        'Commercial_Central_.json': 'COMMERCIAL', 
        'Defense.json': 'DEFENSE',
        'Drains.json': 'DRAINS',
        'HighTech.json': 'HIGH_TECH',
        'Industrial.json': 'INDUSTRIAL',
        'Lake_Tank.json': 'WATER_BODIES',
        'Parks_GreenSpaces_Sports_Playgrounds_Cemetery_BurialGrounds.json': 'PARKS_GREEN',
        'Power_Water_GarbageFacility_TreatmentPlant.json': 'UTILITIES',
        'Public_SemiPublic.json': 'PUBLIC',
        'Residential_Main_.json': 'RESIDENTIAL',
        'Residential_Mixed_.json': 'RESIDENTIAL',
        'Road_Rail_Airport_Transport.json': 'TRANSPORT',
        'StateForest_Valley_ProtectedLand_.json': 'PROTECTED',
        'Unclassified_Use.json': 'UNCLASSIFIED',
    },
    'attribute_mappings': {
        'fid': 'source_fid',
        'OBJECTID': 'source_object_id',
        'PLU_Cd': 'land_use_code',
        'PLU_Tp_pro': 'plu_primary_code',
        'PLU_Tp_p_1': 'plu_secondary_1', 
        'PLU_Tp_p_2': 'plu_secondary_2',
        'PLU_prop_l': 'plu_proposed_use',
        'PLU_F_PD_C': 'plu_development_code',
        'PLU_BDA': 'plu_authority',
        'PLU_Tp_KTC': 'plu_ktc_code',
        'PLU_Tp_sur': 'plu_survey_code',
        'Shape_Leng': 'source_length_value',
        'SHAPE.STArea()': 'source_area_value',
        'SHAPE.STLength()': 'source_perimeter_value',
    },
    'colors': {
        'RESIDENTIAL': '#FFC400',      # Yellow - Residential
        'COMMERCIAL': '#004DA8',       # Blue - Commercial  
        'INDUSTRIAL': '#AA66B2',       # Purple - Industrial
        'HIGH_TECH': '#C29ED7',        # Light Purple - High Tech
        'PUBLIC': '#E60000',           # Red - Public/Semi Public
        'DEFENSE': '#8B4513',          # Brown - Defense
        'PROTECTED': '#228B22',        # Forest Green - State Forest/Protected
        'PARKS_GREEN': '#98E600',      # Bright Green - Parks and Green Spaces
        'WATER_BODIES': '#1E90FF',     # Dodger Blue - Lake/Tank
        'TRANSPORT': '#808080',        # Gray - Road/Rail/Airport Transport
        'UTILITIES': '#FF6347',        # Tomato - Power/Water/Utilities
        'AGRICULTURAL': '#9ACD32',     # Yellow Green - Agricultural Land
        'UNCLASSIFIED': '#D3D3D3',     # Light Gray - Unclassified Use
        'DRAINS': '#4682B4',           # Steel Blue - Drains
    }
}

# Enhanced attribute processing
def process_bangalore_attributes(esri_attributes):
    """
    Process ESRI attributes for Bangalore with smart categorization
    """
    
    # Extract PLU fields
    plu_primary = esri_attributes.get('PLU_Tp_pro', '').strip()
    plu_secondary_1 = esri_attributes.get('PLU_Tp_p_1', '').strip()
    plu_secondary_2 = esri_attributes.get('PLU_Tp_p_2', '').strip()
    plu_bda = esri_attributes.get('PLU_BDA', '').strip()
    
    # Smart categorization
    derived_category = map_plu_code_to_category_bangalore(
        plu_primary, plu_secondary_1, plu_secondary_2, plu_bda
    )
    
    # Build processed attributes
    processed = {
        'plu_primary_code': plu_primary,
        'plu_secondary_1': plu_secondary_1,
        'plu_secondary_2': plu_secondary_2,
        'plu_proposed_use': esri_attributes.get('PLU_prop_l', '').strip(),
        'plu_development_code': esri_attributes.get('PLU_F_PD_C'),
        'plu_authority': plu_bda,
        'plu_ktc_code': esri_attributes.get('PLU_Tp_KTC', '').strip(),
        'plu_survey_code': esri_attributes.get('PLU_Tp_sur', '').strip(),
        'land_use_code': str(esri_attributes.get('PLU_Cd', '')),
        'derived_category': derived_category,
        'land_use_type': derived_category,
        'source_fid': esri_attributes.get('fid'),
        'source_object_id': esri_attributes.get('OBJECTID'),
        'source_area_value': esri_attributes.get('SHAPE.STArea()'),
        'source_length_value': esri_attributes.get('Shape_Leng'),
        'source_perimeter_value': esri_attributes.get('SHAPE.STLength()'),
    }
    
    return processed

# Vizag Configuration (Standard GeoJSON)
VIZAG_CONFIG = {
    'city_info': {
        'name': 'Visakhapatnam',
        'slug': 'vizag',
        'state': 'Andhra Pradesh',
        'center_lat': 17.6868,
        'center_lng': 83.2185,
    },
    'data_format': 'GEOJSON',
    'coordinate_precision': 8,
    'file_mappings': {
        'Residential_Use_Zone.geojson': 'RESIDENTIAL',
        'Commercial_Use_Zone.geojson': 'COMMERCIAL',
        'Mixed_Use_Zone_1.geojson': 'MIXED_USE',
        'Mixed_Use_Zone_2_BAIA.geojson': 'MIXED_USE',
        'Mixed_Use_Zone_3_BAIA.geojson': 'MIXED_USE',
        'Mixed_Use_Zone_4_BAIA.geojson': 'MIXED_USE',
        'Existing_Industrial_Area.geojson': 'INDUSTRIAL',
        'Proposed_Industrial_Use_Zone.geojson': 'INDUSTRIAL',
        'Existing_Government_Semi_Government_Facilities.geojson': 'GOVERNMENT',
        'Existing_Educational_Facilities.geojson': 'EDUCATION',
        'Existing_Health_Facilities.geojson': 'HEALTHCARE',
        'Existing_Religious_Facilities.geojson': 'CULTURAL',
        'Green_Zone_Forest.geojson': 'PROTECTED',
        'Blue_Zone_Water_Bodies.geojson': 'WATER_BODIES',
        'Existing_Road_Railway_Line_Area.geojson': 'TRANSPORT',
        'Proposed_Road_Network.geojson': 'TRANSPORT',
        'Existing_Transportation_Facility.geojson': 'TRANSPORT',
        'Proposed_Transportation_Facility_Use_Zone.geojson': 'TRANSPORT',
        'Existing_Public_Utilities.geojson': 'UTILITIES',
        'Proposed_Public_Utilities_Use_Zone.geojson': 'UTILITIES',
        'Existing_Recreational_Playgrounds_Parks_Layout_OpenSpace.geojson': 'PARKS_GREEN',
        'Proposed_Recreational_Use_Zone.geojson': 'PARKS_GREEN',
        'Existing_Crematorium_Burial_Ground_Graveyard.geojson': 'CEMETERY',
        'Kambalakonda_WildLife_Sanctuary_Biodiversity_Area.geojson': 'PROTECTED',
        'Kambalakonda_Eco_Sensitive_Zone_NAOB_Buffer_Zoological_Park.geojson': 'PROTECTED',
        'Sea_River_Accreted_Land.geojson': 'WATER_BODIES',
        'Water_Body_Buffer.geojson': 'WATER_BODIES',
        'Proposed_PSP_Use_Zone.geojson': 'PUBLIC',
        'Special_Area_Use_Zone.geojson': 'SPECIAL',
    },
    'attribute_mappings': {
        # Standard GeoJSON property mappings
        'name': 'name',
        'type': 'category_name',
        'land_use': 'land_use_type',
        'zone': 'zoning',
        'area': 'source_area_value',
    },
    'colors': {
        'RESIDENTIAL': '#8BC34A',    # Light Green
        'COMMERCIAL': '#FF5722',     # Deep Orange  
        'MIXED_USE': '#9C27B0',      # Purple
        'INDUSTRIAL': '#607D8B',     # Blue Grey
        'GOVERNMENT': '#F44336',     # Red
        'EDUCATION': '#2196F3',      # Blue
        'HEALTHCARE': '#00BCD4',     # Cyan
        'CULTURAL': '#7E57C2',       # Deep Purple
        'PROTECTED': '#4CAF50',      # Green
        'WATER_BODIES': '#03A9F4',   # Light Blue
        'TRANSPORT': '#9E9E9E',      # Grey
        'UTILITIES': '#FF9800',      # Orange
        'PARKS_GREEN': '#8BC34A',    # Light Green
        'CEMETERY': '#757575',       # Grey
        'SPECIAL': '#FFEE58',        # Yellow
    }
}

# Amaravati Configuration (Standard GeoJSON)
AMARAVATI_CONFIG = {
    'city_info': {
        'name': 'Amaravati',
        'slug': 'amaravati',
        'state': 'Andhra Pradesh',
        'center_lat': 16.5062,
        'center_lng': 80.6480,
    },
    'data_format': 'GEOJSON',
    'coordinate_precision': 8,
    'file_mappings': {
        'C1__Mixed_use_zone.geojson': 'MIXED_USE',
        'C2__General_commercial_zone.geojson': 'COMMERCIAL',
        'C3_Neighbourhood_centre_zone.geojson': 'COMMERCIAL',
        'C4_Town_centre_zone.geojson': 'COMMERCIAL',
        'C5_Regional_centre_zone.geojson': 'COMMERCIAL',
        'C6_Central_business_district_zone.geojson': 'COMMERCIAL',
        'I1_Business_park_zone.geojson': 'INDUSTRIAL',
        'I2_Logistics_zone.geojson': 'INDUSTRIAL',
        'I3_Non_polluting_industry_zone.geojson': 'INDUSTRIAL',
        'R1_Village_planning_zone.geojson': 'RESIDENTIAL',
        'R3_Medium_to_high_density_zone.geojson': 'RESIDENTIAL',
        'R4_High_density_zone.geojson': 'RESIDENTIAL',
        'SS1___Government_Zone.geojson': 'GOVERNMENT',
        'SS2a__Education_Zone.geojson': 'EDUCATION',
        'SS2b_Cultural_Zone.geojson': 'CULTURAL',
        'SS2c_Health_Zone.geojson': 'HEALTHCARE',
        'SU2___Road_Network.geojson': 'TRANSPORT',
        'U2__Road_reserve_zone.geojson': 'TRANSPORT',
        'Burial_Ground.geojson': 'CEMETERY',
        'P1_Passive_zone.geojson': 'PROTECTED',
        'P2_Active_zone.geojson': 'PROTECTED',
        'P3_Protected_zone.geojson': 'PROTECTED',
    },
    'attribute_mappings': {
        'name': 'name',
        'zone_type': 'zoning',
        'area': 'source_area_value',
    },
    'colors': {
        'RESIDENTIAL': '#66BB6A',    # Medium Green
        'COMMERCIAL': '#FFA726',     # Amber
        'MIXED_USE': '#AB47BC',      # Purple
        'INDUSTRIAL': '#8D6E63',     # Brown
        'GOVERNMENT': '#EF5350',     # Red
        'EDUCATION': '#42A5F5',      # Light Blue
        'HEALTHCARE': '#26A69A',     # Teal
        'CULTURAL': '#7E57C2',       # Deep Purple
        'TRANSPORT': '#29B6F6',      # Sky Blue
        'UTILITIES': '#FF7043',      # Deep Orange
        'PROTECTED': '#388E3C',      # Forest Green
        'CEMETERY': '#757575',       # Grey
        'SPECIAL': '#FFEE58',        # Yellow
    }
}

# Master configuration dictionary
CITY_CONFIGS = {
    'bangalore': BANGALORE_CONFIG,
    'vizag': VIZAG_CONFIG,
    'amaravati': AMARAVATI_CONFIG,
}

def get_city_config(city_slug):
    """Get configuration for a specific city"""
    return CITY_CONFIGS.get(city_slug.lower())

def get_plu_mapping(city_slug):
    """Get PLU code mapping for a city"""
    config = get_city_config(city_slug)
    return config.get('plu_mapping', {}) if config else {}

def map_plu_code_to_category(city_slug, plu_code):
    """Map a PLU code to a category for a specific city"""
    plu_mapping = get_plu_mapping(city_slug)
    plu_info = plu_mapping.get(plu_code, {})
    return plu_info.get('category', 'UNCLASSIFIED')

def get_attribute_mapping(city_slug):
    """Get attribute field mappings for a city"""
    config = get_city_config(city_slug)
    return config.get('attribute_mappings', {}) if config else {}

def optimize_coordinates(coords, precision=8):
    """Optimize coordinate precision to reduce file size"""
    if isinstance(coords, list):
        if isinstance(coords[0], list):
            # Nested array (polygon rings)
            return [optimize_coordinates(ring, precision) for ring in coords]
        elif isinstance(coords[0], (int, float)):
            # Coordinate pair [lng, lat]
            return [round(coord, precision) for coord in coords]
    return coords

def detect_data_format(data):
    """Detect if data is ESRI JSON or standard GeoJSON"""
    if isinstance(data, dict):
        # Check for ESRI-specific fields
        if 'features' in data:
            first_feature = data['features'][0] if data['features'] else {}
            if 'attributes' in first_feature and 'geometry' in first_feature:
                geometry = first_feature.get('geometry', {})
                if 'rings' in geometry:
                    return 'ESRI_JSON'
                elif 'type' in geometry and 'coordinates' in geometry:
                    return 'GEOJSON'
        elif 'displayFieldName' in data or 'fieldAliases' in data:
            return 'ESRI_JSON'
    return 'UNKNOWN'

def convert_esri_to_geojson_geometry(esri_geometry):
    """Convert ESRI geometry format to GeoJSON format"""
    if not esri_geometry:
        return None
    
    if 'rings' in esri_geometry:
        # ESRI Polygon with rings
        return {
            'type': 'Polygon',
            'coordinates': esri_geometry['rings']
        }
    elif 'paths' in esri_geometry:
        # ESRI LineString with paths
        if len(esri_geometry['paths']) == 1:
            return {
                'type': 'LineString',
                'coordinates': esri_geometry['paths'][0]
            }
        else:
            return {
                'type': 'MultiLineString',
                'coordinates': esri_geometry['paths']
            }
    elif 'x' in esri_geometry and 'y' in esri_geometry:
        # ESRI Point
        return {
            'type': 'Point',
            'coordinates': [esri_geometry['x'], esri_geometry['y']]
        }
    
    # If already in GeoJSON format, return as-is
    return esri_geometry

def validate_city_configuration(city_slug):
    """Validate that a city configuration is complete"""
    config = get_city_config(city_slug)
    if not config:
        return False, f"No configuration found for city: {city_slug}"
    
    required_fields = ['city_info', 'file_mappings', 'colors']
    missing_fields = [field for field in required_fields if field not in config]
    
    if missing_fields:
        return False, f"Missing required configuration fields: {missing_fields}"
    
    return True, "Configuration is valid"

# Export commonly used functions
__all__ = [
    'CITY_CONFIGS',
    'get_city_config',
    'get_plu_mapping', 
    'map_plu_code_to_category',
    'get_attribute_mapping',
    'optimize_coordinates',
    'detect_data_format',
    'convert_esri_to_geojson_geometry',
    'validate_city_configuration'
]