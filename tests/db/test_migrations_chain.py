"""
The whole migration chain, forwards and back.
"""

import pytest
from django_test_migrations.migrator import Migrator

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
LAST = MIGRATIONS[-1]


@pytest.mark.parametrize(
    ("start", "target"),
    [(None, LAST), *((LAST, target) for target in MIGRATIONS[:-1])],
    ids=lambda value: value or "nothing",
)
def test_the_chain_applies_and_rolls_back(migrator: Migrator, start: str | None, target: str) -> None:
    """
    The chain applies from scratch and unwinds to any point it passed.
    """

    migrator.apply_initial_migration(("testapp", start))
    state = migrator.apply_tested_migration(("testapp", target))

    assert state.apps.get_model("testapp", "Terminal") is not None
    assert state.apps.get_model("testapp", "Device") is not None


def test_rollback_past_field_creation(migrator: Migrator) -> None:
    """
    Rolling back past a `PydanticField`'s creation is a no-op.

    `AlterPydantic.database_backwards` gets `previous_schema_hash=None`
    there, and there is no schema left to validate against.
    """

    state = migrator.apply_initial_migration(("testapp", LAST))
    state.apps.get_model("testapp", "Device").objects.create(name="d")

    rolled_back = migrator.apply_tested_migration(("testapp", "0005_metadata_transform"))

    assert "metadata" not in rolled_back.models["testapp", "device"].fields


def test_state_carries_the_schema_hash(migrator: Migrator) -> None:
    """
    Applying a migration records which schema is now current.
    """

    hashes = [SchemaManager.generate_model_hash(version)[0] for version in VERSIONS]

    for migration, expected in zip(MIGRATIONS[:5], hashes, strict=True):
        state = migrator.apply_initial_migration(("testapp", migration))
        assert state.models["testapp", "terminal"].fields["metadata"]._schema_hash == expected
        migrator.reset()
