from ._imports import *


class DeveloperListingDetailAPIView(APIView):
    """
    API endpoint to retrieve complete developer listing details
    including media files, TIF metadata, and webhook events.
    
    GET /api/developer-listings/{listing_type}/{listing_id}/
    
    Returns:
    - Complete listing data
    - All media files with TIF metadata
    - Tile generation status
    - Recent webhook events
    - Media and tile summaries
    """
    permission_classes = [AllowAny]  # Make public or add authentication as needed
    
    def get(self, request, listing_type, listing_id):
        """Get complete details for a developer listing"""
        from ..models import DeveloperListing
        from ..serializers import DeveloperListingDetailSerializer
        
        try:
            # Validate listing_type
            if listing_type not in ['developerland', 'developerplot']:
                return Response(
                    {'error': f'Invalid listing_type. Must be "developerland" or "developerplot"'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get listing
            try:
                listing = DeveloperListing.objects.prefetch_related(
                    'media_files',
                    'media_files__tif_metadata'
                ).get(
                    listing_type=listing_type,
                    backend_listing_id=listing_id
                )
            except DeveloperListing.DoesNotExist:
                return Response(
                    {
                        'error': f'Listing not found',
                        'listing_type': listing_type,
                        'listing_id': listing_id
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Serialize and return
            serializer = DeveloperListingDetailSerializer(listing)
            
            return Response(
                {
                    'success': True,
                    'listing': serializer.data
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error retrieving developer listing details: {e}", exc_info=True)
            return Response(
                {
                    'error': 'Internal server error',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeveloperListingListAPIView(APIView):
    """
    API endpoint to list all developer listings with filtering
    
    GET /api/developer-listings/
    
    Query parameters:
    - listing_type: Filter by type (developerland, developerplot)
    - city: Filter by city name
    - state: Filter by state name
    - is_active: Filter by active status (true/false)
    - has_tiles: Filter listings with TIF tiles (true/false)
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """List developer listings with filtering"""
        from ..models import DeveloperListing
        from ..serializers import DeveloperListingSerializer
        
        try:
            # Get query parameters
            listing_type = request.query_params.get('listing_type')
            city = request.query_params.get('city')
            state = request.query_params.get('state')
            is_active = request.query_params.get('is_active')
            has_tiles = request.query_params.get('has_tiles')
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
            
            # Build queryset
            queryset = DeveloperListing.objects.prefetch_related('media_files').all()
            
            # Apply filters
            if listing_type:
                if listing_type not in ['developerland', 'developerplot']:
                    return Response(
                        {'error': 'Invalid listing_type. Must be "developerland" or "developerplot"'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                queryset = queryset.filter(listing_type=listing_type)
            
            if city:
                queryset = queryset.filter(city__icontains=city)
            
            if state:
                queryset = queryset.filter(state__icontains=state)
            
            if is_active is not None:
                is_active_bool = is_active.lower() == 'true'
                queryset = queryset.filter(is_active=is_active_bool)
            
            if has_tiles is not None:
                has_tiles_bool = has_tiles.lower() == 'true'
                if has_tiles_bool:
                    # Filter listings that have at least one TIF with generated tiles
                    queryset = queryset.filter(
                        media_files__is_tif=True,
                        media_files__tiles_generated=True
                    ).distinct()
                else:
                    # Filter listings without any generated TIF tiles
                    from django.db.models import Q
                    queryset = queryset.exclude(
                        media_files__is_tif=True,
                        media_files__tiles_generated=True
                    ).distinct()
            
            # Order by most recent
            queryset = queryset.order_by('-created_at')
            
            # Pagination
            total_count = queryset.count()
            start = (page - 1) * page_size
            end = start + page_size
            listings = queryset[start:end]
            
            # Serialize
            serializer = DeveloperListingSerializer(listings, many=True)
            
            return Response(
                {
                    'success': True,
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total_count': total_count,
                        'total_pages': (total_count + page_size - 1) // page_size,
                        'has_next': end < total_count,
                        'has_previous': page > 1
                    },
                    'filters': {
                        'listing_type': listing_type,
                        'city': city,
                        'state': state,
                        'is_active': is_active,
                        'has_tiles': has_tiles
                    },
                    'listings': serializer.data
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error listing developer listings: {e}", exc_info=True)
            return Response(
                {
                    'error': 'Internal server error',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EnrichmentLookupAPIView(APIView):
    """
    POST API: return enrichment and full record data for land/plot/developer_land/developer_plot by IDs.

    POST /api/enrichment-lookup/
    Body: { "listing_type": "land"|"plot"|"developer_land"|"developer_plot", "ids": [1, 2, 3] }
    ids can be either Django primary keys (id) or backend_id (1acre-be API id); both are matched.

    Returns: { "results": [ {...}, ... ], "count": N } with enrichment (enriched_layers with optional
    nearest_point per layer, enriched_at, location_point) and all other model fields + payload.
    """
    permission_classes = [AllowAny]

    # Map listing_type -> (Model, backend_id field name)
    _MODEL_MAP = None

    @classmethod
    def _get_model_map(cls):
        if cls._MODEL_MAP is None:
            from ..models import SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot
            cls._MODEL_MAP = {
                'land': SyncedLand,
                'plot': SyncedPlot,
                'developer_land': SyncedDeveloperLand,
                'developer_plot': SyncedDeveloperPlot,
            }
        return cls._MODEL_MAP

    @staticmethod
    def _serialize_point(point):
        if point is None:
            return None
        try:
            return {'type': 'Point', 'coordinates': [point.x, point.y]}
        except Exception:
            return None

    def _record_to_dict(self, obj):
        """Build a dict with all fields + enrichment for one synced record."""
        from django.forms.models import model_to_dict
        d = model_to_dict(obj, exclude=['location_point'])
        d['id'] = obj.pk
        d['backend_id'] = getattr(obj, 'backend_id', None)
        raw_layers = getattr(obj, 'enriched_layers', []) or []
        d['enriched_layers'] = [dict(entry) for entry in raw_layers]
        d['enriched_at'] = obj.enriched_at.isoformat() if getattr(obj, 'enriched_at', None) else None
        d['location_point'] = self._serialize_point(getattr(obj, 'location_point', None))
        if hasattr(obj, 'lat') and obj.lat is not None:
            d['lat'] = obj.lat
        if hasattr(obj, 'long') and obj.long is not None:
            d['long'] = obj.long
        d['payload'] = getattr(obj, 'payload', {}) or {}
        d['synced_at'] = obj.synced_at.isoformat() if getattr(obj, 'synced_at', None) else None
        # True when no coordinates -> enrichment not run or cleared; client can treat as null/false
        has_point = getattr(obj, 'location_point', None) is not None
        if not has_point and hasattr(obj, 'lat') and hasattr(obj, 'long'):
            has_point = obj.lat is not None and obj.long is not None
        if not has_point and hasattr(obj, 'payload') and obj.payload:
            p = obj.payload
            has_point = (p.get('lat') or p.get('latitude')) is not None and (p.get('long') or p.get('lng') or p.get('longitude')) is not None
        d['enrichment_skipped'] = not has_point
        return d

    def post(self, request):
        from ..models import SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot

        try:
            data = request.data if getattr(request, 'data', None) is not None else {}
            if not isinstance(data, dict):
                return Response(
                    {'error': 'Request body must be JSON with listing_type and ids'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            listing_type = (data.get('listing_type') or '').strip().lower()
            ids = data.get('ids')
            if not listing_type:
                return Response(
                    {'error': 'Missing listing_type. Use one of: land, plot, developer_land, developer_plot'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            model_map = self._get_model_map()
            if listing_type not in model_map:
                return Response(
                    {'error': f'Invalid listing_type "{listing_type}". Use one of: land, plot, developer_land, developer_plot'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if ids is None:
                ids = []
            if not isinstance(ids, list):
                ids = [ids] if ids is not None else []
            ids = [int(x) for x in ids if x is not None and str(x).strip() != '']
            ids = list(dict.fromkeys(ids))

            model = model_map[listing_type]
            if ids:
                qs = model.objects.filter(
                    Q(backend_id__in=ids) | Q(pk__in=ids)
                ).distinct()
            else:
                qs = model.objects.none()
            records = list(qs)
            results = [self._record_to_dict(r) for r in records]

            # Resolve "place" (specific feature) for each enriched layer (Fix 5: cache in Redis, TTL 30 min)
            from ..listing_layer_enrichment_service import get_place_for_point_in_layer
            from django.contrib.gis.geos import Point
            _PLACE_CACHE_TTL = 1800  # 30 minutes
            for record, result in zip(records, results):
                point = getattr(record, 'location_point', None)
                if point is None and getattr(record, 'long', None) is not None and getattr(record, 'lat', None) is not None:
                    try:
                        point = Point(float(record.long), float(record.lat), srid=4326)
                    except (TypeError, ValueError):
                        point = None
                if point is None:
                    continue
                point_wkt_hash = hashlib.md5((getattr(point, 'wkt', '') or '').encode()).hexdigest()
                enriched = result.get('enriched_layers') or []
                for layer_entry in enriched:
                    layer_id = layer_entry.get('layer_id')
                    distance_km = layer_entry.get('distance_km', 0)
                    if layer_id is None:
                        continue
                    distance_bucket = '0' if (distance_km or 0) == 0 else '1'
                    place_cache_key = f"enrichment_place:v2:{point_wkt_hash}:{layer_id}:{distance_bucket}"
                    cached_place = cache.get(place_cache_key)
                    if cached_place is not None:
                        layer_entry['place'] = cached_place
                    else:
                        place = get_place_for_point_in_layer(point, layer_id, distance_km)
                        layer_entry['place'] = place
                        if place is not None:
                            cache.set(place_cache_key, place, _PLACE_CACHE_TTL)

            return Response(
                {
                    'listing_type': listing_type,
                    'count': len(results),
                    'results': results,
                },
                status=status.HTTP_200_OK
            )
        except (ValueError, TypeError) as e:
            return Response(
                {'error': 'ids must be a list of integers', 'details': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Enrichment lookup error: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LayerPointCountsAPIView(APIView):
    """
    Point counts (and optional details) per layer. Fast default: counts only, no details.
    - GET /api/layer-point-counts/  → counts for first 50 layers (include_details=false by default).
    - GET /api/layer-point-counts/?layer_ids=1,2,3  → counts for those layers only.
    - Add ?include_details=true for overlapping_details and nearby_details (slower).
    - When include_details=true, details are paginated: detail_page (default 1), detail_page_size (default 100, max 500).
    - Response includes overlapping_pagination and nearby_pagination (page, page_size, total_count, total_pages, has_next, has_previous).
    GET example: ?layer_ids=492&include_details=true&detail_page=1&detail_page_size=100
    POST body: { "layer_ids": [1,2], "within_km": 30, "include_details": false, "detail_limit": 200, "detail_page": 1, "detail_page_size": 100 }
    """
    permission_classes = [AllowAny]

    def _parse_request(self, request):
        layer_ids = None
        within_km = 30.0
        include_details = False  # default False for faster response; pass include_details=true for details
        detail_limit = 200
        detail_page = 1
        detail_page_size = 100
        data = None
        if request.method == 'POST' and getattr(request, 'data', None) and isinstance(request.data, dict):
            data = request.data
        else:
            data = dict(request.query_params) if hasattr(request, 'query_params') else {}
            # query_params values are lists
            for k, v in data.items():
                if isinstance(v, list) and len(v) == 1:
                    data[k] = v[0]
        if data:
            layer_ids = data.get('layer_ids')
            if isinstance(layer_ids, str) and layer_ids:
                try:
                    layer_ids = [int(x.strip()) for x in layer_ids.split(',') if x.strip()]
                except (ValueError, TypeError):
                    layer_ids = None
            elif not isinstance(layer_ids, list):
                layer_ids = None
            if data.get('within_km') is not None:
                try:
                    within_km = float(data.get('within_km'))
                except (TypeError, ValueError):
                    within_km = 30.0
            if data.get('include_details') is not None:
                include_details = str(data.get('include_details')).lower() in ('1', 'true', 'yes')
            if data.get('detail_limit') is not None:
                try:
                    detail_limit = max(0, min(1000, int(data.get('detail_limit'))))
                except (TypeError, ValueError):
                    detail_limit = 200
            if data.get('detail_page') is not None:
                try:
                    detail_page = max(1, int(data.get('detail_page')))
                except (TypeError, ValueError):
                    detail_page = 1
            if data.get('detail_page_size') is not None:
                try:
                    detail_page_size = max(1, min(500, int(data.get('detail_page_size'))))
                except (TypeError, ValueError):
                    detail_page_size = 100
        if request.method == 'GET' and not data:
            layer_ids_str = request.query_params.get('layer_ids', '')
            if layer_ids_str:
                try:
                    layer_ids = [int(x.strip()) for x in layer_ids_str.split(',') if x.strip()]
                except (ValueError, TypeError):
                    layer_ids = None
            w = request.query_params.get('within_km')
            if w is not None:
                try:
                    within_km = float(w)
                except (TypeError, ValueError):
                    within_km = 30.0
            include_details = str(request.query_params.get('include_details', 'false')).lower() in ('1', 'true', 'yes')
            try:
                detail_limit = max(0, min(1000, int(request.query_params.get('detail_limit', 200))))
            except (TypeError, ValueError):
                detail_limit = 200
            try:
                detail_page = max(1, int(request.query_params.get('detail_page', 1)))
            except (TypeError, ValueError):
                detail_page = 1
            try:
                detail_page_size = max(1, min(500, int(request.query_params.get('detail_page_size', 100))))
            except (TypeError, ValueError):
                detail_page_size = 100
        return layer_ids, within_km, include_details, detail_limit, detail_page, detail_page_size

    def _counts_from_cache(self, layer_ids, within_km):
        """Resolve layer_ids if None, then return list of count dicts from LayerPointCountCache with lazy refresh on miss."""
        from ..models import DataLayer, LayerPointCountCache
        from ..listing_layer_enrichment_service import (
            refresh_layer_point_count_cache,
            NEARBY_THRESHOLD_KM,
            MAX_LAYERS_DEFAULT,
        )
        if layer_ids is None:
            layer_ids = list(
                DataLayer.objects.filter(
                    is_processed=True,
                    city__is_active=True,
                )
                .exclude(category__code='DEVELOPER_LISTING')
                .exclude(
                    bbox_xmin__isnull=True, bbox_ymin__isnull=True,
                    bbox_xmax__isnull=True, bbox_ymax__isnull=True,
                )
                .order_by('id')
                .values_list('id', flat=True)[:MAX_LAYERS_DEFAULT]
            )
        if not layer_ids:
            return []
        w_km = within_km if within_km is not None else NEARBY_THRESHOLD_KM
        cache_qs = LayerPointCountCache.objects.filter(
            layer_id__in=layer_ids,
            within_km=w_km,
        ).select_related('layer', 'layer__city')
        cached_layer_ids = set(cache_qs.values_list('layer_id', flat=True))
        missing = [lid for lid in layer_ids if lid not in cached_layer_ids]
        if missing:
            refresh_layer_point_count_cache(layer_ids=missing, within_km=w_km)
            cache_qs = LayerPointCountCache.objects.filter(
                layer_id__in=layer_ids,
                within_km=w_km,
            ).select_related('layer', 'layer__city')
        counts = []
        for c in cache_qs:
            layer = c.layer
            counts.append({
                'layer_id': layer.id,
                'layer_slug': layer.slug or '',
                'city': (layer.city.name if layer.city else ''),
                'overlapping_count': c.overlapping_count,
                'nearby_count': c.nearby_count,
                'total_count': c.total_count,
                'by_source': c.by_source or {},
            })
        # Preserve requested order
        id_to_row = {r['layer_id']: r for r in counts}
        return [id_to_row[lid] for lid in layer_ids if lid in id_to_row]

    def _details_from_cache(self, counts, detail_page, detail_page_size):
        """Attach overlapping_details and nearby_details from LayerPointCountDetail (paginated)."""
        from ..models import LayerPointCountDetail
        page = max(1, detail_page)
        page_size = max(1, min(500, detail_page_size))
        offset = (page - 1) * page_size
        for row in counts:
            lid = row['layer_id']
            over_total = row['overlapping_count']
            near_total = row['nearby_count']
            over_pages = (over_total + page_size - 1) // page_size if page_size else 0
            near_pages = (near_total + page_size - 1) // page_size if page_size else 0
            overlapping_qs = LayerPointCountDetail.objects.filter(
                layer_id=lid, is_overlapping=True
            ).order_by('id')[offset:offset + page_size].values('source', 'point_id', 'backend_id', 'lat', 'lng')
            overlapping_details = [
                {'source': d['source'], 'id': d['point_id'], 'backend_id': d['backend_id'], 'lat': d['lat'], 'lng': d['lng']}
                for d in overlapping_qs
            ]
            nearby_qs = LayerPointCountDetail.objects.filter(
                layer_id=lid, is_overlapping=False
            ).order_by('id')[offset:offset + page_size].values('source', 'point_id', 'backend_id', 'lat', 'lng')
            nearby_details = [
                {'source': d['source'], 'id': d['point_id'], 'backend_id': d['backend_id'], 'lat': d['lat'], 'lng': d['lng']}
                for d in nearby_qs
            ]
            row['overlapping_details'] = overlapping_details
            row['nearby_details'] = nearby_details
            row['overlapping_pagination'] = {
                'page': page,
                'page_size': page_size,
                'total_count': over_total,
                'total_pages': over_pages,
                'has_next': page < over_pages,
                'has_previous': page > 1,
            }
            row['nearby_pagination'] = {
                'page': page,
                'page_size': page_size,
                'total_count': near_total,
                'total_pages': near_pages,
                'has_next': page < near_pages,
                'has_previous': page > 1,
            }

    def get(self, request):
        layer_ids, within_km, include_details, detail_limit, detail_page, detail_page_size = self._parse_request(request)
        try:
            counts = self._counts_from_cache(layer_ids, within_km)
            if not include_details:
                return Response({'counts': counts}, status=status.HTTP_200_OK)
            self._details_from_cache(counts, detail_page, detail_page_size)
            return Response({'counts': counts}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Layer point counts error: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        layer_ids, within_km, include_details, detail_limit, detail_page, detail_page_size = self._parse_request(request)
        try:
            counts = self._counts_from_cache(layer_ids, within_km)
            if not include_details:
                return Response({'counts': counts}, status=status.HTTP_200_OK)
            self._details_from_cache(counts, detail_page, detail_page_size)
            return Response({'counts': counts}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Layer point counts error: {e}", exc_info=True)
            return Response(
                {'error': 'Internal server error', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LayerListingLinksAPIView(APIView):
    """
    GET edges from LayerListingLink for one DataLayer (lookup by DataLayer.slug; must be unique across DB).

    GET /api/layers/<layer_slug>/listing-links/
    Query:
      - source (optional): land | plot | developer_land | developer_plot
      - distance_km (optional): maximum distance in km — rows with distance_km <= this value (0 = inside layer)
      - page (default 1)
      - page_size (default 10, max 100)

    Only returns links where the denormalized listing is status=active and exposure_type=public (case-insensitive).

    Each result includes the corresponding Synced* row as `listing` (payload, enriched_layers, etc.), same shape as POST /api/enrichment-lookup/.
    """
    permission_classes = [AllowAny]

    _MAX_PAGE_SIZE = 100
    _VALID_SOURCES = frozenset({'land', 'plot', 'developer_land', 'developer_plot'})

    @staticmethod
    def _resolve_layer(layer_slug):
        """Return (DataLayer|None, error_response|None). Ambiguous slug if same slug exists in multiple cities."""
        from ..models import DataLayer

        slug = (layer_slug or '').strip()
        if not slug:
            return None, Response({'error': 'Invalid layer slug'}, status=status.HTTP_400_BAD_REQUEST)
        matches = list(DataLayer.objects.filter(slug=slug).select_related('city')[:2])
        if not matches:
            return None, Response({'error': 'Layer not found'}, status=status.HTTP_404_NOT_FOUND)
        if len(matches) > 1:
            sample = [f"{row.city.slug}:{row.slug}" for row in matches]
            return None, Response(
                {
                    'error': 'Multiple layers share this slug; disambiguate by city-scoped API or unique slug.',
                    'matches_sample': sample,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return matches[0], None

    @staticmethod
    def _bulk_listing_payloads(links):
        """Map (source, listing_pk) -> enrichment-lookup style dict for Synced* rows."""
        from collections import defaultdict

        lookup = EnrichmentLookupAPIView()
        model_map = lookup._get_model_map()
        by_source = defaultdict(set)
        for link in links:
            by_source[link.source].add(link.listing_pk)
        out = {}
        for src, pks in by_source.items():
            model = model_map.get(src)
            if not model or not pks:
                continue
            for obj in model.objects.filter(pk__in=pks):
                out[(src, obj.pk)] = lookup._record_to_dict(obj)
        return out

    def get(self, request, layer_slug):
        from ..models import LayerListingLink

        layer, err = self._resolve_layer(layer_slug)
        if err is not None:
            return err

        qs = (
            LayerListingLink.objects.filter(layer_id=layer.pk)
            .filter(status__iexact='active', exposure_type__iexact='public')
            .order_by('source', 'distance_km', 'id')
        )

        src = (request.query_params.get('source') or '').strip().lower()
        if src:
            if src not in self._VALID_SOURCES:
                return Response(
                    {'error': f'Invalid source. Use one of: {sorted(self._VALID_SOURCES)}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(source=src)

        dist_raw = (request.query_params.get('distance_km') or '').strip()
        if dist_raw:
            try:
                dist_max = float(dist_raw)
            except (TypeError, ValueError):
                return Response(
                    {'error': 'distance_km must be a number'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if dist_max < 0:
                return Response(
                    {'error': 'distance_km must be >= 0'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(distance_km__lte=dist_max)

        try:
            page_size = int(request.query_params.get('page_size', 10))
        except (TypeError, ValueError):
            page_size = 10
        page_size = min(self._MAX_PAGE_SIZE, max(1, page_size))

        try:
            page_num = int(request.query_params.get('page', 1))
        except (TypeError, ValueError):
            page_num = 1
        page_num = max(1, page_num)

        paginator = Paginator(qs, page_size)
        try:
            page_obj = paginator.page(page_num)
        except EmptyPage:
            return Response(
                {
                    'error': 'Invalid page',
                    'total_pages': paginator.num_pages,
                    'total': paginator.count,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        listing_map = self._bulk_listing_payloads(page_obj.object_list)

        rows = []
        for link in page_obj.object_list:
            ts = link.enriched_at
            rows.append(
                {
                    'source': link.source,
                    'listing_pk': link.listing_pk,
                    'backend_id': link.backend_id,
                    'status': link.status,
                    'exposure_type': link.exposure_type,
                    'layer_slug': link.layer_slug,
                    'distance_km': link.distance_km,
                    'nearest_point': link.nearest_point,
                    'enriched_at': ts.isoformat() if ts is not None else None,
                    'listing': listing_map.get((link.source, link.listing_pk)),
                }
            )

        base = request.build_absolute_uri(request.path)

        def _link_for_page(p):
            q = request.query_params.copy()
            q['page_size'] = str(page_size)
            q['page'] = str(p)
            return f"{base}?{q.urlencode()}"

        return Response(
            {
                'layer_id': layer.pk,
                'layer_slug': layer.slug,
                'city_slug': layer.city.slug,
                'count': len(rows),
                'total': paginator.count,
                'page': page_obj.number,
                'page_size': page_size,
                'total_pages': paginator.num_pages,
                'next': _link_for_page(page_obj.next_page_number()) if page_obj.has_next() else None,
                'previous': _link_for_page(page_obj.previous_page_number()) if page_obj.has_previous() else None,
                'results': rows,
            },
            status=status.HTTP_200_OK,
        )


class LayerListingLinksExportAPIView(APIView):
    """
    GET LayerListingLink rows for land and plot only (no SyncedLand/SyncedPlot joins).

    GET /api/layer-listing-links-export/
    Query:
      - layer_slug (optional): filter link.layer_slug
      - source (optional): land | plot
      - page (default 1)
      - page_size (default 100, max 1000)

    Each row is fields stored on LayerListingLink (layer_name via layer FK).
    """
    permission_classes = [AllowAny]

    _MAX_PAGE_SIZE = 1000
    _VALID_SOURCES = frozenset({'land', 'plot'})

    @staticmethod
    def _iso(dt):
        return dt.isoformat() if dt is not None else None

    def get(self, request):
        from ..models import LayerListingLink

        qs = (
            LayerListingLink.objects.filter(source__in=self._VALID_SOURCES)
            .select_related('layer')
            .order_by('layer_id', 'source', 'distance_km', 'id')
        )

        layer_slug = (request.query_params.get('layer_slug') or '').strip()
        if layer_slug:
            qs = qs.filter(layer_slug=layer_slug)

        src = (request.query_params.get('source') or '').strip().lower()
        if src:
            if src not in self._VALID_SOURCES:
                return Response(
                    {'error': f'Invalid source. Use one of: {sorted(self._VALID_SOURCES)}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(source=src)

        try:
            page_size = int(request.query_params.get('page_size', 100))
        except (TypeError, ValueError):
            page_size = 1000
        page_size = min(self._MAX_PAGE_SIZE, max(1, page_size))

        try:
            page_num = int(request.query_params.get('page', 1))
        except (TypeError, ValueError):
            page_num = 1
        page_num = max(1, page_num)

        paginator = Paginator(qs, page_size)
        try:
            page_obj = paginator.page(page_num)
        except EmptyPage:
            return Response(
                {
                    'error': 'Invalid page',
                    'total_pages': paginator.num_pages,
                    'total': paginator.count,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        rows = []
        for link in page_obj.object_list:
            layer = link.layer
            rows.append(
                {
                    'layer_name': layer.name if layer is not None else '',
                    'layer_slug': link.layer_slug,
                    'source': link.source,
                    'backend_id': link.backend_id,
                    'distance_km': link.distance_km,
                    'nearest_point': link.nearest_point,
                    'enriched_at': self._iso(link.enriched_at),
                }
            )

        base = request.build_absolute_uri(request.path)

        def _link_for_page(p):
            q = request.query_params.copy()
            q['page_size'] = str(page_size)
            q['page'] = str(p)
            return f"{base}?{q.urlencode()}"

        return Response(
            {
                'count': len(rows),
                'total': paginator.count,
                'page': page_obj.number,
                'page_size': page_size,
                'total_pages': paginator.num_pages,
                'next': _link_for_page(page_obj.next_page_number()) if page_obj.has_next() else None,
                'previous': _link_for_page(page_obj.previous_page_number()) if page_obj.has_previous() else None,
                'results': rows,
            },
            status=status.HTTP_200_OK,
        )


class DeveloperListingMediaDetailAPIView(APIView):
    """
    API endpoint to retrieve detailed information about a specific media file
    including TIF metadata if applicable
    
    GET /api/developer-listing-media/{media_id}/
    """
    permission_classes = [AllowAny]
    
    def get(self, request, media_id):
        """Get detailed information for a media file"""
        from ..models import DeveloperListingMedia
        from ..serializers import DeveloperListingMediaSerializer
        
        try:
            # Get media
            try:
                media = DeveloperListingMedia.objects.select_related(
                    'listing',
                    'tif_metadata'
                ).get(id=media_id)
            except DeveloperListingMedia.DoesNotExist:
                return Response(
                    {'error': f'Media file not found with id {media_id}'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Serialize and return
            serializer = DeveloperListingMediaSerializer(media)
            
            return Response(
                {
                    'success': True,
                    'media': serializer.data,
                    'listing': {
                        'id': media.listing.id,
                        'listing_type': media.listing.listing_type,
                        'backend_listing_id': media.listing.backend_listing_id,
                        'name': media.listing.name
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error retrieving media details: {e}", exc_info=True)
            return Response(
                {
                    'error': 'Internal server error',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WebhookEventListAPIView(APIView):
    """
    API endpoint to list webhook events with filtering
    
    GET /api/webhook-events/
    
    Query parameters:
    - listing_type: Filter by listing type
    - listing_id: Filter by listing ID
    - event_type: Filter by event type
    - processed: Filter by processed status (true/false)
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """List webhook events with filtering"""
        from ..models import WebhookEvent
        from ..serializers import WebhookEventSerializer
        
        try:
            # Get query parameters
            listing_type = request.query_params.get('listing_type')
            listing_id = request.query_params.get('listing_id')
            event_type = request.query_params.get('event_type')
            processed = request.query_params.get('processed')
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
            
            # Build queryset
            queryset = WebhookEvent.objects.all()
            
            # Apply filters
            if listing_type:
                queryset = queryset.filter(listing_type=listing_type)
            
            if listing_id:
                try:
                    listing_id_int = int(listing_id)
                    queryset = queryset.filter(listing_id=listing_id_int)
                except ValueError:
                    return Response(
                        {'error': 'Invalid listing_id. Must be an integer'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if event_type:
                queryset = queryset.filter(event_type=event_type)
            
            if processed is not None:
                processed_bool = processed.lower() == 'true'
                queryset = queryset.filter(processed=processed_bool)
            
            # Order by most recent
            queryset = queryset.order_by('-received_at')
            
            # Pagination
            total_count = queryset.count()
            start = (page - 1) * page_size
            end = start + page_size
            events = queryset[start:end]
            
            # Serialize
            serializer = WebhookEventSerializer(events, many=True)
            
            return Response(
                {
                    'success': True,
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total_count': total_count,
                        'total_pages': (total_count + page_size - 1) // page_size,
                        'has_next': end < total_count,
                        'has_previous': page > 1
                    },
                    'filters': {
                        'listing_type': listing_type,
                        'listing_id': listing_id,
                        'event_type': event_type,
                        'processed': processed
                    },
                    'events': serializer.data
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error listing webhook events: {e}", exc_info=True)
            return Response(
                {
                    'error': 'Internal server error',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    summary="Check if point is inside Hyderabad HMDA Extended Area",
    description="Check whether a given coordinate point is inside the Hyderabad HMDA Extended Area boundary. Returns true if inside, false if outside.",
    parameters=[
        OpenApiParameter(
            name='lat',
            type=float,
            location=OpenApiParameter.QUERY,
            required=True,
            description='Latitude of the point to check'
        ),
        OpenApiParameter(
            name='lng',
            type=float,
            location=OpenApiParameter.QUERY,
            required=True,
            description='Longitude of the point to check'
        )
    ],
    responses={
        200: extend_schema(
            description="Successfully checked point location",
            examples=[
                OpenApiExample(
                    'Point Inside Boundary',
                    value={
                        "success": True,
                        "is_inside": True,
                        "message": "Point is inside Hyderabad HMDA Extended Area",
                        "point": {
                            "latitude": 17.3850,
                            "longitude": 78.4867,
                            "coordinates": [78.4867, 17.3850]
                        },
                        "layer": {
                            "slug": "hyderabad_hmda_extended_area",
                            "name": "Hyderabad HMDA Extended Area",
                            "city": "hyderabad",
                            "state": "telangana"
                        }
                    }
                ),
                OpenApiExample(
                    'Point Outside Boundary',
                    value={
                        "success": True,
                        "is_inside": False,
                        "message": "Point is outside Hyderabad HMDA Extended Area",
                        "point": {
                            "latitude": 12.9716,
                            "longitude": 77.5946,
                            "coordinates": [77.5946, 12.9716]
                        },
                        "layer": {
                            "slug": "hyderabad_hmda_extended_area",
                            "name": "Hyderabad HMDA Extended Area",
                            "city": "hyderabad",
                            "state": "telangana"
                        }
                    }
                )
            ]
        ),
        400: extend_schema(
            description="Invalid request parameters",
            examples=[
                OpenApiExample(
                    'Missing Parameters',
                    value={
                        "success": False,
                        "error": "Missing required parameters: lat and lng"
                    }
                ),
                OpenApiExample(
                    'Invalid Coordinates',
                    value={
                        "success": False,
                        "error": "Invalid coordinates: lat must be between -90 and 90, lng between -180 and 180"
                    }
                )
            ]
        ),
        404: extend_schema(
            description="Layer not found",
            examples=[
                OpenApiExample(
                    'Layer Not Found',
                    value={
                        "success": False,
                        "error": "Hyderabad HMDA Extended Area layer not found"
                    }
                )
            ]
        )
    },
    tags=['boundary-check']
)
class HyderabadHMDABoundaryCheckAPIView(APIView):
    """
    API endpoint to check if a point is inside the Hyderabad HMDA Extended Area boundary.
    
    URL: /api/check-hmda-boundary/?lat={latitude}&lng={longitude}
    
    Returns:
    - is_inside: boolean - true if point is inside boundary, false if outside
    - message: descriptive message
    - point: coordinates that were checked
    - layer: information about the HMDA boundary layer
    
    Example:
    - /api/check-hmda-boundary/?lat=17.3850&lng=78.4867
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Check if point is inside Hyderabad HMDA Extended Area"""
        try:
            # Get query parameters
            lat = request.GET.get('lat')
            lng = request.GET.get('lng')
            
            # Validate required parameters
            if not lat or not lng:
                return Response({
                    'success': False,
                    'error': 'Missing required parameters: lat and lng'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate and convert coordinates
            try:
                latitude = float(lat)
                longitude = float(lng)
            except ValueError:
                return Response({
                    'success': False,
                    'error': 'Invalid coordinate format: lat and lng must be valid numbers'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate coordinate ranges
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                return Response({
                    'success': False,
                    'error': 'Invalid coordinates: lat must be between -90 and 90, lng between -180 and 180'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Cache by rounded coords (~11m) to avoid repeated spatial queries; TTL 5 min
            cache_key = f"hmda_boundary:v1:{round(latitude, 4)}:{round(longitude, 4)}"
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached, status=status.HTTP_200_OK)
            
            # Get the Hyderabad HMDA Extended Area layer
            try:
                layer = DataLayer.objects.select_related('city', 'city__state_ref').get(
                    slug='hyderabad_hmda_extended_area',
                    is_processed=True
                )
            except DataLayer.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Hyderabad HMDA Extended Area layer not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Create point geometry
            search_point = Point(longitude, latitude, srid=4326)
            
            # Check if point is inside any feature of the HMDA boundary layer
            # Use contains for exact boundary check (no buffer)
            is_inside = GeoFeature.objects.filter(
                layer=layer,
                is_valid=True,
                geometry__contains=search_point
            ).exists()
            
            # Prepare response
            response_data = {
                'success': True,
                'is_inside': is_inside,
                'message': f"Point is {'inside' if is_inside else 'outside'} Hyderabad HMDA Extended Area",
                'point': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'coordinates': [longitude, latitude]
                },
                'layer': {
                    'slug': layer.slug,
                    'name': layer.name,
                    'city': layer.city.slug,
                    'city_name': layer.city.name,
                    'state': layer.city.state_ref.slug if layer.city.state_ref else None,
                    'state_name': layer.city.state_ref.name if layer.city.state_ref else None
                }
            }
            cache.set(cache_key, response_data, 300)  # 5 min
            
            logger.info(
                f"HMDA Boundary Check: Point ({latitude}, {longitude}) is "
                f"{'inside' if is_inside else 'outside'} boundary"
            )
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in HyderabadHMDABoundaryCheckAPIView: {e}", exc_info=True)
            return Response({
                'success': False,
                'error': 'Internal server error',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeveloperListingMapDataAPIView(APIView):
    """
    Lightweight API endpoint to get only map-related data for a developer listing.
    Returns bounds, zoom level, and S3 tile paths - everything needed to display on map.
    
    GET /api/developer-listings/{listing_type}/{listing_id}/map-data/
    
    Returns:
    - Bounds (west, south, east, north)
    - Zoom levels (min, max, recommended)
    - Center coordinates
    - S3 tile paths for all TIF files
    - Minimal listing info (name, location)
    - tile_domains: s3_tile_domain (developer rasters use /api/tiles/developer_data/... proxy templates)
    
    Much lighter and faster than the full detail API.
    """
    permission_classes = [AllowAny]
    
    def get(self, request, listing_type, listing_id):
        """Get map data for a developer listing"""
        from ..models import DeveloperListing, TIFMetadata, DeveloperListingMedia
        
        try:
            # Validate listing_type
            if listing_type not in ['developerland', 'developerplot']:
                return Response(
                    {'error': f'Invalid listing_type. Must be "developerland" or "developerplot"'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get listing
            try:
                listing = DeveloperListing.objects.get(
                    listing_type=listing_type,
                    backend_listing_id=listing_id
                )
            except DeveloperListing.DoesNotExist:
                return Response(
                    {
                        'error': f'Listing not found',
                        'listing_type': listing_type,
                        'listing_id': listing_id
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Prefer media rows that finished tile gen; TIFMetadata may be missing if an older
            # callback omitted bounds (fixed in _save_tif_data_from_callback).
            from django.core.exceptions import ObjectDoesNotExist

            tif_media = DeveloperListingMedia.objects.filter(
                listing=listing,
                is_tif=True,
                tiles_generated=True,
            ).select_related('tif_metadata')

            if not tif_media.exists():
                return Response(
                    {
                        'success': False,
                        'error': 'No TIF files have been processed yet',
                        'listing': {
                            'id': listing.id,
                            'listing_type': listing.listing_type,
                            'backend_listing_id': listing.backend_listing_id,
                            'name': listing.name
                        }
                    },
                    status=status.HTTP_200_OK
                )

            media_meta_pairs = []
            for m in tif_media:
                try:
                    tm = m.tif_metadata
                except ObjectDoesNotExist:
                    tm = None
                media_meta_pairs.append((m, tm))

            west_list = [tm.bounds_west for _, tm in media_meta_pairs if tm and tm.bounds_west is not None]
            south_list = [tm.bounds_south for _, tm in media_meta_pairs if tm and tm.bounds_south is not None]
            east_list = [tm.bounds_east for _, tm in media_meta_pairs if tm and tm.bounds_east is not None]
            north_list = [tm.bounds_north for _, tm in media_meta_pairs if tm and tm.bounds_north is not None]

            if west_list and south_list and east_list and north_list:
                west = min(west_list)
                south = min(south_list)
                east = max(east_list)
                north = max(north_list)
            else:
                pt = listing.get_listing_point() if hasattr(listing, 'get_listing_point') else None
                if pt is not None and not getattr(pt, 'empty', True):
                    lat, lng = pt.y, pt.x
                    pad = 0.02
                    west, south, east, north = lng - pad, lat - pad, lng + pad, lat + pad
                else:
                    west = south = east = north = None

            zoom_mins = [tm.min_zoom for _, tm in media_meta_pairs if tm and tm.min_zoom is not None]
            zoom_maxs = [tm.max_zoom for _, tm in media_meta_pairs if tm and tm.max_zoom is not None]
            min_zoom = min(zoom_mins) if zoom_mins else 8
            max_zoom = max(zoom_maxs) if zoom_maxs else 18

            bounds_extent = None
            if west is not None and south is not None and east is not None and north is not None:
                width = east - west
                height = north - south
                area = width * height
                recommended_zoom = recommended_zoom_from_area(area)
            else:
                recommended_zoom = DEVELOPER_LISTING_DEFAULT_ZOOM
                pt = listing.get_listing_point() if hasattr(listing, 'get_listing_point') else None
                if pt is not None and not getattr(pt, 'empty', True):
                    center_lat, center_lng = pt.y, pt.x
                else:
                    center_lat, center_lng = None, None

            recommended_zoom = max(min_zoom, min(recommended_zoom, max_zoom))

            if west is not None and south is not None and east is not None and north is not None:
                fw, fs, fe, fn = west, south, east, north
                west, south, east, north = tighten_bounds_for_map_fit(
                    west, south, east, north, recommended_zoom
                )
                if any(
                    abs(a - b) > 1e-9
                    for a, b in ((fw, west), (fs, south), (fe, east), (fn, north))
                ):
                    bounds_extent = {
                        'west': fw,
                        'south': fs,
                        'east': fe,
                        'north': fn,
                        'bbox': [fw, fs, fe, fn],
                        'leaflet_bounds': [[fs, fw], [fn, fe]],
                    }
                center_lat = (south + north) / 2
                center_lng = (west + east) / 2

            tif_files = []
            for media, tif_meta in media_meta_pairs:
                tile_url_template = tile_proxy_png_template_from_s3_tile_path(media.s3_tile_path)
                if not tile_url_template:
                    _tb = public_https_base_for_s3_tile_prefix(media.s3_tile_path)
                    tile_url_template = f"{_tb}/{media.s3_tile_path}/{{z}}/{{x}}/{{y}}.png"
                tif_files.append({
                    'file_name': media.file_name,
                    's3_tile_path': media.s3_tile_path,
                    'tile_url_template': tile_url_template,
                    'tiles_generated': media.total_tiles_generated,
                    'bounds': {
                        'west': tif_meta.bounds_west if tif_meta else None,
                        'south': tif_meta.bounds_south if tif_meta else None,
                        'east': tif_meta.bounds_east if tif_meta else None,
                        'north': tif_meta.bounds_north if tif_meta else None,
                    }
                })
            
            # Return lightweight response
            return Response(
                {
                    'success': True,
                    'listing': {
                        'id': listing.id,
                        'listing_type': listing.listing_type,
                        'backend_listing_id': listing.backend_listing_id,
                        'name': listing.name,
                        'location': listing.location,
                        'city': listing.city,
                        'state': listing.state
                    },
                    'bounds': {
                        'west': west,
                        'south': south,
                        'east': east,
                        'north': north,
                        'bbox': [west, south, east, north] if west is not None else None,
                        'leaflet_bounds': [[south, west], [north, east]] if west is not None else None,
                    },
                    **(
                        {'bounds_extent': bounds_extent}
                        if bounds_extent is not None
                        else {}
                    ),
                    'center': {
                        'lat': center_lat,
                        'lng': center_lng,
                        'coordinates': (
                            [center_lng, center_lat]
                            if center_lat is not None and center_lng is not None
                            else None
                        ),
                    },
                    'zoom': {
                        'min': min_zoom,
                        'max': max_zoom,
                        'default': recommended_zoom,
                        'recommended': recommended_zoom
                    },
                    'tif_files': tif_files,
                    'summary': {
                        'total_tif_files': len(tif_files),
                        'total_tiles': sum(tf['tiles_generated'] for tf in tif_files)
                    },
                    'tile_domains': {
                        'tile_proxy_api_base': client_tile_proxy_api_root(),
                        'tile_proxy_public_base_url': (
                            (getattr(settings, 'TILE_PROXY_PUBLIC_BASE_URL', None) or '').strip() or None
                        ),
                    },
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error retrieving map data: {e}", exc_info=True)
            return Response(
                {
                    'error': 'Internal server error',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

