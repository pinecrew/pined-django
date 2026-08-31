"""
`SchemaManager.normalize` — what counts as a change of shape, and what
does not.

The fingerprint decides whether every row in a table gets rewritten, so
the line it draws is the whole subject here: everything pydantic puts in a
json schema that a validator would ignore has to fall on the "not a
change" side of it.

Both tables compare normalized schemas rather than their hashes. The hash
follows from the schema, and a failing dict prints a diff.
"""

import enum
from typing import Any, Literal

import pydantic
import pytest

from pined.django.db.pydantic_field.schema import SchemaManager


class Inner(pydantic.BaseModel):
    """
    A nested model, to put a class name somewhere awkward.
    """

    q: int


class Base(pydantic.BaseModel):
    """
    The shape every case below is measured against.
    """

    a: int
    b: str = "x"
    nested: Inner
    kids: list[Inner] = []
    lit: Literal["A", "B"] = "A"


def variant(**overrides: Any) -> type[pydantic.BaseModel]:
    """
    `Base` again, with some of its fields replaced.

    Built from the outside so a case can change one thing and say so in
    its `id`, instead of restating the whole model.
    """

    fields: dict[str, Any] = {
        "a": (int, ...),
        "b": (str, "x"),
        "nested": (Inner, ...),
        "kids": (list[Inner], []),
        "lit": (Literal["A", "B"], "A"),
    }
    name = overrides.pop("__name__", "Base")
    return pydantic.create_model(name, __doc__=Base.__doc__, **(fields | overrides))


def shape(model: type[pydantic.BaseModel]) -> dict[str, Any]:
    """
    The part of a model's schema the fingerprint is taken over.
    """

    return SchemaManager.normalize(model.model_json_schema())


class Renamed(pydantic.BaseModel):
    """
    The same shape under another name, with another docstring, and with a
    title of its own on top of that.
    """

    model_config = pydantic.ConfigDict(title="Whatever")

    a: int
    b: str = "x"
    nested: Inner
    kids: list[Inner] = []
    lit: Literal["A", "B"] = "A"


class Reordered(pydantic.BaseModel):
    lit: Literal["A", "B"] = "A"
    kids: list[Inner] = []
    nested: Inner
    b: str = "x"
    a: int


class InnerRenamed(pydantic.BaseModel):
    """
    `Inner` under another name — its own class name reaches the schema in
    the `$defs` key and inside every `$ref` string, not only in `title`.
    """

    q: int


#: `Inner` again, declared elsewhere: pydantic qualifies a `$defs` key with
#: the module path as soon as two nested models share a name.
InnerElsewhere = pydantic.create_model("Inner", q=(int, ...), __module__="somewhere.else")


class Documented(pydantic.BaseModel):
    a: int = pydantic.Field(title="Custom A", description="what a is", examples=[1, 2], deprecated=True)
    b: str = "x"
    nested: Inner
    kids: list[Inner] = []
    lit: Literal["A", "B"] = "A"


class Ordered(enum.StrEnum):
    RED = "red"
    GREEN = "green"


class Unordered(enum.StrEnum):
    GREEN = "green"
    RED = "red"


@pytest.mark.parametrize(
    "same",
    [
        pytest.param(Renamed, id="a-new-name-a-new-docstring-and-a-config-title"),
        pytest.param(Reordered, id="the-fields-declared-in-another-order"),
        pytest.param(variant(nested=(InnerRenamed, ...), kids=(list[InnerRenamed], [])), id="a-renamed-nested-model"),
        pytest.param(
            variant(nested=(InnerElsewhere, ...), kids=(list[InnerElsewhere], [])),
            id="a-nested-model-moved-to-another-module",
        ),
        pytest.param(Documented, id="a-field-given-a-title-a-description-examples-and-deprecated"),
        pytest.param(variant(lit=(Literal["B", "A"], "A")), id="the-members-of-a-literal-reordered"),
    ],
)
def test_the_fingerprint_ignores_everything_cosmetic(same: type[pydantic.BaseModel]) -> None:
    """
    None of this is something a validator would notice.
    """

    assert shape(same) == shape(Base)


def test_the_fingerprint_ignores_the_order_of_an_enum() -> None:
    """
    An `Enum`'s members reach the schema in declaration order.
    """

    assert shape(pydantic.create_model("E", c=(Ordered, ...))) == shape(pydantic.create_model("E", c=(Unordered, ...)))


