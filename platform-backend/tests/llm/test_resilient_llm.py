"""Verifies the circuit-breaker fallover behaviour described in langgraph-agent-standards:
a hung/failing primary provider degrades to the fallback instead of failing every request,
and once the breaker trips, the primary is skipped entirely rather than retried forever."""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from src.core.exceptions import ProviderUnavailable
from src.llm.base import ChatMessage
from src.llm.circuit_breaker import CircuitBreaker
from src.llm.registry import ResilientLLM

_MESSAGES = [ChatMessage(role="user", content="hello")]


class _WorkingProvider:
    def __init__(self, reply: str = "answer") -> None:
        self.reply = reply
        self.calls = 0

    async def chat(self, messages: list[ChatMessage], **kwargs: Any) -> str:
        self.calls += 1
        return self.reply

    async def stream(self, messages: list[ChatMessage], **kwargs: Any) -> AsyncIterator[str]:
        yield self.reply


class _FailingProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, messages: list[ChatMessage], **kwargs: Any) -> str:
        self.calls += 1
        raise TimeoutError("simulated provider timeout")

    async def stream(self, messages: list[ChatMessage], **kwargs: Any) -> AsyncIterator[str]:
        raise TimeoutError("simulated provider timeout")
        yield ""  # pragma: no cover - unreachable; needed so this is an async generator


async def test_falls_over_to_fallback_when_primary_fails() -> None:
    resilient = ResilientLLM(
        primary=_FailingProvider(), fallback=_WorkingProvider("fallback-answer")
    )
    result = await resilient.chat(_MESSAGES)
    assert result == "fallback-answer"


async def test_raises_provider_unavailable_when_both_fail() -> None:
    resilient = ResilientLLM(primary=_FailingProvider(), fallback=_FailingProvider())
    with pytest.raises(ProviderUnavailable):
        await resilient.chat(_MESSAGES)


async def test_circuit_breaker_skips_primary_once_open() -> None:
    primary = _FailingProvider()
    fallback = _WorkingProvider()
    resilient = ResilientLLM(primary, fallback)

    for _ in range(CircuitBreaker().failure_threshold):
        await resilient.chat(_MESSAGES)

    calls_before = primary.calls
    await resilient.chat(_MESSAGES)
    assert primary.calls == calls_before  # breaker open: primary skipped entirely


async def test_stream_falls_over_to_fallback_when_primary_fails() -> None:
    resilient = ResilientLLM(
        primary=_FailingProvider(), fallback=_WorkingProvider("fallback-answer")
    )
    chunks = [chunk async for chunk in resilient.stream(_MESSAGES)]
    assert chunks == ["fallback-answer"]
