"""Metrics endpoint tests: aggregate correctness and tenant isolation (a different
business's admin must get 403). Seeds UsageEvent rows directly via the session factory.
Randomly-suffixed identifiers so rows never collide with concurrent runs."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User, UserRole
from src.auth.security import hash_password
from src.businesses.models import Business
from src.usage.models import UsageEvent


async def _make_business(db_session: AsyncSession) -> Business:
    suffix = uuid4().hex[:8]
    business = Business(name=f"Metrics Biz {suffix}", slug=f"metrics-biz-{suffix}")
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return business


async def _make_admin(db_session: AsyncSession, business_id: UUID, password: str) -> User:
    email = f"metrics-admin-{uuid4().hex[:8]}@example.com"
    user = User(
        email=email,
        password_hash=hash_password(password),
        role=UserRole.business_admin,
        business_id=business_id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token: str = resp.json()["access_token"]
    return token


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_metrics_aggregate_for_own_business(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    business = await _make_business(db_session)
    db_session.add_all(
        [
            UsageEvent(
                business_id=business.id,
                event_type="chat_answer_grounded",
                tokens_used=100,
                cost_usd=Decimal("0.001000"),
                latency_ms=200,
            ),
            UsageEvent(
                business_id=business.id,
                event_type="chat_answer_grounded",
                tokens_used=300,
                cost_usd=Decimal("0.003000"),
                latency_ms=400,
            ),
            UsageEvent(
                business_id=business.id,
                event_type="chat_answer_ungrounded",
                tokens_used=50,
                cost_usd=Decimal("0.000500"),
                latency_ms=600,
            ),
        ]
    )
    await db_session.commit()

    password = "metrics-admin-pass"
    admin = await _make_admin(db_session, business.id, password)
    token = await _login(client, admin.email, password)

    resp = await client.get(f"/businesses/{business.id}/metrics", headers=_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["total_messages"] == 3
    assert body["total_tokens"] == 450
    assert abs(body["total_cost_usd"] - 0.0045) < 1e-9
    assert abs(body["avg_latency_ms"] - 400.0) < 1e-6
    # 2 grounded / (2 grounded + 1 ungrounded) = 0.666...
    assert abs(body["groundedness_pass_rate"] - (2 / 3)) < 1e-9


async def test_metrics_tenant_isolation_returns_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Business A's admin must NOT read Business B's metrics, even though both are
    legitimate authenticated business_admin accounts."""
    business_a = await _make_business(db_session)
    business_b = await _make_business(db_session)

    password = "cross-tenant-pass"
    admin_a = await _make_admin(db_session, business_a.id, password)
    token_a = await _login(client, admin_a.email, password)

    resp = await client.get(
        f"/businesses/{business_b.id}/metrics", headers=_headers(token_a)
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"] == "NotAuthorized"


async def test_metrics_empty_business_uses_placeholder(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A business with no usage events yet returns zeros and the documented groundedness
    placeholder (1.0), not a divide-by-zero error."""
    business = await _make_business(db_session)
    password = "empty-biz-pass"
    admin = await _make_admin(db_session, business.id, password)
    token = await _login(client, admin.email, password)

    resp = await client.get(f"/businesses/{business.id}/metrics", headers=_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_messages"] == 0
    assert body["total_tokens"] == 0
    assert body["total_cost_usd"] == 0.0
    assert body["avg_latency_ms"] == 0.0
    assert body["groundedness_pass_rate"] == 1.0
