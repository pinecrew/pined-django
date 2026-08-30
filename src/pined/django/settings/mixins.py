import pathlib
import re
from typing import Any, ClassVar

try:
    from pydantic import BaseModel
except ImportError as exc:
    msg = 'To use `settings`, install package with "settings" option: pined-django[settings].'
    raise ImportError(msg) from exc

from . import components
from .utils import DropUnset


class General(DropUnset, BaseModel):
    """
    Settings that belong to the project rather than to a subsystem.

    `root_urlconf`, `asgi_application` and `site_id` have no default in
    django at all, so leaving them unset leaves them absent.
    """

    debug: bool | None = None
    secret_key: str | None = None
    secret_key_fallbacks: list[str] | None = None
    allowed_hosts: list[str] | None = None

    root_urlconf: str | None = None
    wsgi_application: str | None = None
    asgi_application: str | None = None
    site_id: int | None = None

    append_slash: bool | None = None
    prepend_www: bool | None = None
    force_script_name: str | None = None
    default_charset: str | None = None
    absolute_url_overrides: dict[str, Any] | None = None
    urlize_assume_https: bool | None = None

    admins: list[str | tuple[str, str]] | None = None
    managers: list[str | tuple[str, str]] | None = None
    internal_ips: list[str] | None = None
    silenced_system_checks: list[str] | None = None
    disallowed_user_agents: list[re.Pattern[str]] | None = None
    ignorable_404_urls: list[re.Pattern[str]] | None = None

    debug_propagate_exceptions: bool | None = None
    default_exception_reporter: str | None = None
    default_exception_reporter_filter: str | None = None
    signing_backend: str | None = None
    signed_cookie_legacy_salt_fallback: bool | None = None


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

    installed_apps: list[str] | None = None
    middleware: list[str] | None = None


class Database(DropUnset, BaseModel):
    """
    `DATABASES` and the rest of the ORM's configuration.
    """

    databases: components.Databases | None = None
    database_routers: list[str] | None = None
    default_auto_field: str | None = None
    default_tablespace: str | None = None
    default_index_tablespace: str | None = None
    migration_modules: dict[str, str] | None = None


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

    auth_user_model: str | None = None
    authentication_backends: list[str] | None = None
    auth_password_validators: list[components.PasswordValidator] | None = None
    password_hashers: list[str] | None = None
    password_reset_timeout: int | None = None

    login_url: str | None = None
    login_redirect_url: str | None = None
    logout_redirect_url: str | None = None


class Session(DropUnset, BaseModel):
    """
    The session backend and its cookie.
    """

    KEEP_NONE: ClassVar[frozenset[str]] = frozenset({"session_cookie_samesite"})

    session_engine: str | None = None
    session_serializer: str | None = None
    session_cache_alias: str | None = None
    session_file_path: str | pathlib.Path | None = None

    session_cookie_name: str | None = None
    session_cookie_age: int | None = None
    session_cookie_domain: str | None = None
    session_cookie_path: str | None = None
    session_cookie_secure: bool | None = None
    session_cookie_httponly: bool | None = None
    session_cookie_samesite: str | None = "Lax"

    session_expire_at_browser_close: bool | None = None
    session_save_every_request: bool | None = None


class Csrf(DropUnset, BaseModel):
    """
    Cross-site request forgery protection.
    """

    KEEP_NONE: ClassVar[frozenset[str]] = frozenset({"csrf_cookie_samesite"})

    csrf_cookie_name: str | None = None
    csrf_cookie_age: int | None = None
    csrf_cookie_domain: str | None = None
    csrf_cookie_path: str | None = None
    csrf_cookie_secure: bool | None = None
    csrf_cookie_httponly: bool | None = None
    csrf_cookie_samesite: str | None = "Lax"

    csrf_use_sessions: bool | None = None
    csrf_header_name: str | None = None
    csrf_trusted_origins: list[str] | None = None
    csrf_failure_view: str | None = None


class Security(DropUnset, BaseModel):
    """
    `SecurityMiddleware`'s headers and the proxy-facing settings.
    """

    KEEP_NONE: ClassVar[frozenset[str]] = frozenset(
        {"secure_referrer_policy", "secure_cross_origin_opener_policy"},
    )

    secure_content_type_nosniff: bool | None = None
    secure_cross_origin_opener_policy: str | None = "same-origin"
    secure_referrer_policy: str | list[str] | None = "same-origin"

    secure_hsts_seconds: int | None = None
    secure_hsts_include_subdomains: bool | None = None
    secure_hsts_preload: bool | None = None

    secure_ssl_redirect: bool | None = None
    secure_ssl_host: str | None = None
    secure_redirect_exempt: list[str] | None = None

    secure_csp: dict[str, Any] | None = None
    secure_csp_report_only: dict[str, Any] | None = None

    secure_proxy_ssl_header: tuple[str, str] | None = None
    use_x_forwarded_host: bool | None = None
    use_x_forwarded_port: bool | None = None
    x_frame_options: str | None = None


