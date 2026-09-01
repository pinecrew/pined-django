"""
django-debug-toolbar.

Field names follow `debug_toolbar.settings.CONFIG_DEFAULTS`.
"""

import contextlib
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.http import HttpRequest

try:
    from pydantic import BaseModel
except ImportError as exc:
    msg = 'To use `settings`, install package with "settings" option: pined-django[settings].'
    raise ImportError(msg) from exc

from pined.django.settings.utils import UNSET, DjangoModel, DropUnset, Unset

DEBUG_PARAM = "debug"
"""Name the `DEBUG_PARAM` setting falls back to."""
DEBUG_VALUES = frozenset({"1", "true", "yes", "on"})
"""Values of `DEBUG_PARAM` that count as a yes."""


def get_debug(request: HttpRequest) -> bool:
    """
    Decides whether the toolbar renders, for `show_toolbar_callback`.

    With `DEBUG` on, always. With it off, a staff member can still ask
    for one response with `?debug=1` — the toolbar hands out SQL,
    settings and request data, so nobody else gets to.

    The parameter is named by the `DEBUG_PARAM` setting that
    `DebugToolbarSettings` declares, and read per request, so a
    deployment can rename it from the environment.

    Args:
        request: The request the toolbar is asking about.

    Returns:
        Whether to render the toolbar.
    """

    if settings.DEBUG:
        return True

    param = getattr(settings, "DEBUG_PARAM", DEBUG_PARAM)
    if request.method != "GET" or request.GET.get(param, "").lower() not in DEBUG_VALUES:
        return False

    # No `AuthenticationMiddleware` means no `request.user`, and no toolbar.
    with contextlib.suppress(AttributeError):
        # pyrefly: ignore[missing-attribute]  # `AnonymousUser.is_staff` is there, the stub's union hides it
        return bool(request.user.is_staff)

    return False


class DebugToolbar(DjangoModel):
    """
    The `DEBUG_TOOLBAR_CONFIG` dict.

    The two callbacks take a dotted path or the callable itself, which is
    what makes a `DEBUG`-plus-query check readable in a settings module.
    """

    show_toolbar_callback: Unset[str | Callable[..., bool]] = UNSET
    observe_request_callback: Unset[str | Callable[..., bool]] = UNSET

    cache_backend: Unset[str] = UNSET
    cache_key_prefix: Unset[str] = UNSET
    results_cache_size: Unset[int] = UNSET
    toolbar_store_class: Unset[str] = UNSET

    disable_panels: Unset[set[str]] = UNSET
    extra_signals: Unset[list[str]] = UNSET

    insert_before: Unset[str] = UNSET
    root_tag_extra_attrs: Unset[str] = UNSET
    show_collapsed: Unset[bool] = UNSET
    use_shadow_dom: Unset[bool] = UNSET
    update_on_fetch: Unset[bool] = UNSET
    render_panels: Unset[bool] = UNSET
    toolbar_language: Unset[str] = UNSET
    is_running_tests: Unset[bool] = UNSET

    enable_stacktraces: Unset[bool] = UNSET
    enable_stacktraces_locals: Unset[bool] = UNSET
    hide_in_stacktraces: Unset[tuple[str, ...]] = UNSET

    prettify_sql: Unset[bool] = UNSET
    skip_toolbar_queries: Unset[bool] = UNSET
    sql_warning_threshold: Unset[int] = UNSET

    show_template_context: Unset[bool] = UNSET
    skip_template_prefixes: Unset[tuple[str, ...]] = UNSET

    profiler_capture_project_code: Unset[bool] = UNSET
    profiler_max_depth: Unset[int] = UNSET
    profiler_threshold_ratio: Unset[int] = UNSET


class DebugToolbarSettings(DropUnset, BaseModel):
    """
    `DEBUG_TOOLBAR_CONFIG`, and the parameter `get_debug` looks for.

    `INTERNAL_IPS`, which the toolbar also reads, belongs to django and
    lives on `mixins.General`.
    """

    debug_toolbar_config: Unset[DebugToolbar | dict[str, Any]] = UNSET
    debug_param: str = DEBUG_PARAM
