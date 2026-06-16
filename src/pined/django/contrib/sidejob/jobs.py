from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
from dataclasses import dataclass
from enum import StrEnum, auto

if TYPE_CHECKING:
    from .tasks import Task

class JobStatus(StrEnum):
    READY = auto()
    RUNNING = auto()
    FAILED = auto()
    SUCCESSFUL = auto()

@dataclass
class Error:
    exception_class_path: str
    traceback: str

@dataclass
class JobInfo[T, **P]:
    task: Task[T, P]
    id: str
    status: JobStatus
    enqueued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    args: list[Any]
    kwargs: dict[str, Any]
    backend: str
    storage_backend: str
    errors: list[Error]
    worker_id: str | None
    return_value: T | None
