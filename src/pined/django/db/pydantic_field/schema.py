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
    FILE_NAME: ClassVar[str] = "_schema_{model_name}__{field_name}.json"

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
        return self.FILE_NAME.format(model_name=self.model_name, field_name=self.field_name)

    @property
    def basedir(self) -> pathlib.Path:
        # MigrationWriter is the only way (I think?) to get correct migration
        # directory with all the necessary actions and checks done on the way.
        if not hasattr(self, "_basedir"):
            empty = Migration("empty", self.app_label)
            writer = MigrationWriter(empty)
            self._basedir = pathlib.Path(writer.basedir)
        return self._basedir

    @property
    def file(self) -> pathlib.Path:
        return self.basedir / self.get_filename()

    def load_versions(self) -> None:
        if not self.file.exists():
            self.file.touch()
            self.file.write_text("{}")
        self.versions |= json.loads(self.file.read_text())

    @staticmethod
    def describe_model(model: type[pydantic.BaseModel]) -> dict[str, Any]:
        return model.model_json_schema()

    @staticmethod
    def generate_model_hash(model: type[pydantic.BaseModel]) -> tuple[str, dict[str, Any]]:
        schema = SchemaManager.describe_model(model)
        serialized = json.dumps(schema, sort_keys=True, cls=JSONEncoder)
        model_hash = hashlib.sha256(serialized.encode()).hexdigest()[:16]
        return model_hash, schema

    def save_version(self, model: type[pydantic.BaseModel]) -> None:
        model_hash, schema = self.generate_model_hash(model)
        self.versions[model_hash] = schema
        self.file.write_text(json.dumps(self.versions, sort_keys=True, cls=JSONEncoder, indent=2))

    def version_exists(self, model_hash: str) -> bool:
        return model_hash in self.versions

    def ensure_version(self, model_hash: str, model: type[pydantic.BaseModel]) -> None:
        if not self.version_exists(model_hash):
            self.save_version(model)

    def get_model(self, model_hash: str) -> type[pydantic.BaseModel]:
        version = self.versions[model_hash]
        return create_model(version)
