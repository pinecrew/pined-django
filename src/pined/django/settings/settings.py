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

    def __init__(self, _offset: int = 2, **values) -> None:
        """
        Reads the settings and hands them to the module that asked.

        Args:
            _offset: Where the settings module sits, for `_set_globals`.
                Anything calling on a module's behalf owes it a frame.
        """

        super().__init__(**values)
        self._set_globals(_offset)

    def _set_globals(self, offset: int = 2) -> None:
        """
        Fills the globals of the calling module with the model's contents.

        Args:
            offset: How far up the stack the settings module sits. The
                default of 2 counts a plain instantiation:

                ```
                0. DjangoSettings._set_globals
                1. DjangoSettings.__init__
                2. <settings module>
                ```
        """

        settings_module_frame = sys._getframe(offset)
        settings_module_frame.f_locals.update(self.model_dump(by_alias=True))


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
    project_settings: type[DjangoSettings] = type("ProjectSettings", (*parts, DjangoSettings), namespace)

    # One frame more than a plain instantiation: this one.
    return project_settings(_offset=3)
