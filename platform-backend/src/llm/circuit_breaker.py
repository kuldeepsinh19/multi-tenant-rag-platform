"""A minimal circuit breaker so a hung/down primary provider degrades to the fallback
provider instead of hammering it on every request. See langgraph-agent-standards:
resilience around every external call."""

import time
from dataclasses import dataclass, field


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    cooldown_seconds: float = 30.0
    _failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)

    def is_open(self) -> bool:
        """True while the breaker is tripped and still cooling down. Once the cooldown
        elapses, returns False to allow one half-open trial call through."""
        if self._opened_at is None:
            return False
        return (time.monotonic() - self._opened_at) < self.cooldown_seconds

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold and self._opened_at is None:
            self._opened_at = time.monotonic()
