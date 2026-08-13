"""Agent control-flow tests. All deterministic: injected fake retrieve_fn + fake llm, no
Stage 5 and no live model. Proves (1) the routing function is pure & bounded, (2) the happy
path produces a grounded cited answer, (3) ungrounded output exhausts retries and escalates
to the safe fallback — no unverified answer ever escapes."""

import json
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.agent.graph import run_agent, should_retry
from src.agent.prompts import SAFE_FALLBACK_ANSWER
from src.agent.state import AgentState
from src.llm.base import ChatMessage

# --- Fakes -----------------------------------------------------------------------------


class _Chunk:
    """Minimal RetrievedChunk-compatible stand-in (real schema is a Pydantic model, but we
    build real ones below; this docstring documents the injection point)."""


def _make_chunks(doc_id: UUID, content: str) -> list[Any]:
    from src.retrieval.schemas import RetrievedChunk

    return [
        RetrievedChunk(
            chunk_id=uuid4(),
            document_id=doc_id,
            content=content,
            metadata={},
            score=0.9,
        )
    ]


class FakeGroundedLLM:
    """Always cites the id it was told to (grounded happy path)."""

    def __init__(self, doc_id: str) -> None:
        self._doc_id = doc_id

    async def chat(self, messages: list[ChatMessage], **kwargs: Any) -> str:
        return json.dumps({"answer": "Refunds take 30 days.", "citations": [self._doc_id]})

    def stream(self, messages: list[ChatMessage], **kwargs: Any) -> Any: ...


class FakeUngroundedLLM:
    """Always cites an id that was never retrieved (fails the groundedness gate)."""

    async def chat(self, messages: list[ChatMessage], **kwargs: Any) -> str:
        return json.dumps({"answer": "I made this up.", "citations": ["ghost-doc"]})

    def stream(self, messages: list[ChatMessage], **kwargs: Any) -> Any: ...


def _make_retrieve_fn(doc_id: UUID, content: str) -> Any:
    async def _retrieve(
        db: Any, business_id: UUID, query: str, *, top_k: int | None = None
    ) -> list[Any]:
        return _make_chunks(doc_id, content)

    return _retrieve


# --- Routing purity --------------------------------------------------------------------


def test_should_retry_done_when_verified() -> None:
    state: AgentState = {"verified": True, "retry_count": 0, "max_retries": 2}
    assert should_retry(state) == "done"


def test_should_retry_escalate_when_exhausted() -> None:
    state: AgentState = {"verified": False, "retry_count": 2, "max_retries": 2}
    assert should_retry(state) == "escalate"


def test_should_retry_retry_otherwise() -> None:
    state: AgentState = {"verified": False, "retry_count": 1, "max_retries": 2}
    assert should_retry(state) == "retry"


# --- Full-graph behaviour --------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_happy_path_grounded_and_cited() -> None:
    doc_id = uuid4()
    result = await run_agent(
        db=None,
        business_id=uuid4(),
        query="How long do refunds take?",
        retrieve_fn=_make_retrieve_fn(doc_id, "Refunds take 30 days."),
        llm=FakeGroundedLLM(str(doc_id)),
        max_retries=2,
    )
    assert result.answer == "Refunds take 30 days."
    assert result.citations == [str(doc_id)]
    assert result.escalated is False


@pytest.mark.asyncio
async def test_run_agent_escalates_when_output_never_grounded() -> None:
    doc_id = uuid4()
    result = await run_agent(
        db=None,
        business_id=uuid4(),
        query="anything",
        retrieve_fn=_make_retrieve_fn(doc_id, "Some real content."),
        llm=FakeUngroundedLLM(),
        max_retries=2,
    )
    # No unverified/ungrounded answer escapes: we get the safe fallback, escalated.
    assert result.answer == SAFE_FALLBACK_ANSWER
    assert result.citations == []
    assert result.escalated is True


@pytest.mark.asyncio
async def test_run_agent_escalates_when_no_context_retrieved() -> None:
    async def _empty_retrieve(
        db: Any, business_id: UUID, query: str, *, top_k: int | None = None
    ) -> list[Any]:
        return []

    result = await run_agent(
        db=None,
        business_id=uuid4(),
        query="anything",
        retrieve_fn=_empty_retrieve,
        llm=FakeGroundedLLM("unused"),
        max_retries=2,
    )
    assert result.answer == SAFE_FALLBACK_ANSWER
    assert result.escalated is True
