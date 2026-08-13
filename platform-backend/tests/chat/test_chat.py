"""Integration tests for the chat endpoints (httpx AsyncClient + ASGITransport).

No live LLM/retriever: we monkeypatch the agent runner used by the chat service so a
deterministic grounded answer is streamed. Auth failure paths are exercised for real.
Randomly-suffixed identifiers avoid colliding with concurrent test runs."""

import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.graph import AgentResult
from src.auth.models import User, UserRole
from src.auth.security import hash_password
from src.businesses.models import Business, WidgetKey
from src.main import app


async def _make_business_and_admin(db: AsyncSession, password: str) -> tuple[Business, User]:
    business = Business(name=f"Chat Biz {uuid4().hex[:8]}", slug=f"chat-{uuid4().hex[:8]}")
    db.add(business)
    await db.commit()
    await db.refresh(business)
    admin = User(
        email=f"chat-admin-{uuid4().hex[:8]}@example.com",
        password_hash=hash_password(password),
        role=UserRole.business_admin,
        business_id=business.id,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return business, admin


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return str(resp.json()["access_token"])


def _fake_agent_runner(answer: str, citations: list[str]) -> Any:
    async def _runner(db: Any, business_id: UUID, query: str, **kwargs: Any) -> AgentResult:
        return AgentResult(answer=answer, citations=citations, escalated=False)

    return _runner


def _parse_sse(body: str) -> list[dict[str, Any]]:
    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


@pytest.mark.asyncio
async def test_dashboard_chat_requires_auth() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_chat_happy_path_streams_tokens_then_done(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    password = "pw-" + uuid4().hex[:8]
    _business, admin = await _make_business_and_admin(db_session, password)

    monkeypatch.setattr(
        "src.chat.service.run_agent",
        _fake_agent_runner("Refunds take 30 days.", []),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client, admin.email, password)
        resp = await client.post(
            "/chat",
            json={"message": "How long do refunds take?"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(resp.text)
    assert any("token" in e for e in events)
    assert events[-1].get("done") is True
    assert "citations" in events[-1]
    # Reassembling the token stream yields the verified answer.
    streamed = "".join(e["token"] for e in events if "token" in e)
    assert streamed == "Refunds take 30 days."


@pytest.mark.asyncio
async def test_widget_chat_rejects_missing_key() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/widget/chat", json={"message": "hi"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_widget_chat_rejects_invalid_key() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/widget/chat",
            json={"message": "hi"},
            headers={"X-Widget-Key": "nonexistent-" + uuid4().hex},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_widget_chat_rejects_disallowed_origin(db_session: AsyncSession) -> None:
    business = Business(name=f"W Biz {uuid4().hex[:8]}", slug=f"w-{uuid4().hex[:8]}")
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    public_key = "wk-" + uuid4().hex
    db_session.add(
        WidgetKey(
            business_id=business.id,
            public_key=public_key,
            allowed_domains=["allowed.example.com"],
            is_active=True,
        )
    )
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/widget/chat",
            json={"message": "hi"},
            headers={"X-Widget-Key": public_key, "Origin": "https://evil.example.com"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_widget_chat_happy_path(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    business = Business(name=f"W Biz {uuid4().hex[:8]}", slug=f"w-{uuid4().hex[:8]}")
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    public_key = "wk-" + uuid4().hex
    db_session.add(
        WidgetKey(
            business_id=business.id,
            public_key=public_key,
            allowed_domains=["shop.example.com"],
            is_active=True,
        )
    )
    await db_session.commit()

    monkeypatch.setattr(
        "src.chat.service.run_agent",
        _fake_agent_runner("Hello there.", []),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/widget/chat",
            json={"message": "hi"},
            headers={"X-Widget-Key": public_key, "Origin": "https://shop.example.com"},
        )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert events[-1].get("done") is True
    streamed = "".join(e["token"] for e in events if "token" in e)
    assert streamed == "Hello there."
