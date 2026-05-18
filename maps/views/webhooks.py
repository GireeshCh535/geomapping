from ._imports import *

def _webhook_payload_snapshot(data):
    """
    Return a deep copy of webhook payload so we store everything exactly as received.
    Handles QueryDict and nested structures; result is JSON-serializable.
    """
    if data is None:
        return {}
    if hasattr(data, 'dict'):
        data = data.dict()
    elif hasattr(data, 'items') and not isinstance(data, dict):
        data = dict(data)
    try:
        return copy.deepcopy(data)
    except Exception:
        return json.loads(json.dumps(data, default=str))


def _print_webhook_response(webhook_name, data):
    """
    Log the entire webhook request body as clear, readable JSON.
    Use for all webhook endpoints so incoming payload is visible for debugging.
    """
    try:
        if data is None:
            payload = {}
        elif hasattr(data, 'dict'):
            payload = data.dict()
        elif hasattr(data, 'items') and not isinstance(data, dict):
            payload = dict(data)
        else:
            payload = data
        json_str = json.dumps(payload, indent=2, default=str, ensure_ascii=False)
    except Exception as e:
        json_str = f"(could not serialize: {e})"
    sep = "=" * 80
    banner = f"\n{sep}\n  WEBHOOK REQUEST BODY: {webhook_name}\n{sep}"
    # logger.info("%s\n%s", banner, json_str)


def _parse_datetime_webhook(dt_string):
    """Parse datetime string from webhook payload (used in background worker)."""
    if not dt_string:
        return None
    from django.utils.dateparse import parse_datetime
    return parse_datetime(dt_string)


def _execute_listing_deletion(webhook_event, listing_type, listing_id, data):
    """
    Perform listing deletion: delete tiles, media, listing and Synced* records; refresh layer cache.
    Updates webhook_event.processed, processing_result, or processing_error. No return value.
    """
    from django.utils import timezone
    from ..models import DeveloperListing, DeveloperListingMedia
    from ..developer_listing_tile_service import DeveloperListingTileService

    logger.info(f"[WEBHOOK_DELETE] Listing deletion {listing_type} id={listing_id}")

    try:
        try:
            listing = DeveloperListing.objects.get(
                listing_type=listing_type,
                backend_listing_id=listing_id
            )
        except DeveloperListing.DoesNotExist:
            logger.warning(f"[WEBHOOK_DELETE] Listing not found: {listing_type} {listing_id}")
            webhook_event.processed = True
            webhook_event.processed_at = timezone.now()
            webhook_event.processing_result = {'note': 'Listing not found in database'}
            webhook_event.save()
            return

        all_media = DeveloperListingMedia.objects.filter(listing=listing)
        total_tiles_deleted = 0
        tile_service = DeveloperListingTileService()
        for media in all_media:
            if media.is_tif and media.s3_tile_path:
                deleted_count = tile_service._delete_s3_tiles(media.s3_tile_path)
                total_tiles_deleted += deleted_count
        media_count = all_media.count()
        all_media.delete()

        lat, lng = None, None
        point = listing.get_listing_point() if hasattr(listing, 'get_listing_point') else None
        if point is None and getattr(listing, 'location_point', None) and not listing.location_point.empty:
            point = listing.location_point
        if point is not None and not point.empty:
            lat, lng = point.y, point.x

        listing.delete()
        from ..models import SyncedDeveloperLand, SyncedDeveloperPlot
        if listing_type == 'developerland':
            SyncedDeveloperLand.objects.filter(backend_id=listing_id).delete()
        elif listing_type == 'developerplot':
            SyncedDeveloperPlot.objects.filter(backend_id=listing_id).delete()

        if lat is not None and lng is not None:
            try:
                from maps.listing_layer_enrichment_service import (
                    get_layer_ids_containing_point,
                    refresh_layer_point_count_cache,
                )
                affected = get_layer_ids_containing_point(lat, lng)
                if affected:
                    refresh_layer_point_count_cache(layer_ids=affected)
            except Exception as cache_err:
                logger.warning(f"[WEBHOOK_DELETE] Layer point count cache refresh failed: {cache_err}", exc_info=True)

        webhook_event.processed = True
        webhook_event.processed_at = timezone.now()
        webhook_event.tiles_generated = 0
        webhook_event.processing_result = {
            'tiles_deleted': total_tiles_deleted,
            'media_records_deleted': media_count,
            'listing_deleted': True
        }
        webhook_event.save()
        logger.info(f"[WEBHOOK_DELETE] Completed: tiles_deleted={total_tiles_deleted} media_deleted={media_count}")
    except Exception as e:
        logger.error(f"[WEBHOOK_DELETE] Error processing listing deletion: {e}", exc_info=True)
        webhook_event.processing_error = str(e)
        webhook_event.save()


