from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.auth.models import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    # Bounded at the boundary: reject a 1-char-minimum..1024 password before it reaches the
    # hasher, so an oversized body can't be used as a cheap resource-exhaustion vector.
    password: str = Field(..., min_length=1, max_length=1024)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    business_id: UUID | None


class TokenPayload(BaseModel):
    sub: str
    role: UserRole
    business_id: UUID | None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: UserRole
    business_id: UUID | None
    created_at: datetime
