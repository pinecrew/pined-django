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
    app["models"].sort(key=lambda model: (_get_index(objects, model["object_name"]), model["name"]))
    return app


def _get_app_list(
    self: admin.AdminSite,
    request: HttpRequest,
    app_label: str | None = None,
    admin_app_order: dict[str, Sequence[str]] | None = None,
) -> list[AppModel]:
    # The menu's modules, as a dict keyed by app label.
    app_dict: dict[str, AppModel] = self._build_app_dict(request, app_label)

    # A copy: the dict is bound into the partialmethod, so every request
    # shares it, and `_build_app_dict` returns only what this user may see
    # on this page — that must not become everybody's order.
    order = dict(admin_app_order or {})
    # Whatever the intended order left out, in the order the admin would
    # have used on its own — which is `name.lower()`, not `name`, so a
    # verbose name that starts lower-cased lands where the admin puts it.
    for key in sorted(set(app_dict) - set(order), key=lambda label: app_dict[label]["name"].lower()):
        order[key] = ()

    app_list = []
    for app_name, object_list in order.items():
        app = _process_app(app_dict, app_name, object_list)
        if not app:
            continue

        if request.path.startswith(app["app_url"]):  # the app whose pages we are on heads the list
            app_list.insert(0, app)
        else:
            app_list.append(app)

    return app_list


def change_admin_site(admin_app_order: dict[str, Sequence[str]]) -> None:
    """
    Order the admin index the way `admin_app_order` says.

    Call it once the settings are up — the settings module itself is the
    usual place. Apps go in under their `label`, models under their class
    name. Whatever is left out keeps the admin's own ordering and comes
    last, an unnamed model after the named ones and an unnamed app after
    the named ones.

    Args:
        admin_app_order: App labels, each holding its models in order.

    Example:
        Three apps, three models each. "media" first with its models
        spelled out, then "books" — where "Genre" goes unnamed and so
        lands after "Book" — and then "videos", which nobody named at
        all:

        ```
        configure(General, Apps, Database)

        change_admin_site(
            {
                "media": ("Artist", "Album", "Song"),
                "books": ("Author", "Book"),
            }
        )
        ```
    """

    # pyrefly: ignore[bad-assignment]  # a `partialmethod` is a descriptor, and reads back as the method
    admin.AdminSite.get_app_list = functools.partialmethod(_get_app_list, admin_app_order=admin_app_order)
