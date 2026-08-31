"""
Every data migration in the test app's chain, forwards and back.

All of them work the same way: plant rows at one state, apply the next
migration, look at what the rows hold now. So what separates them is data,
not code — one scenario per `AlterPydantic` feature, and one test that
walks them.

Each row is compared whole. That covers strictly more than picking at one
key: it also catches a key that should have been dropped, and one that
should never have appeared.
"""

from dataclasses import dataclass
from typing import Any

import pytest
from django.db import connection
from django_test_migrations.migrator import Migrator

from pined.django.db.migrations import F
from pined.django.db.pydantic_field.migrations import _process_database
from pined.django.db.pydantic_field.schema import SchemaManager
from tests.db.conftest import RawReader, RawWriter
from tests.testapp.schema_history import MetadataV3

V1 = {"os_version": "13", "update_attempts": 2}
V2 = {"os_version": "13", "update_attempts": 0, "max_backup": 20, "region": "eu"}
V3 = {
    "android_version": "unknown",
    "also_version": "unknown",
    "current_software_version": "",
    "update_attempts": 0,
    "max_backup": 10,
    "region": "eu",
}
V4 = V3 | {"log_retention": 7}
V5 = {
    "android_version": "unknown",
    "current_software_version": "",
    "update_attempts": 0,
    "max_backup": 10,
    "log_retention": 7,
    "region": "unset",
}

FOLDABLE = V4 | {"also_version": "15", "current_software_version": "1.2.3", "update_attempts": 4}
"""A V4 row whose `also_version` is the only place a version is written."""
FOLDED = V5 | {"android_version": "15", "current_software_version": "1.2.3", "update_attempts": 4, "region": "eu"}
"""The same row once V5 has taken `also_version` away."""

UNSET = object()
"""Leave the column as the migration found it, rather than planting a value."""


@dataclass(frozen=True)
class Row:
    """
    One row, from the columns it is created with to the value it ends up
    holding.

    Attributes:
        columns: Handed to `objects.create`.
        before: Planted in the `PydanticField`'s column. `None` plants SQL
            NULL; `UNSET` plants nothing at all, which is the only option
            while the column does not exist yet.
        after: What the column should hold once the migration has run.
    """

    columns: dict[str, Any]
    before: Any
    after: Any


@dataclass(frozen=True)
class Scenario:
    """
    One migration, and the rows it is expected to rewrite.

    Attributes:
        id: Shown by pytest as the case's name.
        start: Migration the rows are planted at.
        target: Migration under test. May be earlier than `start`, which is
            how a rollback is spelled.
        model: Model whose table is being rewritten.
        rows: The rows, in the order they are created.
    """

    id: str
    start: str
    target: str
    model: str
    rows: tuple[Row, ...]

    @property
    def table(self) -> str:
        """
        The model's table name.
        """

        return f"testapp_{self.model.lower()}"


