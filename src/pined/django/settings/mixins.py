import re
from typing import Any, ClassVar

try:
    from pydantic import BaseModel
except ImportError as exc:
    msg = 'To use `settings`, install package with "settings" option: pined-django[settings].'
    raise ImportError(msg) from exc

from .components import Databases, PasswordValidator, TemplateEngine
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
        CONTRIB_MIDDLEWARE: What it puts in `MIDDLEWARE`, in order.
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

    databases: Databases | None = None
    database_routers: list[str] | None = None
    default_auto_field: str | None = None
    default_tablespace: str | None = None
    default_index_tablespace: str | None = None
    migration_modules: dict[str, str] | None = None


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

    templates: list[TemplateEngine] | None = None
    form_renderer: str | None = None


class Security(DropUnset, BaseModel):
    """
    `SecurityMiddleware`'s headers and the proxy-facing settings.

    Attributes:
        PASSWORD_VALIDATORS: What `startproject` puts in
            `AUTH_PASSWORD_VALIDATORS`. Lives here rather than on `Auth`
            for the company it keeps.
    """

    KEEP_NONE: ClassVar[frozenset[str]] = frozenset(
        {"secure_referrer_policy", "secure_cross_origin_opener_policy"},
    )
    PASSWORD_VALIDATORS: ClassVar[tuple[PasswordValidator, ...]] = tuple(
        PasswordValidator(name=f"django.contrib.auth.password_validation.{name}")
        for name in (
            "UserAttributeSimilarityValidator",
            "MinimumLengthValidator",
            "CommonPasswordValidator",
            "NumericPasswordValidator",
        )
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
