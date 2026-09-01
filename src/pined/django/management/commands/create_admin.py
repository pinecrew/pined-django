from __future__ import annotations

import argparse
from datetime import date
from traceback import format_exception_only
from typing import TYPE_CHECKING, Any, cast, override

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandParser
from django.db import IntegrityError, models, transaction
from django.utils import timezone

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.contrib.auth.base_user import AbstractBaseUser


class Command(BaseCommand):
    """
    Create a superuser from command-line arguments.

    Belongs to the start-up sequence, so running it twice is not an error.
    Anything other than "the user is already there" is.
    """

    help = "Create admin user"

    # Custom user models can define their own username and email fields, so the
    # default values are keyed by field type, not by field name.
    defaults: dict[type[models.Field[Any, Any]], Any] = {
        models.EmailField: "admin@localhost",
        models.CharField: "admin",
        models.IntegerField: 0,
        models.FloatField: 0.0,
        models.DateTimeField: timezone.now,
        models.DateField: date.today,
    }
    fallback = "admin"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.Model = self.get_model()

    def get_model(self) -> type[AbstractBaseUser]:
        return get_user_model()

    def get_fields(self) -> Iterable[str]:
        return sorted({getattr(self.Model, "USERNAME_FIELD", "username"), "password", *self.Model.REQUIRED_FIELDS})

    def get_default(self, name: str) -> Any:
        # A concrete field: the names come from `get_fields`, and none of
        # `USERNAME_FIELD`, `password` or `REQUIRED_FIELDS` is a relation.
        field = cast("models.Field[Any, Any]", self.Model._meta.get_field(name))
        if field.has_default():
            return field.get_default()

        default = next((value for kind, value in self.defaults.items() if isinstance(field, kind)), self.fallback)
        # `defaults` may hold factories, just as a field's own `default` may.
        return default() if callable(default) else default

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        for field in self.get_fields():
            kwargs = {
                "type": str,
                # Throwaway credentials are a development convenience;
                # in production every value is spelled out.
                "required": not settings.DEBUG,
                "default": self.get_default(field) if settings.DEBUG else None,
            }

            try:
                parser.add_argument(f"-{field[0]}", f"--{field}", **kwargs)
            except argparse.ArgumentError:
                # Initial already spoken for, by a sibling field or by Django's own -h/-v.
                parser.add_argument(f"--{field}", **kwargs)

    @override
    def handle(self, *args, **options) -> None:
        params = {k: v for k, v in options.items() if k in self.get_fields()}

        try:
            # A savepoint of its own: an `IntegrityError` caught without one
            # leaves the surrounding transaction unusable, and this command
            # is meant to be called from a sequence.
            with transaction.atomic():
                # pyrefly: ignore[missing-attribute]  # every user manager has it, `Manager` does not say so
                user = self.Model._default_manager.create_superuser(**params)
        except IntegrityError as e:
            # Almost always "user already exists", which is the whole point
            # of a start-up sequence being re-runnable. Everything else — an
            # unmigrated database, a manager that refuses the values — is a
            # failure of that sequence, and is left to be raised: reporting
            # it and exiting 0 tells a deployment it has an admin when it
            # has none.
            self.stdout.write(self.style.WARNING("".join(format_exception_only(e))))
            return

        self.stdout.write(
            self.style.SUCCESS("Successfully created user [")
            + self.style.WARNING(f"pk={user.pk}")
            + self.style.SUCCESS("]")
        )
