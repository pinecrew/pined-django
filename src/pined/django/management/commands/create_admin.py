from __future__ import annotations

from traceback import format_exception_only
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandParser

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

    def get_model(self) -> type[AbstractBaseUser]:
        return get_user_model()

    def get_fields(self) -> Iterable[str]:
        model = self.get_model()
        return sorted({getattr(model, "USERNAME_FIELD", "username"), "password", *model.REQUIRED_FIELDS})

    def add_arguments(self, parser: CommandParser) -> None:
        defaults = {"email": "admin@localhost", "username": "admin", "password": "admin"}

        for field in self.get_fields():
            kwargs = {
                "type": str,
                # Throwaway credentials are a development convenience;
                # in production every value is spelled out.
                "required": not settings.DEBUG,
                "default": defaults.get(field, "admin") if settings.DEBUG else None,
            }
            # Short flags only for chosen fields, any other initial may clash with a sibling or argparse's -h.
            names = (f"-{field[0]}", f"--{field}") if field in {"email", "password", "username"} else (f"--{field}",)
            parser.add_argument(*names, **kwargs)

    def handle(self, *args, **options) -> None:
        params = {k: v for k, v in options.items() if k in self.get_fields()}

        try:
            user = self.get_model()._default_manager.create_superuser(**params)
            self.stdout.write(
                self.style.SUCCESS("Successfully created user [")
                + self.style.WARNING(f"pk={user.pk}")
                + self.style.SUCCESS("]")
            )
        except Exception as e:  # noqa: BLE001
            # Write the exception instead of throwing, in DEBUG it's nearly
            # always "user already exists". Without the DEBUG this command
            # should run as part of startup sequence with the credentials
            # exported to the environment.
            self.stdout.write(self.style.WARNING("".join(format_exception_only(e))))
