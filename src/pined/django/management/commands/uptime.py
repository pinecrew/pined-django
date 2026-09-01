import os
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import override

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

DIRECTORY = "pined-django"
"""What the stamp file's directory is called wherever it ends up."""


def get_runtime_dir() -> Path:
    """
    Directory to keep the stamp file in, one per user of the machine.

    The requirement is a directory every process of the application
    resolves identically and nobody else can write to — the start-up
    sequence stamps the file and the workers read it back, and a
    world-writable location lets a local user forge the answer or plant
    a symlink for `touch` to follow.

    `tempfile.gettempdir()` is not it: on macOS `$TMPDIR` belongs to a
    bootstrap namespace, so a launchd daemon and a shell get different
    ones. Neither is a bare `/tmp`, which `systemd-tmpfiles` empties on
    a timer — ten days, by default — resetting the uptime of exactly
    the long-lived application the command exists for.

    Returns:
        `$RUNTIME_DIRECTORY` where systemd declared one, otherwise the
        per-user runtime or application directory of the platform, and
        `/tmp` as the last resort. Containers land on that last one,
        where nothing sweeps it and nobody else is logged in.
    """

    if runtime := os.environ.get("RUNTIME_DIRECTORY"):
        # systemd's `RuntimeDirectory=`, colon-separated where there are several.
        return Path(runtime.partition(":")[0]) / DIRECTORY

    match sys.platform:
        case "win32":
            return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / DIRECTORY
        case "darwin":
            # `Caches` is the other candidate, and the system is entitled
            # to empty it — which is the problem being solved here.
            return Path.home() / "Library" / "Application Support" / DIRECTORY
        case _:
            if xdg := os.environ.get("XDG_RUNTIME_DIR"):
                return Path(xdg) / DIRECTORY
            # `getuid` so that two users on one host do not meet in `/tmp`.
            return Path("/tmp") / f"{DIRECTORY}-{os.getuid()}"


def get_file_name(path: Path | None = None) -> Path:
    """
    Path of the stamp file for the current project.

    The project name comes from `DJANGO_SETTINGS_MODULE`, which every
    entry point resolves the same way. `UPTIME_STAMP_PATH` overrides the
    location outright, for a deployment whose start-up sequence and
    workers do not run as the same user — no per-user directory can
    serve both.

    Args:
        path: Path to the target file. Must include filename.
    """

    if path:
        return path

    if configured := getattr(settings, "UPTIME_STAMP_PATH", None):
        return Path(configured)

    # `settings.configure()` leaves the module unset; such a setup should pass `path`.
    project = (settings.SETTINGS_MODULE or "django").partition(".")[0]
    return get_runtime_dir() / f"uptime.{project}"


class Command(BaseCommand):
    """
    Report how long the application has been up.

    Process uptime answers the wrong question: gunicorn and uvicorn
    recycle workers, so a worker is routinely younger than the app. The
    start-up sequence stamps the file with `-s`, later calls measure
    against its mtime.
    """

    help = "Report uptime"

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("-s", "--start", action="store_true", help="Restamp the file, resetting uptime")
        parser.add_argument("--filename", action="store_true", help="Print the path of the stamp file and exit")
        parser.add_argument("--path", type=Path, help="Path to stamp file to use instead of the default location")

    def get_uptime(self, start: bool = False, verbosity: int = 1, path: Path | None = None) -> str:
        file = get_file_name(path)
        directory = file.parent
        directory.mkdir(parents=True, exist_ok=True)

        # The default is ours to make and ours to vouch for; a directory a
        # deployment named outright is its own business, and policing that
        # one would refuse `/tmp` — the obvious thing to reach for, and the
        # place the default just left.
        if directory == get_runtime_dir():
            # `lstat`, so a symlink planted where the directory should be is
            # judged by whoever planted it rather than by what it points at.
            # Somebody else's is somebody else's: whoever got there first can
            # leave a stamp with a forged mtime, or a symlink for `touch` to
            # follow and create the target of.
            if hasattr(os, "getuid") and os.lstat(directory).st_uid != os.getuid():
                msg = f"{directory} belongs to another user"
                raise CommandError(msg)

            # Not `mkdir(mode=...)`, which applies only to a directory it
            # created itself — and only to the last one. Said outright, so a
            # directory left over from a looser umask is narrowed too.
            directory.chmod(0o700)

        if not file.exists() or start:
            file.touch()
            if verbosity > 1:
                self.stdout.write(f"{'Recreated' if start else 'Created'} {file}\n")
        elif verbosity > 1:
            self.stdout.write(f"Checked {file}\n")

        # Epoch seconds, not local wall clock: subtracting naive datetimes
        # gains or drops an hour across a DST shift.
        return str(timedelta(seconds=time.time() - file.stat().st_mtime))

    @override
    def handle(self, *args, **options) -> None:
        path = options.get("path")

        filename_only = options.get("filename", False)
        if filename_only:
            self.stdout.write(f"{get_file_name(path)}\n")
            return

        start = options.get("start", False)
        verbosity = options.get("verbosity", 1)
        self.stdout.write(f"{self.get_uptime(start, verbosity, path)}\n")
