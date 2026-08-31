"""
The components a settings module assembles django's dicts out of.
"""

from typing import Any

import pydantic
import pytest

from pined.django.settings import (
    Cache,
    Database,
    Databases,
    Mailer,
    PasswordValidator,
    Storage,
    TaskBackend,
    TemplateEngine,
    components,
)

CONNECTION = {
    "USER": "",
    "PASSWORD": "",
    "HOST": "",
    "PORT": "",
    "CONN_MAX_AGE": 0,
    "CONN_HEALTH_CHECKS": False,
    "DISABLE_SERVER_SIDE_CURSORS": False,
}
"""What `dj_database_url` fills in for everything nobody named."""


@pytest.mark.parametrize(
    ("database", "expected"),
    [
        pytest.param(
            Database(url="postgres://user:pw@db:5432/app"),
            CONNECTION
            | {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "app",
                "USER": "user",
                "PASSWORD": "pw",
                "HOST": "db",
                "PORT": 5432,
            },
            id="a-full-url",
        ),
        pytest.param(
            Database(url="sqlite:///db.sqlite3"),
            CONNECTION | {"ENGINE": "django.db.backends.sqlite3", "NAME": "db.sqlite3"},
            id="the-spelling-most-projects-start-on",
        ),
        pytest.param(
            Database(url="postgres://db/app", conn_max_age=600, conn_health_checks=True),
            CONNECTION
            | {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "app",
                "HOST": "db",
                "CONN_MAX_AGE": 600,
                "CONN_HEALTH_CHECKS": True,
            },
            id="pooling-and-health-checks",
        ),
        pytest.param(
            # A url django has no backend for still needs one named.
            Database(url="postgres://db/app", engine="django.contrib.gis.db.backends.postgis"),
            CONNECTION | {"ENGINE": "django.contrib.gis.db.backends.postgis", "NAME": "app", "HOST": "db"},
            id="an-engine-by-name",
        ),
        pytest.param(
            Database(url="postgres://db/app", ssl_require=True, test_options={"NAME": "other"}),
            CONNECTION
            | {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "app",
                "HOST": "db",
                "OPTIONS": {"sslmode": "require"},
                "TEST": {"NAME": "other"},
            },
            id="ssl-and-a-test-database",
        ),
    ],
)
def test_a_database_serializes_the_way_django_wants_it(database: Database, expected: dict[str, Any]) -> None:
    """
    A url comes out as the connection dict, via `dj_database_url`.
    """

    assert database.model_dump() == expected


def test_databases_keeps_its_alias_lower_cased() -> None:
    """
    `DATABASES` is keyed by connection alias, and django wants `default`.
    """

    assert set(Databases(default=Database(url="sqlite:///db.sqlite3")).model_dump()) == {"default"}


COMPONENTS = [
    pytest.param(
        TemplateEngine(backend="django.template.backends.django.DjangoTemplates", app_dirs=True),
        {"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True},
        id="template-engine",
    ),
    pytest.param(
        PasswordValidator(name="django.contrib.auth.password_validation.MinimumLengthValidator"),
        {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
        id="password-validator",
    ),
    pytest.param(
        Cache(backend="django.core.cache.backends.locmem.LocMemCache", location="unique-snowflake"),
        {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "unique-snowflake"},
        id="cache",
    ),
    pytest.param(
        # Some backends want a list of servers.
        Cache(
            backend="django.core.cache.backends.memcached.PyMemcacheCache",
            location=["a:11211", "b:11211"],
        ),
        {
            "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
            "LOCATION": ["a:11211", "b:11211"],
        },
        id="cache-with-several-locations",
    ),
    pytest.param(
        # `MAX_ENTRIES` has no key of its own — it is an option.
        Cache(backend="django.core.cache.backends.locmem.LocMemCache", options={"MAX_ENTRIES": 2000}),
        {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "OPTIONS": {"MAX_ENTRIES": 2000}},
        id="cache-with-entry-limits",
    ),
    pytest.param(
        Storage(backend="django.core.files.storage.FileSystemStorage"),
        {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        id="storage",
    ),
    pytest.param(
        TaskBackend(backend="django.tasks.backends.immediate.ImmediateBackend", queues=["default"]),
        {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend", "QUEUES": ["default"]},
        id="task-backend",
    ),
    pytest.param(
        # `options` belongs to the backend: for smtp it takes the `EMAIL_*`
        # settings `MAILERS` replaces, lower-cased and unprefixed.
        Mailer(
            backend="django.core.mail.backends.smtp.EmailBackend",
            options={"host": "smtp.example.net", "use_tls": True},
        ),
        {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {"host": "smtp.example.net", "use_tls": True},
        },
        id="mailer",
    ),
]


@pytest.mark.parametrize(("component", "expected"), COMPONENTS)
def test_a_component_dumps_upper_cased_and_without_the_unset(component: Any, expected: dict[str, Any]) -> None:
    """
    Every component is a `DjangoModel`, so both rules apply to all of them.
    """

    assert component.model_dump(by_alias=True) == expected


def test_every_component_is_accounted_for() -> None:
    """
    A new component has to be added to the table above, not slip past it.

    `Database` and `Databases` are the two that are not `DjangoModel`s and
    have tests of their own, so they are named here rather than in the table.
    """

    declared = {
        value
        for value in vars(components).values()
        if isinstance(value, type) and issubclass(value, pydantic.BaseModel) and value.__module__ == components.__name__
    }
    covered = {type(case.values[0]) for case in COMPONENTS} | {Database, Databases}

    assert declared == covered
