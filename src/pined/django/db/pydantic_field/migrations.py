from __future__ import annotations

import ast
import json
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

import pydantic

from django.db import migrations, models
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.operations.base import Operation, OperationCategory
from django.db.migrations.questioner import InteractiveMigrationQuestioner
from pined.django.serializers.json import JSONEncoder

from .field import PydanticField

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from django.db.backends.base.schema import BaseDatabaseSchemaEditor
    from django.db.migrations.graph import MigrationGraph
    from django.db.migrations.state import ProjectState
    from django.utils.connection import ConnectionProxy


class P:
    """
    Get a value from another field of the Pydantic model.
    """

    __slots__ = ("field_name",)

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name


class R:
    """
    Rename a field in the Pydantic model.
    """

    __slots__ = ("old_name",)

    def __init__(self, old_name: str) -> None:
        self.old_name = old_name


class AlterPydantic(Operation):
    __module__ = "pined.django.db.models"

    reduces_to_sql = False  # doesn't run in sqlmigrate
    reversible = True  # can roll back to the state before this operation
    atomic = True
    category = OperationCategory.ALTERATION  # purely for the "~" symbol

    def __init__(  # noqa: PLR0913
        self,
        model_name: str,
        name: str,
        schema_hash: str,
        previous_schema_hash: str | None = None,
        forwards_defaults: dict[str, Any] | None = None,
        backwards_defaults: dict[str, Any] | None = None,
        forwards_transform: Callable[[dict | list], dict | list] | None = None,
        backwards_transform: Callable[[dict | list], dict | list] | None = None,
        override_fields: list[str] | Literal["*"] | None = None,
    ) -> None:
        """
        Perform actions related to changing internal Pydantic model.

        Args:
            model_name: Name of the Django model, e.g., "PaymentSystemConfig"
            name: Field name, e.g., "contactless"
            schema_hash: Hash of the new schema
            previous_schema_hash: Hash of the previous schema
            forwards_defaults: Default values for migrating to the new schema
            backwards_defaults: Default values for rolling back to the previous
                schema
            forwards_transform: Value transformation function when migrating
                to the new schema. Applied after adding default values
            backwards_transform: Value transformation function when rolling back
                to the new schema. Applied after adding default values
            override_fields: Names of fields which values should be overridden
                from the default values

        Examples:
            - A standard field migration without doing anything fancy:
              ```
              AlterPydantic(
                  model_name="integrations",
                  name="bio_acquiring",
                  schema_hash="010ec46d2fa44a77",
              ),
              ```

            - In `forwards_defaults` and `backwards_defaults`, you can use
              `models.F` to copy data from another field of the Django model.
              To copy data from another field of the Pydantic model, use `P`:
              ```
              AlterPydantic(
                  model_name="terminal",
                  name="metadata",
                  schema_hash="3a14deee5c255329",
                  forwards_defaults={
                      "current_software_version": models.F("current_software_version"),
                      "android_version": P("os_version"),
                  },
              )
              ```

            - When creating a new field, `forwards_defaults` will override the
              default values from the Pydantic model. In other cases, you can
              manually select which fields values should be overriden with the
              values from the defaults. If you want to override all the fields,
              you can pass an asterisk `"*"` instead. **If the field already
              has user data, it will be wiped**:
              ```
              AlterPydantic(
                  model_name="options",
                  name="logging",
                  schema_hash="82ba0e105240e9da",
                  forwards_defaults={
                      "max_backup": 20,
                      "terminal_log_retention": 10,  # None is the default for field in model
                  },
                  # terminal_log_retention won't change in the entries where it wasn't None,
                  # since it does not match the default value.
                  # max_backup, on the other hand, will become 20 in every instance,
                  # since it is passed in override_fields
                  override_fields=["max_backup"],
              )
              ```

            - If you need to remove a field or do something more complex, you
              can use `forwards_transform` and `backwards_transform`. It is
              applied after `forwards_defaults` and `backwards_defaults`, thus
              you can use new values in the transformer function. Also, you can
              use `R` to rename a field (*`R` values are applied before `P`
              values*):
              ```
              def update_version_field(data: dict[str, Any]) -> dict[str, Any]:
                    # here data is underlying json value of Pydantic field
                    data.pop("current_software_version", None)
                    data["software_version"] = random.randint(0, 20)
                    return data

              AlterPydantic(
                  model_name="terminal",
                  name="metadata",
                  schema_hash="3a14deee5c255329",
                  forwards_defaults={
                      # rename "os_version" to "android_version"
                      "android_version": R("os_version"),
                      # notice, that here P uses value from R
                      "also_version": P("android_version"),
                  },
                  forwards_transform=delete_version_field,
              )
              ```
        """

        self.model_name = model_name.lower()
        self.name = name
        self.schema_hash = schema_hash
        self.previous_schema_hash = previous_schema_hash
        self.forwards_defaults = forwards_defaults or {}
        self.backwards_defaults = backwards_defaults or {}
        self.forwards_transform = forwards_transform
        self.backwards_transform = backwards_transform
        self.override_fields = override_fields

    def describe(self) -> str:
        return f"Revalidate data in {self.model_name}.{self.name}"

    @property
    def migration_name_fragment(self) -> str:
        return f"revalidate_{self.model_name.lower()}_{self.name}"

    def deconstruct(self) -> tuple[str, list[Any], dict[str, Any]]:
        kwargs: dict[str, Any] = {"model_name": self.model_name, "name": self.name, "schema_hash": self.schema_hash}
        for field in (
            "previous_schema_hash",
            "forwards_defaults",
            "backwards_defaults",
            "forwards_transform",
            "backwards_transform",
        ):
            if value := getattr(self, field, None):
                kwargs[field] = value
        return self.__class__.__name__, [], kwargs

    def state_forwards(self, app_label: str, state: ProjectState) -> None:
        # the way to distinguish between states of Pydantic model is by _schema_hash
        model_state = state.models[app_label, self.model_name]
        field = model_state.fields[self.name]
        field._schema_hash = self.schema_hash
        state.reload_model(app_label, self.model_name)

    def state_backwards(self, app_label: str, state: ProjectState) -> None:
        model_state = state.models[app_label, self.model_name]
        field = model_state.fields[self.name]
        field._schema_hash = self.previous_schema_hash
        state.reload_model(app_label, self.model_name)

    def database_forwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,  # noqa: ARG002
        to_state: ProjectState,
    ) -> None:
        override_fields = cast("Literal['*']", "*") if self.previous_schema_hash is None else self.override_fields
        self.database_process(
            app_label,
            schema_editor,
            to_state,
            self.forwards_defaults,
            self.forwards_transform,
            override_fields,
        )

    def database_backwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,  # noqa: ARG002
        to_state: ProjectState,  # DB schema does not change with AlterPydantic, so we can use to_state both times
    ) -> None:
        self.database_process(app_label, schema_editor, to_state, self.backwards_defaults, self.backwards_transform)

    def database_process(  # noqa: PLR0913
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        state: ProjectState,
        defaults: dict[str, Any],
        transform: Callable[[Any], Any] | None,
        override_fields: list[str] | Literal["*"] | None = None,
    ) -> None:
        model = state.apps.get_model(app_label, self.model_name)
        field = model._meta.get_field(self.name)
        # technically, nothing stops you from calling AlterPydantic on any field, duh
        if not isinstance(field, PydanticField):
            msg = f"{model.__name__}.{self.name} is not a PydanticField"
            raise TypeError(msg)
        connection = schema_editor.connection
        _process_database(model, field, connection, defaults, transform, override_fields)


