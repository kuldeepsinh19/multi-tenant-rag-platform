"""The document ingestion pipeline: parse -> chunk -> screen -> embed -> persist.

Runs in the Arq worker (src/core/worker.py), never in a FastAPI request handler — this is
slow, I/O- and CPU-bound work per fastapi-backend-standards. `ingest_document` accepts an
optional `embedder` param (defaulting to `get_embedder()`) purely so tests can inject a
fake embedding provider instead of making a real network call.
"""

import re
from pathlib import Path
from uuid import UUID

from llama_index.core.node_parser import SentenceSplitter
from sqlalchemy import delete, func

from src.core.db import async_session_factory
from src.core.logging import get_logger
from src.documents.models import Document, DocumentStatus
from src.ingestion.models import Chunk
from src.llm.base import EmbeddingProvider
from src.llm.registry import get_embedder

logger = get_logger(__name__)

_CHUNK_SIZE = 1000
_CHUNK_OVERLAP = 100

# Deliberately simple, high-recall heuristics: this is a first line of defense that flags
# suspicious ingested text for downstream guardrails, not a full jailbreak classifier.
# See rag-retrieval-standards / llm-guardrails-standards.
_INJECTION_PATTERNS = [
    re.compile(r"ignore (all |any )?(previous|prior|above) instructions", re.IGNORECASE),
    re.compile(r"disregard (all |any )?(previous|prior|above)", re.IGNORECASE),
    re.compile(r"you are now", re.IGNORECASE),
    re.compile(r"system prompt", re.IGNORECASE),
    re.compile(r"act as (a|an) ", re.IGNORECASE),
    re.compile(r"new instructions?:", re.IGNORECASE),
    re.compile(r"\bDAN\b"),
    re.compile(r"override (your |the )?(rules|instructions|guardrails)", re.IGNORECASE),
]


class UnsupportedFileType(ValueError):
    """Raised when the uploaded file extension has no parser."""


def parse_file_to_text(file_path: str) -> str:
    """Extract plain text from a supported file on disk. Supports .txt/.md (read
    directly), .pdf (pypdf), and .docx (python-docx) per the pragmatic-parsing choice
    for this stage — no heavyweight `unstructured` dependency."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="replace")

    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)

    if suffix == ".docx":
        from docx import Document as DocxDocument

        docx_file = DocxDocument(str(path))
        return "\n\n".join(p.text for p in docx_file.paragraphs)

    raise UnsupportedFileType(f"Unsupported file extension: {suffix!r}")


def chunk_text(
    text: str, chunk_size: int = _CHUNK_SIZE, chunk_overlap: int = _CHUNK_OVERLAP
) -> list[str]:
    """Semantic-ish chunking on sentence/paragraph boundaries (not fixed character
    counts) via llama-index-core's SentenceSplitter. Pure function — no I/O — so it's
    unit-testable without a DB or network."""
    if not text.strip():
        return []
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return [chunk for chunk in splitter.split_text(text) if chunk.strip()]


def screen_for_injection(text: str) -> bool:
    """Returns True if the chunk contains obvious planted-prompt-injection patterns.
    This is a cheap first-pass screen; flagged chunks are still stored (so the document
    isn't silently dropped) but tagged in chunk_metadata so downstream prompt assembly
    can exclude or specially handle them. See rag-retrieval-standards."""
    return any(pattern.search(text) for pattern in _INJECTION_PATTERNS)


async def ingest_document(
    document_id: UUID,
    file_path: str,
    embedder: EmbeddingProvider | None = None,
) -> None:
    """The ingestion pipeline. `embedder` defaults to the configured provider via the
    registry; tests pass a fake to avoid real network calls (no Gemini key configured
    in this environment)."""
    embedder = embedder or get_embedder()

    async with async_session_factory() as db:
        document = await db.get(Document, document_id)
        if document is None:
            logger.error("ingest_document_not_found", document_id=str(document_id))
            return

        document.status = DocumentStatus.processing
        document.error = None
        await db.commit()

        try:
            text = parse_file_to_text(file_path)
            chunks = chunk_text(text)

            if not chunks:
                raise ValueError("No extractable text content in document.")

            flags = [screen_for_injection(chunk) for chunk in chunks]
            vectors = await embedder.embed(chunks)

            if len(vectors) != len(chunks):
                raise ValueError("Embedding provider returned a mismatched vector count.")

            # Re-ingestion safety: remove any stale chunks for this document before
            # inserting the new set, per rag-retrieval-standards.
            await db.execute(delete(Chunk).where(Chunk.document_id == document_id))

            for i, (content, vector, flagged) in enumerate(
                zip(chunks, vectors, flags, strict=True)
            ):
                metadata: dict[str, object] = {
                    "title": document.filename,
                    "chunk_index": i,
                }
                if flagged:
                    metadata["flagged"] = True
                db.add(
                    Chunk(
                        document_id=document_id,
                        business_id=document.business_id,
                        content=content,
                        chunk_metadata=metadata,
                        embedding=vector,
                        tsv=func.to_tsvector("english", content),
                    )
                )

            document.status = DocumentStatus.ready
            document.error = None
            await db.commit()
        except Exception as exc:
            logger.error(
                "ingestion_failed",
                document_id=str(document_id),
                error_type=type(exc).__name__,
                exc_info=exc,
            )
            await db.rollback()
            document = await db.get(Document, document_id)
            if document is not None:
                document.status = DocumentStatus.failed
                document.error = "This document could not be processed."
                await db.commit()
