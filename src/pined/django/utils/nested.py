import contextlib
from typing import Any


def get_nested(obj: Any, *path: int | str, default: Any = None) -> Any:
    for val in path:
        attr = val

        if isinstance(obj, dict):
            try:
                obj = obj[attr]
            except (KeyError, TypeError):
                return default

        elif isinstance(obj, list):
            with contextlib.suppress(Exception):
                attr = int(attr)

            try:
                obj = obj[attr]
            except (IndexError, TypeError):
                return default

        elif isinstance(attr, str):
            try:
                obj = getattr(obj, attr)
            except AttributeError:
                return default

        else:
            return default
    return obj
