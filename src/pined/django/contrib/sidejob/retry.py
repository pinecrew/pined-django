from collections.abc import Callable
from dataclasses import dataclass
@dataclass
class RetryPolicy:
    min_backoff: float
    max_backoff: float
    max_retries: int|None
    retry_when: Callable[[int, BaseException], bool] | None = None
