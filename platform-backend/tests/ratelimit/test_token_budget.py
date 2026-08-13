"""Integration tests for the per-business daily token-budget check against the real
Postgres. Randomly-suffixed business ids so rows never collide with concurrent runs."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.businesses.models import Business
from src.ratelimit.service import check_token_budget
from src.usage.models import UsageEvent


async def _make_business(db_session: AsyncSession) -> Business:
    suffix = uuid4().hex[:8]
    business = Business(name=f"Budget Biz {suffix}", slug=f"budget-biz-{suffix}")
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return business


async def test_under_budget_is_allowed(db_session: AsyncSession) -> None:
    business = await _make_business(db_session)
    db_session.add(
        UsageEvent(
            business_id=business.id, event_type="chat_answer", tokens_used=100, latency_ms=10
        )
    )
    await db_session.commit()

    assert await check_token_budget(db_session, business.id, daily_budget=1000) is True


async def test_at_or_over_budget_is_denied(db_session: AsyncSession) -> None:
    business = await _make_business(db_session)
    db_session.add_all(
        [
            UsageEvent(
                business_id=business.id, event_type="chat_answer", tokens_used=600, latency_ms=5
            ),
            UsageEvent(
                business_id=business.id, event_type="chat_answer", tokens_used=500, latency_ms=5
            ),
        ]
    )
    await db_session.commit()

    # 1100 used vs a 1000 budget -> denied.
    assert await check_token_budget(db_session, business.id, daily_budget=1000) is False


async def test_zero_budget_denies(db_session: AsyncSession) -> None:
    business = await _make_business(db_session)
    # A non-positive budget means "no allowance", not "unlimited" — deny.
    assert await check_token_budget(db_session, business.id, daily_budget=0) is False
