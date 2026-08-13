"""End-to-end request tracing via Langfuse — cost and latency as first-class metrics
(llm-evals-standards).

Two hard rules distinguish this from the rate limiter:

  * NO-OP without keys. If LANGFUSE_PUBLIC_KEY/SECRET_KEY are unset, tracing is a strict
    no-op — never an error, never a warning storm. Local dev and CI run with tracing off.
  * FAIL OPEN. Tracing is observability, not a guardrail. A Langfuse outage (network,
    auth, bad payload) must NEVER break the request — every Langfuse call here is wrapped
    and any failure is logged and swallowed. Contrast with the rate limiter, which fails
    closed. Cost/latency are computed locally and are always safe even with tracing off.

Redaction: `trace_request` accepts a metadata dict; callers must not pass raw prompts or
PII (project-conventions: log decisions, not secrets). We shallow-redact any key that looks
sensitive before it leaves the process, as a backstop.
"""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

# Substrings that, if present in a metadata key, cause its value to be redacted before it
# is sent to Langfuse. Backstop only — callers should never pass secrets in the first place.
_SENSITIVE_KEY_HINTS = ("password", "secret", "token", "authorization", "api_key", "apikey")


def _redact(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    redacted: dict[str, Any] = {}
    for key, value in metadata.items():
        if any(hint in key.lower() for hint in _SENSITIVE_KEY_HINTS):
            redacted[key] = "***redacted***"
        else:
            redacted[key] = value
    return redacted


@lru_cache(maxsize=1)
def get_langfuse() -> Any | None:
    """Return a cached Langfuse client, or None when tracing is disabled/unavailable.

    Disabled (returns None, no error) when the keys are unset. Also returns None — rather
    than raising — if the `langfuse` package isn't installed or the client fails to
    construct, so an import/config problem degrades to "no tracing", never to a broken app.
    """
    settings = get_settings()
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None
    try:
        from langfuse import Langfuse

        client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host or None,
        )
    except Exception as exc:  # pragma: no cover - depends on env/package
        logger.warning("langfuse_init_failed", error_type=type(exc).__name__)
        return None
    logger.info("langfuse_initialized", host=settings.langfuse_host or "default")
    return client


def tracing_enabled() -> bool:
    """True when a Langfuse client is configured and constructed. Cheap check for callers
    that want to skip building a metadata payload when tracing is off."""
    return get_langfuse() is not None


@contextmanager
def trace_request(
    name: str,
    correlation_id: str,
    metadata: Mapping[str, Any] | None = None,
) -> Iterator[None]:
    """Time a unit of work and record it to Langfuse as a trace when configured.

    Always measures wall-clock latency locally (safe with tracing off). When Langfuse is
    configured, opens a trace carrying `correlation_id` (so one user problem maps to one
    trace across the backend and the agent) plus redacted metadata, and records final
    latency. FAIL OPEN: any Langfuse error is logged and swallowed — the wrapped work runs
    and returns regardless. The wrapped block's own exceptions propagate unchanged after we
    record the failure.
    """
    client = get_langfuse()
    start = time.perf_counter()
    trace = None
    if client is not None:
        try:
            trace = client.trace(
                name=name,
                metadata={"correlation_id": correlation_id, **_redact(metadata)},
            )
        except Exception as exc:  # pragma: no cover - depends on Langfuse availability
            logger.warning("langfuse_trace_start_failed", error_type=type(exc).__name__)
            trace = None

    error: BaseException | None = None
    try:
        yield
    except BaseException as exc:  # record then re-raise; tracing never eats the error
        error = exc
        raise
    finally:
        latency_ms = int((time.perf_counter() - start) * 1000)
        if trace is not None:
            try:
                trace.update(
                    output={
                        "latency_ms": latency_ms,
                        "status": "error" if error is not None else "ok",
                    }
                )
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "langfuse_trace_update_failed", error_type=type(exc).__name__
                )


def record_llm_cost(
    correlation_id: str,
    *,
    model: str,
    tokens: int,
    cost_usd: float,
    latency_ms: int,
) -> None:
    """Record a single LLM generation's cost/latency to Langfuse when configured.

    Provided for the chat/agent layer to attach cost + latency spans to a request's trace.
    Computing the numbers is the caller's job (and is always possible without Langfuse);
    this only ships them. FAIL OPEN: swallows any Langfuse error.
    """
    client = get_langfuse()
    if client is None:
        return
    try:
        client.generation(
            name="llm_call",
            model=model,
            metadata={
                "correlation_id": correlation_id,
                "tokens": tokens,
                "cost_usd": cost_usd,
                "latency_ms": latency_ms,
            },
        )
    except Exception as exc:  # pragma: no cover - depends on Langfuse availability
        logger.warning("langfuse_cost_record_failed", error_type=type(exc).__name__)


__all__ = [
    "get_langfuse",
    "record_llm_cost",
    "trace_request",
    "tracing_enabled",
]
