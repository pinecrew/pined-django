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


def build_settings(*parts: type[BaseModel], **config: Unpack[SettingsConfigDict]) -> DjangoSettings:
    """
    Assembles the settings out of `parts` and hands them back.

    A project's settings class carries nothing but its bases and a
    `model_config`, which is a class statement's worth of ceremony for
    two pieces of information. What a settings module wants is
    `configure`, which does this and then writes the result out; this is
    the same assembly with nothing written anywhere, for a test or a
    script that only means to look.

    Args:
        *parts: The mixins, in precedence order — earlier ones win.
        **config: `SettingsConfigDict` keys, `env_prefix` chief among them.

    Returns:
        The settings.

    Example:
        ```
        build_settings(General, Apps, Database, env_prefix="MYPROJECT_")
        ```
    """

    namespace = {"model_config": SettingsConfigDict(**config)}
    # A part that is already a `DjangoSettings` is the base; naming it twice
    # would re-apply its own `model_config` over whatever the part set.
    bases = parts if any(issubclass(part, DjangoSettings) for part in parts) else (*parts, DjangoSettings)
    settings_cls: type[DjangoSettings] = type("ProjectSettings", bases, namespace)
    return settings_cls()


def configure(*parts: type[BaseModel], **config: Unpack[SettingsConfigDict]) -> DjangoSettings:
    """
    Assembles the settings out of `parts` and fills the calling module.

    Belongs at the top level of a settings module, and nowhere else —
    filling a module is the whole of what it adds to `build_settings`.

    Args:
        *parts: The mixins, in precedence order — earlier ones win.
        **config: `SettingsConfigDict` keys, `env_prefix` chief among them.

    Returns:
        The settings, already spread over the module's globals.

    Raises:
        RuntimeError: Called from anywhere but the top level of a module.

    Example:
        ```
        configure(General, Apps, Database, env_prefix="MYPROJECT_")
        ```
    """

    project_settings = build_settings(*parts, **config)

    # The settings module sits one frame back up the stack:
    # 0. configure()
    # 1. <settings module>
    #
    # A module frame is the one whose locals are its globals. Anywhere else
    # — a function, a class body — there is nothing to fill, and writing
    # regardless would mean writing into whatever `f_locals` happens to be:
    # a snapshot nobody reads, until PEP 667 made it a write-through proxy
    # in 3.13 and the same call started rewriting the caller's variables.
    frame = sys._getframe(1)
    if frame.f_locals is not frame.f_globals:
        msg = (
            "configure() fills the globals of the settings module it is called from, "
            "and there is no module here to fill. Use build_settings() to assemble "
            "the settings without writing them anywhere."
        )
        raise RuntimeError(msg)

    frame.f_globals.update(project_settings.model_dump(by_alias=True))

    return project_settings
