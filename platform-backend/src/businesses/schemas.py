from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.businesses.models import BusinessStatus


class BusinessCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class BusinessStatusUpdate(BaseModel):
    """Body for PATCH /businesses/{id}. An enum field, so an unknown status is a clean 422
    at the edge rather than a bad value reaching the tenant guard."""

    status: BusinessStatus


class BusinessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    status: BusinessStatus
    plan: str
    created_at: datetime


class AdminInvite(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class WidgetKeyCreate(BaseModel):
    allowed_domains: list[str] = Field(default_factory=list, max_length=50)


class WidgetKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_key: str
    allowed_domains: list[str]
    is_active: bool
    created_at: datetime
