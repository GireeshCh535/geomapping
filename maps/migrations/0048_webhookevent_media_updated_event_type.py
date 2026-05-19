from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("maps", "0047_layerlistinglink_listing_created_at_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="webhookevent",
            name="action",
            field=models.CharField(
                blank=True,
                help_text="Action: created, updated, media_uploaded, media_updated, media_deleted, listing_deleted",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="webhookevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("developer_listing_created", "Developer Listing Created"),
                    ("developer_listing_updated", "Developer Listing Updated"),
                    ("developer_listing_media_uploaded", "Media Uploaded"),
                    ("developer_listing_media_updated", "Media Updated"),
                    ("developer_listing_media_deleted", "Media Deleted"),
                    ("developer_listing_listing_deleted", "Listing Deleted"),
                ],
                max_length=50,
            ),
        ),
    ]
