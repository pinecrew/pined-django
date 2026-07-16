from __future__ import annotations

import hashlib
import json
from typing import Any, get_args, get_origin

import pydantic

from pined.django.serializers.json import JSONEncoder

__all__ = ("describe_model", "generate_model_hash")


class _SchemaGenerator:
    """
    As it turns out, BaseModel.model_json_schema() fails to work when the
    models contain json_schema_extra with sneaky little tricks like having lazy
    translations inside them, e.g.:
    ```
    value: str = pydantic.Field(
        "00AAFF",
        title=pgettext_lazy("Model context", "Value"),
        pattern=r"^([0-9A-F]{2})*$",
        # this would break BaseModel.model_json_schema()
        json_schema_extra={"error_message": pgettext_lazy("Model context", "Enter a valid hexadecimal string")},
    )
    ```
    The thing is, when generating the schema, Pydantic uses its internal
    to_jsonable_python serialization, making it impossible to pass a custom
    JSONEncoder that would handle Django's Promise objects.
    Therefore, we're rolling our own schema generation here.
    """

    @classmethod
    def describe_annotation(cls, annotation: Any, seen: set[type]) -> Any:
        if isinstance(annotation, type) and issubclass(annotation, pydantic.BaseModel):
            return cls.describe_model(annotation, seen)

        origin = get_origin(annotation)
        if origin is not None:
            return {
                "origin": repr(origin),
                "args": [cls.describe_annotation(ann, seen) for ann in get_args(annotation)],
            }
        return repr(annotation)

    @classmethod
    def describe_metadata_item(cls, item: Any) -> Any:
        result = repr(item)
        if " at 0x" in result:
            return f"<{type(item).__module__}.{type(item).__qualname__}>"

        # The validator's repr contains the function's repr, which includes a
        # memory address from that exact moment. This is just a tiny bit
        # inconsistent between runs, so let's build the representation manually,
        # shall we?
        fields = getattr(item, "__dataclass_fields__", None)
        if fields is not None:
            return {
                "type": type(item).__qualname__,
                "fields": {name: cls.describe_metadata_item(getattr(item, name)) for name in fields},
            }

        return result

    @classmethod
    def describe_field(cls, field: pydantic.fields.FieldInfo, seen: set[type]) -> dict:
        return {
            "annotation": cls.describe_annotation(field.annotation, seen),
            "required": field.is_required(),
            "default": None if field.is_required() else repr(field.default),
            "default_factory": cls.describe_metadata_item(field.default_factory) if field.default_factory else None,
            "metadata": [cls.describe_metadata_item(item) for item in (field.metadata or [])],
            # purposefully skipping the json_schema_extra
        }

    @classmethod
    def describe_model(cls, model: type[pydantic.BaseModel], seen: set[type]) -> dict:
        model_ref = f"{model.__module__}.{model.__qualname__}"
        if model in seen:
            return {"__ref__": model_ref}

        seen.add(model)
        return {
            "__model__": model_ref,
            "fields": {name: cls.describe_field(field, seen) for name, field in model.model_fields.items()},
        }

    @classmethod
    def describe(cls, model: type[pydantic.BaseModel]) -> dict:
        return cls.describe_model(model, seen=set())

    @classmethod
    def generate(cls, model: type[pydantic.BaseModel]) -> str:
        schema = cls.describe(model)
        payload = json.dumps(schema, sort_keys=True, cls=JSONEncoder).encode()
        return hashlib.sha256(payload).hexdigest()[:16]


def describe_model(model: type[pydantic.BaseModel]) -> dict[str, Any]:
    return _SchemaGenerator.describe(model)


def generate_model_hash(model: type[pydantic.BaseModel]) -> str:
    return _SchemaGenerator.generate(model)
