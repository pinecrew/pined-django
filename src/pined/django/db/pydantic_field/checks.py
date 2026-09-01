"""
System checks for the Pydantic model behind a `PydanticField`.

Not every Pydantic model survives the round trip a `PydanticField` puts it
through: values are dumped by field name, while migrations rebuild historical
versions of the model from its JSON schema. Aliases and reference cycles each
break one half of that, so they are reported as Django system checks instead
of blowing up much later, in the middle of a migration.
"""

from __future__ import annotations

import collections
from typing import TYPE_CHECKING, Any, get_args

from django.core import checks

try:
    import pydantic
except ImportError as exc:
    msg = 'To use PydanticField, install package with "pydantic-field" option: pined-django[pydantic-field].'
    raise ImportError(msg) from exc

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django.db.models import Field

ALIAS_ERROR = "pined.django.E001"
CYCLE_ERROR = "pined.django.E002"


def iter_nested_models(annotation: Any) -> Iterator[type[pydantic.BaseModel]]:
    """
    Yield every Pydantic model mentioned in `annotation`.

    Digs through whatever the annotation is wrapped in — unions, generics,
    `Annotated` — since `list[dict[str, Inner]]` references `Inner` just as
    much as a bare `Inner` does.

    Args:
        annotation: A resolved field annotation, as pydantic stores it.

    Yields:
        Pydantic model classes, in the order they appear.
    """

    if isinstance(annotation, type) and issubclass(annotation, pydantic.BaseModel):
        yield annotation
        return

    for arg in get_args(annotation):
        yield from iter_nested_models(arg)


def resolved_fields(model: type[pydantic.BaseModel]) -> dict[str, pydantic.fields.FieldInfo]:
    """
    `model`'s fields, with forward references resolved where they can be.

    A model naming one that is defined further down the module stays
    incomplete until something rebuilds it, and until then its annotations
    are `ForwardRef`s — nothing a walk can follow into. Checks run once
    every module is imported, so the rebuild is free by the time it
    happens here.

    Args:
        model: The model to take the fields off.

    Returns:
        The field name to `FieldInfo` mapping pydantic keeps.
    """

    model.model_rebuild(raise_errors=False)
    return model.model_fields


def iter_aliased_fields(model: type[pydantic.BaseModel]) -> Iterator[tuple[type[pydantic.BaseModel], str]]:
    """
    Yield `(owner, field_name)` for every aliased field reachable from `model`.

    Args:
        model: The model to walk, nested models included.

    Yields:
        The model a field belongs to, paired with the field's own name — not
        its alias, which is exactly what makes the pair worth reporting.
    """

    visited: set[type[pydantic.BaseModel]] = set()
    queue = collections.deque([model])

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)

        for field_name, info in resolved_fields(current).items():
            if info.alias or info.validation_alias or info.serialization_alias:
                yield current, field_name
            queue.extend(iter_nested_models(info.annotation))


def find_reference_cycle(
    model: type[pydantic.BaseModel],
    path: tuple[str, ...] = (),
    seen: tuple[type[pydantic.BaseModel], ...] = (),
) -> tuple[str, ...] | None:
    """
    Return the names forming the first reference cycle in `model`, if any.

    Args:
        model: The model to walk, nested models included.
        path: Names collected on the way to `model`, for the report.
        seen: Models already standing on the current branch.

    Returns:
        The chain of alternating model and field names closing the cycle,
        e.g. `("Node", "child", "Node")`, or `None` when the model is a
        plain tree. A model reachable twice by different branches is not a
        cycle and is not reported.
    """

    path = path or (model.__name__,)
    seen = (*seen, model)

    for field_name, info in resolved_fields(model).items():
        for nested in iter_nested_models(info.annotation):
            branch = (*path, field_name, nested.__name__)
            if nested in seen:
                return branch

            cycle = find_reference_cycle(nested, branch, seen)
            if cycle is not None:
                return cycle

    return None


def check_model(model: type[pydantic.BaseModel], obj: Field[Any, Any] | None = None) -> list[checks.Error]:
    """
    Report the ways `model` cannot be stored in a `PydanticField`.

    Args:
        model: The Pydantic model the field was declared with.
        obj: The field itself, so `manage.py check` can point at it.

    Returns:
        One error per aliased field, plus one for the first reference cycle
        found. An empty list means the model round-trips fine.
    """

    errors = [
        checks.Error(
            f"Pydantic field '{owner.__name__}.{field_name}'"
            f"{'' if owner is model else f" (nested in '{model.__name__}')"} has an alias.",
            hint=(
                "PydanticField dumps values by field name, while the JSON schema it records for migrations "
                "names the same field by its alias, so stored data and its schema disagree. Drop the alias "
                "or store the model in a plain JSONField."
            ),
            obj=obj,
            id=ALIAS_ERROR,
        )
        for owner, field_name in iter_aliased_fields(model)
    ]

    cycle = find_reference_cycle(model)
    if cycle is not None:
        errors.append(
            checks.Error(
                f"Pydantic model '{model.__name__}' has a reference cycle: {' -> '.join(cycle)}.",
                hint=(
                    "Migrations rebuild a historical version of the model from its JSON schema, and a schema "
                    "referring to itself cannot be rebuilt. Break the cycle or store the model in a plain "
                    "JSONField."
                ),
                obj=obj,
                id=CYCLE_ERROR,
            )
        )

    return errors
