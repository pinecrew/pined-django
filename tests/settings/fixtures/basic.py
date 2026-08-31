"""
A settings module in the shape the README documents.

Imported by the tests to watch `configure` fill a real module's globals —
which is the one thing it cannot be made to do from inside a function.
"""

from pined.django.settings import components, configure, mixins


class General(mixins.General):
    """
    The handful of things this "project" varies.
    """

    secret_key: str = "from-the-module"
    allowed_hosts: list[str] = ["localhost"]


class Database(mixins.Database):
    """
    One sqlite file.
    """

    databases: components.Databases = components.Databases(
        default=components.Database(url="sqlite:///basic.sqlite3"),
    )


# `env_file=None`, so a developer's own `.env` cannot reach the assertions.
settings = configure(General, Database, mixins.Session, env_file=None)
