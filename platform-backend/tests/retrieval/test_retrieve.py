"""Integration tests for hybrid `retrieve()` against the REAL Postgres (pgvector + FTS)
started by docker-compose. No DB mocking — only the embedder and reranker are injected,
because there is no Gemini key here and we don't want a per-test ONNX model download.

These tests prove the two properties that matter most for this layer:
  * context recall  — the planted relevant chunk ranks above irrelevant ones;
  * tenant isolation — `retrieve()` NEVER returns a chunk from a different business_id.

Business/document identifiers are uuid4-suffixed so concurrent test runs (and the other
agents' work against this shared DB) can't collide.
"""

from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from src.businesses.models import Business
from src.documents.models import Document, DocumentStatus
from src.ingestion.models import EMBED_DIM, Chunk
from src.retrieval.service import retrieve

# A deterministic query vector: unit weight on dimension 0, zero elsewhere. The "relevant"
# chunk is embedded identically (cosine distance 0); "irrelevant" chunks are embedded on a
# different axis (orthogonal, cosine distance 1), so the dense side has an unambiguous winner.
_QUERY_VECTOR = [1.0] + [0.0] * (EMBED_DIM - 1)
_ORTHOGONAL_VECTOR = [0.0, 1.0] + [0.0] * (EMBED_DIM - 2)


class _FakeEmbedder:
    """Returns `_QUERY_VECTOR` for whatever query text is passed — the relevance signal
    lives in the pre-seeded chunk embeddings, not in the query text."""

    @property
    def dim(self) -> int:
        return EMBED_DIM

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(_QUERY_VECTOR) for _ in texts]


class _PassthroughReranker:
    """Trivial reranker: score = -position, preserving the RRF/merge order without a model
    download. Scores start above `retrieval_min_score` (0.35) so ranked items clear the
    threshold, letting us assert ordering rather than exercise the real cross-encoder."""

    async def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        return [1.0 - 0.1 * i for i in range(len(documents))]


async def _make_business(db: AsyncSession) -> Business:
    business = Business(
        name=f"Retrieval Test Biz {uuid4().hex[:8]}", slug=f"retr-{uuid4().hex[:8]}"
    )
    db.add(business)
    await db.commit()
    await db.refresh(business)
    return business


