from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser


class Command(BaseCommand):
    help = "Run sidejob worker"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("backend", nargs="?", type=str, default="default")

    def handle(self, *args, **options) -> None:
        ...
