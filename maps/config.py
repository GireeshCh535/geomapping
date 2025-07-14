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
        'slug': 'vizag',
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