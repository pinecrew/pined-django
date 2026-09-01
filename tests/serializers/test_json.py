"""
`JSONEncoder` — the one django ships, with the escaping turned off.
"""

import datetime
import decimal
import json
import uuid

import pydantic
import pytest
from django.db import connection

from pined.django.serializers.json import JSONEncoder

CYRILLIC = {"город": "Кострома"}


class Model(pydantic.BaseModel):
    """
    Something with a `model_dump` and a value plain json cannot hold.
    """

    when: datetime.date = datetime.date(2020, 1, 1)
    where: str = "Кострома"


def test_non_ascii_survives_json_dumps() -> None:
    """
    The whole point of the encoder, at the only call shape that occurs.

    `json.dumps` fills in every one of its own parameters before handing
    them to `cls`, `ensure_ascii=True` among them. So an `ensure_ascii`
    default on the encoder would be overwritten by every caller that never
    mentioned it — which is all of them — and the class would escape
    everything while claiming the opposite.
    """

    assert json.dumps(CYRILLIC, cls=JSONEncoder) == '{"город": "Кострома"}'
    assert JSONEncoder().encode(CYRILLIC) == '{"город": "Кострома"}'


def test_asking_for_escaping_does_not_get_it() -> None:
    """
    There is no telling a deliberate `ensure_ascii` from `dumps`'s own.

    Both arrive as the same keyword, so the encoder answers to neither.
    Escaping is `json.dumps` without this `cls`.
    """

    assert json.dumps(CYRILLIC, cls=JSONEncoder, ensure_ascii=True) == '{"город": "Кострома"}'


def test_the_other_parameters_still_arrive() -> None:
    """
    Only `ensure_ascii` is taken over; the rest are the parent's own.
    """

    assert json.dumps(CYRILLIC, cls=JSONEncoder, indent=2).startswith('{\n  "город"')
    assert json.dumps({"b": 1, "a": 2}, cls=JSONEncoder, sort_keys=True) == '{"a": 2, "b": 1}'
    assert json.dumps({"a": 1}, cls=JSONEncoder, separators=(",", ":")) == '{"a":1}'


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(Model(), '{"when": "2020-01-01", "where": "Кострома"}', id="a-pydantic-model"),
        pytest.param(datetime.date(2020, 1, 1), '"2020-01-01"', id="what-django-already-handled"),
        pytest.param(decimal.Decimal("1.5"), '"1.5"', id="a-decimal"),
        pytest.param(uuid.UUID(int=0), '"00000000-0000-0000-0000-000000000000"', id="a-uuid"),
    ],
)
def test_what_it_can_encode(value: object, expected: str) -> None:
    """
    A pydantic model goes through `model_dump`; the rest is django's.
    """

    assert json.dumps(value, cls=JSONEncoder) == expected


def test_what_it_still_refuses() -> None:
    """
    Nothing was made lenient — an unknown type is still an error.
    """

    with pytest.raises(TypeError):
        json.dumps(object(), cls=JSONEncoder)


def test_the_column_gets_it_unescaped() -> None:
    """
    How a `PydanticField` value actually reaches the database.

    `adapt_json_value` is `json.dumps(value, cls=encoder)` — the call shape
    the encoder exists for, and the one it used to lose.
    """

    assert connection.ops.adapt_json_value(CYRILLIC, JSONEncoder) == '{"город": "Кострома"}'
