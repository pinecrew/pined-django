import sys

from pydantic_settings import BaseSettings, SettingsConfigDict

from .utils import alias_generator


class DjangoSettings(BaseSettings):
    """
    Base class for a django project's settings.
    """

    model_config = SettingsConfigDict(alias_generator=alias_generator)

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
