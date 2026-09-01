"""
The third-party stubs, and the one of them with behaviour.

Each `contrib` module declares a library's settings surface without
importing it, so a project can configure the library from the same place as
everything else. The assertion that matters for most of them is the same as
for the mixins: nothing arrives unasked.
"""

from typing import Any

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
from django.test import RequestFactory

from pined.django.settings import build_settings
from pined.django.settings.contrib.axes import AxesSettings
from pined.django.settings.contrib.debug_toolbar import DEBUG_VALUES, DebugToolbar, DebugToolbarSettings, get_debug
from pined.django.settings.contrib.easyaudit import EasyAuditSettings
from pined.django.settings.contrib.rest_framework import RestFramework, RestFrameworkSettings
from pined.django.settings.contrib.unfold import Unfold, UnfoldSettings

SPELLINGS = [*sorted(DEBUG_VALUES), "TRUE", "On", "YES"]


def build(part: type, **fields: Any) -> dict[str, Any]:
    """
    Assemble one stub the way a settings module would.
    """

    settings = build_settings(
        type(part.__name__, (part,), {"__annotations__": {}}),
        env_prefix="PINEDTEST_",
        env_file=None,
    )
    return settings.model_copy(update=fields).model_dump(by_alias=True)


@pytest.mark.parametrize(
    ("part", "expected"),
    [
        pytest.param(AxesSettings, {}, id="axes"),
        pytest.param(EasyAuditSettings, {}, id="easyaudit"),
        pytest.param(RestFrameworkSettings, {}, id="rest-framework"),
        pytest.param(UnfoldSettings, {}, id="unfold"),
        # The one field with a default: `get_debug` reads it per request.
        pytest.param(DebugToolbarSettings, {"DEBUG_PARAM": "debug"}, id="debug-toolbar"),
    ],
)
def test_a_bare_stub_brings_only_what_it_stands_behind(part: type, expected: dict[str, Any]) -> None:
    """
    A library the project has not configured keeps its own defaults.
    """

    assert build(part) == expected


def test_rest_framework_nests_upper_cased_and_keeps_a_none() -> None:
    """
    The inner dict gets the same treatment as the outer one.

    `UNAUTHENTICATED_USER` is where that matters: `None` there means
    "nobody", so a project that writes it down has it reach the library,
    while one that never mentions it keeps `rest_framework`'s own
    `AnonymousUser` rather than a restatement of it.
    """

    dumped = build(RestFrameworkSettings, rest_framework=RestFramework(page_size=25, search_param="filter[search]"))

    assert dumped["REST_FRAMEWORK"]["PAGE_SIZE"] == 25
    assert dumped["REST_FRAMEWORK"]["SEARCH_PARAM"] == "filter[search]"

    assert RestFramework().model_dump(by_alias=True) == {}
    assert RestFramework(unauthenticated_user=None).model_dump(by_alias=True) == {"UNAUTHENTICATED_USER": None}


def test_a_stub_takes_a_model_a_dict_or_a_callable() -> None:
    """
    A stub is a convenience, not a requirement.

    A callback given as the callable itself is what makes a
    `DEBUG`-plus-query check readable in a settings module.
    """

    assert build(UnfoldSettings, unfold=Unfold(site_title="Admin"))["UNFOLD"] == {"SITE_TITLE": "Admin"}
    assert build(UnfoldSettings, unfold={"SITE_TITLE": "Admin"})["UNFOLD"] == {"SITE_TITLE": "Admin"}

    dumped = DebugToolbar(show_toolbar_callback=get_debug).model_dump(by_alias=True)

    assert dumped["SHOW_TOOLBAR_CALLBACK"] is get_debug


def request_for(method: str, query: dict[str, str], user: str | None) -> HttpRequest:
    """
    A request, optionally from somebody.

    Args:
        method: `get` or `post`.
        query: The query string, as a dict.
        user: `"staff"`, `"plain"`, or `None` for a request that never met
            `AuthenticationMiddleware`.
    """

    request = getattr(RequestFactory(), method)("/", query)
    if user is not None:
        request.user = AnonymousUser()
        request.user.is_staff = user == "staff"
    return request


@pytest.mark.parametrize(
    ("overrides", "http_request", "expected"),
    [
        pytest.param({"DEBUG": True}, request_for("get", {}, None), True, id="debug-is-enough-on-its-own"),
        pytest.param({"DEBUG": False}, request_for("get", {}, "staff"), False, id="without-asking-nobody-sees-it"),
        *[
            pytest.param(
                {"DEBUG": False},
                request_for("get", {"debug": value}, "staff"),
                True,
                id=f"a-staff-member-asks-{value}",
            )
            for value in SPELLINGS
        ],
        pytest.param({"DEBUG": False}, request_for("get", {"debug": "maybe"}, "staff"), False, id="not-a-yes"),
        # The toolbar hands out SQL, settings and request data.
        pytest.param({"DEBUG": False}, request_for("get", {"debug": "1"}, "plain"), False, id="nobody-else-can-ask"),
        pytest.param({"DEBUG": False}, request_for("post", {"debug": "1"}, "staff"), False, id="only-a-get-counts"),
        pytest.param({"DEBUG": False}, request_for("get", {"debug": "1"}, None), False, id="no-request-user"),
        pytest.param(
            {"DEBUG": False, "DEBUG_PARAM": "peek"},
            request_for("get", {"peek": "1"}, "staff"),
            True,
            id="the-parameter-can-be-renamed",
        ),
        pytest.param(
            {"DEBUG": False, "DEBUG_PARAM": "peek"},
            request_for("get", {"debug": "1"}, "staff"),
            False,
            id="and-then-the-old-name-stops-working",
        ),
    ],
)
def test_get_debug(settings: Any, overrides: dict[str, Any], http_request: HttpRequest, expected: bool) -> None:
    """
    Who is allowed to see the toolbar, and when.

    With `DEBUG` on, everybody. With it off, a staff member can still ask
    for one response by name — and the name is read per request, so a
    deployment can rename it from the environment.
    """

    for name, value in overrides.items():
        setattr(settings, name, value)

    assert get_debug(http_request) is expected
