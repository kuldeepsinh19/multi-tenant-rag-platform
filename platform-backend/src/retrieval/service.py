"""Hybrid retrieval: dense (pgvector cosine) + sparse (Postgres full-text BM25-style),
merged with Reciprocal Rank Fusion, then reranked with a cross-encoder before returning.

Per rag-retrieval-standards: hybrid search is the baseline (not an upgrade), the merged
candidates are reranked with a cross-encoder before they reach the model, and provenance
(document_id, chunk_metadata) is carried all the way to the result so the generation layer
can cite it and the guardrail layer can verify groundedness. Per project-conventions:
retrieval is a trust boundary — EVERY query filters by business_id; nothing crosses tenants.
If nothing clears the score bar we return an empty list — we never pad.

The cross-encoder (fastembed's TextCrossEncoder, ONNX/CPU) is loaded once and cached at
module level because model load is expensive, and every call to it is dispatched to a
worker thread (it is synchronous/CPU-bound) so it never blocks the event loop.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

import anyio.to_thread
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.exceptions import RetrievalFailed
from src.core.logging import get_logger
from src.ingestion.models import Chunk
from src.llm.base import EmbeddingProvider
from src.llm.registry import get_embedder
from src.retrieval.schemas import RetrievedChunk

if TYPE_CHECKING:
    from fastembed.rerank.cross_encoder import TextCrossEncoder

logger = get_logger(__name__)

# Standard RRF constant; damps the influence of any single ranker's tail (higher rank ->
# smaller contribution). 60 is the value from the original Cormack et al. RRF paper.
_RRF_K = 60

# fastembed ships this lightweight ONNX cross-encoder; downloaded once on first use.
_RERANKER_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"


@dataclass(frozen=True)
class _Candidate:
    """A retrieved row before fusion/rerank. `content`/`metadata` are carried so we never
    re-hit the DB after ranking, and so provenance survives to the result."""

    chunk_id: UUID
    document_id: UUID
    content: str
    metadata: dict[str, object]


class Reranker(Protocol):
    """Cross-encoder rerank contract. Real impl is fastembed's TextCrossEncoder (wrapped);
    tests inject a trivial passthrough so they don't download an ONNX model over the
    network. Returns one relevance score per document, aligned to `documents` order."""

    async def rerank(self, query: str, documents: Sequence[str]) -> list[float]: ...


class _FastEmbedReranker:
    """Adapts fastembed's synchronous TextCrossEncoder to the async `Reranker` Protocol.
    The model is loaded lazily and cached at module level (see `_get_default_reranker`);
    the CPU-bound `rerank` call is dispatched to a worker thread so it can't block the
    event loop (fastapi-backend-standards: async correctness)."""

    def __init__(self, encoder: TextCrossEncoder) -> None:
        self._encoder = encoder

    async def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        docs = list(documents)

        def _run() -> list[float]:
            return list(self._encoder.rerank(query, docs))

        return await anyio.to_thread.run_sync(_run)


@lru_cache(maxsize=1)
def _get_default_reranker() -> Reranker:
    """Load + cache the cross-encoder once. Isolated behind lru_cache because model
    construction (ONNX session + first-run model download) is expensive and must not
    happen per-call."""
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return _FastEmbedReranker(TextCrossEncoder(model_name=_RERANKER_MODEL))


async def _dense_search(
    db: AsyncSession, business_id: UUID, query_vector: list[float], limit: int
) -> list[_Candidate]:
    """Nearest-neighbor over the tenant's chunks by pgvector cosine distance. Returns
    candidates in ascending-distance (most-similar-first) order."""
    stmt = (
        select(Chunk)
        .where(Chunk.business_id == business_id)
        .order_by(Chunk.embedding.cosine_distance(query_vector))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [_to_candidate(chunk) for chunk in result.scalars().all()]


async def _sparse_search(
    db: AsyncSession, business_id: UUID, query: str, limit: int
) -> list[_Candidate]:
    """BM25-style keyword search over the tenant's chunks via Postgres full-text ranking
    (ts_rank_cd on the pre-computed `tsv` column). Only rows that actually match the
    tsquery are returned, best-ranked first. plainto_tsquery safely parameterizes the raw
    user query (no injection into the SQL text)."""
    # plainto_tsquery parameterizes the raw user text — it is never interpolated into SQL.
    tsquery = func.plainto_tsquery("english", query)
    stmt = (
        select(Chunk)
        .where(Chunk.business_id == business_id)
        .where(Chunk.tsv.op("@@")(tsquery))
        .order_by(func.ts_rank_cd(Chunk.tsv, tsquery).desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [_to_candidate(chunk) for chunk in result.scalars().all()]


def _to_candidate(chunk: Chunk) -> _Candidate:
    return _Candidate(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        content=chunk.content,
        metadata=dict(chunk.chunk_metadata or {}),
    )


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[UUID]], *, k: int = _RRF_K
) -> list[UUID]:
    """Fuse several ranked id-lists into one, deduplicating by id. Each id's score is the
    sum over lists of 1/(k + rank), rank being its 0-based position in that list. Higher
    fused score ranks first; ties break by first appearance for determinism. Pure function
    (no DB, no I/O) so it's unit-testable in isolation."""
    scores: dict[UUID, float] = {}
    first_seen: dict[UUID, int] = {}
    order = 0
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            if chunk_id not in first_seen:
                first_seen[chunk_id] = order
                order += 1
    return sorted(scores, key=lambda cid: (-scores[cid], first_seen[cid]))


