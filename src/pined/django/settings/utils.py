from typing import Any, ClassVar

try:
    from pydantic import AliasGenerator, BaseModel, ConfigDict, SerializerFunctionWrapHandler, model_serializer
except ImportError as exc:
    msg = 'To use `settings`, install package with "settings" option: pined-django[settings].'
    raise ImportError(msg) from exc


alias_generator = AliasGenerator(serialization_alias=str.upper)


class DropUnset:
    """
    Keeps `None` out of the serialized settings.

    A setting that is present but `None` is not the same as an absent
    one. Django reads some of its own settings truthily, and libraries
    reach for theirs with `getattr(settings, name, default)`, which hands
    back the `None` instead of the default. So `None` here means "not
    configured", and the owner of the setting keeps deciding.

    Attributes:
        KEEP_NONE: Names of the fields where `None` is a value of its
            own, and so has to reach django. Without them there would be
            no way to spell, say, a `SameSite`-less cookie.
        NOT_A_SETTING: Names of the fields that feed another field and
            have no business in the settings module themselves. Named
            here rather than marked with `Field(exclude=True)`, which a
            project silently discards by redeclaring the field.
    """

    KEEP_NONE: ClassVar[frozenset[str]] = frozenset()
    NOT_A_SETTING: ClassVar[frozenset[str]] = frozenset()

    @model_serializer(mode="wrap")
    def _drop_unset(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        keep = self.KEEP_NONE | {name.upper() for name in self.KEEP_NONE}
        drop = self.NOT_A_SETTING | {name.upper() for name in self.NOT_A_SETTING}
        return {
            key: value for key, value in handler(self).items() if key not in drop and (value is not None or key in keep)
        }


class DjangoModel(DropUnset, BaseModel):
    """
    Base model for a block of settings.

    Django is configured by constants in the settings module, so a model
    that upper-cases its own keys spares the transcription. Nested dicts
    like `TEMPLATES` or `REST_FRAMEWORK` want the same treatment.
    """

    model_config = ConfigDict(alias_generator=alias_generator)
