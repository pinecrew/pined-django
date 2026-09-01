from typing import Any, override

from django.core.serializers.json import DjangoJSONEncoder

try:
    from pydantic import BaseModel
except ImportError:
    BaseModel = None


class JSONEncoder(DjangoJSONEncoder):
    """
    `DjangoJSONEncoder` that keeps non-ASCII as it is and knows pydantic.
    """

    @override
    def __init__(self, *args, **kwargs) -> None:
        """
        Set up the encoder, with `ensure_ascii` off whatever was asked for.

        Overridden rather than defaulted, because a default here would
        never be reached. `json.dumps` fills in every one of its own
        parameters before handing them to `cls` — `ensure_ascii=True`
        among them — so the encoder is always told to escape, by callers
        who never mentioned it. Django's `adapt_json_value`, which is how
        a `PydanticField` reaches the column, is one of them.

        Restating the parent's parameters to change one of them is the
        other way to write this, and it drops any parameter a future
        python adds on the floor.
        """

        kwargs["ensure_ascii"] = False
        super().__init__(*args, **kwargs)

    @override
    def default(self, o: Any) -> Any:
        """
        Reduce what plain json cannot hold to something it can.

        Args:
            o: Whatever the encoder ran into.

        Returns:
            A pydantic model as its `model_dump`, and everything else as
            django would have it.

        Raises:
            TypeError: Nothing here knows what `o` is.
        """

        if BaseModel and isinstance(o, BaseModel):
            return o.model_dump()
        return super().default(o)
