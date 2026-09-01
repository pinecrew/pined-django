"""
`configure` — assembling the parts, and filling the module it was called from.
"""

import pathlib
from typing import Any

import pydantic
import pytest

from pined.django.settings import DjangoSettings, build_settings, configure, mixins
from tests.settings.conftest import Loader

SQLITE = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": "basic.sqlite3",
    "USER": "",
    "PASSWORD": "",
    "HOST": "",
    "PORT": "",
    "CONN_MAX_AGE": 0,
    "CONN_HEALTH_CHECKS": False,
    "DISABLE_SERVER_SIDE_CURSORS": False,
}
POSTGRES = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "app",
    "USER": "u",
    "PASSWORD": "p",
    "HOST": "db",
    "PORT": 5432,
    "CONN_MAX_AGE": 600,
    "CONN_HEALTH_CHECKS": False,
    "DISABLE_SERVER_SIDE_CURSORS": False,
}


def filled(module: Any) -> dict[str, Any]:
    """
    Everything `configure` wrote into a module — django reads nothing else.
    """

    return {name: value for name, value in vars(module).items() if name.isupper()}


def test_the_module_gets_the_settings_and_nothing_else(load_settings: Loader) -> None:
    """
    The point of the whole thing: a settings module with no assignments.

    Comparing the module's constants as a set covers all of it at once —
    the components arrive in django's shape, a part taken as-is still
    brings what it declares, and the dozen fields nobody named stay away
    so django keeps its own defaults for them.
    """

    assert filled(load_settings("basic")) == {
        "SECRET_KEY": "from-the-module",
        "ALLOWED_HOSTS": ["localhost"],
        "DATABASES": {"default": SQLITE},
    }


def test_the_settings_come_back_as_well(load_settings: Loader) -> None:
    """
    `configure` returns the instance, which is what a test wants.
    """

    settings = load_settings("basic").settings

    assert isinstance(settings, DjangoSettings)
    assert settings.secret_key == "from-the-module"
    assert sorted(settings.model_dump(by_alias=True)) == [
        "ALLOWED_HOSTS",
        "DATABASES",
        "SECRET_KEY",
    ]


def test_there_has_to_be_a_module_to_fill() -> None:
    """
    Called anywhere but the top level of a module, it says so.

    `f_locals` is the module's own globals in a settings module, and a
    write-through proxy onto the caller's variables in a function — PEP 667
    made it one in 3.13, and before that it was a snapshot nobody read. So
    the same call did nothing on one python and rewrote a local named after
    a setting on the next. Neither is worth keeping: filling a module is
    all `configure` adds to `build_settings`, and where there is no module
    the call was a mistake.
    """

    class Named(mixins.General):
        secret_key: str = "from-the-part"

    SECRET_KEY = "mine"  # noqa: N806

    with pytest.raises(RuntimeError, match="build_settings"):
        configure(Named, env_file=None)

    assert SECRET_KEY == "mine"
    assert "SECRET_KEY" not in globals()


def test_build_settings_writes_nothing() -> None:
    """
    The same assembly, for a test or a script that only means to look.
    """

    class Named(mixins.General):
        secret_key: str = "from-the-part"

    SECRET_KEY = "mine"  # noqa: N806

    assert build_settings(Named, env_file=None).secret_key == "from-the-part"
    assert SECRET_KEY == "mine"
    assert "SECRET_KEY" not in globals()


def test_earlier_parts_win() -> None:
    """
    The parts are handed over in precedence order.
    """

    class First(mixins.General):
        secret_key: str = "first"

    class Second(mixins.General):
        secret_key: str = "second"

    assert build_settings(First, Second, env_file=None).secret_key == "first"
    assert build_settings(Second, First, env_file=None).secret_key == "second"


def test_a_part_that_is_already_settings_stays_the_base(load_settings: Loader) -> None:
    """
    Its own `model_config` is left in place rather than re-applied.
    """

    settings = load_settings("with_base").settings

    assert type(settings).__mro__[1].__name__ == "Base"
    assert settings.model_config["env_prefix"] == "FROMPART_"


def test_a_part_that_will_not_do() -> None:
    """
    A part that is not a class, and one that refuses its own values.

    There is no friendly error for the first — `issubclass` raises before
    the assembly gets a look in, and that is fine. The second is the part's
    own business: cross-field checks belong to whoever declared the fields.
    """

    with pytest.raises(TypeError):
        build_settings("not a class", env_file=None)

    class Reporting(mixins.General):
        sentry_dsn: str | None = None

        @pydantic.model_validator(mode="after")
        def _no_reporting_in_debug(self) -> "Reporting":
            if self.debug and self.sentry_dsn:
                msg = "sentry has no business hearing from a debug run"
                raise ValueError(msg)
            return self

    class Reported(Reporting):
        debug: bool = True
        sentry_dsn: str | None = "https://sentry.example.com/1"

    assert build_settings(Reporting, env_file=None).sentry_dsn is None

    with pytest.raises(pydantic.ValidationError, match="no business"):
        build_settings(Reported, env_file=None)


@pytest.mark.parametrize(
    ("env", "attribute", "expected"),
    [
        pytest.param(
            {"PINEDTEST_SECRET_KEY": "from-the-environment"},
            "SECRET_KEY",
            "from-the-environment",
            id="a-prefixed-variable-beats-the-default",
        ),
        pytest.param(
            {"SECRET_KEY": "somebody-else's"},
            "SECRET_KEY",
            "from-the-module",
            id="the-prefix-keeps-the-project-s-variables-its-own",
        ),
        pytest.param(
            {"PINEDTEST_NOT_A_SETTING": "1"},
            "SECRET_KEY",
            "from-the-module",
            id="a-stray-prefixed-variable-is-ignored",
        ),
        pytest.param(
            {"PINEDTEST_ALLOWED_HOSTS": '["app.example.com", "www.example.com"]'},
            "ALLOWED_HOSTS",
            ["app.example.com", "www.example.com"],
            id="anything-but-a-scalar-arrives-as-json",
        ),
        pytest.param({"PINEDTEST_DEBUG": "true"}, "DEBUG", True, id="a-bool-arrives-as-a-word"),
        pytest.param(
            {
                "PINEDTEST_DATABASES__DEFAULT__URL": "postgres://u:p@db:5432/app",
                "PINEDTEST_DATABASES__DEFAULT__CONN_MAX_AGE": "600",
            },
            "DATABASES",
            {"default": POSTGRES},
            id="a-nested-value-takes-the-delimiter",
        ),
    ],
)
def test_what_the_environment_is_allowed_to_do(
    load_settings: Loader,
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
    attribute: str,
    expected: Any,
) -> None:
    """
    The environment wins over every default, within its own prefix.
    """

    for name, value in env.items():
        monkeypatch.setenv(name, value)

    assert getattr(load_settings("prefixed"), attribute) == expected


def test_an_env_file_is_read_and_still_loses_to_the_environment(
    load_settings: Loader, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """
    A file works the same as the environment, and a deployment's own
    variable is the last word.
    """

    env_file = tmp_path / ".env"
    env_file.write_text("PINEDTEST_SECRET_KEY=from-the-file\n")
    monkeypatch.setenv("PINEDTEST_ENV_FILE", str(env_file))

    assert load_settings("from_file").SECRET_KEY == "from-the-file"

    monkeypatch.setenv("PINEDTEST_SECRET_KEY", "from-the-environment")

    assert load_settings("from_file").SECRET_KEY == "from-the-environment"
