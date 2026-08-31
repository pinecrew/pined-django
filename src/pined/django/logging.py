import logging
from inspect import currentframe
from typing import override


class Logger(logging.Logger):
    """
    Logger that reports the caller by its fully qualified name.

    The stock logger fills `funcName` with a bare function name, which
    says little on its own. This one writes `module.Class.method`, so a
    format string needs nothing else to locate the call.

    Install it before django configures logging, which `django.setup()`
    does ahead of populating the apps — the bottom of the settings module
    is the place:

    ```
    ProjectSettings()
    logging.setLoggerClass(Logger)
    ```
    """

    @override
    def findCaller(
        self,
        stack_info: bool = False,
        stacklevel: int = 1,
    ) -> tuple[str, int, str, str | None]:
        """
        Locates the caller, naming it in full.

        Args:
            stack_info: Whether to collect the formatted stack as well.
            stacklevel: How many frames above the caller to report.
        """

        # +1 for this override's own frame: `logging` counts only frames from
        # its own file as internal, so the walk would otherwise stop here and
        # report this method as the caller.
        filepath, line, funcname, sinfo = super().findCaller(stack_info, stacklevel + 1)

        frame = currentframe()
        while frame and (frame.f_code.co_filename != filepath or frame.f_code.co_name != funcname):
            frame = frame.f_back

        if frame:
            module = frame.f_globals.get("__name__")
            qualname = frame.f_code.co_qualname
            funcname = f"{module}.{qualname}" if module else qualname

        return filepath, line, funcname, sinfo
