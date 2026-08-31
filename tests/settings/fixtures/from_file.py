"""
A settings module reading an `.env` the test points it at.
"""

import os

from pined.django.settings import configure, mixins


class General(mixins.General):
    """
    Defaults the file is expected to win over.
    """

    secret_key: str = "from-the-module"


settings = configure(General, env_prefix="PINEDTEST_", env_file=os.environ["PINEDTEST_ENV_FILE"])
