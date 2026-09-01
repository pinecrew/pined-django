"""
The merge logic behind `AlterPydantic`, without a database in the way.

`_update_instance` decides, field by field, whether a row's value counts as
user data. `_get_field_default` and `unnest` are what it decides with.
"""

import datetime
from typing import Any

import pydantic
import pytest
from django.db import models

from pined.django.db.migrations import F, P, R
from pined.django.db.pydantic_field.migrations import (
    UpdateContext,
    _get_field_default,
    _revalidate_row,
    _update_instance,
    unnest,
)
from tests.testapp.models import Terminal

NOT_PROVIDED = models.NOT_PROVIDED


class Shape(pydantic.BaseModel):
    """
    A model with one of each kind of default.
    """

    required: str
    plain: int = 10
    made: list[str] = pydantic.Field(default_factory=list)
    stamped: datetime.date = datetime.date(2020, 1, 1)


def make_context(**overrides: Any) -> UpdateContext:
    """
    An `UpdateContext` with everything empty but what is asked for.
    """

    base: dict[str, Any] = {
        "parent": Terminal,
        "model": Shape,
        "defaults": {},
        "transform": None,
        "select_sql": "",
        "update_sql": "",
        "err_template": "{pk} {exception}",
        "f_columns": {},
        "f_fields": {},
        "p_fields": {},
        "r_fields": {},
        "batch_size": 1000,
        "to_override": set(),
        "complex_keys": set(),
        "default_values": {},
    }
    return UpdateContext(**(base | overrides))


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        # A required field's "default" can never match stored data, so such a
        # field is only ever backfilled — never compared against.
        pytest.param("required", NOT_PROVIDED, id="a-required-field"),
        pytest.param("nope", NOT_PROVIDED, id="a-field-the-model-does-not-have"),
        pytest.param("plain", 10, id="a-plain-default"),
        pytest.param("made", [], id="a-default-factory"),
        # Defaults are compared against stored data, so they arrive in its shape.
        pytest.param("stamped", "2020-01-01", id="a-default-that-needs-serializing"),
    ],
)
def test_get_field_default(field: str, expected: Any) -> None:
    """
    The value `_update_instance` compares a row against.
    """

    assert _get_field_default(Shape, field) == expected


@pytest.mark.parametrize(
    ("data", "to_override", "expected"),
    [
        pytest.param({}, set(), 99, id="absent-takes-the-default"),
        pytest.param({"plain": 10}, set(), 99, id="untouched-takes-the-default"),
        pytest.param({"plain": 42}, set(), 42, id="user-data-survives"),
        pytest.param({"plain": 42}, {"plain"}, 99, id="named-in-override_fields"),
        pytest.param({"plain": 42}, {"*"}, 99, id="star-in-override_fields"),
        pytest.param({"plain": 42}, {"other"}, 42, id="someone-else-overridden"),
    ],
)
def test_should_set(data: dict[str, Any], to_override: set[str], expected: int) -> None:
    """
    Whether a plain default reaches a row.
    """

    context = make_context(defaults={"plain": 99}, to_override=to_override, default_values={"plain": 10})

    assert _update_instance(context, dict(data), [])["plain"] == expected


