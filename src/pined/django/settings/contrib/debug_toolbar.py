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

from pined.django.settings.utils import DjangoModel, DropUnset

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
        return bool(request.user.is_staff)

    return False


class DebugToolbar(DjangoModel):
    """
    The `DEBUG_TOOLBAR_CONFIG` dict.

    The two callbacks take a dotted path or the callable itself, which is
    what makes a `DEBUG`-plus-query check readable in a settings module.
    """

    show_toolbar_callback: str | Callable[..., bool] | None = None
    observe_request_callback: str | Callable[..., bool] | None = None

    cache_backend: str | None = None
    cache_key_prefix: str | None = None
    results_cache_size: int | None = None
    toolbar_store_class: str | None = None

    disable_panels: set[str] | None = None
    extra_signals: list[str] | None = None

    insert_before: str | None = None
    root_tag_extra_attrs: str | None = None
    show_collapsed: bool | None = None
    use_shadow_dom: bool | None = None
    update_on_fetch: bool | None = None
    render_panels: bool | None = None
    toolbar_language: str | None = None
    is_running_tests: bool | None = None

    enable_stacktraces: bool | None = None
    enable_stacktraces_locals: bool | None = None
    hide_in_stacktraces: tuple[str, ...] | None = None

    prettify_sql: bool | None = None
    skip_toolbar_queries: bool | None = None
    sql_warning_threshold: int | None = None

    show_template_context: bool | None = None
    skip_template_prefixes: tuple[str, ...] | None = None

    profiler_capture_project_code: bool | None = None
    profiler_max_depth: int | None = None
    profiler_threshold_ratio: int | None = None


class DebugToolbarSettings(DropUnset, BaseModel):
    """
    `DEBUG_TOOLBAR_CONFIG`, and the parameter `get_debug` looks for.

    `INTERNAL_IPS`, which the toolbar also reads, belongs to django and
    lives on `mixins.General`.
    """

    debug_toolbar_config: DebugToolbar | dict[str, Any] | None = None
    debug_param: str = DEBUG_PARAM
