import pathlib
import re
from typing import Any, ClassVar, Literal, override

try:
    from pydantic import BaseModel, computed_field
except ImportError as exc:
    msg = 'To use `settings`, install package with "settings" option: pined-django[settings].'
    raise ImportError(msg) from exc

from . import components
from .utils import UNSET, DropUnset, Unset

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class General(DropUnset, BaseModel):
    """
    Settings that belong to the project rather than to a subsystem.

    `root_urlconf`, `asgi_application` and `site_id` have no default in
    django at all, so leaving them unset leaves them absent.
    """

    debug: Unset[bool] = UNSET
    secret_key: Unset[str] = UNSET
    secret_key_fallbacks: Unset[list[str]] = UNSET
    allowed_hosts: Unset[list[str]] = UNSET

    root_urlconf: Unset[str] = UNSET
    wsgi_application: Unset[str] = UNSET
    asgi_application: Unset[str] = UNSET
    site_id: Unset[int] = UNSET

    time_zone: Unset[str] = UNSET
    use_tz: Unset[bool] = UNSET

    append_slash: Unset[bool] = UNSET
    prepend_www: Unset[bool] = UNSET
    force_script_name: Unset[str] = UNSET
    default_charset: Unset[str] = UNSET
    absolute_url_overrides: Unset[dict[str, Any]] = UNSET
    urlize_assume_https: Unset[bool] = UNSET

    admins: Unset[list[str | tuple[str, str]]] = UNSET
    managers: Unset[list[str | tuple[str, str]]] = UNSET
    internal_ips: Unset[list[str]] = UNSET
    silenced_system_checks: Unset[list[str]] = UNSET
    disallowed_user_agents: Unset[list[re.Pattern[str]]] = UNSET
    ignorable_404_urls: Unset[list[re.Pattern[str]]] = UNSET

    debug_propagate_exceptions: Unset[bool] = UNSET
    default_exception_reporter: Unset[str] = UNSET
    default_exception_reporter_filter: Unset[str] = UNSET
    signing_backend: Unset[str] = UNSET
    signed_cookie_legacy_salt_fallback: Unset[bool] = UNSET


class Apps(DropUnset, BaseModel):
    """
    `INSTALLED_APPS` and `MIDDLEWARE`.

    Both are order-sensitive and every project inserts into the middle of
    them, so django's own entries are class attributes to splat rather
    than defaults to override:

    ```
    installed_apps: list[str] = [*Apps.CONTRIB_APPS, "myapp"]
    ```

    Attributes:
        CONTRIB_APPS: What `startproject` puts in `INSTALLED_APPS`.
        CONTRIB_MIDDLEWARE: What it puts in `MIDDLEWARE`.
    """

    CONTRIB_APPS: ClassVar[tuple[str, ...]] = (
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
    )
    CONTRIB_MIDDLEWARE: ClassVar[tuple[str, ...]] = (
        "django.middleware.security.SecurityMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
    )

    installed_apps: Unset[list[str]] = UNSET
    middleware: Unset[list[str]] = UNSET


class Database(DropUnset, BaseModel):
    """
    `DATABASES` and the rest of the ORM's configuration.
    """

    databases: Unset[components.Databases] = UNSET
    database_routers: Unset[list[str]] = UNSET
    default_auto_field: Unset[str] = UNSET
    default_tablespace: Unset[str] = UNSET
    default_index_tablespace: Unset[str] = UNSET
    migration_modules: Unset[dict[str, str]] = UNSET


class Auth(DropUnset, BaseModel):
    """
    Users, passwords and the login flow.

    Attributes:
        PASSWORD_VALIDATORS: What `startproject` puts in
            `AUTH_PASSWORD_VALIDATORS`.
    """

    PASSWORD_VALIDATORS: ClassVar[tuple[components.PasswordValidator, ...]] = tuple(
        components.PasswordValidator(name=f"django.contrib.auth.password_validation.{name}")
        for name in (
            "UserAttributeSimilarityValidator",
            "MinimumLengthValidator",
            "CommonPasswordValidator",
            "NumericPasswordValidator",
        )
    )

    auth_user_model: Unset[str] = UNSET
    authentication_backends: Unset[list[str]] = UNSET
    auth_password_validators: Unset[list[components.PasswordValidator]] = UNSET
    password_hashers: Unset[list[str]] = UNSET
    password_reset_timeout: Unset[int] = UNSET

    login_url: Unset[str] = UNSET
    login_redirect_url: Unset[str] = UNSET
    logout_redirect_url: Unset[str] = UNSET


