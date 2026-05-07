from ._imports import *

@extend_schema(
    summary="Get complete hierarchy",
    description="Retrieve the complete hierarchy of states, cities, and layers in a single API call. This endpoint provides a comprehensive view of the entire geospatial data structure including statistics and tile availability.",
    tags=['hierarchy'],
    responses={
        200: {
            'description': 'Complete hierarchy data',
            'content': {
                'application/json': {
                    'example': {
                        'states': [
                            {
                                'state': {
                                    'name': 'Karnataka',
                                    'slug': 'karnataka',
                                    'is_active': True
                                },
                                'cities': [
                                    {
                                        'name': 'Bengaluru',
                                        'slug': 'bengaluru',
                                        'center_lat': 12.9716,
                                        'center_lng': 77.5946,
                                        'is_active': True,
                                        'is_live': True,
                                        'statistics': {
                                            'total_layers': 5,
                                            'processed_layers': 5,
                                            'layers_with_tiles': 5,
                                            'total_features': 1250
                                        },
                                        'status': 'live',
                                        'layers': [
                                            {
                                                'name': 'Master Plan 2015',
                                                'slug': 'master_plan_2015',
                                                'status': 'live',
                                                'is_live': True,
                                                'tiles_generated': True,
                                                'feature_count': 250,
                                                'bounds': {
                                                    'xmin': 77.4,
                                                    'ymin': 12.8,
                                                    'xmax': 77.8,
                                                    'ymax': 13.2
                                                },
                                                'tile_urls': {
                                                    'png': (
                                                        f'{hierarchical_tile_proxy_base("karnataka", "bengaluru", "bengaluru_master_plan_2015")}'
                                                        f'/{{z}}/{{x}}/{{y}}.png'
                                                    ),
                                                    'mvt': (
                                                        f'{hierarchical_tile_proxy_base("karnataka", "bengaluru", "bengaluru_master_plan_2015")}'
                                                        f'/{{z}}/{{x}}/{{y}}.mvt'
                                                    ),
                                                }
                                            }
                                        ]
                                    }
                                ],
                                'statistics': {
                                    'total_cities': 1,
                                    'total_layers': 5,
                                    'total_features': 1250
                                }
                            }
                        ],
                        'summary': {
                            'total_states': 1,
                            'total_cities': 1,
                            'total_layers': 5,
                            'total_features': 1250
                        }
                    }
                }
            }
        }
    }
)
@extend_schema(
    summary="Get complete system hierarchy",
    description="""
    Returns the complete hierarchy of states, cities, layer groups, layers, and features in a single API call.
    This provides comprehensive data about the entire system structure including:
    
    - All states with their metadata and map settings
    - All cities within each state with map centers and statistics
    - All layer groups within each city with styling information
    - All data layers within each layer group with detailed information
    - Feature counts and processing status
    - Tile generation status and URLs
    - Bounding boxes and geometry information
    - Styling information (without taxonomy codes in the response)
    - Global statistics
    """,
    tags=['hierarchy'],
    responses={
        200: {
            'description': 'Complete hierarchy data',
            'content': {
                'application/json': {
                    'example': {
                        'status': 'success',
                        'timestamp': '2024-01-01T12:00:00Z',
                        'global_statistics': {
                            'total_states': 3,
                            'total_cities': 8,
                            'total_layers': 25,
                            'total_features': 150000,
                        },
                        'hierarchy': [
                            {
                                'id': 1,
                                'name': 'Karnataka',
                                'slug': 'karnataka',
                                'code': 'KA',
                                'map_settings': {
                                    'center_lat': 12.9716,
                                    'center_lng': 77.5946,
                                    'default_zoom': 7
                                },
                                'status': {'is_active': True},
                                'statistics': {
                                    'total_cities': 2,
                                    'total_layers': 10,
                                    'total_features': 75000
                                },
                                'cities': [
                                    {
                                        'id': 1,
                                        'name': 'Bengaluru',
                                        'slug': 'bengaluru',
                                        'state': {
                                            'name': 'Karnataka',
                                            'slug': 'karnataka',
                                            'code': 'KA'
                                        },
                                        'map_settings': {
                                            'center_lat': 12.9716,
                                            'center_lng': 77.5946,
                                            'min_zoom': 8,
                                            'max_zoom': 18
                                        },
                                        'status': {
                                            'is_active': True,
                                            'is_live': True,
                                            'status': 'live'
                                        },
                                        'statistics': {
                                            'total_layer_groups': 3,
                                            'total_layers': 8,
                                            'layers_with_tiles': 8,
                                            'total_features': 50000,
                                            'standalone_layers': 2
                                        },
                                        'styling': [
                                            {
                                                'id': 1,
                                                'fill_color': '#FFFF73',
                                                'stroke_color': '#333333',
                                                'opacity': 0.8,
                                                'stroke_width': 1,
                                                'pattern_config': {
                                                    'pattern_type': 'SOLID',
                                                    'pattern_color': '#FFFF73',
                                                    'pattern_spacing': 10,
                                                    'pattern_angle': 45,
                                                    'pattern_size': 3,
                                                    'secondary_fill': None
                                                },
                                                'visibility': {
                                                    'is_visible': True,
                                                    'min_zoom': 8,
                                                    'max_zoom': 18
                                                }
                                            }
                                        ],
                                        'layer_groups': [
                                            {
                                                'id': 1,
                                                'name': 'Master Plan',
                                                'slug': 'master-plan',
                                                'description': 'Bengaluru Master Plan 2015',
                                                'directory_path': '/data/karnataka/bengaluru/master_plan/',
                                                'styling': {
                                                    'default_color': '#FFFF73',
                                                    'default_stroke': '#333333',
                                                    'default_opacity': 0.8
                                                },
                                                'display_settings': {
                                                    'display_order': 1,
                                                    'is_visible': True,
                                                    'min_zoom': 8,
                                                    'max_zoom': 18
                                                },
                                                'statistics': {
                                                    'total_layers': 3,
                                                    'total_features': 25000
                                                },
                                                'layers': [
                                                    {
                                                        'id': 1,
                                                        'name': 'Bengaluru Master Plan 2015',
                                                        'slug': 'bengaluru_master_plan_2015',
                                                        'description': 'Complete master plan data',
                                                        'file_info': {
                                                            'original_filename': 'bengaluru_master_plan_2015.geojson',
                                                            'file_format': 'GEOJSON',
                                                            'file_path': '/data/karnataka/bengaluru/master_plan/bengaluru_master_plan_2015.geojson',
                                                            'is_directory': False,
                                                            'file_pattern': None,
                                                            'source_files_count': 0
                                                        },
                                                        'geometry_info': {
                                                            'geometry_type': 'POLYGON',
                                                            'has_valid_bbox': True,
                                                            'bounds': {
                                                                'xmin': 77.4567,
                                                                'ymin': 12.8234,
                                                                'xmax': 77.7234,
                                                                'ymax': 13.1234
                                                            },
                                                            'center_point': [12.9734, 77.5901]
                                                        },
                                                        'processing_status': {
                                                            'is_processed': True,
                                                            'tiles_generated': True,
                                                            'feature_count': 15000,
                                                            'processing_errors': None
                                                        },
                                                        'tile_info': {
                                                            'tiles_generated': True,
                                                            'tile_cache_size': 52428800,
                                                            'tile_urls': {
                                                                'png_template': (
                                                                    f'{hierarchical_tile_proxy_base("karnataka", "bengaluru", "bengaluru_master_plan_2015")}'
                                                                    f'/{{z}}/{{x}}/{{y}}.png'
                                                                ),
                                                                'mvt_template': (
                                                                    f'{hierarchical_tile_proxy_base("karnataka", "bengaluru", "bengaluru_master_plan_2015")}'
                                                                    f'/{{z}}/{{x}}/{{y}}.mvt'
                                                                ),
                                                                'api_png_template': (
                                                                    hierarchical_tile_proxy_base(
                                                                        'karnataka', 'bengaluru', 'bengaluru_master_plan_2015'
                                                                    )
                                                                    + '/{z}/{x}/{y}.png'
                                                                ),
                                                                'api_mvt_template': (
                                                                    hierarchical_tile_proxy_base(
                                                                        'karnataka', 'bengaluru', 'bengaluru_master_plan_2015'
                                                                    )
                                                                    + '/{z}/{x}/{y}.mvt'
                                                                ),
                                                                'cloudfront_base': (
                                                                    f'{hierarchical_tile_proxy_base("karnataka", "bengaluru", "bengaluru_master_plan_2015")}/'
                                                                ),
                                                                'api_base': (
                                                                    hierarchical_tile_proxy_base(
                                                                        'karnataka', 'bengaluru', 'bengaluru_master_plan_2015'
                                                                    )
                                                                    + '/'
                                                                ),
                                                            }
                                                        },
                                                        'metadata': {
                                                            'data_source': 'Bengaluru Development Authority',
                                                            'last_updated': '2024-01-01T12:00:00Z',
                                                            'created_at': '2024-01-01T12:00:00Z',
                                                            'updated_at': '2024-01-01T12:00:00Z'
                                                        },
                                                        'statistics': {
                                                            'feature_count': 15000,
                                                            'file_breakdown': None
                                                        }
                                                    }
                                                ]
                                            }
                                        ],
                                        'standalone_layers': [],
                                        'created_at': '2024-01-01T12:00:00Z'
                                    }
                                ],
                                'created_at': '2024-01-01T12:00:00Z'
                            }
                        ]
                    }
                }
            }
        },
        500: {
            'description': 'Server error',
            'content': {
                'application/json': {
                    'example': {
                        'error': 'Failed to load hierarchy',
                        'message': 'Database connection error'
                    }
                }
            }
        }
    }
)
class CompleteHierarchyAPIView(APIView):
    """
    Complete Hierarchy API - Enhanced Version
    
    Returns the complete hierarchy of states, cities, layer groups, layers, and features in a single API call.
    This provides comprehensive data about the entire system structure.
    
    GET /api/hierarchy/
    
    Response includes:
    - All states with their metadata
    - All cities within each state with map centers and statistics
    - All layer groups within each city
    - All data layers within each layer group with detailed information
    - Feature counts and processing status
    - Tile generation status and URLs
    - Bounding boxes and geometry information
    - Styling information (no layer taxonomy codes in JSON)
    """
    
    def get(self, request):
        """Get complete hierarchy with comprehensive statistics and metadata"""
        try:
            # Bulk feature count for all layers (avoids N+1: one query instead of per-layer COUNT)
            layer_ids = list(DataLayer.objects.filter(
                city__state_ref__is_active=True,
                city__is_active=True
            ).values_list('id', flat=True))
            feature_count_map = {}
            if layer_ids:
                counts = GeoFeature.objects.filter(
                    layer_id__in=layer_ids,
                    is_valid=True
                ).values('layer_id').annotate(cnt=Count('id'))
                feature_count_map = {r['layer_id']: r['cnt'] for r in counts}

            # Get all active states with their cities, layer groups, and layers
            states = State.objects.filter(is_active=True).prefetch_related(
                Prefetch(
                    'cities',
                    queryset=City.objects.filter(is_active=True).prefetch_related(
                        Prefetch(
                            'layer_groups',
                            queryset=LayerGroup.objects.all().select_related('category')
                        ),
                        Prefetch(
                            'layers',
                            queryset=DataLayer.objects.all().select_related('category', 'layer_group')
                        ),
                        Prefetch(
                            'layer_styles',
                            queryset=CityLayerStyle.objects.all().select_related('category')
                        )
                    )
                )
            )
            
            hierarchy_data = []
            total_states = 0
            total_cities = 0
            total_layers = 0
            total_features = 0
            
            for state in states:
                state_cities = []
                state_total_features = 0
                state_total_layers = 0
                
                for city in state.cities.all():
                    city_layer_groups = []
                    city_layers = []
                    city_total_features = 0
                    city_total_layers = 0
                    layers_with_tiles = 0
                    
                    # Process layer groups
                    for layer_group in city.layer_groups.all():
                        group_layers = []
                        group_feature_count = 0
                        
                        for layer in city.layers.all():
                            if layer.layer_group == layer_group:
                                layer_data = self._get_layer_data(layer, state.slug, city.slug, feature_count_map)
                                group_layers.append(layer_data)
                                group_feature_count += layer_data['statistics']['feature_count']
                                city_total_features += layer_data['statistics']['feature_count']
                                city_total_layers += 1
                                
                                if layer.tiles_generated:
                                    layers_with_tiles += 1
                        
                        layer_group_data = {
                            'id': layer_group.id,
                            'name': layer_group.name,
                            'slug': layer_group.slug,
                            'description': layer_group.description,
                            'directory_path': layer_group.directory_path,
                            'styling': {
                                'default_color': layer_group.default_color,
                                'default_stroke': layer_group.default_stroke,
                                'default_opacity': layer_group.default_opacity
                            },
                            'display_settings': {
                                'display_order': layer_group.display_order,
                                'is_visible': layer_group.is_visible,
                                'min_zoom': layer_group.min_zoom,
                                'max_zoom': layer_group.max_zoom
                            },
                            'statistics': {
                                'total_layers': len(group_layers),
                                'total_features': group_feature_count
                            },
                            'layers': group_layers
                        }
                        
                        city_layer_groups.append(layer_group_data)
                    
                    # Process layers not in groups (standalone layers)
                    standalone_layers = []
                    for layer in city.layers.all():
                        if not layer.layer_group:
                            layer_data = self._get_layer_data(layer, state.slug, city.slug, feature_count_map)
                            standalone_layers.append(layer_data)
                            city_total_features += layer_data['statistics']['feature_count']
                            city_total_layers += 1
                            
                            if layer.tiles_generated:
                                layers_with_tiles += 1
                    
                    # City layer styles (no taxonomy keys exposed)
                    city_styles = []
                    for style in city.layer_styles.all():
                        city_styles.append({
                            'id': style.id,
                            'fill_color': style.fill_color,
                            'stroke_color': style.stroke_color,
                            'opacity': style.opacity,
                            'stroke_width': style.stroke_width,
                            'pattern_config': style.get_pattern_config(),
                            'visibility': {
                                'is_visible': style.is_visible,
                                'min_zoom': style.min_zoom,
                                'max_zoom': style.max_zoom
                            }
                        })
                    
                    # City status summary
                    city_status = 'live' if layers_with_tiles > 0 else 'pending'
                    is_live = layers_with_tiles > 0
                    
                    city_data = {
                        'id': city.id,
                        'name': city.name,
                        'slug': city.slug,
                        'state': {
                            'name': state.name,
                            'slug': state.slug,
                            'code': state.code
                        },
                        'map_settings': {
                            'center_lat': city.center_lat,
                            'center_lng': city.center_lng,
                            'min_zoom': city.min_zoom,
                            'max_zoom': city.max_zoom
                        },
                        'status': {
                            'is_active': city.is_active,
                            'is_live': is_live,
                            'status': city_status
                        },
                        'statistics': {
                            'total_layer_groups': len(city_layer_groups),
                            'total_layers': city_total_layers,
                            'layers_with_tiles': layers_with_tiles,
                            'total_features': city_total_features,
                            'standalone_layers': len(standalone_layers)
                        },
                        'styling': city_styles,
                        'layer_groups': city_layer_groups,
                        'standalone_layers': standalone_layers,
                        'created_at': city.created_at.isoformat() if city.created_at else None
                    }
                    
                    state_cities.append(city_data)
                    state_total_features += city_total_features
                    state_total_layers += city_total_layers
                    total_cities += 1
                
                # State statistics
                state_data = {
                    'id': state.id,
                    'name': state.name,
                    'slug': state.slug,
                    'code': state.code,
                    'map_settings': {
                        'center_lat': state.center_lat,
                        'center_lng': state.center_lng,
                        'default_zoom': state.default_zoom
                    },
                    'status': {
                        'is_active': state.is_active
                    },
                    'statistics': {
                        'total_cities': len(state_cities),
                        'total_layers': state_total_layers,
                        'total_features': state_total_features
                    },
                    'cities': state_cities,
                    'created_at': state.created_at.isoformat() if state.created_at else None
                }
                
                hierarchy_data.append(state_data)
                total_states += 1
                total_layers += state_total_layers
                total_features += state_total_features
            
            # Global statistics
            global_stats = {
                'total_states': total_states,
                'total_cities': total_cities,
                'total_layers': total_layers,
                'total_features': total_features,
            }
            
            return Response({
                'status': 'success',
                'timestamp': timezone.now().isoformat(),
                'global_statistics': global_stats,
                'hierarchy': hierarchy_data
            })
            
        except Exception as e:
            logger.error(f"Error in CompleteHierarchyAPIView: {e}")
            return Response({
                'error': 'Failed to load hierarchy',
                'message': str(e)
            }, status=500)
    
    def _get_layer_data(self, layer, state_slug, city_slug, feature_count_map=None):
        """Get comprehensive layer data. feature_count_map avoids N+1 (layer_id -> count)."""
        if feature_count_map is not None:
            layer_feature_count = feature_count_map.get(layer.id, 0)
        else:
            layer_feature_count = GeoFeature.objects.filter(layer=layer, is_valid=True).count()
        
        # Get tile URLs if tiles are generated
        tile_urls = None
        if layer.tiles_generated:
            tile_urls = self._get_layer_tile_urls(state_slug, city_slug, layer.slug, True)
        
        # Get feature breakdown by source file if it's a directory layer
        file_breakdown = None
        if layer.is_directory:
            try:
                file_breakdown = layer.get_file_features_breakdown()
            except:
                file_breakdown = None
        
        return {
            'id': layer.id,
            'name': layer.name,
            'slug': layer.slug,
            'description': layer.description,
            'is_true': layer.is_true,  # Layer visibility control
            'file_info': {
                'original_filename': layer.original_filename,
                'file_format': layer.file_format,
                'file_path': layer.file_path,
                'is_directory': layer.is_directory,
                'file_pattern': layer.file_pattern,
                'source_files_count': len(layer.source_files) if layer.source_files else 0
            },
            'geometry_info': {
                'geometry_type': layer.geometry_type,
                'has_valid_bbox': layer.has_valid_bbox(),
                'bounds': {
                    'xmin': layer.bbox_xmin,
                    'ymin': layer.bbox_ymin,
                    'xmax': layer.bbox_xmax,
                    'ymax': layer.bbox_ymax
                } if layer.has_valid_bbox() else None,
                'center_point': layer.get_center_point()
            },
            'processing_status': {
                'is_processed': layer.is_processed,
                'tiles_generated': layer.tiles_generated,
                'feature_count': layer_feature_count,
                'processing_errors': layer.processing_errors
            },
            'tile_info': {
                'tiles_generated': layer.tiles_generated,
                'tile_cache_size': layer.tile_cache_size,
                'tile_urls': tile_urls
            },
            'metadata': {
                'data_source': layer.data_source,
                'last_updated': layer.last_updated.isoformat() if layer.last_updated else None,
                'created_at': layer.created_at.isoformat(),
                'updated_at': layer.updated_at.isoformat()
            },
            'statistics': {
                'feature_count': layer_feature_count,
                'file_breakdown': file_breakdown
            }
        }
    
    def _get_layer_tile_urls(self, state_slug, city_slug, layer_slug, include_cloudfront=True):
        """Tile URL templates on the Django proxy only; CDN is used only server-side to fetch bytes."""
        base = hierarchical_tile_proxy_url_for_client(state_slug, city_slug, layer_slug)
        return {
            'png_template': f"{base}/{{z}}/{{x}}/{{y}}.png",
            'mvt_template': f"{base}/{{z}}/{{x}}/{{y}}.mvt",
            'api_png_template': f"{base}/{{z}}/{{x}}/{{y}}.png",
            'api_mvt_template': f"{base}/{{z}}/{{x}}/{{y}}.mvt",
            'cloudfront_base': f"{base}/",
            'api_base': f"{base}/"
        }


