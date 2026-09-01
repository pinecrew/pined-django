"""
`PydanticField` itself — the reads, the writes, and the migration shape.
"""

import datetime
from typing import Any, cast

import pydantic
import pytest
from django.core.exceptions import ValidationError
from django.db import connection, models

from pined.django.db.models import PydanticField
from pined.django.db.pydantic_field.schema import SchemaManager
from pined.django.serializers.json import JSONEncoder
from tests.testapp.models import Terminal
from tests.testapp.schemas import Metadata


class Filled(pydantic.BaseModel):
    """
    A model that needs no arguments.
    """

    value: int = 1
    when: datetime.date = datetime.date(2020, 1, 1)


class Demanding(pydantic.BaseModel):
    """
    A model that will not be built without help.
    """

    value: int


FIELD = PydanticField(Filled)
NULLABLE = PydanticField(Filled, null=True)
DUMPED = '{"value": 7, "when": "2020-01-01"}'
"""What `Filled(value=7)` looks like on its way into the column."""


def row(value: Any) -> Any:
    """
    A stand-in for a model instance holding `value`.
    """

    return type("Row", (), {"metadata": value})()


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        pytest.param(PydanticField(Filled), Filled, id="a-model-that-instantiates-bare"),
        pytest.param(PydanticField(Demanding), models.NOT_PROVIDED, id="a-model-that-does-not"),
        pytest.param(PydanticField(Filled, null=True, default=None), None, id="a-default-named-outright"),
    ],
)
def test_the_default_is_inferred_from_the_model(field: PydanticField, expected: Any) -> None:
    """
    A model that takes no arguments becomes the field's default factory.

    A model that needs some leaves the field as default-less as a bare
    `JSONField`, and an explicit default is never second-guessed.
    """

    assert field.default is expected
    assert field.has_default() is (expected is not models.NOT_PROVIDED)


def test_what_the_field_settles_on_at_construction() -> None:
    """
    The encoder, the default it built, and the schema it reports.
    """

    assert FIELD.encoder is JSONEncoder
    assert FIELD.get_default().value == 1
    assert FIELD.current_schema == SchemaManager.generate_model_hash(Filled)[0]


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        pytest.param('{"value": 5, "when": "2021-02-03"}', Filled(value=5, when=datetime.date(2021, 2, 3)), id="json"),
        # A `select_related` that found nothing hands back None even where the
        # column is not nullable, so this has nothing to do with `null`.
        pytest.param(None, None, id="nothing"),
    ],
)
def test_from_db_value_validates(stored: str | None, expected: Filled | None) -> None:
    """
    What comes off the database comes out as a model.
    """

    assert FIELD.from_db_value(stored, None, connection) == expected


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        pytest.param(FIELD, Filled(value=7), DUMPED, id="a-model"),
        pytest.param(FIELD, models.Value(Filled(value=7)), DUMPED, id="wrapped-in-value"),
        pytest.param(FIELD, {"anything": True}, '{"anything": true}', id="a-plain-dict"),
        pytest.param(NULLABLE, None, None, id="null"),
    ],
)
def test_get_db_prep_value_reduces_the_value(field: PydanticField, value: Any, expected: str | None) -> None:
    """
    A model reaches the column, wrapper or no wrapper.
    """

    assert field.get_db_prep_value(value, connection) == expected


@pytest.mark.django_db
def test_a_query_expression_never_reaches_the_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    django compiles expressions to SQL rather than preparing them.

    `Value.as_sql` hands `get_db_prep_value` its inner value, and anything
    else — an `F()` resolved to a column, a `Case` built by `bulk_update` —
    is rendered as SQL and never prepared at all. The field used to dig
    through expressions on the assumption that they arrive; they do not,
    and guessing which branch of a `Case` to store was never going to be
    right.
    """

    seen: list[Any] = []
    original = PydanticField.get_db_prep_value

    def record(self: PydanticField, value: Any, *args: Any, **kwargs: Any) -> Any:
        seen.append(value)
        return original(self, value, *args, **kwargs)

    monkeypatch.setattr(PydanticField, "get_db_prep_value", record)

    field = cast("models.Field", Terminal._meta.get_field("metadata"))
    terminals = [Terminal.objects.create(metadata=Metadata(region=str(i))) for i in range(2)]
    Terminal.objects.update(metadata=models.Value(Metadata(region="updated"), output_field=field))
    for terminal in terminals:
        terminal.metadata = Metadata(region="bulk")
    Terminal.objects.bulk_update(terminals, ["metadata"])
    Terminal.objects.update(metadata=models.F("extra"))

    assert seen
    assert all(isinstance(value, Metadata) for value in seen)


def test_to_python_wraps_the_pydantic_error() -> None:
    """
    A form or a fixture sees django's `ValidationError`, not pydantic's.
    """

    assert FIELD.to_python(None) is None

    with pytest.raises(ValidationError):
        FIELD.to_python('{"value": "not-a-number"}')


def test_the_field_survives_a_migration_round_trip() -> None:
    """
    The model goes out as the first positional argument, and the schema
    hash a migration set on the field follows a clone.
    """

    field = PydanticField(Filled, null=True, default=None)
    field._schema_hash = "abc"
    _, path, args, kwargs = field.deconstruct()

    assert path == "pined.django.db.models.PydanticField"
    assert args[0] is Filled

    rebuilt = PydanticField(*args, **kwargs)

    assert rebuilt.inner_model is Filled
    assert rebuilt.null
    assert field.clone()._schema_hash == "abc"


@pytest.mark.parametrize(
    ("obj", "expected"),
    [
        pytest.param(row(Filled(value=3)), {"value": 3, "when": datetime.date(2020, 1, 1)}, id="a-model"),
        # Some apps put a bare dict or list in there — easyaudit, for one.
        pytest.param(row({"raw": 1}), {"raw": 1}, id="a-dict"),
        pytest.param(row([1, 2]), [1, 2], id="a-list"),
        pytest.param(row(None), None, id="an-empty-column"),
    ],
)
def test_value_to_string(obj: Any, expected: Any) -> None:
    """
    Serialization for fixtures hands back plain data.
    """

    field = PydanticField(Filled, null=True, default=None)
    field.attname = field.name = "metadata"

    assert field.value_to_string(obj) == expected


@pytest.mark.django_db
def test_a_round_trip_through_the_database() -> None:
    """
    What was saved as a model comes back as one.
    """

    Terminal.objects.create(metadata=Metadata(android_version="15", region="eu"))
    stored = Terminal.objects.get()

    assert isinstance(stored.metadata, Metadata)
    assert (stored.metadata.android_version, stored.metadata.region) == ("15", "eu")
