"""
`pydantic_expression`, and the `F`/`P`/`R` it builds.

The three of them are values that have to survive a round trip through a
migration file, which is what most of this is about.
"""

import dataclasses

import pytest
from django.db.migrations import Migration
from django.db.migrations.writer import MigrationWriter

from pined.django.db.migrations import AlterPydantic, F, P, R
from pined.django.db.pydantic_field.migrations import pydantic_expression


@pytest.mark.parametrize("cls", [F, P, R], ids=["F", "P", "R"])
def test_the_shape_of_an_expression(cls: type) -> None:
    """
    Frozen, slotted, and named by the public path.

    Frozen because a migration's arguments have no business changing under
    it, slotted so a typo becomes an error instead of a silent no-op, and
    `__module__` rewritten so generated migrations import them from
    `pined.django.db.migrations` rather than from the private module.
    """

    instance = cls("x")
    only_field = dataclasses.fields(cls)[0].name

    assert cls.__module__ == "pined.django.db.migrations"
    assert cls.__slots__
    assert not hasattr(instance, "__dict__")

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, only_field, "y")


def test_decorator_takes_a_path() -> None:
    """
    The bare and the called form both work, and `path` is honoured.
    """

    @pydantic_expression(path="somewhere.else")
    class Custom:
        value: str

    assert Custom.__module__ == "somewhere.else"
    assert Custom("v").value == "v"


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (F("x"), "pined.django.db.migrations.F('x')"),
        (F("a.b", 1), "pined.django.db.migrations.F('a.b', default_value=1)"),
        (F("a.b", None), "pined.django.db.migrations.F('a.b')"),
        (P("y"), "pined.django.db.migrations.P('y')"),
        (R("z"), "pined.django.db.migrations.R('z')"),
    ],
)
def test_serialization(expression: object, expected: str) -> None:
    """
    Each expression serializes to a call django can write out.

    A field holding its default is left off, so `F("x")` does not come
    back as `F('x', None)`, and one that is passed goes out by name — a
    position would rebind if the signature ever grew an argument in the
    middle.
    """

    serialized, imports = MigrationWriter.serialize(expression)

    assert serialized == expected
    assert imports == {"import pined.django.db.migrations"}


def test_a_migration_holding_expressions_round_trips() -> None:
    """
    An `AlterPydantic` full of expressions can be written and re-read.

    Django has no serializer for dataclasses, so without the `deconstruct`
    that `pydantic_expression` attaches, `squashmigrations` and every other
    rewrite would refuse the migration outright.
    """

    operation = AlterPydantic(
        "Terminal",
        "metadata",
        "abc",
        previous_schema_hash="def",
        forwards_defaults={"a": F("b"), "c": F("d.e", 0), "f": R("g"), "h": P("i")},
    )
    migration = type("Migration", (Migration,), {"operations": [operation]})("0001_test", "testapp")

    namespace: dict[str, object] = {}
    exec(compile(MigrationWriter(migration).as_string(), "<migration>", "exec"), namespace)

    defaults = namespace["Migration"].operations[0].forwards_defaults
    assert defaults["a"].field_name == "b"
    assert (defaults["c"].field_name, defaults["c"].default_value) == ("d.e", 0)
    assert defaults["f"].old_name == "g"
    assert defaults["h"].field_name == "i"


def test_a_default_in_the_middle_can_be_skipped() -> None:
    """
    Naming the optional fields is what lets one of them be left off.

    Positionally, writing the second option means writing the first one
    out as well — and a migration that spells out a default is one that
    quietly disagrees with the code once that default changes.
    """

    @pydantic_expression(path="somewhere.else")
    class Custom:
        value: str
        first: bool = False
        second: int = 0

    serialized, _ = MigrationWriter.serialize(Custom("v", second=3))

    assert serialized == "somewhere.else.Custom('v', second=3)"
