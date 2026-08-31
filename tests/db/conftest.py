"""
Helpers for reading and writing a `PydanticField`'s column directly.

Every migration in `tests.testapp` references the *current*
`schemas.Metadata`, exactly like a migration django generates would —
which means the historical model in a migration state validates against
the newest shape, not the one that was current back then. Writing an
intermediate shape through the ORM happens to work (a plain `dict` falls
straight through to `JSONField`), but reading one back does not. So
assertions go through raw SQL.
"""

import json
from collections.abc import Callable
from typing import Any

import pytest
from django.db import connection

type RawReader = Callable[[str, int], Any]
type RawWriter = Callable[[str, int, Any], None]


@pytest.fixture
def read_raw() -> RawReader:
    """
    Return a reader for one row's raw `metadata` value.
    """

    def read(table: str, pk: int) -> Any:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT metadata FROM {table} WHERE id = %s", [pk])
            (value,) = cursor.fetchone()
        return json.loads(value) if isinstance(value, str) else value

    return read


@pytest.fixture
def write_raw() -> RawWriter:
    """
    Return a writer that plants a raw `metadata` value on one row.
    """

    def write(table: str, pk: int, value: Any) -> None:
        dumped = None if value is None else json.dumps(value)
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {table} SET metadata = %s WHERE id = %s", [dumped, pk])

    return write