async def retrieve(
    db: AsyncSession,
    business_id: UUID,
    query: str,
    *,
    top_k: int | None = None,
    embedder: EmbeddingProvider | None = None,
    reranker: Reranker | None = None,
) -> list[RetrievedChunk]:
    """Hybrid retrieve for a single tenant: dense + sparse -> RRF merge -> cross-encoder
    rerank -> threshold -> top_k.

    `business_id` scopes every underlying query (trust boundary — never cross-tenant).
    `embedder`/`reranker` default to the configured providers but can be injected (tests
    pass fakes to avoid network calls), mirroring src/ingestion/service.ingest_document.
    Returns an empty list when nothing clears `retrieval_min_score` — we never pad.
    Any external failure is wrapped as RetrievalFailed."""
    settings = get_settings()
    if not query.strip():
        return []

    embedder = embedder or get_embedder()
    reranker = reranker or _get_default_reranker()
    final_k = top_k if top_k is not None else settings.retrieval_top_k_final
    candidate_k = settings.retrieval_top_k_candidates

    try:
        embeddings = await embedder.embed([query])
    except Exception as exc:
        logger.error("retrieval_embed_failed", error_type=type(exc).__name__, exc_info=exc)
        raise RetrievalFailed() from exc
    if not embeddings:
        raise RetrievalFailed("Embedding provider returned no vector for the query.")
    query_vector = embeddings[0]

    try:
        dense = await _dense_search(db, business_id, query_vector, candidate_k)
        sparse = await _sparse_search(db, business_id, query, candidate_k)
    except Exception as exc:
        logger.error("retrieval_search_failed", error_type=type(exc).__name__, exc_info=exc)
        raise RetrievalFailed() from exc

    by_id: dict[UUID, _Candidate] = {c.chunk_id: c for c in (*dense, *sparse)}
    if not by_id:
        return []

    fused_ids = reciprocal_rank_fusion(
        [[c.chunk_id for c in dense], [c.chunk_id for c in sparse]]
    )
    merged = [by_id[cid] for cid in fused_ids]

    try:
        rerank_scores = await reranker.rerank(query, [c.content for c in merged])
    except Exception as exc:
        logger.error("retrieval_rerank_failed", error_type=type(exc).__name__, exc_info=exc)
        raise RetrievalFailed() from exc

    scored = sorted(
        zip(merged, rerank_scores, strict=True), key=lambda pair: pair[1], reverse=True
    )

    results: list[RetrievedChunk] = []
    for candidate, score in scored[:final_k]:
        if score < settings.retrieval_min_score:
            continue
        results.append(
            RetrievedChunk(
                chunk_id=candidate.chunk_id,
                document_id=candidate.document_id,
                content=candidate.content,
                metadata=candidate.metadata,
                score=float(score),
            )
        )

    logger.info(
        "retrieval_complete",
        business_id=str(business_id),
        dense=len(dense),
        sparse=len(sparse),
        merged=len(merged),
        returned=len(results),
    )
    return results


__all__ = ["Reranker", "reciprocal_rank_fusion", "retrieve"]
