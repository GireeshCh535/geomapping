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
        'slug': 'bengaluru',
        'state': 'Karnataka',
        'center_lat': 12.9716,
        'center_lng': 77.5946,
    },
    'data_format': 'ESRI_JSON',
    'coordinate_precision': 8,
    'plu_mapping': BANGALORE_PLU_MAPPING,
    'file_mappings': {
        # Updated with your actual files
        'Agricultural_Land.json': 'AGRICULTURAL',
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
        'slug': 'visakhapatnam',
        'state': 'Andhra Pradesh',
        'center_lat': 17.6868,
        'center_lng': 83.2185,
    },
    'data_format': 'GEOJSON',
    'coordinate_precision': 8,
    
    # File mappings (inferred from category names)
    'file_mappings': {
        'Agricultural_Use_Zone.geojson': 'AGRICULTURAL',
        'Blue_Zone_Water_Bodies.geojson': 'WATER_BODIES',
        'Brown_Zone_Hills.geojson': 'HILLS',
        'Commercial_Use_Zone.geojson': 'COMMERCIAL',
        'Existing_Crematorium_Burial_Ground_Graveyard.geojson': 'CEMETERY',
        'Existing_Educational_Facilities.geojson': 'EDUCATION',
        'Existing_Government_Semi_Government_Facilities.geojson': 'GOVERNMENT',
        'Existing_Health_Facilities.geojson': 'HEALTHCARE',
        'Existing_Industrial_Area.geojson': 'INDUSTRIAL',
        'Existing_Public_Utilities.geojson': 'UTILITIES',
        'Existing_Recreational_Playgrounds_Parks_Layout_OpenSpace.geojson': 'PARKS_GREEN',
        'Existing_Religious_Facilities.geojson': 'CULTURAL',
        'Existing_Road_Railway_Line_Area.geojson': 'TRANSPORT',
        'Existing_Transportation_Facility.geojson': 'TRANSPORT',
        'Green_Zone_Forest.geojson': 'PROTECTED',
        'Kambalakonda_Eco_Sensitive_Zone_NAOB_Buffer_Zoological_Park.geojson': 'PROTECTED',
        'Kambalakonda_WildLife_Sanctuary_Biodiversity_Area.geojson': 'PROTECTED',
        'Mixed_Use_Zone_1.geojson': 'MIXED_USE',
        'Mixed_Use_Zone_2_BAIA.geojson': 'MIXED_USE',
        'Mixed_Use_Zone_3_BAIA.geojson': 'MIXED_USE',
        'Mixed_Use_Zone_4_BAIA.geojson': 'MIXED_USE',
        'Proposed_Industrial_Use_Zone.geojson': 'INDUSTRIAL',
        'Proposed_PSP_Use_Zone.geojson': 'PUBLIC',
        'Proposed_Public_Utilities_Use_Zone.geojson': 'UTILITIES',
        'Proposed_Recreational_Use_Zone.geojson': 'PARKS_GREEN',
        'Proposed_Road_Network.geojson': 'TRANSPORT',
        'Proposed_Transportation_Facility_Use_Zone.geojson': 'TRANSPORT',
        'Residential_Use_Zone.geojson': 'RESIDENTIAL',
        'Sea_River_Accreted_Land.geojson': 'WATER_BODIES',
        'Special_Area_Use_Zone.geojson': 'SPECIAL',
        'Water_Body_Buffer.geojson': 'WATER_BODIES',
    },
    
    # Attribute mappings to match your data structure
    'attribute_mappings': {
        'FID': 'source_fid',
        'Category': 'land_use_type',
        'Category': 'category_name',
        'MANDAL': 'mandal',
        'DISTRICT': 'district',
        'Village': 'village',
        'Shape_Area': 'source_area_value',
        'Shape_Length': 'source_length_value',
        'RuleID': 'rule_id',
        'Override': 'override_value',
    },
    
    # Complete category mappings - maps Category field values to standard categories
    'category_mappings': {
        'Agricultural Use Zone': 'AGRICULTURAL',
        'Blue Zone (Water Bodies)': 'WATER_BODIES',
        'Brown Zone (Hills)': 'HILLS',
        'Commercial Use Zone': 'COMMERCIAL',
        'Existing Crematorium / Burial Ground / Graveyard': 'CEMETERY',
        'Existing Educational Facilities': 'EDUCATION',
        'Existing Government & Semi Government Facilities': 'GOVERNMENT',
        'Existing Health Facilities': 'HEALTHCARE',
        'Existing Industrial Area': 'INDUSTRIAL',
        'Existing Public Utilities': 'UTILITIES',
        'Existing Recreational, Play grounds, Parks & Layout Open Space': 'PARKS_GREEN',
        'Existing Religious Facilities': 'CULTURAL',
        'Existing Road & Railway Line Area': 'TRANSPORT',
        'Existing Transportation Facility': 'TRANSPORT',
        'Green Zone (Forest)': 'PROTECTED',
        'Kambalakonda Eco Sensitive Zone/ NAOB Buffer, Zoological Park': 'PROTECTED',
        'Kambalakonda WildLife Sanctuary & Biodiversity Area': 'PROTECTED',
        'Mixed Use Zone - 1': 'MIXED_USE',
        'Mixed Use Zone - 2 (BAIA)': 'MIXED_USE',
        'Mixed Use Zone - 3 (BAIA)': 'MIXED_USE',
        'Mixed Use Zone - 4 (BAIA)': 'MIXED_USE',
        'Proposed Industrial Use Zone': 'INDUSTRIAL',
        'Proposed PSP Use Zone': 'PUBLIC',
        'Proposed Public Utilities Use Zone': 'UTILITIES',
        'Proposed Recreational Use Zone': 'PARKS_GREEN',
        'Proposed Road Network': 'TRANSPORT',
        'Proposed Transportation Facility Use Zone': 'TRANSPORT',
        'Residential Use Zone': 'RESIDENTIAL',
        'Sea / River Accreted Land': 'WATER_BODIES',
        'Special Area Use Zone': 'SPECIAL',
        'Water Body Buffer': 'WATER_BODIES',
    },
    
    # Colors based on your specifications (using solid fill colors)
    'colors': {
        'AGRICULTURAL': '#D3FFBE',       # Agricultural Use Zone
        'WATER_BODIES': '#73FFDF',       # Blue Zone Water Bodies  
        'HILLS': '#A87000',              # Brown Zone Hills
        'COMMERCIAL': '#004DA8',         # Commercial Use Zone
        'CEMETERY': '#FFFFFF',           # Existing Crematorium (solid fill)
        'EDUCATION': '#FF0000',          # Existing Educational (solid fill)
        'GOVERNMENT': '#FF0000',         # Existing Government Semi Government
        'HEALTHCARE': '#FF0000',         # Existing Health (solid fill)
        'INDUSTRIAL': '#C500FF',         # Existing Industrial Area
        'UTILITIES': '#FF7F7F',          # Existing Public Utilities (solid fill)
        'PARKS_GREEN': '#55FF00',        # Existing Recreational
        'CULTURAL': '#FF0000',           # Existing Religious (solid fill)
        'TRANSPORT': '#686868',          # Existing Transportation Facility
        'PROTECTED': '#00734C',          # Green Zone Forest
        'MIXED_USE': '#FFAA00',          # Mixed Use Zone 1
        'PUBLIC': '#FF0000',             # Proposed PSP (hatch fill color)
        'SPECIAL': '#FFFFFF',            # Special Area (solid fill)
        'RESIDENTIAL': '#FFFF73',
    },
    
    # Detailed colors for specific subcategories (optional - for future use)
    'detailed_colors': {
        'Agricultural Use Zone': '#D3FFBE',
        'Blue Zone (Water Bodies)': '#73FFDF',
        'Brown Zone (Hills)': '#A87000',
        'Commercial Use Zone': '#004DA8',
        'Existing Crematorium / Burial Ground / Graveyard': '#FFFFFF',
        'Existing Educational Facilities': '#FF0000',
        'Existing Government & Semi Government Facilities': '#FF0000',
        'Existing Health Facilities': '#FF0000',
        'Existing Industrial Area': '#C500FF',
        'Existing Public Utilities': '#FF7F7F',
        'Existing Recreational, Play grounds, Parks & Layout Open Space': '#55FF00',
        'Existing Religious Facilities': '#FF0000',
        'Existing Road & Railway Line Area': '#828282',
        'Existing Transportation Facility': '#686868',
        'Green Zone (Forest)': '#00734C',
        'Kambalakonda Eco Sensitive Zone/ NAOB Buffer': '#D7C29E',
        'Kambalakonda WildLife Sanctuary & Biodiversity Area': '#38A800',
        'Mixed Use Zone - 1': '#FFAA00',
        'Mixed Use Zone - 2 (BAIA)': '#FFD37F',
        'Mixed Use Zone - 3 (BAIA)': '#E69800',
        'Mixed Use Zone - 4 (BAIA)': '#FFAA00',
        'Proposed Industrial Use Zone': '#C500FF',
        'Proposed PSP Use Zone': '#FF0000',
        'Proposed Public Utilities Use Zone': '#F57A7A',
        'Proposed Recreational Use Zone': '#4C7300',
        'Proposed Road Network': '#000000',
        'Proposed Transportation Facility Use Zone': '#343434',
        'Residential Use Zone': '#FFFF73',
        'Sea / River Accreted Land': '#D7C29E',
        'Special Area Use Zone': '#FFFFFF',
        'Water Body Buffer': '#4CE600',
    }
}

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
    
    'category_mappings': {
        'C1 -Mixed use zone': 'MIXED_USE',                    # 16 features
        'C2- General commercial zone': 'COMMERCIAL',          # 29801 features
        'C3-Neighbourhood centre zone': 'COMMERCIAL',         # 121 features
        'C4-Town centre zone': 'COMMERCIAL',                  # 24 features
        'C5-Regional centre zone': 'COMMERCIAL',              # 13 features
        'C6-Central business district zone': 'COMMERCIAL',    # 13 features
        'Commercial Vacant': 'COMMERCIAL',                    # 2710 features
        
        'I1-Business park zone': 'INDUSTRIAL',                # 4 features
        'I2-Logistics zone': 'INDUSTRIAL',                    # 5 features
        'I3-Non polluting industry zone': 'INDUSTRIAL',       # 12 features
        
        'R1-Village planning zone': 'RESIDENTIAL',            # 187 features (Note: different from your list!)
        'R3-Medium to high density zone': 'RESIDENTIAL',      # 43874 features
        'R4-High density zone': 'RESIDENTIAL',                # 7 features
        'RAA': 'RESIDENTIAL',                                  # 39 features
        'Residential Vacant': 'RESIDENTIAL',                  # 5323 features
        'SR2 Low Density Housing': 'RESIDENTIAL',             # 6 features
        'SR4 - High Density Private': 'RESIDENTIAL',          # 11 features
        
        'P1-Passive zone': 'PROTECTED',                       # 757 features
        'P2-Active zone': 'PROTECTED',                        # 1144 features
        'P3-Protected zone': 'PROTECTED',                     # 210 features
        'P3-Protected zone Hills': 'PROTECTED',               # 6 features
        'SP1- Passive Zone': 'PROTECTED',                     # 33 features
        'SP2- Active Zone': 'PROTECTED',                      # 54 features
        'SP3-Protected Zone': 'PROTECTED',                    # 7 features
        'PGN-G': 'PARKS_GREEN',                               # 1090 features
        'PGN-V': 'PARKS_GREEN',                               # 658 features
        
        'SS1 - Government Zone': 'GOVERNMENT',                # 13 features
        'SS2a- Education Zone': 'EDUCATION',                  # 17 features
        'SS2b Cultural Zone': 'CULTURAL',                     # 19 features
        'SS2c Health Zone': 'HEALTHCARE',                     # 2 features
        'S2-Education zone': 'EDUCATION',                     # 400 features
        'SS3 - Special Zone': 'SPECIAL',                      # 10 features
        'S3-Special zone': 'SPECIAL',                         # 167 features
        
        'SC1a-Mixed Use': 'MIXED_USE',                        # 80 features
        'SC1b - Mixed Use': 'MIXED_USE',                      # 20 features
        
        'SU1-Reserve Zone': 'UTILITIES',                      # 27 features
        'SU2 - Road Network': 'TRANSPORT',                    # 13 features
        'U1-Reserve zone': 'UTILITIES',                       # 548 features
        'U2- Road reserve zone': 'TRANSPORT',                 # 3160 features
        
        'Burial Ground': 'CEMETERY',                          # 4 features
    },
    
    'file_mappings': {
        # Commercial zones
        'C1__Mixed_use_zone.geojson': 'MIXED_USE',
        'C2__General_commercial_zone.geojson': 'COMMERCIAL',
        'C3_Neighbourhood_centre_zone.geojson': 'COMMERCIAL',
        'C4_Town_centre_zone.geojson': 'COMMERCIAL',
        'C5_Regional_centre_zone.geojson': 'COMMERCIAL',
        'C6_Central_business_district_zone.geojson': 'COMMERCIAL',
        'Commercial_Vacant.geojson': 'COMMERCIAL',
        
        'I1_Business_park_zone.geojson': 'INDUSTRIAL',
        'I2_Logistics_zone.geojson': 'INDUSTRIAL',
        'I3_Non_polluting_industry_zone.geojson': 'INDUSTRIAL',
        
        'R1_Village_planning_zone.geojson': 'RESIDENTIAL',
        'R3_Medium_to_high_density_zone.geojson': 'RESIDENTIAL',
        'R4_High_density_zone.geojson': 'RESIDENTIAL',
        'RAA.geojson': 'RESIDENTIAL',
        'Residential_Vacant.geojson': 'RESIDENTIAL',
        'SR2_Low_Density_Housing.geojson': 'RESIDENTIAL',
        'SR4___High_Density_Private.geojson': 'RESIDENTIAL',
        
        'P1_Passive_zone.geojson': 'PROTECTED',
        'P2_Active_zone.geojson': 'PROTECTED',
        'P3_Protected_zone.geojson': 'PROTECTED',
        'P3_Protected_zone_Hills.geojson': 'HILLS',
        'SP1__Passive_Zone.geojson': 'PROTECTED',
        'SP2__Active_Zone.geojson': 'PROTECTED',
        'SP3_Protected_Zone.geojson': 'PROTECTED',
        'PGN_G.geojson': 'PARKS_GREEN',
        'PGN_V.geojson': 'PARKS_GREEN',
        
        'SS1___Government_Zone.geojson': 'GOVERNMENT',
        'SS2a__Education_Zone.geojson': 'EDUCATION',
        'SS2b_Cultural_Zone.geojson': 'CULTURAL',
        'SS2c_Health_Zone.geojson': 'HEALTHCARE',
        'S2_Education_zone.geojson': 'EDUCATION',
        'SS3___Special_Zone.geojson': 'SPECIAL',
        'S3_Special_zone.geojson': 'SPECIAL',
        
        'SC1a_Mixed_Use.geojson': 'MIXED_USE',
        'SC1b___Mixed_Use.geojson': 'MIXED_USE',
        
        'SU1_Reserve_Zone.geojson': 'UTILITIES',
        'SU2___Road_Network.geojson': 'TRANSPORT',
        'U1_Reserve_zone.geojson': 'UTILITIES',
        'U2__Road_reserve_zone.geojson': 'TRANSPORT',
        
        'Burial_Ground.geojson': 'CEMETERY',
    },
    
    'attribute_mappings': {
        'OBJECTID': 'source_object_id',
        'plot_code': 'name',
        'symbology': 'land_use_type',  # Key field for categorization
        'alloted_ex': 'source_area_value',
        'plot_no': 'plot_number',
        'plot_categ': 'plot_category',
        'township': 'township',
        'sector': 'sector',
        'colony': 'colony',
        'Shape_Length': 'source_length_value',
        'Shape_Area': 'calculated_area',
    },
    
    # Color scheme for Amaravati
    'colors': {
        'RESIDENTIAL': '#8BC34A',      # Light Green
        
        'COMMERCIAL': '#2196F3',       # Blue
        'MIXED_USE': '#9C27B0',        # Purple
        
        'INDUSTRIAL': '#FF9800',       # Orange
        
        'GOVERNMENT': '#F44336',       # Red
        'PUBLIC': '#E91E63',           # Pink
        'EDUCATION': '#3F51B5',        # Indigo
        'HEALTHCARE': '#009688',       # Teal
        'CULTURAL': '#673AB7',         # Deep Purple
        
        'TRANSPORT': '#607D8B',        # Blue Grey
        'UTILITIES': '#795548',        # Brown
        
        'PROTECTED': '#4CAF50',        # Green
        'PARKS_GREEN': '#8BC34A',      # Light Green
        'WATER_BODIES': '#03A9F4',     # Light Blue
        
        'CEMETERY': '#9E9E9E',         # Grey
        'SPECIAL': '#FFEB3B',          # Yellow
        'UNCLASSIFIED': '#CFD8DC',     # Light Blue Grey
    }
}

