"""
`chain` — a sequence of commands, and the variables it expands for them.
"""

import argparse
import io

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError

from pined.django.management.commands.chain import LinkedStoreTrueAction, expand_environment_variables


def run(*arguments: str) -> str:
    """
    Run the chain and hand back what it wrote.
    """

    out = io.StringIO()
    call_command("chain", *arguments, stdout=out)
    return out.getvalue()


@pytest.mark.parametrize(
    ("argument", "expected"),
    [
        pytest.param("$SET", "value", id="bare"),
        pytest.param("${SET}", "value", id="braced"),
        pytest.param("--password=$SET", "--password=value", id="inside-a-longer-argument"),
        pytest.param("$SET$SET", "valuevalue", id="twice"),
        pytest.param("${UNSET:-fallback}", "fallback", id="a-fallback-for-an-unset-one"),
        pytest.param("${SET:-fallback}", "value", id="a-fallback-nobody-needs"),
        pytest.param("${UNSET:-}", "", id="an-empty-value-asked-for-outright"),
        pytest.param("${EMPTY:-fallback}", "", id="set-to-empty-is-set"),
        pytest.param("100$", "100$", id="a-dollar-that-names-nothing"),
    ],
)
def test_expansion(argument: str, expected: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    What a variable expands to, and what it takes to allow an empty one.
    """

    monkeypatch.setenv("SET", "value")
    monkeypatch.setenv("EMPTY", "")
    monkeypatch.delenv("UNSET", raising=False)

    assert expand_environment_variables(argument) == expected


def test_an_unset_variable_stops_the_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    An unset variable is an error, not an empty argument.

    `--password $ADMIN_PASSWORD` used to become `--password ''`, and
    `create_admin` has no way to tell that from a password that was meant:
    a typo in a compose file bought a superuser with an empty password and
    a deployment that reported success.
    """

    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    with pytest.raises(CommandError, match="ADMIN_PASSWORD is not set"):
        expand_environment_variables("$ADMIN_PASSWORD")


@pytest.mark.django_db
def test_the_chain_runs_management_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Each command runs in turn, with its variables filled in.
    """

    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    run("--manage", "create_admin --username root --email a@b.c --password $ADMIN_PASSWORD")

    assert User.objects.get(username="root").check_password("s3cret")


@pytest.mark.django_db
def test_a_typo_in_a_variable_name_takes_the_chain_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    No user is created, and the chain exits non-zero.
    """

    monkeypatch.delenv("ADMIN_PASSOWRD", raising=False)

    with pytest.raises(CommandError, match="ADMIN_PASSOWRD is not set"):
        run("--manage", "create_admin --username root --email a@b.c --password $ADMIN_PASSOWRD")

    assert not User.objects.filter(username="root").exists()


def test_allow_failure_belongs_to_the_command_before_it() -> None:
    """
    A failure is carried past only where the chain was told to.
    """

    assert "Error" in run("--shell", "exit 1", "--allow-failure")

    with pytest.raises(Exception, match="exit status 1"):
        run("--shell", "exit 1")


def test_allow_failure_takes_no_argument_of_its_own() -> None:
    """
    The flag stands alone, and the command after it is its own step.

    `LinkedStoreTrueAction` gets that from `argparse._StoreTrueAction` —
    private, and the bet this module takes on python rather than on django.
    A store-true that stopped being `nargs=0` would swallow the next
    argument instead, which is what this watches for. The python matrix in
    CI is what makes the bet come due somewhere visible.
    """

    assert issubclass(LinkedStoreTrueAction, argparse._StoreTrueAction)

    reported = run("--shell", "echo first", "--allow-failure", "--shell", "echo second")

    assert "> echo first" in reported
    assert "> echo second" in reported


def test_allow_failure_before_any_command_is_refused() -> None:
    """
    There is no preceding command for the flag to belong to.
    """

    with pytest.raises(CommandError, match="can't be used before --manage or --shell"):
        run("--allow-failure", "--shell", "true")
