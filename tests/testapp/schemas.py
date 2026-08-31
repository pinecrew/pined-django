"""
The pydantic model behind `Terminal.metadata` and `Device.metadata`.

Only the current shape lives here — earlier ones survive as schemas in
`migrations/_schema_*.json`, which is exactly how a real project carries
its history. `schema_history.py` keeps them as classes too, but only so a
test can guard the hashes.
"""

import pydantic


class Metadata(pydantic.BaseModel):
    android_version: str = "unknown"
    current_software_version: str = ""
    update_attempts: int = 0
    max_backup: int = 10
    log_retention: int = 7
    region: str = "unset"
