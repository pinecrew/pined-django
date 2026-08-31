"""
The same module, reading `PINEDTEST_`-prefixed variables.
"""

from pined.django.settings import components, configure, mixins


class General(mixins.General):
    """
    Defaults the environment is expected to win over.
    """

    secret_key: str = "from-the-module"
    debug: bool = False
    allowed_hosts: list[str] = ["localhost"]


class Database(mixins.Database):
    """
    A connection the environment can replace outright.
    """

    databases: components.Databases = components.Databases(
        default=components.Database(url="sqlite:///prefixed.sqlite3"),
    )


settings = configure(General, Database, env_prefix="PINEDTEST_", env_file=None)
