from django.core.management.commands import makemigrations as mm
from django.core.management.commands import migrate as mg

from .migrations import PydanticAwareAutodetector


class MakeMigrations(mm.Command):
    autodetector = PydanticAwareAutodetector


class Migrate(mg.Command):
    autodetector = PydanticAwareAutodetector