def _execute_media_deletion(webhook_event, listing_type, listing_id, data):
    """
    Perform media deletion: delete tiles for deleted media, remove media records, sync remaining.
    Updates webhook_event.processed, processing_result, or processing_error. No return value.
    """
    from django.utils import timezone
    from ..models import DeveloperListing, DeveloperListingMedia
    from ..developer_listing_tile_service import DeveloperListingTileService

    media_items = data.get('media_items') or []
    logger.info(f"[WEBHOOK_DELETE] Media deletion {listing_type} id={listing_id}")

    try:
        try:
            listing = DeveloperListing.objects.get(
                listing_type=listing_type,
                backend_listing_id=listing_id
            )
        except DeveloperListing.DoesNotExist:
            logger.warning(f"[WEBHOOK_DELETE] Listing not found: {listing_type} {listing_id}")
            webhook_event.processed = True
            webhook_event.processed_at = timezone.now()
            webhook_event.processing_result = {'note': 'Listing not found in database'}
            webhook_event.save()
            return

        deleted_media_items = [m for m in media_items if m.get('deleted', False)]
        total_tiles_deleted = 0
        deleted_media_count = 0
        tile_service = DeveloperListingTileService()

        for deleted_media in deleted_media_items:
            media_id = deleted_media.get('id')
            file_name = deleted_media.get('file_name', 'unknown')
            s3_tile_path = deleted_media.get('s3_tile_path', '')
            is_tif = deleted_media.get('is_tif', False)

            if is_tif and s3_tile_path:
                deleted_count = tile_service._delete_s3_tiles(s3_tile_path)
                total_tiles_deleted += deleted_count
            elif is_tif:
                logger.warning(f"[WEBHOOK_DELETE] TIF file {file_name} has no s3_tile_path, skipping tile deletion")

            try:
                media_obj = DeveloperListingMedia.objects.get(
                    listing=listing,
                    backend_media_id=media_id
                )
                media_obj.delete()
                deleted_media_count += 1
            except DeveloperListingMedia.DoesNotExist:
                pass

        remaining_media_items = [m for m in media_items if not m.get('deleted', False)]
        for media_item in remaining_media_items:
            media_id = media_item.get('id')
            if not media_id:
                continue
            DeveloperListingMedia.objects.update_or_create(
                listing=listing,
                backend_media_id=media_id,
                defaults={
                    'media_type': media_item.get('media_type', 'file'),
                    'category': media_item.get('category', ''),
                    'file_name': media_item.get('file_name', ''),
                    'file_url': media_item.get('url', ''),
                    's3_path': media_item.get('s3_path', ''),
                    'is_tif': media_item.get('is_tif', False),
                    's3_tile_path': media_item.get('s3_tile_path', ''),
                    'media_data': media_item,
                }
            )

        webhook_event.processed = True
        webhook_event.processed_at = timezone.now()
        webhook_event.tiles_generated = 0
        webhook_event.processing_result = {
            'tiles_deleted': total_tiles_deleted,
            'media_records_deleted': deleted_media_count,
            'remaining_media_count': len(remaining_media_items)
        }
        webhook_event.save()
        logger.info(f"[WEBHOOK_DELETE] Media deletion completed: tiles_deleted={total_tiles_deleted} media_deleted={deleted_media_count}")
    except Exception as e:
        logger.error(f"[WEBHOOK_DELETE] Error processing media deletion: {e}", exc_info=True)
        webhook_event.processing_error = str(e)
        webhook_event.save()


