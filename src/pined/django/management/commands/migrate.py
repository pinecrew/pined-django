"""
`migrate` that uses the `pydantic-field` autodetector.

The autodetector lives behind the optional `pydantic-field` extra, so
without `pydantic` installed the default `migrate` is used.

Note:
    Whether the extra was actually chosen is not detectable, so any
    `pydantic` in the environment toggles the autodetector on.
"""

try:
    from pined.django.db.pydantic_field.commands import Migrate as Command
except ImportError:
    from django.core.management.commands.migrate import Command

__all__ = ["Command"]
