from pydantic import AliasGenerator, BaseModel, ConfigDict

alias_generator = AliasGenerator(serialization_alias=str.upper)


class DjangoModel(BaseModel):
    """
    Base model for a block of settings.

    Django is configured by constants in the settings module, so a model
    that upper-cases its own keys spares the transcription. Nested dicts
    like `TEMPLATES` or `REST_FRAMEWORK` want the same treatment.
    """

    model_config = ConfigDict(alias_generator=alias_generator)
