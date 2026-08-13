"""ASGI rate-limit middleware — enforced BEFORE the chat handler (and thus before any LLM
call) so abuse costs a Redis INCR, not a model call (fastapi-backend-standards).

Scope: only chat paths (`/chat`, `/widget/chat`). Every other route (health, auth, admin,
metrics) passes through untouched — the limiter must not throttle the dashboard or break
login. For an in-scope request we identify the tenant/principal in priority order:

  1. JWT in the `Authorization: Bearer` header  -> keyed by business_id (authenticated user)
  2. `X-Widget-Key` header -> WidgetKey lookup   -> keyed by widget public key
  3. neither -> fall back to the client IP        -> keyed by IP

then apply a fixed-window request limit (settings.rate_limit_requests_per_minute / 60s).

Fail closed: if the limiter backend errors we return 429, we do NOT fall through to allow.
But a Redis outage must not crash the app — we catch the outage, log it, and deny with a
clean 429 JSON matching the app error shape ({"error","message"}), never a 500 stack trace.
The per-business daily token budget is enforced here too when we have a business_id.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from src.businesses.models import WidgetKey
from src.core.config import get_settings
from src.core.db import async_session_factory
from src.core.exceptions import BudgetExceeded, RateLimitExceeded
from src.core.logging import get_logger
from src.ratelimit.service import (
    RateLimiterUnavailable,
    check_rate_limit,
    check_token_budget,
)

logger = get_logger(__name__)

# Only these path prefixes are rate limited. Everything else is permissive.
_CHAT_PATH_PREFIXES = ("/chat", "/widget/chat")
_WINDOW_SECONDS = 60


def _is_chat_path(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in _CHAT_PATH_PREFIXES)


def _business_id_from_jwt(request: Request) -> UUID | None:
    """Best-effort tenant extraction from a bearer token. A malformed/expired token yields
    None here (we simply fall through to the next identity source); the actual 401 is the
    handler's auth dependency's job, not the rate limiter's."""
    auth = request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    token = auth[len("bearer ") :].strip()
    # Imported lazily so a token-decode import cost isn't paid on every non-chat request.
    from src.auth.security import decode_access_token

    try:
        payload = decode_access_token(token)
    except ValueError:
        return None
    return payload.business_id


async def _business_id_from_widget_key(public_key: str) -> UUID | None:
    """Resolve a widget public key to its business. Returns None if unknown/inactive."""
    async with async_session_factory() as session:
        stmt = select(WidgetKey).where(
            WidgetKey.public_key == public_key,
            WidgetKey.is_active.is_(True),
        )
        result = await session.execute(stmt)
        widget = result.scalar_one_or_none()
    return widget.business_id if widget is not None else None


def _client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _mask_secret(value: str) -> str:
    """Mask a credential for logging: keep a short non-reversible prefix for correlation,
    drop the rest. The widget public key is the sole bearer credential for `/widget/chat`,
    so it must never be written to logs verbatim (logs have a wider audience than the app)."""
    prefix = value[:6]
    return f"{prefix}…({len(value)} chars)"


def _deny_response(exc: RateLimitExceeded | BudgetExceeded) -> JSONResponse:
    """Render a domain 429 into the app's canonical error shape without going through the
    exception handler (middleware runs outside the handler stack)."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": type(exc).__name__, "message": exc.client_message},
    )


class RateLimitMiddleware:
    """Pure-ASGI middleware holding one shared async Redis client for the app's lifetime.

    Kept as a class (rather than an `@app.middleware("http")` function) so the Redis
    connection pool is created once at construction and reused, instead of per request.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        settings = get_settings()
        self._redis_url = settings.redis_url
        self._limit = settings.rate_limit_requests_per_minute
        self._daily_budget = settings.per_business_daily_token_budget
        self._redis: redis.Redis | None = None
        self._redis_loop: object | None = None

    def _get_redis(self) -> redis.Redis:
        """Return an async Redis client bound to the currently-running event loop.

        redis-py's async connection pool binds to the loop it was first used on. In
        production the app has a single loop for its lifetime, so this creates the client
        once. Under pytest-asyncio each test gets its own loop, so we rebind when the loop
        changes — otherwise a client from a previous (now-closed) loop raises
        "Event loop is closed". Mirrors the per-test engine disposal in tests/conftest.py.
        """
        loop = asyncio.get_running_loop()
        if self._redis is None or self._redis_loop is not loop:
            # redis-py's async from_url is untyped, hence the narrowly-scoped ignore.
            self._redis = redis.from_url(  # type: ignore[no-untyped-call]
                self._redis_url, encoding="utf-8", decode_responses=True
            )
            self._redis_loop = loop
        return self._redis

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        if not _is_chat_path(request.url.path):
            await self.app(scope, receive, send)
            return

        try:
            await self._enforce(request)
        except (RateLimitExceeded, BudgetExceeded) as exc:
            await _deny_response(exc)(scope, receive, send)
            return

        await self.app(scope, receive, send)

    async def _enforce(self, request: Request) -> None:
        """Identify the principal, then enforce the request-rate limit and (when we know
        the business) the daily token budget. Raises RateLimitExceeded / BudgetExceeded to
        deny. Fails closed on any limiter backend error."""
        business_id = _business_id_from_jwt(request)
        widget_key = request.headers.get("x-widget-key")
        if business_id is None and widget_key:
            business_id = await _business_id_from_widget_key(widget_key)

        # `principal` keys the Redis counter (must be exact/unique). `log_principal` is the
        # log-safe rendering — the raw widget key is a credential and is masked before it
        # ever reaches a log line.
        if business_id is not None:
            principal = f"business:{business_id}"
            log_principal = principal
        elif widget_key:
            principal = f"widget:{widget_key}"
            log_principal = f"widget:{_mask_secret(widget_key)}"
        else:
            principal = f"ip:{_client_ip(request)}"
            log_principal = principal

        rate_key = f"ratelimit:{principal}"
        try:
            allowed = await check_rate_limit(
                self._get_redis(), rate_key, self._limit, _WINDOW_SECONDS
            )
        except RateLimiterUnavailable as exc:
            # Fail closed on an outage, but with a 429 (not a crash). Deny, log, move on.
            logger.warning("rate_limit_backend_unavailable", principal=log_principal)
            raise RateLimitExceeded(
                "Rate limiting is temporarily unavailable; please retry shortly."
            ) from exc

        if not allowed:
            logger.info("rate_limit_exceeded", principal=log_principal)
            raise RateLimitExceeded()

        if business_id is not None:
            await self._enforce_budget(business_id)

    async def _enforce_budget(self, business_id: UUID) -> None:
        """Per-business daily token budget. Fails closed: a DB error denies with a 429
        rather than allowing an unbounded spend."""
        try:
            async with async_session_factory() as session:
                within_budget = await check_token_budget(
                    session, business_id, self._daily_budget
                )
        except Exception as exc:
            logger.error(
                "token_budget_check_failed",
                business_id=str(business_id),
                error_type=type(exc).__name__,
            )
            raise BudgetExceeded(
                "Usage budget could not be verified; please retry shortly."
            ) from exc

        if not within_budget:
            logger.info("token_budget_exceeded", business_id=str(business_id))
            raise BudgetExceeded()


__all__ = ["RateLimitMiddleware"]
