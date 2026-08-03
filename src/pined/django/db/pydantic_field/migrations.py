from __future__ import annotations

import ast
import contextlib
import json
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pydantic

from django.db import migrations, models
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.operations.base import Operation, OperationCategory
from django.db.migrations.questioner import InteractiveMigrationQuestioner
from pined.django.serializers.json import JSONEncoder
from pined.django.utils.nested import get_nested

from .field import PydanticField
from .schema import SchemaManager

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, MutableMapping, Sequence
    from typing import Any, Literal, Protocol

    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.db.backends.base.schema import BaseDatabaseSchemaEditor
    from django.db.migrations.state import ProjectState

    class DataTransformer(Protocol):
        def __call__(
            self, data_before: Mapping[Any, Any] | Sequence[Any] | None
        ) -> Mapping[Any, Any] | Sequence[Any] | None: ...


@dataclass(frozen=True, slots=True, eq=False)
class F:
    """
    Get a value from another model field.
    """

    __module__ = "pined.django.db.models"

    field_name: str
    default_value: Any = None


@dataclass(frozen=True, slots=True, eq=False)
class P:
    """
    Get a value from another field of the Pydantic model.
    """

    __module__ = "pined.django.db.models"

    field_name: str


@dataclass(frozen=True, slots=True, eq=False)
class R:
    """
    Rename a field in the Pydantic model.
    """

    __module__ = "pined.django.db.models"

    old_name: str


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
        forwards_defaults: MutableMapping[str, Any] | None = None,
        backwards_defaults: MutableMapping[str, Any] | None = None,
        forwards_transform: DataTransformer | None = None,
        backwards_transform: DataTransformer | None = None,
        override_fields: list[str] | Literal["*"] | None = None,
    ) -> None:
        """
        Perform actions related to changing internal Pydantic model.

        Args:
            model_name: Name of the Django model, e.g., "Options"
            name: Field name, e.g., "email_settings"
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
                  model_name="options",
                  name="email_settings",
                  schema_hash="010ec46d2fa44a77",
              ),
              ```

            - In `forwards_defaults` and `backwards_defaults`, you can use
              specialized classes to access data from different sources.
              Instance of `F` allows to copy value from another field of the
              current Django model. Instance of `P` allows to copy data from
              another field of the Pydantic model. Instance of `R` allows to
              rename another Pydantic field without changing its value. If you
              want to get nested value from another PydanticField or JSONField,
              you can use `F`, but pass whole path (with dot "." as separator)
              to value as an argument. Notice, `P` is applied after the `R`, and
              the `R` is applied after the `F`.
              ```
              AlterPydantic(
                  model_name="terminal",
                  name="metadata",
                  schema_hash="3a14deee5c255329",
                  forwards_defaults={
                      # get value of "current_software_version" from parent
                      # model's field with the same name
                      "current_software_version": F("current_software_version"),
                      # rename "os_version" to "android_version"
                      "android_version": R("os_version"),
                      # notice, here P copies value from R
                      "also_version": P("android_version"),
                      # dig out the "update_attempts" from the JSONField named
                      # "extra_info", containing a dict with "software" as a key
                      # and nested dict with "update_attempts" as a key
                      "update_attempts": F("extra_info.software.update_attempts"),
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
              you can use new values in the transformer function. Also, don't
              forget that you can use `R` to rename a field:
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
            self.schema_hash,
            self.forwards_defaults,
            self.forwards_transform,
            override_fields,
        )

    def database_backwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,  # noqa: ARG002
    ) -> None:
        self.database_process(
            app_label,
            schema_editor,
            from_state,
            self.previous_schema_hash,
            self.backwards_defaults,
            self.backwards_transform,
        )

    def database_process(  # noqa: PLR0913
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        state: ProjectState,
        schema_hash: str | None,
        defaults: MutableMapping[str, Any],
        transform: DataTransformer | None,
        override_fields: list[str] | Literal["*"] | None = None,
    ) -> None:
        model = cast("type[models.Model]", state.apps.get_model(app_label, self.model_name))
        field = model._meta.get_field(self.name)
        # technically, nothing stops you from calling AlterPydantic on any field, duh
        if not isinstance(field, PydanticField):
            msg = f"{model.__name__}.{self.name} is not a PydanticField"
            raise TypeError(msg)
        connection = schema_editor.connection
        _process_database(model, field, schema_hash, connection, defaults, transform, override_fields)


@dataclass
class UpdateContext:
    parent: type[models.Model]
    model: type[pydantic.BaseModel]
    defaults: MutableMapping[str, Any]
    transform: Callable[[Any], Any] | None

    select_sql: str
    update_sql: str
    err_template: str

    f_columns: MutableMapping[str, str]
    f_fields: MutableMapping[str, tuple[str, Any]]
    p_fields: MutableMapping[str, str]
    r_fields: MutableMapping[str, str]

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
    schema_hash: str | None,
    connection: BaseDatabaseWrapper,
    defaults: MutableMapping[str, Any],
    transform: DataTransformer | None,
    override_fields: list[str] | Literal["*"] | None = None,
) -> None:
    if schema_hash is None or not getattr(field, "column", None):
        # The only way to achieve first part of the condition is to roll back
        # model or field creation migration. Second part is somewhat ridiculous,
        # but what if somebody did set db_column to None?
        return

    manager = SchemaManager(
        model._meta.app_label,
        model._meta.model_name or model.__name__.lower(),
        field.name,
    )
    pydantic_model: type[pydantic.BaseModel] = manager.get_model(schema_hash)

    quote = connection.ops.quote_name
    table = quote(model._meta.db_table)
    column = quote(cast("str", field.column))  # PydanticField db column
    pk_col = quote(model._meta.pk.column or "id")  # primary key db column

    f_columns: MutableMapping[str, str] = {}  # { F field name: db column }. These columns will be added to select query
    f_fields: MutableMapping[str, tuple[str, Any]] = {}  # { defaults field: (F field name, F default value) }
    p_fields: MutableMapping[str, str] = {}  # { defaults field: pydantic_model field name }
    r_fields: MutableMapping[str, str] = {}  # { defaults field: pydantic_model field name }

    # E.g., defaults = {"what": F("whatever"), "field": R("old_field"), "same_as_field": P("field")}
    # f_columns["whatever"] = "whatever_db_column"
    # f_fields["what"] = "whatever"
    # r_fields["field"] = "old_field"
    # p_fields["same_as_field"] = "field"

    for key, value in defaults.items():
        if isinstance(value, F):
            field_name = value.field_name.split(".")[0]
            if field_name in f_columns:
                # f_fields contains original getter to allow nested value gathering
                f_fields[key] = (value.field_name, value.default_value)
                continue

            field = model._meta.get_field(field_name)
            if not getattr(field, "column", None):
                continue

            f_fields[key] = (value.field_name, value.default_value)
            f_columns[field_name] = cast("str", field.column)
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
        parent=model,
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


def unnest(f: tuple[str, Any], data: Any, model: type[models.Model]) -> Any:
    getter, default = f
    field_name, *path = getter.split(".")
    field_value = get_nested(data, field_name)

    # I give my special thanks to SQLite for this
    with contextlib.suppress(Exception):
        field = model._meta.get_field(field_name)
        if isinstance(field, models.JSONField) and isinstance(field_value, str):
            field_value = json.loads(field_value)
    return get_nested(field_value, *path, default=default)


def _bulk_update(conn: BaseDatabaseWrapper, context: UpdateContext) -> None:
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


def _update_instance(
    context: UpdateContext, data: MutableMapping[str, Any], other: Sequence[Any]
) -> MutableMapping[str, Any]:
    """
    Merges multiple layers of defaults into a single deserialized
    PydanticField value, in order:
      - plain defaults (simple values) + F (db values)
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

    def handle_rp(mapping: MutableMapping[str, str], pop: bool = False) -> None:
        for field, old_field in mapping.items():
            v = data.pop(old_field, models.NOT_PROVIDED) if pop else data.get(old_field, models.NOT_PROVIDED)
            if v is not models.NOT_PROVIDED and should_set(field):
                data[field] = v

    direct = {k: v for k, v in context.defaults.items() if k not in context.complex_keys and should_set(k)}
    f_gathered = dict(zip(context.f_columns.keys(), other, strict=False))
    f_values = {k: unnest(v, f_gathered, context.parent) for k, v in context.f_fields.items() if should_set(k)}
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
    generated_operations: dict[str, list[Operation]]

    # Imagine: you want to add a new type of detectable changes that requires
    # migrations. You crack open MigrationAutodetector's code, and lo and
    # behold — you realize that it wouldn't be so simple. You see that there
    # are two distinct ways. The first one is: make all your superb detection
    # inside the `changes` method right after calling `super().changes(...)`.
    # But that returns already done-and-dusted list of all the needed migrations
    # — they're sorted, deduplicated, and have a bow on top. Tinkering with that
    # is not a walk in a park, plus there might be no migrations whatsoever if
    # the autodetector didn't find any changes represented by default
    # operations. Hence, you take road número dos: dive into the detector's
    # inner underscore-prefixed API, specifically, into the `_detect_changes`
    # method. But when you read the code, you realize — there's no magic method
    # like `generate_extra_operations` tucked between of default generations,
    # that could save the day by letting you override it. No — it's just a roll
    # call of all the standard operation generators, followed immediately by
    # operations sorting and migrations optimizers. Woe is us, cry me a river.
    # Oh, wait. There's *sorting* function that gets called *right after* all
    # the generators? What if — listen, what if we sneak our changes detection
    # into it, *before* calling super? So, ladies and gentlemen, feast your eyes
    # on our savior — `_sort_migrations`, let's give it a round of applause!
    # Because of this little gem of a method, we can work directly with
    # `generated_operations` dictionary, containing `Operation` lists instead
    # of `Migration` lists. Hurray!
    #
    # But, in all seriousness, I couldn't find a better way to append new
    # operations *before* migrations are created. `_sort_migrations` looks like
    # one of the "stablest" methods, so it's better to choose it rather than
    # overriding one of generators.

    def _sort_migrations(self) -> None:
        self.generate_pydantic_operations()

        super()._sort_migrations()

    def generate_pydantic_operations(self) -> None:
        # adding AlterPydantic after CreateModel
        for app_label, ops in self.generated_operations.items():
            extra = []

            for operation in ops:
                if isinstance(operation, migrations.CreateModel):
                    for field_name, field in operation.fields:
                        if not isinstance(field, PydanticField):
                            continue

                        extra.append(
                            self.create_alter_pydantic(
                                app_label,
                                field.inner_model,
                                model_name=operation.name,
                                name=field_name,
                                schema_hash=field.current_schema,
                            ),
                        )
            self.generated_operations[app_label].extend(extra)

        # looking for schema changes throughout all the PydanticField fields
        schema_operations = self.detect_schema_change()
        for app_label, ops in schema_operations.items():
            if not ops:
                continue

            self.generated_operations.setdefault(app_label, []).extend(ops)

    # @wraps(AlterPydantic.__init__)
    def create_alter_pydantic(  # noqa: PLR0913
        self,
        app_label: str,
        model: type[pydantic.BaseModel],
        /,
        model_name: str,
        name: str,
        schema_hash: str,
        previous_schema_hash: str | None = None,
        forwards_defaults: MutableMapping[str, Any] | None = None,
        backwards_defaults: MutableMapping[str, Any] | None = None,
        forwards_transform: DataTransformer | None = None,
        backwards_transform: DataTransformer | None = None,
        override_fields: list[str] | Literal["*"] | None = None,
    ) -> AlterPydantic:
        operation = AlterPydantic(
            model_name,
            name,
            schema_hash,
            previous_schema_hash=previous_schema_hash,
            forwards_defaults=forwards_defaults,
            backwards_defaults=backwards_defaults,
            forwards_transform=forwards_transform,
            backwards_transform=backwards_transform,
            override_fields=override_fields,
        )
        if not self.questioner.dry_run:
            manager = SchemaManager(app_label, model_name, name)
            manager.ensure_version(schema_hash, model)

        # in theory, we can add dependency on field creation
        operation._auto_deps = []
        return operation

    def detect_schema_change(self) -> dict[str, list[AlterPydantic]]:
        result: dict[str, list] = {}

        # I doubt, there's any simpler way to do this without iterating over
        # every single model in the current state, since we need to extract
        # all the fields from all the models.

        for (app_label, model_name), model_state in self.to_state.models.items():
            # check if app_label was set in makemigrations command
            if self.questioner.specified_apps and app_label not in self.questioner.specified_apps:
                continue

            for field_name, field in model_state.fields.items():
                if not isinstance(field, PydanticField):
                    continue

                new_hash = field.current_schema
                # field or model itself may not exist before
                old_model = self.from_state.models.get((app_label, model_name), None)
                if old_model is None:
                    # AlterPydantic is handled via inject_after_createmodel
                    continue

                old_hash = getattr(old_model.fields.get(field_name), "_schema_hash", None) if old_model else None

                if old_hash == new_hash:
                    continue

                forwards_defaults = (
                    self._ask_defaults(model=field.inner_model, model_name=model_name, field_name=field_name)
                    if old_hash is not None
                    else {}
                )

                result.setdefault(app_label, []).append(
                    self.create_alter_pydantic(
                        app_label,
                        field.inner_model,
                        model_name=model_name,
                        name=field_name,
                        schema_hash=new_hash,
                        previous_schema_hash=old_hash,
                        forwards_defaults=forwards_defaults,
                    )
                )
        return result

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
