"""
Settings for the run with the optional extras left out.

`tests.conf` cannot serve: it installs `tests.testapp`, whose models
declare a `PydanticField`, and that is the one thing a bare install has
no way to import.
"""

SECRET_KEY = "django-insecure-tests"
USE_TZ = True

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    # Shadows django's own `makemigrations`/`migrate` — with django's own, here.
    "pined.django",
]