@dataclass
class UpdateContext:
    model: type[pydantic.BaseModel]
    defaults: dict[str, Any]
    transform: Callable[[Any], Any] | None

    select_sql: str
    update_sql: str
    err_template: str

    f_columns: dict[str, str]
    f_fields: dict[str, str]
    p_fields: dict[str, str]
    r_fields: dict[str, str]

    batch_size: int

    to_override: set[str]
    complex_keys: set[str]
    default_values: dict[str, Any]


def _get_field_default(model: type[pydantic.BaseModel], field_name: str) -> Any:
    info: pydantic.fields.FieldInfo | None = model.model_fields.get(field_name)
    if not info or info.is_required():
        # NOT_PROVIDED would never equal stored data, so such fields are only
        # updated when missing from data or listed in override_fields
        return models.NOT_PROVIDED

    # default may be datetime, but data is always in serialized form
    return json.loads(json.dumps(info.get_default(call_default_factory=True), cls=JSONEncoder))


def _process_database(  # noqa: PLR0913
    model: type[models.Model],
    field: PydanticField,
    connection: ConnectionProxy,
    defaults: dict[str, Any],
    transform: Callable[[Any], Any] | None,
    override_fields: list[str] | Literal["*"] | None = None,
) -> None:
    pydantic_model: type[pydantic.BaseModel] = field.inner_model
    quote = connection.ops.quote_name
    table = quote(model._meta.db_table)
    column = quote(field.column)  # PydanticField db column
    pk_col = quote(model._meta.pk.column)

    f_columns = {}  # mapping: { models.F field name: column name }. These columns will be added to select query
    f_fields = {}  # mapping: { defaults field: models.F field name }
    p_fields = {}  # mapping: { defaults field: pydantic_model field name }
    r_fields = {}  # mapping: { defaults field: pydantic_model field name }

    # E.g., defaults = {"what": models.F("whatever"), "field": R("old_field"), "same_as_field": P("field")}
    # f_columns["whatever"] = "whatever_db_column"
    # f_fields["what"] = "whatever"
    # r_fields["field"] = "old_field"
    # p_fields["same_as_field"] = "field"

    for key, value in defaults.items():
        if isinstance(value, models.F):
            f_fields[key] = value.name
            if value.name not in f_columns:
                f_columns[value.name] = model._meta.get_field(value.name).column
        elif isinstance(value, P):
            p_fields[key] = value.field_name
        elif isinstance(value, R):
            r_fields[key] = value.old_name

    selected_columns = [pk_col, column, *(quote(col) for col in f_columns.values())]

    select_sql = f"SELECT {', '.join(selected_columns)} FROM {table}"
    update_sql = f"UPDATE {table} SET {column} = %s WHERE {pk_col} = %s"
    error_message = f"Failed to migrate {model.__name__}(pk={{pk}}).{field.name}:\n{{exception}}\n"

    to_override = set(override_fields or [])
    complex_keys = set().union(f_fields, p_fields, r_fields)

    model_default_values = {k: _get_field_default(pydantic_model, k) for k in defaults}

    context = UpdateContext(
        model=pydantic_model,
        defaults=defaults,
        transform=transform,
        select_sql=select_sql,
        update_sql=update_sql,
        err_template=error_message,
        f_columns=f_columns,
        f_fields=f_fields,
        p_fields=p_fields,
        r_fields=r_fields,
        batch_size=1000,
        to_override=to_override,
        complex_keys=complex_keys,
        default_values=model_default_values,
    )

    _bulk_update(connection, context)