async def _make_document(db: AsyncSession, business_id: UUID) -> Document:
    document = Document(
        business_id=business_id,
        filename=f"doc-{uuid4().hex[:8]}.txt",
        mime_type="text/plain",
        status=DocumentStatus.ready,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def _add_chunk(
    db: AsyncSession,
    *,
    business_id: UUID,
    document_id: UUID,
    content: str,
    embedding: list[float],
) -> Chunk:
    chunk = Chunk(
        business_id=business_id,
        document_id=document_id,
        content=content,
        chunk_metadata={"title": "seed"},
        embedding=embedding,
        tsv=func.to_tsvector("english", content),
    )
    db.add(chunk)
    await db.commit()
    await db.refresh(chunk)
    return chunk


@pytest.fixture
def fake_embedder() -> _FakeEmbedder:
    return _FakeEmbedder()


@pytest.fixture
def passthrough_reranker() -> _PassthroughReranker:
    return _PassthroughReranker()


async def test_retrieve_ranks_relevant_chunk_first(
    db_session: AsyncSession,
    fake_embedder: _FakeEmbedder,
    passthrough_reranker: _PassthroughReranker,
) -> None:
    business = await _make_business(db_session)
    document = await _make_document(db_session, business.id)

    relevant = await _add_chunk(
        db_session,
        business_id=business.id,
        document_id=document.id,
        content="Our refund policy allows returns within thirty days for a full refund.",
        embedding=list(_QUERY_VECTOR),
    )
    for _ in range(3):
        await _add_chunk(
            db_session,
            business_id=business.id,
            document_id=document.id,
            content="Unrelated content about office parking arrangements and lunch menus.",
            embedding=list(_ORTHOGONAL_VECTOR),
        )

    results = await retrieve(
        db_session,
        business.id,
        "refund policy",
        embedder=fake_embedder,
        reranker=passthrough_reranker,
    )

    assert results, "expected at least the relevant chunk to be retrieved"
    assert results[0].chunk_id == relevant.id  # context recall: relevant chunk on top
    assert results[0].document_id == document.id  # provenance carried through
    assert results[0].metadata["title"] == "seed"


async def test_retrieve_never_crosses_tenants(
    db_session: AsyncSession,
    fake_embedder: _FakeEmbedder,
    passthrough_reranker: _PassthroughReranker,
) -> None:
    biz_a = await _make_business(db_session)
    biz_b = await _make_business(db_session)
    doc_a = await _make_document(db_session, biz_a.id)
    doc_b = await _make_document(db_session, biz_b.id)

    # Both tenants hold a chunk that matches the query perfectly (same embedding + keyword).
    chunk_a = await _add_chunk(
        db_session,
        business_id=biz_a.id,
        document_id=doc_a.id,
        content="Tenant A refund policy: returns within thirty days.",
        embedding=list(_QUERY_VECTOR),
    )
    chunk_b = await _add_chunk(
        db_session,
        business_id=biz_b.id,
        document_id=doc_b.id,
        content="Tenant B refund policy: returns within thirty days.",
        embedding=list(_QUERY_VECTOR),
    )

    results = await retrieve(
        db_session,
        biz_a.id,
        "refund policy",
        embedder=fake_embedder,
        reranker=passthrough_reranker,
    )

    returned_ids = {r.chunk_id for r in results}
    assert chunk_a.id in returned_ids
    assert chunk_b.id not in returned_ids  # strict tenant isolation
    assert all(r.document_id == doc_a.id for r in results)


async def test_retrieve_empty_query_returns_empty(
    db_session: AsyncSession,
    fake_embedder: _FakeEmbedder,
    passthrough_reranker: _PassthroughReranker,
) -> None:
    business = await _make_business(db_session)
    results = await retrieve(
        db_session,
        business.id,
        "   ",
        embedder=fake_embedder,
        reranker=passthrough_reranker,
    )
    assert results == []


async def test_retrieve_drops_below_threshold_never_pads(
    db_session: AsyncSession,
    fake_embedder: _FakeEmbedder,
) -> None:
    """Even with matching chunks present, if the reranker scores everything below
    `retrieval_min_score` the result is empty — retrieval never pads with weak context."""

    class _ZeroReranker:
        async def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
            return [0.0 for _ in documents]

    business = await _make_business(db_session)
    document = await _make_document(db_session, business.id)
    await _add_chunk(
        db_session,
        business_id=business.id,
        document_id=document.id,
        content="Refund policy content that matches the query keyword.",
        embedding=list(_QUERY_VECTOR),
    )

    results = await retrieve(
        db_session,
        business.id,
        "refund policy",
        embedder=fake_embedder,
        reranker=_ZeroReranker(),
    )
    assert results == []


@pytest.mark.slow
async def test_retrieve_with_real_reranker_smoke(
    db_session: AsyncSession, fake_embedder: _FakeEmbedder
) -> None:
    """Exercises the REAL fastembed cross-encoder end-to-end (downloads an ONNX model on
    first run). Marked `slow` and degrades gracefully — skipped, not failed — if the model
    can't be fetched in this environment, so the tenant-isolation guarantees above never
    depend on network access."""
    business = await _make_business(db_session)
    document = await _make_document(db_session, business.id)
    await _add_chunk(
        db_session,
        business_id=business.id,
        document_id=document.id,
        content="Our refund policy allows returns within thirty days for a full refund.",
        embedding=list(_QUERY_VECTOR),
    )
    await _add_chunk(
        db_session,
        business_id=business.id,
        document_id=document.id,
        content="Completely unrelated text about parking and lunch.",
        embedding=list(_ORTHOGONAL_VECTOR),
    )

    try:
        results = await retrieve(
            db_session, business.id, "what is the refund policy", embedder=fake_embedder
        )
    except Exception as exc:  # pragma: no cover - environment/network dependent
        pytest.skip(f"real reranker unavailable in this environment: {exc!r}")

    # If the model loaded, the refund chunk should out-rank the parking chunk.
    assert all(r.metadata["title"] == "seed" for r in results)
    if results:
        assert "refund" in results[0].content.lower()
