from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.schemas import LoginRequest, TokenResponse
from src.auth.security import create_access_token
from src.auth.service import authenticate
from src.core.db import get_db
from src.core.exceptions import NotAuthenticated
from src.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await authenticate(db, payload.email, payload.password)
    if user is None:
        # Security audit trail: record the failed attempt (email is the account identifier,
        # not a secret) without revealing whether the email exists — the client still gets a
        # single generic "invalid email or password".
        logger.warning("auth_login_failed", email=payload.email)
        raise NotAuthenticated("Invalid email or password.")

    token = create_access_token(user.id, user.role, user.business_id)
    logger.info(
        "auth_login_success",
        user_id=str(user.id),
        role=user.role.value,
        business_id=str(user.business_id) if user.business_id else None,
    )
    return TokenResponse(
        access_token=token,
        role=user.role,
        business_id=user.business_id,
    )
