"""
`DropUnset`, `DjangoModel`, `UNSET` and the alias generator underneath them.
"""

import copy

import pydantic
import pytest

from pined.django.settings import UNSET, DjangoModel, DropUnset, Unset, UnsetType
from pined.django.settings.utils import alias_generator


class Block(DjangoModel):
    """
    A block with one field of each disposition.
    """

    set_value: Unset[str] = "here"
    unset_value: Unset[str] = UNSET
    nullable: Unset[str | None] = UNSET


def test_a_block_dumps_upper_cased_and_without_the_unset() -> None:
    """
    Django is configured by constants, and a field nobody set is absent.

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
    assert alias_generator.serialization_alias is not None
    assert alias_generator.serialization_alias("secret_key") == "SECRET_KEY"
    assert alias_generator.validation_alias is None


def test_a_none_written_down_is_a_none_django_hears() -> None:
    """
    `None` is a value, and `UNSET` is the absence of one.

    Without the two being separate a part could either write every setting
    it knows of — restating framework defaults and holding them there long
    after the framework had moved on — or never write a `None` at all, and
    there would be no way to spell a `SameSite`-less cookie.
    """

    assert Block(nullable=None).model_dump(by_alias=True) == {"SET_VALUE": "here", "NULLABLE": None}
    assert Block(nullable="value").model_dump(by_alias=True) == {"SET_VALUE": "here", "NULLABLE": "value"}
    assert Block(set_value=UNSET).model_dump(by_alias=True) == {}


def test_a_subclass_sets_a_field_by_giving_it_a_default() -> None:
    """
    How a project spells a setting: a part of its own, and a default.

    `configure` builds the settings class and instantiates it with nothing,
    so the field's default is the whole of the interface — which is why
    `UNSET` has to be a value a default can be, and not merely the absence
    of an argument.
    """

    class Overriding(Block):
        unset_value: Unset[str] = "given"
        nullable: Unset[str | None] = None

    assert Overriding().model_dump(by_alias=True) == {
        "SET_VALUE": "here",
        "UNSET_VALUE": "given",
        "NULLABLE": None,
    }


def test_unset_is_falsy_and_says_its_name() -> None:
    """
    It shows up in tracebacks and in `repr`, so it reads as itself.
    """

    assert not UNSET
    assert repr(UNSET) == "UNSET"
    assert repr(Block().unset_value) == "UNSET"


@pytest.mark.parametrize("spelling", ["through-the-alias", "by-hand"])
def test_nothing_validates_into_the_sentinel(spelling: str) -> None:
    """
    `UNSET` is reached by identity, and nothing coerces to it.

    It was an `Enum` member to begin with, which pydantic matches by its
    *value* in lax mode — so the `1` that `auto()` handed out validated as
    `UNSET` against every field a `1` did not otherwise fit, and
    `SECRET_KEY=1` was not an error but a setting quietly going missing.
    Both spellings of the union are here because the first fix put the
    guard in the alias, where a hand-written `str | UnsetType` walked
    straight past it.
    """

    if spelling == "through-the-alias":

        class Model(DjangoModel):
            value: Unset[str] = UNSET
    else:

        class Model(DjangoModel):  # type: ignore[no-redef]
            value: str | UnsetType = UNSET

    with pytest.raises(pydantic.ValidationError):
        Model(value=1)

    assert Model().model_dump(by_alias=True) == {}
    assert Model(value="given").model_dump(by_alias=True) == {"VALUE": "given"}


def test_a_computed_field_is_dropped_in_every_mode() -> None:
    """
    A part that computes a setting can decline to have one.

    The check used to run over what the serializer had already produced,
    where json mode had turned the sentinel into the number behind it and
    `is UNSET` no longer recognised it — so a `model_dump_json` carried a
    setting whose value was an implementation detail.
    """

    class Computing(DjangoModel):
        on: Unset[bool] = UNSET

        @pydantic.computed_field
        def derived(self) -> Unset[str]:
            return "here" if self.on else UNSET

    assert Computing().model_dump(by_alias=True) == {}
    assert Computing().model_dump(by_alias=True, mode="json") == {}
    assert Computing().model_dump_json(by_alias=True) == "{}"
    assert Computing(on=True).model_dump(by_alias=True, mode="json") == {"ON": True, "DERIVED": "here"}


def test_there_is_only_one_of_it() -> None:
    """
    `is UNSET` is the interface, so a copy has to answer to it too.
    """

    assert UnsetType() is UNSET
    assert copy.deepcopy(UNSET) is UNSET
    assert copy.copy(UNSET) is UNSET


def test_drop_unset_needs_no_model_of_its_own() -> None:
    """
    A part is any model built on `DropUnset`, not on `DjangoModel`.
    """

    class Loose(DropUnset, pydantic.BaseModel):
        value: Unset[str] = UNSET
        other: str = "kept"

    assert Loose().model_dump() == {"other": "kept"}