HYDERABAD_CONFIG = {
    'city_info': {
        'name': 'Hyderabad',
        'slug': 'hyderabad',
        'state': 'Telangana',
        'center_lat': 17.385044,
        'center_lng': 78.486671,
    },
    'data_format': 'MIXED',  # We have both GeoJSON and Shapefiles
    'coordinate_precision': 8,
    
    # Layer Groups configuration
    'layer_groups': {
        'transport': {
            'name': 'Transportation',
            'slug': 'transport',
            'category': 'TRANSPORT',
            'description': 'Transportation infrastructure including metro, highways, RRR, and masterplan roads',
            'directory_path': 'data/hyderabad',
            'default_color': '#607D8B',  # Blue Grey
            'layers': {
                'hyd_metro_stations_ph1&2': {
                    'file': 'Hyd_metro_stations_ph1&2.geojson',
                    'name': 'Metro Stations',
                    'color': '#F44336',  # Red
                    'metadata': {
                        'lines': [
                            {'name': 'Metro Phase 1 Existing Green Line', 'status': 'Existing', 'color': 'Green', 'from': 'JBS Parade Ground', 'to': 'MG Bus Station'},
                            {'name': 'Metro Phase 1 Existing Blue Line', 'status': 'Existing', 'color': 'Blue', 'from': 'Nagole', 'to': 'Raidurg'},
                            {'name': 'Metro Phase 1 Existing Red Line', 'status': 'Existing', 'color': 'Red', 'from': 'Miyapur', 'to': 'L.B. Nagar'},
                            {'name': 'Metro Phase 2 A Upcoming Green Line', 'status': 'Upcoming', 'color': 'Green', 'from': 'MG Bus Station', 'to': 'Chandrayangutta'},
                            {'name': 'Metro Phase 2 A Upcoming Purple Line', 'status': 'Upcoming', 'color': 'Purple', 'from': 'Nagole', 'to': 'RGIA Shamshabad'},
                            {'name': 'Metro Phase 2 B Upcoming Future City Line', 'status': 'Upcoming', 'color': 'Future City', 'from': 'RGIA Shamshabad', 'to': 'Future City'},
                            {'name': 'Metro Phase 2 B Upcoming Blue Line', 'status': 'Upcoming', 'color': 'Blue', 'from': 'JBS Parade Ground', 'to': 'Shamirpet'},
                            {'name': 'Metro Phase 2 B Upcoming Green Line', 'status': 'Upcoming', 'color': 'Green', 'from': 'Paradise', 'to': 'Medchal'},
                        ]
                    }
                },
                'hyd_metro_lines_ph_1&2_final': {
                    'file': 'Hyd_metro_lines_ph_1&2_Final.geojson',
                    'name': 'Metro Lines',
                    'color': '#4CAF50',  # Green
                },
                'hyd_highways_merged': {
                    'file': 'hyd_highways_merged.geojson',
                    'name': 'Highways',
                    'color': '#2196F3',  # Blue
                    'metadata': {
                        'highways': [
                            {'name': 'Mumbai Highway', 'notation': 'NH 65 (West)', 'endpoints': 'Hyderabad to Mumbai', 'width': '4 Lane'},
                            {'name': 'Bangalore Highway', 'notation': 'NH 44 (South)', 'endpoints': 'Hyderabad to Bangalore', 'width': '4 Lane'},
                            {'name': 'Srisailam Highway', 'notation': 'NH 765 (South)', 'endpoints': 'Hyderabad to Srisailam', 'width': '2 Lane'},
                            {'name': 'Medak Highway', 'notation': 'NH 765D (North)', 'endpoints': 'Hyderabad to Medak', 'width': '2 Lane'},
                            {'name': 'Vijaywada Highway', 'notation': 'NH65 (East)', 'endpoints': 'Hyderabad to Vijaywada', 'width': '4 Lane'},
                            {'name': 'Warangal Highway', 'notation': 'NH 163 (East)', 'endpoints': 'Hyderabad to Warangal', 'width': '4 Lane'},
                            {'name': 'Chevella Highway', 'notation': 'NH 163 (West)', 'endpoints': 'Hyderabad to Chevella', 'width': '2 Lane'},
                            {'name': 'Nagpur Highway', 'notation': 'NH 44 (North)', 'endpoints': 'Hyderabad to Nagpur', 'width': '4 Lane'},
                            {'name': 'Karimnagar Highway', 'notation': 'SH 1', 'endpoints': 'Hyderabad to Karimnagar', 'width': '4 Lane'},
                            {'name': 'Nagarjuna Sagar Highway', 'notation': 'SH 19', 'endpoints': 'Hyderabad to Nagarjuna Sagar', 'width': '2 Lane'},
                        ]
                    }
                },
                'rrr_final': {
                    'file': 'RRR_Final.geojson',
                    'name': 'Regional Ring Road',
                    'color': '#9C27B0',  # Purple
                    'metadata': {
                        'rrr': [
                            {'name': 'Proposed Hyderabad Regional Ring Road - Northern Part', 'notation': 'RRR North', 'alignment': 'Finalised', 'status': 'Finalised', 'width': '6 Lane'},
                            {'name': 'Proposed Hyderabad Regional Ring Road - Southern Part', 'notation': 'RRR South', 'alignment': 'Yet to be finalised', 'status': 'Yet to be finalised', 'width': '6 Lane'},
                        ]
                    }
                },
                'hmda_masterplan_roads_merged': {
                    'file': 'HMDA_masterplan_roads_merged.geojson',
                    'name': 'HMDA Masterplan Roads',
                    'color': '#FF9800',  # Orange
                    'metadata': {
                        'roads': [
                            {'name': 'Proposed Masterplan Road', 'width_m': 18},
                            {'name': 'Proposed Masterplan Road', 'width_m': 30},
                            {'name': 'Proposed Masterplan Road', 'width_m': 45},
                            {'name': 'Proposed Masterplan Road', 'width_m': 90},
                        ]
                    }
                },
            }
        },
        'economic': {
            'name': 'Economic Zones',
            'slug': 'economic',
            'category': 'INDUSTRIAL',
            'description': 'Special Economic Zones and industrial areas',
            'directory_path': 'data/hyderabad',
            'default_color': '#FF9800',  # Orange
            'layers': {
                'hyd_sezs_final': {
                    'file': 'Hyd_SEZs_Final.geojson',
                    'name': 'Special Economic Zones',
                    'color': '#FF9800',  # Orange
                    'metadata': {
                        'sezs': [
                            {'name': 'Adibatla Aerospace Park', 'industry': 'Aerospace & Precision Engineering', 'employment_type': 'White Collar', 'employees': 5000, 'size': '339 acres', 'polluting': 'No'},
                            {'name': 'Adibatla Aerospace SEZ', 'industry': 'Aerospace & Precision Engineering', 'employment_type': 'White Collar', 'employees': 27000, 'size': '500 acres', 'polluting': 'No'},
                            {'name': 'Industrial Park Nadergul', 'industry': 'Aerospace & Precision Engineering', 'employment_type': 'Blue Collar', 'employees': 35000, 'size': '602 acres', 'polluting': 'No'},
                            {'name': 'Industrial Park Ramachandrapuram', 'industry': 'Automobile', 'employment_type': 'Blue Collar', 'employees': '2000 - 4000', 'size': '', 'polluting': 'No'},
                            {'name': 'Auto Nagar Hyderabad', 'industry': 'Automobile', 'employment_type': 'Blue Collar', 'employees': '', 'size': '54 acres', 'polluting': 'No'},
                            {'name': 'Industrial Park Banda Mailaram', 'industry': 'Seed Processing Industry', 'employment_type': 'Blue Collar', 'employees': '', 'size': '370 acres', 'polluting': 'No'},
                            {'name': 'Industrial Park Banda Thimmapur', 'industry': 'Food processing & FMCG', 'employment_type': 'Blue Collar', 'employees': 410, 'size': '49 acres', 'polluting': 'No'},
                            {'name': 'Industrial Park Toopran', 'industry': 'Multi - Industry', 'employment_type': 'Blue Collar', 'employees': '50000 - 60000', 'size': '737.3 acres', 'polluting': 'Yes'},
                            {'name': 'Chandanvelly Industrial Park SEZ', 'industry': 'Multi - Industry', 'employment_type': 'Blue Collar', 'employees': 12000, 'size': '1569.89 acres', 'polluting': 'Yes'},
                            {'name': 'Chandulal Baradari Industrial Park', 'industry': 'Multi - Industry', 'employment_type': 'Blue Collar', 'employees': 250, 'size': '25.82 acres', 'polluting': 'Yes'},
                            {'name': 'Cherlapally Industrial Area', 'industry': 'Multi - Industry', 'employment_type': 'Blue Collar', 'employees': '40000+', 'size': '120 acres', 'polluting': 'Yes'},
                            {'name': 'Green Industrial Park Dandumalkapur', 'industry': 'Multi - Industry', 'employment_type': 'Blue Collar', 'employees': 35000, 'size': '2000 acres', 'polluting': 'No'},
                            {'name': 'Electronic City SEZ', 'industry': 'Electronics', 'employment_type': 'White Collar', 'employees': 2500, 'size': '1000 acres', 'polluting': 'No'},
                        ]
                    }
                }
            }
        },
        'administrative': {
            'name': 'Administrative Boundaries',
            'slug': 'administrative',
            'category': 'GOVERNMENT',
            'description': 'City boundaries and administrative zones',
            'directory_path': 'data/hyderabad/FutureCityHyderabad_Boundary',
            'default_color': '#F44336',  # Red
            'layers': {
                'future_city': {
                    'file': 'FutureCityHyderabad_Boundary.shp',
                    'name': 'Future City Boundary',
                    'color': '#2196F3',  # Blue
                }
            }
        },
        'villages': {
            'name': 'Village Boundaries',
            'slug': 'villages',
            'category': 'GOVERNMENT',
            'description': 'HMDA boundary and village boundaries',
            'directory_path': 'data/hyderabad/FCDA_Boundary_Villages',
            'default_color': '#8BC34A',  # Light Green
            'layers': {
                'hmda_boundary': {
                    'file': 'HMDA_Boundary.geojson',
                    'name': 'HMDA Boundary',
                    'color': '#388E3C',  # Dark Green
                },
                'hmda_villages_clip': {
                    'file': 'HMDA_Villages_Clip.geojson',
                    'name': 'HMDA Villages',
                    'color': '#C8E6C9',  # Light Green
                }
            }
        }
    },
    
    # Colors for different categories
    'colors': {
        'TRANSPORT': '#607D8B',      # Blue Grey
        'INDUSTRIAL': '#FF9800',     # Orange
        'GOVERNMENT': '#F44336',     # Red
        'COMMERCIAL': '#2196F3',     # Blue
        'RESIDENTIAL': '#8BC34A',    # Light Green
        'SPECIAL': '#9C27B0',        # Purple
    },
    'file_mappings': {
        'Hyd_metro_stations_ph1&2.geojson': 'TRANSPORT',
        'Hyd_metro_lines_ph_1&2_Final.geojson': 'TRANSPORT',
        'hyd_highways_merged.geojson': 'TRANSPORT',
        'RRR_Final.geojson': 'TRANSPORT',
        'HMDA_masterplan_roads_merged.geojson': 'TRANSPORT',
        'Hyd_SEZs_Final.geojson': 'INDUSTRIAL',
        'FutureCityHyderabad_Boundary.shp': 'GOVERNMENT',
        'HMDA_Boundary.geojson': 'GOVERNMENT',
        'HMDA_Villages_Clip.geojson': 'GOVERNMENT',
    },
    # Attribute mappings for key layers (can be expanded as needed)
    'attribute_mappings': {
        # Highways
        'highways': {
            'Name': 'name',
            'Notation': 'notation',
            'End to End points': 'endpoints',
            'Width': 'width',
        },
        # RRR
        'rrr': {
            'Name': 'name',
            'Notation': 'notation',
            'Alignment': 'alignment',
            'Status': 'status',
            'Width': 'width',
        },
        # HMDA Roads
        'hmda_roads': {
            'Name': 'name',
            'Road width ( in meters )': 'width_m',
        },
        # Metro
        'metro': {
            'Name': 'name',
            'Status': 'status',
            'Line Colour': 'color',
            'From Junction': 'from',
            'To Junction': 'to',
        },
        # SEZs
        'sez': {
            'Name': 'name',
            'Industry': 'industry',
            'Primary Employment Type': 'employment_type',
            'No. of Employees': 'employees',
            'Size': 'size',
            'Polluting': 'polluting',
        },
    },
}

