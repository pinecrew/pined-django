"""
Loading a settings module the way django would — once, freshly.
"""

import importlib
import sys
from collections.abc import Callable, Iterator
from types import ModuleType

import pytest

type Loader = Callable[[str], ModuleType]


@pytest.fixture
def load_settings() -> Iterator[Loader]:
    """
    Return a loader that imports one of `fixtures/` from scratch.

    `configure` runs while the module is being imported, so anything the
    settings are meant to read has to be in place before the import — and
    the module has to be gone from `sys.modules` for the import to happen
    at all.
    """

    loaded: list[str] = []

    def load(name: str) -> ModuleType:
        path = f"tests.settings.fixtures.{name}"
        sys.modules.pop(path, None)
        loaded.append(path)
        return importlib.import_module(path)

    yield load

    for path in loaded:
        sys.modules.pop(path, None)
