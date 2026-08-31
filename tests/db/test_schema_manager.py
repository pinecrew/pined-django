"""
`SchemaManager`, and a guard on the hashes the test app has committed.
"""

import importlib
import itertools
import json
import pathlib
from typing import Any

import pydantic
import pytest
from django.core.management import call_command

from pined.django.db.pydantic_field.migrations import AlterPydantic
from pined.django.db.pydantic_field.schema import SchemaManager
from tests.testapp.schema_history import VERSIONS

MIGRATIONS = (
    "0001_initial",
    "0002_metadata_defaults",
    "0003_metadata_expressions",
    "0004_metadata_override",
    "0005_metadata_transform",
    "0006_device_metadata",
    "0007_device_revalidate",
)
SCHEMA_FILES = ("_schema_terminal__metadata.json", "_schema_device__metadata.json")


class Shape(pydantic.BaseModel):
    """
    A model to hash and rebuild.
    """

    required: str
    optional: int = 3


def twin(name: str = "Shape", doc: str | None = None) -> type[pydantic.BaseModel]:
    """
    Build `Shape` again from the outside, under a name and doc of choice.
    """

    return pydantic.create_model(
        name,
        __doc__=Shape.__doc__ if doc is None else doc,
        required=(str, ...),
        optional=(int, 3),
    )


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> SchemaManager:
    """
    A manager writing into `tmp_path` instead of an app's migrations.
    """

    monkeypatch.setattr(SchemaManager, "basedir", property(lambda _self: tmp_path))
    return SchemaManager("testapp", "terminal", "metadata")


def test_a_field_gets_an_empty_file_of_its_own(manager: SchemaManager, tmp_path: pathlib.Path) -> None:
    """
    One file per model and field, created on the first look.
    """

    assert manager.get_filename() == "_schema_terminal__metadata.json"
    assert manager.versions == {}
    assert (tmp_path / "_schema_terminal__metadata.json").read_text() == "{}"


def test_a_version_is_saved_once(manager: SchemaManager) -> None:
    """
    A saved version is found by its hash, and not written again.
    """

    model_hash, _ = SchemaManager.generate_model_hash(Shape)
    manager.save_version(Shape)
    saved = manager.file.read_text()

    assert manager.version_exists(model_hash)
    assert SchemaManager("testapp", "terminal", "metadata").version_exists(model_hash)

    manager.ensure_version(model_hash, Shape)

    assert manager.file.read_text() == saved


def test_the_hash_covers_the_shape_and_nothing_else() -> None:
    """
    The same shape hashes the same, however named and however documented.

    Where exactly the fingerprint draws that line is
    `test_fingerprint.py`'s subject; this is the one promise
    `generate_model_hash` itself makes.
    """

    original, _ = SchemaManager.generate_model_hash(Shape)

    assert SchemaManager.generate_model_hash(twin())[0] == original
    assert SchemaManager.generate_model_hash(twin(name="Renamed", doc="Something else."))[0] == original


def test_what_lands_on_disk(manager: SchemaManager) -> None:
    """
    The stored schema is the normalized one, documentation and all gone.

    Nothing reads the file but `get_model`, and a data migration has no
    use for a docstring — so it is not written. `required` arrives sorted
    for the same reason it is sorted before hashing.
    """

    manager.save_version(Shape)
    stored = next(iter(manager.versions.values()))

    assert stored == {
        "properties": {"optional": {"default": 3, "type": "integer"}, "required": {"type": "string"}},
        "required": ["required"],
        "type": "object",
    }


def test_get_model_rebuilds_the_shape(manager: SchemaManager) -> None:
    """
    A recorded schema comes back as a working model, named after the field.

    The name is handed back by `get_model`, since the schema no longer
    carries one — without it a row that fails to validate would be
    reported against an anonymous `DynamicModel`.
    """

    model_hash, _ = SchemaManager.generate_model_hash(Shape)
    manager.save_version(Shape)

    rebuilt = manager.get_model(model_hash)

    assert set(rebuilt.model_fields) == {"required", "optional"}
    assert rebuilt.model_fields["required"].is_required()
    assert rebuilt(required="x").optional == 3
    assert rebuilt.__name__ == "terminal.metadata"


def alter_operations() -> list[AlterPydantic]:
    """
    Every `AlterPydantic` the test app's migrations declare.
    """

    return [
        operation
        for name in MIGRATIONS
        for operation in importlib.import_module(f"tests.testapp.migrations.{name}").Migration.operations
        if isinstance(operation, AlterPydantic)
    ]


def committed_schemas() -> dict[str, Any]:
    """
    Every schema the test app has on disk, by hash.
    """

    basedir = pathlib.Path(__file__).parents[1] / "testapp" / "migrations"
    versions: dict[str, Any] = {}
    for name in SCHEMA_FILES:
        versions |= json.loads((basedir / name).read_text())
    return versions


def test_the_committed_chain_agrees_with_the_history() -> None:
    """
    Every hash a migration names is on disk, and stands for a known shape.

    This is the test that catches a pydantic release changing
    `model_json_schema()`: regenerate the schema files and the hashes in
    the migrations rather than chasing a `KeyError` out of a data
    migration.
    """

    stored = committed_schemas()
    operations = alter_operations()
    hashes = [SchemaManager.generate_model_hash(version)[0] for version in VERSIONS]

    declared = {
        model_hash
        for operation in operations
        for model_hash in (operation.schema_hash, operation.previous_schema_hash)
        if model_hash is not None
    }
    assert declared <= set(stored)

    assert [
        version.__name__ for version in VERSIONS if SchemaManager.generate_model_hash(version)[0] not in stored
    ] == []

    steps = [
        (operation.previous_schema_hash, operation.schema_hash)
        for operation in operations
        if operation.model_name == "terminal"
    ]
    assert steps == [(None, hashes[0]), *itertools.pairwise(hashes)]


@pytest.mark.django_db
def test_the_models_agree_with_the_last_migration() -> None:
    """
    `makemigrations` finds nothing left to generate.
    """

    call_command("makemigrations", "testapp", "--check", "--dry-run", verbosity=0)
