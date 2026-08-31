"""
`Device.metadata` arrives — and nothing else.

The `AlterPydantic` django generated alongside the `AddField` was moved
into `0007` by hand. Left where it was, every row would still be holding
the field's own default by the time it ran, and nothing could tell the
forced backfill apart from the ordinary one.
"""

from django.db import migrations

import pined.django.db.models
import pined.django.serializers.json
import tests.testapp.schemas


class Migration(migrations.Migration):
    dependencies = [
        ("testapp", "0005_metadata_transform"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="metadata",
            field=pined.django.db.models.PydanticField(
                tests.testapp.schemas.Metadata,
                default=tests.testapp.schemas.Metadata,
                encoder=pined.django.serializers.json.JSONEncoder,
            ),
        ),
    ]
