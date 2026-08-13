"""Security regression tests for the document upload hardening:

- path traversal / absolute-path filenames are reduced to a safe leaf name (never escape
  the per-document directory),
- oversized uploads are rejected with 413,
- a suspended business cannot ingest new documents (403).
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User, UserRole
from src.auth.security import hash_password
from src.businesses.models import Business, BusinessStatus


async def _business_with_admin(
    db_session: AsyncSession, password: str, *, status: BusinessStatus = BusinessStatus.active
) -> tuple[Business, User]:
    business = Business(
        name=f"Upload Test Biz {uuid4().hex[:8]}",
        slug=f"upl-{uuid4().hex[:8]}",
        status=status,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)

    admin = User(
        email=f"test-upl-admin-{uuid4().hex[:8]}@example.com",
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
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    "hostile_name",
    [
        "../../../etc/cron.d/evil.txt",
        "/etc/passwd.txt",
        "..\\..\\windows\\system32\\evil.md",
        "subdir/nested/notes.md",
    ],
)
async def test_upload_sanitizes_traversal_filename(
    client: AsyncClient, db_session: AsyncSession, hostile_name: str
) -> None:
    password = "upl-pass"
    business, admin = await _business_with_admin(db_session, password)
    token = await _login(client, admin.email, password)

    response = await client.post(
        f"/businesses/{business.id}/documents",
        files={"file": (hostile_name, b"harmless content", "text/plain")},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    stored = response.json()["filename"]
    # The stored (and on-disk) name is a bare leaf — no directory separators survive.
    assert "/" not in stored
    assert "\\" not in stored
    assert not stored.startswith("..")


async def test_upload_rejects_oversized_file(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Shrink the cap so the test doesn't have to send 25 MB to exercise the reject path.
    monkeypatch.setattr("src.documents.router._MAX_UPLOAD_BYTES", 16)

    password = "upl-pass"
    business, admin = await _business_with_admin(db_session, password)
    token = await _login(client, admin.email, password)

    response = await client.post(
        f"/businesses/{business.id}/documents",
        files={"file": ("big.txt", b"x" * 1024, "text/plain")},
        headers=_auth(token),
    )
    assert response.status_code == 413, response.text


async def test_suspended_business_cannot_upload(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    password = "upl-pass"
    business, admin = await _business_with_admin(
        db_session, password, status=BusinessStatus.suspended
    )
    token = await _login(client, admin.email, password)

    response = await client.post(
        f"/businesses/{business.id}/documents",
        files={"file": ("policy.txt", b"content", "text/plain")},
        headers=_auth(token),
    )
    assert response.status_code == 403, response.text
