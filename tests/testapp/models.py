from django.db import models

from pined.django.db.models import PydanticField

from .schemas import Metadata


class Terminal(models.Model):
    """
    The model the whole migration chain is built around.

    `extra` is a plain `JSONField`, so it doubles as the source for a
    nested `F("extra.software.update_attempts")` lookup and as the field
    `AlterPydantic` should refuse to touch. `metadata` is nullable to
    keep the "row holds NULL" path reachable, and carries an explicit
    `default=None` so the field's own deconstruction never changes
    across the chain — otherwise every schema bump that adds a required
    pydantic field would drag an `AlterField` along with it.
    """

    current_software_version = models.CharField(max_length=32, default="0.0.0")
    extra = models.JSONField(null=True, default=None)
    metadata = PydanticField(Metadata, null=True, default=None)


class Device(models.Model):
    """
    A model that gets its `PydanticField` later than it gets its rows.

    `metadata` arrives in `0006`, which is what makes the
    "field created for the first time" path reachable on a table that
    already holds data.
    """

    name = models.CharField(max_length=32, default="device")
    metadata = PydanticField(Metadata, default=Metadata)
