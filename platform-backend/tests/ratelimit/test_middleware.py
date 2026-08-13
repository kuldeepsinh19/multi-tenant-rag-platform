"""Middleware-level tests. We do NOT depend on the real /chat route existing — instead we
mount a throwaway FastAPI app with RateLimitMiddleware and a tiny route at a chat path,
so the test exercises the middleware's tenant-identification + limit-check + 429-shaping
logic in isolation. A non-chat path on the same app is asserted to pass through untouched.

The request limit here comes from settings.rate_limit_requests_per_minute; we hammer past
it against the real Redis and assert a 429 with the app's canonical {"error","message"}
shape. These unauthenticated requests are keyed per client IP; the fixture clears leftover
per-IP counters up front so a re-run starts clean."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
import redis.asyncio as redis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.config import get_settings
from src.ratelimit.middleware import RateLimitMiddleware


async def _clear_ip_keys() -> None:
    """These unauthenticated requests are keyed by client IP. Clear any leftover
    per-IP counters so a re-run within the fixed window starts clean (the ASGI test
    client's IP is stable across runs)."""
    client: redis.Redis = redis.from_url(  # type: ignore[no-untyped-call]
        get_settings().redis_url, encoding="utf-8", decode_responses=True
    )
    try:
        keys = [k async for k in client.scan_iter(match="ratelimit:ip:*")]
        if keys:
            await client.delete(*keys)
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def limited_client() -> AsyncGenerator[AsyncClient, None]:
    await _clear_ip_keys()
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/chat/ping")
    async def chat_ping() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ping")
    async def health_ping() -> dict[str, str]:
        return {"status": "ok"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_non_chat_path_is_not_rate_limited(limited_client: AsyncClient) -> None:
    settings = get_settings()
    # Fire well past the limit at a non-chat path: every one must succeed.
    for _ in range(settings.rate_limit_requests_per_minute + 5):
        resp = await limited_client.get("/health/ping")
        assert resp.status_code == 200


async def test_chat_path_returns_429_past_limit(limited_client: AsyncClient) -> None:
    settings = get_settings()
    limit = settings.rate_limit_requests_per_minute

    saw_429 = False
    body: dict[str, str] = {}
    # Hammer beyond the limit. Because these are unauthenticated the principal is the client
    # IP; within a single fixed window we must cross from 200 into 429.
    for _ in range(limit + 10):
        resp = await limited_client.get("/chat/ping")
        if resp.status_code == 429:
            saw_429 = True
            body = resp.json()
            break

    assert saw_429, "expected a 429 once the per-window request limit was exceeded"
    # The 429 must match the app's canonical error shape.
    assert set(body.keys()) == {"error", "message"}
    assert body["error"] == "RateLimitExceeded"
    assert isinstance(body["message"], str) and body["message"]
