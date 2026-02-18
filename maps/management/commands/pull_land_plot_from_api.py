"""
Pull Land, Plot, Developer Land and Developer Plot data from 1acre-be API and store in geomapping.

Uses:
  - GET /lands/                     (LandListSerializer)  → optional GET /lands/{id}/ (LandSerializer) with --fetch-detail
  - GET /plots/                     (PlotListSerializer) → optional GET /plots/{id}/ (PlotSerializer) with --fetch-detail
  - GET /developer-lands-listings/  → optional GET /developer-lands/{id}/ with --fetch-detail
  - GET /developer-plots-listings/  → optional GET /developer-plots/{id}/ with --fetch-detail

Data is stored in per-type tables: SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot.
The full API response (list item or detail when --fetch-detail) is stored in each row's payload JSONField.

Usage (clear and fetch again):
  # Clear ALL 5 tables and fetch lands + plots + developer lands + developer plots (one token)
  python manage.py pull_land_plot_from_api --clear-first --token "YOUR_TOKEN"

  # Clear and fetch only one type at a time (--clear-before-fetch clears only that table)
  python manage.py pull_land_plot_from_api --clear-before-fetch --lands-only --token "USER_TOKEN"
  python manage.py pull_land_plot_from_api --clear-before-fetch --plots-only --token "USER_TOKEN"
  python manage.py pull_land_plot_from_api --clear-before-fetch --developer-lands-only --token "DEV_TOKEN"
  python manage.py pull_land_plot_from_api --clear-before-fetch --developer-plots-only --token "DEV_TOKEN"

Other:
  python manage.py pull_land_plot_from_api --fetch-detail --token "eyJ..."   # store full detail API response in payload
  python manage.py pull_land_plot_from_api --lands-only --plots-only         # fetch only lands and plots (no clear)
  export ONECRE_BE_TOKEN="eyJ..." && python manage.py pull_land_plot_from_api
"""

import logging
import os
import requests
from django.core.management.base import BaseCommand

from maps.models import (
    SyncedLand,
    SyncedLandPlot,
    SyncedPlot,
    SyncedDeveloperLand,
    SyncedDeveloperPlot,
)
from maps.sync_utils import (
    defaults_for_land,
    defaults_for_plot,
    defaults_for_developer_land,
    defaults_for_developer_plot,
)

logger = logging.getLogger(__name__)

DEFAULTS_BUILDER = {
    SyncedLand: defaults_for_land,
    SyncedPlot: defaults_for_plot,
    SyncedDeveloperLand: defaults_for_developer_land,
    SyncedDeveloperPlot: defaults_for_developer_plot,
}

DEFAULT_BASE_URL = 'https://prod-be.1acre.in'
DEFAULT_PAGE_SIZE = 50  # 1acre-be CustomPagination max_page_size is 50

# When --fetch-detail: for each list path, fetch this detail path (use {id} for backend_id)
LIST_PATH_TO_DETAIL_PATH = {
    '/lands/': '/lands/{id}/',
    '/plots/': '/plots/{id}/',
    '/developer-lands-listings/': '/developer-lands/{id}/',
    '/developer-plots-listings/': '/developer-plots/{id}/',
}


