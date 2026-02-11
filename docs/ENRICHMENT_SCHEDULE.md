# Listing–Layer Enrichment Schedule

Enrichment attaches overlapping and nearby (≤30 km) data layers to every listing (DeveloperListing + SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot). Each listing stores a unified `enriched_layers` list: `{ layer_id, layer_slug, layer_type, distance_km }` (0 = overlap, 0.01–30 = nearby).

## Daily job (recommended: off-peak)

Run the management command once per day, e.g. at 2 AM:

```bash
# Cron (Linux/macOS) – run at 2:00 AM every day
0 2 * * * cd /path/to/geomapping && python manage.py enrich_listing_layers
```

With virtualenv:

```bash
0 2 * * * cd /path/to/geomapping && .venv/bin/python manage.py enrich_listing_layers
```

## Command options

| Option | Description |
|--------|-------------|
| (default) | **Incremental**: new listings (enriched_at null), stale (synced_at/updated_at > enriched_at), and listings near layers created in last 24h |
| `--full` | Re-enrich all listings with coordinates |
| `--new-listings-only` | Only never-enriched (enriched_at is null) |
| `--new-layers-only` | Only re-enrich listings near layers created in last 24h |
| `--developer-only` | Only DeveloperListing (skip 4 Synced* tables) |
| `--synced-only` | Only SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot |
| `--dry-run` | Log what would be done, no DB writes |

## Automation

- **On new/updated DataLayer**: When a layer is saved and `is_processed=True`, the app automatically enriches all DeveloperListing and Synced* records whose `location_point` is within 30 km of that layer (see `maps/signals.py`).
- **Daily run**: Use cron (or Celery beat) to run `enrich_listing_layers` at a fixed time for incremental catch-up and consistency.
