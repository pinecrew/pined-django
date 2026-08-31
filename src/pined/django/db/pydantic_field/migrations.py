from __future__ import annotations

import ast
import contextlib
import json
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast, dataclass_transform, overload

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

    from _typeshed import DataclassInstance

    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.db.backends.base.schema import BaseDatabaseSchemaEditor
    from django.db.migrations.state import ProjectState

    class DataTransformer(Protocol):
        def __call__(
            self, data_before: Mapping[Any, Any] | Sequence[Any] | None
        ) -> Mapping[Any, Any] | Sequence[Any] | None: ...


@overload
def pydantic_expression[T: type](cls: T, *, path: str = "pined.django.db.migrations") -> type[DataclassInstance]: ...


@overload
def pydantic_expression[T: type](
    cls: None, *, path: str = "pined.django.db.migrations"
) -> Callable[[T], type[DataclassInstance]]: ...


@dataclass_transform()
def pydantic_expression[T: type](
    cls: T | None = None, *, path="pined.django.db.migrations"
) -> type[DataclassInstance] | Callable[[T], type[DataclassInstance]]:
    """
    Turns `cls` into a migration expression.

    Each is a frozen, slotted dataclass claiming `path` as its module, so
    the migrations django generates import it from the public path rather
    than from here. `AlterPydantic` says as much in its own class body;
    `F`/`P`/`R` cannot, since `@dataclass` then resolves their annotations
    against a module that is not in `sys.modules` yet.

    Args:
        cls: Class to convert. Left out when `path` is passed instead.
        path: Module the expression reports as its own.
    """

    def deco(cls: T) -> type[DataclassInstance]:
        c = dataclass(cls, frozen=True, slots=True, eq=False)
        c.__module__ = path
        return c

    if cls is not None:
        return deco(cls)

    return deco


@pydantic_expression
class F:
    """
    Pull a default value from another field on the same Django model.

    Used inside `AlterPydantic`'s `forwards_defaults`/`backwards_defaults`
    to copy an already-stored column's value into the Pydantic field
    being migrated, instead of hardcoding a default. `field_name` may be
    a dotted path to reach into a nested `PydanticField`/`JSONField`,
    e.g. `"extra_info.software.update_attempts"`. `default_value` is
    used when the source field/path holds no value.
    """

    field_name: str
    default_value: Any = None


@pydantic_expression
class P:
    """
    Copy a value from another field of the same Pydantic model, once
    it's set.

    Used inside `AlterPydantic`'s `forwards_defaults`/`backwards_defaults`.
    Resolved after `F` and `R`, so it can pick up values produced by
    either.
    """

    field_name: str


@pydantic_expression
class R:
    """
    Rename a field of the Pydantic model, keeping its stored value.

    Used inside `AlterPydantic`'s `forwards_defaults`/`backwards_defaults`
    to move `old_name`'s value onto the key it's assigned to, without
    touching the value itself. Resolved before `P`.
    """

    old_name: str