@pytest.mark.parametrize(
    ("context", "data", "other", "expected"),
    [
        pytest.param(
            make_context(
                defaults={"new": R("old")},
                complex_keys={"new"},
                r_fields={"new": "old"},
                default_values={"new": NOT_PROVIDED},
            ),
            {"old": "v"},
            [],
            {"new": "v"},
            id="r-renames-and-takes-the-old-key-with-it",
        ),
        pytest.param(
            make_context(
                defaults={"copy": P("source")},
                complex_keys={"copy"},
                p_fields={"copy": "source"},
                default_values={"copy": NOT_PROVIDED},
            ),
            {"source": "v"},
            [],
            {"source": "v", "copy": "v"},
            id="p-copies-and-leaves-the-source-alone",
        ),
        pytest.param(
            make_context(
                defaults={"new": R("old"), "copy": P("new")},
                complex_keys={"new", "copy"},
                r_fields={"new": "old"},
                p_fields={"copy": "new"},
                default_values={"new": NOT_PROVIDED, "copy": NOT_PROVIDED},
            ),
            {"old": "v"},
            [],
            {"new": "v", "copy": "v"},
            id="p-resolves-after-r-so-it-can-chase-a-rename",
        ),
        pytest.param(
            make_context(
                defaults={"new": R("old")},
                complex_keys={"new"},
                r_fields={"new": "old"},
                default_values={"new": NOT_PROVIDED},
            ),
            {"kept": 1},
            [],
            {"kept": 1},
            id="a-missing-source-changes-nothing",
        ),
        pytest.param(
            # Plain defaults and `F` values are merged in one step, with the
            # plain ones applied last.
            make_context(
                defaults={"plain": 99, "same": F("current_software_version")},
                complex_keys={"same"},
                f_columns={"current_software_version": "current_software_version"},
                f_fields={"same": ("current_software_version", None)},
                default_values={"plain": 10, "same": NOT_PROVIDED},
            ),
            {},
            ["1.2.3"],
            {"plain": 99, "same": "1.2.3"},
            id="a-plain-default-wins-over-an-f-naming-the-same-key",
        ),
    ],
)
def test_the_expressions_resolve_in_order(
    context: UpdateContext, data: dict[str, Any], other: list[Any], expected: dict[str, Any]
) -> None:
    """
    `F`, then `R`, then `P` — and none of them touches user data.
    """

    assert _update_instance(context, dict(data), other) == expected


@pytest.mark.parametrize(
    ("getter", "gathered", "expected"),
    [
        pytest.param(("extra", None), {"extra": {"a": 1}}, {"a": 1}, id="whole-column"),
        pytest.param(("extra.a", None), {"extra": {"a": 1}}, 1, id="one-step"),
        pytest.param(("extra.a.b", None), {"extra": {"a": {"b": 2}}}, 2, id="two-steps"),
        pytest.param(("extra.a.0", None), {"extra": {"a": ["first"]}}, "first", id="list-index"),
        pytest.param(("extra.missing", "fallback"), {"extra": {}}, "fallback", id="absent-path"),
        pytest.param(("extra.a", 0), {"extra": None}, 0, id="null-column"),
        # SQLite's doing: a raw cursor hands a `JSONField` back as text rather
        # than decoded json.
        pytest.param(("extra.a", None), {"extra": '{"a": 1}'}, 1, id="json-as-a-string"),
    ],
)
def test_unnest(getter: tuple[str, Any], gathered: dict[str, Any], expected: Any) -> None:
    """
    Resolving an `F`'s dotted path against a row's gathered columns.
    """

    assert unnest(getter, gathered, Terminal) == expected


def test_a_row_is_merged_then_transformed_then_validated() -> None:
    """
    A transform runs last, and only a mapping is merged into at all.
    """

    seen: dict[str, Any] = {}

    def transform(data: Any) -> Any:
        seen.update(data)
        return data | {"required": "from-the-transform"}

    context = make_context(defaults={"plain": 99}, default_values={"plain": 10}, transform=transform)
    dumped, pk = _revalidate_row(context, 7, {"required": "original"}, [])

    assert seen == {"required": "original", "plain": 99}
    assert pk == 7
    assert '"required": "from-the-transform"' in dumped

    # A `PydanticField` over a `RootModel` stores a json array, and there is
    # nothing in there for `F`/`P`/`R` to name.
    class Listed(pydantic.RootModel[list[int]]):
        pass

    listed = make_context(model=Listed, defaults={"plain": 99}, default_values={"plain": 10})

    assert _revalidate_row(listed, 1, [3, 2, 1], [])[0] == "[3, 2, 1]"
