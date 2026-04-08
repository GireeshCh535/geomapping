# Generated manually for LayerListingLink

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("maps", "0039_alter_synceddeveloperland_enriched_layers_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="LayerListingLink",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        help_text="land, plot, developer_land, developer_plot",
                        max_length=32,
                    ),
                ),
                (
                    "listing_pk",
                    models.IntegerField(
                        help_text="Primary key of the row in the source listing table"
                    ),
                ),
                (
                    "backend_id",
                    models.IntegerField(help_text="Backend/API listing id"),
                ),
                (
                    "layer_slug",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "distance_km",
                    models.FloatField(
                        help_text="0 = inside layer geometry; else distance to layer in km"
                    ),
                ),
                (
                    "nearest_point",
                    models.JSONField(blank=True, null=True),
                ),
                ("enriched_at", models.DateTimeField()),
                (
                    "layer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="listing_links",
                        to="maps.datalayer",
                    ),
                ),
            ],
            options={
                "db_table": "maps_layer_listing_link",
            },
        ),
        migrations.AddConstraint(
            model_name="layerlistinglink",
            constraint=models.UniqueConstraint(
                fields=("layer", "source", "listing_pk"),
                name="uniq_maps_layer_listing_link_layer_source_listingpk",
            ),
        ),
        migrations.AddIndex(
            model_name="layerlistinglink",
            index=models.Index(fields=["layer", "source"], name="maps_layer_l_layer_i_7b8f91_idx"),
        ),
        migrations.AddIndex(
            model_name="layerlistinglink",
            index=models.Index(
                fields=["source", "listing_pk"], name="maps_layer_l_source__f7e2c1_idx"
            ),
        ),
    ]