WARANGAL_PLU_MAPPING = {
    'Agriculture': {
        'category': 'AGRICULTURAL',
        'description': 'Agricultural land use',
        'secondary_codes': [],
        'examples': ['Agricultural areas', 'Farming land']
    },
    'Air Strip': {
        'category': 'TRANSPORT',
        'description': 'Air strip/Airport facilities',
        'secondary_codes': [],
        'examples': ['Airports', 'Air strips', 'Aviation facilities']
    },
    'Commercial': {
        'category': 'COMMERCIAL',
        'description': 'Commercial land use',
        'secondary_codes': [],
        'examples': ['Shopping areas', 'Business districts', 'Commercial complexes']
    },
    'Forest': {
        'category': 'PROTECTED',
        'description': 'Forest areas',
        'secondary_codes': [],
        'examples': ['Reserved forests', 'Protected forest areas']
    },
    'Growth Corridor': {
        'category': 'SPECIAL',
        'description': 'Designated growth corridor',
        'secondary_codes': [],
        'examples': ['Development corridors', 'Growth zones']
    },
    'Growth Corridor 2': {
        'category': 'SPECIAL',
        'description': 'Secondary growth corridor',
        'secondary_codes': [],
        'examples': ['Secondary development corridors']
    },
    'Heritage': {
        'category': 'CULTURAL',
        'description': 'Heritage conservation areas',
        'secondary_codes': [],
        'examples': ['Historical sites', 'Heritage buildings', 'Archaeological sites']
    },
    'Hill Buffer': {
        'category': 'PARKS_GREEN',
        'description': 'Hill buffer zones',
        'secondary_codes': [],
        'examples': ['Hill protection zones', 'Buffer areas around hills']
    },
    'Hillocks': {
        'category': 'PROTECTED',
        'description': 'Protected hillock areas',
        'secondary_codes': [],
        'examples': ['Small hills', 'Rocky outcrops', 'Protected hillocks']
    },
    'Industrial': {
        'category': 'INDUSTRIAL',
        'description': 'Industrial land use',
        'secondary_codes': [],
        'examples': ['Manufacturing areas', 'Industrial estates', 'Factories']
    },
    'Mixed Use': {
        'category': 'MIXED_USE',
        'description': 'Mixed use development',
        'secondary_codes': [],
        'examples': ['Residential-commercial mix', 'Multi-purpose developments']
    },
    'Public & Semi-Public': {
        'category': 'PUBLIC',
        'description': 'Public and semi-public facilities',
        'secondary_codes': [],
        'examples': ['Government buildings', 'Public institutions', 'Semi-public facilities']
    },
    'Public Utilities': {
        'category': 'UTILITIES',
        'description': 'Public utility infrastructure',
        'secondary_codes': [],
        'examples': ['Power stations', 'Water treatment', 'Waste management']
    },
    'Railway Land': {
        'category': 'TRANSPORT',
        'description': 'Railway infrastructure',
        'secondary_codes': [],
        'examples': ['Railway tracks', 'Railway stations', 'Railway yards']
    },
    'Recreational': {
        'category': 'PARKS_GREEN',
        'description': 'Recreational facilities',
        'secondary_codes': [],
        'examples': ['Parks', 'Sports facilities', 'Recreation centers']
    },
    'Residential': {
        'category': 'RESIDENTIAL',
        'description': 'Residential areas',
        'secondary_codes': [],
        'examples': ['Housing areas', 'Residential colonies', 'Neighborhoods']
    },
    'Residential Expansion': {
        'category': 'RESIDENTIAL',
        'description': 'Planned residential expansion areas',
        'secondary_codes': [],
        'examples': ['Future residential zones', 'Residential development areas']
    },
    'Road Buffer': {
        'category': 'TRANSPORT',
        'description': 'Road buffer zones',
        'secondary_codes': [],
        'examples': ['Road side buffers', 'Highway buffers']
    },
    'Transportation': {
        'category': 'TRANSPORT',
        'description': 'Transportation infrastructure',
        'secondary_codes': [],
        'examples': ['Roads', 'Transportation hubs', 'Transit facilities']
    },
    'Water Bodies': {
        'category': 'WATER_BODIES',
        'description': 'Water bodies',
        'secondary_codes': [],
        'examples': ['Lakes', 'Ponds', 'Reservoirs', 'Rivers']
    },
    'Water Body Buffer': {
        'category': 'PARKS_GREEN',
        'description': 'Water body buffer zones',
        'secondary_codes': [],
        'examples': ['Lake buffers', 'River buffers', 'Wetland buffers']
    },
    'Zoological park': {
        'category': 'PARKS_GREEN',
        'description': 'Zoological park',
        'secondary_codes': [],
        'examples': ['Zoo', 'Wildlife park', 'Animal sanctuary']
    }
}

