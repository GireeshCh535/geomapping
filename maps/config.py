# maps/config.py
"""
Complete configuration with Telangana (Hyderabad & Warangal) support
Preserves all existing Karnataka Bengaluru functionality without changes
"""

LAYER_CATEGORIES = {
    'RESIDENTIAL': {
        'name': 'Residential',
        'description': 'Residential areas',
        'default_color': '#FFFF73',
        'default_opacity': 0.8
    },
    'COMMERCIAL': {
        'name': 'Commercial',
        'description': 'Commercial and business areas',
        'default_color': '#004DA8',
        'default_opacity': 0.8
    },
    'INDUSTRIAL': {
        'name': 'Industrial',
        'description': 'Industrial zones',
        'default_color': '#C500FF',
        'default_opacity': 0.8
    },
    'AGRICULTURAL': {
        'name': 'Agricultural',
        'description': 'Agricultural lands',
        'default_color': '#D3FFBE',
        'default_opacity': 0.8
    },
    'TRANSPORT': {
        'name': 'Transportation',
        'description': 'Transport infrastructure',
        'default_color': '#686868',
        'default_opacity': 0.9
    },
    'PARKS_GREEN': {
        'name': 'Parks & Green Spaces',
        'description': 'Parks and recreational areas',
        'default_color': '#55FF00',
        'default_opacity': 0.8
    },
    'WATER_BODIES': {
        'name': 'Water Bodies',
        'description': 'Water bodies',
        'default_color': '#73FFDF',
        'default_opacity': 0.9
    },
    'GOVERNMENT': {
        'name': 'Government',
        'description': 'Government and public facilities',
        'default_color': '#E60000',
        'default_opacity': 0.8
    },
    'MIXED_USE': {
        'name': 'Mixed Use',
        'description': 'Mixed use zones',
        'default_color': '#FFAA00',
        'default_opacity': 0.8
    },
    'PROTECTED': {
        'name': 'Protected',
        'description': 'Protected areas',
        'default_color': '#267300',
        'default_opacity': 0.8
    },
    'UTILITIES': {
        'name': 'Utilities',
        'description': 'Public utilities and infrastructure',
        'default_color': '#D79E9E',
        'default_opacity': 0.8
    },
    'UNCLASSIFIED': {
        'name': 'Unclassified',
        'description': 'Unclassified land use',
        'default_color': '#E1E1E1',
        'default_opacity': 0.7
    }
}

# ================================
# COMPLETE DATA IMPORT CONFIGURATION
# ================================

