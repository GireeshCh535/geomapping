# Why the server stops (high CPU, 499s, workers saturated) – root cause

## Summary

The server has **2 vCPUs** and **~8 GB RAM**. Every incoming request that hits certain endpoints runs **heavy PostGIS spatial queries** (geometry containment, distance) and **multiple DB round-trips** in the **same worker process**. With only **2 gunicorn workers**, a few such requests at once tie up all workers → queue builds → clients time out → **499** and the app “stops responding.” CPU spikes to ~100% because PostGIS + Python run on the same 2 cores.

---

## 1. Request paths that cause the load

### A. Developer listing webhook – `POST /api/webhooks/developer-listing-media/`

**When it’s called:** This app **does not** schedule or trigger the webhook. The **1acre backend** (e.g. be.1acre.in) is the client that POSTs to this URL. The “every ~12s” was observed in nginx logs (same IP, similar spacing). That frequency is determined by the backend: e.g. it may send a webhook on every listing/media save, or on retries after timeouts, or when multiple users edit the same listing. To change how often it’s called, you’d need to adjust the **backend** (e.g. batch updates, or send webhooks less often). This repo only receives and processes the POST.

**What runs in the request (sync, in one worker):**

| Step | Where | What it does | Cost |
|------|--------|----------------|------|
| 1 | `views.py` | Create `WebhookEvent`, parse JSON, `DeveloperListing.update_or_create` | DB writes |
| 2 | `views.py` | `SyncedDeveloperLand` / `SyncedDeveloperPlot.update_or_create` | DB writes |
| 3 | `enrich_listing(listing)` | `listing_layer_enrichment_service.enrich_listing` | **Heavy** |
| 4 | `enrich_synced_record(synced_record)` | Same service, same point | **Heavy** (again) |
| 5 | `get_layer_ids_containing_point(lat, lng)` | `GeoFeature.objects.filter(geometry__contains=point)` | **Spatial query** |
| 6 | `refresh_layer_point_count_cache(layer_ids=affected)` | `get_point_counts_per_layer` + `_populate_layer_point_count_details` | **Very heavy** |
| 7 | Media loop | Update/create `DeveloperListingMedia`, maybe invoke Lambda | DB + boto3 |
| 8 | Return 200 | | |

**Heavy parts in detail:**

- **`compute_enriched_layers_for_point(point, state_name)`** (used by both `enrich_listing` and `enrich_synced_record`):
  - `_layer_ids_near_point(point)` → `DataLayer` bbox filter.
  - `GeoFeature.objects.filter(geometry__contains=point, layer_id__in=layer_ids)`.
  - `GeoFeature.objects.filter(geometry__dwithin=(point, 30km)).annotate(dist_m=ST_Distance(...))` and iteration.
  - `DataLayer.objects.filter(id__in=overlapping_layer_ids).values(...)`.
  So **each webhook runs this twice** (once for DeveloperListing, once for Synced*).

- **`get_layer_ids_containing_point(lat, lng)`**:  
  One more **full scan** of `GeoFeature` with `geometry__contains=point` (no layer_id filter).

- **`refresh_layer_point_count_cache(layer_ids)`**:
  - `get_point_counts_per_layer(layer_ids)` → for each layer, **overlapping** and **nearby** counts using `GeoFeature` + `geometry__contains` / `geometry__dwithin` and subqueries over Land/Plot/Synced* tables.
  - `_populate_layer_point_count_details(layer_ids)` → for each layer, again **overlapping** and **nearby** queries (with limits), then bulk insert into `LayerPointCountDetail`.

So **one webhook** = many spatial queries (contains, dwithin, ST_Distance) and a lot of DB/CPU work in a **single** worker. If webhooks arrive every ~12s and each takes 3–10s, one worker is often busy; with 2 workers, tile + other requests queue and you see 499s and 100% CPU.

---

### B. Enrichment lookup – `POST /api/enrichment-lookup/`

**Body:** `{ "listing_type": "developer_land", "ids": [1,2,3] }`.

- Loads records; for each record already has `enriched_layers` (from webhook).
- For **each** record and **each** entry in `enriched_layers`, calls **`get_place_for_point_in_layer(point, layer_id, distance_km)`**:
  - Either `GeoFeature.objects.filter(layer_id=..., geometry__contains=point).order_by('-area').first()`.
  - Or `GeoFeature.objects.filter(layer_id=..., geometry__dwithin=(point, 30km)).annotate(dist_m=ST_Distance(...)).order_by('dist_m').first()`.

So **N records × M layers = N×M** spatial queries in **one** request. Example: 10 records, 5 layers each → 50 spatial queries. This blocks one worker for a long time and burns CPU.

---

### C. Tile requests – `GET /api/tiles/<state>/<city>/<layer>/<z>/<x>/<y>.png`

**Already optimized:** Layer existence is **cached** (5 min), and the view **redirects (302)** to CloudFront, so no proxy I/O in Django. Cost per request is small (cache lookup + redirect). If you still see 499s on tiles, it’s usually because **other** requests (webhook, enrichment, HMDA) have saturated the 2 workers, not because tile logic is slow.

---

### D. HMDA boundary check – `GET /api/check-hmda-boundary/?lat=...&lng=...`

**Already optimized:** Result is **cached** by rounded (lat, lng), TTL 5 min (`views.py`). First request does one `DataLayer.get` + one `GeoFeature.objects.filter(geometry__contains=search_point).exists()`; repeats for same area are served from cache.

---

### E. Layer point counts – `GET/POST /api/layer-point-counts/`

Uses `LayerPointCountCache` (and optional details). If cache is warm, cost is low. When cache is refreshed (e.g. from webhook’s `refresh_layer_point_count_cache`), that refresh is heavy (see above).