# Warangal Configuration
WARANGAL_CONFIG = {
    'city_info': {
        'name': 'Warangal',
        'slug': 'warangal',
        'state': 'Telangana',
        'center_lat': 17.9689,  # Warangal coordinates
        'center_lng': 79.5941,
    },
    'data_format': 'GEOJSON',
    'coordinate_precision': 8,
    'plu_mapping': WARANGAL_PLU_MAPPING,
    
    # File mappings - mapping filename to category
    'file_mappings': {
        'Agriculture.geojson': 'AGRICULTURAL',
        'AirStrip.geojson': 'TRANSPORT',
        'Commercial.geojson': 'COMMERCIAL',
        'Forest.geojson': 'PROTECTED',
        'GrowthCorridor.geojson': 'SPECIAL',
        'GrowthCorridor2.geojson': 'SPECIAL',
        'Heritage.geojson': 'CULTURAL',
        'HillBuffer.geojson': 'PARKS_GREEN',
        'Hillocks.geojson': 'PROTECTED',
        'Industrial.geojson': 'INDUSTRIAL',
        'MixedUse.geojson': 'MIXED_USE',
        'Public_and_SemiPublic.geojson': 'PUBLIC',
        'PublicUtilities.geojson': 'UTILITIES',
        'RailwayLand.geojson': 'TRANSPORT',
        'Recreational.geojson': 'PARKS_GREEN',
        'Residential.geojson': 'RESIDENTIAL',
        'ResidentialExpansion.geojson': 'RESIDENTIAL',
        'RoadBuffer.geojson': 'TRANSPORT',
        'Transportation.geojson': 'TRANSPORT',
        'Water_Bodies.geojson': 'WATER_BODIES',
        'WaterBodyBuffer.geojson': 'PARKS_GREEN',
        'ZoologicalPark.geojson': 'PARKS_GREEN',
    },
    
    # Colors - converted from your provided colors
    'colors': {
        'AGRICULTURAL': '#D3FFBE',
        'TRANSPORT': '#B2B2B2',  # Using Transportation color as default for transport
        'COMMERCIAL': '#0070FF',
        'PROTECTED': '#267300',  # Using Forest color for protected areas
        'SPECIAL': '#FFBEE8',    # Using Growth Corridor color
        'CULTURAL': '#FFA77F',   # Using Heritage solid fill color
        'PARKS_GREEN': '#55FF00', # Using Recreational color
        'INDUSTRIAL': '#C500FF',
        'MIXED_USE': '#FFAA00',
        'PUBLIC': '#FF0000',
        'UTILITIES': '#E69800',  # Using Public Utilities solid fill color
        'RESIDENTIAL': '#FFFF00',
        'WATER_BODIES': '#00C5FF',
        'GOVERNMENT': '#FF0000', # Same as public
        'EDUCATION': '#FF0000',   # Same as public
        'HEALTHCARE': '#FF0000',  # Same as public
        'DEFENSE': '#666666',     # Default
        'HIGH_TECH': '#C500FF',   # Same as industrial
        'DRAINS': '#00C5FF',      # Same as water bodies
        'HILLS': '#A87000',       # Using Hillocks color
        'CEMETERY': '#55FF00',    # Same as parks/green
        'UNCLASSIFIED': '#CCCCCC'
    },
    
    # Attribute mappings for Warangal (based on your sample data structure)
    'attribute_mappings': {
        'land_use_fields': {
            'PLU Code': 'plu_code',
            'PLU': 'plu_name',
            'PLU_NAME': 'plu_category',
            'Name': 'name',
            'Area': 'area',
            'OBJECTID': 'object_id',
        },
        'geometry_fields': {
            'Area': 'area',
            'Shape_Length': 'perimeter',
            'Shape_Area': 'shape_area',
        },
        'metadata_fields': {
            'KUDA': 'authority',
            'ELU': 'existing_land_use',
            'Ex_PR': 'existing_proposed',
            'Category': 'category',
            'Sub_Catego': 'sub_category',
            'Layout': 'layout',
        }
    }
}

