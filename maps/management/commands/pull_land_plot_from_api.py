"""
Pull Land, Plot, Developer Land and Developer Plot data from 1acre-be API and store in geomapping.

Uses:
  - GET /lands/                     (LandListSerializer)
  - GET /plots/                     (PlotListSerializer)
  - GET /developer-lands-listings/  (DeveloperLandListSerializer)
  - GET /developer-plots-listings/  (DeveloperPlotListSerializer)

Data is stored in per-type tables: SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot.

Usage:
  python manage.py pull_land_plot_from_api --token "eyJ..."
  python manage.py pull_land_plot_from_api --clear-first --token "eyJ..."   # clear all 5 tables then pull fresh
  python manage.py pull_land_plot_from_api --lands-only
  python manage.py pull_land_plot_from_api --plots-only
  python manage.py pull_land_plot_from_api --developer-lands-only
  python manage.py pull_land_plot_from_api --developer-plots-only
  export ONECRE_BE_TOKEN="eyJ..." && python manage.py pull_land_plot_from_api
"""

import logging
import os
import requests
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from maps.models import (
    SyncedLand,
    SyncedLandPlot,
    SyncedPlot,
    SyncedDeveloperLand,
    SyncedDeveloperPlot,
)

logger = logging.getLogger(__name__)


def _f(v, default=None):
    if v is None:
        return default
    if isinstance(v, bool):
        return default
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except (ValueError, TypeError):
            return default
    return default


def _dt(s):
    if not s or not isinstance(s, str):
        return None
    return parse_datetime(s)


def _str_trunc(s, max_len):
    if s is None:
        return ''
    return (str(s) or '')[:max_len]


def defaults_for_land(item):
    p = item
    return {
        'payload': item,
        'lat': _f(p.get('lat')),
        'long': _f(p.get('long')),
        'slug': _str_trunc(p.get('slug'), 500),
        'status': _str_trunc(p.get('status'), 20),
        'price_per_acre': _f(p.get('price_per_acre')),
        'total_land_size': _f(p.get('total_land_size')),
        'total_price': _f(p.get('total_price')),
        'created_at': _dt(p.get('created_at')),
        'updated_at': _dt(p.get('updated_at')),
        'exposure_type': _str_trunc(p.get('exposure_type'), 20),
        'seller_type': _str_trunc(p.get('seller_type'), 30),
        'zone_type': (p.get('zone_type') or '')[:50] if p.get('zone_type') is not None else None,
        'is_exact': bool(p.get('is_exact')),
        'approach_road_length': _f(p.get('approach_road_length')),
    }


def defaults_for_plot(item):
    p = item
    return {
        'payload': item,
        'lat': _f(p.get('lat')),
        'long': _f(p.get('long')),
        'slug': _str_trunc(p.get('slug'), 500),
        'status': _str_trunc(p.get('status'), 20),
        'total_plot_size': _f(p.get('total_plot_size')),
        'total_price': _f(p.get('total_price')),
        'price_per_square_yard': _f(p.get('price_per_square_yard')),
        'created_at': _dt(p.get('created_at')),
        'updated_at': _dt(p.get('updated_at')),
        'exposure_type': _str_trunc(p.get('exposure_type'), 20),
        'seller_type': _str_trunc(p.get('seller_type'), 30),
        'zone_type': (p.get('zone_type') or '')[:50] if p.get('zone_type') is not None else None,
        'is_exact': bool(p.get('is_exact')),
        'abutting_road_length': _f(p.get('abutting_road_length')),
    }


def defaults_for_developer_land(item):
    p = item
    return {
        'payload': item,
        'status': _str_trunc(p.get('status'), 20),
        'location': _str_trunc(p.get('location'), 200),
        'deal_type': _str_trunc(p.get('deal_type'), 50),
        'total_land_size': _f(p.get('total_land_size')),
        'total_price': _f(p.get('total_price')),
        'price_per_acre': _f(p.get('price_per_acre')),
        'created_at': _dt(p.get('created_at')),
        'updated_at': _dt(p.get('updated_at')),
        'exposure_type': _str_trunc(p.get('exposure_type'), 20),
        'marker_title': _str_trunc(p.get('marker_title'), 500),
        'description': _str_trunc(p.get('description'), 10000),
    }


def defaults_for_developer_plot(item):
    p = item
    return {
        'payload': item,
        'status': _str_trunc(p.get('status'), 20),
        'location': _str_trunc(p.get('location'), 200),
        'deal_type': _str_trunc(p.get('deal_type'), 50),
        'total_plot_size': _f(p.get('total_plot_size')),
        'total_price': _f(p.get('total_price')),
        'price_per_square_yard': _f(p.get('price_per_square_yard')),
        'created_at': _dt(p.get('created_at')),
        'updated_at': _dt(p.get('updated_at')),
        'exposure_type': _str_trunc(p.get('exposure_type'), 20),
        'marker_title': _str_trunc(p.get('marker_title'), 500),
        'description': _str_trunc(p.get('description'), 10000),
    }


DEFAULTS_BUILDER = {
    SyncedLand: defaults_for_land,
    SyncedPlot: defaults_for_plot,
    SyncedDeveloperLand: defaults_for_developer_land,
    SyncedDeveloperPlot: defaults_for_developer_plot,
}

DEFAULT_BASE_URL = 'https://prod-be.1acre.in'
DEFAULT_PAGE_SIZE = 50  # 1acre-be CustomPagination max_page_size is 50


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
            help='Delete all rows from SyncedLandPlot, SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot before pulling (fresh sync).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Log requests and counts only, do not save to DB',
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

        any_only = lands_only or plots_only or developer_lands_only or developer_plots_only
        fetch_lands = lands_only or not any_only
        fetch_plots = plots_only or not any_only
        fetch_dev_lands = developer_lands_only or not any_only
        fetch_dev_plots = developer_plots_only or not any_only
        clear_first = options['clear_first']

        if clear_first and not dry_run:
            self._clear_all_synced_tables()

        if not token:
            self.stdout.write(
                self.style.ERROR('Token is required. Use --token or set ONECRE_BE_TOKEN.')
            )
            return

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Token {token}',
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

    def _fetch_and_save(self, base_url, path, model_class, headers, page_size, dry_run):
        url = f'{base_url}{path}'
        count = 0
        page = 1

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
