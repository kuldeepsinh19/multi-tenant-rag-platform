from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.businesses.models import BusinessStatus


class BusinessCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


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
