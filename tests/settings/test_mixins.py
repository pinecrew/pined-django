"""
The mixins — what each one brings before a project touches it.

A mixin's whole job is to declare django's settings surface and stay out
of the way, so the interesting assertion is that almost nothing arrives
unasked. The few defaults that do are the ones the library takes a
position on.
"""

from typing import Any

import pytest

from pined.django.settings import DropUnset, components, configure, mixins

EXPECTED_DEFAULTS: dict[str, dict[str, Any]] = {
    "General": {},
    "Apps": {},
    "Database": {},
    "Auth": {},
    "Session": {"SESSION_COOKIE_SAMESITE": "Lax"},
    "Csrf": {"CSRF_COOKIE_SAMESITE": "Lax"},
    "Security": {
        "SECURE_CROSS_ORIGIN_OPENER_POLICY": "same-origin",
        "SECURE_REFERRER_POLICY": "same-origin",
    },
    "Email": {},
    "Templates": {},
    "Static": {},
    "Uploads": {"FILE_UPLOAD_PERMISSIONS": 0o644},
    "I18n": {},
    "Formats": {},
    "Cache": {},
    "Logging": {
        "LOG_LEVEL": "INFO",
        "LOG_FORMAT": "{levelname} {asctime} {funcName} {message}",
        "LOG_DATEFMT": "%Y-%m-%d %H:%M:%S %z",
        "HANDLER_CLASS": "logging.handlers.TimedRotatingFileHandler",
        "HANDLER_OPTIONS": {"when": "midnight", "backupCount": 10},
        "LOG_FILES": {},
        "IGNORED_LOGGERS": [],
    },
    "Messages": {},
    "Tasks": {},
    "Testing": {},
}


def test_every_mixin_is_accounted_for() -> None:
    """
    A new mixin has to be added to the table above, not slip past it.
    """

    declared = {
        name
        for name, value in vars(mixins).items()
        if isinstance(value, type) and issubclass(value, DropUnset) and value.__module__ == mixins.__name__
    }

    assert declared == set(EXPECTED_DEFAULTS)


@pytest.mark.parametrize(("name", "expected"), EXPECTED_DEFAULTS.items())
def test_a_bare_mixin_brings_only_what_it_stands_behind(name: str, expected: dict[str, Any]) -> None:
    """
    Everything else stays unset, so django keeps its own default.
    """

    settings = configure(getattr(mixins, name), env_prefix="PINEDTEST_", env_file=None)

    assert settings.model_dump(by_alias=True) == expected


def test_a_mixin_on_its_own_is_not_a_settings_class() -> None:
    """
    The upper-casing arrives with `DjangoSettings`, not with the mixin.

    A mixin is a part — it declares fields and drops the unset ones, and
    leaves the aliasing to whatever `configure` builds around it.
    """

    assert mixins.Session().model_dump(by_alias=True) == {"session_cookie_samesite": "Lax"}


def test_the_classvars_a_project_splats_in() -> None:
    """
    The lists and tuples a project reaches for instead of transcribing.

    Middleware order is the whole content of that setting, and the password
    validators arrive as components rather than as dicts to be copied out.
    """

    assert mixins.Apps.CONTRIB_APPS[0] == "django.contrib.admin"
    assert "django.contrib.staticfiles" in mixins.Apps.CONTRIB_APPS
    assert [*mixins.Apps.CONTRIB_APPS, "myapp"][-1] == "myapp"

    middleware = mixins.Apps.CONTRIB_MIDDLEWARE
    assert middleware.index("django.contrib.sessions.middleware.SessionMiddleware") < middleware.index(
        "django.contrib.auth.middleware.AuthenticationMiddleware"
    )

    validators = mixins.Auth.PASSWORD_VALIDATORS
    assert all(isinstance(validator, components.PasswordValidator) for validator in validators)
    assert (
        next(iter(validators)).model_dump(by_alias=True)["NAME"].startswith("django.contrib.auth.password_validation.")
    )


def test_the_django_template_engine() -> None:
    """
    Taken as-is it needs no arguments, and copying it leaves it alone.

    The copy is the idiom the docstring recommends for adding a template
    directory.
    """

    dumped = mixins.Templates.DJANGO_ENGINE.model_dump(by_alias=True)

    assert dumped["BACKEND"] == "django.template.backends.django.DjangoTemplates"
    assert dumped["APP_DIRS"] is True
    assert dumped["OPTIONS"]["context_processors"] == list(mixins.Templates.CONTEXT_PROCESSORS)

    engine = mixins.Templates.DJANGO_ENGINE.model_copy(update={"dirs": ["templates"]})

    assert engine.model_dump(by_alias=True)["DIRS"] == ["templates"]
    assert mixins.Templates.DJANGO_ENGINE.dirs is None
