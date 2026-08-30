import sys

try:
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

    def __init__(self, **values) -> None:
        super().__init__(**values)
        self._set_globals()

    def _set_globals(self, offset: int = 2) -> None:
        """
        Fills the globals of the calling module with the model's contents.

        Args:
            offset: How far up the stack the settings module sits. The
                default of 2 matches the intended use:

                ```
                0. DjangoSettings._set_globals
                1. DjangoSettings.__init__
                2. <settings module>
                ```
        """

        settings_module_frame = sys._getframe(offset)
        settings_module_frame.f_locals.update(self.model_dump(by_alias=True))
