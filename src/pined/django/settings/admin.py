from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from django.contrib import admin

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import TypedDict

    from django.db import models
    from django.http import HttpRequest

    class ModelDict(TypedDict):
        model: type[models.Model]
        name: str
        object_name: str
        perms: dict[str, bool]
        admin_url: str
        add_url: str
        view_only: bool

    class AppModel(TypedDict):
        name: str
        app_label: str
        app_url: str
        has_module_perms: bool
        models: list[ModelDict]


def _get_index[T](iterable: Sequence[T], value: T) -> int:
    try:
        return iterable.index(value)
    except ValueError:
        return len(iterable)


def _process_app(initial: dict[str, AppModel], name: str, objects: Sequence[str]) -> AppModel | None:
    app: AppModel | None = initial.get(name)
    if not app:
        return None
    app["models"].sort(key=lambda x: (_get_index(objects, x["object_name"]), x["name"]))
    return app


def _get_app_list(
    self: admin.AdminSite,
    request: HttpRequest,
    app_label: str | None = None,
    admin_app_order: dict[str, Sequence[str]] | None = None,
) -> list[AppModel]:
    admin_app_order = admin_app_order or {}

    app_dict: dict = self._build_app_dict(request, app_label)  # the menu's modules, as a dict
    for key in set(app_dict) - set(admin_app_order):  # whatever the intended order left out
        admin_app_order[key] = ()

    app_list = []
    for app_name, object_list in admin_app_order.items():
        app = _process_app(app_dict, app_name, object_list)
        if not app:
            continue

        if app.get("app_url") in request.path:
            app_list.insert(0, app)
        else:
            app_list.append(app)

    return app_list


def change_admin_site(admin_app_order: dict[str, Sequence[str]]) -> None:
    """
    Change the admin apps and models order according to `admin_app_order`.

    Function should be called after settings are set up, e.g., in the settings
    module itself. Apps must be listed as their `label` values, models must be
    listed as their class names.

    Example:
        There are three apps: "media", "books" and "videos". Each app has three models.
        Let's set "media" app as first, with models in the following order: "Artist", "Album", "Song".
        Then set "books" app as next, with models in the following order: "Author", "Book".
        Now, because it wasn't specified, third model in "books" app, "Genre" will come after "Book".
        And "videos" app will come after "books" app with default order of models.

        >>> ...
        >>> configure(General, Apps, Database)
        >>>
        >>> admin_order = {
        >>>     "media": ("Artist", "Album", "Song"),
        >>>     "books": ("Author", "Book"),  # "Genre" will be the last model
        >>>     # "videos": ("Video", "Channel", "Comment")  # default model order
        >>> }
        >>> change_admin_site(admin_order)

    Args:
        admin_app_order: dict with app labels as keys and lists of models as values.
    """

    admin.AdminSite.get_app_list = functools.partialmethod(_get_app_list, admin_app_order=admin_app_order)