def _process_developer_listing_webhook(webhook_event_id):
    """
    Background processing for developer listing webhook: sync listing + Synced*, enrich once,
    refresh layer cache only when location changed, media loop. Tile job is enqueued by signal
    (maps.signals) when DeveloperListingMedia is saved; we set thread-local so callback gets webhook_event_id.
    """
    from django.db import close_old_connections
    from django.utils import timezone
    from ..tile_job_queue import (
        set_developer_webhook_event_id,
        get_developer_listing_job_enqueued,
        clear_developer_listing_job_enqueued,
    )

    close_old_connections()
    try:
        webhook_event = WebhookEvent.objects.get(pk=webhook_event_id)
    except WebhookEvent.DoesNotExist:
        logger.warning(f"[WEBHOOK_BACKGROUND] WebhookEvent id={webhook_event_id} not found")
        return

    data = webhook_event.payload if isinstance(getattr(webhook_event, 'payload', None), dict) else {}
    if not data:
        data = {}
    action = data.get('action', '')
    listing_type = data.get('listing_type', '')
    listing_id = data.get('listing_id')
    listing_data = data.get('listing_data') or {}
    media_items = data.get('media_items') or []
    tif_files = data.get('tif_files', [])
    event_type = data.get('event_type', '')

    if action == 'listing_deleted':
        _execute_listing_deletion(webhook_event, listing_type, listing_id, data)
        return
    if action == 'media_deleted':
        _execute_media_deletion(webhook_event, listing_type, listing_id, data)
        return

    # Create/update path
    city_name = ''
    if listing_data.get('city'):
        city_name = listing_data.get('city', '')
    elif listing_data.get('division'):
        division = listing_data.get('division', [])
        if isinstance(division, list) and len(division) > 0:
            city_name = division[0].get('name', '') if isinstance(division[0], dict) else ''
        elif isinstance(division, dict):
            city_name = division.get('name', '')

    listing_data_stored = _webhook_payload_snapshot(listing_data)
    listing, created = DeveloperListing.objects.update_or_create(
        listing_type=listing_type,
        backend_listing_id=listing_id,
        defaults={
            'listing_data': listing_data_stored,
            'name': listing_data.get('name', '') or listing_data.get('title', ''),
            'description': listing_data.get('description', ''),
            'location': listing_data.get('location', ''),
            'city': city_name,
            'state': listing_data.get('state', ''),
            'last_webhook_event': event_type,
            'backend_created_at': _parse_datetime_webhook(listing_data.get('created_at')),
            'backend_updated_at': _parse_datetime_webhook(listing_data.get('updated_at')),
        }
    )
    logger.info(f"[WEBHOOK_BACKGROUND] DeveloperListing {'created' if created else 'updated'}: ID={listing.id}")

    # Set thread-local so signal (DeveloperListingMedia post_save) includes webhook_event_id in SQS payload
    set_developer_webhook_event_id(webhook_event.id)
    get_developer_listing_job_enqueued()  # init dedupe set
    try:
        # Detect location change before updating location_point (Fix 3: skip cache refresh when unchanged)
        old_point = listing.location_point
        new_point = listing.get_listing_point()
        location_changed = (
            (old_point is None and new_point is not None)
            or (new_point is not None and (old_point is None or old_point.wkt != new_point.wkt))
        )
        if new_point is not None and (listing.location_point is None or listing.location_point.wkt != new_point.wkt):
            listing.location_point = new_point
            listing.save(update_fields=['location_point'])

        from ..models import SyncedDeveloperLand, SyncedDeveloperPlot
        from ..sync_utils import defaults_for_developer_land, defaults_for_developer_plot
        listing_data_for_sync = dict(listing_data_stored) if listing_data_stored else {}
        listing_data_for_sync['id'] = listing_id
        synced_record = None
        if listing_type == 'developerland':
            defaults = defaults_for_developer_land(listing_data_for_sync)
            synced_record, _ = SyncedDeveloperLand.objects.update_or_create(backend_id=listing_id, defaults=defaults)
        elif listing_type == 'developerplot':
            defaults = defaults_for_developer_plot(listing_data_for_sync)
            synced_record, _ = SyncedDeveloperPlot.objects.update_or_create(backend_id=listing_id, defaults=defaults)

        # Enrich once, write to both tables (Fix 2)
        try:
            from maps.listing_layer_enrichment_service import (
                _sync_listing_location_point,
                get_listing_point,
                _get_state_name_from_payload,
                compute_enriched_layers_for_point,
                refresh_layer_listing_links_from_stored_enrichment,
            )
            _sync_listing_location_point(listing)
            point = get_listing_point(listing)
            if point is None:
                listing.enriched_layers = []
                listing.enriched_at = None
                listing.save(update_fields=['enriched_layers', 'enriched_at'])
                if synced_record is not None:
                    synced_record.enriched_layers = []
                    synced_record.enriched_at = None
                    synced_record.save(update_fields=['enriched_layers', 'enriched_at'])
                    refresh_layer_listing_links_from_stored_enrichment(synced_record)
            else:
                state_name = _get_state_name_from_payload(listing.listing_data or {})
                enriched = compute_enriched_layers_for_point(point, state_name=state_name)
                now = timezone.now()
                listing.enriched_layers = enriched
                listing.enriched_at = now
                listing.save(update_fields=['enriched_layers', 'enriched_at'])
                if synced_record is not None:
                    synced_record.enriched_layers = enriched
                    synced_record.enriched_at = now
                    synced_record.save(update_fields=['enriched_layers', 'enriched_at'])
                    refresh_layer_listing_links_from_stored_enrichment(synced_record)
                logger.info(f"[WEBHOOK_BACKGROUND] Enriched {listing_type} {listing_id} ({len(enriched)} layers)")
        except Exception as enr_err:
            logger.warning(f"[WEBHOOK_BACKGROUND] Enrichment failed for {listing_type} {listing_id}: {enr_err}", exc_info=True)

        # Refresh layer point count cache only when location changed (Fix 3)
        if location_changed:
            try:
                from maps.listing_layer_enrichment_service import (
                    get_layer_ids_containing_point,
                    refresh_layer_point_count_cache,
                )
                point = listing.get_listing_point() if hasattr(listing, 'get_listing_point') else None
                if point is None and getattr(listing, 'location_point', None) and not listing.location_point.empty:
                    point = listing.location_point
                if point is not None and not point.empty:
                    lat, lng = point.y, point.x
                    affected = get_layer_ids_containing_point(lat, lng)
                    if affected:
                        refresh_layer_point_count_cache(layer_ids=affected)
            except Exception as cache_err:
                logger.warning(f"[WEBHOOK_BACKGROUND] Layer point count cache refresh failed: {cache_err}", exc_info=True)

        # Media loop
        webhook_media_ids = {m.get('id') for m in media_items if m.get('id')}
        tile_service_for_cleanup = None
        for idx, media_item in enumerate(media_items, 1):
            media_id = media_item.get('id')
            if not media_id:
                continue
            is_tif = media_item.get('is_tif', False)
            file_name = media_item.get('file_name', 'unknown')
            new_s3_tile_path = media_item.get('s3_tile_path', '')
            old_media = None
            old_s3_tile_path = None
            try:
                old_media = DeveloperListingMedia.objects.get(listing=listing, backend_media_id=media_id)
                old_s3_tile_path = old_media.s3_tile_path
                if is_tif and old_s3_tile_path:
                    if not tile_service_for_cleanup:
                        from ..developer_listing_tile_service import DeveloperListingTileService
                        tile_service_for_cleanup = DeveloperListingTileService()
                    tile_service_for_cleanup._delete_s3_tiles(old_s3_tile_path)
            except DeveloperListingMedia.DoesNotExist:
                pass
            media_data_stored = _webhook_payload_snapshot(media_item)
            DeveloperListingMedia.objects.update_or_create(
                listing=listing,
                backend_media_id=media_id,
                defaults={
                    'media_type': media_item.get('media_type', 'file'),
                    'category': media_item.get('category', ''),
                    'file_name': file_name,
                    'file_url': media_item.get('url', ''),
                    's3_path': media_item.get('s3_path', ''),
                    'is_tif': is_tif,
                    's3_tile_path': new_s3_tile_path,
                    'media_data': media_data_stored,
                }
            )

        if action in ['updated', 'media_uploaded', 'media_updated'] and webhook_media_ids:
            existing_media = DeveloperListingMedia.objects.filter(listing=listing)
            for existing_media_obj in existing_media:
                if existing_media_obj.backend_media_id not in webhook_media_ids:
                    if existing_media_obj.is_tif and existing_media_obj.s3_tile_path:
                        from ..developer_listing_tile_service import DeveloperListingTileService
                        DeveloperListingTileService()._delete_s3_tiles(existing_media_obj.s3_tile_path)
                    existing_media_obj.delete()

        # Tile job is enqueued by signal when DeveloperListingMedia (TIF) is saved
        if not tif_files:
            webhook_event.processed = True
            webhook_event.processed_at = timezone.now()
            webhook_event.save()
    finally:
        set_developer_webhook_event_id(None)
        clear_developer_listing_job_enqueued()


