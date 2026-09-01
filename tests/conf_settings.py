"""
Settings for the run with only the `settings` extra installed.

`tests.conf` cannot serve: it installs `tests.testapp`, whose models
declare a `PydanticField` — and importing one pulls in
`json_schema_to_pydantic`, which belongs to the other extra. Everything
else in `tests/settings` is about models and serialization, and needs
neither.
"""

from tests.conf import *  # noqa: F403

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.admin",
    "pined.django",
]
