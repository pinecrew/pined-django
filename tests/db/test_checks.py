"""
The system checks a `PydanticField` runs over its pydantic model.

Aliases and reference cycles both pass a field declaration without a word
and only come apart later: one puts the stored data and the recorded
schema under different names, the other cannot be rebuilt into a
historical model at all. These checks are what stands between such a
model and a migration that discovers it the hard way.
"""

from typing import Annotated, Any

import pydantic
import pytest
from django.core import checks

from pined.django.db.models import PydanticField
from pined.django.db.pydantic_field.checks import ALIAS_ERROR, CYCLE_ERROR, check_model


class Plain(pydantic.BaseModel):
    """
    A model with nothing wrong with it.
    """

    value: int = 0


class Aliased(pydantic.BaseModel):
    """
    The plain shape, renamed on its way in and out.
    """

    value: int = pydantic.Field(0, alias="v")


class ValidationAliased(pydantic.BaseModel):
    """
    Renamed on the way in only.
    """

    value: int = pydantic.Field(0, validation_alias="v")


class SerializationAliased(pydantic.BaseModel):
    """
    Renamed on the way out only.
    """

    value: int = pydantic.Field(0, serialization_alias="v")


class Generated(pydantic.BaseModel):
    """
    Nobody wrote an alias here; the config produced one anyway.
    """

    model_config = pydantic.ConfigDict(alias_generator=str.upper)

    value: int = 0


class Node(pydantic.BaseModel):
    """
    A model that refers to itself.
    """

    name: str = ""
    child: "Node | None" = None


class Tree(pydantic.BaseModel):
    """
    The same, one collection removed.
    """

    kids: "list[Tree]" = []


class Ping(pydantic.BaseModel):
    """
    Half of a cycle that takes two models to close.

    Named before `Pong` exists, so it stays incomplete — and its
    annotation a `ForwardRef` — until something rebuilds it.
    """

    pong: "Pong | None" = None


class Pong(pydantic.BaseModel):
    """
    The other half.
    """

    ping: Ping | None = None


class Diamond(pydantic.BaseModel):
    """
    One model reached by two roads — a shape, not a cycle.
    """

    left: Plain | None = None
    right: list[Plain] = []


class CyclicAndAliased(pydantic.BaseModel):
    """
    A cycle to walk into and an alias to find on the way.
    """

    value: int = pydantic.Field(0, alias="v")
    child: "CyclicAndAliased | None" = None


def holder(annotation: Any) -> type[pydantic.BaseModel]:
    """
    A model with one field of `annotation`, whatever it is wrapped in.

    Args:
        annotation: The annotation to hang an aliased model off.

    Returns:
        A freshly built model, so a case can name a single wrapper and
        leave the rest alone.
    """

    return pydantic.create_model("Holder", held=(annotation, None))


def test_a_model_that_round_trips_is_left_alone() -> None:
    """
    Nothing to say about a plain model.
    """

    assert check_model(Plain) == []
    assert check_model(Diamond) == []


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        pytest.param(Aliased, "Pydantic field 'Aliased.value' has an alias.", id="an-alias"),
        pytest.param(ValidationAliased, "Pydantic field 'ValidationAliased.value' has an alias.", id="on-the-way-in"),
        pytest.param(
            SerializationAliased,
            "Pydantic field 'SerializationAliased.value' has an alias.",
            id="on-the-way-out",
        ),
        pytest.param(Generated, "Pydantic field 'Generated.value' has an alias.", id="from-a-generator"),
    ],
)
def test_an_alias_is_reported_however_it_got_there(model: type[pydantic.BaseModel], expected: str) -> None:
    """
    Any of the three aliases counts, written by hand or generated.

    The report names the field, not the alias: the field name is what a
    stored value is written under, and what has to go.
    """

    (error,) = check_model(model)

    assert error.id == ALIAS_ERROR
    assert error.msg == expected


@pytest.mark.parametrize(
    "annotation",
    [
        pytest.param(Aliased, id="a-model"),
        pytest.param(Aliased | None, id="a-union"),
        pytest.param(list[Aliased], id="a-list"),
        pytest.param(dict[str, Aliased], id="a-dict"),
        pytest.param(tuple[int, Aliased], id="a-tuple"),
        pytest.param(list[dict[str, Aliased | None]], id="a-pile-of-generics"),
        pytest.param(Annotated[Aliased | None, pydantic.Field(description="whatever")], id="annotated"),
    ],
)
def test_an_alias_is_found_through_whatever_wraps_it(annotation: Any) -> None:
    """
    A nested model is reached however its annotation is dressed up.
    """

    (error,) = check_model(holder(annotation))

    assert error.id == ALIAS_ERROR
    assert error.msg == "Pydantic field 'Aliased.value' (nested in 'Holder') has an alias."


def test_every_aliased_field_gets_its_own_error() -> None:
    """
    One error per field, so a single `check` run lists all the work.
    """

    model = pydantic.create_model(
        "Both",
        first=(int, pydantic.Field(0, alias="a")),
        second=(int, pydantic.Field(0, alias="b")),
    )

    assert [error.msg for error in check_model(model)] == [
        "Pydantic field 'Both.first' has an alias.",
        "Pydantic field 'Both.second' has an alias.",
    ]


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        pytest.param(Node, "Node -> child -> Node", id="straight-at-itself"),
        pytest.param(Tree, "Tree -> kids -> Tree", id="through-a-collection"),
        pytest.param(Ping, "Ping -> pong -> Pong -> ping -> Ping", id="the-long-way-round"),
        pytest.param(holder(Node | None), "Holder -> held -> Node -> child -> Node", id="one-model-down"),
    ],
)
def test_a_cycle_is_reported_with_the_way_into_it(model: type[pydantic.BaseModel], expected: str) -> None:
    """
    The chain of names is the point: it says where to cut.
    """

    (error,) = check_model(model)

    assert error.id == CYCLE_ERROR
    assert error.msg == f"Pydantic model '{model.__name__}' has a reference cycle: {expected}."


def test_a_cycle_does_not_swallow_the_alias_walk() -> None:
    """
    Both problems are reported, and the walk still finishes.
    """

    assert [error.id for error in check_model(CyclicAndAliased)] == [ALIAS_ERROR, CYCLE_ERROR]


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        pytest.param(Plain, [], id="a-model-that-round-trips"),
        pytest.param(Aliased, [ALIAS_ERROR], id="an-alias"),
        pytest.param(Node, [CYCLE_ERROR], id="a-cycle"),
    ],
)
def test_the_field_reports_the_model_against_itself(model: type[pydantic.BaseModel], expected: list[str]) -> None:
    """
    `manage.py check` points at the field that named the model.
    """

    field = PydanticField(model, null=True, default=None)
    field.set_attributes_from_name("metadata")
    errors = field.check()

    assert [error.id for error in errors] == expected
    assert all(isinstance(error, checks.Error) and error.obj is field for error in errors)


def test_the_field_still_runs_the_checks_it_inherited() -> None:
    """
    The pydantic errors come on top of django's, not instead of them.
    """

    field = PydanticField(Aliased, null=True, default=None)
    field.set_attributes_from_name("metadata_")

    assert [error.id for error in field.check()] == ["fields.E001", ALIAS_ERROR]
