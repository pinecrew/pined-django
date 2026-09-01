"""
`uptime` — the stamp file, and where it is allowed to live.
"""

import io
import os
import pathlib
import time

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from pined.django.management.commands import uptime
from pined.django.management.commands.uptime import DIRECTORY, get_file_name, get_runtime_dir


def run(*arguments: str) -> str:
    """
    Run the command and hand back what it wrote.
    """

    out = io.StringIO()
    call_command("uptime", *arguments, stdout=out)
    return out.getvalue()


def test_the_directory_is_the_one_systemd_handed_over(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    `RuntimeDirectory=` in a unit file is the answer where there is one.

    systemd makes it, owns it to the service's user, and removes it when
    the service stops — which is when the uptime should reset anyway.
    Several of them arrive colon-separated; the first one is ours.
    """

    monkeypatch.setenv("RUNTIME_DIRECTORY", "/run/myapp:/run/myapp-cache")

    assert get_runtime_dir() == pathlib.Path("/run/myapp") / DIRECTORY


def test_a_user_session_gets_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    `$XDG_RUNTIME_DIR` is per-user, 0700 and swept by nobody's timer.
    """

    monkeypatch.delenv("RUNTIME_DIRECTORY", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")

    assert get_runtime_dir() == pathlib.Path("/run/user/1000") / DIRECTORY


def test_the_last_resort_is_told_apart_by_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A container has neither, and `/tmp` is what is left.

    The uid in the name is what keeps two users on one host from meeting
    over the same file — `/tmp` lets anyone create any name in it.
    """

    monkeypatch.delenv("RUNTIME_DIRECTORY", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)

    assert get_runtime_dir() == pathlib.Path("/tmp") / f"{DIRECTORY}-{os.getuid()}"


def test_the_setting_wins_over_the_default(tmp_path: pathlib.Path) -> None:
    """
    `UPTIME_STAMP_PATH` is for a deployment whose start-up sequence and
    workers run as different users — no per-user directory serves both.
    """

    stamp = tmp_path / "run" / "uptime"

    with override_settings(UPTIME_STAMP_PATH=stamp):
        assert get_file_name() == stamp
        assert get_file_name(tmp_path / "explicit") == tmp_path / "explicit"


def test_the_default_directory_is_made_private(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    The directory arrives with the file, and only its owner gets in.

    Said outright rather than through `mkdir(mode=...)`, which applies only
    to a directory it made itself, and only to the last of them — so a
    directory left from a looser umask, or an intermediate one, would keep
    whatever it had.
    """

    runtime = tmp_path / "deep" / "run"
    monkeypatch.setattr(uptime, "get_runtime_dir", lambda: runtime)

    runtime.mkdir(parents=True)
    runtime.chmod(0o755)
    run("-s")

    assert (runtime / "uptime.tests").exists()
    assert runtime.stat().st_mode & 0o777 == 0o700


def test_the_default_directory_has_to_be_ours(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    The whole reason the file left `/tmp`.

    Where anyone may create a name, the stamp can be planted first — as a
    file with a forged mtime, or as a symlink that `Path.touch` follows and
    creates the target of. So the directory the command picks for itself
    has to be the command's own.
    """

    planted = tmp_path / "planted"
    planted.mkdir()
    monkeypatch.setattr(uptime, "get_runtime_dir", lambda: planted)
    monkeypatch.setattr(os, "getuid", lambda: os.lstat(planted).st_uid + 1)

    with pytest.raises(CommandError, match="belongs to another user"):
        run("-s")

    assert not (planted / "uptime.tests").exists()


def test_a_directory_a_deployment_named_is_left_alone(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    `UPTIME_STAMP_PATH` is a decision, not a guess to be second-guessed.

    Policing it would turn down `/tmp/uptime.myproject` — the obvious thing
    to reach for, `1777` and owned by root — which is to say the escape
    hatch would refuse the case it exists for.
    """

    shared = tmp_path / "shared"
    shared.mkdir()
    shared.chmod(0o1777)
    monkeypatch.setattr(os, "getuid", lambda: os.lstat(shared).st_uid + 1)

    with override_settings(UPTIME_STAMP_PATH=shared / "uptime"):
        run("-s")

    assert (shared / "uptime").exists()


def test_the_stamp_measures_from_its_mtime(tmp_path: pathlib.Path) -> None:
    """
    `-s` restamps, a bare call reads, and neither invents a number.
    """

    stamp = tmp_path / "uptime"

    with override_settings(UPTIME_STAMP_PATH=stamp):
        run("-s")
        os.utime(stamp, (time.time() - 3600, time.time() - 3600))

        assert run().startswith("1:00:00")

        run("-s")

        assert run().startswith("0:00:00")


def test_filename_only_prints(tmp_path: pathlib.Path) -> None:
    """
    Asking where the file is does not make it, nor its directory.
    """

    stamp = tmp_path / "never" / "made" / "uptime"

    with override_settings(UPTIME_STAMP_PATH=stamp):
        assert run("--filename").strip() == str(stamp)

    assert not stamp.parent.exists()
