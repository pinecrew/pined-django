from __future__ import annotations
from typing import cast, TYPE_CHECKING, overload

from asgiref.sync import async_to_sync, sync_to_async
from inspect import iscoroutinefunction

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Callable

from .retry import RetryPolicy
from .periodic import Schedule

if TYPE_CHECKING:
    from .jobs import JobInfo, JobStatus

@dataclass
class TaskResult[T, **P]:
    task: Task[T, P]
    job_id: str

    @property
    def job(self) -> JobInfo[T, P]:
        return self.task.get_backend().fetch_job(self.job_id)


    @property
    def return_value(self) -> T:
        match self.job.status:
            case JobStatus.SUCCESSFUL:
                return cast(T, self.job.return_value)
            case JobStatus.FAILED:
                raise ValueError("Task failed")
            case _:
                raise ValueError("Task is not finished yet")

@dataclass(frozen=True)
class Task[T, **P]:
    func: Callable[P, T]
    priority: int
    backend: str
    result_backend: str|None
    queue_name: str
    run_after: datetime | None
    retry: RetryPolicy | None
    schedule: Schedule | None

    def enqueue(self, *args: P.args, **kwargs: P.kwargs) -> TaskResult[T, P]:
        return self.get_backend().enqueue(self, args, kwargs)

    async def aenqueue(self, *args: P.args, **kwargs: P.kwargs) -> TaskResult[T, P]:
        return await self.get_backend().aenqueue(self, args, kwargs)

    def call(self, *args: P.args, **kwargs: P.kwargs) -> T:
        if iscoroutinefunction(self.func):
            return async_to_sync(self.func)(*args, **kwargs)
        return self.func(*args, **kwargs)

    async def acall(self, *args: P.args, **kwargs: P.kwargs) -> T
        if iscoroutinefunction(self.func):
            return await self.func(*args, **kwargs)
        return await sync_to_async(self.func)(*args, **kwargs)

# Bare decorator usage
# e.g. @task
@overload
def task[T, **P](function: Callable[P, T]) -> Task[T, P]: ...


# Decorator with arguments
# e.g. @task() or @task(priority=1, ...)
@overload
def task[T, **P](
    *,
    priority: int = DEFAULT_TASK_PRIORITY,
    queue_name: str = DEFAULT_TASK_QUEUE_NAME,
    backend: str = DEFAULT_TASK_BACKEND_ALIAS,
    **kwargs,
) -> Callable[[Callable[P, T]], Task[T, P]]: ...




# Implementation
def task[T, **P](
    function: Callable[P, T] | None = None,
    *,
    priority: int = DEFAULT_TASK_PRIORITY,
    queue_name: str = DEFAULT_TASK_QUEUE_NAME,
    backend: str = DEFAULT_TASK_BACKEND_ALIAS,
    retry: RetryPolicy|None = None,
    schedule: Schedule|None = None,
) -> (
    Task[T, P]
    | Callable[[Callable[P, T]], Task[T, P]]
):
    """
    A decorator used to create a task.
    """
    from . import task_backends

    def wrapper(f: Callable[P, T]) -> Task[T, P]:
        return Task(
            func=f,
            priority=priority,
            backend=backend,
            result_backend=result_backend,
            queue_name=queue_name,
            run_after=None,
            retry=retry,
            schedule=schedule,
        )

    if function:
        return wrapper(function)

    return wrapper
