import sys
from typing import Unpack

try:
    from pydantic import BaseModel
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError as exc:
    msg = 'To use `settings`, install package with "settings" option: pined-django[settings].'
    raise ImportError(msg) from exc

from .utils import DropUnset, alias_generator


class DjangoSettings(DropUnset, BaseSettings):
    """
    Base class for a django project's settings.

    A project usually adds no more than `env_prefix` and `env_file` of its own,
    since pydantic merges `model_config` down the MRO instead of replacing it.
    """

    model_config = SettingsConfigDict(
        alias_generator=alias_generator,
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


def configure(*parts: type[BaseModel], **config: Unpack[SettingsConfigDict]) -> DjangoSettings:
    """
    Assembles the settings out of `parts` and fills the calling module.

    A project's settings class carries nothing but its bases and a
    `model_config`, which is a class statement's worth of ceremony for
    two pieces of information.

    Args:
        *parts: The mixins, in precedence order — earlier ones win.
        **config: `SettingsConfigDict` keys, `env_prefix` chief among them.

    Returns:
        The settings, already spread over the caller's globals.

    Example:
        ```
        configure(General, Apps, Database, env_prefix="MYPROJECT_")
        ```
    """

    namespace = {"model_config": SettingsConfigDict(**config)}
    # A part that is already a `DjangoSettings` is the base; naming it twice
    # would re-apply its own `model_config` over whatever the part set.
    bases = parts if any(issubclass(part, DjangoSettings) for part in parts) else (*parts, DjangoSettings)
    settings_cls: type[DjangoSettings] = type("ProjectSettings", bases, namespace)
    project_settings = settings_cls()

    # Fills the globals of the calling module with the model's contents.
    # Module sits one frame back up the stack:
    # 0. configure()
    # 1. <settings module>
    settings_module_frame = sys._getframe(1)
    settings_module_frame.f_locals.update(project_settings.model_dump(by_alias=True))

    return project_settings
