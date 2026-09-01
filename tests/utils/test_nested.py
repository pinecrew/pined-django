"""
`get_nested` — one path over dicts, lists and objects.
"""

import dataclasses
from typing import Any

import pytest

from pined.django.utils.nested import get_nested


@dataclasses.dataclass
class Node:
    """
    Something reached by attribute rather than by key.
    """

    name: str = "leaf"


PAYLOAD = {"data": {"items": [{"name": "first"}, {"name": "second"}], "node": Node()}}


@pytest.mark.parametrize(
    ("obj", "path", "expected"),
    [
        pytest.param({"a": 1}, ("a",), 1, id="dict-key"),
        pytest.param({"a": 1}, ("missing",), None, id="missing-key"),
        pytest.param({"a": 1}, ("a", "deeper"), None, id="through-a-scalar"),
        pytest.param(["first"], ("0",), "first", id="list-index-as-a-string"),
        pytest.param(["first"], (0,), "first", id="list-index-as-a-number"),
        pytest.param(["first"], ("7",), None, id="index-out-of-range"),
        pytest.param(["first"], ("nope",), None, id="index-that-is-not-a-number"),
        pytest.param({"a": 1}, (0,), None, id="an-index-into-a-dict"),
        pytest.param(object(), (0,), None, id="a-path-step-that-fits-nothing"),
        pytest.param(Node(), ("name",), "leaf", id="an-attribute"),
        pytest.param(Node(), ("nothing",), None, id="an-attribute-nobody-carries"),
        # The whole point: three kinds of step in one path.
        pytest.param(PAYLOAD, ("data", "items", 1, "name"), "second", id="dict-list-dict"),
        pytest.param(PAYLOAD, ("data", "node", "name"), "leaf", id="dict-object"),
        pytest.param(PAYLOAD, ("data", "items", "0", "name"), "first", id="the-index-written-as-a-string"),
    ],
)
def test_what_a_path_reaches(obj: Any, path: tuple[Any, ...], expected: Any) -> None:
    """
    Each kind of step, and the ones that give out.
    """

    assert get_nested(obj, *path) == expected


@pytest.mark.parametrize(
    ("obj", "path"),
    [
        pytest.param({"a": 1}, ("missing",), id="a-key-nobody-put-there"),
        pytest.param(["first"], ("7",), id="past-the-end"),
        pytest.param(Node(), ("nothing",), id="an-attribute-nobody-carries"),
        pytest.param(PAYLOAD, ("data", "items", 9, "name"), id="halfway-along"),
    ],
)
def test_default_comes_back_wherever_it_gives_out(obj: Any, path: tuple[Any, ...]) -> None:
    """
    `default` is the answer at the first step that does not resolve.

    Including partway along a longer path — the walk ends there rather
    than carrying `None` into the steps that follow.
    """

    sentinel = object()

    assert get_nested(obj, *path, default=sentinel) is sentinel


def test_an_empty_path_is_the_object_itself() -> None:
    """
    Nothing to walk, nothing to give out.
    """

    assert get_nested(PAYLOAD) is PAYLOAD
    assert get_nested(None, default="unused") is None


def test_a_step_int_cannot_take_at_all() -> None:
    """
    `int()` refuses more than a bad string.

    Both steps below are outside what `*path` is annotated to take, and
    that is the case: the function exists for payloads whose shape nobody
    controls, and the path into one is as likely to come from untyped data
    as the payload is. The conversion used to be wrapped in a bare
    `except Exception`, which hid the difference between "not a number"
    and "not something a number can be made of" — along with anything else
    that might have gone wrong in there.
    """

    assert get_nested(["first"], (1, 2)) is None
    assert get_nested(["first"], None) is None
