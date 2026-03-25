from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar


T = TypeVar("T")


@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay_seconds: float = 0.25
    backoff_multiplier: float = 2.0

    def normalized(self) -> "RetryConfig":
        return RetryConfig(
            max_attempts=max(1, int(self.max_attempts)),
            base_delay_seconds=max(0.0, float(self.base_delay_seconds)),
            backoff_multiplier=max(1.0, float(self.backoff_multiplier)),
        )


class RetryPolicy:
    def __init__(self, config: RetryConfig | None = None) -> None:
        self.config = (config or RetryConfig()).normalized()

    def run(self, fn: Callable[[], T]) -> T:
        last_exc: Exception | None = None
        delay = self.config.base_delay_seconds
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return fn()
            except Exception as exc:
                last_exc = exc
                if attempt >= self.config.max_attempts:
                    break
                if delay > 0:
                    time.sleep(delay)
                delay *= self.config.backoff_multiplier
        assert last_exc is not None
        raise last_exc


def should_retry(attempt: int, max_attempts: int = 3) -> bool:
    return attempt < max_attempts
