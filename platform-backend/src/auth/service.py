"""Auth business logic — kept out of the router so it's independently testable."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User
from src.auth.security import verify_password


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    """Looks up the user by email and verifies the password. Returns None on any
    failure (unknown email or wrong password) — callers must fail closed and raise
    a generic NotAuthenticated, never distinguish "no such user" from "wrong password"
    in the response."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
