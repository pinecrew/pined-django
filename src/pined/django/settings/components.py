from typing import Any

try:
    import dj_database_url
    from pydantic import BaseModel, model_serializer
except ImportError as exc:
    msg = 'To use `settings`, install package with "settings" option: pined-django[settings].'
    raise ImportError(msg) from exc

from .utils import UNSET, DjangoModel, Unset


class Database(BaseModel):
    """
    Connection parameters of a single database.

    Fields mirror the arguments of `dj_database_url.parse`, which turns
    them into Django's own shape at serialization time.
    """

    url: str
    engine: Unset[str] = UNSET
    conn_max_age: int | None = 0
    conn_health_checks: bool = False
    disable_server_side_cursors: bool = False
    ssl_require: bool = False
    test_options: Unset[dict[str, Any]] = UNSET

    @model_serializer
    def serialize(self) -> dj_database_url.DBConfig:
        # `UNSET` is ours to keep: `parse` wants the argument left out, and
        # it happening to be falsy is not something to lean on.
        return dj_database_url.parse(**{name: value for name, value in self if value is not UNSET})


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
    name: Unset[str] = UNSET
    dirs: Unset[list[str]] = UNSET
    app_dirs: Unset[bool] = UNSET
    options: Unset[dict[str, Any]] = UNSET


class PasswordValidator(DjangoModel):
    """
    One entry of `AUTH_PASSWORD_VALIDATORS`.
    """

    name: str
    options: Unset[dict[str, Any]] = UNSET


class Cache(DjangoModel):
    """
    One entry of `CACHES`.

    `MAX_ENTRIES` and `CULL_FREQUENCY` are read out of `options`, not
    from a key of their own.
    """

    backend: str
    location: Unset[str | list[str]] = UNSET
    timeout: Unset[int] = UNSET
    key_prefix: Unset[str] = UNSET
    version: Unset[int] = UNSET
    key_function: Unset[str] = UNSET
    options: Unset[dict[str, Any]] = UNSET


class Storage(DjangoModel):
    """
    One entry of `STORAGES`.
    """

    backend: str
    options: Unset[dict[str, Any]] = UNSET


class Mailer(DjangoModel):
    """
    One entry of `MAILERS` (added in django 6.1).

    Keys of `options` belong to the backend; the smtp one takes the
    `EMAIL_*` settings it replaces, lower-cased and unprefixed.
    """

    backend: str
    options: Unset[dict[str, Any]] = UNSET


class TaskBackend(DjangoModel):
    """
    One entry of `TASKS` (added in django 6.0).
    """

    backend: str
    queues: Unset[list[str]] = UNSET
    options: Unset[dict[str, Any]] = UNSET