class TileGenerationCallbackView(APIView):
    """
    Callback endpoint for Lambda (or external tile worker) to report tile generation
    results and logs. Secured by X-Tile-Callback-Secret header.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    http_method_names = ['post']

    def post(self, request):
        from ..models import LandPlotWebhookEvent, WebhookEvent
        secret = request.headers.get('X-Tile-Callback-Secret', '')
        expected = getattr(settings, 'TILE_CALLBACK_SECRET', '') or ''
        if expected and secret != expected:
            logger.warning("[TILE_CALLBACK] Rejected: missing or invalid X-Tile-Callback-Secret")
            return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            data = request.data if getattr(request.data, 'get', None) else {}
            if not data and request.body:
                data = json.loads(request.body.decode('utf-8', errors='replace'))
        except Exception as e:
            logger.warning(f"[TILE_CALLBACK] Invalid JSON body: {e}")
            return Response({'error': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
        webhook_event_id = data.get('webhook_event_id')
        # webhook_event_id may be None for admin/API-triggered tile jobs (no event to update)
        processing_result = data.get('processing_result') if isinstance(data.get('processing_result'), dict) else {}
        runtime_config = data.get('runtime_config') if isinstance(data.get('runtime_config'), dict) else {}
        logs = data.get('logs')
        normalized_logs = [
            {'ts': str(item.get('ts', '')), 'level': str(item.get('level', 'info')), 'msg': str(item.get('msg', ''))}
            for item in logs[:10000]
        ] if isinstance(logs, list) else []

        # Admin/API-triggered jobs may have no webhook_event_id; accept and return ok
        if webhook_event_id is None:
            logger.info("[TILE_CALLBACK] Callback received with no webhook_event_id (admin/API-triggered job)")
            return Response({'status': 'ok', 'note': 'no event to update'}, status=status.HTTP_200_OK)

        # Try TIF webhook event first
        try:
            webhook_event = WebhookEvent.objects.get(pk=webhook_event_id)
        except WebhookEvent.DoesNotExist:
            webhook_event = None

        if webhook_event is not None:
            webhook_event.processed = True
            webhook_event.processed_at = timezone.now()
            webhook_event.tiles_generated = int(data.get('tiles_generated', 0))
            webhook_event.tif_files_processed = int(data.get('tif_files_processed', 0))
            webhook_event.processing_result = processing_result
            webhook_event.processing_error = str(data.get('processing_error', ''))[:65535]
            webhook_event.tile_generation_logs = normalized_logs
            webhook_event.save()

            # Persist TIF data (bounds, zoom levels, tiles_by_zoom) to DeveloperListingMedia and TIFMetadata
            self._save_tif_data_from_callback(webhook_event, processing_result)

            logger.info(
                f"[TILE_CALLBACK] Updated webhook_event_id={webhook_event_id} "
                f"tiles_generated={webhook_event.tiles_generated} logs_count={len(webhook_event.tile_generation_logs)}"
            )
            return Response({'status': 'ok', 'webhook_event_id': webhook_event_id}, status=status.HTTP_200_OK)

        # Fall through to land/plot webhook event (MVT lambda callback)
        try:
            land_plot_event = LandPlotWebhookEvent.objects.get(pk=webhook_event_id)
        except LandPlotWebhookEvent.DoesNotExist:
            logger.warning(f"[TILE_CALLBACK] webhook_event_id={webhook_event_id} not found in WebhookEvent or LandPlotWebhookEvent")
            return Response({'error': 'WebhookEvent not found'}, status=status.HTTP_404_NOT_FOUND)

        payload = land_plot_event.payload if isinstance(land_plot_event.payload, dict) else {}
        payload['tile_generation_callback'] = {
            'received_at': timezone.now().isoformat(),
            'success': bool(data.get('success', False)),
            'tiles_generated': int(data.get('tiles_generated', 0)),
            'tif_files_processed': int(data.get('tif_files_processed', 0)),
            'processing_result': processing_result,
            'processing_error': str(data.get('processing_error', ''))[:65535],
            'runtime_config': runtime_config,
            'logs': normalized_logs,
        }
        land_plot_event.payload = payload
        land_plot_event.save(update_fields=['payload'])

        logger.info(
            f"[TILE_CALLBACK] Updated land_plot_webhook_event_id={webhook_event_id} "
            f"tiles_generated={payload['tile_generation_callback']['tiles_generated']} logs_count={len(normalized_logs)}"
        )
        return Response({'status': 'ok', 'webhook_event_id': webhook_event_id}, status=status.HTTP_200_OK)

    def _save_tif_data_from_callback(self, webhook_event, processing_result):
        """Update DeveloperListingMedia and TIFMetadata from Lambda callback file_results (bounds, zoom, tiles_by_zoom)."""
        from ..models import DeveloperListing, DeveloperListingMedia, TIFMetadata
        listing_type = getattr(webhook_event, 'listing_type', None) or (processing_result or {}).get('listing_type')
        listing_id = getattr(webhook_event, 'listing_id', None) or (processing_result or {}).get('listing_id')
        if not listing_type or listing_id is None:
            return
        try:
            listing = DeveloperListing.objects.get(
                listing_type=listing_type,
                backend_listing_id=listing_id
            )
        except DeveloperListing.DoesNotExist:
            return
        file_results = (processing_result or {}).get('file_results') or []
        for fr in file_results:
            success = fr.get('success')
            file_name = fr.get('file_name') or ''
            media_id = fr.get('media_id')
            tiles_generated = int(fr.get('tiles_generated', 0))
            bounds = fr.get('bounds') if isinstance(fr.get('bounds'), dict) else None
            tiles_by_zoom = fr.get('tiles_by_zoom') if isinstance(fr.get('tiles_by_zoom'), dict) else {}
            min_zoom = fr.get('min_zoom')
            max_zoom = fr.get('max_zoom')
            s3_tile_path = fr.get('s3_tile_path') or ''

            media = None
            if media_id is not None:
                try:
                    media = DeveloperListingMedia.objects.get(listing=listing, backend_media_id=media_id)
                except DeveloperListingMedia.DoesNotExist:
                    pass
            if media is None and file_name:
                try:
                    media = DeveloperListingMedia.objects.get(listing=listing, file_name=file_name)
                except (DeveloperListingMedia.DoesNotExist, DeveloperListingMedia.MultipleObjectsReturned):
                    pass

            if not media:
                continue
            if success and (tiles_generated > 0 or bounds or tiles_by_zoom):
                media.tiles_generated = True
                media.tiles_generation_completed_at = timezone.now()
                media.total_tiles_generated = tiles_generated
                media.tiles_generation_error = ''
                if s3_tile_path:
                    media.s3_tile_path = s3_tile_path
                media.save()
                # Always write TIFMetadata when tiles succeeded. Worker callbacks often omit
                # bounds/zoom; map-data and admin rely on this row existing.
                TIFMetadata.objects.update_or_create(
                    media=media,
                    defaults={
                        'bounds_west': bounds.get('west') if bounds else None,
                        'bounds_south': bounds.get('south') if bounds else None,
                        'bounds_east': bounds.get('east') if bounds else None,
                        'bounds_north': bounds.get('north') if bounds else None,
                        'min_zoom': min_zoom if min_zoom is not None else 8,
                        'max_zoom': max_zoom if max_zoom is not None else 18,
                        'total_tiles_generated': tiles_generated,
                        'tiles_by_zoom': tiles_by_zoom,
                        'tif_data': {'bounds': bounds, 'tiles_by_zoom': tiles_by_zoom, 'min_zoom': min_zoom, 'max_zoom': max_zoom},
                    }
                )
            elif not success:
                err = fr.get('error') or 'Unknown error'
                media.tiles_generation_error = str(err)[:65535]
                media.save(update_fields=['tiles_generation_error'])


class DeveloperListingMediaWebhookView(APIView):
    """
    Webhook endpoint to receive notifications when developer listing media files
    are uploaded and need tile generation.
    
    Supports: Developer Land and Developer Plot (listing_type: developerland, developerplot).
    
    We store everything from the webhook:
    - WebhookEvent.payload: full request body (every key/value sent by backend)
    - DeveloperListing.listing_data: full listing object (unchanged)
    - DeveloperListingMedia.media_data: full media object per item (unchanged)
    
    This endpoint receives POST requests when:
    - DeveloperLand or DeveloperPlot is created/updated
    - TIF files are uploaded/updated
    
    The service will:
    1. Save full webhook data to database (no fields dropped)
    2. Download TIF files from configured URLs
    3. Generate map tiles from TIF files
    4. Upload tiles to Cloudflare R2 at the specified object key prefix
    5. Store TIF metadata and bounds
    """
    permission_classes = [AllowAny]  # Public endpoint (webhook)
    authentication_classes = []  # No authentication required
    http_method_names = ['post']  # Only allow POST requests
    
    def post(self, request):
        """Process webhook and generate tiles for TIF files"""
        from ..models import (
            DeveloperListing, DeveloperListingMedia, WebhookEvent
        )
        from django.utils import timezone
        
        logger.info(f"[WEBHOOK_RECEIVE] POST received (developer-listing-media)")
        
        webhook_event = None
        try:
            # Read body once (stream can only be read once); use it for both parsing and raw storage
            raw_body_full = ''
            try:
                raw_body_full = request.body.decode('utf-8', errors='replace')
            except Exception:
                pass
            import json
            data = {}
            if raw_body_full:
                try:
                    data = json.loads(raw_body_full)
                except Exception:
                    pass
            raw_body_str = raw_body_full[:50000] if len(raw_body_full) > 50000 else raw_body_full
            # Snapshot full payload so we store everything (no keys dropped)
            payload_snapshot = _webhook_payload_snapshot(data)
            # Print entire webhook JSON clearly for debugging
            _print_webhook_response("developer-listing-media", data)
            
            # Validate required fields
            event_type = data.get('event_type')
            listing_type = data.get('listing_type')
            listing_id = data.get('listing_id')
            tif_files = data.get('tif_files', [])
            listing_data = data.get('listing_data', {}) or {}
            media_items = data.get('media_items', []) or []
            action = data.get('action', '')
            
            if not all([event_type, listing_type, listing_id]):
                logger.warning(f"Webhook received with missing required fields: {data}")
                return Response(
                    {"error": "Missing required fields: event_type, listing_type, listing_id"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate event type
            valid_event_types = [
                'developer_listing_created',
                'developer_listing_updated',
                'developer_listing_media_uploaded',
                'developer_listing_media_updated',
                'developer_listing_media_deleted',
                'developer_listing_listing_deleted'
            ]
            
            if event_type not in valid_event_types:
                logger.warning(f"Webhook received with unknown event_type: {event_type}")
                return Response(
                    {"error": f"Unknown event_type: {event_type}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Save webhook event first – store everything: full payload + raw body (already read above)
            webhook_event = WebhookEvent.objects.create(
                event_type=event_type,
                action=action,
                listing_type=listing_type,
                listing_id=listing_id,
                payload=payload_snapshot,
                raw_body=raw_body_str,
                request_headers=dict(request.headers),
                request_ip=self._get_client_ip(request)
            )
            
            # Process all events (create/update/deletion) in background; return 202 immediately (Fix 1).
            # Bounded pool: bulk uploads can send 1000+ webhooks; unbounded threads exhaust DB pool and RAM.
            from ..webhook_background import submit_webhook_job
            submit_webhook_job(_process_developer_listing_webhook, webhook_event.id)
            logger.info(f"[WEBHOOK_RECEIVE] Accepted event={event_type} action={action} listing={listing_type} id={listing_id} webhook_event_id={webhook_event.id}")
            return Response(
                {'status': 'accepted', 'webhook_event_id': webhook_event.id},
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception as e:
            logger.error(f"[WEBHOOK_RECEIVE] Exception: {e}", exc_info=True)
            if webhook_event:
                webhook_event.processing_error = str(e)
                webhook_event.save()
            return Response(
                {
                    "error": "Internal server error processing webhook",
                    "details": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _parse_datetime(self, dt_string):
        """Parse datetime string from backend"""
        if not dt_string:
            return None
        from django.utils.dateparse import parse_datetime
        return parse_datetime(dt_string)

class LandPlotMVTBuildView(APIView):
    """
    Internal endpoint: build and return raw MVT bytes for a land/plot tile.
    Called by Lambda during tile refresh. Secured by X-Internal-Secret header.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    http_method_names = ['get']

    def get(self, request, z, x, y):
        secret = request.headers.get('X-Internal-Secret', '')
        expected = getattr(settings, 'TILE_CALLBACK_SECRET', '')
        if expected and secret != expected:
            return Response({'error': 'Unauthorized'}, status=401)
        try:
            from maps.management.commands.generate_land_plot_mvt_tiles import build_land_plot_tile_mvt
            mvt_bytes = build_land_plot_tile_mvt(z, x, y, percentiles=None, swap_lat_long=False)
            from django.http import HttpResponse
            return HttpResponse(
                mvt_bytes,
                content_type='application/vnd.mapbox-vector-tile',
                status=200,
            )
        except Exception as e:
            logger.error(f"[MVT_BUILD] Error building {z}/{x}/{y}: {e}", exc_info=True)
            return Response({'error': str(e)}, status=500)