class Session(DropUnset, BaseModel):
    """
    The session backend and its cookie.
    """

    session_engine: Unset[str] = UNSET
    session_serializer: Unset[str] = UNSET
    session_cache_alias: Unset[str] = UNSET
    session_file_path: Unset[str | pathlib.Path] = UNSET

    session_cookie_name: Unset[str] = UNSET
    session_cookie_age: Unset[int] = UNSET
    session_cookie_domain: Unset[str] = UNSET
    session_cookie_path: Unset[str] = UNSET
    session_cookie_secure: Unset[bool] = UNSET
    session_cookie_httponly: Unset[bool] = UNSET
    session_cookie_samesite: Unset[str | None] = UNSET

    session_expire_at_browser_close: Unset[bool] = UNSET
    session_save_every_request: Unset[bool] = UNSET


class Csrf(DropUnset, BaseModel):
    """
    Cross-site request forgery protection.
    """

    csrf_cookie_name: Unset[str] = UNSET
    csrf_cookie_age: Unset[int] = UNSET
    csrf_cookie_domain: Unset[str] = UNSET
    csrf_cookie_path: Unset[str] = UNSET
    csrf_cookie_secure: Unset[bool] = UNSET
    csrf_cookie_httponly: Unset[bool] = UNSET
    csrf_cookie_samesite: Unset[str | None] = UNSET

    csrf_use_sessions: Unset[bool] = UNSET
    csrf_header_name: Unset[str] = UNSET
    csrf_trusted_origins: Unset[list[str]] = UNSET
    csrf_failure_view: Unset[str] = UNSET


class Security(DropUnset, BaseModel):
    """
    `SecurityMiddleware`'s headers and the proxy-facing settings.
    """

    secure_content_type_nosniff: Unset[bool] = UNSET
    secure_cross_origin_opener_policy: Unset[str | None] = UNSET
    secure_referrer_policy: Unset[str | list[str] | None] = UNSET

    secure_hsts_seconds: Unset[int] = UNSET
    secure_hsts_include_subdomains: Unset[bool] = UNSET
    secure_hsts_preload: Unset[bool] = UNSET

    secure_ssl_redirect: Unset[bool] = UNSET
    secure_ssl_host: Unset[str] = UNSET
    secure_redirect_exempt: Unset[list[str]] = UNSET

    secure_csp: Unset[dict[str, Any]] = UNSET
    secure_csp_report_only: Unset[dict[str, Any]] = UNSET

    secure_proxy_ssl_header: Unset[tuple[str, str]] = UNSET
    use_x_forwarded_host: Unset[bool] = UNSET
    use_x_forwarded_port: Unset[bool] = UNSET
    x_frame_options: Unset[str] = UNSET


class Email(DropUnset, BaseModel):
    """
    The mail backend and the addresses django sends from.

    `mailers` arrived in django 6.1 to replace the `email_*` backend
    settings below it, and 7.0 removes those. The addresses,
    `email_subject_prefix` and `email_use_localtime` are staying.
    """

    mailers: Unset[dict[str, components.Mailer]] = UNSET

    email_backend: Unset[str] = UNSET
    email_file_path: Unset[str | pathlib.Path] = UNSET
    email_host: Unset[str] = UNSET
    email_port: Unset[int] = UNSET
    email_host_user: Unset[str] = UNSET
    email_host_password: Unset[str] = UNSET
    email_timeout: Unset[float] = UNSET

    email_use_tls: Unset[bool] = UNSET
    email_use_ssl: Unset[bool] = UNSET
    email_ssl_certfile: Unset[str | pathlib.Path] = UNSET
    email_ssl_keyfile: Unset[str | pathlib.Path] = UNSET
    email_use_localtime: Unset[bool] = UNSET

    email_subject_prefix: Unset[str] = UNSET
    default_from_email: Unset[str] = UNSET
    server_email: Unset[str] = UNSET


