"""Document upload/list/delete endpoints, mounted under /businesses per main.py.

Every handler is a business_admin action scoped to the caller's own tenant:
`require_business_admin` authenticates + role-checks, `ensure_same_business` blocks
cross-tenant access to a business_id supplied in the path. Ingestion itself never runs
here — it's hand off to the Arq worker (see src/ingestion/service.py), per
fastapi-backend-standards (long work must not block a request handler).
"""

import asyncio
from pathlib import Path
from uuid import UUID

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import APIRouter, Depends, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import ensure_same_business, require_business_admin
from src.auth.models import User
from src.businesses.service import ensure_business_active
from src.core.config import get_settings
from src.core.db import get_db
from src.core.exceptions import DomainError
from src.core.logging import get_logger
from src.documents.schemas import DocumentOut
from src.documents.service import (
    create_document_record,
    delete_document,
    get_document,
    list_documents,
)

router = APIRouter()
logger = get_logger(__name__)

_UPLOAD_ROOT = Path("/app/uploads")

# Reject obviously-wrong uploads before they ever reach disk or the worker.
_ALLOWED_SUFFIXES = {".txt", ".md", ".pdf", ".docx"}
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

_arq_pool: ArqRedis | None = None
_arq_pool_loop: object | None = None


class UnsupportedUploadType(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    client_message = "Unsupported file type. Allowed: .txt, .md, .pdf, .docx"


class UploadTooLarge(DomainError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    client_message = "File exceeds the maximum upload size."


def _safe_upload_name(raw_filename: str, suffix: str) -> str:
    """Reduce a client-supplied filename to a safe leaf name for on-disk storage.

    The upload filename is fully attacker-controlled: `../../etc/cron.d/x.txt` or an
    absolute `/etc/passwd`-style path would otherwise escape the per-document directory
    when joined (pathlib resets the join on an absolute segment). `Path(...).name` strips
    every directory component, and we fall back to a synthetic name if nothing usable
    remains. This is the value written to disk AND stored as the display filename, so a
    hostile path never reaches either sink.
    """
    leaf = Path(raw_filename).name.strip()
    # Reject a residual traversal token or empty result; keep the validated suffix.
    if not leaf or leaf in {".", ".."} or "/" in leaf or "\\" in leaf:
        return f"upload{suffix}"
    return leaf


async def _read_upload_capped(file: UploadFile, cap_bytes: int) -> bytes:
    """Read an upload in bounded chunks, aborting as soon as the cap is exceeded.

    `await file.read()` with no argument buffers the entire request body (memory + spooled
    temp file) before any size check, so a multi-GB body exhausts resources before the cap
    is ever evaluated. Reading in 1 MiB chunks and stopping at the cap bounds peak usage to
    roughly the cap regardless of how large the client claims/sends the body to be.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > cap_bytes:
            raise UploadTooLarge()
        chunks.append(chunk)
    return b"".join(chunks)


async def _get_arq_pool() -> ArqRedis:
    """Return an Arq pool bound to the currently-running event loop.

    The underlying redis-py async pool binds to the loop it was first used on. Production
    runs a single loop for the app's lifetime, so this creates the pool once; but if the
    loop is ever replaced (e.g. under pytest-asyncio, where each test gets its own loop) a
    pool from a closed loop raises "Event loop is closed" on the next enqueue. Rebinding on
    a loop change mirrors RateLimitMiddleware._get_redis() and the per-test engine disposal.
    """
    global _arq_pool, _arq_pool_loop
    loop = asyncio.get_running_loop()
    if _arq_pool is None or _arq_pool_loop is not loop:
        settings = get_settings()
        _arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        _arq_pool_loop = loop
    return _arq_pool


@router.post(
    "/{business_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    business_id: UUID,
    file: UploadFile,
    request: Request,
    user: User = Depends(require_business_admin),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    ensure_same_business(business_id, user)
    # A suspended tenant may not ingest new documents (stops disk + worker + embed spend).
    await ensure_business_active(db, business_id)

    raw_filename = file.filename or "upload"
    suffix = Path(raw_filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise UnsupportedUploadType()

    # Reject early on an oversized declared Content-Length before reading a single byte.
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > _MAX_UPLOAD_BYTES:
        raise UploadTooLarge()

    # Bounded read: never buffer more than the cap, whatever the client actually sends.
    content = await _read_upload_capped(file, _MAX_UPLOAD_BYTES)

    # Sanitize to a safe leaf name — used for BOTH the on-disk path and the stored display
    # name — so a traversal/absolute path can never escape the per-document directory.
    safe_name = _safe_upload_name(raw_filename, suffix)

    document = await create_document_record(
        db,
        business_id=business_id,
        filename=safe_name,
        mime_type=file.content_type or "application/octet-stream",
        uploaded_by=user.id,
    )

    dest_dir = _UPLOAD_ROOT / str(document.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / safe_name
    # Defense in depth: assert the resolved path is still inside the per-document dir.
    if not dest_path.resolve().is_relative_to(dest_dir.resolve()):
        raise UnsupportedUploadType()
    dest_path.write_bytes(content)

    pool = await _get_arq_pool()
    await pool.enqueue_job("ingest_document_task", str(document.id), str(dest_path))

    logger.info("document_uploaded", document_id=str(document.id), business_id=str(business_id))
    return DocumentOut.model_validate(document)


@router.get("/{business_id}/documents", response_model=list[DocumentOut])
async def list_business_documents(
    business_id: UUID,
    user: User = Depends(require_business_admin),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentOut]:
    ensure_same_business(business_id, user)
    documents = await list_documents(db, business_id)
    return [DocumentOut.model_validate(doc) for doc in documents]


@router.delete("/{business_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_business_document(
    business_id: UUID,
    document_id: UUID,
    user: User = Depends(require_business_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    ensure_same_business(business_id, user)
    # Verifies tenant ownership (raises ResourceNotFound otherwise) before any disk I/O.
    await get_document(db, business_id, document_id)
    await delete_document(db, business_id, document_id)

    doc_dir = _UPLOAD_ROOT / str(document_id)
    if doc_dir.exists():
        for child in doc_dir.iterdir():
            child.unlink(missing_ok=True)
        doc_dir.rmdir()
