"""Standalone script to bootstrap a super_admin user.

There is no public registration endpoint for super_admin on purpose (security: the
platform operator is the only one who should be able to mint one). Run from the repo
root via:

    docker compose run --rm api python scripts/create_superadmin.py <email> <password>
"""

import asyncio
import sys
from pathlib import Path

# Allow running as `python scripts/create_superadmin.py` with cwd at /app (repo root
# inside the container), where `src` is a top-level package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from src.auth.models import User, UserRole  # noqa: E402
from src.auth.security import hash_password  # noqa: E402
from src.core.db import async_session_factory  # noqa: E402
from src.core.logging import get_logger  # noqa: E402

# Register all ORM models so SQLAlchemy can resolve cross-table foreign keys when the ORM
# configures mappers for this session (e.g. users.business_id -> businesses.id).
import src.core.models  # noqa: E402, F401

logger = get_logger(__name__)


async def create_superadmin(email: str, password: str) -> None:
    async with async_session_factory() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            print(f"A user with email {email!r} already exists.", file=sys.stderr)
            raise SystemExit(1)

        user = User(
            email=email,
            password_hash=hash_password(password),
            role=UserRole.super_admin,
            business_id=None,
        )
        db.add(user)
        await db.commit()
        print(f"Created super_admin user {email!r}.")


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python scripts/create_superadmin.py <email> <password>", file=sys.stderr)
        raise SystemExit(2)

    _, email, password = sys.argv
    asyncio.run(create_superadmin(email, password))


if __name__ == "__main__":
    main()