# Cache key and TTL for optimized hierarchy (5 min)
HIERARCHY_V2_CACHE_KEY = 'hierarchy_v2_response'
HIERARCHY_V2_CACHE_KEY_MINIMAL = 'hierarchy_v2_response_minimal'
HIERARCHY_V2_CACHE_TTL = 300


def _build_layer_data_minimal(layer, state_slug, city_slug, feature_count_map):
    """Minimal layer payload: id, slug, name, feature_count, tiles, bounds, tile URL."""
    fc = feature_count_map.get(layer.id, 0)
    tile_template = None
    if layer.tiles_generated:
        b = hierarchical_tile_proxy_url_for_client(state_slug, city_slug, layer.slug)
        tile_template = f"{b}/{{z}}/{{x}}/{{y}}.png"
    bounds = None
    if layer.bbox_xmin is not None and layer.bbox_ymin is not None and layer.bbox_xmax is not None and layer.bbox_ymax is not None:
        bounds = {'xmin': layer.bbox_xmin, 'ymin': layer.bbox_ymin, 'xmax': layer.bbox_xmax, 'ymax': layer.bbox_ymax}
    return {
        'id': layer.id,
        'name': layer.name,
        'slug': layer.slug,
        'feature_count': fc,
        'tiles_generated': layer.tiles_generated,
        'bounds': bounds,
        'tile_url_template': tile_template,
    }


