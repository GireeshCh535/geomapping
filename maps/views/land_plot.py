from ._imports import *

# ================================
# LAND/PLOT MVT TILES (S3 by default; optional CloudFront; local dev fallback)
# ================================


def _fetch_tile_url(url, timeout=5):
    """Fetch tile bytes from URL; return bytes or None. Shared by tile proxy views."""
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            return response.content
        # print(f"[tile_proxy] _fetch_tile_url HTTP error: {response.status_code} {url[:100]}...")
    except Exception as e:
        print(f"[tile_proxy] _fetch_tile_url error: {e}")
    return None


class LandPlotTileView(APIView):
    """
    Serve land/plot MVT tiles via proxy (S3 by default; server-side cache).
    Optional local file fallback. No redirects; client never sees backend URL.
    Requires API key (X-API-Key) when any active ApiKey exists; same as other API endpoints except webhooks.
    """
    # Uses default permission_classes from settings: AllowIfWebhookOrHasAPIKey (API key required when keys exist)

    def get(self, request, z, x, y):
        z, x, y = int(z), int(x), int(y)
        tile_path_service = TilePathService()
        if not tile_path_service.validate_tile_coordinates(z, x, y):
            return Response({'error': 'Invalid tile coordinates'}, status=400)

        # Local file fallback first (no network)
        from pathlib import Path
        local_path = Path(settings.BASE_DIR) / 'land_plot_tiles' / str(z) / str(x) / f'{y}.mvt'
        if local_path.is_file():
            return self._mvt_response(local_path.read_bytes())

        s3_key = tile_path_service.land_plot_s3_key(z, x, y)
        cache_key = f"tile_proxy:{s3_key}"
        ttl = getattr(settings, 'TILE_PROXY_CACHE_TTL', 3600)
        if ttl > 0:
            cached = cache.get(cache_key)
            if cached is not None:
                return self._mvt_response(cached)
        backend_url = tile_path_service.get_backend_url_for_land_plot(z, x, y)
        backend_label = tile_path_service._backend_label(s3_key)
        # print(f"[tile_proxy] land-plot serving from {backend_label}: {backend_url}")
        tile_data = _fetch_tile_url(backend_url)
        if tile_data:
            if ttl > 0:
                try:
                    cache.set(cache_key, tile_data, ttl)
                except Exception:
                    pass
            return self._mvt_response(tile_data)
        # print(f"[tile_proxy] land-plot fetch FAIL ({backend_label}): {s3_key}")
        return Response({'error': 'Tile not found'}, status=404)

    def _mvt_response(self, data):
        headers = TilePathService().get_tile_cache_headers('mvt')
        response = HttpResponse(data, content_type=headers['ContentType'])
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        response['Access-Control-Allow-Origin'] = '*'
        return response


# Alias for backward compatibility (URL still uses this name)
LandPlotLocalTileView = LandPlotTileView


def _land_plot_price_percentiles():
    """Compute 33rd and 66th percentile of total_price per type for 3 tiers (active+public only)."""
    land_prices = list(
        SyncedLand.objects.filter(
            location_point__isnull=False, status='active', exposure_type='public'
        )
        .exclude(total_price__isnull=True)
        .values_list("total_price", flat=True)
    )
    land_prices = sorted([float(p) for p in land_prices if p is not None and p > 0])
    n_land = len(land_prices)
    land_p33 = land_prices[int(n_land * 0.33)] if n_land else 0
    land_p66 = land_prices[int(n_land * 0.66)] if n_land else 0

    plot_prices = list(
        SyncedPlot.objects.filter(
            location_point__isnull=False, status='active', exposure_type='public'
        )
        .exclude(total_price__isnull=True)
        .values_list("total_price", flat=True)
    )
    plot_prices = sorted([float(p) for p in plot_prices if p is not None and p > 0])
    n_plot = len(plot_prices)
    plot_p33 = plot_prices[int(n_plot * 0.33)] if n_plot else 0
    plot_p66 = plot_prices[int(n_plot * 0.66)] if n_plot else 0
    return {"land": (land_p33, land_p66), "plot": (plot_p33, plot_p66)}


def _tier_for_price(price, p33, p66):
    """Return 1=low, 2=mid, 3=high."""
    if price is None or price <= 0:
        return 1
    if price <= p33:
        return 1
    if price <= p66:
        return 2
    return 3


