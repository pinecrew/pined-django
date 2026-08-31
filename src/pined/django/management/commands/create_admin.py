from __future__ import annotations

import argparse
from datetime import date
from traceback import format_exception_only
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandParser
from django.db import models
from django.utils import timezone

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.contrib.auth.base_user import AbstractBaseUser


class Command(BaseCommand):
    """
    Create a superuser from command-line arguments.

    Belongs to the start-up sequence, so it reports failures
    instead of raising them.
    """

    help = "Create admin user"

    # Custom user models can define their own username and email fields, so the
    # default values are keyed by field type, not by field name.
    defaults: dict[type[models.Field], Any] = {
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
        field = self.Model._meta.get_field(name)
        if field.has_default():
            return field.get_default()

        default = next((value for kind, value in self.defaults.items() if isinstance(field, kind)), self.fallback)
        # `defaults` may hold factories, just as a field's own `default` may.
        return default() if callable(default) else default

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

    def handle(self, *args, **options) -> None:
        params = {k: v for k, v in options.items() if k in self.get_fields()}

        try:
            user = self.Model._default_manager.create_superuser(**params)
            self.stdout.write(
                self.style.SUCCESS("Successfully created user [")
                + self.style.WARNING(f"pk={user.pk}")
                + self.style.SUCCESS("]")
            )
        except Exception as e:  # noqa: BLE001
            # Write the exception instead of raising it: in DEBUG it's nearly
            # always "user already exists". Outside DEBUG this command runs as
            # part of the start-up sequence, with the credentials exported to
            # the environment.
            self.stdout.write(self.style.WARNING("".join(format_exception_only(e))))
