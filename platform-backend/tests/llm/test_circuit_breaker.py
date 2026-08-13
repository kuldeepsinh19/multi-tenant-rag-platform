import time

from src.llm.circuit_breaker import CircuitBreaker


def test_stays_closed_below_failure_threshold() -> None:
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=10)
    assert not breaker.is_open()
    breaker.record_failure()
    assert not breaker.is_open()


def test_opens_at_failure_threshold() -> None:
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=10)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.is_open()


def test_success_resets_failure_count() -> None:
    breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=10)
    breaker.record_failure()
    assert breaker.is_open()
    breaker.record_success()
    assert not breaker.is_open()


def test_half_opens_after_cooldown() -> None:
    breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)
    breaker.record_failure()
    assert breaker.is_open()
    time.sleep(0.02)
    assert not breaker.is_open()
