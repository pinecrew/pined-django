from typing import Any, Final


class ProviderSettings:
    backend: str
    options: dict[str, Any]


class BackendSettings:
    execution: ProviderSettings
    result: ProviderSettings


class Settings: ...


SIDEJOB_SETTINGS: Final = "SIDEJOB"
