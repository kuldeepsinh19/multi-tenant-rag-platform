from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import (
    ensure_same_business,
    get_current_user,
    require_business_admin,
    require_super_admin,
)
from src.auth.models import User, UserRole
from src.auth.schemas import UserOut
from src.businesses.schemas import (
    AdminInvite,
    BusinessCreate,
    BusinessOut,
    WidgetKeyCreate,
    WidgetKeyOut,
)
from src.businesses.service import (
    create_business,
    create_widget_key,
    get_business,
    invite_admin,
    list_businesses,
)
from src.core.db import get_db
from src.core.exceptions import NotAuthorized
from src.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Accepts either a super_admin or a business_admin. Handlers that use this must
    call `ensure_same_business(business_id, user)` themselves to enforce tenant
    scoping — this dependency only narrows "authenticated" down to "some admin role."
    """
    if user.role not in (UserRole.super_admin, UserRole.business_admin):
        raise NotAuthorized()
    return user


@router.post("", response_model=BusinessOut, status_code=201)
async def create_business_endpoint(
    payload: BusinessCreate,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> BusinessOut:
    business = await create_business(db, payload.name)
    return BusinessOut.model_validate(business)


@router.get("", response_model=list[BusinessOut])
async def list_businesses_endpoint(
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> list[BusinessOut]:
    businesses = await list_businesses(db)
    return [BusinessOut.model_validate(b) for b in businesses]


@router.get("/{business_id}", response_model=BusinessOut)
async def get_business_endpoint(
    business_id: UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BusinessOut:
    ensure_same_business(business_id, user)
    business = await get_business(db, business_id)
    return BusinessOut.model_validate(business)


@router.post("/{business_id}/admins", response_model=UserOut, status_code=201)
async def invite_admin_endpoint(
    business_id: UUID,
    payload: AdminInvite,
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await invite_admin(db, business_id, payload.email, payload.password)
    return UserOut.model_validate(user)


@router.post("/{business_id}/widget-keys", response_model=WidgetKeyOut, status_code=201)
async def create_widget_key_endpoint(
    business_id: UUID,
    payload: WidgetKeyCreate,
    user: User = Depends(require_business_admin),
    db: AsyncSession = Depends(get_db),
) -> WidgetKeyOut:
    ensure_same_business(business_id, user)
    widget_key = await create_widget_key(db, business_id, payload.allowed_domains)
    return WidgetKeyOut.model_validate(widget_key)
