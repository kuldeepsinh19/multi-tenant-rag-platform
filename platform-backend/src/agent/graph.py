"""The bounded agent state machine (see langgraph-agent-standards).

Flow:  retrieve -> generate -> verify -> [conditional] -> done | retry | escalate

- Every loop is capped by `max_retries` (from Settings.agent_max_retries), checked by a
  small *pure* routing function `should_retry`.
- `verify` is a separate, narrow groundedness gate (every cited id was actually retrieved)
  — never the same open-ended generation call. No unverified draft can reach END.
- On exhaustion the graph routes to a designed `escalate` node returning a safe answer,
  never a crash and never a hallucinated draft.
- LLM and retrieval are injectable (`retrieve_fn`, `llm`) so the control flow is testable
  without Stage 5 or a live model. External calls are wrapped in timeouts; on error we
  route to escalate rather than raising out of the graph.
"""

import asyncio
import json
from typing import Any, Protocol
from uuid import UUID

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from src.agent.prompts import SAFE_FALLBACK_ANSWER, SYSTEM_PROMPT, build_user_prompt
from src.agent.state import AgentState
from src.core.config import get_settings
from src.core.logging import get_logger
from src.guardrails.input import sanitize_retrieved
from src.guardrails.output import GroundedAnswer, enforce_grounded
from src.llm.base import ChatMessage, LLMProvider
from src.retrieval.schemas import RetrievedChunk

logger = get_logger(__name__)

# Hard wall-clock caps so a hung provider/retriever times out and routes to escalate
# instead of hanging the request.
_RETRIEVE_TIMEOUT_S = 30.0
_GENERATE_TIMEOUT_S = 90.0

_JSON_INSTRUCTION = (
    "\n\nReturn ONLY a JSON object of the form "
    '{"answer": "<your answer>", "citations": ["<document id>", ...]}. '
    "No prose outside the JSON."
)


class RetrieveFn(Protocol):
    async def __call__(
        self, db: Any, business_id: UUID, query: str, *, top_k: int | None = ...
    ) -> list[RetrievedChunk]: ...


def _parse_grounded_answer(raw: str) -> GroundedAnswer | None:
    """Best-effort structured-output parse. We instruct the model to emit JSON and validate
    it into `GroundedAnswer` (the Instructor role: force a typed schema, fail loudly on
    malformed output). Returns None if the output can't be coerced — the caller treats that
    as an ungrounded draft and retries/escalates, never a silent pass-through."""
    text = raw.strip()
    # Strip a ```json fence if the model wrapped the object in one.
    if text.startswith("```"):
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text.strip("`")
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    try:
        return GroundedAnswer.model_validate(data)
    except ValidationError:
        return None


def build_agent_graph(retrieve_fn: RetrieveFn, llm: LLMProvider, db: Any) -> Any:
    """Compile the LangGraph app, closing over the injected retriever/llm/db so the nodes
    themselves stay small and stateless."""

    async def retrieve_node(state: AgentState) -> dict[str, Any]:
        try:
            async with asyncio.timeout(_RETRIEVE_TIMEOUT_S):
                chunks = await retrieve_fn(db, state["tenant_id"], state["query"])
        except Exception:  # noqa: BLE001 — any retrieval failure (incl. timeout) routes to
            # escalate via the empty-context path, never crashes the graph.
            logger.warning("agent_retrieve_failed", exc_info=True)
            chunks = []
        # Retrieved content is untrusted data — sanitise before it enters the prompt.
        safe_chunks = [
            chunk.model_copy(update={"content": sanitize_retrieved(chunk.content)})
            for chunk in chunks
        ]
        return {
            "retrieved": safe_chunks,
            "retrieved_ids": {c.citation_id() for c in safe_chunks},
        }

    async def generate_node(state: AgentState) -> dict[str, Any]:
        chunks = state.get("retrieved", [])
        if not chunks:
            # Nothing to ground on — don't spend a big generation, go straight to escalate.
            return {"draft": None}
        messages = [
            ChatMessage(role="system", content=SYSTEM_PROMPT + _JSON_INSTRUCTION),
            ChatMessage(role="user", content=build_user_prompt(state["query"], chunks)),
        ]
        try:
            async with asyncio.timeout(_GENERATE_TIMEOUT_S):
                raw = await llm.chat(messages)
        except Exception:  # noqa: BLE001 — provider failure (incl. timeout) -> escalate.
            logger.warning("agent_generate_failed", exc_info=True)
            return {"draft": None}
        return {"draft": _parse_grounded_answer(raw)}

    def verify_node(state: AgentState) -> dict[str, Any]:
        """Narrow groundedness gate — NOT another generation call. A draft is verified iff
        it is well-formed and every cited id was actually retrieved."""
        draft = state.get("draft")
        verified = draft is not None and enforce_grounded(draft, state.get("retrieved_ids", set()))
        return {
            "verified": verified,
            "retry_count": state.get("retry_count", 0) + (0 if verified else 1),
        }

    def escalate_node(state: AgentState) -> dict[str, Any]:
        logger.info(
            "agent_escalated",
            tenant_id=str(state.get("tenant_id")),
            retry_count=state.get("retry_count"),
        )
        return {
            "draft": GroundedAnswer(answer=SAFE_FALLBACK_ANSWER, citations=[]),
            "escalated": True,
            "verified": False,
        }

    graph: StateGraph[AgentState] = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_node("verify", verify_node)
    graph.add_node("escalate", escalate_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "verify")
    graph.add_conditional_edges(
        "verify",
        should_retry,
        {"done": END, "retry": "retrieve", "escalate": "escalate"},
    )
    graph.add_edge("escalate", END)
    return graph.compile()


def should_retry(state: AgentState) -> str:
    """Pure routing function — deterministic control flow (see langgraph-agent-standards).
    verified -> done; retries exhausted -> escalate (designed exit); else -> retry."""
    if state.get("verified"):
        return "done"
    if state.get("retry_count", 0) >= state.get("max_retries", 0):
        return "escalate"
    return "retry"


class AgentResult(GroundedAnswer):
    """What `run_agent` returns: a grounded answer plus whether it was escalated (so the
    chat layer can flag/handle escalation) — a superset of GroundedAnswer."""

    escalated: bool = False


async def run_agent(
    db: Any,
    business_id: UUID,
    query: str,
    *,
    retrieve_fn: RetrieveFn | None = None,
    llm: LLMProvider | None = None,
    max_retries: int | None = None,
) -> AgentResult:
    """Entry point. `retrieve_fn` and `llm` default to the real ones but are injectable so
    tests need neither Stage 5 nor a live model. Always returns a verified grounded answer
    or the safe escalation fallback — never raises for a generation/retrieval failure."""
    if retrieve_fn is None:
        from src.retrieval.service import retrieve as _retrieve

        retrieve_fn = _retrieve
    if llm is None:
        from src.llm.registry import get_llm

        llm = get_llm()
    if max_retries is None:
        max_retries = get_settings().agent_max_retries

    app = build_agent_graph(retrieve_fn, llm, db)
    initial: AgentState = {
        "tenant_id": business_id,
        "query": query,
        "retry_count": 0,
        "max_retries": max_retries,
        "verified": False,
        "escalated": False,
    }
    final: AgentState = await app.ainvoke(initial)

    draft = final.get("draft")
    if draft is None or not final.get("verified"):
        # Belt-and-suspenders: nothing unverified escapes even if a node misbehaved.
        return AgentResult(answer=SAFE_FALLBACK_ANSWER, citations=[], escalated=True)
    return AgentResult(
        answer=draft.answer,
        citations=draft.citations,
        escalated=bool(final.get("escalated")),
    )
