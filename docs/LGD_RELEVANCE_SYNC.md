# LGD Division + relevance sync (geomapping)

This document describes how administrative boundaries from 1acre-be (`LgdDivision`) are loaded into geomapping, how `(DataLayer, LgdDivision)` pairs are computed, and how they are written to `relevant_layers`—via a **Django signal** when a layer becomes ready, or manually through the **management command** and **HTTP API**.

## Data model (geomapping)

| Concept | Django model | DB table | Notes |
|--------|----------------|----------|--------|
| LGD mirror | `LgdDivision` | `lgd_divisions` | `backend_id` = 1acre-be `LgdDivision.id` (sync key). `geom` is WGS84 `MultiPolygon`. |
| Relevance output | `RelevantLayer` | `relevant_layers` | Unique `(layer, lgddivision)`. |

Layer boundaries come from `GeoFeature` rows for each `DataLayer` (not a single column on the layer).

## Migrations

Apply before loading data:

```bash
docker exec -it geomapping_web_1 python manage.py migrate
```

Migrations of interest: `0045_lgddivision_relevantlayer` (and follow-ups such as `0046_*` if present).

---

## 1) Importing LGD from a **plain SQL** dump (1acre-be `location_lgddivision`)

A typical `pg_dump` SQL file contains `CREATE TABLE` + `COPY public.location_lgddivision ...`. That creates **`location_lgddivision`** in the target DB, not `lgd_divisions` directly. You then **copy/upsert** into `lgd_divisions`.

### 1a) Import the SQL file

```bash
docker exec -i geomapping_db_1 psql -U postgres -d geo_mapping_db < /path/to/lgddivision_new.sql
```

If the dump uses `ALTER TABLE ... OWNER TO oneacreadmin`, create a minimal role first (or fix errors and re-run):

```bash
docker exec -i geomapping_db_1 psql -U postgres -d geo_mapping_db -c \
  "DO \$\$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'oneacreadmin') THEN CREATE ROLE oneacreadmin; END IF; END \$\$;"
```

### 1b) Copy from `location_lgddivision` → `lgd_divisions`

```sql
INSERT INTO lgd_divisions (
  backend_id, name, slug, code, division_type,
  parent_backend_id, state_backend_id, geom, backend_updated_at, synced_at
)
SELECT
  id AS backend_id,
  name,
  COALESCE(slug, ''),
  COALESCE(code, ''),
  division_type,
  parent_id AS parent_backend_id,
  CASE WHEN division_type = 'state' THEN id ELSE NULL END AS state_backend_id,
  CASE
    WHEN ST_SRID(geometry) = 4326 THEN ST_Multi(geometry)
    WHEN ST_SRID(geometry) = 0 THEN ST_Multi(ST_SetSRID(geometry, 4326))
    ELSE ST_Multi(ST_Transform(geometry, 4326))
  END AS geom,
  NOW(),
  NOW()
FROM location_lgddivision
ON CONFLICT (backend_id) DO UPDATE SET
  name = EXCLUDED.name,
  slug = EXCLUDED.slug,
  code = EXCLUDED.code,
  division_type = EXCLUDED.division_type,
  parent_backend_id = EXCLUDED.parent_backend_id,
  geom = EXCLUDED.geom,
  backend_updated_at = EXCLUDED.backend_updated_at,
  synced_at = EXCLUDED.synced_at;

UPDATE lgd_divisions c
SET parent_id = p.id
FROM lgd_divisions p
WHERE c.parent_backend_id = p.backend_id;

WITH RECURSIVE chain AS (
  SELECT d.backend_id AS start_id, d.backend_id AS curr_id, d.parent_backend_id, d.division_type
  FROM lgd_divisions d
  UNION ALL
  SELECT c.start_id, p.backend_id, p.parent_backend_id, p.division_type
  FROM chain c
  JOIN lgd_divisions p ON p.backend_id = c.parent_backend_id
),
state_map AS (
  SELECT start_id, MIN(curr_id) FILTER (WHERE division_type = 'state') AS state_id
  FROM chain
  GROUP BY start_id
)
UPDATE lgd_divisions d
SET state_backend_id = s.state_id
FROM state_map s
WHERE d.backend_id = s.start_id;
```

**Verify:**

```sql
SELECT division_type, COUNT(*) FROM lgd_divisions GROUP BY 1 ORDER BY 1;
```

---

## 2) Importing from **pg_dump custom** format (`.dump`)

List contents (needs `pg_restore` new enough to read the file; e.g. PG 18 on Ubuntu):

```bash
/usr/lib/postgresql/18/bin/pg_restore -l /path/to/lgddivision.dump | head
```

Restore **data** for the LGD table only (table name in dump is usually `location_lgddivision`):

```bash
/usr/lib/postgresql/18/bin/pg_restore \
  --host=127.0.0.1 --port=5433 \
  --username=postgres --dbname=geo_mapping_db \
  --data-only --no-owner --no-privileges \
  -t location_lgddivision \
  /path/to/lgddivision.dump
```

Then run the same **1b) copy into `lgd_divisions`** SQL as above.

### **Exporting** LGD from 1acre-be (for reference)

To create a new dump from the source database (run where `pg_dump` can reach 1acre-be DB):