@pytest.mark.parametrize(
    "different",
    [
        pytest.param(variant(c=(bool, False)), id="a-field-added"),
        pytest.param(pydantic.create_model("Base", a=(int, ...), b=(str, "x")), id="a-field-removed"),
        pytest.param(variant(a=(str, ...)), id="a-field-retyped"),
        pytest.param(variant(b=(str, "y")), id="a-default-changed"),
        pytest.param(variant(a=(int | None, None)), id="a-field-turned-optional"),
        pytest.param(variant(a=(int, pydantic.Field(ge=0))), id="a-constraint-added"),
        pytest.param(
            variant(
                nested=(pydantic.create_model("Inner", q=(int, ...), r=(str, "")), ...),
                kids=(list[Inner], []),
            ),
            id="a-field-added-inside-the-nested-model",
        ),
        pytest.param(variant(a=(int, pydantic.Field(alias="aa"))), id="an-alias-changed"),
        pytest.param(variant(lit=(Literal["A", "C"], "A")), id="a-member-of-a-literal-changed"),
        # Whatever a caller hung on the field, it may mean something to them.
        pytest.param(
            variant(a=(int, pydantic.Field(json_schema_extra={"x-encrypted": True}))),
            id="json-schema-extra-changed",
        ),
    ],
)
def test_the_fingerprint_catches_a_real_change(different: type[pydantic.BaseModel]) -> None:
    """
    Anything that moves what pydantic accepts moves the fingerprint.
    """

    assert shape(different) != shape(Base)


def test_extra_forbid_is_a_real_change() -> None:
    """
    `model_config.extra` reaches the schema as `additionalProperties`.
    """

    forbidding = pydantic.create_model("Base", __config__=pydantic.ConfigDict(extra="forbid"), a=(int, ...))

    assert shape(forbidding) != shape(pydantic.create_model("Base", a=(int, ...)))


def test_a_cyclic_model_still_normalizes() -> None:
    """
    A self-referencing model is the one shape that could walk forever.

    Its schema is a bare `$ref` at the root with the model itself in
    `$defs`, so there is no top-level `properties` to lean on either.

    Note:
        Only the fingerprint is claimed here. Rebuilding a cyclic model
        through `SchemaManager.get_model` hits a `RecursionError` inside
        `json_schema_to_pydantic`, and did so before any of this.
    """

    class Node(pydantic.BaseModel):
        val: int
        child: "Node | None" = None
        kids: list["Node"] = []

    class Renamed(pydantic.BaseModel):
        val: int
        child: "Renamed | None" = None
        kids: list["Renamed"] = []

    normalized = shape(Node)

    assert normalized["$ref"] == "#/$defs/d0"
    assert set(normalized["$defs"]) == {"d0"}
    assert normalized == shape(Renamed)


class KeywordNames(pydantic.BaseModel):
    """
    A model whose fields are named after json schema keywords.

    `title` is documentation one level up and a field name here. Nothing
    in the key itself says which — only where it sits does.
    """

    title: str
    description: int
    examples: list[int] = []
    deprecated: bool = False
    readOnly: str = ""  # noqa: N815 - the keyword is spelled this way
    required: str = ""
    enum: str = ""


def test_a_field_named_after_a_keyword_is_still_a_field() -> None:
    """
    Documentation is dropped by position, not by name.
    """

    assert sorted(shape(KeywordNames)["properties"]) == [
        "deprecated",
        "description",
        "enum",
        "examples",
        "readOnly",
        "required",
        "title",
    ]


def test_retyping_a_field_named_after_a_keyword_is_a_real_change() -> None:
    """
    A field the fingerprint cannot see is a table it cannot migrate.
    """

    retyped = pydantic.create_model("KeywordNames", title=(int, ...))
    same = pydantic.create_model("KeywordNames", title=(str, ...))

    assert shape(retyped) != shape(same)


def test_a_default_that_looks_like_documentation_is_data() -> None:
    """
    A `title` inside a stored value is the value's, not the schema's.
    """

    kept = pydantic.create_model("D", a=(dict, pydantic.Field(default={"title": "kept"})))
    other = pydantic.create_model("D", a=(dict, pydantic.Field(default={"title": "other"})))

    assert shape(kept) != shape(other)
