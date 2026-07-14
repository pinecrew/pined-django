from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core import checks
from django.utils import timezone

if TYPE_CHECKING:
    from pined.django.contrib.sidejob.tasks import Task, TaskResult


class BaseExecutionBackend(metaclass=ABCMeta):
    alias: str

    def __init__(self, alias: str, params: dict) -> None:
        self.alias = alias
        self.options = params.get("OPTIONS", {})

    def validate_task(self, task: Task) -> None:
        """
        Determine whether the provided Task can be executed by the backend.
        """
        if not is_module_level_function(task.func):
            raise InvalidTask("Task function must be defined at a module level.")

        if not self.supports_async_task and iscoroutinefunction(task.func):
            raise InvalidTask("Backend does not support async Tasks.")

        task_func_args = get_func_args(task.func)

        if task.takes_context and (not task_func_args or task_func_args[0] != "context"):
            raise InvalidTask("Task takes context but does not have a first argument of 'context'.")

        if not self.supports_defer and task.run_after is not None:
            raise InvalidTask("Backend does not support run_after.")

        if settings.USE_TZ and task.run_after is not None and not timezone.is_aware(task.run_after):
            raise InvalidTask("run_after must be an aware datetime.")

        if self.queues and task.queue_name not in self.queues:
            raise InvalidTask(f"Queue '{task.queue_name}' is not valid for backend.")

    @abstractmethod
    def enqueue[T, **P](
        self,
        task: Task[T, P],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> TaskResult[T, P]:
        """
        Queue up a task to be executed
        """

    async def aenqueue[T, **P](
        self,
        task: Task[T, P],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> TaskResult[T, P]:
        """
        Queue up a task function (or coroutine) to be executed
        """
        return await sync_to_async(self.enqueue, thread_sensitive=True)(task, *args, **kwargs)

    def get_result[T, **P](self, job_id: str) -> TaskResult[T, P]:
        """
        Retrieve a result by id if it exists, otherwise raise
        ResultDoesNotExist.
        """
        raise NotImplementedError("This backend does not support retrieving or refreshing results.")

    async def aget_result[T, **P](self, job_id: str) -> TaskResult[T, P]:
        """See get_result()."""
        return await sync_to_async(self.get_result, thread_sensitive=True)(job_id)

    def check(self, **kwargs: Any) -> Iterable[checks.CheckMessage]:
        return []
