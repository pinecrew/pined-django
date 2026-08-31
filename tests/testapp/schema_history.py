"""
Every shape `schemas.Metadata` has had, kept as classes.

Nothing imports these at runtime — the migrations reference schema
hashes, and the schemas themselves live in
`migrations/_schema_terminal__metadata.json`. They exist so a test can
assert those hashes still describe these shapes: a pydantic release that
changes `model_json_schema()` would otherwise surface as a `KeyError`
somewhere deep in a data migration.

That they are named `MetadataV1`..`MetadataV4` and still answer to the
hashes the migrations declare is the point of `SchemaManager.normalize`:
a model's name is not part of its shape.
"""

import pydantic

from .schemas import Metadata


class MetadataV1(pydantic.BaseModel):
    os_version: str = "unknown"
    update_attempts: int = 0


class MetadataV2(pydantic.BaseModel):
    os_version: str = "unknown"
    update_attempts: int = 0
    max_backup: int = 10
    region: str


class MetadataV3(pydantic.BaseModel):
    android_version: str = "unknown"
    also_version: str = "unknown"
    current_software_version: str = ""
    update_attempts: int = 0
    max_backup: int = 10
    region: str


class MetadataV4(pydantic.BaseModel):
    android_version: str = "unknown"
    also_version: str = "unknown"
    current_software_version: str = ""
    update_attempts: int = 0
    max_backup: int = 10
    log_retention: int = 7
    region: str


#: Every version in order, newest last. `MetadataV5` is `schemas.Metadata`
#: itself — the shape the models still declare.
VERSIONS = (MetadataV1, MetadataV2, MetadataV3, MetadataV4, Metadata)
