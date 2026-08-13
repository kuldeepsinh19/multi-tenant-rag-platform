"""Document CRUD service. Every lookup is tenant-scoped by business_id — never a bare
PK lookup — per the multi-tenancy security boundary in project-conventions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ResourceNotFound
from src.documents.models import Document, DocumentStatus


async def create_document_record(
    db: AsyncSession,
    business_id: UUID,
    filename: str,
    mime_type: str,
    uploaded_by: UUID | None,
) -> Document:
    document = Document(
        business_id=business_id,
        filename=filename,
        mime_type=mime_type,
        status=DocumentStatus.pending,
        uploaded_by=uploaded_by,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def list_documents(db: AsyncSession, business_id: UUID) -> list[Document]:
    result = await db.execute(
        select(Document)
        .where(Document.business_id == business_id)
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def get_document(db: AsyncSession, business_id: UUID, document_id: UUID) -> Document:
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.business_id == business_id,
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise ResourceNotFound("Document not found.")
    return document


async def delete_document(db: AsyncSession, business_id: UUID, document_id: UUID) -> None:
    document = await get_document(db, business_id, document_id)
    await db.delete(document)
    await db.commit()
