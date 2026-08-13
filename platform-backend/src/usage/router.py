"""Metrics endpoint: `GET /businesses/{business_id}/metrics`.

READS the `usage_events` rows the Stage 6 chat turn WRITES (this module never writes them)
and returns the per-business production numbers (llm-evals-standards: cost + latency are
first-class SLOs). Tenant isolation is enforced exactly like every other business-scoped
route: super_admin, or that business's own admin via `ensure_same_business`; a different
business's admin gets a 403.

Event-type convention (shared contract with the writer):
  * every answered chat turn is one usage event whose event_type starts with "chat" —
    these count as messages and carry tokens/cost/latency.
  * groundedness is recorded on the answer event's type suffix: "chat_answer_grounded" vs
    "chat_answer_ungrounded". groundedness_pass_rate = grounded / (grounded + ungrounded).
    If no grounded/ungrounded events exist yet (writer not merged), we return the neutral
    placeholder 1.0 rather than divide by zero — a documented default, not real data.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import ensure_same_business, get_current_user
from src.auth.models import User, UserRole
from src.core.db import get_db
from src.core.exceptions import NotAuthorized
from src.core.logging import get_logger
from src.usage.models import UsageEvent
from src.usage.schemas import BusinessMetrics

router = APIRouter()
logger = get_logger(__name__)

_GROUNDED_EVENT = "chat_answer_grounded"
_UNGROUNDED_EVENT = "chat_answer_ungrounded"
# Placeholder returned when there is no groundedness data yet (writer not merged / no
# traffic). Documented as a default, not a measured value.
_GROUNDEDNESS_PLACEHOLDER = 1.0


async def _require_admin(user: User = Depends(get_current_user)) -> User:
    """Narrow 'authenticated' to 'some admin role'. Per-tenant scoping is enforced in the
    handler via ensure_same_business — this only rejects non-admins."""
    if user.role not in (UserRole.super_admin, UserRole.business_admin):
        raise NotAuthorized()
    return user


@router.get("/{business_id}/metrics", response_model=BusinessMetrics)
async def get_business_metrics(
    business_id: UUID,
    user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> BusinessMetrics:
    # Tenant boundary: a business_admin may only read their own business's metrics.
    ensure_same_business(business_id, user)

    # Message/token/cost/latency aggregate over all chat events for this business.
    stmt = select(
        func.count(UsageEvent.id),
        func.coalesce(func.sum(UsageEvent.tokens_used), 0),
        func.coalesce(func.sum(UsageEvent.cost_usd), 0),
        func.coalesce(func.avg(UsageEvent.latency_ms), 0),
        func.coalesce(
            func.sum(case((UsageEvent.event_type == _GROUNDED_EVENT, 1), else_=0)), 0
        ),
        func.coalesce(
            func.sum(case((UsageEvent.event_type == _UNGROUNDED_EVENT, 1), else_=0)), 0
        ),
    ).where(UsageEvent.business_id == business_id)

    row = (await db.execute(stmt)).one()
    total_messages, total_tokens, total_cost, avg_latency, grounded, ungrounded = row

    grounded_total = int(grounded) + int(ungrounded)
    groundedness_pass_rate = (
        int(grounded) / grounded_total
        if grounded_total > 0
        else _GROUNDEDNESS_PLACEHOLDER
    )

    return BusinessMetrics(
        total_messages=int(total_messages),
        total_tokens=int(total_tokens),
        total_cost_usd=float(total_cost),
        avg_latency_ms=float(avg_latency),
        groundedness_pass_rate=groundedness_pass_rate,
    )


__all__ = ["router"]
