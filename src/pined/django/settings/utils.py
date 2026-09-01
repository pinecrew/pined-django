from typing import TYPE_CHECKING, Any, ClassVar, Literal

try:
    from pydantic import AliasGenerator, BaseModel, ConfigDict, SerializerFunctionWrapHandler, model_serializer
    from pydantic_core import core_schema
except ImportError as exc:
    msg = 'To use `settings`, install package with "settings" option: pined-django[settings].'
    raise ImportError(msg) from exc

if TYPE_CHECKING:
    from pydantic.fields import ComputedFieldInfo


alias_generator = AliasGenerator(serialization_alias=str.upper)


class UnsetType:
    """
    The absence of a value, told apart from `None`.

    A settings model needs three states, not two: a setting nobody
    mentioned, one written as `None` on purpose, and one written with a
    value. Without the first, a library either writes every setting it
    knows of — restating framework defaults and holding them there long
    after the framework has moved on — or it can never write `None` at
    all.

    A class of its own rather than an `Enum` member, which is the
    obvious way to hand pydantic something it already knows how to
    carry. Pydantic matches an enum by its *value* in lax mode, so an
    `Enum` sentinel is only ever as safe as every annotation that
    mentions it: `1` — whatever `auto()` handed out — would validate as
    the sentinel against every field a `1` does not otherwise fit, and
    `SECRET_KEY=1` would be a setting quietly going missing rather than
    an error. Validating by identity leaves nothing to collide with, and
    puts that where a hand-written `str | UnsetType` gets it too.
    """

    __slots__ = ()

    _instance: ClassVar["UnsetType | None"] = None

    def __new__(cls) -> "UnsetType":
        """
        Hand back the one there is, so `is UNSET` always answers.
        """

        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __bool__(self) -> Literal[False]:
        """
        Falsy, the way an absent value ought to be.

        `Literal[False]` rather than `bool` so that a type checker can
        narrow on it: `if self.logs_root` leaves a `Path` behind, and a
        field declared `Unset[T]` reads as a plain `T` past the guard.
        """

        return False

    def __repr__(self) -> str:
        """
        The name it is reached for under.
        """

        return "UNSET"

    def __reduce__(self) -> str:
        """
        Copies and pickles resolve back to the singleton by name.
        """

        return "UNSET"

    @classmethod
    def __get_pydantic_core_schema__(cls, _source: Any, _handler: Any) -> "core_schema.CoreSchema":
        """
        Validate by identity, and serialize to nothing in particular.

        Nothing coerces to the sentinel — the object itself is the only
        thing that validates. The serializer is there because json mode
        insists on one; `DropUnset` drops the field before anybody sees
        what it produced.
        """

        return core_schema.is_instance_schema(
            cls,
            serialization=core_schema.plain_serializer_function_ser_schema(lambda _: None),
        )


UNSET = UnsetType()
"""What every field a project has not spoken for is left at."""

type Unset[T] = T | UnsetType
"""A field that is either unset or a `T`: `Unset[str]`, `Unset[str | None]`."""


class DropUnset:
    """
    Keeps the settings nobody set out of the serialized settings.

    A setting that is present but `None` is not the same as an absent
    one. Django reads some of its own settings truthily, and libraries
    reach for theirs with `getattr(settings, name, default)`, which hands
    back the `None` instead of the default. So a field left at `UNSET` is
    never written and the owner of the setting keeps deciding, while a
    field set to `None` says `None` and django hears it — which is how a
    `SameSite`-less cookie gets spelled.
    """

    if TYPE_CHECKING:
        # Whatever this is mixed into is a model, and brings it along. The
        # block never runs, so pydantic never sees an annotation of its own
        # here to make sense of.
        model_computed_fields: ClassVar[dict[str, ComputedFieldInfo]]

    @model_serializer(mode="wrap")
    def _drop_unset(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        # Values off the instance rather than off the handler, which has
        # already turned the names into their aliases — and, in json mode,
        # the sentinel into the integer behind it, which no `is UNSET` would
        # recognise. A computed field is not in `vars`, so it is asked for
        # by name.
        unset = {name for name, value in vars(self).items() if value is UNSET}
        unset |= {name for name in type(self).model_computed_fields if getattr(self, name) is UNSET}
        return {key: value for key, value in handler(self).items() if key.lower() not in unset}


class DjangoModel(DropUnset, BaseModel):
    """
    Base model for a block of settings.

    Django is configured by constants in the settings module, so a model
    that upper-cases its own keys spares the transcription. Nested dicts
    like `TEMPLATES` or `REST_FRAMEWORK` want the same treatment.
    """

    model_config = ConfigDict(alias_generator=alias_generator)
