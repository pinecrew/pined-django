"""
`mixins.Logging` — the one mixin that builds something.

It turns a handful of fields into a whole `dictConfig`: one rotating
handler per logger named in `log_files`, an optional root handler, and a
`NullHandler` for the loggers to be silenced.
"""

import logging.config
import pathlib
import shutil
from typing import Any

from pydantic_settings import SettingsConfigDict

from pined.django.settings import UNSET, DjangoSettings, UnsetType, mixins


class Settings(mixins.Logging, DjangoSettings):
    """
    `mixins.Logging` in the class `configure` would have built for it.
    """

    model_config = SettingsConfigDict(env_prefix="PINEDTEST_", env_file=None)


def build(logs_root: pathlib.Path | UnsetType = UNSET, **fields: Any) -> dict[str, Any]:
    """
    Assemble the settings the way a settings module would.
    """

    return Settings(logs_root=logs_root, **fields).model_dump(by_alias=True)


def test_no_logs_root_leaves_django_alone() -> None:
    """
    Without a directory to write into there is no configuration at all.
    """

    assert "LOGGING" not in build()


def test_the_whole_config(tmp_path: pathlib.Path) -> None:
    """
    Every field, and the `dictConfig` they add up to.

    One comparison for the lot: the single formatter, a handler per named
    logger plus one for the root, handler names, `filename`s under
    `logs_root`, the level everywhere it belongs, `handler_options` merged
    in, the `NullHandler` for the silenced, and the promise not to disturb
    the loggers django and its libraries have already made.
    """

    logs = tmp_path / "deep" / "logs"
    handler = {
        "class": "logging.handlers.RotatingFileHandler",
        "level": "DEBUG",
        "formatter": "verbose",
        "maxBytes": 1024,
        "backupCount": 3,
    }

    dumped = build(
        logs,
        log_files={"myapp.api": "api.log"},
        root_log_file="everything.log",
        ignored_loggers=["PIL"],
        log_level="DEBUG",
        handler_class="logging.handlers.RotatingFileHandler",
        handler_options={"maxBytes": 1024, "backupCount": 3},
        log_format="{message}",
        log_datefmt="%H:%M",
        logging_config="logging.config.dictConfig",
    )

    assert dumped["LOGGING"] == {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"verbose": {"style": "{", "format": "{message}", "datefmt": "%H:%M"}},
        "handlers": {
            "null": {"class": "logging.NullHandler"},
            "myapp.api_file": handler | {"filename": logs / "api.log"},
            "root_file": handler | {"filename": logs / "everything.log"},
        },
        "loggers": {
            "myapp.api": {"handlers": ["myapp.api_file"], "level": "DEBUG", "propagate": False},
            "PIL": {"handlers": ["null"], "propagate": False},
        },
        "root": {"handlers": ["root_file"], "level": "DEBUG"},
    }
    # `LOGGING_CONFIG` names the callable, and is nothing to do with the dict.
    assert dumped["LOGGING_CONFIG"] == "logging.config.dictConfig"
    assert logs.is_dir()


def test_what_is_left_out_stays_out(tmp_path: pathlib.Path) -> None:
    """
    No root file means django's own root logging is left where it was, and
    nothing to silence means no `NullHandler` to declare.
    """

    without_root = build(tmp_path, log_files={"myapp": "app.log"})["LOGGING"]

    assert "root" not in without_root
    assert "root" not in without_root["loggers"]

    without_ignored = build(tmp_path, root_log_file="app.log")["LOGGING"]

    assert "null" not in without_ignored["handlers"]


def test_the_directory_is_made_once_the_settings_are_built(tmp_path: pathlib.Path) -> None:
    """
    `logs_root` appears when the settings do, not when they are dumped.

    `dictConfig` opens every file as it goes, so the directory has to be
    there by the time django configures logging. Making it while building
    the config meant every `model_dump` wrote to disk — a diagnostic dump,
    a comparison in a test, a read-only container.
    """

    logs = tmp_path / "deep" / "logs"
    settings = Settings(logs_root=logs, root_log_file="everything.log")

    assert logs.is_dir()

    shutil.rmtree(logs)
    settings.model_dump(by_alias=True)

    assert not logs.exists()


def test_the_result_is_something_dictconfig_accepts(tmp_path: pathlib.Path) -> None:
    """
    The proof that all of the above adds up to a usable configuration.
    """

    config = build(
        tmp_path,
        log_files={"myapp.api": "api.log"},
        root_log_file="everything.log",
        ignored_loggers=["PIL"],
    )["LOGGING"]

    logging.config.dictConfig(config)

    try:
        logging.getLogger("myapp.api").info("hello")
        assert (tmp_path / "api.log").exists()
    finally:
        logging.config.dictConfig({"version": 1, "disable_existing_loggers": False})
