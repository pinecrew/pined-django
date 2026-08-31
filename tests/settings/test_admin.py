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

    assert {label for label, _ in listing()} == {"auth", "testapp"}


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
