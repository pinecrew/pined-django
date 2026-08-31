"""
`PydanticAwareAutodetector` — the part that notices a schema changed.

Everything here runs on hand-built states with a dry-run questioner, so no
database is touched and no schema file is written.
"""

import pathlib
from typing import Any

import pytest
from django.db import models
from django.db.migrations import AddField, CreateModel
from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
from django.db.migrations.state import ModelState, ProjectState

from pined.django.db.migrations import AlterPydantic
from pined.django.db.models import PydanticField
from pined.django.db.pydantic_field.migrations import PydanticAwareAutodetector
from pined.django.db.pydantic_field.schema import SchemaManager
from tests.testapp.schemas import Metadata

CURRENT_HASH, _ = SchemaManager.generate_model_hash(Metadata)


def project(spec: dict[str, Any] | None) -> ProjectState:
    """
    A project holding one `Terminal`, or nothing at all.

    Args:
        spec: `with_field` and `schema_hash` for the model's state, or
            `None` for a project that has no models yet.
    """

    if spec is None:
        return ProjectState()

    fields: list[tuple[str, models.Field]] = [("id", models.AutoField(primary_key=True))]
    if spec.get("with_field", True):
        field = PydanticField(Metadata, null=True, default=None)
        field._schema_hash = spec.get("schema_hash")
        fields.append(("metadata", field))

    state = ProjectState()
    state.add_model(ModelState("otherapp", "Terminal", fields))
    return state


@pytest.mark.parametrize(
    ("before", "after", "questioner_kwargs", "expected"),
    [
        pytest.param(
            None,
            {},
            {},
            [(CreateModel, None, None), (AlterPydantic, CURRENT_HASH, None)],
            id="a-new-model-records-its-schema",
        ),
        pytest.param(
            {"schema_hash": "stale"},
            {"schema_hash": "stale"},
            {},
            [(AlterPydantic, CURRENT_HASH, "stale")],
            id="a-moved-hash-is-migrated-from-the-old-one",
        ),
        pytest.param(
            {"schema_hash": CURRENT_HASH},
            {"schema_hash": CURRENT_HASH},
            {},
            [],
            id="an-unchanged-hash-generates-nothing",
        ),
        pytest.param(
            {"with_field": False},
            {},
            {},
            [(AddField, None, None), (AlterPydantic, CURRENT_HASH, None)],
            id="a-field-added-later-has-no-previous-schema",
        ),
        pytest.param(
            {"schema_hash": "stale"},
            {"schema_hash": "stale"},
            {"specified_apps": {"someapp"}},
            [],
            id="another-app-named-leaves-this-one-alone",
        ),
    ],
)
def test_what_the_autodetector_notices(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    questioner_kwargs: dict[str, Any],
    expected: list[tuple[type, str | None, str | None]],
) -> None:
    """
    The operations generated, in order, with the hashes they carry.

    The order is the assertion the first case is about: an `AlterPydantic`
    has to land after the `CreateModel` that brought the field in.
    """

    questioner = NonInteractiveMigrationQuestioner(dry_run=True, **questioner_kwargs)
    detector = PydanticAwareAutodetector(project(before), project(after), questioner)

    changes = detector._detect_changes()
    operations = [operation for migration in changes.get("otherapp", []) for operation in migration.operations]

    assert [
        (type(operation), getattr(operation, "schema_hash", None), getattr(operation, "previous_schema_hash", None))
        for operation in operations
    ] == expected


def test_defaults_are_not_asked_for_without_anyone_to_ask() -> None:
    """
    Outside an interactive run there is nobody to answer the prompts.
    """

    detector = PydanticAwareAutodetector(
        ProjectState(), ProjectState(), NonInteractiveMigrationQuestioner(dry_run=True)
    )

    assert detector._ask_defaults(Metadata, "terminal", "metadata") == {}


def test_a_real_run_records_the_schema(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """
    Off dry-run, the schema is written next to the app's migrations.
    """

    monkeypatch.setattr(SchemaManager, "basedir", property(lambda _self: tmp_path))
    questioner = NonInteractiveMigrationQuestioner(dry_run=False)
    detector = PydanticAwareAutodetector(ProjectState(), project({}), questioner)

    detector._detect_changes()

    assert SchemaManager("otherapp", "terminal", "metadata").version_exists(CURRENT_HASH)
    assert (tmp_path / "_schema_terminal__metadata.json").exists()
