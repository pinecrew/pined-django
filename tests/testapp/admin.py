"""
Both models on the default admin site.

Registered here rather than in a fixture so they are on the site by the
time `tests.urls` builds its patterns — `_build_app_dict` reverses an
`app_list` url per app, and the admin only routes what it knows about.
"""

from django.contrib import admin

from .models import Device, Terminal

admin.site.register(Terminal)
admin.site.register(Device)
