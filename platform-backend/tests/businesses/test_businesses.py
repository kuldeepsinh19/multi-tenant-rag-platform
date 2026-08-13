"""Covers business CRUD, role-gating, and the cross-tenant security boundary that
`ensure_same_business` is supposed to guarantee."""

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


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    token: str = response.json()["access_token"]
    return token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_super_admin_can_create_business(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    password = "super-secret-pass"
    admin = await _create_super_admin(db_session, password)
    token = await _login(client, admin.email, password)

    business_name = f"Test Business {uuid4().hex[:8]}"
    response = await client.post(
        "/businesses", json={"name": business_name}, headers=_auth_headers(token)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == business_name
    assert body["slug"]
    assert body["status"] == "active"


async def test_business_admin_cannot_create_business(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    super_password = "super-secret-pass"
    super_admin = await _create_super_admin(db_session, super_password)
    super_token = await _login(client, super_admin.email, super_password)

    business_resp = await client.post(
        "/businesses",
        json={"name": f"Test Business {uuid4().hex[:8]}"},
        headers=_auth_headers(super_token),
    )
    assert business_resp.status_code == 201
    business_id = business_resp.json()["id"]

    admin_email = f"test-admin-{uuid4().hex[:8]}@example.com"
    admin_password = "biz-admin-pass"
    invite_resp = await client.post(
        f"/businesses/{business_id}/admins",
        json={"email": admin_email, "password": admin_password},
        headers=_auth_headers(super_token),
    )
    assert invite_resp.status_code == 201

    biz_admin_token = await _login(client, admin_email, admin_password)

    response = await client.post(
        "/businesses",
        json={"name": f"Should Not Be Created {uuid4().hex[:8]}"},
        headers=_auth_headers(biz_admin_token),
    )

    assert response.status_code == 403


async def test_business_admin_cannot_read_another_businesses_details(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The cross-tenant test that matters most: Business A's admin must not be able
    to read Business B's details, even though both are legitimate, authenticated
    business_admin accounts."""
    super_password = "super-secret-pass"
    super_admin = await _create_super_admin(db_session, super_password)
    super_token = await _login(client, super_admin.email, super_password)
    super_headers = _auth_headers(super_token)

    business_a_resp = await client.post(
        "/businesses", json={"name": f"Business A {uuid4().hex[:8]}"}, headers=super_headers
    )
    business_b_resp = await client.post(
        "/businesses", json={"name": f"Business B {uuid4().hex[:8]}"}, headers=super_headers
    )
    assert business_a_resp.status_code == 201
    assert business_b_resp.status_code == 201
    business_a_id = business_a_resp.json()["id"]
    business_b_id = business_b_resp.json()["id"]

    admin_a_email = f"test-admin-a-{uuid4().hex[:8]}@example.com"
    admin_a_password = "biz-admin-a-pass"
    invite_a_resp = await client.post(
        f"/businesses/{business_a_id}/admins",
        json={"email": admin_a_email, "password": admin_a_password},
        headers=super_headers,
    )
    assert invite_a_resp.status_code == 201

    admin_b_email = f"test-admin-b-{uuid4().hex[:8]}@example.com"
    admin_b_password = "biz-admin-b-pass"
    invite_b_resp = await client.post(
        f"/businesses/{business_b_id}/admins",
        json={"email": admin_b_email, "password": admin_b_password},
        headers=super_headers,
    )
    assert invite_b_resp.status_code == 201

    admin_a_token = await _login(client, admin_a_email, admin_a_password)

    # Business A's admin CAN read their own business.
    own_response = await client.get(
        f"/businesses/{business_a_id}", headers=_auth_headers(admin_a_token)
    )
    assert own_response.status_code == 200

    # But Business A's admin must NOT be able to read Business B's details.
    cross_tenant_response = await client.get(
        f"/businesses/{business_b_id}", headers=_auth_headers(admin_a_token)
    )
    assert cross_tenant_response.status_code == 403


async def test_business_admin_can_create_own_widget_key(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    super_password = "super-secret-pass"
    super_admin = await _create_super_admin(db_session, super_password)
    super_token = await _login(client, super_admin.email, super_password)
    super_headers = _auth_headers(super_token)

    business_resp = await client.post(
        "/businesses", json={"name": f"Widget Biz {uuid4().hex[:8]}"}, headers=super_headers
    )
    assert business_resp.status_code == 201
    business_id = business_resp.json()["id"]

    admin_email = f"test-widget-admin-{uuid4().hex[:8]}@example.com"
    admin_password = "widget-admin-pass"
    invite_resp = await client.post(
        f"/businesses/{business_id}/admins",
        json={"email": admin_email, "password": admin_password},
        headers=super_headers,
    )
    assert invite_resp.status_code == 201

    admin_token = await _login(client, admin_email, admin_password)

    response = await client.post(
        f"/businesses/{business_id}/widget-keys",
        json={"allowed_domains": ["https://example.com"]},
        headers=_auth_headers(admin_token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["allowed_domains"] == ["https://example.com"]
    assert body["is_active"] is True
    assert body["public_key"]


# --- Tenant suspension -----------------------------------------------------------------
# `ensure_business_active` has always guarded chat and uploads, but until PATCH existed
# there was no way to actually suspend a tenant — the guard was unreachable. These cover
# the control itself and, critically, that a business_admin cannot lift their own
# suspension (which would make the spending guard self-serve).


async def _make_business_with_admin(
    client: AsyncClient, super_token: str
) -> tuple[str, str, str]:
    """Returns (business_id, admin_email, admin_password)."""
    business_resp = await client.post(
        "/businesses",
        json={"name": f"Suspend Biz {uuid4().hex[:8]}"},
        headers=_auth_headers(super_token),
    )
    assert business_resp.status_code == 201
    business_id: str = business_resp.json()["id"]

    admin_email = f"suspend-admin-{uuid4().hex[:8]}@example.com"
    admin_password = "biz-admin-pass"
    invite = await client.post(
        f"/businesses/{business_id}/admins",
        json={"email": admin_email, "password": admin_password},
        headers=_auth_headers(super_token),
    )
    assert invite.status_code == 201
    return business_id, admin_email, admin_password


async def test_super_admin_can_suspend_and_reactivate_a_business(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    password = "super-secret-pass"
    admin = await _create_super_admin(db_session, password)
    token = await _login(client, admin.email, password)
    business_id, _, _ = await _make_business_with_admin(client, token)

    suspended = await client.patch(
        f"/businesses/{business_id}",
        json={"status": "suspended"},
        headers=_auth_headers(token),
    )
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"

    reactivated = await client.patch(
        f"/businesses/{business_id}",
        json={"status": "active"},
        headers=_auth_headers(token),
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == "active"


async def test_setting_the_same_status_is_idempotent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    password = "super-secret-pass"
    admin = await _create_super_admin(db_session, password)
    token = await _login(client, admin.email, password)
    business_id, _, _ = await _make_business_with_admin(client, token)

    first = await client.patch(
        f"/businesses/{business_id}", json={"status": "active"}, headers=_auth_headers(token)
    )
    assert first.status_code == 200
    assert first.json()["status"] == "active"


async def test_business_admin_cannot_change_their_own_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The authorization decision that matters: a suspended tenant must not be able to
    un-suspend itself and resume spending."""
    password = "super-secret-pass"
    admin = await _create_super_admin(db_session, password)
    token = await _login(client, admin.email, password)
    business_id, admin_email, admin_password = await _make_business_with_admin(client, token)

    suspend = await client.patch(
        f"/businesses/{business_id}",
        json={"status": "suspended"},
        headers=_auth_headers(token),
    )
    assert suspend.status_code == 200

    biz_token = await _login(client, admin_email, admin_password)
    response = await client.patch(
        f"/businesses/{business_id}",
        json={"status": "active"},
        headers=_auth_headers(biz_token),
    )

    assert response.status_code == 403


async def test_suspending_rejects_an_unknown_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    password = "super-secret-pass"
    admin = await _create_super_admin(db_session, password)
    token = await _login(client, admin.email, password)
    business_id, _, _ = await _make_business_with_admin(client, token)

    response = await client.patch(
        f"/businesses/{business_id}",
        json={"status": "deleted"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


async def test_patching_an_unknown_business_is_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    password = "super-secret-pass"
    admin = await _create_super_admin(db_session, password)
    token = await _login(client, admin.email, password)

    response = await client.patch(
        f"/businesses/{uuid4()}",
        json={"status": "suspended"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404
