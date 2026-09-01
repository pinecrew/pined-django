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

import datetime
import decimal
import enum
import uuid
from typing import Annotated, Any, Literal

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


SHAPES: dict[str, tuple[Any, Any]] = {
    "plain": (str, ...),
    "with_default": (str, "d"),
    "optional": (str | None, None),
    "constrained": (Annotated[int, pydantic.Field(ge=1, le=10)], 5),
    "pattern": (Annotated[str, pydantic.Field(pattern=r"^[a-z]+$")], "abc"),
    "literal": (Literal["a", "b"], "a"),
    "an_enum": (Ordered, Ordered.RED),
    "a_union": (int | str, 0),
    "a_list": (list[int], []),
    "a_dict": (dict[str, int], {}),
    "nested": (Inner, Inner(q=1)),
    "a_date": (datetime.date, datetime.date(2020, 1, 1)),
    "a_decimal": (decimal.Decimal, decimal.Decimal("1.5")),
    "a_uuid": (uuid.UUID, uuid.UUID(int=0)),
    "described": (str, pydantic.Field("v", description="d", title="t")),
    "cyrillic": (str, "Кострома"),
    "factory": (list[str], pydantic.Field(default_factory=lambda: ["a"])),
}
"""One field of every kind whose json schema pydantic might render differently."""


@pytest.mark.parametrize(
    ("shape_name", "expected"),
    [
        pytest.param("plain", "c0296fc4874369fe", id="plain"),
        pytest.param("with_default", "684447a103b921db", id="with-default"),
        pytest.param("optional", "b9217f6ab246ed9d", id="optional"),
        pytest.param("constrained", "2652ceafe092b4b5", id="constrained"),
        pytest.param("pattern", "1744cc64100f03fc", id="pattern"),
        pytest.param("literal", "33e25fef3d0ce192", id="literal"),
        pytest.param("an_enum", "4e98ac5ba9c2d56e", id="an-enum"),
        pytest.param("a_union", "1cc43f72e80a639c", id="a-union"),
        pytest.param("a_list", "5a78cf3b5160b13b", id="a-list"),
        pytest.param("a_dict", "44a01ffa90b98ddb", id="a-dict"),
        pytest.param("nested", "b37b9cd1e16e3590", id="nested"),
        pytest.param("a_date", "5c6fbc473691b445", id="a-date"),
        pytest.param("a_decimal", "112a1698b55e380a", id="a-decimal"),
        pytest.param("a_uuid", "fab52b17b0ff05cd", id="a-uuid"),
        pytest.param("described", "3ba02969beecb8db", id="described"),
        pytest.param("cyrillic", "74f7d4324bcc4294", id="cyrillic"),
        pytest.param("factory", "559e1cf3898db77a", id="factory"),
    ],
)
def test_the_fingerprint_of_a_shape_does_not_move(shape_name: str, expected: str) -> None:
    """
    A hash written into a migration has to mean the same thing tomorrow.

    The fingerprint is taken over what `model_json_schema()` produces, so a
    pydantic release that renders a shape differently moves it — and every
    project holding that shape gets an `AlterPydantic` nobody wrote, on a
    model nobody touched. Which is exactly what pydantic 2.12 did to
    `Decimal`: it added a `pattern` to the string arm, and the hash of
    `a_decimal` went from `e93668c429b3f38b` to the value below. `>=2.12`
    is the floor for that reason, so that every version this package
    supports agrees on all seventeen.

    A failure here is that happening again. It is not a bug in this file:
    find what pydantic changed, decide whether the new rendering is the one
    to keep, and if it is, raise the floor and write the migration note that
    tells projects why their next `makemigrations` has something to say.
    """

    model = pydantic.create_model(f"Shape_{shape_name}", **{shape_name: SHAPES[shape_name]})

    assert SchemaManager.generate_model_hash(model)[0] == expected
