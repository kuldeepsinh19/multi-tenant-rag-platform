"""Integration tests for the rate limiter against the real Redis started by docker-compose.
Every test uses a randomly-suffixed key so concurrent test runs (and other agents' work
against the same Redis) never collide."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
import redis.asyncio as redis

from src.core.config import get_settings
from src.ratelimit.service import RateLimiterUnavailable, check_rate_limit


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[redis.Redis, None]:
    client: redis.Redis = redis.from_url(  # type: ignore[no-untyped-call]
        get_settings().redis_url, encoding="utf-8", decode_responses=True
    )
    try:
        yield client
    finally:
        await client.aclose()


async def test_allows_up_to_limit_then_denies(redis_client: redis.Redis) -> None:
    key = f"test:ratelimit:{uuid4().hex}"
    limit = 5
    window = 60

    # The first `limit` requests are allowed.
    for i in range(limit):
        allowed = await check_rate_limit(redis_client, key, limit, window)
        assert allowed is True, f"request {i + 1} within limit should be allowed"

    # The next one is denied.
    denied = await check_rate_limit(redis_client, key, limit, window)
    assert denied is False

    await redis_client.delete(key)


async def test_window_resets(redis_client: redis.Redis) -> None:
    key = f"test:ratelimit:{uuid4().hex}"
    limit = 2
    window = 1  # 1-second window so the reset is observable without a long sleep

    assert await check_rate_limit(redis_client, key, limit, window) is True
    assert await check_rate_limit(redis_client, key, limit, window) is True
    assert await check_rate_limit(redis_client, key, limit, window) is False

    # Let the window's TTL lapse, then the counter is gone and requests are allowed again.
    import asyncio

    await asyncio.sleep(1.2)
    assert await check_rate_limit(redis_client, key, limit, window) is True

    await redis_client.delete(key)


async def test_separate_keys_are_independent(redis_client: redis.Redis) -> None:
    key_a = f"test:ratelimit:{uuid4().hex}"
    key_b = f"test:ratelimit:{uuid4().hex}"
    limit = 1

    assert await check_rate_limit(redis_client, key_a, limit, 60) is True
    assert await check_rate_limit(redis_client, key_a, limit, 60) is False
    # key_b is untouched by key_a's exhaustion.
    assert await check_rate_limit(redis_client, key_b, limit, 60) is True

    await redis_client.delete(key_a, key_b)


async def test_fails_closed_on_redis_error() -> None:
    """A limiter that can't reach Redis must raise (so the caller denies), never return
    True. Point the client at a dead port to force a connection error."""
    dead_client: redis.Redis = redis.from_url("redis://127.0.0.1:1/0")  # type: ignore[no-untyped-call]
    with pytest.raises(RateLimiterUnavailable):
        await check_rate_limit(dead_client, f"test:{uuid4().hex}", 5, 60)
    await dead_client.aclose()
