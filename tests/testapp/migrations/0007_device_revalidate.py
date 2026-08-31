"""
The revalidation split off `0006`'s `AddField`.

`previous_schema_hash` stays unset, which is how `AlterPydantic` knows
the field is being filled for the first time — and makes it force every
default in, user data or not.
"""

from django.db import migrations

import pined.django.db.migrations


class Migration(migrations.Migration):
    dependencies = [
        ("testapp", "0006_device_metadata"),
    ]

    operations = [
        pined.django.db.migrations.AlterPydantic(
            model_name="device",
            name="metadata",
            schema_hash="f6f354d12d0e9bec",
            forwards_defaults={"region": "forced", "max_backup": 123},
        ),
    ]
