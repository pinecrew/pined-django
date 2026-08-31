import os
import sys
import time
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser


def get_temp_dir() -> Path:
    """
    Temp directory every process on the host resolves the same way.

    `tempfile.gettempdir()` is not that: on macOS and Windows it points
    into a per-user directory, so the start-up sequence and the workers
    would stamp and read different files.
    """

    match sys.platform:
        case "win32":
            return Path(os.environ.get("TEMP", r"C:\Windows\Temp"))
        case "darwin":
            return Path("/var/tmp")
        case _:
            return Path("/tmp")


def get_file_name(path: Path | None = None) -> Path:
    """
    Path of the stamp file for the current project.

    The project name comes from `DJANGO_SETTINGS_MODULE`, which every
    entry point resolves the same way.

    Args:
        path: Path to the target file. Must include filename.
    """

    if path:
        return path

    # `settings.configure()` leaves the module unset; such a setup should pass `path`.
    project = (settings.SETTINGS_MODULE or "django").partition(".")[0]
    return get_temp_dir() / f"uptime.{project}"


class Command(BaseCommand):
    """
    Report how long the application has been up.

    Process uptime answers the wrong question: gunicorn and uvicorn
    recycle workers, so a worker is routinely younger than the app. The
    start-up sequence stamps the file with `-s`, later calls measure
    against its mtime.
    """

    help = "Report uptime"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("-s", "--start", action="store_true", help="Restamp the file, resetting uptime")
        parser.add_argument("--filename", action="store_true", help="Print the path of the stamp file and exit")
        parser.add_argument("--path", type=Path, help="Path to stamp file to use instead of the default location")

    def get_uptime(self, start: bool = False, verbosity: int = 1, path: Path | None = None) -> str:
        file = get_file_name(path)
        if not file.exists() or start:
            file.touch()
            if verbosity > 1:
                self.stdout.write(f"{'Recreated' if start else 'Created'} {file}\n")
        elif verbosity > 1:
            self.stdout.write(f"Checked {file}\n")

        # Epoch seconds, not local wall clock: subtracting naive datetimes
        # gains or drops an hour across a DST shift.
        return str(timedelta(seconds=time.time() - file.stat().st_mtime))

    def handle(self, *args, **options) -> None:
        path = options.get("path")

        filename_only = options.get("filename", False)
        if filename_only:
            self.stdout.write(f"{get_file_name(path)}\n")
            return

        start = options.get("start", False)
        verbosity = options.get("verbosity", 1)
        self.stdout.write(f"{self.get_uptime(start, verbosity, path)}\n")
