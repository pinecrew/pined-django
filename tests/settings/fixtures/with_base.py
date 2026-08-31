"""
A part that is already a `DjangoSettings`, carrying its own config.

`configure` must not name `DjangoSettings` a second base here — doing so
would re-apply its `model_config` over the one this part set.
"""

from pined.django.settings import DjangoSettings, configure


class Base(DjangoSettings):
    """
    A project's own base, with a prefix of its own.
    """

    model_config = {"env_prefix": "FROMPART_", "env_file": None}

    secret_key: str = "from-the-module"


settings = configure(Base)