class Command(BaseCommand):
    help = 'Pull Land, Plot, Developer Land and Developer Plot from 1acre-be API into per-type tables.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--base-url',
            type=str,
            default=os.environ.get('ONECRE_BE_BASE_URL', DEFAULT_BASE_URL),
            help=f'1acre-be API base URL (default: {DEFAULT_BASE_URL} or ONECRE_BE_BASE_URL)',
        )
        parser.add_argument(
            '--token',
            type=str,
            default=os.environ.get('ONECRE_BE_TOKEN', ''),
            help='Auth token (Authorization: Token <token>). Or set ONECRE_BE_TOKEN.',
        )
        parser.add_argument(
            '--page-size',
            type=int,
            default=DEFAULT_PAGE_SIZE,
            help=f'Items per page (default: {DEFAULT_PAGE_SIZE}, backend max 50)',
        )
        parser.add_argument(
            '--lands-only',
            action='store_true',
            help='Only fetch lands',
        )
        parser.add_argument(
            '--plots-only',
            action='store_true',
            help='Only fetch plots',
        )
        parser.add_argument(
            '--developer-lands-only',
            action='store_true',
            help='Only fetch developer lands',
        )
        parser.add_argument(
            '--developer-plots-only',
            action='store_true',
            help='Only fetch developer plots',
        )
        parser.add_argument(
            '--clear-first',
            action='store_true',
            help='Delete all rows from SyncedLandPlot, SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot before pulling (full fresh sync).',
        )
        parser.add_argument(
            '--clear-before-fetch',
            action='store_true',
            help='Clear only the synced table(s) that will be fetched in this run (e.g. with --lands-only clear only SyncedLand), then fetch. Use for per-type clear + refetch.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Log requests and counts only, do not save to DB',
        )
        parser.add_argument(
            '--fetch-detail',
            action='store_true',
            help='For each list item, fetch detail API (/lands/{id}/, /plots/{id}/, etc.) and store that full response in payload (slower but complete data).',
        )

    def handle(self, *args, **options):
        base_url = options['base_url'].rstrip('/')
        token = (options['token'] or '').strip()
        page_size = min(options['page_size'], 50)
        lands_only = options['lands_only']
        plots_only = options['plots_only']
        developer_lands_only = options['developer_lands_only']
        developer_plots_only = options['developer_plots_only']
        dry_run = options['dry_run']
        fetch_detail = options.get('fetch_detail', False)

        any_only = lands_only or plots_only or developer_lands_only or developer_plots_only
        fetch_lands = lands_only or not any_only
        fetch_plots = plots_only or not any_only
        fetch_dev_lands = developer_lands_only or not any_only
        fetch_dev_plots = developer_plots_only or not any_only
        clear_first = options['clear_first']
        clear_before_fetch = options.get('clear_before_fetch', False)

        if clear_first and not dry_run:
            self._clear_all_synced_tables()
        elif clear_before_fetch and not dry_run:
            self._clear_tables_before_fetch(fetch_lands, fetch_plots, fetch_dev_lands, fetch_dev_plots)

        if not token:
            self.stdout.write(
                self.style.ERROR('Token is required. Use --token or set ONECRE_BE_TOKEN.')
            )
            return

        # JWT tokens (start with eyJ) use Bearer; Django REST Token auth uses Token
        auth_header = f'Bearer {token}' if token.strip().startswith('eyJ') else f'Token {token}'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': auth_header,
        }

        total_lands = 0
        total_plots = 0
        total_dev_lands = 0
        total_dev_plots = 0

        if fetch_lands:
            self.stdout.write('Fetching lands...')
            total_lands = self._fetch_and_save(
                base_url=base_url,
                path='/lands/',
                model_class=SyncedLand,
                headers=headers,
                page_size=page_size,
                dry_run=dry_run,
                fetch_detail=fetch_detail,
            )
            self.stdout.write(self.style.SUCCESS(f'Lands: {total_lands} items'))

        if fetch_plots:
            self.stdout.write('Fetching plots...')
            total_plots = self._fetch_and_save(
                base_url=base_url,
                path='/plots/',
                model_class=SyncedPlot,
                headers=headers,
                page_size=page_size,
                dry_run=dry_run,
                fetch_detail=fetch_detail,
            )
            self.stdout.write(self.style.SUCCESS(f'Plots: {total_plots} items'))

        if fetch_dev_lands:
            self.stdout.write('Fetching developer lands...')
            total_dev_lands = self._fetch_and_save(
                base_url=base_url,
                path='/developer-lands-listings/',
                model_class=SyncedDeveloperLand,
                headers=headers,
                page_size=page_size,
                dry_run=dry_run,
                fetch_detail=fetch_detail,
            )
            self.stdout.write(self.style.SUCCESS(f'Developer lands: {total_dev_lands} items'))

        if fetch_dev_plots:
            self.stdout.write('Fetching developer plots...')
            total_dev_plots = self._fetch_and_save(
                base_url=base_url,
                path='/developer-plots-listings/',
                model_class=SyncedDeveloperPlot,
                headers=headers,
                page_size=page_size,
                dry_run=dry_run,
                fetch_detail=fetch_detail,
            )
            self.stdout.write(self.style.SUCCESS(f'Developer plots: {total_dev_plots} items'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: no data saved.'))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Done. Synced lands={total_lands}, plots={total_plots}, '
                    f'developer_lands={total_dev_lands}, developer_plots={total_dev_plots}.'
                )
            )

    def _fetch_detail(self, base_url, detail_path, headers):
        """Fetch a single detail API response. Returns dict or None on failure."""
        url = f'{base_url}{detail_path}'
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning('Detail fetch failed: %s error=%s', url, e)
            return None

    def _fetch_and_save(self, base_url, path, model_class, headers, page_size, dry_run, fetch_detail=False):
        url = f'{base_url}{path}'
        count = 0
        page = 1
        detail_path_template = LIST_PATH_TO_DETAIL_PATH.get(path)

        while True:
            params = {'page': page, 'page_size': page_size}
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=60)
                resp.raise_for_status()
            except requests.RequestException as e:
                self.stdout.write(
                    self.style.ERROR(f'Request failed: {url} params={params} error={e}')
                )
                break

            data = resp.json()
            results = data.get('results')
            if not results:
                break

            for item in results:
                backend_id = item.get('id')
                if backend_id is None:
                    continue
                count += 1
                if not dry_run:
                    # Optionally fetch full detail so payload = /lands/{id}/ etc.
                    if fetch_detail and detail_path_template:
                        detail_path = detail_path_template.format(id=backend_id)
                        detail_item = self._fetch_detail(base_url, detail_path, headers)
                        if detail_item is not None:
                            item = detail_item
                        # else keep list item so we still persist something
                    builder = DEFAULTS_BUILDER.get(model_class)
                    defaults = builder(item) if builder else {'payload': item}
                    model_class.objects.update_or_create(
                        backend_id=backend_id,
                        defaults=defaults,
                    )

            next_page = data.get('next')
            if not next_page:
                break
            page += 1

        return count

    def _clear_all_synced_tables(self):
        """Delete all rows from the 5 synced tables (legacy + per-type) for a fresh pull."""
        tables = [
            (SyncedLandPlot, 'SyncedLandPlot'),
            (SyncedLand, 'SyncedLand'),
            (SyncedPlot, 'SyncedPlot'),
            (SyncedDeveloperLand, 'SyncedDeveloperLand'),
            (SyncedDeveloperPlot, 'SyncedDeveloperPlot'),
        ]
        for model, label in tables:
            n, _ = model.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Cleared {label}: {n} rows deleted.'))
        self.stdout.write(self.style.SUCCESS('All synced tables cleared. Starting fresh pull.'))

    def _clear_tables_before_fetch(self, fetch_lands, fetch_plots, fetch_dev_lands, fetch_dev_plots):
        """Clear only the per-type table(s) that will be fetched in this run."""
        cleared = []
        if fetch_lands:
            n, _ = SyncedLand.objects.all().delete()
            cleared.append(f'SyncedLand({n})')
        if fetch_plots:
            n, _ = SyncedPlot.objects.all().delete()
            cleared.append(f'SyncedPlot({n})')
        if fetch_dev_lands:
            n, _ = SyncedDeveloperLand.objects.all().delete()
            cleared.append(f'SyncedDeveloperLand({n})')
        if fetch_dev_plots:
            n, _ = SyncedDeveloperPlot.objects.all().delete()
            cleared.append(f'SyncedDeveloperPlot({n})')
        if cleared:
            self.stdout.write(self.style.WARNING('Cleared (rows): ' + ', '.join(cleared)))
            self.stdout.write(self.style.SUCCESS('Cleared tables for this run. Fetching...'))
        else:
            self.stdout.write(self.style.WARNING('No tables selected to clear (use e.g. --lands-only).'))
