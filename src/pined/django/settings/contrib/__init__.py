"""
Stubs for the settings of libraries that django projects often carry.

One module per library, imported only when a project wants it — the
field definitions are not free to build, and most projects want none of
them. Each module names its classes after its library: a model for the one
dict a library reads, and a mixin for the settings themselves.

Field names follow each library's own defaults, never a project's, and
the values stay unset so the library keeps deciding them.

Import the classes rather than the module: a field has to be named after
the setting it becomes, so `unfold: unfold.Unfold` would rebind the module
name before the annotation is read.

```
from pined.django.settings.contrib.rest_framework import (
    RestFramework,
    RestFrameworkSettings,
)
```
"""