def _process_land_plot_webhook(webhook_event_id):
    """
    Background processing for land/plot webhook: sync SyncedLand/SyncedPlot, enrich,
    refresh layer cache. Tile job is enqueued by signal (maps.signals) when SyncedLand/SyncedPlot
    is saved; we set thread-local so callback gets webhook_event_id.
    """
    from django.db import close_old_connections
    from ..models import LandPlotWebhookEvent, SyncedLand, SyncedPlot
    from ..sync_utils import defaults_for_land, defaults_for_plot
    from ..tile_job_queue import set_land_plot_webhook_event_id

    close_old_connections()
    try:
        webhook_event = LandPlotWebhookEvent.objects.get(pk=webhook_event_id)
    except LandPlotWebhookEvent.DoesNotExist:
        logger.warning(f"[LAND_PLOT_WEBHOOK] LandPlotWebhookEvent id={webhook_event_id} not found")
        return

    data = getattr(webhook_event, 'payload', None) or {}
    if not isinstance(data, dict):
        data = {}
    action = data.get('action', '')
    listing_type = data.get('listing_type', '')
    listing_id = data.get('listing_id')
    listing_data = data.get('listing_data', {}) or {}
    event_type = data.get('event_type', '')

    lat, lng = None, None
    if action in ('created', 'updated'):
        set_land_plot_webhook_event_id(webhook_event.id)
        try:
            item = dict(listing_data) if listing_data else {}
            item['id'] = listing_id
            if listing_type == 'land':
                defaults = defaults_for_land(item)
                record, _ = SyncedLand.objects.update_or_create(backend_id=listing_id, defaults=defaults)
                logger.info(f"[LAND_PLOT_WEBHOOK] Synced SyncedLand backend_id={listing_id}")
            else:
                defaults = defaults_for_plot(item)
                record, _ = SyncedPlot.objects.update_or_create(backend_id=listing_id, defaults=defaults)
                logger.info(f"[LAND_PLOT_WEBHOOK] Synced SyncedPlot backend_id={listing_id}")
            try:
                from maps.listing_layer_enrichment_service import enrich_synced_record
                if enrich_synced_record(record, update_location_point=True):
                    logger.info(f"[LAND_PLOT_WEBHOOK] Enriched {listing_type} {listing_id}")
                else:
                    logger.info(f"[LAND_PLOT_WEBHOOK] Enrichment skipped/cleared for {listing_type} {listing_id}")
            except Exception as enr_err:
                logger.warning(f"[LAND_PLOT_WEBHOOK] Enrichment failed for {listing_type} {listing_id}: {enr_err}", exc_info=True)
            try:
                from maps.listing_layer_enrichment_service import (
                    get_layer_ids_containing_point,
                    refresh_layer_point_count_cache,
                )
                if getattr(record, 'location_point', None) and not record.location_point.empty:
                    lat, lng = record.location_point.y, record.location_point.x
                if lat is None or lng is None:
                    lat = listing_data.get('lat') or listing_data.get('latitude')
                    lng = listing_data.get('long') or listing_data.get('lng') or listing_data.get('longitude') or listing_data.get('lon')
                logger.info(
                    f"[LAND_PLOT_WEBHOOK] Resolved coordinates for {listing_type} {listing_id}: "
                    f"lat={lat} lng={lng} "
                    f"location_point_present={bool(getattr(record, 'location_point', None) and not record.location_point.empty)}"
                )
                if lat is not None and lng is not None:
                    affected = get_layer_ids_containing_point(lat, lng)
                    if affected:
                        refresh_layer_point_count_cache(layer_ids=affected)
            except Exception as cache_err:
                logger.warning(f"[LAND_PLOT_WEBHOOK] Layer point count cache refresh failed: {cache_err}", exc_info=True)
            if lat is None or lng is None:
                logger.warning(
                    f"[LAND_PLOT_WEBHOOK] No coordinates for {listing_type} {listing_id} (tile job skipped)"
                )
        finally:
            set_land_plot_webhook_event_id(None)
    elif action == 'deleted':
        if listing_type == 'land':
            rec = SyncedLand.objects.filter(backend_id=listing_id).first()
            if rec and getattr(rec, 'location_point', None) and not rec.location_point.empty:
                lat, lng = rec.location_point.y, rec.location_point.x
            SyncedLand.objects.filter(backend_id=listing_id).delete()
            logger.info(f"[LAND_PLOT_WEBHOOK] Deleted SyncedLand backend_id={listing_id}")
        else:
            rec = SyncedPlot.objects.filter(backend_id=listing_id).first()
            if rec and getattr(rec, 'location_point', None) and not rec.location_point.empty:
                lat, lng = rec.location_point.y, rec.location_point.x
            SyncedPlot.objects.filter(backend_id=listing_id).delete()
            logger.info(f"[LAND_PLOT_WEBHOOK] Deleted SyncedPlot backend_id={listing_id}")
        if lat is not None and lng is not None:
            try:
                from maps.listing_layer_enrichment_service import (
                    get_layer_ids_containing_point,
                    refresh_layer_point_count_cache,
                )
                affected = get_layer_ids_containing_point(lat, lng)
                if affected:
                    refresh_layer_point_count_cache(layer_ids=affected)
            except Exception as cache_err:
                logger.warning(f"[LAND_PLOT_WEBHOOK] Layer point count cache refresh failed: {cache_err}", exc_info=True)


