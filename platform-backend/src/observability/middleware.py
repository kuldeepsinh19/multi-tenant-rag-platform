"""Per-request tracing middleware. Records each request's latency + method/path/status to
Langfuse (when configured) under the request's correlation id, so a single user problem
maps to a single trace across the stack (fastapi-backend-standards: observability).

FAIL OPEN throughout — this is observability, not a guardrail. `trace_request` swallows any
Langfuse error, and this middleware adds no failure path of its own: if tracing is off it is
a thin timing wrapper. The correlation id is read from the header the existing
correlation-id middleware sets on the request.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

from src.observability.tracing import trace_request


async def tracing_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    correlation_id = request.headers.get("x-correlation-id", "-")
    metadata = {
        "method": request.method,
        "path": request.url.path,
    }
    with trace_request(name="http_request", correlation_id=correlation_id, metadata=metadata):
        return await call_next(request)


__all__ = ["tracing_middleware"]
