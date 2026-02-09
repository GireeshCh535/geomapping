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
from django.utils import timezone

from maps.models import (
    SyncedLand,
    SyncedPlot,
    SyncedDeveloperLand,
    SyncedDeveloperPlot,
)

logger = logging.getLogger(__name__)

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
                    model_class.objects.update_or_create(
                        backend_id=backend_id,
                        defaults={'payload': item},
                    )

            next_page = data.get('next')
            if not next_page:
                break
            page += 1

        return count
