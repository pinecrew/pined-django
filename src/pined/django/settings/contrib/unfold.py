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

from pined.django.settings.utils import DjangoModel, DropUnset


class Unfold(DjangoModel):
    """
    The `UNFOLD` dict.

    The branches unfold nests several levels deep — `colors`, `forms`,
    `sidebar`, `login`, `command`, `account`, `languages` — stay plain
    dicts. The image and icon entries take a callable of the request,
    so they are left open.
    """

    site_title: str | None = None
    site_header: str | None = None
    site_subheader: str | None = None
    site_version: str | None = None
    site_url: str | None = None
    site_symbol: str | None = None
    site_icon: Any = None
    site_logo: Any = None
    site_favicons: list[dict[str, Any]] | None = None
    site_dropdown: list[dict[str, Any]] | None = None
    site_views: list[Any] | None = None

    show_history: bool | None = None
    show_view_on_site: bool | None = None
    show_languages: bool | None = None
    show_back_button: bool | None = None
    show_ui_warnings: bool | None = None

    environment: str | Callable[..., Any] | None = None
    environment_title_prefix: str | None = None

    global_callback: str | Callable[..., Any] | None = None
    dashboard_callback: str | Callable[..., Any] | None = None

    styles: list[Any] | None = None
    scripts: list[Any] | None = None
    tabs: list[dict[str, Any]] | None = None

    language_flags: dict[str, str] | None = None
    colors: dict[str, Any] | None = None
    forms: dict[str, Any] | None = None
    sidebar: dict[str, Any] | None = None
    login: dict[str, Any] | None = None
    command: dict[str, Any] | None = None
    account: dict[str, Any] | None = None
    languages: dict[str, Any] | None = None


class UnfoldSettings(DropUnset, BaseModel):
    """
    `UNFOLD`.
    """

    unfold: Unfold | dict[str, Any] | None = None
