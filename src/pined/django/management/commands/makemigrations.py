"""
`makemigrations` that uses the `pydantic-field` autodetector.

The autodetector lives behind the optional `pydantic-field` extra, so
without `pydantic` installed the default `makemigrations` is used.

Note:
    Whether the extra was actually chosen is not detectable, so any
    `pydantic` in the environment toggles the autodetector on.
"""

try:
    from pined.django.db.pydantic_field.commands import MakeMigrations as Command
except ImportError:
    from django.core.management.commands.makemigrations import Command

__all__ = ["Command"]
