"""
`examples/settings.py` — the README's own smoke check.

Run in a subprocess: the module calls `configure`, installs a logger
class and patches the admin site at import time, none of which belongs in
the process running the rest of the suite.
"""

import os
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).parents[2]


def run(*args: str, **env: str) -> subprocess.CompletedProcess[str]:
    """
    Run a django command against `examples.settings`.
    """

    return subprocess.run(
        [sys.executable, "-m", "django", *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "examples.settings",
            "PYTHONPATH": str(REPO_ROOT),
            **env,
        },
    )


def test_the_example_settings_check_out(tmp_path: pathlib.Path) -> None:
    """
    `django check` has nothing to say about the assembled settings.

    `EXAMPLE_LOGS_ROOT` is redirected because `mixins.Logging` creates the
    directory as it serializes — which is also why the redirection has to
    work, and is asserted here rather than left to a test of its own.
    """

    logs = tmp_path / "logs"
    result = run("check", EXAMPLE_LOGS_ROOT=str(logs))

    assert result.returncode == 0, result.stderr
    assert "System check identified no issues" in result.stdout
    assert logs.is_dir()


def test_the_environment_reaches_the_example(tmp_path: pathlib.Path) -> None:
    """
    The `EXAMPLE_` prefix is what the module documents, so it should work.
    """

    result = run(
        "diffsettings",
        "--output",
        "unified",
        EXAMPLE_LOGS_ROOT=str(tmp_path / "logs"),
        EXAMPLE_SECRET_KEY="from-the-environment",
        EXAMPLE_DATABASES__DEFAULT__URL=f"sqlite:///{tmp_path / 'other.sqlite3'}",
    )

    assert result.returncode == 0, result.stderr
    assert "from-the-environment" in result.stdout
    assert "other.sqlite3" in result.stdout
