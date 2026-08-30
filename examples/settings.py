"""
A settings module built out of `pined.django.settings`.

Run anything against it with `DJANGO_SETTINGS_MODULE=examples.settings`.

One class per concern, each carrying only what this project changes.
Everything the mixins declare and nobody overrides stays unset, so django
keeps its own default for it.
"""

import logging
import pathlib

from pined.django.logging import Logger
from pined.django.settings import components, configure, mixins
from pined.django.settings.admin import change_admin_site
from pined.django.settings.contrib.debug_toolbar import DebugToolbar, DebugToolbarSettings, get_debug
from pined.django.settings.contrib.rest_framework import RestFramework, RestFrameworkSettings

BASE_DIR = pathlib.Path(__file__).resolve().parent


class General(mixins.General):
    """
    What the project is, where its entry points live, and when it is.
    """

    secret_key: str = "django-insecure-example"
    root_urlconf: str = "examples.urls"
    time_zone: str = "Etc/UTC"


class Apps(mixins.Apps):
    """
    Django's own apps and middleware, plus this project's.
    """

    installed_apps: list[str] = [*mixins.Apps.CONTRIB_APPS, "pined.django"]
    middleware: list[str] = [*mixins.Apps.CONTRIB_MIDDLEWARE]


class Database(mixins.Database):
    """
    One sqlite file, next to this module.
    """

    databases: components.Databases = components.Databases(
        default=components.Database(url=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
    )


class Auth(mixins.Auth):
    """
    Django's stock password validators, unchanged.
    """

    auth_password_validators: list[components.PasswordValidator] = list(mixins.Auth.PASSWORD_VALIDATORS)


class Templates(mixins.Templates):
    """
    The engine `startproject` configures, unchanged.
    """

    templates: list[components.TemplateEngine] = [mixins.Templates.DJANGO_ENGINE]


class Static(mixins.Static):
    """
    Static files, collected next to this module.
    """

    static_url: str = "static/"
    static_root: pathlib.Path = BASE_DIR / "static"


class Logging(mixins.Logging):
    """
    A file per logger, with everything else landing in `example.log`.
    """

    logs_root: pathlib.Path = BASE_DIR / "logs"
    log_level: mixins.LogLevel = "DEBUG"
    log_files: dict[str, str] = {"examples.web": "web.log", "examples.api": "api.log"}
    root_log_file: str = "example.log"
    ignored_loggers: list[str] = ["PIL"]


class ThirdParty(DebugToolbarSettings, RestFrameworkSettings):
    """
    Two libraries this project would carry, were they installed.

    Their apps belong in `Apps` alongside django's; the settings below
    are inert until then, since the stubs import nothing.
    """

    debug_toolbar_config: DebugToolbar = DebugToolbar(show_toolbar_callback=get_debug)
    rest_framework: RestFramework = RestFramework(
        page_size=25,
        search_param="filter[search]",
        default_permission_classes=["rest_framework.permissions.IsAuthenticated"],
    )


# `EXAMPLE_`-prefixed environment variables are read over the defaults above.
# Nested values take the `__` delimiter, so `EXAMPLE_DATABASES__DEFAULT__URL`
# replaces the connection. `mixins.I18n` goes in unchanged, which leaves the
# languages to django while keeping them open to the environment.
configure(General, Apps, Database, Auth, Templates, Static, mixins.I18n, Logging, ThirdParty, env_prefix="EXAMPLE_")

# Both belong here, after the settings exist and before django reads them:
# `django.setup()` calls `configure_logging()` and then populates the apps, so
# a logger class installed later would not reach the loggers django builds.
logging.setLoggerClass(Logger)
change_admin_site({"auth": ("User", "Group")})
