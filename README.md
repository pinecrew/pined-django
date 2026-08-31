# pined-django

*The missing pieces of Django, for perfectionists with deadlines.*

[![CI](https://github.com/pinecrew/pined-django/actions/workflows/ci.yml/badge.svg)](https://github.com/pinecrew/pined-django/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/coverallsCoverage/github/pinecrew/pined-django)](https://coveralls.io/github/pinecrew/pined-django)
[![PyPI](https://img.shields.io/pypi/v/pined-django.svg)](https://pypi.org/project/pined-django/)
[![Python](https://img.shields.io/pypi/pyversions/pined-django.svg)](https://pypi.org/project/pined-django/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Django stays out of your way right up until it doesn't. Has your settings module
grown into a thousand untyped constants? Do you re-validate a `JSONField`'s
contents on every read? Has the start-up sequence become a pile of unrelated
commands, or a shell script nobody wants to touch? Does configuring logging
still give you a headache?

`pined-django` is the parts you were going to write anyway.

- **Settings that type-check.** Django's whole settings surface as models:
  composed per concern, read from the environment, validated before the first
  request.
- **Pydantic models in the database.** A field that gives back validated
  instances — and writes its own data migrations when the model changes shape.
- **Commands the start-up sequence needs.** Chain commands, create the
  superuser, measure uptime that outlives a worker.
- **The small things.** Logger names worth grepping, admin ordering, control
  over related-field widgets.

Take one piece or all of them. Installing the package pulls in nothing but
Django, and every module stands on its own.

## Installation

```bash
pip install pined-django
```

The settings and the model field carry their own dependencies:

```bash
pip install "pined-django[settings]"        # pydantic-settings, dj-database-url
pip install "pined-django[pydantic-field]"  # pydantic, json-schema-to-pydantic
```

Add the app to reach the management commands:

```python
INSTALLED_APPS = [..., "pined.django"]
```

Works on Python 3.12+ and [Django](https://www.djangoproject.com/) 5.2+.

## What's inside

### Settings

A settings module, composed from the concerns your project actually varies:

```python
import pathlib

from pined.django.settings import components, configure, mixins

BASE_DIR = pathlib.Path(__file__).resolve().parent


class General(mixins.General):
    secret_key: str = "django-insecure-example"
    root_urlconf: str = "myproject.urls"
    time_zone: str = "Etc/UTC"


class Apps(mixins.Apps):
    installed_apps: list[str] = [*mixins.Apps.CONTRIB_APPS, "pined.django", "myapp"]
    middleware: list[str] = [*mixins.Apps.CONTRIB_MIDDLEWARE]


class Database(mixins.Database):
    databases: components.Databases = components.Databases(
        default=components.Database(url=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
    )


class Templates(mixins.Templates):
    templates: list[components.TemplateEngine] = [mixins.Templates.DJANGO_ENGINE]


configure(General, Apps, Database, Templates, env_prefix="MYPROJECT_")
```

That is a complete settings module. `SECRET_KEY`, `DATABASES`, `TEMPLATES` and
the rest land in it upper-cased, and the environment wins over every default:

```bash
export MYPROJECT_SECRET_KEY="the real one"
export MYPROJECT_DATABASES__DEFAULT__URL="postgres://user:pw@db:5432/app"
export MYPROJECT_DEBUG=false
```

The prefix keeps the project's own variables apart from everything else sharing
the deployment's environment.

#### Unset means unset

The one place this departs from a plain settings module. A settings file that
reads its own environment:

```python
X_FRAME_OPTIONS = os.environ.get("X_FRAME_OPTIONS")
```

With the variable unset that writes `None`, and Django's own `"DENY"` is gone.
Libraries lose their defaults the same way — they look their settings up with
`getattr(settings, name, default)`, and the `None` sitting in the module is
handed back instead.

As a model, a field that comes out `None` is never written at all:

```python
class Security(mixins.Security):
    x_frame_options: str | None = None      # absent, so Django's default DENY stands
```

`MYPROJECT_X_FRAME_OPTIONS=SAMEORIGIN` sets it. Nothing else touches it.

Where `None` is a value in its own right — a cookie with no `SameSite`, a file
mode Django shouldn't force — the mixin says so, and it reaches Django intact.

|                       | Constants in a module      | `pined.django.settings`                                 |
| --------------------- | -------------------------- | ------------------------------------------------------- |
| Bad value             | breaks when the code runs  | breaks at start-up                                      |
| Environment           | `os.environ` and hand-cast | typed, nested, `.env`                                   |
| Unset vs `None`       | the same thing             | different things                                        |
| Reuse across projects | copy the file              | import a mixin                                          |
| Misspelled name       | a stray global, ignored    | a stray setting, ignored — but the editor completes the real ones |
| Cost                  | none                       | a dependency, and a layer between you and Django's docs |

### PydanticField

A `JSONField` that reads and writes validated
[Pydantic](https://docs.pydantic.dev/) model instances instead of dicts:

```python
import pydantic
from django.db import models
from pined.django.db.models import PydanticField


class EmailSettings(pydantic.BaseModel):
    host: str = "localhost"
    port: int = 25
    use_tls: bool = True


class Options(models.Model):
    email = PydanticField(EmailSettings)
```

```python
options = Options.objects.first()
options.email.port          # 25, an int, on an EmailSettings instance
options.email = {"host": "smtp.example.com", "port": 587}   # validated on the way in
options.save()
```

Change the model, and `makemigrations` writes the data migration for you:

```python
class EmailSettings(pydantic.BaseModel):
    host: str = "localhost"
    port: int = 25
    use_tls: bool = True
    timeout: float = 10.0       # new
```

```
$ python manage.py makemigrations myapp
Migrations for 'myapp':
  myapp/migrations/0002_revalidate_options_email.py
    ~ Revalidate data in options.email
```

```python
# myapp/migrations/0002_revalidate_options_email.py — generated
operations = [
    pined.django.db.migrations.AlterPydantic(
        model_name="options",
        name="email",
        schema_hash="9c6d8bf79fa52b7a",
        previous_schema_hash="aa233cc7fafb703b",
    ),
]
```

Every stored row is re-read, given the new field, and revalidated. Rolling the
migration back does the same in reverse. The schemas are written into the
`migrations` directory, since they are part of the migration — commit them with
it.

Two shapes of Pydantic model do not survive that round trip, and `manage.py
check` says so rather than letting a migration find out:

```
$ python manage.py check
myapp.Options.email: (pined.django.E001) Pydantic field 'EmailSettings.host' has an alias.
myapp.Options.tree: (pined.django.E002) Pydantic model 'Node' has a reference cycle: Node -> child -> Node.
```

A value is dumped by field name while the recorded schema names that same field
by its alias, so data and schema disagree; and a schema referring to itself
cannot be rebuilt into the historical model an `AlterPydantic` works against.
Both checks look through nested models as well. Where either shape is
unavoidable, a plain `JSONField` still takes the data.

### Management commands

Three commands for the part of a deployment that lives outside Django: the
entrypoint script.

`chain` runs commands in sequence — Django's own or the shell's — so a container
entrypoint is one line instead of a script:

```bash
python manage.py chain --manage 'migrate --noinput' --shell 'npm run build'
```

`create_admin` creates the superuser from flags instead of a prompt, so it can
run unattended. Its arguments come from your user model, custom or not:

```bash
python manage.py create_admin --username admin --password secret --email admin@example.com
```

`uptime` answers "how long has this deployment been up?" — which process uptime
cannot, since the application server recycles workers all day. Stamp once at
start-up, read it from anywhere afterwards:

```bash
python manage.py uptime -s      # at the top of the sequence
python manage.py uptime         # 4 days, 1:04:35.271442 — cheap enough for a healthcheck
```

Together, a whole start-up sequence. `--allow-failure` marks the step that is
allowed to fail — the superuser already exists on every deploy after the first:

```bash
python manage.py chain \
    --manage 'migrate --noinput' \
    --manage 'collectstatic --noinput' \
    --manage 'create_admin -u $ADMIN_USER -p $ADMIN_PASSWORD -e $ADMIN_EMAIL' --allow-failure \
    --manage 'uptime -s'
```

### Logging

`Logger` is a drop-in `logging.Logger` that shows the fully qualified name of
the caller. One line in the settings module puts it behind every logger Django
builds:

```python
import logging

from pined.django.logging import Logger

logging.setLoggerClass(Logger)
```

`%(funcName)s` then resolves to `module.Class.method` rather than a bare
function name, which is the difference between a log line you can grep for and
one you have to go looking for:

```
INFO 2026-08-30 12:00:00 +0000 post                          order 41 accepted
INFO 2026-08-30 12:00:00 +0000 myapp.api.OrderView.post      order 41 accepted
```

Nothing else changes: no new format string, no call sites touched.

### Admin

Order the index the way the business reads it, not alphabetically:

```python
change_admin_site({
    "shop": ("Order", "Customer", "Product"),
    "cms": ("Page", "Menu"),
})
```

Take the add/change/delete/view actions off a related field with
`hide_related_actions`:

```python
@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    def get_form(self, request, *args, **kwargs):
        form = super().get_form(request, *args, **kwargs)
        hide_related_actions(form.base_fields["author"])
        hide_related_actions(form.base_fields["genre"], can_view=True)
        return form
```

### Utilities

`get_nested` digs a value out of a payload whose shape you don't control — or
one you would rather not wrap in `if...else` and `try...except` to reach. A
single path walks dicts by key, lists by index and objects by attribute, in any
combination, and `default` comes back at the first step that doesn't resolve.
Think of it as a *Maybe* chain over the whole path, with `default` where it
gives out:

```python
get_nested(payload, "data", "items", 0, "name", default="")
```

`JSONEncoder` is Django's own with two habits fixed: Pydantic models serialize
through `model_dump` instead of raising, and non-ASCII stays readable in the
database rather than becoming `\u0441`. `PydanticField` uses it already; a plain
`JSONField` is worth pointing at it too:

```python
from pined.django.serializers.json import JSONEncoder

notes = models.JSONField(encoder=JSONEncoder)
```

---

## Usage

### `pined.django.settings`

#### Composing a module

`configure(*parts, **model_config)` builds the settings class out of `parts`,
reads the environment over their defaults, and fills the calling module. Parts
are in precedence order — the first one wins a clash. The keyword arguments are
[`SettingsConfigDict`](https://docs.pydantic.dev/latest/api/pydantic_settings/)
keys.

```python
configure(General, Apps, Database, env_prefix="MYPROJECT_", env_file=".env.local")
```

Settings of the project's own, and checks across them, go in a part like
everything else. Extend the part holding the fields the check needs, and pass
it in place of that part — here `General` from the example above:

```python
import pydantic


class Reporting(General):
    sentry_dsn: str | None = None       # lands as SENTRY_DSN

    @pydantic.model_validator(mode="after")
    def no_debug_where_reported(self) -> "Reporting":
        if self.debug and self.sentry_dsn:
            msg = "DEBUG must be off wherever Sentry is configured"
            raise ValueError(msg)
        return self


configure(Reporting, Apps, Database, Templates, env_prefix="MYPROJECT_")
```

Cross-field checks are worth the trouble: they run before the first request,
so a misconfigured deployment fails at start-up rather than in production.

`configure` is the only thing that fills a module, so it belongs at the bottom
of `settings.py`. It returns the settings as well, which is what tests want —
instantiating a class built by hand fills nothing.

#### The mixins

| Mixin       | Covers                                                                    |
|-------------|---------------------------------------------------------------------------|
| `General`   | `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, URLconf, WSGI / ASGI, `TIME_ZONE` |
| `Apps`      | `INSTALLED_APPS`, `MIDDLEWARE`                                            |
| `Database`  | `DATABASES`, routers, `DEFAULT_AUTO_FIELD`                                |
| `Auth`      | user model, backends, password validators, login URLs                     |
| `Session`   | the session backend and its cookie                                        |
| `Csrf`      | CSRF protection and its cookie                                            |
| `Security`  | `SecurityMiddleware` headers, SSL, proxy headers                          |
| `Email`     | `MAILERS`, the mail backend and the addresses Django sends from           |
| `Templates` | `TEMPLATES`, `FORM_RENDERER`                                              |
| `Static`    | static and media files, `STORAGES`                                        |
| `Uploads`   | limits and permissions for incoming files                                 |
| `I18n`      | languages and the locale cookie                                           |
| `Formats`   | how dates and numbers are rendered and parsed                             |
| `Cache`     | `CACHES` and the caching middleware                                       |
| `Logging`   | `LOGGING`, assembled from parts                                           |
| `Messages`  | `django.contrib.messages`                                                 |
| `Tasks`     | `TASKS` (new in Django 6.0)                                               |
| `Testing`   | the test runner and what it loads                                         |

Together they cover every setting in Django's `global_settings`, plus the ones
that have no default there at all — `ROOT_URLCONF`, `ASGI_APPLICATION`,
`SITE_ID`, `MESSAGE_LEVEL`, `MESSAGE_TAGS`, `EMAIL_FILE_PATH` and `MAILERS`,
which stay absent unless set.

Take only what the project varies. A mixin passed to `configure` unchanged still
leaves its settings open to the environment, which is often reason enough to
include one.

Order-sensitive lists come as class attributes to splat rather than defaults to
override, so a project inserts into the middle of them:

```python
installed_apps: list[str] = [*mixins.Apps.CONTRIB_APPS, "myapp"]
```

Constants `Apps.CONTRIB_APPS`, `Apps.CONTRIB_MIDDLEWARE`,
`Auth.PASSWORD_VALIDATORS`, `Templates.DJANGO_ENGINE` and
`Templates.CONTEXT_PROCESSORS` are what `startproject` would have written into
the corresponding parameters. `DJANGO_ENGINE` takes a
`.model_copy(update={"dirs": [...]})` where an entry needs one key changed.

They are plain tuples with no logic behind them, so splatting one gives you
Django's order and nothing else. Reordering Django's own entries means writing
the list out in full.

#### Components

Settings with structure get a model instead of a raw dict:

| Component           | One entry of                       |
|---------------------|------------------------------------|
| `Database`          | a connection, parsed from a URL    |
| `Databases`         | `DATABASES`; `default` is required |
| `TemplateEngine`    | `TEMPLATES`                        |
| `PasswordValidator` | `AUTH_PASSWORD_VALIDATORS`         |
| `Cache`             | `CACHES`                           |
| `Storage`           | `STORAGES`                         |
| `Mailer`            | `MAILERS` (new in Django 6.1)      |
| `TaskBackend`       | `TASKS` (new in Django 6.0)        |

`Database` hands its URL to
[`dj-database-url`](https://github.com/jazzband/dj-database-url), which is
where the syntax comes from.

Django 6.1 added `MAILERS` to replace the `EMAIL_*` backend settings, which
Django 7.0 removes. `Mailer` is one entry of it — one per sender, and `options`
takes the backend's own keys, which for smtp are the settings it supersedes,
lower-cased and unprefixed:

```python
class Email(mixins.Email):
    mailers: dict[str, components.Mailer] = {
        "default": components.Mailer(
            backend="django.core.mail.backends.smtp.EmailBackend",
            options={"host": "smtp.example.net", "use_tls": True},
        ),
        "newsletters": components.Mailer(
            backend="django.core.mail.backends.console.EmailBackend",
        ),
    }
    default_from_email: str = "noreply@example.net"
```

```python
class Cache(mixins.Cache):
    caches: dict[str, components.Cache] = {
        "default": components.Cache(
            backend="django.core.cache.backends.redis.RedisCache",
            location="redis://127.0.0.1:6379",
        ),
    }
```

For a block of your own — a third-party library's dict, or a project's own
settings — subclass `DjangoModel`, which upper-cases its keys and drops what is
unset. It becomes a setting through a part of its own, and a part is any model
built on `DropUnset`:

```python
from pydantic import BaseModel

from pined.django.settings import DjangoModel, DropUnset


class Payments(DjangoModel):
    api_key: str
    currency: str = "EUR"
    timeout: float | None = None            # absent from PAYMENTS unless set


class Billing(DropUnset, BaseModel):
    payments: Payments = Payments(api_key="")   # lands as PAYMENTS
    invoice_prefix: str | None = None           # lands as INVOICE_PREFIX


configure(General, Apps, Database, Billing, env_prefix="MYPROJECT_")
```

`MYPROJECT_PAYMENTS__API_KEY` reaches into it like any other component.

#### Environment

`pined-django` inherits pydantic-settings' resolution, configured with an
`env_nested_delimiter` of `__` and `.env` as the `env_file`. Set `env_prefix`
per project.

```bash
MYPROJECT_ALLOWED_HOSTS='["app.example.com"]'      # JSON for lists and dicts
MYPROJECT_DATABASES__DEFAULT__CONN_MAX_AGE=600     # __ reaches into a component
```

Unknown variables under the prefix are ignored, so an environment shared with
other services is safe to read.

#### Keeping a `None`

A field whose `None` must reach Django goes in that model's `KEEP_NONE`. The
mixins already do this for `SESSION_COOKIE_SAMESITE`, `CSRF_COOKIE_SAMESITE`,
`SECURE_REFERRER_POLICY`, `SECURE_CROSS_ORIGIN_OPENER_POLICY` and
`FILE_UPLOAD_PERMISSIONS` — the settings where "no value" is itself a value.

#### Logging

`mixins.Logging` builds the whole `dictConfig` from the parts projects vary.
Each entry of `log_files` gets a rotating handler, and the logger it is keyed by
writes there and nowhere else:

```python
class Logging(mixins.Logging):
    logs_root: pathlib.Path = BASE_DIR / "logs"
    log_level: mixins.LogLevel = "INFO"
    log_files: dict[str, str] = {"myapp.web": "web.log", "myapp.api": "api.log"}
    root_log_file: str = "myproject.log"
    ignored_loggers: list[str] = ["PIL"]        # handed a NullHandler
```

`handler_class` and `handler_options` choose the handler and its keys
(`TimedRotatingFileHandler` at midnight, keeping ten, by default); `log_format`
and `log_datefmt` set the single formatter. `logs_root` left unset produces no
`LOGGING` at all, leaving Django's own configuration alone.

The directory is created when the config is built, since `dictConfig` opens
every file as it goes.

#### Third-party stubs

`pined.django.settings.contrib` holds settings models for libraries projects
often carry: [`axes`](https://github.com/jazzband/django-axes),
[`debug_toolbar`](https://github.com/jazzband/django-debug-toolbar),
[`easyaudit`](https://github.com/soynatan/django-easy-audit),
[`rest_framework`](https://www.django-rest-framework.org/) and
[`unfold`](https://github.com/unfoldadmin/django-unfold). Field names follow
each library's own defaults, values stay unset, and no stub imports the library
it describes — so it costs nothing until that library arrives.

```python
from pined.django.settings.contrib.debug_toolbar import DebugToolbar, DebugToolbarSettings, get_debug
from pined.django.settings.contrib.rest_framework import RestFramework, RestFrameworkSettings


class ThirdParty(DebugToolbarSettings, RestFrameworkSettings):
    debug_toolbar_config: DebugToolbar = DebugToolbar(show_toolbar_callback=get_debug)
    rest_framework: RestFramework = RestFramework(
        page_size=25,
        default_permission_classes=["rest_framework.permissions.IsAuthenticated"],
    )
```

Import the classes, not the module: a field has to be named after the setting it
becomes, so `unfold: unfold.Unfold` would rebind the module name before the
annotation is read.

`get_debug` is the toolbar's `show_toolbar_callback`, asking for `is_staff` once
`DEBUG` is off, so the toolbar stays reachable in staging without opening it to
the world.

### `pined.django.db.models`

```python
PydanticField(model, verbose_name=None, name=None, encoder=None, decoder=None, default=..., **kwargs)
```

Everything a `JSONField` takes, plus the Pydantic `model` as the first argument.
`encoder` defaults to `pined.django.serializers.json.JSONEncoder`.

Declared without a `default`, the field tries to instantiate `model` with no
arguments. Where every field of the model has a default of its own that
succeeds, and `model` becomes the field's default factory. Otherwise the field
is left without a default, exactly as a bare `JSONField` would be.

`model` is checked at `manage.py check` time: an aliased field anywhere in it
raises `pined.django.E001`, a reference cycle `pined.django.E002`.

### `pined.django.db.migrations`

The bundled `makemigrations` and `migrate` management commands swap in an
autodetector that notices a Pydantic model changing shape and writes
`AlterPydantic`. They are what `"pined.django"` in `INSTALLED_APPS` provides,
and they fall through to Django's own commands when `pydantic` is not installed.

Each field's schema versions are kept in a `_schema_<model>__<field>.json`
beside that app's migrations, keyed by hash. It is how an old shape and a new
one can both be reconstructed later, so commit it along with the migration.

A "change of shape" is whatever changes what the model accepts: fields added,
removed or retyped, defaults, constraints, aliases, `extra`. Renaming the model,
rewriting its docstring, documenting a field, reordering the field declarations
or the members of a `Literal` — none of those count, and none of them will
rewrite a table.

```python
AlterPydantic(
    model_name,                 # the django model, e.g. "options"
    name,                       # the PydanticField on it, e.g. "email"
    schema_hash,                # the schema being migrated to
    previous_schema_hash=None,  # left out when the field is new
    forwards_defaults=None,
    backwards_defaults=None,
    forwards_transform=None,
    backwards_transform=None,
    override_fields=None,
)
```

`forwards_defaults` and `backwards_defaults` backfill values. Alongside plain
values they take three helpers, which resolve in the order `F`, `R`, `P` — so
`P` can read what the other two just produced. `F` copies from another *Django*
model field, `R` renames a field of the *Pydantic* model, and `P` is `F` for the
*Pydantic* model:

| Helper          | Takes the value from                                                                                      |
|-----------------|-----------------------------------------------------------------------------------------------------------|
| `F("field")`    | another field of the *Django* model; a dotted path reaches inside a nested `PydanticField` or `JSONField` |
| `R("old_name")` | the Pydantic field it is renaming, value untouched                                                        |
| `P("field")`    | another field of the *same* Pydantic model                                                                |

```python
from pined.django.db.migrations import AlterPydantic, F, P, R

AlterPydantic(
    model_name="terminal",
    name="metadata",
    schema_hash="3a14deee5c255329",
    forwards_defaults={
        "current_software_version": F("current_software_version"),
        "android_version": R("os_version"),
        "also_version": P("android_version"),
        "update_attempts": F("extra.software.update_attempts"),
    },
)
```

A backfilled value lands only where the row has none or still holds the Pydantic
default. To overwrite regardless, name the field in `override_fields`, or pass
`"*"` for all of them — but take care: **this replaces data your users
entered**. On a field being created for the first time, `forwards_defaults`
always wins over the model's own defaults.

For what defaults can't express — dropping a field, computing one from several —
`forwards_transform` and `backwards_transform` take a function over the raw JSON
value. They run last.

```python
from pined.django.db.migrations import AlterPydantic, P

def drop_legacy_version(data: dict[str, Any]) -> dict[str, Any]:
    data.pop("current_software_version", None)
    return data

AlterPydantic(
    model_name="terminal",
    name="metadata",
    schema_hash="92ce2171086e292a",
    previous_schema_hash="3a14deee5c255329",
    forwards_defaults={
        "software_version": P("current_software_version"),
    },
    forwards_transform=drop_legacy_version,
)
```

### Management commands

Available once `"pined.django"` is in `INSTALLED_APPS`.

#### `chain`

```bash
python manage.py chain --manage 'migrate --noinput' --shell 'npm run build' --allow-failure
```

Runs commands in order, `--manage` through Django's own dispatcher and `--shell`
through the shell. Each command sits in one quoted string, or the parser tries
to read its arguments as its own.

`--allow-failure` belongs to the command immediately before it, and lets the
chain outlive that command's failure; the traceback is printed and the chain
carries on. Without it the chain stops and the exit code is non-zero.

To reach an environment variable from a management command, write `$NAME`: it is
substituted from the environment, and empty when unset. Shell commands get that
from the shell itself.

#### `create_admin`

```bash
python manage.py create_admin --username admin --password secret --email admin@example.com
```

Arguments are derived from the user model — `USERNAME_FIELD`, `password` and
everything in `REQUIRED_FIELDS` — so a custom user model needs no configuration.
Each gets a short flag where its initial is free.

Under `DEBUG` every argument has a default, keyed by field type, and the command
runs bare. Otherwise every argument is required.

Failures are reported, never raised. The command is built for a start-up
sequence, where "that user already exists" must not stop the steps after it; the
cost is that **a genuinely broken database also passes quietly**.

#### `uptime`

```bash
python manage.py uptime -s      # stamp, at the top of the start-up sequence
python manage.py uptime         # 4 days, 1:04:35.271442
python manage.py uptime --filename
```

Process uptime answers the wrong question when gunicorn or uvicorn recycles
workers — a worker is routinely younger than the application. `uptime` stamps a
file and measures against its mtime instead.

The path is derived from `DJANGO_SETTINGS_MODULE`, which every entry point
resolves alike, and sits in a temp directory shared by every process on the
host. `--path` overrides it, which a `settings.configure()` setup needs, since
that leaves no settings module to name the file after.

#### `makemigrations`, `migrate`

Django's own, with the `PydanticField` autodetector in front. Be aware that any
`pydantic` in the environment turns it on; without one, the commands are
Django's, unchanged.

### `pined.django.logging`

`Logger` fills `funcName` with `module.Class.method` rather than a bare function
name, so a format string needs nothing else to locate a call.

Install it at the bottom of the settings module. `django.setup()` configures
logging before it populates the apps, so a class installed any later never
reaches the loggers Django has already built:

```python
import logging

from pined.django.logging import Logger

configure(General, Apps, Database)
logging.setLoggerClass(Logger)
```

### `pined.django.settings.admin`

```python
change_admin_site(admin_app_order: dict[str, Sequence[str]])
```

Orders the apps and models on the admin index. Apps are named by `label`, models
by class name. Whatever is left out keeps its default order, after everything
named. The app currently being viewed is moved to the top.

Call it after the settings exist — the bottom of the settings module.

```python
from pined.django.settings.admin import change_admin_site

configure(General, Apps, Database)
change_admin_site({"media": ("Artist", "Album", "Song"), "books": ("Author", "Book")})
```

### `pined.django.admin`

```python
hide_related_actions(field, *, can_view=False, can_add=False, can_change=False, can_delete=False)
```

Strips the related-model icons from a form field's widget. Call it from
`get_form` on a `ModelAdmin`, or `get_formset` on an `InlineModelAdmin`, with a
field out of `form.base_fields`. Each keyword left `False` hides that icon.

### `pined.django.serializers.json`

`JSONEncoder` is `DjangoJSONEncoder` with `ensure_ascii=False` and Pydantic
models serialized through `model_dump`. `PydanticField` uses it for encoding by
default. It is worth passing to a plain `JSONField` too, if only to keep
non-ASCII readable in the database.

### `pined.django.utils.nested`

```python
get_nested(obj, *path, default=None)
```

Walks `path` through dicts by key, lists by index and objects by attribute, in
any combination, returning `default` at the first step that doesn't resolve. For
payloads whose shape you don't control.

## Development

```bash
uv sync --all-extras
uv run poe fix          # ruff format + ruff check --fix
uv run poe fix --check  # no writes
uv run poe test         # pytest
uv run poe cov          # pytest, with a coverage report
```

`examples/` is a settings module that runs:

```bash
DJANGO_SETTINGS_MODULE=examples.settings python -m django check
```

`tests/testapp/` is a django app whose migration chain walks a
`PydanticField` through five versions of its pydantic model, one
`AlterPydantic` feature per migration. Each schema the chain references is
committed beside it as `_schema_<model>__<field>.json`, and the shapes
those hashes stand for are kept as classes in `tests/testapp/schema_history.py`
— a pydantic release that changes `model_json_schema()` fails there, with
the fix being to regenerate both.

`tests/no_pydantic/` is the install with neither extra: the commands falling
through to django's own, and every module behind an extra naming the extra it
wants. It skips itself wherever `pydantic` is importable, and `pydantic` only
ever arrives with an extra, so:

```bash
uv sync                 # neither extra
uv run poe test-bare
uv sync --all-extras    # back to the usual one
```

## License

MIT. See [LICENSE](LICENSE).