class AlterPydantic(Operation):
    """
    A migration operation that revalidates a `PydanticField`'s stored
    data against a new schema.

    Generated automatically when a `PydanticField`'s Pydantic model
    changes shape, or written by hand for a data migration. Running it
    re-reads every row's JSON value, applies any
    defaults/renames/transform, and re-saves it validated against the
    model for `schema_hash`. See `__init__` for the available options
    and worked examples.
    """

    __module__ = "pined.django.db.migrations"

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
        Set up an operation that revalidates a `PydanticField`'s stored
        data against a new schema version.

        Args:
            model_name: Name of the Django model, e.g. "Options".
            name: Name of the `PydanticField` on that model, e.g.
                "email_settings".
            schema_hash: Hash of the schema being migrated to.
            previous_schema_hash: Hash of the schema being migrated from. Left
                unset when the field is being created for the first time.
            forwards_defaults: Values to backfill when migrating forwards to
                the new schema.
            backwards_defaults: Values to backfill when rolling back to the
                previous schema.
            forwards_transform: Arbitrary transform applied to the raw JSON
                value when migrating forwards, run after `forwards_defaults`
                has been applied.
            backwards_transform: Arbitrary transform applied to the raw JSON
                value when rolling back, run after `backwards_defaults` has
                been applied.
            override_fields: Names of fields whose stored value should be
                overwritten by the corresponding default, even if the row
                already holds user data for them.

        Examples:
            - A standard field migration, with nothing beyond a schema bump:
              ```
              AlterPydantic(
                  model_name="options",
                  name="email_settings",
                  schema_hash="010ec46d2fa44a77",
              ),
              ```

            - `forwards_defaults`/`backwards_defaults` can hold plain values,
              or one of three helper classes that pull a value from somewhere
              else instead: `F` copies from another field on the same Django
              model (pass a dotted path to reach into a nested `PydanticField`
              or `JSONField`), `P` copies from another field of the same
              Pydantic model, and `R` renames a Pydantic field while keeping
              its value. They resolve in the order `F`, then `R`, then `P` —
              so `P` can read a value that `F` or `R` just produced:
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
                      # dig out "update_attempts" from the JSONField named
                      # "extra", containing a dict with "software" as a key
                      # and a nested dict with "update_attempts" as a key
                      "update_attempts": F("extra.software.update_attempts"),
                  },
              )
              ```

            - When a field is being created for the first time, its
              `forwards_defaults` always take precedence over the Pydantic
              model's own defaults. Otherwise, a value in `forwards_defaults`/
              `backwards_defaults` is only written where the row's current
              value is missing or still equal to the Pydantic default — pass
              the field's name in `override_fields` to force it in every row
              instead, or pass `"*"` to force all of them. **This overwrites
              existing user data for those fields**:
              ```
              AlterPydantic(
                  model_name="options",
                  name="logging",
                  schema_hash="82ba0e105240e9da",
                  forwards_defaults={
                      "max_backup": 20,
                      "terminal_log_retention": 10,  # field's own default
                  },
                  # terminal_log_retention stays put in rows where it wasn't
                  # None, since that doesn't match the Pydantic default.
                  # max_backup becomes 20 everywhere, since it's listed in
                  # override_fields.
                  override_fields=["max_backup"],
              )
              ```

            - For anything `forwards_defaults`/`backwards_defaults` can't
              express — removing a field outright, computing a value from
              several others — pass a plain function as `forwards_transform`/
              `backwards_transform`. It runs last, after defaults have been
              applied, and receives/returns the field's raw JSON value:
              ```
              def replace_version_field(data: dict[str, Any]) -> dict[str, Any]:
                    # `data` is the PydanticField's underlying JSON value
                    data.pop("current_software_version", None)
                    data["software_version"] = random.randint(0, 20)
                    return data

              AlterPydantic(
                  model_name="terminal",
                  name="metadata",
                  schema_hash="3a14deee5c255329",
                  forwards_transform=replace_version_field,
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
            "override_fields",
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
    """
    Everything `_bulk_update` needs to revalidate one `PydanticField`
    across a table.

    Built once per `AlterPydantic` run by `_process_database` and
    threaded through the row-by-row revalidation in
    `_bulk_update`/`_revalidate_row`.
    """

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
    """
    Return `field_name`'s default value on `model`, serialized like
    stored data.

    Returns `models.NOT_PROVIDED` for required fields, since that value
    can never match real stored data — such fields are only ever
    backfilled, via `override_fields` or when missing from a row
    entirely.
    """

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
    """
    Build an `UpdateContext` for `field` and revalidate every row of
    `model`'s table.

    Resolves `schema_hash` back to a Pydantic model via `SchemaManager`,
    sorts `defaults` into plain values vs. `F`/`P`/`R` lookups, and hands
    the result to `_bulk_update`. A no-op if there's no schema to
    migrate to (rolling back past field creation) or no column to
    update against.
    """

    if schema_hash is None or not getattr(field, "column", None):
        # Rolling back past a field's creation migration leaves schema_hash
        # None. A missing column is unlikelier — db_column set to None by hand.
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

            source_field = model._meta.get_field(field_name)
            if not getattr(source_field, "column", None):
                continue

            f_fields[key] = (value.field_name, value.default_value)
            f_columns[field_name] = cast("str", source_field.column)
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
    """
    Resolve an `F` lookup — `(dotted "field.path", default)` — against
    a row's `f_columns` values.

    `data` maps `F`-referenced field names to their raw column values,
    as gathered by `_update_instance`. If the top-level field turns out
    to be a `JSONField` whose driver returned a string instead of
    decoded JSON (SQLite does this), it's parsed before descending into
    `path`.
    """

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
    """
    Stream `context.select_sql`'s rows, revalidate each, and write
    results back in batches.

    Uses a chunked (server-side, on PostgreSQL) cursor for the select
    so large tables aren't pulled into memory at once, and a separate
    plain cursor for updates so it doesn't interfere with the
    streaming select.
    """

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
    Merge defaults, `F`/`R`/`P` lookups, and existing data into one
    deserialized `PydanticField` value.

    Applied in this order: plain defaults and `F` values (already
    fetched db columns) are merged first, then `R` renames (popping
    the old key), then `P` copies — so `P` can reference values
    produced by `F` or `R`. A field is only overwritten if it's
    "untouched": missing from the saved data, equal to its Pydantic
    default, or listed in `override_fields`. Values that differ from
    the default are treated as user data and left alone.
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
    """
    Merge defaults into one row's value, validate it against the new
    model, and return `(json, pk)` to write back.

    Raises `RuntimeError` (chaining the original
    `pydantic.ValidationError`) if the merged data doesn't validate,
    identifying the offending row by `pk`.
    """

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
    """
    A `MigrationAutodetector` that also emits `AlterPydantic` operations
    for `PydanticField` schema changes.
    """

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
        """
        Add `AlterPydantic` operations for newly-created and
        schema-changed `PydanticField`s.
        """

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
        """
        Build an `AlterPydantic` for `model`, recording its schema
        under `schema_hash` unless this is a dry run.
        """

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
        """
        Find every `PydanticField` whose schema hash changed and build
        an `AlterPydantic` for each.

        Fields on newly-created models are skipped here — those are
        handled by `generate_pydantic_operations` right after their
        `CreateModel`. Has to walk every model in `to_state`, since
        fields aren't indexed by type anywhere the autodetector already
        iterates.
        """

        result: dict[str, list] = {}

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
        """
        Interactively prompt for a default value for each of `model`'s
        required fields.

        Mirrors `makemigrations`'s own field-default prompts. Returns
        `{}` outside an interactive `makemigrations` run, since there
        would be no one to answer the prompts.
        """

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
