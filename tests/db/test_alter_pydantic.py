"""
`AlterPydantic`'s own surface, and the ways it refuses to run.
"""

from typing import Any

import pytest
from django.db import connection
from django_test_migrations.migrator import Migrator

from pined.django.db.migrations import AlterPydantic, F, R


def test_the_operation_describes_itself() -> None:
    """
    What `makemigrations` and `migrate` read off the operation.

    The model name is normalised on the way in, since everything
    downstream — the schema file's name included — is keyed by the
    lower-cased one.
    """

    operation = AlterPydantic("Terminal", "metadata", "abc")

    assert operation.model_name == "terminal"
    assert operation.describe() == "Revalidate data in terminal.metadata"
    assert operation.migration_name_fragment == "revalidate_terminal_metadata"
    assert AlterPydantic.__module__ == "pined.django.db.migrations"
    assert (AlterPydantic.reversible, AlterPydantic.reduces_to_sql, AlterPydantic.atomic) == (True, False, True)


def test_deconstruct_keeps_what_was_set_and_nothing_else() -> None:
    """
    Empty optionals stay out of the generated migration.
    """

    def transform(data: Any) -> Any:
        return data

    bare = AlterPydantic("Terminal", "metadata", "abc").deconstruct()

    assert bare == ("AlterPydantic", [], {"model_name": "terminal", "name": "metadata", "schema_hash": "abc"})

    _, _, kwargs = AlterPydantic(
        "Terminal",
        "metadata",
        "abc",
        previous_schema_hash="def",
        forwards_defaults={"a": F("b")},
        backwards_defaults={"c": R("d")},
        forwards_transform=transform,
        override_fields="*",
    ).deconstruct()

    assert kwargs["previous_schema_hash"] == "def"
    assert kwargs["forwards_defaults"]["a"].field_name == "b"
    assert kwargs["backwards_defaults"]["c"].old_name == "d"
    assert kwargs["forwards_transform"] is transform
    assert kwargs["override_fields"] == "*"
    assert "backwards_transform" not in kwargs


def test_a_row_that_cannot_validate_names_itself(migrator: Migrator, write_raw: Any) -> None:
    """
    An unvalidatable row fails the migration, pointing at its own pk.
    """

    state = migrator.apply_initial_migration(("testapp", "0002_metadata_defaults"))
    model = state.apps.get_model("testapp", "Terminal")
    pk = model.objects.create().pk
    write_raw(
        "testapp_terminal",
        pk,
        {"os_version": "13", "update_attempts": "not-an-int", "max_backup": 20, "region": "eu"},
    )

    with pytest.raises(RuntimeError, match=rf"Failed to migrate Terminal\(pk={pk}\)\.metadata"):
        migrator.apply_tested_migration(("testapp", "0003_metadata_expressions"))

    # The row would fail again on the way the migrator unwinds itself.
    write_raw("testapp_terminal", pk, None)


def test_a_plain_json_field_is_refused(migrator: Migrator) -> None:
    """
    Nothing stops you pointing the operation at any field — this does.
    """

    state = migrator.apply_initial_migration(("testapp", "0005_metadata_transform"))
    operation = AlterPydantic("Terminal", "extra", "unused")

    with (
        connection.schema_editor() as editor,
        pytest.raises(TypeError, match=r"Terminal\.extra is not a PydanticField"),
    ):
        operation.database_process("testapp", editor, state, "unused", {}, None)
