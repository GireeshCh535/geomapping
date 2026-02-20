# Land / Plot Map – APIs for Frontend

Base URL: your API host (e.g. `https://layers.1acre.in/api` or `http://localhost:8000/api`).

---

## 1. MVT tiles (map layer)

**GET** `/api/tiles/land-plot/{z}/{x}/{y}.mvt`

- **Purpose:** Vector tiles for the land/plot map. Served from CloudFront → S3 → local.
- **Parameters:** `z` (zoom 2–14), `x`, `y` (tile coordinates).
- **Response:** Binary MVT (`Content-Type: application/vnd.mapbox-vector-tile`).
- **Usage:** Set as MapLibre/Mapbox **vector** source; `source-layer` name is `landplot`.

**Example tile URL:**  
`/api/tiles/land-plot/10/707/415.mvt`

---

## 2. Hover (tooltip) – no extra API

**Show only marker title on hover.**  
Use the MVT feature property **`marker_label`** (this is the marker title / `marker_title` from the backend). No API call.

- On `mousemove` on the land/plot symbol layer: `feature.properties.marker_label`.
- If empty, you can fallback to e.g. `"Land"` or `"Plot"` from `feature.properties.type`.

**MVT feature properties** (for reference; only `marker_label` is needed for hover):

| Property       | Type   | Use                          |
|----------------|--------|------------------------------|
| `marker_label` | string | **Hover: show this only** (marker title) |
| `id`           | number | **Click: pass as `ids`** to enrichment-lookup |
| `type`         | string | `"land"` or `"plot"` – use as `listing_type` on click |
| `total_price`, `size`, `slug`, `status`, `tier`, `marker_id`, … | | Optional; full data on **click** via enrichment-lookup |

---

## 3. Click – full details (enrichment lookup)

**POST** `/api/enrichment-lookup/`

- **Purpose:** Get full record + enrichment (e.g. overlapping layers) for a listing when user clicks a point.
- **Request body (JSON):**
  ```json
  {
    "listing_type": "land" | "plot" | "developer_land" | "developer_plot",
    "ids": [ 123, 456 ]
  }
  ```
  - `ids`: list of **backend_id** (or Django pk). Use the `id` from the clicked MVT feature (`feature.properties.id`).
- **Response (200):**
  ```json
  {
    "listing_type": "land",
    "count": 1,
    "results": [
      {
        "id": 1,
        "backend_id": 123,
        "total_price": 5000000,
        "total_land_size": 2.5,
        "slug": "listing-slug",
        "status": "active",
        "location_point": { "type": "Point", "coordinates": [ 77.59, 12.97 ] },
        "enriched_layers": [
          { "layer_id": 1, "layer_slug": "...", "layer_type": "...", "distance_km": 0.5, "place": "..." }
        ],
        "enriched_at": "2025-01-15T10:00:00Z",
        "payload": { ... },
        ...
      }
    ]
  }
  ```

**Example (click on a point):**
1. From the clicked feature: `backendId = feature.properties.id`, `listingType = feature.properties.type`.
2. `POST /api/enrichment-lookup/` with `{ "listing_type": listingType, "ids": [ backendId ] }`.
3. Show detail panel/popup using `results[0]`.

---

## 4. GeoJSON (optional – for icons)

**GET** `/api/geojson/land-plot/all.geojson`

- **Purpose:** Single GeoJSON with all land/plot points. Optional; use if you need to discover all `marker_id` values to preload icons. Map **rendering** should use MVT tiles (1), not this GeoJSON.
- **Response:** GeoJSON FeatureCollection; each feature has `properties.type`, `properties.marker_id`, etc.

---

## Summary for frontend

| Need              | API / source                                      |
|-------------------|---------------------------------------------------|
| Map tiles         | **GET** `/api/tiles/land-plot/{z}/{x}/{y}.mvt`    |
| **Hover**         | Show only **`feature.properties.marker_label`** (marker title). No API. |
| **Click**         | **POST** `/api/enrichment-lookup/` with `listing_type` + `ids: [ feature.properties.id ]` → show full record |
| Icons (optional)  | **GET** `/api/geojson/land-plot/all.geojson` or derive from MVT |

Icons path (if you serve them): `/static/1acre-icons/{type}/{folder}/{marker_id}.svg`  
e.g. `plot/owner/plot-owner-1.svg`. Folder: `owner` if `marker_id` contains `-owner-`, `1acre` if `-1acre-`, else `base`.