def _build_layer_data_optimized(layer, state_slug, city_slug, feature_count_map):
    """Build layer payload using precomputed feature count (no extra queries)."""
    layer_feature_count = feature_count_map.get(layer.id, 0)
    tile_urls = None
    if layer.tiles_generated:
        base = hierarchical_tile_proxy_url_for_client(state_slug, city_slug, layer.slug)
        tile_urls = {
            'png_template': f"{base}/{{z}}/{{x}}/{{y}}.png",
            'mvt_template': f"{base}/{{z}}/{{x}}/{{y}}.mvt",
            'api_png_template': f"{base}/{{z}}/{{x}}/{{y}}.png",
            'api_mvt_template': f"{base}/{{z}}/{{x}}/{{y}}.mvt",
            'cloudfront_base': f"{base}/",
            'api_base': f"{base}/"
        }
    return {
        'id': layer.id,
        'name': layer.name,
        'slug': layer.slug,
        'description': layer.description or '',
        'is_true': layer.is_true,
        'file_info': {
            'original_filename': layer.original_filename,
            'file_format': layer.file_format,
            'file_path': layer.file_path,
            'is_directory': layer.is_directory,
            'file_pattern': layer.file_pattern,
            'source_files_count': len(layer.source_files) if layer.source_files else 0
        },
        'geometry_info': {
            'geometry_type': layer.geometry_type,
            'has_valid_bbox': layer.has_valid_bbox(),
            'bounds': {
                'xmin': layer.bbox_xmin,
                'ymin': layer.bbox_ymin,
                'xmax': layer.bbox_xmax,
                'ymax': layer.bbox_ymax
            } if layer.has_valid_bbox() else None,
            'center_point': layer.get_center_point()
        },
        'processing_status': {
            'is_processed': layer.is_processed,
            'tiles_generated': layer.tiles_generated,
            'feature_count': layer_feature_count,
            'processing_errors': layer.processing_errors
        },
        'tile_info': {
            'tiles_generated': layer.tiles_generated,
            'tile_cache_size': layer.tile_cache_size,
            'tile_urls': tile_urls
        },
        'metadata': {
            'data_source': layer.data_source,
            'last_updated': layer.last_updated.isoformat() if layer.last_updated else None,
            'created_at': layer.created_at.isoformat(),
            'updated_at': layer.updated_at.isoformat()
        },
        'statistics': {
            'feature_count': layer_feature_count,
            'file_breakdown': None
        }
    }


