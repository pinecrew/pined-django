"""
What the package does with the optional extras left out.

`pip install pined-django` pulls in nothing but django, and the README
promises two things for that install: the management commands fall through
to django's own, and anything needing an extra says which one. No other
cell of the matrix can see either — they all install everything.

Every test here is skipped when `pydantic` is importable, so the file is
only doing its job in the one CI cell that leaves it out.
"""

import importlib
from importlib.util import find_spec

import pytest
from django.core.management import call_command, load_command_class

pytestmark = pytest.mark.skipif(find_spec("pydantic") is not None, reason="pydantic is installed")


@pytest.mark.parametrize("name", ["makemigrations", "migrate"])
def test_the_command_falls_through_to_django(name: str) -> None:
    """
    With no autodetector to add, django's own command is what
    `"pined.django"` in `INSTALLED_APPS` ends up providing.
    """

    command = load_command_class("pined.django", name)

    assert type(command).__module__ == f"django.core.management.commands.{name}"


def test_the_app_still_checks_out() -> None:
    """
    A bare install boots: the app registry loads and `check` passes.
    """

    call_command("check")


@pytest.mark.parametrize(
    ("module", "extra"),
    [("pined.django.settings", "settings"), ("pined.django.db.models", "pydantic-field")],
    ids=["settings", "pydantic-field"],
)
def test_importing_a_module_behind_an_extra_names_the_extra(module: str, extra: str) -> None:
    """
    The error says which install to do, not which import failed.
    """

    with pytest.raises(ImportError, match=rf"pined-django\[{extra}\]"):
        importlib.import_module(module)