DELHI_NAME_MAPPING = {
    'AGRICULTURE': {
        'category': 'AGRICULTURAL',
        'description': 'Agricultural land use',
        'examples': ['Farmland', 'Agricultural areas']
    },
    'AIR CITY': {
        'category': 'TRANSPORT',
        'description': 'Aviation and airport facilities',
        'examples': ['Airport areas', 'Aviation facilities']
    },
    'CITY PARK': {
        'category': 'PARKS_GREEN',
        'description': 'City parks',
        'examples': ['Public parks', 'Urban green spaces']
    },
    'COLD STORAGE': {
        'category': 'INDUSTRIAL',
        'description': 'Cold storage facilities',
        'examples': ['Refrigeration facilities', 'Storage warehouses']
    },
    'COMMUNITY CENTRE': {
        'category': 'PUBLIC',
        'description': 'Community centers',
        'examples': ['Community halls', 'Public meeting spaces']
    },
    'COMMUNITY PARK': {
        'category': 'PARKS_GREEN',
        'description': 'Community parks',
        'examples': ['Neighborhood parks', 'Local green spaces']
    },
    'CULTURAL COMPLEX': {
        'category': 'CULTURAL',
        'description': 'Cultural facilities',
        'examples': ['Cultural centers', 'Arts complexes']
    },
    'DISTRICT CENTRE': {
        'category': 'COMMERCIAL',
        'description': 'District commercial centers',
        'examples': ['Shopping centers', 'Commercial hubs']
    },
    'EDUCATION AND RESEARCH': {
        'category': 'EDUCATION',
        'description': 'Educational and research institutions',
        'examples': ['Schools', 'Universities', 'Research centers']
    },
    'ELECTRICITY (POWER HOUSE SUB STATION)': {
        'category': 'UTILITIES',
        'description': 'Power infrastructure',
        'examples': ['Power stations', 'Electrical substations']
    },
    'FOREIGN MISSION': {
        'category': 'GOVERNMENT',
        'description': 'Foreign diplomatic missions',
        'examples': ['Embassies', 'Consulates']
    },
    'GENERAL BUSINESS': {
        'category': 'COMMERCIAL',
        'description': 'General business areas',
        'examples': ['Business districts', 'Commercial areas']
    },
    'GOVERNMENT LAND': {
        'category': 'GOVERNMENT',
        'description': 'Government owned land',
        'examples': ['Government reserves', 'Public land']
    },
    'GOVERNMET OFFICE': {
        'category': 'GOVERNMENT',
        'description': 'Government offices',
        'examples': ['Administrative buildings', 'Government facilities']
    },
    'HISTORICAL MONUMENTS': {
        'category': 'CULTURAL',
        'description': 'Historical monuments',
        'examples': ['Heritage sites', 'Historical buildings']
    },
    'HOSPITAL': {
        'category': 'HEALTHCARE',
        'description': 'Healthcare facilities',
        'examples': ['Hospitals', 'Medical centers']
    },
    'HOTEL': {
        'category': 'COMMERCIAL',
        'description': 'Hospitality services',
        'examples': ['Hotels', 'Guest houses']
    },
    'INDUSTRY': {
        'category': 'INDUSTRIAL',
        'description': 'Industrial areas',
        'examples': ['Factories', 'Manufacturing units']
    },
    'MANUFACTURING SERVICE AND REPAIR INDUSTRY': {
        'category': 'INDUSTRIAL',
        'description': 'Manufacturing and repair industries',
        'examples': ['Service industries', 'Repair facilities']
    },
    'NON HIERARCHIALCOMMERCIAL CENTRE': {
        'category': 'COMMERCIAL',
        'description': 'Non-hierarchical commercial centers',
        'examples': ['Local commercial areas', 'Mixed commercial zones']
    },
    'PARK': {
        'category': 'PARKS_GREEN',
        'description': 'Parks and green spaces',
        'examples': ['Public parks', 'Recreation areas']
    },
    'PARLIAMENT HOUSE': {
        'category': 'GOVERNMENT',
        'description': 'Parliament facilities',
        'examples': ['Legislative buildings', 'Parliament complex']
    },
    'POLICE': {
        'category': 'GOVERNMENT',
        'description': 'Police facilities',
        'examples': ['Police stations', 'Law enforcement']
    },
    'POLICE HEADQUARTER': {
        'category': 'GOVERNMENT',
        'description': 'Police headquarters',
        'examples': ['Police headquarters', 'Command centers']
    },
    'PRESIDENT HOUSE': {
        'category': 'GOVERNMENT',
        'description': 'Presidential residence',
        'examples': ['Presidential palace', 'Executive residence']
    },
    'REGIONAL PARK': {
        'category': 'PARKS_GREEN',
        'description': 'Regional parks',
        'examples': ['Large parks', 'Regional green areas']
    },
    'RELIGIOUS': {
        'category': 'CULTURAL',
        'description': 'Religious facilities',
        'examples': ['Temples', 'Churches', 'Mosques', 'Religious buildings']
    },
    'RESIDENTIAL AREA': {
        'category': 'RESIDENTIAL',
        'description': 'Residential areas',
        'examples': ['Housing areas', 'Residential colonies']
    },
    'SEWERAGE (TREATMENT PLANT)': {
        'category': 'UTILITIES',
        'description': 'Sewerage treatment facilities',
        'examples': ['Water treatment plants', 'Sewage facilities']
    },
    'SOCIAL CULTURAL': {
        'category': 'CULTURAL',
        'description': 'Social and cultural facilities',
        'examples': ['Social centers', 'Cultural institutions']
    },
    'SOLID WASTE (SANITERY LANDFILL)': {
        'category': 'UTILITIES',
        'description': 'Waste management facilities',
        'examples': ['Landfills', 'Waste treatment']
    },
    'SPECIAL AREA': {
        'category': 'SPECIAL',
        'description': 'Special designated areas',
        'examples': ['Special zones', 'Designated areas']
    },
    'SPORTS': {
        'category': 'PARKS_GREEN',
        'description': 'Sports facilities',
        'examples': ['Sports grounds', 'Athletic facilities']
    },
    'SPORTS CENTRE': {
        'category': 'PARKS_GREEN',
        'description': 'Sports centers',
        'examples': ['Sports complexes', 'Recreation centers']
    },
    'SPORTS FACILITIES': {
        'category': 'PARKS_GREEN',
        'description': 'Sports facilities',
        'examples': ['Sports infrastructure', 'Athletic venues']
    },
    'STADIUM': {
        'category': 'PARKS_GREEN',
        'description': 'Stadiums',
        'examples': ['Sports stadiums', 'Event venues']
    },
    'TERMINAL': {
        'category': 'TRANSPORT',
        'description': 'Transportation terminals',
        'examples': ['Bus terminals', 'Transport hubs']
    },
    'TERMINAL RAIL': {
        'category': 'TRANSPORT',
        'description': 'Railway terminals',
        'examples': ['Railway stations', 'Train terminals']
    },
    'TRANSMISSION CENTRE': {
        'category': 'UTILITIES',
        'description': 'Transmission centers',
        'examples': ['Communication centers', 'Broadcasting facilities']
    },
    'TRANSMISSION SITE': {
        'category': 'UTILITIES',
        'description': 'Transmission sites',
        'examples': ['Communication towers', 'Transmission infrastructure']
    },
    'UNIVERSITY CENTRE': {
        'category': 'EDUCATION',
        'description': 'University centers',
        'examples': ['Higher education', 'University campuses']
    },
    'URBANISABLE AREA': {
        'category': 'SPECIAL',
        'description': 'Areas designated for urbanization',
        'examples': ['Development zones', 'Urban expansion areas']
    },
    'WAREHOUSING': {
        'category': 'INDUSTRIAL',
        'description': 'Warehousing facilities',
        'examples': ['Storage facilities', 'Distribution centers']
    },
    'WASTE LAND': {
        'category': 'UNCLASSIFIED',
        'description': 'Waste land',
        'examples': ['Unused land', 'Barren areas']
    },
    'WATER BODIES': {
        'category': 'WATER_BODIES',
        'description': 'Water bodies',
        'examples': ['Rivers', 'Lakes', 'Ponds']
    },
    'WATER TREATMENT PLANT': {
        'category': 'UTILITIES',
        'description': 'Water treatment facilities',
        'examples': ['Water purification plants', 'Treatment facilities']
    },
    'WHOLE SALE': {
        'category': 'COMMERCIAL',
        'description': 'Wholesale markets',
        'examples': ['Wholesale markets', 'Distribution centers']
    }
}

