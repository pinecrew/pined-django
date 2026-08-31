from typing import Any

try:
    import dj_database_url
    from pydantic import BaseModel, model_serializer
except ImportError as exc:
    msg = 'To use `settings`, install package with "settings" option: pined-django[settings].'
    raise ImportError(msg) from exc

from .utils import DjangoModel


class Database(BaseModel):
    """
    Connection parameters of a single database.

    Fields mirror the arguments of `dj_database_url.parse`, which turns
    them into Django's own shape at serialization time.
    """

    url: str
    engine: str | None = None
    conn_max_age: int | None = 0
    conn_health_checks: bool = False
    disable_server_side_cursors: bool = False
    ssl_require: bool = False
    test_options: dict | None = None

    @model_serializer
    def serialize(self) -> dj_database_url.DBConfig:
        return dj_database_url.parse(**dict(self))


class Databases(BaseModel):
    """
    Entries of `DATABASES`.

    Django requires the `default` to be here. A project should add an alias
    per extra connection.
    """

    default: Database


class TemplateEngine(DjangoModel):
    """
    One entry of `TEMPLATES`.
    """

    backend: str
    name: str | None = None
    dirs: list[str] | None = None
    app_dirs: bool | None = None
    options: dict[str, Any] | None = None


class PasswordValidator(DjangoModel):
    """
    One entry of `AUTH_PASSWORD_VALIDATORS`.
    """

    name: str
    options: dict[str, Any] | None = None


class Cache(DjangoModel):
    """
    One entry of `CACHES`.

    `MAX_ENTRIES` and `CULL_FREQUENCY` are read out of `options`, not
    from a key of their own.
    """

    backend: str
    location: str | list[str] | None = None
    timeout: int | None = None
    key_prefix: str | None = None
    version: int | None = None
    key_function: str | None = None
    options: dict[str, Any] | None = None


class Storage(DjangoModel):
    """
    One entry of `STORAGES`.
    """

    backend: str
    options: dict[str, Any] | None = None


class Mailer(DjangoModel):
    """
    One entry of `MAILERS` (added in django 6.1).

    Keys of `options` belong to the backend; the smtp one takes the
    `EMAIL_*` settings it replaces, lower-cased and unprefixed.
    """

    backend: str
    options: dict[str, Any] | None = None


class TaskBackend(DjangoModel):
    """
    One entry of `TASKS` (added in django 6.0).
    """

    backend: str
    queues: list[str] | None = None
    options: dict[str, Any] | None = None
