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

from pined.django.settings.utils import UNSET, DropUnset, Unset


class AxesSettings(DropUnset, BaseModel):
    """
    The `AXES_*` settings.

    Every callable setting takes a dotted path or the callable itself.
    """

    axes_enabled: Unset[bool] = UNSET
    axes_verbose: Unset[bool] = UNSET
    axes_handler: Unset[str] = UNSET

    axes_failure_limit: Unset[int | Callable[..., int]] = UNSET
    axes_lock_out_at_failure: Unset[bool] = UNSET
    axes_lockout_parameters: Unset[list[str | list[str]]] = UNSET
    axes_cooloff_time: Unset[int | float | timedelta | Callable[..., timedelta]] = UNSET
    axes_reset_on_success: Unset[bool] = UNSET
    axes_reset_cool_off_on_failure_during_lockout: Unset[bool] = UNSET
    axes_use_attempt_expiration: Unset[bool] = UNSET

    axes_lockout_template: Unset[str] = UNSET
    axes_lockout_url: Unset[str] = UNSET
    axes_lockout_callable: Unset[str | Callable[..., object]] = UNSET
    axes_cooloff_message: Unset[str] = UNSET
    axes_permalock_message: Unset[str] = UNSET
    axes_http_response_code: Unset[int] = UNSET

    axes_only_admin_site: Unset[bool] = UNSET
    axes_enable_admin: Unset[bool] = UNSET
    axes_only_whitelist: Unset[bool] = UNSET
    axes_never_lockout_get: Unset[bool] = UNSET
    axes_never_lockout_whitelist: Unset[bool] = UNSET
    axes_ip_whitelist: Unset[list[str]] = UNSET
    axes_ip_blacklist: Unset[list[str]] = UNSET
    axes_whitelist_callable: Unset[str | Callable[..., bool]] = UNSET

    axes_username_form_field: Unset[str] = UNSET
    axes_password_form_field: Unset[str] = UNSET
    axes_username_callable: Unset[str | Callable[..., str]] = UNSET
    axes_sensitive_parameters: Unset[list[str]] = UNSET

    axes_client_ip_callable: Unset[str | Callable[..., str]] = UNSET
    axes_client_str_callable: Unset[str | Callable[..., str]] = UNSET
    axes_ipware_proxy_count: Unset[int] = UNSET
    axes_ipware_proxy_order: Unset[str] = UNSET
    axes_ipware_proxy_trusted_ips: Unset[list[str]] = UNSET
    axes_ipware_meta_precedence_order: Unset[tuple[str, ...]] = UNSET

    axes_disable_access_log: Unset[bool] = UNSET
    axes_enable_access_failure_log: Unset[bool] = UNSET
    axes_access_failure_log_per_user_limit: Unset[int] = UNSET
    axes_allowed_cors_origins: Unset[str] = UNSET
