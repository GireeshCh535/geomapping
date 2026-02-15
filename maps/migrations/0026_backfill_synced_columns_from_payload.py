# Backfill new columns from payload for SyncedLand, SyncedPlot, SyncedDeveloperLand, SyncedDeveloperPlot

from django.db import migrations
from django.utils.dateparse import parse_datetime


def _f(v, default=None):
    if v is None:
        return default
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v) if v is not None else default
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


def backfill_land(apps, schema_editor):
    SyncedLand = apps.get_model('maps', 'SyncedLand')
    for r in SyncedLand.objects.all():
        p = r.payload or {}
        r.lat = _f(p.get('lat'))
        r.long = _f(p.get('long'))
        r.slug = (p.get('slug') or '')[:500]
        r.status = (p.get('status') or '')[:20]
        r.price_per_acre = _f(p.get('price_per_acre'))
        r.total_land_size = _f(p.get('total_land_size'))
        r.total_price = _f(p.get('total_price'))
        r.created_at = _dt(p.get('created_at'))
        r.updated_at = _dt(p.get('updated_at'))
        r.exposure_type = (p.get('exposure_type') or '')[:20]
        r.seller_type = (p.get('seller_type') or '')[:30]
        z = p.get('zone_type')
        r.zone_type = (z or '')[:50] if z is not None else None
        r.is_exact = bool(p.get('is_exact'))
        r.approach_road_length = _f(p.get('approach_road_length'))
        r.save(update_fields=[
            'lat', 'long', 'slug', 'status', 'price_per_acre', 'total_land_size', 'total_price',
            'created_at', 'updated_at', 'exposure_type', 'seller_type', 'zone_type',
            'is_exact', 'approach_road_length',
        ])


def backfill_plot(apps, schema_editor):
    SyncedPlot = apps.get_model('maps', 'SyncedPlot')
    for r in SyncedPlot.objects.all():
        p = r.payload or {}
        r.lat = _f(p.get('lat'))
        r.long = _f(p.get('long'))
        r.slug = (p.get('slug') or '')[:500]
        r.status = (p.get('status') or '')[:20]
        r.total_plot_size = _f(p.get('total_plot_size'))
        r.total_price = _f(p.get('total_price'))
        r.price_per_square_yard = _f(p.get('price_per_square_yard'))
        r.created_at = _dt(p.get('created_at'))
        r.updated_at = _dt(p.get('updated_at'))
        r.exposure_type = (p.get('exposure_type') or '')[:20]
        r.seller_type = (p.get('seller_type') or '')[:30]
        z = p.get('zone_type')
        r.zone_type = (z or '')[:50] if z is not None else None
        r.is_exact = bool(p.get('is_exact'))
        r.abutting_road_length = _f(p.get('abutting_road_length'))
        r.save(update_fields=[
            'lat', 'long', 'slug', 'status', 'total_plot_size', 'total_price', 'price_per_square_yard',
            'created_at', 'updated_at', 'exposure_type', 'seller_type', 'zone_type',
            'is_exact', 'abutting_road_length',
        ])


def backfill_developer_land(apps, schema_editor):
    SyncedDeveloperLand = apps.get_model('maps', 'SyncedDeveloperLand')
    for r in SyncedDeveloperLand.objects.all():
        p = r.payload or {}
        r.status = (p.get('status') or '')[:20]
        r.location = (p.get('location') or '')[:200]
        r.deal_type = (p.get('deal_type') or '')[:50]
        r.total_land_size = _f(p.get('total_land_size'))
        r.total_price = _f(p.get('total_price'))
        r.price_per_acre = _f(p.get('price_per_acre'))
        r.created_at = _dt(p.get('created_at'))
        r.updated_at = _dt(p.get('updated_at'))
        r.exposure_type = (p.get('exposure_type') or '')[:20]
        r.marker_title = (p.get('marker_title') or '')[:500]
        r.description = (p.get('description') or '')[:10000]
        r.save(update_fields=[
            'status', 'location', 'deal_type', 'total_land_size', 'total_price', 'price_per_acre',
            'created_at', 'updated_at', 'exposure_type', 'marker_title', 'description',
        ])


def backfill_developer_plot(apps, schema_editor):
    SyncedDeveloperPlot = apps.get_model('maps', 'SyncedDeveloperPlot')
    for r in SyncedDeveloperPlot.objects.all():
        p = r.payload or {}
        r.status = (p.get('status') or '')[:20]
        r.location = (p.get('location') or '')[:200]
        r.deal_type = (p.get('deal_type') or '')[:50]
        r.total_plot_size = _f(p.get('total_plot_size'))
        r.total_price = _f(p.get('total_price'))
        r.price_per_square_yard = _f(p.get('price_per_square_yard'))
        r.created_at = _dt(p.get('created_at'))
        r.updated_at = _dt(p.get('updated_at'))
        r.exposure_type = (p.get('exposure_type') or '')[:20]
        r.marker_title = (p.get('marker_title') or '')[:500]
        r.description = (p.get('description') or '')[:10000]
        r.save(update_fields=[
            'status', 'location', 'deal_type', 'total_plot_size', 'total_price', 'price_per_square_yard',
            'created_at', 'updated_at', 'exposure_type', 'marker_title', 'description',
        ])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('maps', '0025_synced_tables_payload_columns'),
    ]

    operations = [
        migrations.RunPython(backfill_land, noop),
        migrations.RunPython(backfill_plot, noop),
        migrations.RunPython(backfill_developer_land, noop),
        migrations.RunPython(backfill_developer_plot, noop),
    ]
