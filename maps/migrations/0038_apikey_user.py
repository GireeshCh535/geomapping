# Add optional user FK to ApiKey. Column is created here (0037 does not add user_id).

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("maps", "0037_add_api_key_model"),
    ]

    operations = [
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
    ]
