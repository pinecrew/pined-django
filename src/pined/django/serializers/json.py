from collections.abc import Callable
from typing import Any, override

from django.core.serializers.json import DjangoJSONEncoder

try:
    from pydantic import BaseModel
except ImportError:
    BaseModel = None


class JSONEncoder(DjangoJSONEncoder):
    """
    Same as DjangoJSONEncoder, but with ensure_ascii=False and pydantic support
    """

    @override
    def __init__(
        self,
        *,
        skipkeys: bool = False,
        ensure_ascii: bool = False,
        check_circular: bool = True,
        allow_nan: bool = True,
        sort_keys: bool = False,
        indent: int | str | None = None,
        separators: tuple[str, str] | None = None,
        default: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__(
            skipkeys=skipkeys,
            ensure_ascii=ensure_ascii,
            check_circular=check_circular,
            allow_nan=allow_nan,
            sort_keys=sort_keys,
            indent=indent,
            separators=separators,
            default=default,
        )

    @override
    def default(self, o: Any) -> Any:
        if BaseModel and isinstance(o, BaseModel):
            return o.model_dump()
        return super().default(o)
