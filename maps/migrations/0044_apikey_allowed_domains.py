from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0043_rename_maps_layer_l_layer_i_7b8f91_idx_maps_layer__layer_i_db8386_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='apikey',
            name='allowed_domains',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    'List of domains allowed to use this key (e.g. ["layers.1acre.in", "app.example.com"]). '
                    'Leave empty for no domain restriction. Requests from other origins will be rejected.'
                ),
            ),
        ),
    ]
