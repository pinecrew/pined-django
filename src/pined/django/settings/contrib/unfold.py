"""
django-unfold.

Field names follow `unfold.settings.CONFIG_DEFAULTS`.
"""

from collections.abc import Callable
from typing import Any

try:
    from pydantic import BaseModel
except ImportError as exc:
    msg = 'To use `settings`, install package with "settings" option: pined-django[settings].'
    raise ImportError(msg) from exc

from pined.django.settings.utils import UNSET, DjangoModel, DropUnset, Unset


class Unfold(DjangoModel):
    """
    The `UNFOLD` dict.

    The branches unfold nests several levels deep — `colors`, `forms`,
    `sidebar`, `login`, `command`, `account`, `languages` — stay plain
    dicts. The image and icon entries take a callable of the request,
    so they are left open.
    """

    site_title: Unset[str] = UNSET
    site_header: Unset[str] = UNSET
    site_subheader: Unset[str] = UNSET
    site_version: Unset[str] = UNSET
    site_url: Unset[str] = UNSET
    site_symbol: Unset[str] = UNSET
    site_icon: Any = UNSET
    site_logo: Any = UNSET
    site_favicons: Unset[list[dict[str, Any]]] = UNSET
    site_dropdown: Unset[list[dict[str, Any]]] = UNSET
    site_views: Unset[list[Any]] = UNSET

    show_history: Unset[bool] = UNSET
    show_view_on_site: Unset[bool] = UNSET
    show_languages: Unset[bool] = UNSET
    show_back_button: Unset[bool] = UNSET
    show_ui_warnings: Unset[bool] = UNSET

    environment: Unset[str | Callable[..., Any]] = UNSET
    environment_title_prefix: Unset[str] = UNSET

    global_callback: Unset[str | Callable[..., Any]] = UNSET
    dashboard_callback: Unset[str | Callable[..., Any]] = UNSET

    styles: Unset[list[Any]] = UNSET
    scripts: Unset[list[Any]] = UNSET
    tabs: Unset[list[dict[str, Any]]] = UNSET

    language_flags: Unset[dict[str, str]] = UNSET
    colors: Unset[dict[str, Any]] = UNSET
    forms: Unset[dict[str, Any]] = UNSET
    sidebar: Unset[dict[str, Any]] = UNSET
    login: Unset[dict[str, Any]] = UNSET
    command: Unset[dict[str, Any]] = UNSET
    account: Unset[dict[str, Any]] = UNSET
    languages: Unset[dict[str, Any]] = UNSET


class UnfoldSettings(DropUnset, BaseModel):
    """
    `UNFOLD`.
    """

    unfold: Unset[Unfold | dict[str, Any]] = UNSET
