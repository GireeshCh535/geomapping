"""
Backfill / reconcile (DataLayer -> LgdDivision) relevance pairs.

Run after first LGD ingest, after schema/data changes on either side, or as a
periodic cron to repair drift between geomapping and 1acre-be.

Examples:
  python manage.py reindex_all_relevance
  python manage.py reindex_all_relevance --state telangana
  python manage.py reindex_all_relevance --layer hyderabad_masterplan
  python manage.py reindex_all_relevance --layer-ids 12,34,56 --dry-run
"""
from __future__ import annotations

import json
import time

from django.core.management.base import BaseCommand

from maps.models import DataLayer
from maps.relevance_service import get_layer_relevant_data, reindex_layer, resolve_layer_from_payload


class Command(BaseCommand):
    help = 'Recompute RelevantLayer pairs for all (or filtered) processed DataLayers.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--state',
            type=str,
            help='Restrict to layers whose city.state_ref.slug matches this value (e.g. "telangana")',
        )
        parser.add_argument(
            '--city',
            type=str,
            help='Restrict to layers in this city slug',
        )
        parser.add_argument(
            '--layer',
            type=str,
            help='Restrict to a single DataLayer.slug (still applies city/state filters if provided)',
        )
        parser.add_argument(
            '--layer-ids',
            type=str,
            help='Comma-separated DataLayer.id values',
        )
        parser.add_argument(
            '--include-unprocessed',
            action='store_true',
            help='Include DataLayers where is_processed=False (default: skip them)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Resolve and print the layers that would be reindexed; do not run the engine',
        )
        parser.add_argument(
            '--payload-json',
            type=str,
            help=(
                'Path to JSON payload file. Supports either a single object or a list of objects, '
                'each shaped like {layer_id, layer_name, geompapping_layer_name_slug, states}. '
                'When provided, filters (--state/--city/--layer/--layer-ids) are ignored.'
            ),
        )

    def handle(self, *args, **options):
        payload_json = options.get('payload_json')
        if payload_json:
            return self._handle_payload_json(payload_json, dry_run=bool(options.get('dry_run')))

        qs = DataLayer.objects.select_related('city__state_ref').all()
        if not options.get('include_unprocessed'):
            qs = qs.filter(is_processed=True)

        state_slug = options.get('state')
        if state_slug:
            qs = qs.filter(city__state_ref__slug=state_slug)

        city_slug = options.get('city')
        if city_slug:
            qs = qs.filter(city__slug=city_slug)

        layer_slug = options.get('layer')
        if layer_slug:
            qs = qs.filter(slug=layer_slug)

        layer_ids_raw = options.get('layer_ids')
        if layer_ids_raw:
            try:
                layer_ids = [int(x.strip()) for x in layer_ids_raw.split(',') if x.strip()]
            except ValueError:
                self.stderr.write(self.style.ERROR('--layer-ids must be comma-separated integers'))
                return
            qs = qs.filter(id__in=layer_ids)

        layers = list(qs.order_by('city__state_ref__slug', 'city__slug', 'slug'))
        self.stdout.write(f'Resolved {len(layers)} layer(s) for reindex.')

        if options.get('dry_run'):
            for layer in layers:
                state = layer.city.state_ref.slug if (layer.city_id and layer.city.state_ref) else '-'
                self.stdout.write(f'  - id={layer.id} state={state} city={layer.city.slug} slug={layer.slug}')
            self.stdout.write(self.style.SUCCESS('Dry run complete.'))
            return

        totals = {'pairs_written': 0, 'pairs_updated': 0, 'pairs_deleted': 0, 'total_pairs': 0, 'failed': 0}
        started = time.time()

        for index, layer in enumerate(layers, start=1):
            state = layer.city.state_ref.slug if (layer.city_id and layer.city.state_ref) else '-'
            try:
                # Pass an empty payload so the service falls back to layer.city.state_ref.
                result = reindex_layer(layer, payload={})
            except Exception as exc:
                totals['failed'] += 1
                self.stderr.write(self.style.ERROR(
                    f'[{index}/{len(layers)}] FAIL id={layer.id} slug={layer.slug}: {type(exc).__name__}: {exc}'
                ))
                continue

            for key in ('pairs_written', 'pairs_updated', 'pairs_deleted', 'total_pairs'):
                totals[key] += result.get(key, 0)
            self.stdout.write(
                f'[{index}/{len(layers)}] OK  id={layer.id} state={state} slug={layer.slug} '
                f'-> total={result.get("total_pairs", 0)} '
                f'(written={result.get("pairs_written", 0)}, '
                f'updated={result.get("pairs_updated", 0)}, '
                f'deleted={result.get("pairs_deleted", 0)})'
            )

        elapsed = time.time() - started
        self.stdout.write(self.style.SUCCESS(
            f'Done in {elapsed:.1f}s. totals={totals}'
        ))

    def _handle_payload_json(self, payload_json: str, dry_run: bool = False):
        try:
            with open(payload_json, encoding='utf-8') as fp:
                payload_data = json.load(fp)
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f'JSON file not found: {payload_json}'))
            return
        except json.JSONDecodeError as exc:
            self.stderr.write(self.style.ERROR(f'Invalid JSON in {payload_json}: {exc}'))
            return

        if isinstance(payload_data, dict):
            payloads = [payload_data]
        elif isinstance(payload_data, list):
            payloads = [p for p in payload_data if isinstance(p, dict)]
        else:
            self.stderr.write(self.style.ERROR('JSON root must be an object or an array of objects'))
            return

        self.stdout.write(f'Loaded {len(payloads)} payload item(s) from {payload_json}')
        totals = {'pairs_written': 0, 'pairs_updated': 0, 'pairs_deleted': 0, 'total_pairs': 0, 'failed': 0}
        started = time.time()

        for index, payload in enumerate(payloads, start=1):
            layer, err = resolve_layer_from_payload(payload)
            if not layer:
                totals['failed'] += 1
                self.stderr.write(self.style.ERROR(
                    f'[{index}/{len(payloads)}] FAIL payload layer resolver: {err}'
                ))
                continue

            if dry_run:
                self.stdout.write(
                    f'[{index}/{len(payloads)}] DRY  id={layer.id} slug={layer.slug} '
                    f'states={payload.get("states", {})}'
                )
                continue

            try:
                result = reindex_layer(layer, payload=payload)
            except Exception as exc:
                totals['failed'] += 1
                self.stderr.write(self.style.ERROR(
                    f'[{index}/{len(payloads)}] FAIL id={layer.id} slug={layer.slug}: {type(exc).__name__}: {exc}'
                ))
                continue

            relevant_data = get_layer_relevant_data(layer)
            for key in ('pairs_written', 'pairs_updated', 'pairs_deleted', 'total_pairs'):
                totals[key] += result.get(key, 0)
            self.stdout.write(
                f'[{index}/{len(payloads)}] OK  id={layer.id} slug={layer.slug} '
                f'-> total={result.get("total_pairs", 0)} '
                f'(written={result.get("pairs_written", 0)}, '
                f'updated={result.get("pairs_updated", 0)}, '
                f'deleted={result.get("pairs_deleted", 0)}) '
                f'response_rows={len(relevant_data)}'
            )

        elapsed = time.time() - started
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'Dry run complete in {elapsed:.1f}s.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Done in {elapsed:.1f}s. totals={totals}'
            ))
