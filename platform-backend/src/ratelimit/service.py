"""Redis-backed rate limiting and per-business daily token-budget enforcement.

Two independent controls, both enforced BEFORE any LLM call (see fastapi-backend-standards
and llm-evals-standards: reject abuse for the cost of a Redis INCR, not a model call):

  * `check_rate_limit` — a fixed-window request counter keyed per principal/widget-key/IP.
  * `check_token_budget` — a per-business daily token cap, summed from `usage_events`.

Both FAIL CLOSED: if Redis (or the DB, for the budget) errors, we deny rather than fall
through to "allow". A limiter that crashes open is worse than no limiter — it gives the
false impression of protection while permitting exactly the abuse it exists to stop. The
caller (middleware) translates a False/denied result into a clean 429, and translates a
limiter *outage* into a 429/503 rather than a 500 so a Redis blip doesn't crash every
request.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.usage.models import UsageEvent

logger = get_logger(__name__)


class RateLimiterUnavailable(Exception):
    """Raised when the limiter backend (Redis) cannot be reached or errors. The caller
    MUST treat this as a denial (fail closed), never as an allow."""


async def check_rate_limit(
    redis_client: redis.Redis,
    key: str,
    limit: int,
    window_seconds: int,
) -> bool:
    """Fixed-window rate limit. Returns True if the request is allowed, False if the caller
    has exceeded `limit` requests within the current `window_seconds` window.

    Implementation: INCR a per-key counter and, on the first increment of a fresh window,
    set its TTL to `window_seconds`. The window is fixed (aligned to whenever the first
    request in it landed) — simple, cheap, and unit-testable against a real Redis. The
    counter key should already be namespaced by the caller (principal identity + route).

    Raises RateLimiterUnavailable on any Redis error so the caller can fail closed; this
    function never silently returns True on failure.
    """
    try:
        current = int(await redis_client.incr(key))
        if current == 1:
            # First hit in a new window — start the countdown. Only set on the first
            # increment so a burst doesn't keep pushing the expiry forward.
            await redis_client.expire(key, window_seconds)
        return current <= limit
    except redis.RedisError as exc:
        logger.error("rate_limit_redis_error", key=key, error_type=type(exc).__name__)
        raise RateLimiterUnavailable() from exc


async def check_token_budget(
    db: AsyncSession,
    business_id: UUID,
    daily_budget: int,
) -> bool:
    """Per-business daily token budget. Returns True if the business is still under its
    `daily_budget` for the current UTC day, False if it has met or exceeded it.

    Sums `usage_events.tokens_used` for this business since UTC midnight. This reads the
    same table the Stage 6 chat turn writes to, so the budget reflects real consumption.
    Fails closed: any DB error is surfaced (as an exception the caller denies on), never
    swallowed into an "allow".
    """
    if daily_budget <= 0:
        # A non-positive budget means "no allowance" — deny. Treat 0 as fully consumed
        # rather than as "unlimited", which would be an unsafe default.
        return False

    start_of_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.coalesce(func.sum(UsageEvent.tokens_used), 0)).where(
        UsageEvent.business_id == business_id,
        UsageEvent.created_at >= start_of_day,
    )
    result = await db.execute(stmt)
    used = int(result.scalar_one())
    return used < daily_budget


__all__ = ["RateLimiterUnavailable", "check_rate_limit", "check_token_budget"]
