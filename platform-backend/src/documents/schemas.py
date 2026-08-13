from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.documents.models import DocumentStatus


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    filename: str
    mime_type: str
    status: DocumentStatus
    error: str | None
    created_at: datetime
    updated_at: datetime