class Email(DropUnset, BaseModel):
    """
    The mail backend and the addresses django sends from.
    """

    email_backend: str | None = None
    email_host: str | None = None
    email_port: int | None = None
    email_host_user: str | None = None
    email_host_password: str | None = None
    email_timeout: float | None = None

    email_use_tls: bool | None = None
    email_use_ssl: bool | None = None
    email_ssl_certfile: str | pathlib.Path | None = None
    email_ssl_keyfile: str | pathlib.Path | None = None
    email_use_localtime: bool | None = None

    email_subject_prefix: str | None = None
    default_from_email: str | None = None
    server_email: str | None = None


class Templates(DropUnset, BaseModel):
    """
    `TEMPLATES` and the form renderer.

    Attributes:
        CONTEXT_PROCESSORS: What `startproject` puts in the django
            backend's `OPTIONS`, to splat into a project's own list.
    """

    CONTEXT_PROCESSORS: ClassVar[tuple[str, ...]] = (
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    )

    templates: list[components.TemplateEngine] | None = None
    form_renderer: str | None = None


class Static(DropUnset, BaseModel):
    """
    Static and media files, and the storage backends behind them.
    """

    static_url: str | None = None
    static_root: str | pathlib.Path | None = None
    staticfiles_dirs: list[str | pathlib.Path | tuple[str, str | pathlib.Path]] | None = None
    staticfiles_finders: list[str] | None = None

    media_url: str | None = None
    media_root: str | pathlib.Path | None = None

    storages: dict[str, components.Storage] | None = None


class Uploads(DropUnset, BaseModel):
    """
    Limits and permissions for incoming files and form data.
    """

    KEEP_NONE: ClassVar[frozenset[str]] = frozenset({"file_upload_permissions"})

    file_upload_handlers: list[str] | None = None
    file_upload_max_memory_size: int | None = None
    file_upload_temp_dir: str | pathlib.Path | None = None
    file_upload_permissions: int | None = 0o644
    file_upload_directory_permissions: int | None = None

    data_upload_max_memory_size: int | None = None
    data_upload_max_number_fields: int | None = None
    data_upload_max_number_files: int | None = None


class I18n(DropUnset, BaseModel):
    """
    Languages, the locale cookie and the timezone.
    """

    language_code: str | None = None
    languages: list[tuple[str, str]] | None = None
    languages_bidi: list[str] | None = None
    locale_paths: list[str | pathlib.Path] | None = None
    use_i18n: bool | None = None

    language_cookie_name: str | None = None
    language_cookie_age: int | None = None
    language_cookie_domain: str | None = None
    language_cookie_path: str | None = None
    language_cookie_secure: bool | None = None
    language_cookie_httponly: bool | None = None
    language_cookie_samesite: str | None = None

    time_zone: str | None = None
    use_tz: bool | None = None


class Formats(DropUnset, BaseModel):
    """
    How dates and numbers are rendered and parsed.
    """

    date_format: str | None = None
    date_input_formats: list[str] | None = None
    datetime_format: str | None = None
    datetime_input_formats: list[str] | None = None
    time_format: str | None = None
    time_input_formats: list[str] | None = None
    short_date_format: str | None = None
    short_datetime_format: str | None = None
    month_day_format: str | None = None
    year_month_format: str | None = None
    first_day_of_week: int | None = None

    decimal_separator: str | None = None
    thousand_separator: str | None = None
    number_grouping: int | None = None
    use_thousand_separator: bool | None = None

    format_module_path: str | list[str] | None = None


class Cache(DropUnset, BaseModel):
    """
    `CACHES` and the caching middleware.
    """

    caches: dict[str, components.Cache] | None = None
    cache_middleware_alias: str | None = None
    cache_middleware_key_prefix: str | None = None
    cache_middleware_seconds: int | None = None


class Logging(DropUnset, BaseModel):
    """
    The `dictConfig` django hands to the logging module.
    """

    logging: dict[str, Any] | None = None
    logging_config: str | None = None


class Messages(DropUnset, BaseModel):
    """
    `django.contrib.messages`.

    `message_level` and `message_tags` have no default of their own; the
    storage backend falls back to `INFO` and to the built-in tags.
    """

    message_storage: str | None = None
    message_level: int | None = None
    message_tags: dict[int, str] | None = None


class Tasks(DropUnset, BaseModel):
    """
    `TASKS`, which django gained in 6.0.
    """

    tasks: dict[str, components.TaskBackend] | None = None


class Testing(DropUnset, BaseModel):
    """
    The test runner and what it loads.
    """

    test_runner: str | None = None
    test_non_serialized_apps: list[str] | None = None
    fixture_dirs: list[str | pathlib.Path] | None = None
