"""The retrieval layer's public contract — the stable interface between hybrid retrieval
(src/retrieval/service.py) and the agent that consumes it (src/agent/). A retrieved chunk
carries its provenance (document_id, metadata) all the way through so the generation layer
can cite it and the guardrail layer can verify groundedness against it. See
rag-retrieval-standards: provenance must never be dropped in retrieval."""

from uuid import UUID

from pydantic import BaseModel


class RetrievedChunk(BaseModel):
    chunk_id: UUID
    document_id: UUID
    content: str
    metadata: dict[str, object]
    # Final relevance score after hybrid merge + reranking; higher is more relevant.
    score: float

    def citation_id(self) -> str:
        """Short, stable id the model cites (e.g. `[doc_id]`) and the groundedness gate
        checks against the set of actually-retrieved documents."""
        return str(self.document_id)
