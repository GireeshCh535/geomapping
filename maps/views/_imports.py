from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Prefetch
from django.db import connection, close_old_connections
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.conf import settings
from django.core.cache import cache
import hashlib
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import HttpResponseRedirect, HttpResponse
from django.core.paginator import EmptyPage, Paginator
from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.db.models.functions import Distance
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from ..models import *
from ..serializers import *
from ..tile_path_service import (
    TilePathService,
    client_tile_proxy_api_root,
    developer_raster_path_valid,
    hierarchical_tile_proxy_base,
    hierarchical_tile_proxy_url_for_client,
    is_developer_data_tile_request,
    public_https_base_for_s3_tile_prefix,
    tile_proxy_png_template_from_s3_tile_path,
)
from ..developer_listing_map_bounds import (
    DEVELOPER_LISTING_DEFAULT_ZOOM,
    recommended_zoom_from_area,
    tighten_bounds_for_map_fit,
)
from ..feature_legend_display import (
    AIRPORT_POLYGON_FILL_FROM_GEOJSON_SLUGS,
    CRZ_SEARCH_LAYER_SLUGS,
    HIGHWAY_INFRASTRUCTURE_POPUP_SLUGS,
    fill_hex_from_geojson_properties_for_legend,
    _filter_crz_geojson_properties,
    _highway_infra_legend_popup_text,
    _masterplan_fill_color_svg_data_uri,
)

# `from ._imports import *` omits names starting with '_' (see importlib). Expose
# public aliases so view submodules get these helpers via star-import.
masterplan_fill_color_svg_data_uri = _masterplan_fill_color_svg_data_uri
filter_crz_geojson_properties = _filter_crz_geojson_properties
highway_infra_legend_popup_text = _highway_infra_legend_popup_text

import copy
import logging
import json
import boto3
import requests
import psycopg2
from psycopg2 import OperationalError, DatabaseError

# Single logger name for all view submodules (matches geo_mapping/settings.py LOGGING).
logger = logging.getLogger('maps.views')