def _bulk_update(conn: ConnectionProxy, context: UpdateContext) -> None:
    # chunked_cursor gives a server-side cursor on PostgreSQL instead of plain
    # "cursor" that stores data in client memory. Thus, select now streams in
    # batches, and updates are made with a separate cursor — it doesn't
    # interfere with chunked_cursor
    with conn.chunked_cursor() as cursor:
        cursor.execute(context.select_sql)

        while True:
            rows = cursor.fetchmany(size=context.batch_size)
            if not rows:
                break

            params: list[tuple[str, Any]] = []
            for pk, raw, *other in rows:  # pk, PydanticField value, values of f_columns
                if raw is None:
                    # NOTE: idk if this approach is correct. Should defaults and
                    #       transform work even on None? Maybe try to create an
                    #       instance via pydantic_model() and apply changes to it?
                    continue

                params.append(_revalidate_row(context, pk, raw, other))

            if params:
                with conn.cursor() as update_cursor:
                    update_cursor.executemany(context.update_sql, params)


def _update_instance(context: UpdateContext, data: dict[str, Any], other: Sequence[Any]) -> dict[str, Any]:
    """
    Merges multiple layers of defaults into a single deserialized
    PydanticField value, in order:
      - plain defaults (simple values) + models.F (db values)
      - R (renames, old key is popped)
      - P (value copying)

    Thus, P can reference values produced by F and R. A field may be written
    only if it is "untouched": missing from saved data, equal to its Pydantic
    default, or listed in override_fields. Values that differ from the Pydantic
    default are treated as user data and preserved.
    """

    def value_is_default(name: str) -> bool:
        return data.get(name) == context.default_values.get(name)

    def should_set(field: str) -> bool:
        return (
            "*" in context.to_override or field in context.to_override or field not in data or value_is_default(field)
        )

    def handle_rp(mapping: dict[str, str], pop: bool = False) -> None:
        for field, old_field in mapping.items():
            v = data.pop(old_field, models.NOT_PROVIDED) if pop else data.get(old_field, models.NOT_PROVIDED)
            if v is not models.NOT_PROVIDED and should_set(field):
                data[field] = v

    direct = {k: v for k, v in context.defaults.items() if k not in context.complex_keys and should_set(k)}
    f_gathered = dict(zip(context.f_columns.keys(), other, strict=False))
    f_values = {k: f_gathered.get(v) for k, v in context.f_fields.items() if should_set(k)}
    data |= f_values | direct

    handle_rp(context.r_fields, pop=True)
    handle_rp(context.p_fields, pop=False)
    return data


def _revalidate_row[PK](context: UpdateContext, pk: PK, raw: str | dict | list, other: Sequence[Any]) -> tuple[str, PK]:
    data = json.loads(raw) if isinstance(raw, str) else raw

    if isinstance(data, dict):
        data = _update_instance(context, data, other)

    if context.transform is not None:
        data = context.transform(data)

    try:
        instance = context.model.model_validate(data)
    except pydantic.ValidationError as e:
        msg = context.err_template.format(pk=pk, exception=e)
        raise RuntimeError(msg) from e

    return json.dumps(instance.model_dump(), cls=JSONEncoder), pk