# Delhi Configuration
DELHI_CONFIG = {
    'city_info': {
        'name': 'Delhi',
        'slug': 'delhi',
        'state': 'Delhi',
        'center_lat': 28.6139,  # New Delhi coordinates
        'center_lng': 77.2090,
    },
    'data_format': 'GEOJSON',
    'coordinate_precision': 8,
    'name_mapping': DELHI_NAME_MAPPING,
    
    # File mappings - mapping filename to category based on NAME field
    'file_mappings': {
        'AGRICULTURE.geojson': 'AGRICULTURAL',
        'AIR_CITY.geojson': 'TRANSPORT',
        'CITY_PARK.geojson': 'PARKS_GREEN',
        'COLD_STORAGE.geojson': 'INDUSTRIAL',
        'COMMUNITY_CENTRE.geojson': 'PUBLIC',
        'COMMUNITY_PARK.geojson': 'PARKS_GREEN',
        'CULTURAL_COMPLEX.geojson': 'CULTURAL',
        'DISTRICT_CENTRE.geojson': 'COMMERCIAL',
        'EDUCATION_AND_RESEARCH.geojson': 'EDUCATION',
        'ELECTRICITY__POWER_HOUSE_SUB_STATION__.geojson': 'UTILITIES',
        'FOREIGN_MISSION.geojson': 'GOVERNMENT',
        'GENERAL_BUSINESS.geojson': 'COMMERCIAL',
        'GOVERNMENT_LAND.geojson': 'GOVERNMENT',
        'GOVERNMET_OFFICE.geojson': 'GOVERNMENT',
        'HISTORICAL_MONUMENTS.geojson': 'CULTURAL',
        'HOSPITAL.geojson': 'HEALTHCARE',
        'HOTEL.geojson': 'COMMERCIAL',
        'INDUSTRY.geojson': 'INDUSTRIAL',
        'MANUFACTURING_SERVICE_AND_REPAIR_INDUSTRY.geojson': 'INDUSTRIAL',
        'NON_HIERARCHIALCOMMERCIAL_CENTRE.geojson': 'COMMERCIAL',
        'PARK.geojson': 'PARKS_GREEN',
        'PARLIAMENT_HOUSE.geojson': 'GOVERNMENT',
        'POLICE.geojson': 'GOVERNMENT',
        'POLICE_HEADQUARTER.geojson': 'GOVERNMENT',
        'PRESIDENT_HOUSE.geojson': 'GOVERNMENT',
        'REGIONAL_PARK.geojson': 'PARKS_GREEN',
        'RELIGIOUS.geojson': 'CULTURAL',
        'RESIDENTIAL_AREA.geojson': 'RESIDENTIAL',
        'SEWERAGE__TREATMENT_PLANT__.geojson': 'UTILITIES',
        'SOCIAL_CULTURAL.geojson': 'CULTURAL',
        'SOLID_WASTE__SANITERY_LANDFILL__.geojson': 'UTILITIES',
        'SPECIAL_AREA.geojson': 'SPECIAL',
        'SPORTS.geojson': 'PARKS_GREEN',
        'SPORTS_CENTRE.geojson': 'PARKS_GREEN',
        'SPORTS_FACILITIES.geojson': 'PARKS_GREEN',
        'STADIUM.geojson': 'PARKS_GREEN',
        'TERMINAL.geojson': 'TRANSPORT',
        'TERMINAL_RAIL_.geojson': 'TRANSPORT',
        'TRANSMISSION_CENTRE.geojson': 'UTILITIES',
        'TRANSMISSION_SITE.geojson': 'UTILITIES',
        'UNIVERSITY_CENTRE.geojson': 'EDUCATION',
        'URBANISABLE_AREA.geojson': 'SPECIAL',
        'WAREHOUSING.geojson': 'INDUSTRIAL',
        'WASTE_LAND.geojson': 'UNCLASSIFIED',
        'WATER_BODIES.geojson': 'WATER_BODIES',
        'WATER_TREATMENT_PLANT.geojson': 'UTILITIES',
        'WHOLE_SALE.geojson': 'COMMERCIAL',
    },
    
    # Colors - using the hex codes you provided
    'colors': {
        'AGRICULTURAL': '#005CE6',        # Agriculture
        'TRANSPORT': '#FFFFFF',           # Air City, Terminal, Terminal Rail
        'PARKS_GREEN': '#4CE600',         # City Park, Community Park, Park, Regional Park, Sports, Sports Centre, Sports Facilities, Stadium
        'INDUSTRIAL': '#8400A8',          # Cold Storage, Industry, Manufacturing Service And Repair Industry, Warehousing
        'PUBLIC': '#FF0000',              # Community Centre
        'CULTURAL': '#4CE600',            # Cultural Complex, Historical Monuments, Religious, Social Cultural
        'COMMERCIAL': '#FF0000',          # District Centre, General Business, Hotel, Non Hierarchical Commercial Centre, Whole Sale
        'EDUCATION': '#005CE6',           # Education And Research, University Centre
        'UTILITIES': '#FFFFFF',           # Electricity, Sewerage, Solid Waste, Transmission Centre, Transmission Site, Water Treatment Plant
        'GOVERNMENT': '#FFFFFF',          # Foreign Mission, Government Land, Government Office, Parliament House, Police, Police Headquarter, President House
        'HEALTHCARE': '#005CE6',          # Hospital
        'RESIDENTIAL': '#FFFF00',         # Residential Area
        'WATER_BODIES': '#73B2FF',        # Water Bodies
        'SPECIAL': '#7AF5CA',             # Special Area, Urbanisable Area
        'UNCLASSIFIED': '#000000',        # Waste Land
        # Fallback colors
        'MIXED_USE': '#FFAA00',
        'PROTECTED': '#267300',
        'DEFENSE': '#666666',
        'HIGH_TECH': '#C500FF',
        'DRAINS': '#00C5FF',
        'HILLS': '#A87000',
        'CEMETERY': '#55FF00',
    },
    
    # Attribute mappings for Delhi (based on your sample data structure)
    'attribute_mappings': {
        'land_use_fields': {
            'NAME': 'name',
            'fid': 'source_fid',
            'AREA_SQMTR': 'area_sqmtr',
            'COLOR': 'original_color',
        },
        'geometry_fields': {
            'AREA_SQMTR': 'area',
        },
        'metadata_fields': {
            'fid': 'source_object_id',
        }
    }
}

