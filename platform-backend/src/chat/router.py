"""Chat endpoints. Both stream Server-Sent Events; both apply input guardrails before the
agent and derive tenant scope from the authenticated principal (never the body).

- POST /chat        dashboard, JWT (require_business_admin), business_id from the JWT.
- POST /widget/chat public, no JWT, auth via X-Widget-Key + Origin allowlist.

Handlers stay thin: authenticate -> derive business_id -> hand off to the service, which
runs guardrails, the agent, persistence and the SSE generator.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_business_id
from src.businesses.service import ensure_business_active
from src.chat.dependencies import authenticate_widget, origin_header, widget_key_header
from src.chat.models import ChatChannel
from src.chat.schemas import ChatRequest
from src.chat.service import stream_turn
from src.core.db import get_db
from src.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.post("/chat")
async def dashboard_chat(
    payload: ChatRequest,
    business_id: UUID = Depends(get_current_business_id),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    # A suspended tenant may not spend on LLM calls, even with a valid admin JWT.
    await ensure_business_active(db, business_id)
    stream = stream_turn(
        db,
        business_id=business_id,
        channel=ChatChannel.dashboard,
        message=payload.message,
        conversation_id=payload.conversation_id,
    )
    return StreamingResponse(stream, media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/widget/chat")
async def widget_chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    widget_key: str | None = Depends(widget_key_header),
    origin: str | None = Depends(origin_header),
) -> StreamingResponse:
    # Fail closed: invalid key -> 401, disallowed origin -> 403 (raised before streaming).
    key = await authenticate_widget(db, widget_key=widget_key, origin=origin)
    # A suspended tenant's widget stops answering (and stops spending), even with a live key.
    await ensure_business_active(db, key.business_id)
    stream = stream_turn(
        db,
        business_id=key.business_id,
        channel=ChatChannel.widget,
        message=payload.message,
        conversation_id=payload.conversation_id,
    )
    return StreamingResponse(stream, media_type="text/event-stream", headers=_SSE_HEADERS)
