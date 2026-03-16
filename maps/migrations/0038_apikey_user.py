# api_keys.user_id already exists in DB (NOT NULL); only make it nullable and add field to state.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("maps", "0037_add_api_key_model"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="apikey",
                    name="user",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="api_keys",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE api_keys ALTER COLUMN user_id DROP NOT NULL;",
                    reverse_sql="ALTER TABLE api_keys ALTER COLUMN user_id SET NOT NULL;",
                ),
            ],
        ),
    ]
