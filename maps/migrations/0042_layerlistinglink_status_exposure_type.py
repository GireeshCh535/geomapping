# Generated manually

from django.db import migrations, models


def backfill_status_exposure(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    # One-shot denorm backfill from Synced* tables (new writes go through sync_layer_listing_links).
    statements = [
        """
        UPDATE maps_layer_listing_link AS l
        SET status = COALESCE(s.status, ''),
            exposure_type = COALESCE(s.exposure_type, '')
        FROM synced_land AS s
        WHERE l.source = 'land' AND l.listing_pk = s.id
        """,
        """
        UPDATE maps_layer_listing_link AS l
        SET status = COALESCE(s.status, ''),
            exposure_type = COALESCE(s.exposure_type, '')
        FROM synced_plot AS s
        WHERE l.source = 'plot' AND l.listing_pk = s.id
        """,
        """
        UPDATE maps_layer_listing_link AS l
        SET status = COALESCE(s.status, ''),
            exposure_type = COALESCE(s.exposure_type, '')
        FROM synced_developer_land AS s
        WHERE l.source = 'developer_land' AND l.listing_pk = s.id
        """,
        """
        UPDATE maps_layer_listing_link AS l
        SET status = COALESCE(s.status, ''),
            exposure_type = COALESCE(s.exposure_type, '')
        FROM synced_developer_plot AS s
        WHERE l.source = 'developer_plot' AND l.listing_pk = s.id
        """,
    ]
    with schema_editor.connection.cursor() as cursor:
        for sql in statements:
            cursor.execute(sql)


class Migration(migrations.Migration):

    dependencies = [
        ("maps", "0041_remove_developer_listing_layer_listing_links"),
    ]

    operations = [
        migrations.AddField(
            model_name="layerlistinglink",
            name="status",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Denormalized from Synced* listing row (e.g. active)",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="layerlistinglink",
            name="exposure_type",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Denormalized from Synced* listing row (e.g. public)",
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name="layerlistinglink",
            index=models.Index(
                fields=["layer", "status"],
                name="maps_layer_ll_layer_status_idx",
            ),
        ),
        migrations.RunPython(backfill_status_exposure, migrations.RunPython.noop),
    ]
