import django.contrib.gis.db.models.fields
import django.contrib.postgres.indexes
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0044_apikey_allowed_domains'),
    ]

    operations = [
        migrations.CreateModel(
            name='LgdDivision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('backend_id', models.IntegerField(help_text='Primary key of the LgdDivision row on 1acre-be (sync key)', unique=True)),
                ('name', models.CharField(max_length=255)),
                ('slug', models.CharField(blank=True, default='', max_length=500)),
                ('code', models.CharField(blank=True, default='', help_text='LGD code from source data', max_length=64)),
                ('division_type', models.CharField(choices=[('state', 'State'), ('district', 'District'), ('subdistrict', 'Subdistrict'), ('mandal', 'Mandal'), ('village', 'Village')], max_length=32)),
                ('parent_backend_id', models.IntegerField(blank=True, db_index=True, help_text='Raw parent backend_id, kept for repair after partial sync', null=True)),
                ('state_backend_id', models.IntegerField(blank=True, db_index=True, help_text='backend_id of the rolled-up state row (self for state rows)', null=True)),
                ('geom', django.contrib.gis.db.models.fields.MultiPolygonField(blank=True, null=True, srid=4326)),
                ('backend_updated_at', models.DateTimeField(blank=True, null=True)),
                ('synced_at', models.DateTimeField(auto_now=True)),
                ('parent', models.ForeignKey(blank=True, help_text='Parent division on 1acre-be (resolved by backend_id during sync)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='maps.lgddivision')),
            ],
            options={
                'db_table': 'lgd_divisions',
                'ordering': ['division_type', 'name'],
            },
        ),
        migrations.AddIndex(
            model_name='lgddivision',
            index=models.Index(fields=['division_type'], name='lgd_divisio_divisio_8e7f5d_idx'),
        ),
        migrations.AddIndex(
            model_name='lgddivision',
            index=models.Index(fields=['state_backend_id', 'division_type'], name='lgd_divisio_state_b_2c5b9b_idx'),
        ),
        migrations.AddIndex(
            model_name='lgddivision',
            index=models.Index(fields=['parent'], name='lgd_divisio_parent__9b3eb8_idx'),
        ),
        migrations.AddIndex(
            model_name='lgddivision',
            index=models.Index(fields=['slug'], name='lgd_divisio_slug_71b4f7_idx'),
        ),
        migrations.AddIndex(
            model_name='lgddivision',
            index=django.contrib.postgres.indexes.GistIndex(fields=['geom'], name='lgd_divisio_geom_3a14d2_gist'),
        ),

        migrations.CreateModel(
            name='RelevantLayer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_state_backend_id', models.IntegerField(blank=True, help_text='backend_id of the state under which this match was computed', null=True)),
                ('matched_level', models.CharField(help_text='state | district | subdistrict | mandal', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('layer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='relevant_lgd_divisions', to='maps.datalayer')),
                ('lgddivision', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='relevant_layers', to='maps.lgddivision')),
            ],
            options={
                'db_table': 'relevant_layers',
            },
        ),
        migrations.AddConstraint(
            model_name='relevantlayer',
            constraint=models.UniqueConstraint(fields=('layer', 'lgddivision'), name='uniq_relevant_layer_pair'),
        ),
        migrations.AddIndex(
            model_name='relevantlayer',
            index=models.Index(fields=['lgddivision'], name='relevant_la_lgddivi_e3a7c1_idx'),
        ),
        migrations.AddIndex(
            model_name='relevantlayer',
            index=models.Index(fields=['layer'], name='relevant_la_layer_i_2f8a44_idx'),
        ),
        migrations.AddIndex(
            model_name='relevantlayer',
            index=models.Index(fields=['updated_at'], name='relevant_la_updated_64b1c8_idx'),
        ),
        migrations.AddIndex(
            model_name='relevantlayer',
            index=models.Index(fields=['matched_level'], name='relevant_la_matched_3a92f6_idx'),
        ),
    ]