GURGAON_CLASSTEXT_MAPPING = {
    '100 Residential (Group Housing/Plotted)': {
        'category': 'RESIDENTIAL',
        'description': 'Residential areas with group housing and plotted development',
        'examples': ['Group housing', 'Plotted development', 'Housing societies']
    },
    '200 Commercial': {
        'category': 'COMMERCIAL',
        'description': 'Commercial areas',
        'examples': ['Shopping centers', 'Business districts', 'Commercial complexes']
    },
    '300 Industrial': {
        'category': 'INDUSTRIAL',
        'description': 'Industrial areas',
        'examples': ['Manufacturing units', 'Industrial estates', 'Factories']
    },
    '400 Transport and Communication': {
        'category': 'TRANSPORT',
        'description': 'Transportation and communication infrastructure',
        'examples': ['Roads', 'Railways', 'Communication facilities']
    },
    '500 Public Utilities': {
        'category': 'UTILITIES',
        'description': 'Public utility infrastructure',
        'examples': ['Power stations', 'Water treatment', 'Utility facilities']
    },
    '600 Public and Semi Public Use': {
        'category': 'PUBLIC',
        'description': 'Public and semi-public facilities',
        'examples': ['Government buildings', 'Public institutions', 'Semi-public facilities']
    },
    '700 Open Spaces': {
        'category': 'PARKS_GREEN',
        'description': 'Open spaces and green areas',
        'examples': ['Parks', 'Open grounds', 'Green spaces']
    },
    '800 Aggriculture Zone': {
        'category': 'AGRICULTURAL',
        'description': 'Agricultural zones',
        'examples': ['Agricultural land', 'Farming areas']
    },
    '900 Special Zone': {
        'category': 'SPECIAL',
        'description': 'Special designated zones',
        'examples': ['Special economic zones', 'Designated special areas']
    },
    '1000 Natural Conservation Zone Hubs': {
        'category': 'PROTECTED',
        'description': 'Natural conservation areas',
        'examples': ['Conservation zones', 'Protected natural areas', 'Environmental reserves']
    },
    'Hubs': {
        'category': 'COMMERCIAL',
        'description': 'Commercial and business hubs',
        'examples': ['Business hubs', 'Commercial centers']
    },
    'H6 World Trade Hub': {
        'category': 'COMMERCIAL',
        'description': 'World Trade Hub',
        'examples': ['International trade center', 'World trade facilities']
    }
}

