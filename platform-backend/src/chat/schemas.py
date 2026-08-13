"""Request/response contracts for the chat endpoints. Every body is a Pydantic v2 model —
the first, cheapest guardrail (size/shape) at the API boundary. Note: neither body carries
a `business_id`; tenant scope is derived from the JWT (dashboard) or the widget key
(widget), never trusted from the client."""

from uuid import UUID

from pydantic import BaseModel, Field

from src.guardrails.input import MAX_INPUT_CHARS


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS)
    conversation_id: UUID | None = None


class Citation(BaseModel):
    doc_id: str
    title: str
