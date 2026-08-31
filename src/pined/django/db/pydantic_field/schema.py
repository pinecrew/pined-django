"""
Tracking of `PydanticField` schema versions across migrations.

Each `(app, model, field)` triple gets its own JSON file, next to that
app's migrations, mapping a schema hash to the schema it was taken over.
`AlterPydantic` migrations reference these hashes so old and new versions
of a Pydantic model can both be reconstructed later, e.g. to migrate data
between them.

What is stored is the *normalized* schema. The hash answers one question
— does the stored data have to be migrated? — so it has to be taken over
what pydantic would accept and reject, and nothing else. A json schema
carries plenty besides: the model's own name and docstring, a title per
field, whatever `Field(description=...)` was given. Hashing that would
mean a renamed class or a rewritten comment rewrites every row in the
table.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from typing import TYPE_CHECKING, Any, ClassVar

from django.db.migrations import Migration
from django.db.migrations.writer import MigrationWriter
from pined.django.serializers.json import JSONEncoder

try:
    from json_schema_to_pydantic import create_model
except ImportError as exc:
    msg = 'To use PydanticField, install package with "pydantic-field" option: pined-django[pydantic-field].'
    raise ImportError(msg) from exc


if TYPE_CHECKING:
    import pydantic


class SchemaManager:
    """
    Reads and writes the schema-version file for one `PydanticField`.

    Identified by `app_label`/`model_name`/`field_name` rather than the
    field itself, since during migrations the field isn't attached to a
    live model.
    """

    FILE_NAME: ClassVar[str] = "_schema_{model_name}__{field_name}.json"

    COSMETIC: ClassVar[frozenset[str]] = frozenset(
        {"title", "description", "examples", "deprecated", "$comment", "readOnly", "writeOnly"}
    )
    """Schema keys that document a schema without constraining it."""

    SET_LIKE: ClassVar[frozenset[str]] = frozenset({"required", "enum"})
    """Schema keys json schema reads as a set, and pydantic writes in declaration order."""

    SUBSCHEMA: ClassVar[frozenset[str]] = frozenset(
        {
            "additionalItems",
            "additionalProperties",
            "contains",
            "contentSchema",
            "else",
            "if",
            "items",
            "not",
            "propertyNames",
            "then",
            "unevaluatedItems",
            "unevaluatedProperties",
        }
    )
    """Schema keys holding one subschema — or, for `items`, a list of them."""

    SUBSCHEMA_LIST: ClassVar[frozenset[str]] = frozenset({"allOf", "anyOf", "oneOf", "prefixItems"})
    """Schema keys holding a list of subschemas."""

    SUBSCHEMA_MAP: ClassVar[frozenset[str]] = frozenset(
        {"$defs", "definitions", "dependentSchemas", "patternProperties", "properties"}
    )
    """Schema keys holding subschemas keyed by name — the names are not keywords."""

    REF_PREFIX: ClassVar[str] = "#/$defs/"

    app_label: str
    model_name: str
    field_name: str
    versions: dict[str, dict[str, Any]]

    def __init__(self, app_label: str, model_name: str, field_name: str) -> None:
        # On migration stage, fields don't have `model` attribute set. Smh,
        # that would be so much cleaner — only field arg would be needed
        # instead of all these strings.

        self.app_label = app_label
        self.model_name = model_name
        self.field_name = field_name
        self.versions = {}

        self.load_versions()

    def get_filename(self) -> str:
        """
        The schema file's name for this field, e.g.
        `_schema_options__logging.json`.
        """

        return self.FILE_NAME.format(model_name=self.model_name, field_name=self.field_name)

    @property
    def basedir(self) -> pathlib.Path:
        """
        The app's migrations directory, resolved the same way Django
        itself would.
        """

        # MigrationWriter is the only way (I think?) to get correct migration
        # directory with all the necessary actions and checks done on the way.
        if not hasattr(self, "_basedir"):
            empty = Migration("empty", self.app_label)
            writer = MigrationWriter(empty)
            self._basedir = pathlib.Path(writer.basedir)
        return self._basedir

    @property
    def file(self) -> pathlib.Path:
        """
        Full path to this field's schema-version file.
        """

        return self.basedir / self.get_filename()

    def load_versions(self) -> None:
        """
        Read known schema versions from disk, creating an empty file if
        none exists yet.
        """

        if not self.file.exists():
            self.file.touch()
            self.file.write_text("{}")
        self.versions |= json.loads(self.file.read_text())

    @classmethod
    def describe_model(cls, model: type[pydantic.BaseModel]) -> dict[str, Any]:
        """
        Return `model`'s JSON schema.
        """

        return model.model_json_schema()

    @classmethod
    def normalize(cls, schema: dict[str, Any]) -> dict[str, Any]:
        """
        Return a copy of `schema` carrying only what affects validation.

        Three passes' worth:

        - documentation keys go, in every subschema;
        - `required` and `enum` are sorted, since json schema reads them
          as sets while pydantic emits them in declaration order;
        - `$defs` keys are renumbered by the order they are first
          reached, and every `$ref` follows — a nested model's class name
          lives in the `$defs` key and inside the `$ref` string, not only
          in its `title`.

        Args:
            schema: A json schema, as `model_json_schema()` returns it.
                Left untouched — every level is rebuilt rather than
                edited.

        Returns:
            The same schema with documentation dropped, set-like lists
            sorted and `$defs` named after the order they are used.

        Note:
            `COSMETIC` is a denylist, deliberately. `json_schema_extra`
            is inlined into a property's schema as ordinary sibling keys,
            so an unrecognised key cannot be told apart from a real json
            schema keyword — and it may well mean something to whoever
            put it there. Which is why the denylist is only ever applied
            where a keyword can sit; see `_strip`.
        """

        return cls._canonical_refs(cls._strip(schema))

    @classmethod
    def _sort_key(cls, value: Any) -> str:
        """
        Order values of mixed types, as a `Literal[1, "a"]` produces.
        """

        return json.dumps(value, sort_keys=True, default=repr)

    @classmethod
    def _strip(cls, schema: Any) -> Any:
        """
        Drop documentation and sort set-like lists, through every
        subschema.

        Walks by position rather than by name: only the keys that json
        schema says hold subschemas are followed, and the names under
        `properties` are read as names. `title` means one thing as a
        keyword and quite another as a field called `title` — a walk that
        cannot tell them apart drops the field.

        Args:
            schema: A subschema. Booleans are a schema too —
                `additionalProperties: false` — and pass through.
        """

        if not isinstance(schema, dict):
            return schema

        stripped: dict[str, Any] = {}
        for key, value in schema.items():
            if key in cls.COSMETIC:
                continue
            if key in cls.SET_LIKE and isinstance(value, list):
                stripped[key] = sorted(value, key=cls._sort_key)
            elif key in cls.SUBSCHEMA_MAP and isinstance(value, dict):
                stripped[key] = {name: cls._strip(body) for name, body in value.items()}
            elif key in cls.SUBSCHEMA_LIST and isinstance(value, list):
                stripped[key] = [cls._strip(item) for item in value]
            elif key in cls.SUBSCHEMA:
                stripped[key] = [cls._strip(item) for item in value] if isinstance(value, list) else cls._strip(value)
            else:
                # A default, a `const`, whatever `json_schema_extra` carried:
                # data, and nothing to walk into.
                stripped[key] = value
        return stripped

    @classmethod
    def _claim_names(cls, node: Any, defs: dict[str, Any], names: dict[str, str]) -> None:
        """
        Number every `$defs` entry reachable from `node`, first reached
        first.

        Claiming a name before following the reference is what keeps a
        self-referencing model from walking forever.
        """

        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith(cls.REF_PREFIX):
                name = ref.removeprefix(cls.REF_PREFIX)
                if name not in names and name in defs:
                    names[name] = f"d{len(names)}"
                    cls._claim_names(defs[name], defs, names)
            for key in sorted(node):
                cls._claim_names(node[key], defs, names)
        elif isinstance(node, list):
            for item in node:
                cls._claim_names(item, defs, names)

    @classmethod
    def _canonical_refs(cls, schema: dict[str, Any]) -> dict[str, Any]:
        """
        Rename `$defs` to `d0..dN` by the order they are first reached.

        Numbering follows use rather than content, which keeps it
        independent of the class names pydantic derived the keys from —
        including the module path it prepends once two nested models
        share a name.
        """

        defs = schema.get("$defs")
        if not defs:
            return schema

        names: dict[str, str] = {}
        cls._claim_names({key: value for key, value in schema.items() if key != "$defs"}, defs, names)
        for name in sorted(defs):  # nothing points at these, but they still need a name
            names.setdefault(name, f"d{len(names)}")

        return cls._rewrite(schema, names)

    @classmethod
    def _rewrite(cls, node: Any, names: dict[str, str], *, root: bool = True) -> Any:
        """
        Apply a `$defs` renaming to the keys and to every `$ref` string.
        """

        if isinstance(node, dict):
            rewritten = {}
            for key, value in node.items():
                if key == "$ref" and isinstance(value, str) and value.startswith(cls.REF_PREFIX):
                    name = value.removeprefix(cls.REF_PREFIX)
                    rewritten[key] = cls.REF_PREFIX + names.get(name, name)
                elif key == "$defs" and root:
                    rewritten[key] = {
                        names[name]: cls._rewrite(body, names, root=False) for name, body in value.items()
                    }
                else:
                    rewritten[key] = cls._rewrite(value, names, root=False)
            return rewritten
        if isinstance(node, list):
            return [cls._rewrite(item, names, root=False) for item in node]
        return node

    @classmethod
    def generate_model_hash(cls, model: type[pydantic.BaseModel]) -> tuple[str, dict[str, Any]]:
        """
        Fingerprint `model`, returning `(hash, normalized schema)`.

        The hash covers what pydantic would accept and reject, and
        nothing else: two models declaring the same fields with the same
        types, defaults and constraints hash the same however they are
        named, wherever they are defined, and in whatever order the
        fields were written. `normalize` is what draws that line.

        Returns:
            The hash, and the schema it was taken over — which is also
            the one that belongs on disk.
        """

        schema = cls.normalize(cls.describe_model(model))
        serialized = json.dumps(schema, sort_keys=True, cls=JSONEncoder)
        model_hash = hashlib.sha256(serialized.encode()).hexdigest()[:16]
        return model_hash, schema

    def save_version(self, model: type[pydantic.BaseModel]) -> None:
        """
        Record `model`'s current schema under its hash, persisting to
        disk.
        """

        model_hash, schema = self.generate_model_hash(model)
        self.versions[model_hash] = schema
        self.file.write_text(json.dumps(self.versions, sort_keys=True, cls=JSONEncoder, indent=2))

    def version_exists(self, model_hash: str) -> bool:
        """
        Whether `model_hash` has already been recorded.
        """

        return model_hash in self.versions

    def ensure_version(self, model_hash: str, model: type[pydantic.BaseModel]) -> None:
        """
        Record `model`'s schema under `model_hash` unless it's already
        known.
        """

        if not self.version_exists(model_hash):
            self.save_version(model)

    def get_model(self, model_hash: str) -> type[pydantic.BaseModel]:
        """
        Reconstruct the Pydantic model that produced `model_hash`, from
        its recorded schema.

        The recorded schema carries no `title`, since a model's name is
        not part of its shape — so one is handed back here. It is all
        `create_model` uses it for, and without it a failing row would be
        reported against an anonymous `DynamicModel` instead of the field
        it came from.
        """

        version = self.versions[model_hash]
        return create_model({"title": f"{self.model_name}.{self.field_name}", **version})
