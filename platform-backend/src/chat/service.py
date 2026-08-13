"""Chat turn orchestration: input guardrails -> agent -> persistence -> SSE stream.

Streaming + verify-before-answer resolution (documented choice): the groundedness gate
needs the *full* draft, but the UI wants token streaming. So we run the agent to produce a
fully verified `AgentResult` first, then stream that already-verified text token-by-token,
followed by a `done` event with citations. Nothing unverified ever leaves the graph, and
the client still gets a streaming UX.

SSE shape emitted (exactly, matching the frontend contract):
    data: {"token": "..."}\\n\\n           (repeated per token)
    data: {"done": true, "citations": [{"doc_id": "...", "title": "..."}],
           "conversation_id": "...", "escalated": false}\\n\\n

`conversation_id` is what makes a multi-turn conversation possible: the client has no other
way to learn the id of a conversation the server created, so without it every turn would
start a fresh thread. `escalated` surfaces `AgentResult.escalated` so the UI can render the
"escalated to a human" state. On a guardrail-blocked turn no conversation is persisted (an
unsafe request must not create tenant state), so `conversation_id` is null there — clients
must keep their existing id rather than overwrite it with null.
"""

import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.graph import AgentResult, run_agent
from src.chat.models import ChatChannel, Conversation, Message, MessageRole
from src.chat.schemas import Citation
from src.core.exceptions import GuardrailBlocked
from src.core.logging import get_logger
from src.documents.models import Document
from src.guardrails.input import screen_input
from src.usage.models import UsageEvent

logger = get_logger(__name__)

# Rough token estimate when the provider doesn't return exact usage: ~4 chars/token is the
# common English heuristic. Documented as an estimate; Stage 8 metrics read tokens_used.
_CHARS_PER_TOKEN = 4

# Type of the agent entry point, injectable so the router/tests can override it.
AgentRunner = Callable[..., Awaitable[AgentResult]]


def _estimate_tokens(*texts: str) -> int:
    return sum(max(1, len(t) // _CHARS_PER_TOKEN) for t in texts if t)


async def get_or_create_conversation(
    db: AsyncSession,
    *,
    business_id: UUID,
    channel: ChatChannel,
    conversation_id: UUID | None,
) -> Conversation:
    """Fetch an existing conversation (validating it belongs to this tenant — fail closed
    on cross-tenant access) or create a new one."""
    if conversation_id is not None:
        conversation = await db.get(Conversation, conversation_id)
        if conversation is None or conversation.business_id != business_id:
            # Don't leak whether the id exists for another tenant; treat as blocked.
            raise GuardrailBlocked("Conversation not found.")
        return conversation
    conversation = Conversation(business_id=business_id, channel=channel)
    db.add(conversation)
    await db.flush()
    return conversation


async def _resolve_titles(db: AsyncSession, doc_ids: list[str]) -> dict[str, str]:
    """Map cited document_ids to human titles for the citations done-event. Missing/invalid
    ids fall back to the id itself so a citation is never dropped."""
    titles: dict[str, str] = {}
    for raw in doc_ids:
        try:
            doc = await db.get(Document, UUID(raw))
        except Exception:  # noqa: BLE001 — a bad/unknown id shouldn't break the turn.
            doc = None
        titles[raw] = (getattr(doc, "filename", None) or raw) if doc else raw
    return titles


def _sse(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def stream_turn(
    db: AsyncSession,
    *,
    business_id: UUID,
    channel: ChatChannel,
    message: str,
    conversation_id: UUID | None,
    agent_runner: AgentRunner | None = None,
) -> AsyncIterator[str]:
    """Run one chat turn and yield SSE frames. Input guardrails run before the agent; the
    verified answer is persisted and its tokens streamed; a UsageEvent is recorded.

    Guardrail failures are surfaced as a normal `done` event carrying a safe message (the
    stream has already started with a 200, so we can't switch to a 4xx mid-stream) — the
    unsafe request never reaches the model."""
    started = time.monotonic()

    # --- Input guardrails (before the agent). Fail closed to a safe streamed message. ---
    try:
        safe_query = screen_input(message)
    except GuardrailBlocked as exc:
        logger.info("chat_input_blocked", business_id=str(business_id), detail=exc.detail)
        yield _sse({"token": exc.client_message})
        # No conversation is created for a blocked turn, so there is no id to hand back.
        yield _sse(
            {"done": True, "citations": [], "conversation_id": None, "escalated": False}
        )
        return

    conversation = await get_or_create_conversation(
        db, business_id=business_id, channel=channel, conversation_id=conversation_id
    )
    db.add(
        Message(conversation_id=conversation.id, role=MessageRole.user, content=safe_query)
    )
    await db.flush()

    # Resolve at call time (not as a default arg) so a test that monkeypatches
    # `src.chat.service.run_agent` is honored — a default bound at import time wouldn't be.
    runner = agent_runner if agent_runner is not None else run_agent
    result = await runner(db, business_id, safe_query)

    citations_payload = await _build_citations(db, result.citations)

    # Persist the assistant message with its citations before streaming it out.
    db.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.assistant,
            content=result.answer,
            citations=[c.model_dump() for c in citations_payload] or None,
        )
    )

    latency_ms = int((time.monotonic() - started) * 1000)
    db.add(
        UsageEvent(
            business_id=business_id,
            event_type="chat_turn",
            # Estimated (len-based heuristic) — providers here don't return exact counts.
            tokens_used=_estimate_tokens(safe_query, result.answer),
            cost_usd=0,
            latency_ms=latency_ms,
        )
    )
    await db.commit()

    # Stream the already-verified answer token-by-token, then the citations done-event.
    for token in _tokenize(result.answer):
        yield _sse({"token": token})
    yield _sse(
        {
            "done": True,
            "citations": [c.model_dump() for c in citations_payload],
            "conversation_id": str(conversation.id),
            "escalated": result.escalated,
        }
    )


async def _build_citations(db: AsyncSession, doc_ids: list[str]) -> list[Citation]:
    titles = await _resolve_titles(db, doc_ids)
    return [Citation(doc_id=d, title=titles.get(d, d)) for d in doc_ids]


def _tokenize(text: str) -> list[str]:
    """Split the verified answer into stream chunks — whitespace-preserving word tokens so
    the client can concatenate them back into the exact answer."""
    out: list[str] = []
    current = ""
    for ch in text:
        current += ch
        if ch == " ":
            out.append(current)
            current = ""
    if current:
        out.append(current)
    return out