# Gurgaon Configuration
GURGAON_CONFIG = {
    'city_info': {
        'name': 'Gurgaon',
        'slug': 'gurgaon',
        'state': 'Haryana',
        'center_lat': 28.4595,  # Gurgaon coordinates
        'center_lng': 77.0266,
    },
    'data_format': 'GEOJSON',
    'coordinate_precision': 8,
    'classtext_mapping': GURGAON_CLASSTEXT_MAPPING,
    
    # File mappings - mapping filename to category based on classtext field
    'file_mappings': {
        'Agriculture_Zone.geojson': 'AGRICULTURAL',
        'Commercial.geojson': 'COMMERCIAL',
        'Hubs.geojson': 'COMMERCIAL',
        'Industrial.geojson': 'INDUSTRIAL',
        'Natural_Conservation_Zone_Hubs.geojson': 'PROTECTED',
        'Open_Spaces.geojson': 'PARKS_GREEN',
        'Public_and_Semi_Public_Use.geojson': 'PUBLIC',
        'Public_Utilities.geojson': 'UTILITIES',
        'Residential_GroupHousing_Plotted.geojson': 'RESIDENTIAL',
        'Special_Zone.geojson': 'SPECIAL',
        'Transport_and_Communication.geojson': 'TRANSPORT',
        'World_Trade_Hub.geojson': 'COMMERCIAL',
    },
    
    # Colors - using the hex codes you provided
    'colors': {
        'RESIDENTIAL': '#FFFF73',        # 100 Residential (Group Housing/Plotted)
        'COMMERCIAL': '#BED2FF',         # 200 Commercial, Hubs, H6 World Trade Hub
        'INDUSTRIAL': '#A80084',         # 300 Industrial
        'TRANSPORT': '#828282',          # 400 Transport and Communication
        'UTILITIES': '#A83800',          # 500 Public Utilities
        'PUBLIC': '#E60000',             # 600 Public and Semi Public Use
        'PARKS_GREEN': '#F57A7A',        # 700 Open Spaces (using solid fill)
        'AGRICULTURAL': '#4CE600',       # 800 Agriculture Zone (using dot fill)
        'SPECIAL': '#DF73FF',            # 900 Special Zone
        'PROTECTED': '#38A800',          # 1000 Natural Conservation Zone Hubs
        # Fallback colors for other categories
        'WATER_BODIES': '#00C5FF',
        'GOVERNMENT': '#E60000',         # Same as public
        'EDUCATION': '#E60000',          # Same as public
        'HEALTHCARE': '#E60000',         # Same as public
        'CULTURAL': '#FFAA00',           # Using Hubs color
        'MIXED_USE': '#FFAA00',
        'DEFENSE': '#666666',
        'HIGH_TECH': '#A80084',          # Same as industrial
        'DRAINS': '#00C5FF',
        'HILLS': '#38A800',              # Same as protected
        'CEMETERY': '#F57A7A',           # Same as parks/green
        'UNCLASSIFIED': '#CCCCCC'
    },
    
    # Attribute mappings for Gurgaon (based on your sample data structure)
    'attribute_mappings': {
        'land_use_fields': {
            'classtext': 'classtext',
            'class': 'class_code',
            'code': 'code',
            'name': 'sector_name',
            'density': 'density',
            'val': 'val',
            'text_': 'text_code',
            'codetext': 'codetext',
        },
        'geometry_fields': {
            'Shape_Area': 'area',
            'Shape_Length': 'perimeter',
        },
        'metadata_fields': {
            'OBJECTID': 'object_id',
            'objectid': 'object_id_alt',
            'id': 'feature_id',
            'final_gmda_jan17_sde_sector_no_': 'gmda_sector_no',
        }
    }
}


# Master configuration dictionary
CITY_CONFIGS = {
    'bengaluru': BANGALORE_CONFIG,
    'visakhapatnam': VIZAG_CONFIG,
    'amaravati': AMARAVATI_CONFIG,
    'hyderabad': HYDERABAD_CONFIG,
    'warangal': WARANGAL_CONFIG,
    'delhi': DELHI_CONFIG,
    'gurgaon': GURGAON_CONFIG,
}

def map_name_to_category_delhi(name_field):
    """
    Map Delhi NAME field to categories
    Delhi uses simple NAME field mapping
    """
    # Clean input
    name_field = (name_field or '').strip()
    
    # Check direct NAME mapping
    if name_field and name_field in DELHI_NAME_MAPPING:
        return DELHI_NAME_MAPPING[name_field]['category']
    
    return 'UNCLASSIFIED'

def map_classtext_to_category_gurgaon(classtext_field):
    """
    Map Gurgaon classtext field to categories
    Gurgaon uses classtext field mapping with codes
    """
    # Clean input
    classtext_field = (classtext_field or '').strip()
    
    # Check direct classtext mapping
    if classtext_field and classtext_field in GURGAON_CLASSTEXT_MAPPING:
        return GURGAON_CLASSTEXT_MAPPING[classtext_field]['category']
    
    return 'UNCLASSIFIED'

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

def map_plu_code_to_category_warangal(plu_code, plu_name=None):
    """
    Map Warangal PLU codes to categories
    Warangal uses simple PLU field mapping
    """
    # Clean inputs
    plu_code = (plu_code or '').strip()
    plu_name = (plu_name or '').strip()
    
    # Check direct PLU code mapping
    if plu_code and plu_code in WARANGAL_PLU_MAPPING:
        return WARANGAL_PLU_MAPPING[plu_code]['category']
    
    # Fallback to PLU_NAME if available
    if plu_name and plu_name in WARANGAL_PLU_MAPPING:
        return WARANGAL_PLU_MAPPING[plu_name]['category']
    
    return 'UNCLASSIFIED'

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
    'validate_city_configuration',
    'map_plu_code_to_category_warangal',
]