class Templates(DropUnset, BaseModel):
    """
    `TEMPLATES`, the form renderer and the label of a blank choice.

    Attributes:
        CONTEXT_PROCESSORS: What `startproject` puts in the django
            backend's `OPTIONS`, to splat into a project's own list.
        DJANGO_ENGINE: The whole engine `startproject` configures. Django
            supplies `NAME`, `DIRS` and `OPTIONS` where an entry leaves
            them out, so a project needing one of those can ask for
            `DJANGO_ENGINE.model_copy(update={"dirs": [...]})`.
    """

    CONTEXT_PROCESSORS: ClassVar[tuple[str, ...]] = (
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    )
    DJANGO_ENGINE: ClassVar[components.TemplateEngine] = components.TemplateEngine(
        backend="django.template.backends.django.DjangoTemplates",
        app_dirs=True,
        options={"context_processors": [*CONTEXT_PROCESSORS]},
    )

    templates: Unset[list[components.TemplateEngine]] = UNSET
    form_renderer: Unset[str] = UNSET

    use_blank_choice_dash: Unset[bool] = UNSET
    """Restores the old `---------` blank label, which django 7.0 drops."""


class Static(DropUnset, BaseModel):
    """
    Static and media files, and the storage backends behind them.
    """

    static_url: Unset[str] = UNSET
    static_root: Unset[str | pathlib.Path] = UNSET
    staticfiles_dirs: Unset[list[str | pathlib.Path | tuple[str, str | pathlib.Path]]] = UNSET
    staticfiles_finders: Unset[list[str]] = UNSET

    media_url: Unset[str] = UNSET
    media_root: Unset[str | pathlib.Path] = UNSET

    storages: Unset[dict[str, components.Storage]] = UNSET


class Uploads(DropUnset, BaseModel):
    """
    Limits and permissions for incoming files and form data.
    """

    file_upload_handlers: Unset[list[str]] = UNSET
    file_upload_max_memory_size: Unset[int] = UNSET
    file_upload_temp_dir: Unset[str | pathlib.Path] = UNSET
    file_upload_permissions: Unset[int | None] = UNSET
    file_upload_directory_permissions: Unset[int] = UNSET

    data_upload_max_memory_size: Unset[int] = UNSET
    data_upload_max_number_fields: Unset[int] = UNSET
    data_upload_max_number_files: Unset[int] = UNSET


class I18n(DropUnset, BaseModel):
    """
    Languages and the locale cookie.
    """

    language_code: Unset[str] = UNSET
    languages: Unset[list[tuple[str, str]]] = UNSET
    languages_bidi: Unset[list[str]] = UNSET
    locale_paths: Unset[list[str | pathlib.Path]] = UNSET
    use_i18n: Unset[bool] = UNSET

    language_cookie_name: Unset[str] = UNSET
    language_cookie_age: Unset[int] = UNSET
    language_cookie_domain: Unset[str] = UNSET
    language_cookie_path: Unset[str] = UNSET
    language_cookie_secure: Unset[bool] = UNSET
    language_cookie_httponly: Unset[bool] = UNSET
    language_cookie_samesite: Unset[str] = UNSET


class Formats(DropUnset, BaseModel):
    """
    How dates and numbers are rendered and parsed.
    """

    date_format: Unset[str] = UNSET
    date_input_formats: Unset[list[str]] = UNSET
    datetime_format: Unset[str] = UNSET
    datetime_input_formats: Unset[list[str]] = UNSET
    time_format: Unset[str] = UNSET
    time_input_formats: Unset[list[str]] = UNSET
    short_date_format: Unset[str] = UNSET
    short_datetime_format: Unset[str] = UNSET
    month_day_format: Unset[str] = UNSET
    year_month_format: Unset[str] = UNSET
    first_day_of_week: Unset[int] = UNSET

    decimal_separator: Unset[str] = UNSET
    thousand_separator: Unset[str] = UNSET
    number_grouping: Unset[int] = UNSET
    use_thousand_separator: Unset[bool] = UNSET

    format_module_path: Unset[str | list[str]] = UNSET


class Cache(DropUnset, BaseModel):
    """
    `CACHES` and the caching middleware.
    """

    caches: Unset[dict[str, components.Cache]] = UNSET
    cache_middleware_alias: Unset[str] = UNSET
    cache_middleware_key_prefix: Unset[str] = UNSET
    cache_middleware_seconds: Unset[int] = UNSET