class LandPlotWebhookView(APIView):
    """
    Webhook endpoint for Land and Plot (regular listings) from 1acre-be.
    Receives create/update/delete events with full listing_data.
    Same pattern as DeveloperListingMediaWebhookView.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ['post']

    def post(self, request):
        from ..models import LandPlotWebhookEvent

        logger.info("[LAND_PLOT_WEBHOOK] ===== Land/Plot webhook POST received =====")
        try:
            raw_body = ''
            try:
                _req = getattr(request, '_request', request)
                raw_body = (_req.body.decode('utf-8', errors='replace')
                            if getattr(_req, 'body', None) else '')
            except Exception:
                pass
            data = {}
            if raw_body and raw_body.strip():
                try:
                    data = json.loads(raw_body)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"[LAND_PLOT_WEBHOOK] Could not parse JSON body: {e}")
                    return Response(
                        {"error": "Invalid JSON body"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            if not isinstance(data, dict):
                data = {}
            payload_snapshot = _webhook_payload_snapshot(data)
            _print_webhook_response("land-plot", data)
            if len(raw_body) > 50000:
                raw_body = raw_body[:50000]

            event_type = data.get('event_type')
            action = data.get('action')
            listing_type = data.get('listing_type')
            listing_id = data.get('listing_id')

            if not all([event_type, action, listing_type, listing_id is not None]):
                return Response(
                    {"error": "Missing required fields: event_type, action, listing_type, listing_id"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if event_type not in ('listing_created', 'listing_updated', 'listing_deleted'):
                return Response(
                    {"error": f"Unknown event_type: {event_type}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if listing_type not in ('land', 'plot'):
                return Response(
                    {"error": f"Unknown listing_type: {listing_type}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            ip = self._get_client_ip(request)
            webhook_event = LandPlotWebhookEvent.objects.create(
                event_type=event_type,
                action=action,
                listing_type=listing_type,
                listing_id=listing_id,
                payload=payload_snapshot,
                raw_body=raw_body,
                request_headers=dict(request.headers),
                request_ip=ip,
            )
            from ..webhook_background import submit_webhook_job
            submit_webhook_job(_process_land_plot_webhook, webhook_event.id)
            logger.info(f"[LAND_PLOT_WEBHOOK] Accepted: {action} {listing_type} {listing_id} event_id={webhook_event.id}")
            return Response(
                {"status": "success", "message": "accepted", "event_id": webhook_event.id},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"[LAND_PLOT_WEBHOOK] Error: {e}", exc_info=True)
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

