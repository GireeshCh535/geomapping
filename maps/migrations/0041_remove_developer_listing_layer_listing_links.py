# Remove LayerListingLink rows with source=developer_listing (no longer used).

from django.db import migrations


def forwards(apps, schema_editor):
    LayerListingLink = apps.get_model("maps", "LayerListingLink")
    LayerListingLink.objects.filter(source="developer_listing").delete()


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("maps", "0040_layerlistinglink"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