---

## 2. Why CPU hits ~100%

- **PostGIS** runs in the same process as gunicorn (same 2 vCPUs). Spatial queries (contains, dwithin, ST_Distance) are CPU- and I/O-intensive.
- **Sync workers**: each request holds a worker until the **entire** response is done. Long-running webhook or enrichment lookup = one worker busy for seconds.
- **No offload**: webhook does **all** work (enrichment + cache refresh) **before** returning 200. No background task queue (Celery, etc.).
- So: a few webhooks + a few enrichment lookups + tile traffic → 2 workers busy → queue → timeouts → 499 and “server stopped.”

---

## 3. Root causes (code-level)

| Cause | Location | Why it hurts |
|-------|----------|---------------|
| Webhook does enrichment + cache refresh **synchronously** | `views.py` `DeveloperListingMediaWebhookView.post` | One webhook = many spatial queries and cache refresh in the request; blocks a worker for seconds. |
| **Double** enrichment per webhook | **Fixed:** enrich once, sync to both tables | **DeveloperListing** and **SyncedDeveloperLand/SyncedDeveloperPlot** are two tables for the *same* entity (same `backend_listing_id`/`backend_id`, same point). Both need `enriched_layers`; the value is identical. We now compute once and write the same list to both → halves enrichment cost per webhook. |
| `refresh_layer_point_count_cache(affected)` on every webhook | `views.py` after enrichment | `get_point_counts_per_layer` + `_populate_layer_point_count_details` for all “affected” layers = many spatial queries per webhook. |
| Enrichment lookup: **N×M** spatial queries | `views.py` `EnrichmentLookupAPIView.post`: loop over records and `enriched_layers`, call `get_place_for_point_in_layer` each time | One POST with 10 records × 5 layers = 50 DB/spatial queries in one request; holds one worker and high CPU. |
| Only 2 gunicorn workers | `docker-compose.yml` `WEB_CONCURRENCY=2` | Any 2 slow requests (webhook + enrichment, or 2 webhooks) tie up all capacity. |
| 2 vCPUs, 8 GB RAM | Server | Limited headroom; more workers risk OOM and more context switching. |

---

## 4. Recommendations (in order of impact)

1. **Offload webhook processing**
   - Accept webhook: create `WebhookEvent`, enqueue job (e.g. Celery, SQS + worker), return **202 Accepted** immediately.
   - Worker runs: `DeveloperListing`/Synced* update, `enrich_listing`, `enrich_synced_record`, `refresh_layer_point_count_cache`, media updates, Lambda invoke.
   - Effect: webhook response is fast; heavy work no longer blocks gunicorn workers or burns CPU in the same 2 processes.

2. **Debounce or skip cache refresh on webhook**
   - Option A: Do **not** call `refresh_layer_point_count_cache` in the webhook request; run it on a schedule (e.g. every 5–10 min) or from a background job.
   - Option B: Push “affected layer_ids” to a queue and have a single worker refresh cache in background (debounced per layer).
   - Effect: Webhook path becomes lighter; fewer spatial queries in the request.

3. **Enrich once per webhook**
   - Compute `enriched_layers` **once** (e.g. only in `enrich_synced_record`) and reuse for `DeveloperListing` if possible, or at least avoid two full `compute_enriched_layers_for_point` runs for the same point.
   - Effect: Cuts enrichment cost per webhook roughly in half.

4. **Cache or limit “place” resolution in enrichment lookup**
   - For `POST /api/enrichment-lookup/`, either:
     - Cache `get_place_for_point_in_layer(point, layer_id, distance_km)` by `(layer_id, rounded_lat, rounded_lng)` with short TTL, or
     - Resolve “place” only for the first few layers per record, or
     - Lazy-load “place” in a separate endpoint when the user expands a layer.
   - Effect: Fewer spatial queries per enrichment-lookup request; lower CPU and latency.

5. **Keep workers at 2 on current hardware**
   - With 2 vCPUs and 8 GB, increasing workers can increase context switching and OOM risk. Fix the **cost per request** (offload, debounce, cache) rather than adding more workers on this box.

6. **Upgrade instance if you cannot offload soon**
   - Move to 4 vCPU + 16 GB (or similar) so you can run 4 workers and have more headroom for the same code; then still apply 1–4 to avoid future saturation.

---

## 5. Files to change (for reference)

- **Webhook flow:** `maps/views.py` – `DeveloperListingMediaWebhookView.post` (enrichment + cache refresh).
- **Enrichment service:** `maps/listing_layer_enrichment_service.py` – `compute_enriched_layers_for_point`, `get_layer_ids_containing_point`, `refresh_layer_point_count_cache`, `get_point_counts_per_layer`, `_populate_layer_point_count_details`.
- **Enrichment lookup:** `maps/views.py` – `EnrichmentLookupAPIView.post` (loop calling `get_place_for_point_in_layer`).
- **Worker count:** `docker-compose.yml` – `WEB_CONCURRENCY`.

---

## 6. Quick checks when it “stops again”

- **Nginx:** `docker logs geomapping-nginx-1 2>&1 | grep " 499 " | tail -20` → which URLs are getting 499.
- **App log:** `docker compose logs --tail=200 web` → look for `[WEBHOOK_RECEIVE]`, `Enrichment lookup`, and any long gaps between log lines (worker blocked).
- **CPU:** CloudWatch CPU utilization; if it’s at 100% during 499s, the above request paths are the cause.

Implementing **offload webhook** (1) and **debounce/skip cache refresh** (2) will have the largest impact on stability and CPU.