DATA_IMPORT_CONFIG = {
    'states': {
        'karnataka': {
            'name': 'Karnataka',
            'code': 'KA',
            'cities': {
                'bengaluru': {
                    'name': 'Bengaluru',
                    'center_lat': 12.9716,
                    'center_lng': 77.5946,
                    'zoom_level': 11,
                    'data_format': 'esri_json',
                    'plu_field': 'PLU_Tp_pro',
                    'layer_groups': {
                        'master-plan': {
                            'name': 'Master Plan 2015',
                            'description': 'Bengaluru Master Plan 2015 - Land Use Categories',
                            'path': 'karnataka/bengaluru/master_plan',
                            'display_order': 1,
                            'files': {
                                'Residential_Mixed_.json': {
                                    'name': 'Residential Mixed',
                                    'color': '#FFC400',
                                    'category': 'RESIDENTIAL'
                                },
                                'Residential_Main_.json': {
                                    'name': 'Residential Main',
                                    'color': '#FFEB4F',
                                    'category': 'RESIDENTIAL'
                                },
                                'Commercial_Central_.json': {
                                    'name': 'Commercial Central',
                                    'color': '#004DA8',
                                    'category': 'COMMERCIAL'
                                },
                                'Commercial_Business_.json': {
                                    'name': 'Commercial Business',
                                    'color': '#73B2FF',
                                    'category': 'COMMERCIAL'
                                },
                                'Industrial.json': {
                                    'name': 'Industrial',
                                    'color': '#AA66B2',
                                    'category': 'INDUSTRIAL'
                                },
                                'HighTech.json': {
                                    'name': 'High Tech',
                                    'color': '#C29ED7',
                                    'category': 'INDUSTRIAL'
                                },
                                'Public_SemiPublic.json': {
                                    'name': 'Public & Semi Public',
                                    'color': '#E60000',
                                    'category': 'GOVERNMENT'
                                },
                                'Defense.json': {
                                    'name': 'Defense',
                                    'color': '#E0B8FC',
                                    'category': 'GOVERNMENT'
                                },
                                'StateForest_Valley_ProtectedLand_.json': {
                                    'name': 'State Forest Valley Protected Land',
                                    'color': '#70A800',
                                    'category': 'PROTECTED'
                                },
                                'Parks_GreenSpaces_Sports_Playgrounds_Cemetery_BurialGrounds.json': {
                                    'name': 'Parks Green Spaces',
                                    'color': '#98E600',
                                    'category': 'PARKS_GREEN'
                                },
                                'Lake_Tank.json': {
                                    'name': 'Lake Tank',
                                    'color': '#BEE8FF',
                                    'category': 'WATER_BODIES'
                                },
                                'Road_Rail_Airport_Transport.json': {
                                    'name': 'Road Rail Airport Transport',
                                    'color': '#828282',
                                    'category': 'TRANSPORT'
                                },
                                'Power_Water_GarbageFacility_TreatmentPlant.json': {
                                    'name': 'Power Water Garbage Facility',
                                    'color': '#D79E9E',
                                    'category': 'UTILITIES'
                                },
                                'Agricultural_Land.json': {
                                    'name': 'Agricultural Land',
                                    'color': '#9DC1CB',
                                    'category': 'AGRICULTURAL'
                                },
                                'Unclassified_Use.json': {
                                    'name': 'Unclassified Use',
                                    'color': '#E1E1E1',
                                    'category': 'UNCLASSIFIED'
                                },
                                'Drains.json': {
                                    'name': 'Drains',
                                    'color': '#267300',
                                    'category': 'WATER_BODIES'
                                }
                            }
                        },
                        'highways': {
                            'name': 'Highways',
                            'description': 'National Highways and Major Roads',
                            'path': 'karnataka/bengaluru/highways',
                            'display_order': 2,
                            'data_format': 'geojson',
                            'files': {
                                'BellaryRoad_NH44.geojson': {
                                    'name': 'Bellary Road (NH-44)',
                                    'color': '#14e098',
                                    'category': 'TRANSPORT'
                                },
                                'BengaluruChennaiExpressway_NE7.geojson': {
                                    'name': 'Bengaluru-Chennai Expressway (NE-7)',
                                    'color': '#14e098',
                                    'category': 'TRANSPORT'
                                },
                                'BengaluruMysuruRoad_NH275.geojson': {
                                    'name': 'Bengaluru-Mysuru Road (NH-275)',
                                    'color': '#14e098',
                                    'category': 'TRANSPORT'
                                },
                                'HosurRoad_NH48.geojson': {
                                    'name': 'Hosur Road (NH-48)',
                                    'color': '#14e098',
                                    'category': 'TRANSPORT'
                                },
                                'KanakpuraRoad_NH948.geojson': {
                                    'name': 'Kanakpura Road (NH-948)',
                                    'color': '#14e098',
                                    'category': 'TRANSPORT'
                                },
                                'MadrasRoad_NH75.geojson': {
                                    'name': 'Madras Road (NH-75)',
                                    'color': '#14e098',
                                    'category': 'TRANSPORT'
                                },
                                'NICE_Road.geojson': {
                                    'name': 'NICE Road',
                                    'color': '#14e098',
                                    'category': 'TRANSPORT'
                                },
                                'TumakuruRoad_NH48.geojson': {
                                    'name': 'Tumakuru Road (NH-48)',
                                    'color': '#14e098',
                                    'category': 'TRANSPORT'
                                }
                            }
                        },
                        'metro': {
                            'name': 'Metro',
                            'description': 'Bengaluru Metro Lines',
                            'path': 'karnataka/bengaluru/metro',
                            'display_order': 3,
                            'files': {
                                'Bangalore Metro Phases 1,2,2A&2B.geojson': {
                                    'name': 'Bangalore Metro Phases 1, 2, 2A & 2B',
                                    'color': '#14b8a6',
                                    'category': 'TRANSPORT'
                                }
                            }
                        },
                        'strr': {
                            'name': 'STRR',
                            'description': 'Satellite Town Ring Road',
                            'path': 'karnataka/bengaluru/strr',
                            'display_order': 4,
                            'files': {
                                'STRR.geojson': {
                                    'name': 'Satellite Town Ring Road',
                                    'color': '#14b8a6',
                                    'category': 'TRANSPORT'
                                }
                            }
                        },
                        'workspace': {
                            'name': 'Workspace',
                            'description': 'Industrial Areas and Workspaces',
                            'path': 'karnataka/bengaluru/workspace',
                            'display_order': 5,
                            'files': {
                                'Blr_Industrial_Area_processed.geojson': {
                                    'name': 'Bengaluru Industrial Areas',
                                    'color': '#14e098',
                                    'category': 'INDUSTRIAL'
                                }
                            }
                        }
                    }
                }
            }
        },
        'telangana': {
            'name': 'Telangana',
            'code': 'TS',
            'cities': {
                'hyderabad': {
                    'name': 'Hyderabad',
                    'center_lat': 17.3850,
                    'center_lng': 78.4867,
                    'zoom_level': 11,
                    'data_format': 'geojson',
                    'plu_field': 'name',
                    'layer_groups': {
                        'rrr': {
                            'name': 'RRR (Regional Ring Road)',
                            'description': 'Hyderabad Regional Ring Road',
                            'path': 'Telangana/Hyderabad/rrr',
                            'display_order': 1,
                            'files': {
                                'RRR_Final.geojson': {
                                    'name': 'RRR Final',
                                    'color': '#14E098',
                                    'category': 'TRANSPORT'
                                }
                            }
                        },
                        'ratan-tata-roads': {
                            'name': 'Ratan Tata Roads',
                            'description': 'Hyderabad Ratan Tata Roads',
                            'path': 'Telangana/Hyderabad/ratan-tata-road',
                            'display_order': 2,
                            'files': {
                                'RatanTataRoad.geojson': {
                                    'name': 'Ratan Tata Road',
                                    'color': '#14E098',
                                    'category': 'TRANSPORT'
                                }
                            }
                        },
                        'highways': {
                            'name': 'Highways',
                            'description': 'Hyderabad Highways',
                            'path': 'Telangana/Hyderabad/highways',
                            'display_order': 3,
                            'files': {
                                'hyd_highways_merged.geojson': {
                                    'name': 'Hyderabad Highways',
                                    'color': '#14E098',
                                    'category': 'TRANSPORT'
                                }
                            }
                        },
                        'future-city': {
                            'name': 'Future City Development',
                            'description': 'Hyderabad Future City Development Authority (FCDA) Boundary',
                            'path': 'Telangana/Hyderabad/future-city',
                            'display_order': 4,
                            'files': {
                                'FCDA Boundary.geojson': {
                                    'name': 'FCDA Boundary',
                                    'color': '#7D7D7D',
                                    'category': 'PLANNING',
                                    'border_color': '#C3C3C3',
                                    'opacity': 0.5,
                                    'type': 'boundary'
                                }
                            }
                        },
                        'metro': {
                            'name': 'Metro Lines',
                            'description': 'Hyderabad Metro - All Phases',
                            'path': 'Telangana/Hyderabad/metro-lines',
                            'display_order': 5,
                            'files': {
                                'Hyd_metro_lines_ph_1&2_Final.geojson': {
                                    'name': 'Hyderabad Metro - All Phases',
                                    'color': '#00933D',
                                    'category': 'TRANSPORT',
                                    'line_colors': {
                                        'Green Line': '#00933D',  # Green Line: JBS Parade Ground ↔ MG Bus Station
                                        'Blue Line': '#2D6BA1',  # Blue Line: Nagole ↔ Raidurg
                                        'Red Line': '#E40D17',   # Red Line: Miyapur ↔ L.B. Nagar
                                        'Purple Line': '#8C06ED', # Purple Line (Phase 2A): Nagole ↔ RGIA
                                        'Orange Line': '#EF6908'  # Future City Line (Phase 2B): RGIA ↔ Future City
                                    },
                                    'phases': {
                                        'phase_1': {
                                            'name': 'Phase 1 (Existing)',
                                            'lines': {
                                                'green_line': {
                                                    'name': 'Green Line',
                                                    'route': 'JBS Parade Ground ↔ MG Bus Station',
                                                    'color': '#00933D',
                                                    'status': 'Existing'
                                                },
                                                'blue_line': {
                                                    'name': 'Blue Line',
                                                    'route': 'Nagole ↔ Raidurg',
                                                    'color': '#2D6BA1',
                                                    'status': 'Existing'
                                                },
                                                'red_line': {
                                                    'name': 'Red Line',
                                                    'route': 'Miyapur ↔ L.B. Nagar',
                                                    'color': '#E40D17',
                                                    'status': 'Existing'
                                                }
                                            }
                                        },
                                        'phase_2a': {
                                            'name': 'Phase 2A (Upcoming)',
                                            'lines': {
                                                'green_line_extension': {
                                                    'name': 'Green Line Extension',
                                                    'route': 'MG Bus Station ↔ Chandrayangutta',
                                                    'color': '#00933D',
                                                    'status': 'Upcoming'
                                                },
                                                'purple_line': {
                                                    'name': 'Purple Line',
                                                    'route': 'Nagole ↔ RGIA (Shamshabad Airport)',
                                                    'color': '#8C06ED',
                                                    'status': 'Upcoming'
                                                }
                                            }
                                        },
                                        'phase_2b': {
                                            'name': 'Phase 2B (Upcoming)',
                                            'lines': {
                                                'future_city_line': {
                                                    'name': 'Future City Line',
                                                    'route': 'RGIA (Shamshabad) ↔ Future City',
                                                    'color': '#EF6908',
                                                    'status': 'Upcoming'
                                                },
                                                'blue_line_extension': {
                                                    'name': 'Blue Line Extension',
                                                    'route': 'JBS Parade Ground ↔ Shamirpet',
                                                    'color': '#2D6BA1',
                                                    'status': 'Upcoming'
                                                },
                                                'green_line_extension_2': {
                                                    'name': 'Green Line Extension',
                                                    'route': 'Paradise ↔ Medchal',
                                                    'color': '#00933D',
                                                    'status': 'Upcoming'
                                                }
                                            }
                                        }
                                    }
                                },
                                'Hyd_metro_stations_ph1&2.geojson': {
                                    'name': 'Hyderabad Metro Stations',
                                    'color': '#00933D',
                                    'category': 'TRANSPORT',
                                    'type': 'stations'
                                }
                            }
                        }
                    }
                },
                'warangal': {
                    'name': 'Warangal',
                    'center_lat': 17.9784,
                    'center_lng': 79.6003,
                    'zoom_level': 12,
                    'data_format': 'geojson',
                    'plu_field': 'PLU',
                    'layer_groups': {
                        'master-plan': {
                            'name': 'Master Plan',
                            'description': 'Warangal Master Plan - Land Use Categories',
                            'path': 'Telangana/warangal/master_plan',
                            'display_order': 1,
                            'files': {
                                'Agriculture.geojson': {
                                    'name': 'Agriculture',
                                    'color': '#D3FFBE',
                                    'category': 'AGRICULTURAL'
                                },
                                'AirStrip.geojson': {
                                    'name': 'Air Strip',
                                    'color': {'hatch': '#FFFFFF', 'solid': '#FF00C5'},
                                    'category': 'TRANSPORT'
                                },
                                'Commercial.geojson': {
                                    'name': 'Commercial',
                                    'color': '#0070FF',
                                    'category': 'COMMERCIAL'
                                },
                                'Forest.geojson': {
                                    'name': 'Forest',
                                    'color': '#267300',
                                    'category': 'PROTECTED'
                                },
                                'GrowthCorridor.geojson': {
                                    'name': 'Growth Corridor',
                                    'color': '#FFBEE8',
                                    'category': 'MIXED_USE'
                                },
                                'GrowthCorridor2.geojson': {
                                    'name': 'Growth Corridor 2',
                                    'color': '#FF73DF',
                                    'category': 'MIXED_USE'
                                },
                                'Heritage.geojson': {
                                    'name': 'Heritage',
                                    'color': {'hatch': '#732600', 'solid': '#FFA77F'},
                                    'category': 'PROTECTED'
                                },
                                'HillBuffer.geojson': {
                                    'name': 'Hill Buffer',
                                    'color': '#55FF00',
                                    'category': 'PROTECTED'
                                },
                                'Hillocks.geojson': {
                                    'name': 'Hillocks',
                                    'color': '#A87000',
                                    'category': 'PROTECTED'
                                },
                                'Industrial.geojson': {
                                    'name': 'Industrial',
                                    'color': '#C500FF',
                                    'category': 'INDUSTRIAL'
                                },
                                'MixedUse.geojson': {
                                    'name': 'Mixed Use',
                                    'color': '#FFAA00',
                                    'category': 'MIXED_USE'
                                },
                                'Public_and_SemiPublic.geojson': {
                                    'name': 'Public and Semi Public',
                                    'color': '#FF0000',
                                    'category': 'GOVERNMENT'
                                },
                                'PublicUtilities.geojson': {
                                    'name': 'Public Utilities',
                                    'color': {'hatch': '#FF0000', 'solid': '#E69800'},
                                    'category': 'UTILITIES'
                                },
                                'RailwayLand.geojson': {
                                    'name': 'Railway Land',
                                    'color': '#CCCCCC',
                                    'category': 'TRANSPORT'
                                },
                                'Recreational.geojson': {
                                    'name': 'Recreational',
                                    'color': '#55FF00',
                                    'category': 'PARKS_GREEN'
                                },
                                'Residential.geojson': {
                                    'name': 'Residential',
                                    'color': '#FFFF00',
                                    'category': 'RESIDENTIAL'
                                },
                                'ResidentialExpansion.geojson': {
                                    'name': 'Residential Expansion',
                                    'color': '#9C9C9C',
                                    'category': 'RESIDENTIAL'
                                },
                                'RoadBuffer.geojson': {
                                    'name': 'Road Buffer',
                                    'color': '#4E4E4E',
                                    'category': 'TRANSPORT'
                                },
                                'Transportation.geojson': {
                                    'name': 'Transportation',
                                    'color': '#B2B2B2',
                                    'category': 'TRANSPORT'
                                },
                                'Water_Bodies.geojson': {
                                    'name': 'Water Bodies',
                                    'color': '#00C5FF',
                                    'category': 'WATER_BODIES'
                                },
                                'WaterBodyBuffer.geojson': {
                                    'name': 'Water Body Buffer',
                                    'color': '#55FF00',
                                    'category': 'WATER_BODIES'
                                },
                                'ZoologicalPark.geojson': {
                                    'name': 'Zoological Park',
                                    'color': '#38A800',
                                    'category': 'PARKS_GREEN'
                                }
                            }
                        }
                    }
                }
            }
        },
        'andhra-pradesh': {
            'name': 'Andhra Pradesh',
            'code': 'AP',
            'cities': {
                'visakhapatnam': {
                    'name': 'Visakhapatnam',
                    'center_lat': 17.6868,
                    'center_lng': 83.2185,
                    'zoom_level': 11,
                    'data_format': 'geojson',
                    'plu_field': 'Category',
                    'layer_groups': {
                        'master-plan': {
                            'name': 'Master Plan',
                            'description': 'Visakhapatnam Master Plan - Land Use Categories',
                            'path': 'andhra_pradesh/visakhapatnam/master_plan',
                            'display_order': 1,
                            'files': {
                                'Agricultural_Use_Zone.geojson': {
                                    'name': 'Agricultural Use Zone',
                                    'color': '#D3FFBE',
                                    'category': 'AGRICULTURAL'
                                },
                                'Blue_Zone_Water_Bodies.geojson': {
                                    'name': 'Blue Zone Water Bodies',
                                    'color': '#73FFDF',
                                    'category': 'WATER_BODIES'
                                },
                                'Brown_Zone_Hills.geojson': {
                                    'name': 'Brown Zone Hills',
                                    'color': '#A87000',
                                    'category': 'PROTECTED'
                                },
                                'Commercial_Use_Zone.geojson': {
                                    'name': 'Commercial Use Zone',
                                    'color': '#004DA8',
                                    'category': 'COMMERCIAL'
                                },
                                'Existing_Crematorium_Burial_Ground_Graveyard.geojson': {
                                    'name': 'Existing Crematorium',
                                    'color': {'hatch': '#FF0000', 'solid': '#FFFFFF'},
                                    'category': 'GOVERNMENT'
                                },
                                'Existing_Educational_Facilities.geojson': {
                                    'name': 'Existing Educational',
                                    'color': {'hatch': '#000000', 'solid': '#FF0000'},
                                    'category': 'GOVERNMENT'
                                },
                                'Existing_Government_Semi_Government_Facilities.geojson': {
                                    'name': 'Existing Government',
                                    'color': '#FF0000',
                                    'category': 'GOVERNMENT'
                                },
                                'Existing_Health_Facilities.geojson': {
                                    'name': 'Existing Health',
                                    'color': {'dot': '#CCCCCC', 'solid': '#FF0000'},
                                    'category': 'GOVERNMENT'
                                },
                                'Proposed_Industrial_Use_Zone.geojson': {
                                    'name': 'Proposed Industrial',
                                    'color': {'hatch': '#FFFFFF', 'solid': '#C500FF'},
                                    'category': 'INDUSTRIAL'
                                },
                                'Existing_Industrial_Area.geojson': {
                                    'name': 'Existing Industrial',
                                    'color': '#C500FF',
                                    'category': 'INDUSTRIAL'
                                },
                                'Existing_Public_Utilities.geojson': {
                                    'name': 'Existing Public Utilities',
                                    'color': {'hatch': '#E60000', 'solid': '#FF7F7F'},
                                    'category': 'UTILITIES'
                                },
                                'Existing_Recreational_Playgrounds_Parks_Layout_OpenSpace.geojson': {
                                    'name': 'Existing Recreational',
                                    'color': '#55FF00',
                                    'category': 'PARKS_GREEN'
                                },
                                'Existing_Religious_Facilities.geojson': {
                                    'name': 'Existing Religious',
                                    'color': {'hatch': '#55FF00', 'solid': '#FF0000'},
                                    'category': 'GOVERNMENT'
                                },
                                'Existing_Road_Railway_Line_Area.geojson': {
                                    'name': 'Existing Road Railway',
                                    'color': {'hatch': '#828282'},
                                    'category': 'TRANSPORT'
                                },
                                'Existing_Transportation_Facility.geojson': {
                                    'name': 'Existing Transportation',
                                    'color': '#686868',
                                    'category': 'TRANSPORT'
                                },
                                'Green_Zone_Forest.geojson': {
                                    'name': 'Green Zone Forest',
                                    'color': '#00734C',
                                    'category': 'PROTECTED'
                                },
                                'Kambalakonda_Eco_Sensitive_Zone_NAOB_Buffer_Zoological_Park.geojson': {
                                    'name': 'Kambalakonda Eco',
                                    'color': '#D7C29E',
                                    'category': 'PROTECTED'
                                },
                                'Kambalakonda_WildLife_Sanctuary_Biodiversity_Area.geojson': {
                                    'name': 'Kambalakonda Wildlife',
                                    'color': '#38A800',
                                    'category': 'PROTECTED'
                                },
                                'Mixed_Use_Zone_1.geojson': {
                                    'name': 'Mixed Use Zone 1',
                                    'color': '#FFAA00',
                                    'category': 'MIXED_USE'
                                },
                                'Mixed_Use_Zone_2_BAIA.geojson': {
                                    'name': 'Mixed Use Zone 2',
                                    'color': '#FFD37F',
                                    'category': 'MIXED_USE'
                                },
                                'Mixed_Use_Zone_3_BAIA.geojson': {
                                    'name': 'Mixed Use Zone 3',
                                    'color': {'hatch': '#E1E1E1', 'solid': '#E69800'},
                                    'category': 'MIXED_USE'
                                },
                                'Mixed_Use_Zone_4_BAIA.geojson': {
                                    'name': 'Mixed Use Zone 4',
                                    'color': {'dot': '#000000', 'solid': '#FFAA00'},
                                    'category': 'MIXED_USE'
                                },
                                'Proposed_PSP_Use_Zone.geojson': {
                                    'name': 'Proposed PSP',
                                    'color': {'hatch': '#FF0000'},
                                    'category': 'GOVERNMENT'
                                },
                                'Proposed_Public_Utilities_Use_Zone.geojson': {
                                    'name': 'Proposed Public Utilities',
                                    'color': {'hatch': '#FFFFFF', 'solid': '#F57A7A'},
                                    'category': 'UTILITIES'
                                },
                                'Proposed_Recreational_Use_Zone.geojson': {
                                    'name': 'Proposed Recreational',
                                    'color': '#4C7300',
                                    'category': 'PARKS_GREEN'
                                },
                                'Proposed_Road_Network.geojson': {
                                    'name': 'Proposed Road Network',
                                    'color': '#C47362',
                                    'category': 'TRANSPORT'
                                },
                                'Proposed_Transportation_Facility_Use_Zone.geojson': {
                                    'name': 'Proposed Transportation',
                                    'color': {'hatch': '#FFFFFF', 'solid': '#343434'},
                                    'category': 'TRANSPORT'
                                },
                                'Residential_Use_Zone.geojson': {
                                    'name': 'Residential Use Zone',
                                    'color': '#FFFF73',
                                    'category': 'RESIDENTIAL'
                                },
                                'Sea_River_Accreted_Land.geojson': {
                                    'name': 'Sea River Accreted Land',
                                    'color': {'dot': '#E39E00', 'solid': '#D7C29E'},
                                    'category': 'WATER_BODIES'
                                },
                                'Special_Area_Use_Zone.geojson': {
                                    'name': 'Special Area Use Zone',
                                    'color': {'hatch': '#002673', 'solid': '#FFFFFF'},
                                    'category': 'MIXED_USE'
                                },
                                'Water_Body_Buffer.geojson': {
                                    'name': 'Water Body Buffer',
                                    'color': {'dot': '#267300', 'solid': '#4CE600'},
                                    'category': 'WATER_BODIES'
                                }
                            }
                        }
                    }
                },
                'amaravati': {
                    'name': 'Amaravati',
                    'center_lat': 16.5131,
                    'center_lng': 80.5165,
                    'zoom_level': 11,
                    'data_format': 'geojson',
                    'plu_field': 'symbology',
                    'layer_groups': {
                        'master-plan': {
                            'name': 'Master Plan',
                            'description': 'Amaravati Capital City Master Plan',
                            'path': 'andhra_pradesh/amaravati/master_plan',
                            'display_order': 1,
                            'files': {
                                'Burial_Ground.geojson': {
                                    'name': 'Burial Ground',
                                    'color': {'dot': '#E39E00', 'solid': '#FFFFFF'},
                                    'category': 'GOVERNMENT'
                                },
                                'C1__Mixed_use_zone.geojson': {
                                    'name': 'C1 Mixed Use Zone',
                                    'color': '#73B2FF',
                                    'category': 'MIXED_USE'
                                },
                                'C2__General_commercial_zone.geojson': {
                                    'name': 'C2 General Commercial Zone',
                                    'color': '#00C5FF',
                                    'category': 'COMMERCIAL'
                                },
                                'C3_Neighbourhood_centre_zone.geojson': {
                                    'name': 'C3 Neighbourhood Centre Zone',
                                    'color': '#00C5FF',
                                    'category': 'COMMERCIAL'
                                },
                                'C4_Town_centre_zone.geojson': {
                                    'name': 'C4 Town Centre Zone',
                                    'color': '#00A9E6',
                                    'category': 'COMMERCIAL'
                                },
                                'C5_Regional_centre_zone.geojson': {
                                    'name': 'C5 Regional Centre Zone',
                                    'color': '#0070FF',
                                    'category': 'COMMERCIAL'
                                },
                                'C6_Central_business_district_zone.geojson': {
                                    'name': 'C6 Central Business District',
                                    'color': '#005CE6',
                                    'category': 'COMMERCIAL'
                                },
                                'Commercial_Vacant.geojson': {
                                    'name': 'Commercial Vacant',
                                    'color': '#C5E2FF',
                                    'category': 'COMMERCIAL'
                                },
                                'I1_Business_park_zone.geojson': {
                                    'name': 'I1 Business Park Zone',
                                    'color': '#FFBEE8',
                                    'category': 'INDUSTRIAL'
                                },
                                'I2_Logistics_zone.geojson': {
                                    'name': 'I2 Logistics Zone',
                                    'color': '#FF73DF',
                                    'category': 'INDUSTRIAL'
                                },
                                'I3_Non_polluting_industry_zone.geojson': {
                                    'name': 'I3 Non Polluting Industry Zone',
                                    'color': '#A900E6',
                                    'category': 'INDUSTRIAL'
                                },
                                'P1_Passive_zone.geojson': {
                                    'name': 'P1 Passive Zone',
                                    'color': '#267300',
                                    'category': 'PARKS_GREEN'
                                },
                                'P2_Active_zone.geojson': {
                                    'name': 'P2 Active Zone',
                                    'color': '#38A800',
                                    'category': 'PARKS_GREEN'
                                },
                                'P3_Protected_zone.geojson': {
                                    'name': 'P3 Protected Zone',
                                    'color': '#BEE8FF',
                                    'category': 'PROTECTED'
                                },
                                'P3_Protected_zone_Hills.geojson': {
                                    'name': 'P3 Protected Zone Hills',
                                    'color': '#4C7300',
                                    'category': 'PROTECTED'
                                },
                                'PGN_G.geojson': {
                                    'name': 'PGN G',
                                    'color': '#4C7300',
                                    'category': 'PARKS_GREEN'
                                },
                                'PGN_V.geojson': {
                                    'name': 'PGN V',
                                    'color': '#897044',
                                    'category': 'PARKS_GREEN'
                                },
                                'R1_Village_planning_zone.geojson': {
                                    'name': 'R1 Village Planning Zone',
                                    'color': {'solid': '#FFFFFF', 'hatch': '#000000'},
                                    'category': 'RESIDENTIAL'
                                },
                                'R3_Medium_to_high_density_zone.geojson': {
                                    'name': 'R3 Medium to High Density Zone',
                                    'color': '#F5CA7A',
                                    'category': 'RESIDENTIAL'
                                },
                                'R4_High_density_zone.geojson': {
                                    'name': 'R4 High Density Zone',
                                    'color': '#E69800',
                                    'category': 'RESIDENTIAL'
                                },
                                'RAA.geojson': {
                                    'name': 'RAA',
                                    'color': '#FFAA00',
                                    'category': 'RESIDENTIAL'
                                },
                                'Residential_Vacant.geojson': {
                                    'name': 'Residential Vacant',
                                    'color': '#FFD37F',
                                    'category': 'RESIDENTIAL'
                                },
                                'S2_Education_zone.geojson': {
                                    'name': 'S2 Education Zone',
                                    'color': '#FFF7F7',
                                    'category': 'GOVERNMENT'
                                },
                                'S3_Special_zone.geojson': {
                                    'name': 'S3 Special Zone',
                                    'color': '#D7B09E',
                                    'category': 'GOVERNMENT'
                                },
                                'SC1a_Mixed_Use.geojson': {
                                    'name': 'SC1a Mixed Use',
                                    'color': '#0070FF',
                                    'category': 'MIXED_USE'
                                },
                                'SC1b___Mixed_Use.geojson': {
                                    'name': 'SC1b Mixed Use',
                                    'color': '#73B2FF',
                                    'category': 'MIXED_USE'
                                },
                                'SP1__Passive_Zone.geojson': {
                                    'name': 'SP1 Passive Zone',
                                    'color': '#267300',
                                    'category': 'PARKS_GREEN'
                                },
                                'SP2__Active_Zone.geojson': {
                                    'name': 'SP2 Active Zone',
                                    'color': '#38A800',
                                    'category': 'PARKS_GREEN'
                                },
                                'SP3_Protected_Zone.geojson': {
                                    'name': 'SP3 Protected Zone',
                                    'color': '#00C5FF',
                                    'category': 'PROTECTED'
                                },
                                'SR2_Low_Density_Housing.geojson': {
                                    'name': 'SR2 Low Density Housing',
                                    'color': '#FFFFBE',
                                    'category': 'RESIDENTIAL'
                                },
                                'SR4___High_Density_Private.geojson': {
                                    'name': 'SR4 High Density Private',
                                    'color': '#FFAA00',
                                    'category': 'RESIDENTIAL'
                                },
                                'SS1___Government_Zone.geojson': {
                                    'name': 'SS1 Government Zone',
                                    'color': '#E60000',
                                    'category': 'GOVERNMENT'
                                },
                                'SS2a__Education_Zone.geojson': {
                                    'name': 'SS2a Education Zone',
                                    'color': '#FFF7F7',
                                    'category': 'GOVERNMENT'
                                },
                                'SS2b_Cultural_Zone.geojson': {
                                    'name': 'SS2b Cultural Zone',
                                    'color': '#C500FF',
                                    'category': 'GOVERNMENT'
                                },
                                'SS2c_Health_Zone.geojson': {
                                    'name': 'SS2c Health Zone',
                                    'color': '#D3FFBE',
                                    'category': 'GOVERNMENT'
                                },
                                'SS3___Special_Zone.geojson': {
                                    'name': 'SS3 Special Zone',
                                    'color': '#A83800',
                                    'category': 'GOVERNMENT'
                                },
                                'SU1_Reserve_Zone.geojson': {
                                    'name': 'SU1 Reserve Zone',
                                    'color': '#E1E1E1',
                                    'category': 'MIXED_USE'
                                },
                                'SU2___Road_Network.geojson': {
                                    'name': 'SU2 Road Network',
                                    'color': '#FFFFFF',
                                    'category': 'TRANSPORT'
                                },
                                'U1_Reserve_zone.geojson': {
                                    'name': 'U1 Reserve Zone',
                                    'color': '#CCCCCC',
                                    'category': 'MIXED_USE'
                                },
                                'U2__Road_reserve_zone.geojson': {
                                    'name': 'U2 Road Reserve Zone',
                                    'color': '#C47362',
                                    'category': 'TRANSPORT'
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

# ================================
# HELPER FUNCTIONS (UNCHANGED + EXTENDED)
# ================================

def get_state_config(state_slug):
    """Get configuration for a specific state"""
    return DATA_IMPORT_CONFIG.get('states', {}).get(state_slug)

def get_city_config(state_slug, city_slug):
    """Get configuration for a specific city"""
    state_config = get_state_config(state_slug)
    if state_config:
        return state_config.get('cities', {}).get(city_slug)
    return None

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
def get_layer_group_config(state_slug, city_slug, group_slug):
    """Get configuration for a specific layer group"""
    city_config = get_city_config(state_slug, city_slug)
    if city_config:
        return city_config.get('layer_groups', {}).get(group_slug)
    return None

def get_layer_file_config(state_slug, city_slug, group_slug, filename):
    """Get configuration for a specific file"""
    group_config = get_layer_group_config(state_slug, city_slug, group_slug)
    if group_config:
        return group_config.get('files', {}).get(filename)
    return None

def get_layer_group_config(state_slug, city_slug, group_slug):
    """Get configuration for a specific layer group"""
    city_config = get_city_config(state_slug, city_slug)
    if city_config:
        return city_config.get('layer_groups', {}).get(group_slug)
    return None

def get_all_cities():
    """Get all cities from configuration"""
    cities = []
    for state_slug, state_config in DATA_IMPORT_CONFIG.get('states', {}).items():
        for city_slug, city_config in state_config.get('cities', {}).items():
            cities.append({
                'state_slug': state_slug,
                'state_name': state_config['name'],
                'city_slug': city_slug,
                'city_name': city_config['name']
            })
    return cities

def get_layer_color(state_slug, city_slug, group_slug, filename):
    """Get color for a specific layer file"""
    file_config = get_layer_file_config(state_slug, city_slug, group_slug, filename)
    if file_config:
        color = file_config.get('color', '#CCCCCC')
        # If it's a pattern dict, return it as is
        if isinstance(color, dict):
            return color
        # Otherwise return solid color
        return {'solid': color}
    return {'solid': '#CCCCCC'}

def get_pattern_style(city_slug, layer_name):
    """Get pattern style for a layer if it exists"""
    # Search all states for the city
    for state_slug, state_config in DATA_IMPORT_CONFIG.get('states', {}).items():
        if city_slug in state_config.get('cities', {}):
            city_config = state_config['cities'][city_slug]
            # Search all layer groups
            for group_slug, group_config in city_config.get('layer_groups', {}).items():
                # Search all files
                for filename, file_config in group_config.get('files', {}).items():
                    # Check if layer name matches
                    if layer_name in filename or layer_name == file_config.get('name', '').lower().replace(' ', '_'):
                        color = file_config.get('color')
                        if isinstance(color, dict):
                            return color
    return None

CITY_CONFIGS = {}

def get_category_color(city_slug, category_code):
    """Get default color for a category in a city"""
    config = get_city_config(city_slug)
    if config and 'default_colors' in config:
        return config['default_colors'].get(category_code, '#CCCCCC')
    
    # Fallback to global category colors
    category_info = LAYER_CATEGORIES.get(category_code, {})
    return category_info.get('default_color', '#CCCCCC')

for state_slug, state_config in DATA_IMPORT_CONFIG.get('states', {}).items():
    for city_slug, city_config in state_config.get('cities', {}).items():
        CITY_CONFIGS[city_slug] = {
            'city_info': {
                'name': city_config['name'],
                'slug': city_slug,
                'state_ref_id': None,
                'center_lat': city_config.get('center_lat', 0),
                'center_lng': city_config.get('center_lng', 0),
                'zoom_level': city_config.get('zoom_level', 11)
            },
            'data_format': city_config.get('data_format', 'geojson'),
            'plu_field': city_config.get('plu_field', 'PLU'),
            'layer_groups': city_config.get('layer_groups', {})
        }

# State configurations for backwards compatibility
STATE_CONFIGS = {}

for state_slug, state_config in DATA_IMPORT_CONFIG.get('states', {}).items():
    STATE_CONFIGS[state_slug] = {
        'name': state_config['name'],
        'code': state_config['code'],
        'cities': list(state_config.get('cities', {}).keys())
    }

def get_layer_groups_config(city_slug):
    """Backwards compatibility function"""
    city_config = CITY_CONFIGS.get(city_slug)
    if city_config:
        return city_config.get('layer_groups', {})
    return {}

def get_state_for_city(city_slug):
    """Get state for a city"""
    for state_slug, state_config in DATA_IMPORT_CONFIG.get('states', {}).items():
        if city_slug in state_config.get('cities', {}):
            return state_slug, state_config
    return None, None

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
        return None

# Export commonly used functions for import compatibility
__all__ = [
    'CITY_CONFIGS',
    'STATE_CONFIGS',
    'LAYER_CATEGORIES',
    'DATA_IMPORT_CONFIG',  # Added this
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
    'get_city_style_config',  # Fixed: added comma here
    'get_state_config',
    'get_state_for_city',
    'get_pattern_style',
    'get_visakhapatnam_styles',
    'get_amaravati_styles',
    'PATTERN_DEFAULTS'
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