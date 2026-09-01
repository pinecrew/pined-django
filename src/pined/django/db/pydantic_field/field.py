"""
A Django model field that stores a Pydantic model as JSON.

`PydanticField` behaves like a `JSONField`, but reads and writes come out as
validated instances of the Pydantic model it was declared with, instead of
plain dicts/lists.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, override

from django.core.exceptions import ValidationError
from django.db import models
from pined.django.serializers.json import JSONEncoder

try:
    import pydantic
except ImportError as exc:
    msg = 'To use PydanticField, install package with "pydantic-field" option: pined-django[pydantic-field].'
    raise ImportError(msg) from exc

from .checks import check_model
from .schema import SchemaManager

if TYPE_CHECKING:
    import json
    from collections.abc import Callable, Sequence

    from django.core.checks import CheckMessage
    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.db.models import Expression


class PydanticField[T: pydantic.BaseModel](models.JSONField):
    """
    A `JSONField` that (de)serializes its value through a Pydantic model.

    Reading the field off a model instance always yields a validated
    instance of `model`; writing accepts either an instance of `model` or a
    plain dict/list that can be validated into one.
    """

    __module__ = "pined.django.db.models"

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        model: type[T],
        verbose_name: str | None = None,
        name: str | None = None,
        encoder: type[json.JSONEncoder] | None = None,
        decoder: type[json.JSONDecoder] | None = None,
        default: Callable[[], Any] | models.NOT_PROVIDED | None = models.NOT_PROVIDED,
        **kwargs,
    ) -> None:
        """
        Set up the field for `model`, defaulting encoder and default value.

        If `default` is left unset, an attempt is made to instantiate `model`
        with no arguments. If that succeeds (i.e. every field has a default),
        `model` itself is used as the default factory. Otherwise the field is
        left without a default, same as a bare `JSONField` would be.
        """

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

    @override
    def check(self, **kwargs) -> list[CheckMessage]:
        """
        Run `JSONField`'s own checks, then those for `inner_model`.

        Reports aliases and reference cycles in the Pydantic model: both
        pass a field declaration just fine and only fall apart later, at
        migration time.
        """

        return [*super().check(**kwargs), *check_model(self.inner_model, self)]

    @override
    def from_db_value(self, value: str | None, expression: Expression, connection: BaseDatabaseWrapper) -> T | None:
        """
        Validate the raw JSON coming back from the database into `model`.
        """

        v = super().from_db_value(value, expression, connection)

        # Querysets with select_related would set None if corresponding instance
        # is missing, even if `null=False`. Thus, `null` is just db-related
        # option and have nothing to do with value checks.
        if v is None:
            return v

        return self._pydantic_model.model_validate(v)

    @override
    def get_db_prep_value(self, value: Any, connection: BaseDatabaseWrapper, prepared: bool = False) -> Any:
        """
        Reduce `value` to something a plain `JSONField` can store.

        `value` is a `BaseModel` instance, or already a plain dict/list.
        Anything a query expression wrapped never arrives here: django
        compiles those to SQL, and `Value.as_sql` hands over its inner
        value rather than itself.
        """

        if self.null and value is None:
            return None

        # got normal BaseModel, pass as a dict into underlying JSONField
        if hasattr(value, "model_dump"):
            return super().get_db_prep_value(value.model_dump(), connection, prepared)

        # not a route django takes, but a caller reaching for the field
        # directly may well hand over the wrapper it has
        if isinstance(value, models.Value):
            return self.get_db_prep_value(value.value, connection, prepared)

        return super().get_db_prep_value(value, connection, prepared)

    @override
    def to_python(self, value: Any) -> T | None:
        """
        Validate a form/deserialization-time value into `model`.

        Wraps Pydantic's `ValidationError` in Django's `ValidationError`, so
        it surfaces normally through model/form validation.
        """

        if value is None:
            return None  # same logic as in from_db_value
        try:
            return self._pydantic_model.model_validate(super().to_python(value))
        except pydantic.ValidationError as e:
            raise ValidationError(str(e)) from e

    @override
    def deconstruct(self) -> tuple[str, str, Sequence[Any], dict[str, Any]]:
        """
        Serialize the field for migrations, including `model` as the
        first positional arg.
        """

        name, path, args, kwargs = super().deconstruct()
        return name, path, (self._pydantic_model, *args), kwargs

    @override
    def value_to_string(self, obj: models.Model) -> dict[str, Any] | list[Any] | None:
        """
        Return the field's value as plain dict/list data, for fixture
        serialization.
        """

        # some apps may pass a dict / list, not a BaseModel (I'm looking at you, easyaudit)
        value = self.value_from_object(obj)
        if value is None:
            return None
        if isinstance(value, (dict, list)):  # a tuple, not `dict | list`: that one cannot carry type arguments
            return value
        return value.model_dump()

    @property
    def inner_model(self) -> type[T]:
        """
        The Pydantic model this field validates its value against.
        """

        return self._pydantic_model

    @override
    def clone(self) -> PydanticField[T]:
        """
        Copy the field, carrying over the schema hash set by migrations.
        """

        clone = super().clone()  # gets args from deconstruct and pass them into self.__class__
        clone._schema_hash = self._schema_hash
        return clone

    @property
    def current_schema(self) -> str:
        """
        The hash of `inner_model`'s current JSON schema.

        Used to detect, at migration-generation time, whether the Pydantic
        model has changed since the last recorded schema version.
        """

        model_hash, _ = SchemaManager.generate_model_hash(self.inner_model)
        return model_hash