def _build_layer_data_full_trimmed(layer, state_slug, city_slug, feature_count_map):
    """Trimmed layer payload for hierarchy v2: id, name, slug, feature_count; tile_urls only when present."""
    layer_feature_count = feature_count_map.get(layer.id, 0)
    tile_urls = None
    if layer.tiles_generated:
        base = hierarchical_tile_proxy_url_for_client(state_slug, city_slug, layer.slug)
        tile_urls = {
            'png_template': f"{base}/{{z}}/{{x}}/{{y}}.png",
            'mvt_template': f"{base}/{{z}}/{{x}}/{{y}}.mvt",
            'api_png_template': f"{base}/{{z}}/{{x}}/{{y}}.png",
            'api_mvt_template': f"{base}/{{z}}/{{x}}/{{y}}.mvt",
            'cloudfront_base': f"{base}/",
            'api_base': f"{base}/"
        }
    out = {
        'id': layer.id,
        'name': layer.name,
        'slug': layer.slug,
        'feature_count': layer_feature_count,
    }
    if tile_urls is not None:
        out['tile_urls'] = tile_urls
    return out


class OptimizedHierarchyAPIView(APIView):
    """
    Optimized hierarchy API – same graph data as /api/hierarchy/ with fewer queries and caching.

    - One bulk query for all layer feature counts (no N+1).
    - Response cached for 5 minutes (invalidate by query param ?refresh=1).
    - Full response: no categories/map_settings/styling; layers have id, name, slug, feature_count,
      and tile_urls only when tiles exist; layer_groups have id, name, slug, layers only.
    - ?minimal=1 returns a lean payload: no styling, no file_info/metadata, only structure + ids, slugs, bounds, tile URL.

    GET /api/hierarchy/v2/           full response (trimmed)
    GET /api/hierarchy/v2/?minimal=1  minimal response (recommended for map UIs)
    GET /api/hierarchy/v2/?refresh=1  bypass cache
    """
    permission_classes = [AllowAny]

    def get(self, request):
        minimal = request.query_params.get('minimal', '').lower() in ('1', 'true', 'yes')
        refresh = request.query_params.get('refresh')
        cache_key = HIERARCHY_V2_CACHE_KEY_MINIMAL if minimal else HIERARCHY_V2_CACHE_KEY
        if refresh:
            cache.delete(HIERARCHY_V2_CACHE_KEY)
            cache.delete(HIERARCHY_V2_CACHE_KEY_MINIMAL)
        payload = cache.get(cache_key)
        if payload is not None:
            return Response(payload)

        try:
            layer_ids = list(DataLayer.objects.filter(
                city__state_ref__is_active=True,
                city__is_active=True
            ).values_list('id', flat=True))
            feature_count_map = {}
            if layer_ids:
                counts = GeoFeature.objects.filter(
                    layer_id__in=layer_ids,
                    is_valid=True
                ).values('layer_id').annotate(cnt=Count('id'))
                feature_count_map = {r['layer_id']: r['cnt'] for r in counts}

            if minimal:
                states = State.objects.filter(is_active=True).prefetch_related(
                    Prefetch(
                        'cities',
                        queryset=City.objects.filter(is_active=True).prefetch_related(
                            Prefetch('layer_groups', queryset=LayerGroup.objects.all().select_related('category')),
                            Prefetch('layers', queryset=DataLayer.objects.all().select_related('category', 'layer_group')),
                        )
                    )
                )
                payload = self._build_minimal_hierarchy(states, feature_count_map)
            else:
                states = State.objects.filter(is_active=True).prefetch_related(
                    Prefetch(
                        'cities',
                        queryset=City.objects.filter(is_active=True).prefetch_related(
                            Prefetch(
                                'layer_groups',
                                queryset=LayerGroup.objects.all().select_related('category')
                            ),
                            Prefetch(
                                'layers',
                                queryset=DataLayer.objects.all().select_related('category', 'layer_group')
                            )
                        )
                    )
                )
                payload = self._build_full_hierarchy(states, feature_count_map)

            cache.set(cache_key, payload, HIERARCHY_V2_CACHE_TTL)
            return Response(payload)

        except Exception as e:
            logger.exception("OptimizedHierarchyAPIView error: %s", e)
            return Response({
                'error': 'Failed to load hierarchy',
                'message': str(e)
            }, status=500)

    def _build_minimal_hierarchy(self, states, feature_count_map):
        """Build hierarchy with only essential fields: no styling, no file_info, no metadata."""
        hierarchy_data = []
        total_states = 0
        total_cities = 0
        total_layers = 0
        total_features = 0

        for state in states:
            state_cities = []
            state_layers = 0
            state_features = 0

            for city in state.cities.all():
                city_layers = list(city.layers.all())
                group_list = []
                standalone_list = []
                city_features = 0
                layers_with_tiles = 0

                for layer_group in city.layer_groups.all():
                    group_layers = []
                    for layer in city_layers:
                        if layer.layer_group_id == layer_group.id:
                            ld = _build_layer_data_minimal(layer, state.slug, city.slug, feature_count_map)
                            group_layers.append(ld)
                            city_features += ld['feature_count']
                            if layer.tiles_generated:
                                layers_with_tiles += 1
                    group_list.append({
                        'id': layer_group.id,
                        'name': layer_group.name,
                        'slug': layer_group.slug,
                        'layers': group_layers,
                    })

                for layer in city_layers:
                    if not layer.layer_group_id:
                        ld = _build_layer_data_minimal(layer, state.slug, city.slug, feature_count_map)
                        standalone_list.append(ld)
                        city_features += ld['feature_count']
                        if layer.tiles_generated:
                            layers_with_tiles += 1

                state_cities.append({
                    'id': city.id,
                    'name': city.name,
                    'slug': city.slug,
                    'state': {'name': state.name, 'slug': state.slug, 'code': state.code},
                    'center_lat': city.center_lat,
                    'center_lng': city.center_lng,
                    'min_zoom': city.min_zoom,
                    'max_zoom': city.max_zoom,
                    'is_live': layers_with_tiles > 0,
                    'layer_groups': group_list,
                    'standalone_layers': standalone_list,
                })
                state_layers += sum(len(g['layers']) for g in group_list) + len(standalone_list)
                state_features += city_features
                total_cities += 1

            hierarchy_data.append({
                'id': state.id,
                'name': state.name,
                'slug': state.slug,
                'code': state.code,
                'center_lat': state.center_lat,
                'center_lng': state.center_lng,
                'default_zoom': state.default_zoom,
                'cities': state_cities,
            })
            total_states += 1
            total_layers += state_layers
            total_features += state_features

        return {
            'status': 'success',
            'timestamp': timezone.now().isoformat(),
            'hierarchy': hierarchy_data,
        }

    def _build_full_hierarchy(self, states, feature_count_map):
        """Build full hierarchy without categories, map_settings, styling, or per-layer metadata/processing/tile_info."""
        hierarchy_data = []
        total_states = 0
        total_cities = 0
        total_layers = 0
        total_features = 0

        for state in states:
            state_cities = []
            state_total_features = 0
            state_total_layers = 0

            for city in state.cities.all():
                city_layer_groups = []
                city_layers = list(city.layers.all())
                city_total_features = 0
                city_total_layers = 0
                layers_with_tiles = 0

                for layer_group in city.layer_groups.all():
                    group_layers = []
                    group_feature_count = 0
                    for layer in city_layers:
                        if layer.layer_group_id == layer_group.id:
                            layer_data = _build_layer_data_full_trimmed(
                                layer, state.slug, city.slug, feature_count_map
                            )
                            group_layers.append(layer_data)
                            fc = layer_data['feature_count']
                            group_feature_count += fc
                            city_total_features += fc
                            city_total_layers += 1
                            if layer.tiles_generated:
                                layers_with_tiles += 1
                    layer_group_data = {
                        'id': layer_group.id,
                        'name': layer_group.name,
                        'slug': layer_group.slug,
                        'layers': group_layers
                    }
                    city_layer_groups.append(layer_group_data)

                standalone_layers = []
                for layer in city_layers:
                    if not layer.layer_group_id:
                        layer_data = _build_layer_data_full_trimmed(
                            layer, state.slug, city.slug, feature_count_map
                        )
                        standalone_layers.append(layer_data)
                        city_total_features += layer_data['feature_count']
                        city_total_layers += 1
                        if layer.tiles_generated:
                            layers_with_tiles += 1

                city_data = {
                    'id': city.id,
                    'name': city.name,
                    'slug': city.slug,
                    'state': {
                        'name': state.name,
                        'slug': state.slug,
                        'code': state.code
                    },
                    'layer_groups': city_layer_groups,
                    'standalone_layers': standalone_layers,
                }
                state_cities.append(city_data)
                state_total_features += city_total_features
                state_total_layers += city_total_layers
                total_cities += 1

            state_data = {
                'id': state.id,
                'name': state.name,
                'slug': state.slug,
                'code': state.code,
                'cities': state_cities,
            }
            hierarchy_data.append(state_data)
            total_states += 1
            total_layers += state_total_layers
            total_features += state_total_features

        return {
            'status': 'success',
            'timestamp': timezone.now().isoformat(),
            'hierarchy': hierarchy_data
        }


