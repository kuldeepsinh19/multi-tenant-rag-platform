"""Output guardrails — everything that screens what leaves the model.

The structured-output schema (`GroundedAnswer`) plus the groundedness gate
(`citations_are_real`) and citation enforcement (`enforce_grounded`). Per
llm-guardrails-standards these are the *guarantee* that the prompt only *requests*: no
claim without a citation, and every citation must correspond to a chunk that was actually
retrieved. Fail closed — an ungrounded answer is rejected, not shown.
"""

from pydantic import BaseModel, Field, field_validator

from src.core.exceptions import GuardrailBlocked

# Sentinel the model emits (per the system prompt) when the context can't answer the
# question. An honest fallback carries no citations, so it is exempt from the "must cite"
# rule — but it is also never presented as a grounded answer.
INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class GroundedAnswer(BaseModel):
    """The structured answer Instructor forces the model to produce. `citations` are the
    document_ids (RetrievedChunk.citation_id()) the answer relies on."""

    answer: str = Field(..., min_length=1)
    citations: list[str] = Field(default_factory=list)

    @field_validator("citations")
    @classmethod
    def _dedup(cls, v: list[str]) -> list[str]:
        # Order-preserving de-dup; the model sometimes repeats a citation.
        seen: set[str] = set()
        out: list[str] = []
        for c in v:
            if c and c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def is_insufficient(self) -> bool:
        return self.answer.strip() == INSUFFICIENT_CONTEXT


def citations_are_real(answer: GroundedAnswer, retrieved_ids: set[str]) -> bool:
    """The cheap groundedness gate: every cited id must be in the retrieved set.

    Empty citations are *not* real grounding — a substantive answer with no citation fails
    this gate (caught by `enforce_grounded` as a citation-enforcement failure)."""
    if not answer.citations:
        return False
    return all(c in retrieved_ids for c in answer.citations)


def enforce_grounded(answer: GroundedAnswer, retrieved_ids: set[str]) -> bool:
    """Full output gate combining citation enforcement + groundedness.

    Returns True iff the answer may leave the system as a grounded answer. An honest
    ``INSUFFICIENT_CONTEXT`` fallback returns False here (it is not a grounded answer) so
    the caller routes it to the safe-fallback path rather than presenting it with
    citations. Any *malformed* state (a fabricated citation) also returns False so the
    caller retries or escalates — never a silent pass-through.
    """
    if answer.is_insufficient():
        return False
    return citations_are_real(answer, retrieved_ids)


def assert_grounded(answer: GroundedAnswer, retrieved_ids: set[str]) -> None:
    """Fail-closed variant for call sites that want an exception, not a bool."""
    if not enforce_grounded(answer, retrieved_ids):
        raise GuardrailBlocked("Answer failed the groundedness / citation check.")
