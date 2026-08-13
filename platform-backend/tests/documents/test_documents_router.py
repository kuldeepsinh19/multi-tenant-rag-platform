"""Covers the document upload/list/delete endpoints: happy path, file-type rejection,
and the cross-tenant boundary (a business_admin must never reach another business's
documents, mirroring the same guarantee tests/businesses/test_businesses.py proves for
business details)."""

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User, UserRole
from src.auth.security import hash_password
from src.businesses.models import Business


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


async def _create_business_with_admin(
    db_session: AsyncSession, password: str
) -> tuple[Business, User]:
    business = Business(name=f"Docs Test Biz {uuid4().hex[:8]}", slug=f"docs-{uuid4().hex[:8]}")
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)

    admin = User(
        email=f"test-docs-admin-{uuid4().hex[:8]}@example.com",
        password_hash=hash_password(password),
        role=UserRole.business_admin,
        business_id=business.id,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return business, admin


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    token: str = response.json()["access_token"]
    return token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_upload_list_and_delete_document_happy_path(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    password = "doc-admin-pass"
    business, admin = await _create_business_with_admin(db_session, password)
    token = await _login(client, admin.email, password)

    upload_response = await client.post(
        f"/businesses/{business.id}/documents",
        files={"file": ("policy.txt", b"Our return policy is thirty days.", "text/plain")},
        headers=_auth_headers(token),
    )
    assert upload_response.status_code == 201, upload_response.text
    document = upload_response.json()
    assert document["filename"] == "policy.txt"
    assert document["status"] in ("pending", "processing", "ready")

    list_response = await client.get(
        f"/businesses/{business.id}/documents", headers=_auth_headers(token)
    )
    assert list_response.status_code == 200
    assert any(d["id"] == document["id"] for d in list_response.json())

    delete_response = await client.delete(
        f"/businesses/{business.id}/documents/{document['id']}", headers=_auth_headers(token)
    )
    assert delete_response.status_code == 204

    list_after_delete = await client.get(
        f"/businesses/{business.id}/documents", headers=_auth_headers(token)
    )
    assert all(d["id"] != document["id"] for d in list_after_delete.json())


async def test_upload_rejects_unsupported_file_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    password = "doc-admin-pass"
    business, admin = await _create_business_with_admin(db_session, password)
    token = await _login(client, admin.email, password)

    response = await client.post(
        f"/businesses/{business.id}/documents",
        files={"file": ("malware.exe", b"not a document", "application/octet-stream")},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


async def test_business_admin_cannot_access_another_businesses_documents(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    password_a = "biz-a-admin-pass"
    password_b = "biz-b-admin-pass"
    business_a, admin_a = await _create_business_with_admin(db_session, password_a)
    business_b, admin_b = await _create_business_with_admin(db_session, password_b)

    token_b = await _login(client, admin_b.email, password_b)

    # Business B's admin must not be able to upload into, list, or delete from
    # Business A's document collection.
    upload_response = await client.post(
        f"/businesses/{business_a.id}/documents",
        files={"file": ("sneaky.txt", b"should not land here", "text/plain")},
        headers=_auth_headers(token_b),
    )
    assert upload_response.status_code == 403

    list_response = await client.get(
        f"/businesses/{business_a.id}/documents", headers=_auth_headers(token_b)
    )
    assert list_response.status_code == 403

    delete_response = await client.delete(
        f"/businesses/{business_a.id}/documents/{uuid4()}", headers=_auth_headers(token_b)
    )
    assert delete_response.status_code == 403