```bash
pg_dump -h <host> -U <user> -d <dbname> -Fc -t location_lgddivision -f lgddivision.dump

pg_dump -h <host> -U <user> -d <dbname> --inserts -t location_lgddivision -f lgddivision.sql
```

---

## 3) Reindexing layers from a JSON payload (management command)

Payload shape (per layer), from 1acre-be:

```json
{
  "layer_id": 104,
  "layer_name": "Kota Masterplan",
  "geompapping_layer_name_slug": "masterplan",
  "states": {
    "primary": { "id": 34, "name": "Rajasthan", "slug": "rajasthan" },
    "additional": [],
    "all": [{ "id": 34, "name": "Rajasthan", "slug": "rajasthan" }]
  }
}
```

File can be a **single object** or an **array** of such objects.

Dry run:

```bash
docker exec -it geomapping_web_1 python manage.py reindex_all_relevance \
  --payload-json /path/inside/container/layers_payload.json \
  --dry-run
```

Run:

```bash
docker exec -it geomapping_web_1 python manage.py reindex_all_relevance \
  --payload-json /path/inside/container/layers_payload.json
```

Mount the JSON into the container or copy it in with `docker cp` if the path is only on the host.

---

## 3.5) Automatic reindex when a `DataLayer` is ready (signal)

**Location:** `maps/signals.py` (`_datalayer_post_save`, `_relevance_reindex_after_commit`).

After the DB transaction **commits**, geomapping runs **`reindex_layer(layer, payload=None)`**, which fills `relevant_layers` using PostGIS overlap. State scope uses **`fallback_state_backend_ids_from_layer`** (LGD state inferred from `layer.city.state_ref`) because no JSON payload is passed.

**When it runs** (same gate as auto listing enrichment):

- `DataLayer.is_processed` is **True**
- Category is **not** `DEVELOPER_LISTING`
- **Either** the row was **just created** with `is_processed=True`, **or** `is_processed` **transitioned** from false → true (processing finished)

**Order on commit:** listing enrichment first, then relevance reindex.

**Not triggered:** saves that only tweak metadata while already processed (no create / no first-time-process transition). For explicit **multi-state** payloads or fixes, use **`reindex_all_relevance`** or **`POST /api/relevance/reindex`** with a `states` block.

---

## 4) HTTP API: `/api/relevance/reindex`

Base URL example (host maps container `8000` → host `8001`): `http://localhost:8001`

Authentication: project uses `X-API-Key` when active API keys exist in DB; domain-restricted keys may require `X-API-Caller-Host` or browser `Origin`/`Referer`.

### GET — read stored relevance (no recompute)

Single layer by slug:

```bash
curl -s "http://localhost:8001/api/relevance/reindex?geompapping_layer_name_slug=masterplan" \
  -H "X-API-Key: <KEY>" \
  -H "X-API-Caller-Host: localhost"
```

Single layer by geomapping `DataLayer.id`:

```bash
curl -s "http://localhost:8001/api/relevance/reindex?geompapping_layer_id=123" \
  -H "X-API-Key: <KEY>" \
  -H "X-API-Caller-Host: localhost"
```

All layers:

```bash
curl -s "http://localhost:8001/api/relevance/reindex?all=true" \
  -H "X-API-Key: <KEY>" \
  -H "X-API-Caller-Host: localhost"
```

### POST — recompute + return `relevant_layers`

```bash
curl -s -X POST "http://localhost:8001/api/relevance/reindex/" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <KEY>" \
  -H "X-API-Caller-Host: localhost" \
  -d '{
    "layer_id": 104,
    "geompapping_layer_name_slug": "masterplan",
    "states": {
      "primary": {"id": 34},
      "additional": [],
      "all": [{"id": 34}]
    }
  }'
```

Resolution: prefer `geompapping_layer_id` (geomapping `DataLayer` PK); else `geompapping_layer_name_slug` must be unique across cities.

---

## 5) Matching logic (high level)

For each state id in the payload:

1. Intersect layer `GeoFeature` geometries with the **state** LGD polygon (`backend_id` = state id).
2. If that passes, find intersecting **districts** in that state.
3. Only under matched districts, find **subdistrict** / **mandal** overlaps.

Results are stored in `relevant_layers` with `matched_level` and optional `source_state_backend_id`.

---

## 6) Code references

| Piece | Location |
|-------|----------|
| `LgdDivision` / `RelevantLayer` models | `maps/models.py` |
| Spatial + upsert (set math: remove / add / keep) | `maps/relevance_service.py` |
| Auto reindex on processed layer (`post_save` + `on_commit`) | `maps/signals.py` |
| App loads signals | `maps/apps.py` → `ready()` imports `maps.signals` |
| Reindex API | `maps/views/relevance_reindex.py` |
| URLs | `maps/urls.py` → `relevance/reindex/` |
| Bulk reindex command | `maps/management/commands/reindex_all_relevance.py` |

---

## 7) Docker quick reference

Typical services:

| Service | Port (example) |
|---------|------------------|
| Web | `8001:8000` |
| PostGIS | `5433:5432` |
| Redis | `6380:6379` |

Replace container names (`geomapping_web_1`, `geomapping_db_1`) with `docker ps` output on your machine.
