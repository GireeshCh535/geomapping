"""
Spatial overlap engine that maps `DataLayer` -> `LgdDivision` (state / district /
subdistrict) using PostGIS, scoped per state.

Why this is its own module:
- Called by both the `POST /relevance/reindex` API and the
  `reindex_all_relevance` management command.
- Keeps the SQL/spatial logic out of the views so it can be tested and reused.

Contract:
- `compute_relevance_pairs(layer, state_backend_ids)` -> set of
  (lgd_division_id, matched_level, source_state_backend_id) tuples.
- `reindex_layer(layer, payload)` performs the upsert + stale-row cleanup
  inside a single transaction and returns counts.

Acceptance criteria from the spec the engine satisfies:
- District / subdistrict matches are constrained to the layer's state(s)
  (so a Telangana layer never matches Andhra districts even when geometries
  touch the border).
- Idempotent: re-running `reindex_layer` does not create duplicates and
  removes pairs that no longer match.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

from django.db import connection, transaction
from django.utils import timezone

from .models import DataLayer, LgdDivision, RelevantLayer

logger = logging.getLogger('maps.views')


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------

def extract_state_backend_ids(payload: dict) -> list[int]:
    """
    Pull state backend_ids from the reindex payload's `states` block.

    Accepts the recommended `states` shape:
        {"primary": {"id": ..}, "additional": [{"id": ..}, ..], "all": [{"id": ..}, ..]}
    and also tolerates flat lists / scalar ids so 1acre-be can evolve the
    contract without breaking us.
    """
    states_block = (payload or {}).get('states') or {}
    raw_ids: list = []

    if isinstance(states_block, dict):
        primary = states_block.get('primary')
        if isinstance(primary, dict):
            raw_ids.append(primary.get('id') or primary.get('backend_id'))
        elif isinstance(primary, int):
            raw_ids.append(primary)

        for source_key in ('all', 'additional'):
            entries = states_block.get(source_key) or []
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        raw_ids.append(entry.get('id') or entry.get('backend_id'))
                    elif isinstance(entry, int):
                        raw_ids.append(entry)
    elif isinstance(states_block, list):
        for entry in states_block:
            if isinstance(entry, dict):
                raw_ids.append(entry.get('id') or entry.get('backend_id'))
            elif isinstance(entry, int):
                raw_ids.append(entry)

    state_ids: list[int] = []
    seen: set[int] = set()
    for value in raw_ids:
        try:
            sid = int(value) if value is not None else None
        except (TypeError, ValueError):
            sid = None
        if sid is not None and sid not in seen:
            seen.add(sid)
            state_ids.append(sid)
    return state_ids


def fallback_state_backend_ids_from_layer(layer: DataLayer) -> list[int]:
    """
    When the reindex payload omits `states`, fall back to the layer's primary
    state inferred from `layer.city.state_ref`.

    Geomapping `State` rows are not the same table as `LgdDivision(division_type='state')`,
    so we look up the LGD state by name (case-insensitive) and slug.
    """
    state_ref = getattr(layer.city, 'state_ref', None) if layer.city_id else None
    if not state_ref:
        return []
    candidates = LgdDivision.objects.filter(division_type='state')
    match = (
        candidates.filter(name__iexact=state_ref.name).first()
        or candidates.filter(slug__iexact=state_ref.slug).first()
    )
    return [match.backend_id] if match and match.backend_id is not None else []


def resolve_layer_from_payload(payload: dict) -> tuple[Optional[DataLayer], dict]:
    """
    Resolve a geomapping `DataLayer` from a reindex payload.

    Resolution order:
        1) geompapping_layer_id / layer_id_geomapping
        2) geompapping_layer_name_slug / layer_slug
    """
    geomapping_layer_id = payload.get('geompapping_layer_id') or payload.get('layer_id_geomapping')
    if geomapping_layer_id is not None:
        try:
            layer = DataLayer.objects.select_related('city__state_ref').get(pk=int(geomapping_layer_id))
            return layer, {}
        except (ValueError, TypeError, DataLayer.DoesNotExist):
            return None, {
                'error': 'unknown_layer',
                'detail': f'No DataLayer found for geompapping_layer_id={geomapping_layer_id}',
            }

    slug = payload.get('geompapping_layer_name_slug') or payload.get('layer_slug')
    if slug:
        matches = list(
            DataLayer.objects
            .select_related('city__state_ref')
            .filter(slug=slug)[:3]
        )
        if not matches:
            return None, {
                'error': 'unknown_layer',
                'detail': f'No DataLayer found for slug={slug!r}',
            }
        if len(matches) > 1:
            return None, {
                'error': 'ambiguous_layer',
                'detail': (
                    f'slug={slug!r} matches multiple DataLayer rows '
                    f'({[(l.id, l.city.slug) for l in matches]}). '
                    'Send geompapping_layer_id to disambiguate.'
                ),
            }
        return matches[0], {}

    return None, {
        'error': 'missing_layer_identifier',
        'detail': 'Provide geompapping_layer_id or geompapping_layer_name_slug',
    }


# ---------------------------------------------------------------------------
# Spatial overlap (PostGIS, no Python geometry round-trip)
# ---------------------------------------------------------------------------

def _intersect_lgd_with_layer(
    layer_id: int,
    division_type: str,
    state_backend_id: Optional[int] = None,
    backend_ids: Optional[Iterable[int]] = None,
    parent_backend_ids: Optional[Iterable[int]] = None,
) -> list[int]:
    """
    Return LgdDivision ids of the given `division_type` (within `state_backend_id`,
    optionally also restricted to `parent_backend_ids`) whose geometry intersects
    *any* GeoFeature geometry belonging to `layer_id`.

    Implementation: a single SQL `EXISTS` join lets PostGIS pick the GiST index
    on `geo_features.geometry` per LGD candidate. Avoids `ST_Union` over the
    layer (slow + memory-heavy on large layers).
    """
    sql = [
        "SELECT lgd.id",
        "FROM lgd_divisions lgd",
        "WHERE lgd.division_type = %s",
        "  AND lgd.geom IS NOT NULL",
    ]
    params: list = [division_type]

    if state_backend_id is not None:
        sql.append("  AND lgd.state_backend_id = %s")
        params.append(state_backend_id)

    if backend_ids is not None:
        backend_list = [int(v) for v in backend_ids if v is not None]
        if not backend_list:
            return []
        sql.append("  AND lgd.backend_id = ANY(%s)")
        params.append(backend_list)

    if parent_backend_ids is not None:
        parent_list = [int(p) for p in parent_backend_ids if p is not None]
        if not parent_list:
            return []
        sql.append("  AND lgd.parent_backend_id = ANY(%s)")
        params.append(parent_list)

    sql.append(
        "  AND EXISTS ("
        "    SELECT 1 FROM geo_features gf"
        "    WHERE gf.layer_id = %s"
        "      AND gf.is_valid = TRUE"
        "      AND gf.geometry && lgd.geom"
        "      AND ST_Intersects(gf.geometry, lgd.geom)"
        "  )"
    )
    params.append(layer_id)

    with connection.cursor() as cursor:
        cursor.execute("\n".join(sql), params)
        return [row[0] for row in cursor.fetchall()]


def compute_relevance_pairs(
    layer: DataLayer,
    state_backend_ids: Iterable[int],
) -> list[tuple[int, str, int]]:
    """
    For each state in `state_backend_ids`, compute relevant LgdDivision ids at
    state / district / subdistrict (and mandal) levels using PostGIS overlap.

    Returns deduplicated tuples of (lgddivision_id, matched_level, source_state_backend_id).
    A single LGD division can only appear once per layer (unique constraint), so
    the *first* matched level wins, in this order: state > district > subdistrict > mandal.
    """
    pairs: dict[int, tuple[str, int]] = {}  # lgddivision_id -> (matched_level, source_state)

    state_ids = sorted({int(sid) for sid in state_backend_ids if sid is not None})
    if not state_ids:
        return []

    for source_state_backend_id in state_ids:
        # Step 1: only continue when the layer actually intersects this state boundary.
        state_ids_hit = _intersect_lgd_with_layer(
            layer_id=layer.id,
            division_type='state',
            backend_ids=[source_state_backend_id],
        )
        if not state_ids_hit:
            continue
        for sid in state_ids_hit:
            pairs.setdefault(sid, ('state', source_state_backend_id))

        # Step 2: district matches inside this state.
        district_ids = _intersect_lgd_with_layer(
            layer_id=layer.id,
            division_type='district',
            state_backend_id=source_state_backend_id,
        )
        for did in district_ids:
            pairs.setdefault(did, ('district', source_state_backend_id))

        # Step 3: only after district match, check mandal/subdistrict under those districts.
        if not district_ids:
            continue

        matched_district_backend_ids: list[int] = []
        matched_district_backend_ids = list(
            LgdDivision.objects
            .filter(id__in=district_ids)
            .values_list('backend_id', flat=True)
        )

        # Subdistrict matches scoped to matched districts.
        subdistrict_ids = _intersect_lgd_with_layer(
            layer_id=layer.id,
            division_type='subdistrict',
            state_backend_id=source_state_backend_id,
            parent_backend_ids=matched_district_backend_ids or None,
        )
        for sid in subdistrict_ids:
            pairs.setdefault(sid, ('subdistrict', source_state_backend_id))

        # Mandal matches (Telangana / AP nomenclature for subdistrict).
        mandal_ids = _intersect_lgd_with_layer(
            layer_id=layer.id,
            division_type='mandal',
            state_backend_id=source_state_backend_id,
            parent_backend_ids=matched_district_backend_ids or None,
        )
        for mid in mandal_ids:
            pairs.setdefault(mid, ('mandal', source_state_backend_id))

    return [
        (lgd_id, level, source_state)
        for lgd_id, (level, source_state) in pairs.items()
    ]


# ---------------------------------------------------------------------------
# Persistence (idempotent upsert + stale-row cleanup)
# ---------------------------------------------------------------------------
#
# For each reindex, sets are LgdDivision PKs (`RelevantLayer.lgddivision_id`):
#   Remove  := old_set − new_set   → delete rows no longer relevant
#   Add     := new_set − old_set   → insert new pairs
#   Keep    := old_set ∩ new_set   → update row only if matched_level / source changed


@transaction.atomic
def reindex_layer(layer: DataLayer, payload: Optional[dict] = None) -> dict:
    """
    Recompute relevance pairs for `layer` and persist them idempotently.

    Persistence follows set math on LgdDivision ids (see module comment above):
    remove (old − new), add (new − old), keep (intersection) with optional field updates.

    Returns: {pairs_written, pairs_updated, pairs_deleted, total_pairs, state_backend_ids}.
    """
    payload = payload or {}
    state_backend_ids = extract_state_backend_ids(payload)
    if not state_backend_ids:
        state_backend_ids = fallback_state_backend_ids_from_layer(layer)

    new_pairs = compute_relevance_pairs(layer, state_backend_ids)
    new_by_lgd: dict[int, tuple[str, int]] = {
        lgd_id: (matched_level, source_state)
        for lgd_id, matched_level, source_state in new_pairs
    }
    new_lgd_ids = set(new_by_lgd.keys())

    existing_qs = RelevantLayer.objects.filter(layer=layer)
    existing_by_lgd = {row.lgddivision_id: row for row in existing_qs}
    old_lgd_ids = set(existing_by_lgd.keys())

    to_remove_ids = old_lgd_ids - new_lgd_ids
    to_add_ids = new_lgd_ids - old_lgd_ids
    keep_ids = old_lgd_ids & new_lgd_ids

    to_create: list[RelevantLayer] = []
    to_update: list[RelevantLayer] = []
    now = timezone.now()

    for lgd_id in to_add_ids:
        matched_level, source_state = new_by_lgd[lgd_id]
        to_create.append(RelevantLayer(
            layer=layer,
            lgddivision_id=lgd_id,
            matched_level=matched_level,
            source_state_backend_id=source_state,
        ))

    for lgd_id in keep_ids:
        matched_level, source_state = new_by_lgd[lgd_id]
        existing = existing_by_lgd[lgd_id]
        changed = False
        if existing.matched_level != matched_level:
            existing.matched_level = matched_level
            changed = True
        if existing.source_state_backend_id != source_state:
            existing.source_state_backend_id = source_state
            changed = True
        if changed:
            existing.updated_at = now
            to_update.append(existing)

    if to_create:
        RelevantLayer.objects.bulk_create(to_create, batch_size=1000, ignore_conflicts=True)
    if to_update:
        RelevantLayer.objects.bulk_update(
            to_update,
            ['matched_level', 'source_state_backend_id', 'updated_at'],
            batch_size=1000,
        )

    deleted_count = 0
    if to_remove_ids:
        deleted_count, _ = RelevantLayer.objects.filter(
            layer=layer,
            lgddivision_id__in=to_remove_ids,
        ).delete()

    result = {
        'pairs_written': len(to_create),
        'pairs_updated': len(to_update),
        'pairs_deleted': deleted_count,
        'total_pairs': len(new_pairs),
        'state_backend_ids': state_backend_ids,
    }
    logger.info(
        "reindex_layer layer_id=%s slug=%s states=%s -> %s",
        layer.id, layer.slug, state_backend_ids, result,
    )
    return result


def get_layer_relevant_data(layer: DataLayer) -> list[dict]:
    """
    Return canonical relevant-layer response rows for one DataLayer.
    """
    rows = (
        RelevantLayer.objects
        .select_related('lgddivision')
        .filter(layer=layer)
        .order_by('matched_level', 'lgddivision__name')
    )
    return [
        {
            'geomapping_layer_id': layer.id,
            'geomapping_layer_name_slug': layer.slug,
            'lgd_division_id': row.lgddivision.backend_id if row.lgddivision_id else None,
            'lgd_division_name': row.lgddivision.name if row.lgddivision_id else None,
            'lgd_division_slug': row.lgddivision.slug if row.lgddivision_id else None,
            'lgd_division_code': row.lgddivision.code if row.lgddivision_id else None,
            'lgd_division_type': row.lgddivision.division_type if row.lgddivision_id else None,
            'matched_level': row.matched_level,
            'source_state_id': row.source_state_backend_id,
        }
        for row in rows
    ]
