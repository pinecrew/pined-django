"""
`DropUnset`, `DjangoModel` and the alias generator underneath them.
"""

from typing import ClassVar

import pydantic

from pined.django.settings import DjangoModel, DropUnset
from pined.django.settings.utils import alias_generator


class Block(DjangoModel):
    """
    A block with one field of each disposition.
    """

    set_value: str | None = "here"
    unset_value: str | None = None


class KeepsOne(DjangoModel):
    """
    A block where one `None` is a value in its own right.
    """

    KEEP_NONE: ClassVar[frozenset[str]] = frozenset({"kept"})

    kept: str | None = None
    dropped: str | None = None


class KeepsAnother(KeepsOne):
    """
    A subclass naming a different field.
    """

    KEEP_NONE: ClassVar[frozenset[str]] = frozenset({"dropped"})


def test_a_block_dumps_upper_cased_and_without_the_unset() -> None:
    """
    Django is configured by constants, and an unset field is absent.

    A setting that is present but `None` is not the same as an absent one:
    django and its libraries reach for a setting with a default in hand,
    and a `None` sitting there is handed back instead of that default.
    """

    assert Block().model_dump(by_alias=True) == {"SET_VALUE": "here"}


def test_only_serialization_is_aliased() -> None:
    """
    Fields are still set and read under their own names.
    """

    assert Block(set_value="given").set_value == "given"
    assert alias_generator.serialization_alias("secret_key") == "SECRET_KEY"
    assert alias_generator.validation_alias is None


def test_keep_none() -> None:
    """
    A field named in `KEEP_NONE` reaches django as `None`.

    The names are written as fields and matched against both spellings, and
    it is a plain `ClassVar` — so a subclass overrides rather than adds.
    """

    assert KeepsOne().model_dump(by_alias=True) == {"KEPT": None}
    assert KeepsOne().model_dump() == {"kept": None}
    assert KeepsAnother().model_dump(by_alias=True) == {"DROPPED": None}


def test_drop_unset_needs_no_model_of_its_own() -> None:
    """
    A part is any model built on `DropUnset`, not on `DjangoModel`.
    """

    class Loose(DropUnset, pydantic.BaseModel):
        value: str | None = None
        other: str = "kept"

    assert Loose().model_dump() == {"other": "kept"}
