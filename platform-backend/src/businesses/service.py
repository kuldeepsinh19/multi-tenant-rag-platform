"""Business (tenant) management — business logic only, no request/response concerns."""

import re
import secrets
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User, UserRole
from src.auth.security import hash_password
from src.businesses.models import Business, BusinessStatus, WidgetKey
from src.core.exceptions import BusinessSuspended, ResourceNotFound
from src.core.logging import get_logger

logger = get_logger(__name__)

_SLUG_INVALID_CHARS = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    slug = _SLUG_INVALID_CHARS.sub("-", name.strip().lower()).strip("-")
    return slug or "business"


async def create_business(db: AsyncSession, name: str) -> Business:
    """Auto-generates a unique slug from `name`. Insert-then-retry-on-conflict rather
    than check-then-insert, to avoid a TOCTOU race between two concurrent creations
    with the same name."""
    base_slug = _slugify(name)

    for attempt in range(5):
        slug = base_slug if attempt == 0 else f"{base_slug}-{secrets.token_hex(3)}"
        business = Business(name=name, slug=slug)
        db.add(business)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            continue
        await db.refresh(business)
        return business

    raise RuntimeError("Could not generate a unique business slug after several attempts.")


async def list_businesses(db: AsyncSession) -> list[Business]:
    result = await db.execute(select(Business).order_by(Business.created_at.desc()))
    return list(result.scalars().all())


async def get_business(db: AsyncSession, business_id: UUID) -> Business:
    business = await db.get(Business, business_id)
    if business is None:
        raise ResourceNotFound("Business not found.")
    return business


async def ensure_business_active(db: AsyncSession, business_id: UUID) -> None:
    """Guard for tenant-facing, resource-consuming actions (chat, uploads): the business
    must exist and be active. Raises ResourceNotFound if unknown, BusinessSuspended if not
    active. Call this at the point of action, in addition to the auth/tenant checks — a
    suspended tenant must stop spending on LLM calls and ingestion even if its credentials
    (JWT or widget key) are still otherwise valid."""
    business = await get_business(db, business_id)
    if business.status != BusinessStatus.active:
        logger.warning("business_suspended_action_blocked", business_id=str(business_id))
        raise BusinessSuspended()


async def invite_admin(db: AsyncSession, business_id: UUID, email: str, password: str) -> User:
    """Ensures the target business exists, then creates a business_admin User scoped
    to it."""
    await get_business(db, business_id)

    user = User(
        email=email,
        password_hash=hash_password(password),
        role=UserRole.business_admin,
        business_id=business_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_widget_key(
    db: AsyncSession, business_id: UUID, allowed_domains: list[str]
) -> WidgetKey:
    await get_business(db, business_id)

    widget_key = WidgetKey(
        business_id=business_id,
        public_key=secrets.token_urlsafe(32),
        allowed_domains=allowed_domains,
    )
    db.add(widget_key)
    await db.commit()
    await db.refresh(widget_key)
    return widget_key
