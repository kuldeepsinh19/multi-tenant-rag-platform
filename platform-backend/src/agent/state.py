"""The agent's typed state (see langgraph-agent-standards): every field the graph reads or
writes, including the control fields `retry_count`, `max_retries`, `verified` that make the
loop bounded and observable. No hidden globals — nodes read and return this dict."""

from uuid import UUID

from typing_extensions import TypedDict

from src.guardrails.output import GroundedAnswer
from src.retrieval.schemas import RetrievedChunk


class AgentState(TypedDict, total=False):
    # --- inputs (set once at entry) ---
    tenant_id: UUID
    query: str

    # --- working data (written by nodes) ---
    retrieved: list[RetrievedChunk]
    retrieved_ids: set[str]
    draft: GroundedAnswer | None

    # --- control fields (the bounded-loop machinery) ---
    retry_count: int
    max_retries: int
    verified: bool
    escalated: bool
