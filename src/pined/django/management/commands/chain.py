import argparse
import os
import re
import shlex
import subprocess
from traceback import format_exception_only
from typing import Any, override

from django.core import management
from django.core.management.base import BaseCommand, CommandError


class AppendWithRelatedActions(argparse.Action):
    """
    An argparse action letting an argument carry sub-arguments of its own.

    It collects a namespace per occurrence, each holding the values of
    the arguments linked to it.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, default=[], **kwargs)
        self.related = []  # linked arguments

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        # Copy rather than append in place, the way `_AppendAction` does: the
        # initial list is the action's own default and outlives the namespace.
        dest = list(getattr(namespace, self.dest, []))
        dest.append(
            argparse.Namespace(
                type=(option_string or "").lstrip(parser.prefix_chars).replace("-", "_"),  # hardly general-purpose
                value=values,
                **{action.dest: action.default for action in self.related if action.default is not None},
            )
        )
        setattr(namespace, self.dest, dest)


class LinkedStoreTrueAction(argparse._StoreTrueAction):
    """
    Subclassing private classes is bad, but they had it coming.
    """

    def __init__(self, *args, linked_to: AppendWithRelatedActions, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.linked_to = linked_to
        linked_to.related.append(self)

    def get_namespace(self, namespace: argparse.Namespace) -> argparse.Namespace:
        """
        The namespace of the last flag this one was linked to.
        """

        namespaces = getattr(namespace, self.linked_to.dest)
        if not namespaces:
            raise argparse.ArgumentError(self, f"can't be used before {' or '.join(self.linked_to.option_strings)}")
        return namespaces[-1]

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        super().__call__(parser, self.get_namespace(namespace), values, option_string)


ENVIRONMENT_VARIABLE = re.compile(r"\$(?:(\w+)|\{(\w+)(?::-([^}]*))?\})")
"""`$NAME`, `${NAME}`, and `${NAME:-fallback}`."""


def expand_environment_variables(arg: str) -> str:
    """
    Substitutes `$NAME` or `${NAME}` with its environment variable.

    An unset variable is an error. Expanding it to an empty string turns
    `--password $ADMIN_PASSWORD` into `--password ''`, which the command
    behind it cannot tell from a password that was meant. Write
    `${NAME:-fallback}` to ask for a value when the variable is unset, and
    `${NAME:-}` when the empty string is the intended one.

    Args:
        arg: A single argument of a management command.

    Raises:
        CommandError: A variable is unset and names no fallback.
    """

    def substitute(match: re.Match[str]) -> str:
        bare, braced, fallback = match.groups()
        name = bare or braced
        value = os.getenv(name)
        if value is not None:
            return value
        if fallback is not None:
            return fallback

        msg = f"{name} is not set. Write ${{{name}:-}} to pass an empty value, or ${{{name}:-something}} for a default"
        raise CommandError(msg)

    return ENVIRONMENT_VARIABLE.sub(substitute, arg)


class Command(BaseCommand):
    """
    Runs a chain of commands, one after another.

    Every command has to sit in a single quoted string, or the parser
    tries to make sense of its arguments. `--allow-failure` belongs to
    the command right before it and lets the chain outlive its failure.

    Example:
        ```
        manage.py chain --shell 'ls -l' --manage 'collectstatic --noinput'
        ```
    """

    help = "Chain commands execution"

    @override
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        command = parser.add_argument(
            "--manage",
            "--shell",
            action=AppendWithRelatedActions,
            dest="commands",
            help="A management command or a shell one, quoted whole",
        )
        parser.add_argument(
            "--allow-failure",
            action=LinkedStoreTrueAction,
            linked_to=command,
            help="Carry on with the chain if the preceding command fails",
        )

    @override
    def handle(self, *args, **options) -> None:
        for command in options.get("commands", []):
            try:
                self.stdout.write(self.style.SUCCESS(f"> {command.value}"))
                # A child writes straight to the descriptor, so the banner goes first.
                self.stdout.flush()
                if command.type == "shell":
                    subprocess.run(command.value, shell=True, check=True)
                else:
                    # The shell did this for us above, here it is on us.
                    argv = shlex.split(command.value)
                    expanded = (expand_environment_variables(arg) for arg in argv)
                    management.call_command(*expanded)
            except Exception as e:
                if not command.allow_failure:
                    raise

                self.stdout.write(self.style.WARNING("".join(format_exception_only(e))))