SCENARIOS = (
    Scenario(
        # 0002 adds `max_backup`, which has a default, and `region`, which is
        # required — so every row has to be handed one.
        id="defaults",
        start="0001_initial",
        target="0002_metadata_defaults",
        model="Terminal",
        rows=(
            # Neither field is in the row, so both defaults land.
            Row(columns={}, before=V1, after=V1 | {"max_backup": 20, "region": "eu"}),
            # `region` stays: it is required, so its pydantic default can never
            # look like stored data.
            Row(columns={}, before=V1 | {"region": "us"}, after=V1 | {"max_backup": 20, "region": "us"}),
            # `max_backup` stays: 99 is not its default, so it reads as user data.
            Row(columns={}, before=V1 | {"max_backup": 99}, after=V1 | {"max_backup": 99, "region": "eu"}),
        ),
    ),
    Scenario(
        # Rolling back revalidates against the older schema, which has no room
        # for the keys 0002 added.
        id="defaults-rolled-back",
        start="0002_metadata_defaults",
        target="0001_initial",
        model="Terminal",
        rows=(Row(columns={}, before=V1 | {"max_backup": 20, "region": "eu"}, after=V1),),
    ),
    Scenario(
        # 0003 is the whole expression suite: `F` off a column and through a
        # JSONField, `R` renaming, `P` reading what `R` produced.
        id="expressions",
        start="0002_metadata_defaults",
        target="0003_metadata_expressions",
        model="Terminal",
        rows=(
            Row(
                columns={"current_software_version": "1.2.3", "extra": {"software": {"update_attempts": 7}}},
                before=V2,
                after={
                    "android_version": "13",  # R took it off `os_version`
                    "also_version": "13",  # P read it back off `android_version`
                    "current_software_version": "1.2.3",  # F off the parent column
                    "update_attempts": 7,  # F through the `extra` JSONField
                    "max_backup": 20,
                    "region": "eu",
                },
            ),
            Row(
                # `update_attempts` is 3, which is not its default, so the same
                # `F` that filled the row above leaves this one alone.
                columns={"current_software_version": "9.9.9", "extra": None},
                before=V2 | {"os_version": "12", "update_attempts": 3, "region": "us"},
                after={
                    "android_version": "12",
                    "also_version": "12",
                    "current_software_version": "9.9.9",
                    "update_attempts": 3,
                    "max_backup": 20,
                    "region": "us",
                },
            ),
            Row(
                # The dotted path is not there, so `F`'s own default stands in.
                columns={"current_software_version": "4.4.4", "extra": {"nothing": "here"}},
                before=V2,
                after={
                    "android_version": "13",
                    "also_version": "13",
                    "current_software_version": "4.4.4",
                    "update_attempts": 0,
                    "max_backup": 20,
                    "region": "eu",
                },
            ),
            # A row holding NULL is passed over rather than validated.
            Row(columns={"current_software_version": "0.0.1"}, before=None, after=None),
        ),
    ),
    Scenario(
        # `backwards_defaults` renames the field back on the way out.
        id="expressions-rolled-back",
        start="0003_metadata_expressions",
        target="0002_metadata_defaults",
        model="Terminal",
        rows=(
            Row(
                columns={},
                before=V3 | {"android_version": "14", "also_version": "14", "update_attempts": 5, "max_backup": 20},
                after={"os_version": "14", "update_attempts": 5, "max_backup": 20, "region": "eu"},
            ),
        ),
    ),
    Scenario(
        # 0004 lists `max_backup` in `override_fields` and nothing else.
        id="override",
        start="0003_metadata_expressions",
        target="0004_metadata_override",
        model="Terminal",
        rows=(
            Row(
                columns={},
                before=V3 | {"max_backup": 99, "region": "us"},
                after=V3
                | {
                    "max_backup": 50,  # listed, so it is forced over user data
                    "region": "us",  # not listed, so the row keeps its own
                    "log_retention": 14,  # never in the row, so the default lands
                },
            ),
        ),
    ),
    Scenario(
        # 0005 folds `also_version` into `android_version` before the schema
        # drops it — which neither a default nor a rename can express.
        id="transform",
        start="0004_metadata_override",
        target="0005_metadata_transform",
        model="Terminal",
        rows=(
            Row(columns={}, before=FOLDABLE, after=FOLDED),
            # The fold is conditional, and this row already has a version.
            Row(
                columns={},
                before=FOLDABLE | {"android_version": "13"},
                after=FOLDED | {"android_version": "13"},
            ),
        ),
    ),
    Scenario(
        id="transform-rolled-back",
        start="0005_metadata_transform",
        target="0004_metadata_override",
        model="Terminal",
        rows=(Row(columns={}, before=FOLDED, after=FOLDABLE | {"android_version": "15", "also_version": "15"}),),
    ),
    Scenario(
        # 0006 only adds the column, which is filled from the pydantic model's
        # own default.
        id="field-added",
        start="0005_metadata_transform",
        target="0006_device_metadata",
        model="Device",
        rows=(Row(columns={"name": "fresh"}, before=UNSET, after=V5),),
    ),
    Scenario(
        # 0007 revalidates with `previous_schema_hash` unset, which forces every
        # default in as if `override_fields="*"` had been passed. Under 0004's
        # rules `region` would have survived — see the `override` scenario.
        id="field-created",
        start="0006_device_metadata",
        target="0007_device_revalidate",
        model="Device",
        rows=(
            Row(
                columns={"name": "planted"},
                before=V5 | {"region": "keepme", "max_backup": 99},
                after=V5 | {"region": "forced", "max_backup": 123},
            ),
        ),
    ),
)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.id)
def test_a_data_migration_rewrites_every_row(
    migrator: Migrator,
    scenario: Scenario,
    read_raw: RawReader,
    write_raw: RawWriter,
) -> None:
    """
    Every row comes out holding what its scenario says it should.
    """

    state = migrator.apply_initial_migration(("testapp", scenario.start))
    model = state.apps.get_model("testapp", scenario.model)

    pks = [model.objects.create(**row.columns).pk for row in scenario.rows]
    for pk, row in zip(pks, scenario.rows, strict=True):
        if row.before is not UNSET:
            write_raw(scenario.table, pk, row.before)

    migrator.apply_tested_migration(("testapp", scenario.target))

    assert [read_raw(scenario.table, pk) for pk in pks] == [row.after for row in scenario.rows]


def test_two_lookups_can_share_one_column(migrator: Migrator, read_raw: RawReader, write_raw: RawWriter) -> None:
    """
    Two `F`s naming the same column select it once.
    """

    state = migrator.apply_initial_migration(("testapp", "0002_metadata_defaults"))
    model = state.apps.get_model("testapp", "Terminal")
    pk = model.objects.create(current_software_version="1.2.3").pk
    write_raw("testapp_terminal", pk, V2)

    _process_database(
        model,
        model._meta.get_field("metadata"),
        SchemaManager.generate_model_hash(MetadataV3)[0],
        connection,
        {
            "android_version": F("current_software_version"),
            "current_software_version": F("current_software_version"),
        },
        None,
        ["*"],
    )

    assert read_raw("testapp_terminal", pk) == V3 | {
        "android_version": "1.2.3",
        "current_software_version": "1.2.3",
        "max_backup": 20,
    }
