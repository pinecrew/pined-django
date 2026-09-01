"""
`change_admin_site` — the order the admin index lists things in.
"""

from collections.abc import Iterator, Sequence
from typing import Any

import pytest
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory

from pined.django.settings.admin import change_admin_site


@pytest.fixture(autouse=True)
def restore_admin_site() -> Iterator[None]:
    """
    Put `AdminSite.get_app_list` back.

    `change_admin_site` patches the class, not an instance, so a test that
    forgot this would reorder every admin that follows it.
    """

    original = admin.AdminSite.get_app_list
    yield
    admin.AdminSite.get_app_list = original


def listing(path: str = "/admin/") -> list[tuple[str, list[str]]]:
    """
    The index as the admin would build it for `path`, as labels and the
    model class names under them.
    """

    request = RequestFactory().get(path)
    request.user = User(is_superuser=True, is_staff=True, is_active=True)
    apps: Sequence[dict[str, Any]] = admin.site.get_app_list(request)
    return [(app["app_label"], [model["object_name"] for model in app["models"]]) for app in apps]


@pytest.mark.django_db
def test_the_order_is_followed() -> None:
    """
    Apps come out in the order they were named, and so do their models.

    Whatever the order left out keeps the admin's own sorting and goes
    last — `Device` among the models, and a whole app that nobody named.
    """

    change_admin_site({"testapp": ("Terminal",), "auth": ("User", "Group")})

    assert listing() == [("testapp", ["Terminal", "Device"]), ("auth", ["User", "Group"])]

    change_admin_site({"auth": ()})

    assert [label for label, _ in listing()] == ["auth", "testapp"]


@pytest.mark.django_db
def test_the_order_survives_the_first_request() -> None:
    """
    The caller's dict is left alone.

    It is bound into the `partialmethod` and shared by every request, while
    the app list is only what the current user may see on the current page.
    Writing the leftovers back would let the first request decide where the
    unnamed apps sit for everyone after it.
    """

    order: dict[str, Sequence[str]] = {"auth": ()}
    change_admin_site(order)

    listing("/admin/testapp/terminal/")

    assert order == {"auth": ()}
    assert [label for label, _ in listing()] == ["auth", "testapp"]


@pytest.mark.django_db
def test_the_unnamed_tail_is_sorted_the_way_the_admin_would(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Case-insensitively, which is what `AdminSite.get_app_list` does.

    Sorting by the verbose name as written puts every capitalised app ahead
    of every lower-cased one — "Banana" before "apple", where the admin
    would have put "apple" first.
    """

    original = admin.AdminSite._build_app_dict

    def relabelled(self: admin.AdminSite, request: Any, label: str | None = None) -> dict[str, Any]:
        built = original(self, request, label)
        for name, app in built.items():
            app["name"] = {"auth": "apple", "testapp": "Banana"}.get(name, app["name"])
        return built

    monkeypatch.setattr(admin.AdminSite, "_build_app_dict", relabelled)
    change_admin_site({})

    assert [label for label, _ in listing()] == ["auth", "testapp"]


@pytest.mark.django_db
def test_a_name_nobody_registered_is_skipped() -> None:
    """
    Naming an app or a model the admin has never heard of is not an error.
    """

    change_admin_site({"nosuchapp": ("Nothing",), "auth": ("Nothing", "Group", "User")})
    listed = listing()

    assert "nosuchapp" not in {label for label, _ in listed}
    assert dict(listed)["auth"] == ["Group", "User"]


@pytest.mark.django_db
def test_the_app_being_looked_at_goes_first() -> None:
    """
    Inside an app's own pages, that app heads the sidebar.
    """

    change_admin_site({"auth": (), "testapp": ()})

    assert listing("/admin/testapp/terminal/")[0][0] == "testapp"


@pytest.mark.django_db
def test_only_the_app_the_path_starts_with_goes_first() -> None:
    """
    An app url further down the path does not count.

    A char primary key ends up in `request.path` verbatim, and the sidebar
    can be rendered outside the admin altogether — neither is a reason to
    call the app the current one.
    """

    change_admin_site({"auth": (), "testapp": ()})

    assert listing("/dashboard/admin/testapp/")[0][0] == "auth"
