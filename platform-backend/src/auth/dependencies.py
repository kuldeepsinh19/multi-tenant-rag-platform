"""Auth dependencies shared across every domain. Names are a stable contract — other
domains (documents, chat, ingestion) import `require_business_admin`,
`get_current_business_id`, and `ensure_same_business` directly. Fails closed throughout:
any missing/invalid/mismatched credential raises, never falls through to "allow"."""

from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User, UserRole
from src.auth.security import decode_access_token
from src.core.db import get_db
from src.core.exceptions import NotAuthenticated, NotAuthorized

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise NotAuthenticated()
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise NotAuthenticated() from exc

    user = await db.get(User, UUID(payload.sub))
    if user is None:
        raise NotAuthenticated()
    return user


async def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.super_admin:
        raise NotAuthorized()
    return user


async def require_business_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.business_admin:
        raise NotAuthorized()
    return user


def get_current_business_id(user: User = Depends(require_business_admin)) -> UUID:
    if user.business_id is None:
        raise NotAuthorized()
    return user.business_id


def ensure_same_business(business_id: UUID, user: User) -> None:
    """The cross-tenant guard: a business_admin may only act on their own business,
    regardless of what business_id appears in the URL path. super_admin bypasses this.
    Call this at the top of every router handler that takes a business_id path param."""
    if user.role == UserRole.super_admin:
        return
    if user.business_id != business_id:
        raise NotAuthorized()
