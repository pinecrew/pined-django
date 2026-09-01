"""
`create_admin` — the superuser a start-up sequence makes for itself.
"""

import io

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import OperationalError, connection


def run(**options: str) -> str:
    """
    Run the command, with the credentials spelled out, and hand back
    whatever it wrote.
    """

    out = io.StringIO()
    call_command("create_admin", stdout=out, **{"username": "root", "password": "s3cret", "email": "a@b.c"} | options)
    return out.getvalue()


@pytest.mark.django_db
def test_the_user_is_created() -> None:
    """
    The superuser lands, and the command says which one it is.
    """

    reported = run()
    user = User.objects.get(username="root")

    assert f"pk={user.pk}" in reported
    assert user.is_superuser


@pytest.mark.django_db
def test_running_it_twice_is_not_an_error() -> None:
    """
    A start-up sequence runs every time the container does.

    The second run reports the collision and stops there — raising would
    take a deployment down over a database that is already in the state
    it was asked for. The collision is rolled back to a savepoint, so the
    transaction around the sequence survives it.
    """

    run()

    assert "IntegrityError" in run()
    assert User.objects.filter(username="root").count() == 1
    assert User.objects.filter(username="other").count() == 0

    run(username="other")

    assert User.objects.filter(username="other").count() == 1


@pytest.mark.django_db
def test_a_database_that_cannot_hold_a_user_is_an_error() -> None:
    """
    An unmigrated database is not "the user is already there".

    It used to be reported the same way, and the command exited 0 — so a
    deployment carried on believing it had an admin.
    """

    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE auth_user")

    with pytest.raises(OperationalError):
        run()