class Logging(DropUnset, BaseModel):
    """
    `LOGGING`, assembled from the parts a project actually varies.

    Every entry of `log_files` gets a rotating handler of its own, and
    the logger it is keyed by writes there and nowhere else. The fields
    that feed `LOGGING` land in the settings module beside it, where
    django pays them no mind and a reader can still find them.

    Attributes:
        FORMATTER: Name the single formatter is registered under.
        ROOT: Handler prefix used for `root_log_file`.
    """

    FORMATTER: ClassVar[str] = "verbose"
    ROOT: ClassVar[str] = "root"
    NULL: ClassVar[str] = "null"

    logs_root: Unset[pathlib.Path] = UNSET
    log_level: LogLevel = "INFO"
    logging_config: Unset[str] = UNSET

    log_format: str = "{levelname} {asctime} {funcName} {message}"
    log_datefmt: str = "%Y-%m-%d %H:%M:%S %z"

    handler_class: str = "logging.handlers.TimedRotatingFileHandler"
    handler_options: dict[str, Any] = {"when": "midnight", "backupCount": 10}
    """Keys of the chosen handler class, `maxBytes` and friends included."""

    log_files: dict[str, str] = {}
    """Logger name to the file it writes, e.g. `{"myapp.api": "api.log"}`."""
    root_log_file: Unset[str] = UNSET
    ignored_loggers: list[str] = []
    """Loggers to silence, handed a `NullHandler` of their own."""

    @override
    def model_post_init(self, context: Any, /) -> None:
        """
        Make `logs_root` on the way in.

        `dictConfig` opens every file as it builds the handler, so the
        directory has to be there before django configures logging — which
        is after the settings are built, and that is the moment to do it.
        Building the config is serialization, and serialization has no
        business writing to disk: a diagnostic dump, a settings comparison
        in a test and a read-only container each got a `mkdir` out of it.
        """

        super().model_post_init(context)

        if self.logs_root:
            self.logs_root.mkdir(parents=True, exist_ok=True)

    def _handler_name(self, logger: str) -> str:
        return f"{logger}_file"

    @computed_field
    def logging(self) -> Unset[dict[str, Any]]:
        """
        Builds the `dictConfig` out of the fields above.

        Returns:
            `UNSET` while `logs_root` is unset, so that `LOGGING` is not
            written at all and django's own configuration stands.
        """

        if not self.logs_root:
            return UNSET

        root = {self.ROOT: self.root_log_file} if self.root_log_file else {}
        files: dict[str, str] = self.log_files | root
        config: dict[str, Any] = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                self.FORMATTER: {"style": "{", "format": self.log_format, "datefmt": self.log_datefmt},
            },
            "handlers": {
                **({self.NULL: {"class": "logging.NullHandler"}} if self.ignored_loggers else {}),
                **{
                    self._handler_name(logger): {
                        "class": self.handler_class,
                        "level": self.log_level,
                        "formatter": self.FORMATTER,
                        "filename": self.logs_root / filename,
                        **self.handler_options,
                    }
                    for logger, filename in files.items()
                },
            },
            "loggers": {
                **{
                    logger: {"handlers": [self._handler_name(logger)], "level": self.log_level, "propagate": False}
                    for logger in self.log_files
                },
                **{logger: {"handlers": [self.NULL], "propagate": False} for logger in self.ignored_loggers},
            },
        }

        if self.root_log_file:
            config["root"] = {"handlers": [self._handler_name(self.ROOT)], "level": self.log_level}

        return config


class Messages(DropUnset, BaseModel):
    """
    `django.contrib.messages`.

    `message_level` and `message_tags` have no default of their own; the
    storage backend falls back to `INFO` and to the built-in tags.
    """

    message_storage: Unset[str] = UNSET
    message_level: Unset[int] = UNSET
    message_tags: Unset[dict[int, str]] = UNSET


class Tasks(DropUnset, BaseModel):
    """
    `TASKS`, which django gained in 6.0.
    """

    tasks: Unset[dict[str, components.TaskBackend]] = UNSET


class Testing(DropUnset, BaseModel):
    """
    The test runner and what it loads.
    """

    test_runner: Unset[str] = UNSET
    test_non_serialized_apps: Unset[list[str]] = UNSET
    fixture_dirs: Unset[list[str | pathlib.Path]] = UNSET
