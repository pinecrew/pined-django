import contextlib
from typing import Any


def get_nested(obj: Any, *path: int | str, default: Any = None) -> Any:
    """
    Walks `path` into `obj`, handing back `default` where it gives out.

    Each step reads a dict by key, a list by index and anything else by
    attribute, so one path crosses all three without a line of `if` and
    `try` per level. A step that does not resolve — a key nobody put
    there, an index past the end, an attribute the object does not carry
    — ends the walk, and `default` comes back. An index may be written as
    a string, since that is how one arrives inside a dotted path.

    Args:
        obj: What the first step is taken against.
        *path: The steps, in order.
        default: Handed back at the first step that does not resolve.

    Returns:
        Whatever sits at the end of `path`, or `default`.

    Example:
        ```
        get_nested(payload, "data", "items", 0, "name", default="")
        ```
    """

    for val in path:
        attr = val

        if isinstance(obj, dict):
            try:
                obj = obj[attr]
            except (KeyError, TypeError):
                return default

        elif isinstance(obj, list):
            # `ValueError` for a step that is not a number, `TypeError` for
            # one `int` will not take at all.
            with contextlib.suppress(ValueError, TypeError):
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