class PydanticAwareAutodetector(MigrationAutodetector):
    def _detect_changes(
        self, convert_apps: list[str] | None = None, graph: MigrationGraph | None = None
    ) -> dict[str, list[Operation]]:
        changes = super()._detect_changes(convert_apps, graph)
        self.generate_pydantic_operations(changes)
        return changes

    def generate_pydantic_operations(self, changes: dict[str, list[migrations.Migration]]) -> None:
        # adding AlterPydantic after CreateModel
        for migrations_list in changes.values():
            for migration in migrations_list:
                migration.operations = self.inject_after_createmodel(migration.operations)

        # looking for changes in all PydanticFields
        schema_operations = self.detect_schema_change()
        for app_label, ops in schema_operations.items():
            if not ops:
                continue

            existing = changes.setdefault(app_label, [])
            # If there are existing migrations, append to it,
            # otherwise create a new one
            if existing:
                existing[-1].operations.extend(ops)
            else:
                existing.append(self._make_migration(app_label, ops))

    @staticmethod
    def inject_after_createmodel(operations: list[Operation]) -> list[Operation]:
        out = []
        for op in operations:
            out.append(op)

            if not isinstance(op, migrations.CreateModel):
                continue

            for field_name, field in op.fields:
                if not isinstance(field, PydanticField):
                    continue
                out.append(
                    AlterPydantic(model_name=op.name, name=field_name, schema_hash=field.current_schema),
                )
        return out

    def detect_schema_change(self) -> dict[str, list[AlterPydantic]]:
        result: dict[str, list] = {}
        # NOTE: I doubt there's any simpler way to do this without iterating
        #       over every single model in the state, since we need to extract
        #       fields from them
        for (app_label, model_name), model_state in self.to_state.models.items():
            for field_name, field in model_state.fields.items():
                if not isinstance(field, PydanticField):
                    continue

                new_hash = field.current_schema
                # field or model itself may not exist before
                old_model = self.from_state.models.get((app_label, model_name), None)
                if old_model is None:
                    # AlterPydantic is handled via inject_after_createmodel
                    continue

                old_hash = getattr(old_model.fields.get(field_name), "_schema_hash", None)

                if old_hash == new_hash:
                    continue

                forwards_defaults = (
                    self._ask_defaults(model=field.inner_model, model_name=model_name, field_name=field_name)
                    if old_hash is not None
                    else {}
                )

                result.setdefault(app_label, []).append(
                    AlterPydantic(
                        model_name=model_name,
                        name=field_name,
                        schema_hash=new_hash,
                        previous_schema_hash=old_hash,
                        forwards_defaults=forwards_defaults,
                    )
                )
        return result

    def _make_migration(self, app_label: str, operations: list[Operation]) -> migrations.Migration:
        # there's a migration creation in _build_migration_list, but it wasn't
        # extracted to a separate function, so let's just create a new one here
        # but in a simpler manner (without subclasses and all that stuff)
        migration = migrations.Migration("auto_pydantic", app_label)
        migration.operations = operations
        return migration

    def _ask_defaults(self, model: type[pydantic.BaseModel], model_name: str, field_name: str) -> dict[str, Any]:
        # if this is called not via makemigrations, it won't be interactive;
        # that's not what we want here
        if not isinstance(self.questioner, InteractiveMigrationQuestioner):
            return {}

        q: InteractiveMigrationQuestioner = self.questioner

        required = [name for name, info in model.model_fields.items() if info.is_required()]
        if not required:
            return {}

        prompts = (
            f"\nThe schema of {model_name}.{field_name} has changed.",
            "Since it can't be determined if present required fields have"
            " existed before the change or just have been added, you will be"
            " asked to fill default values for all of them.",
            "For each required field provide a default value to backfill existing rows.",
            '(Enter a python literal, e.g. "string", 42, []. Leaving blank value will skip the process, but the'
            " migration will fail if any existing row is missing the field value)",
        )
        for prompt in prompts:
            q.prompt_output.write(prompt)

        defaults = {}
        for name in required:
            field_info = model.model_fields[name]
            annotation = field_info.annotation
            while True:
                raw = ""

                try:
                    raw = input(f'  {model_name}.{field_name}["{name}"] ({annotation}) = ').strip()
                except KeyboardInterrupt:  # ctrl+c
                    q.prompt_output.write("  skipping...\n")
                    break
                except EOFError:  # ctrl+d
                    q.prompt_output.write("  exiting...\n")
                    sys.exit(1)

                if not raw:  # empty string
                    q.prompt_output.write("Skipping...\n")
                    break

                try:
                    defaults[name] = ast.literal_eval(raw)
                    break
                except (ValueError, SyntaxError) as e:
                    q.prompt_output.write(f"    Invalid python literal: {e}. Try again.")
        return defaults
