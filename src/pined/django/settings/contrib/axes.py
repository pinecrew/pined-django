"""
django-axes.

`axes.conf` declares no defaults dict; it writes them straight onto
`django.conf.settings` with `getattr(settings, name, default)`. Nothing
here carries a value for that reason: an emitted `None` would win over
the library's own default rather than defer to it.
"""

from collections.abc import Callable
from datetime import timedelta

try:
    from pydantic import BaseModel
except ImportError as exc:
    msg = 'To use `settings`, install package with "settings" option: pined-django[settings].'
    raise ImportError(msg) from exc

from pined.django.settings.utils import DropUnset


class AxesSettings(DropUnset, BaseModel):
    """
    The `AXES_*` settings.

    Every callable setting takes a dotted path or the callable itself.
    """

    axes_enabled: bool | None = None
    axes_verbose: bool | None = None
    axes_handler: str | None = None

    axes_failure_limit: int | Callable[..., int] | None = None
    axes_lock_out_at_failure: bool | None = None
    axes_lockout_parameters: list[str | list[str]] | None = None
    axes_cooloff_time: int | float | timedelta | Callable[..., timedelta] | None = None
    axes_reset_on_success: bool | None = None
    axes_reset_cool_off_on_failure_during_lockout: bool | None = None
    axes_use_attempt_expiration: bool | None = None

    axes_lockout_template: str | None = None
    axes_lockout_url: str | None = None
    axes_lockout_callable: str | Callable[..., object] | None = None
    axes_cooloff_message: str | None = None
    axes_permalock_message: str | None = None
    axes_http_response_code: int | None = None

    axes_only_admin_site: bool | None = None
    axes_enable_admin: bool | None = None
    axes_only_whitelist: bool | None = None
    axes_never_lockout_get: bool | None = None
    axes_never_lockout_whitelist: bool | None = None
    axes_ip_whitelist: list[str] | None = None
    axes_ip_blacklist: list[str] | None = None
    axes_whitelist_callable: str | Callable[..., bool] | None = None

    axes_username_form_field: str | None = None
    axes_password_form_field: str | None = None
    axes_username_callable: str | Callable[..., str] | None = None
    axes_sensitive_parameters: list[str] | None = None

    axes_client_ip_callable: str | Callable[..., str] | None = None
    axes_client_str_callable: str | Callable[..., str] | None = None
    axes_ipware_proxy_count: int | None = None
    axes_ipware_proxy_order: str | None = None
    axes_ipware_proxy_trusted_ips: list[str] | None = None
    axes_ipware_meta_precedence_order: tuple[str, ...] | None = None

    axes_disable_access_log: bool | None = None
    axes_enable_access_failure_log: bool | None = None
    axes_access_failure_log_per_user_limit: int | None = None
    axes_allowed_cors_origins: str | None = None