def _marker_id_for_listing(obj, listing_type):
    """
    Get marker_id for 1acre-icons path: use stored column if set, else payload.
    Icons: land|plot / base|owner|1acre / {marker_id}.svg
    """
    mid = (getattr(obj, 'marker_id', None) or '').strip()
    if mid:
        return mid
    payload = getattr(obj, 'payload', None) or {}
    if isinstance(payload, dict):
        mid = (payload.get('marker_id') or '').strip()
        if mid:
            return mid
    return 'land-0' if listing_type == 'land' else 'plot-0'


class LandPlotGeoJSONView(APIView):
    """Return all SyncedLand + SyncedPlot points as one GeoJSON FeatureCollection. Cached 5 min to avoid full table scans on every request."""
    permission_classes = [AllowAny]
    _GEOJSON_CACHE_KEY = "land_plot_geojson:v1"
    _GEOJSON_CACHE_TTL = 300  # 5 minutes

    def get(self, request):
        cached = cache.get(self._GEOJSON_CACHE_KEY)
        if cached is not None:
            return HttpResponse(cached, content_type="application/geo+json")

        percentiles = _land_plot_price_percentiles()
        land_p33, land_p66 = percentiles["land"]
        plot_p33, plot_p66 = percentiles["plot"]

        features = []

        for obj in SyncedLand.objects.filter(
            location_point__isnull=False, status='active', exposure_type='public'
        ).only(
            "backend_id", "total_price", "total_land_size", "slug", "status", "exposure_type", "location_point", "lat", "long", "marker_id", "payload"
        ):
            pt = obj.location_point
            if not pt:
                continue
            # Use scalar columns: long=longitude, lat=latitude (WGS84)
            if obj.lat is not None and obj.long is not None:
                try:
                    lon, lat = float(obj.long), float(obj.lat)
                except (TypeError, ValueError):
                    lon, lat = pt.x, pt.y
            else:
                lon, lat = pt.x, pt.y
            try:
                price = float(obj.total_price) if obj.total_price is not None else None
            except (TypeError, ValueError):
                price = None
            tier = _tier_for_price(price, land_p33, land_p66)
            try:
                size = float(obj.total_land_size) if obj.total_land_size is not None else None
            except (TypeError, ValueError):
                size = None
            marker_id = _marker_id_for_listing(obj, "land")
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "id": obj.backend_id,
                    "type": "land",
                    "total_price": price or 0,
                    "size": size,
                    "size_label": "acres",
                    "slug": (obj.slug or "")[:200],
                    "status": obj.status or "",
                    "tier": tier,
                    "sort_key": price or 0,
                    "marker_id": marker_id,
                },
            })

        for obj in SyncedPlot.objects.filter(
            location_point__isnull=False, status='active', exposure_type='public'
        ).only(
            "backend_id", "total_price", "total_plot_size", "slug", "status", "exposure_type", "location_point", "lat", "long", "marker_id", "payload"
        ):
            pt = obj.location_point
            if not pt:
                continue
            # Use scalar columns: long=longitude, lat=latitude (WGS84)
            if obj.lat is not None and obj.long is not None:
                try:
                    lon, lat = float(obj.long), float(obj.lat)
                except (TypeError, ValueError):
                    lon, lat = pt.x, pt.y
            else:
                lon, lat = pt.x, pt.y
            try:
                price = float(obj.total_price) if obj.total_price is not None else None
            except (TypeError, ValueError):
                price = None
            tier = _tier_for_price(price, plot_p33, plot_p66)
            try:
                size = float(obj.total_plot_size) if obj.total_plot_size is not None else None
            except (TypeError, ValueError):
                size = None
            marker_id = _marker_id_for_listing(obj, "plot")
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "id": obj.backend_id,
                    "type": "plot",
                    "total_price": price or 0,
                    "size": size,
                    "size_label": "sqyd",
                    "slug": (obj.slug or "")[:200],
                    "status": obj.status or "",
                    "tier": tier,
                    "sort_key": price or 0,
                    "marker_id": marker_id,
                },
            })

        geojson = {"type": "FeatureCollection", "features": features}
        json_str = json.dumps(geojson)
        cache.set(self._GEOJSON_CACHE_KEY, json_str, self._GEOJSON_CACHE_TTL)
        return HttpResponse(json_str, content_type="application/geo+json")


class LandPlotMapTestView(APIView):
    """Serve HTML test page for land/plot MVT map (3 colors by price tier, hover tooltip)."""
    permission_classes = [AllowAny]

    def get(self, request):
        from django.shortcuts import render
        return render(request, 'land_plot_map_test.html')