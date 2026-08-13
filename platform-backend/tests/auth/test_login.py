"""Covers POST /auth/login and the fail-closed behavior of protected routes."""

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User, UserRole
from src.auth.security import hash_password


async def _create_super_admin(db_session: AsyncSession, password: str) -> User:
    email = f"test-superadmin-{uuid4().hex[:8]}@example.com"
    user = User(
        email=email,
        password_hash=hash_password(password),
        role=UserRole.super_admin,
        business_id=None,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_login_success(client: AsyncClient, db_session: AsyncSession) -> None:
    password = "correct-horse-battery-staple"
    user = await _create_super_admin(db_session, password)

    response = await client.post(
        "/auth/login", json={"email": user.email, "password": password}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "super_admin"
    assert body["business_id"] is None
    assert isinstance(body["access_token"], str) and body["access_token"]


async def test_login_wrong_password_returns_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _create_super_admin(db_session, "correct-horse-battery-staple")

    response = await client.post(
        "/auth/login", json={"email": user.email, "password": "wrong-password"}
    )

    assert response.status_code == 401


async def test_login_unknown_email_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": f"nobody-{uuid4().hex[:8]}@example.com", "password": "whatever123"},
    )

    assert response.status_code == 401


async def test_protected_route_missing_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/businesses")

    assert response.status_code == 401


async def test_protected_route_invalid_token_returns_401(client: AsyncClient) -> None:
    response = await client.get(
        "/businesses", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401
