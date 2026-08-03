from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.db import models
from pined.django.serializers.json import JSONEncoder

try:
    import pydantic
except ImportError as exc:
    msg = 'To use PydanticField, install package with "pydantic-field" option: pined-django[pydantic-field].'
    raise ImportError(msg) from exc

from .schema import SchemaManager

if TYPE_CHECKING:
    import json
    from collections.abc import Callable, Sequence

    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.db.models import Expression


class PydanticField[T: pydantic.BaseModel](models.JSONField):
    __module__ = "pined.django.db.models"

    def __init__(  # noqa: PLR0913
        self,
        model: type[T],
        verbose_name: str | None = None,
        name: str | None = None,
        encoder: type[json.JSONEncoder] | None = None,
        decoder: type[json.JSONDecoder] | None = None,
        default: Callable | models.NOT_PROVIDED | None = models.NOT_PROVIDED,
        **kwargs,
    ) -> None:
        if encoder is None:
            encoder = JSONEncoder

        if default is models.NOT_PROVIDED:
            with contextlib.suppress(pydantic.ValidationError):
                # Check if pydantic model was defined with default values for all fields.
                # If so, use it as default value, otherwise JSONField would throw
                # an exception via CheckFieldDefaultMixin — we do nothing.
                model()
                default = model

        super().__init__(verbose_name, name, encoder, decoder, default=default, **kwargs)
        self._pydantic_model = model
        self._schema_hash: str | None = None

    def from_db_value(self, value: str | None, expression: Expression, connection: BaseDatabaseWrapper) -> None | T:
        v = super().from_db_value(value, expression, connection)

        # Querysets with select_related would set None if corresponding instance
        # is missing, even if `null=False`. Thus, `null` is just db-related
        # option and have nothing to do with value checks.
        if v is None:
            return v

        return self._pydantic_model.model_validate(v)

    def get_db_prep_value(self, value: Any, connection: BaseDatabaseWrapper, prepared: bool = False) -> Any:  # noqa: PLR0911, C901
        if self.null and value is None:
            return None

        # got normal BaseModel, pass as a dict into underlying JSONField
        if hasattr(value, "model_dump"):
            return super().get_db_prep_value(value.model_dump(), connection, prepared)

        # got models.Value, rerun this function with the inner value
        if isinstance(value, models.Value):
            return self.get_db_prep_value(value.value, connection, prepared)

        # got an Expression, prepare yourself for some digging
        if hasattr(value, "get_source_expressions"):
            expressions = value.get_source_expressions()
            # nothing inside — broken Expression?
            if not expressions:
                return None

            expr = expressions[0]

            # If null=True, django would make a backflip and wrap everything
            # into Case-When-Else, with Value-s inside. Amusing.
            if isinstance(expr, models.Case):
                for when in expr.cases:
                    if isinstance(when, models.When):
                        return self.get_db_prep_value(when.result, connection, prepared)
                if hasattr(expr, "default"):
                    return self.get_db_prep_value(expr.default, connection, prepared)

            if hasattr(expr, "value"):
                return self.get_db_prep_value(expr.value, connection, prepared)
            return self.get_db_prep_value(expr, connection, prepared)

        return super().get_db_prep_value(value, connection, prepared)

    def to_python(self, value: Any) -> T | None:
        if value is None:
            return None  # same logic as in from_db_value
        try:
            return self._pydantic_model.model_validate(super().to_python(value))
        except pydantic.ValidationError as e:
            raise ValidationError(str(e)) from e

    def deconstruct(self) -> tuple[str, str, Sequence[Any], dict[str, Any]]:
        name, path, args, kwargs = super().deconstruct()
        return name, path, (self._pydantic_model, *args), kwargs

    def value_to_string(self, obj: models.Model) -> dict | list | None:
        if self.null and obj is None:
            return None

        # some apps may pass a dict / list, not a BaseModel (I'm looking at you, easyaudit)
        value = self.value_from_object(obj)
        if value is None:
            return None
        if isinstance(value, dict | list):
            return value
        return value.model_dump()

    @property
    def inner_model(self) -> type[T]:
        return self._pydantic_model

    def clone(self) -> PydanticField[T]:
        clone = super().clone()  # gets args from deconstruct and pass them into self.__class__
        clone._schema_hash = self._schema_hash
        return clone

    @property
    def current_schema(self) -> str:
        model_hash, _ = SchemaManager.generate_model_hash(self.inner_model)
        return model_hash
