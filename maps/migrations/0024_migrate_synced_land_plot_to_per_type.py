# Data migration: copy existing SyncedLandPlot rows into per-type tables

from django.db import migrations


def copy_to_per_type_tables(apps, schema_editor):
    SyncedLandPlot = apps.get_model('maps', 'SyncedLandPlot')
    SyncedLand = apps.get_model('maps', 'SyncedLand')
    SyncedPlot = apps.get_model('maps', 'SyncedPlot')
    SyncedDeveloperLand = apps.get_model('maps', 'SyncedDeveloperLand')
    SyncedDeveloperPlot = apps.get_model('maps', 'SyncedDeveloperPlot')

    mapping = {
        'land': SyncedLand,
        'plot': SyncedPlot,
        'developerland': SyncedDeveloperLand,
        'developerplot': SyncedDeveloperPlot,
    }

    for row in SyncedLandPlot.objects.all():
        model_class = mapping.get(row.listing_type)
        if not model_class:
            continue
        model_class.objects.update_or_create(
            backend_id=row.backend_id,
            defaults={'payload': row.payload},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('maps', '0023_synced_land_plot_per_type_tables'),
    ]

    operations = [
        migrations.RunPython(copy_to_per_type_tables, noop_reverse),
    ]
