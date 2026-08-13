"""CORS for the public widget endpoint.

The dashboard's CORS is a static allowlist (`settings.dashboard_origins`). The widget's
cannot be: it is embedded on arbitrary customer domains, and the set of permitted origins
lives in each `WidgetKey.allowed_domains` row. Without this middleware the browser blocks
every `/widget/chat` response for lack of `Access-Control-Allow-Origin`, so the widget is
authorised correctly server-side and then discarded client-side.

Why this cannot reuse the key lookup in `chat/dependencies.py`: the widget authenticates
with a custom `X-Widget-Key` header, which forces a CORS preflight, and browsers do not
send custom headers on preflight. The permitted origin therefore has to be resolvable from
the `Origin` header alone — so we ask "does ANY active widget key allow this origin?".
That is strictly weaker than the per-key check, which is fine: this decides only whether
the browser may read the response. `authenticate_widget` still runs on the real request and
is what enforces the key/origin pairing and the tenancy boundary.

Fails closed: an unknown origin, or a database error while resolving one, yields no CORS
headers (and a 403 on preflight), so the browser refuses the exchange.

No `Access-Control-Allow-Credentials` is sent — widget auth is a header, not a cookie, so
the widget never needs credentialed requests and enabling them would only widen exposure.
"""

from __future__ import annotations

from sqlalchemy import select
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.businesses.models import WidgetKey
from src.chat.dependencies import origin_allowed
from src.core.db import async_session_factory
from src.core.logging import get_logger

logger = get_logger(__name__)

_WIDGET_PATH_PREFIX = "/widget/"
_ALLOW_METHODS = "POST, OPTIONS"
_ALLOW_HEADERS = "Content-Type, X-Widget-Key, X-Correlation-Id"
_EXPOSE_HEADERS = "X-Correlation-Id"
# Preflight results are cacheable, which keeps the per-origin lookup off the hot path.
_MAX_AGE = "600"


async def origin_allowed_for_any_active_key(origin: str) -> bool:
    """True when some active widget key allowlists `origin`. Fails closed on DB error."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(WidgetKey.allowed_domains).where(WidgetKey.is_active.is_(True))
            )
            return any(origin_allowed(origin, list(domains or [])) for (domains,) in result.all())
    except Exception:
        # Never surface a 500 from a CORS decision — deny and let the browser report it.
        logger.exception("widget_cors_lookup_failed", extra={"origin": origin})
        return False


def _apply_cors_headers(headers: MutableHeaders, origin: str) -> None:
    headers["access-control-allow-origin"] = origin
    headers["access-control-expose-headers"] = _EXPOSE_HEADERS
    # The reply differs per Origin, so caches must key on it.
    existing_vary = headers.get("vary")
    if existing_vary is None:
        headers["vary"] = "Origin"
    elif "origin" not in existing_vary.lower():
        headers["vary"] = f"{existing_vary}, Origin"


def _preflight_response(origin: str) -> Response:
    response = Response(status_code=204)
    _apply_cors_headers(response.headers, origin)
    response.headers["access-control-allow-methods"] = _ALLOW_METHODS
    response.headers["access-control-allow-headers"] = _ALLOW_HEADERS
    response.headers["access-control-max-age"] = _MAX_AGE
    return response


class WidgetCORSMiddleware:
    """Per-key CORS for `/widget/*`. Must be registered OUTSIDE `CORSMiddleware`: Starlette's
    CORSMiddleware answers every preflight it sees and rejects origins outside its static
    allowlist with a 400, which would kill widget preflights before they reach us."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        origin = request.headers.get("origin")
        if origin is None or not request.url.path.startswith(_WIDGET_PATH_PREFIX):
            await self.app(scope, receive, send)
            return

        is_preflight = (
            request.method == "OPTIONS" and "access-control-request-method" in request.headers
        )
        allowed = await origin_allowed_for_any_active_key(origin)

        if is_preflight:
            response: Response = (
                _preflight_response(origin)
                if allowed
                else PlainTextResponse("Disallowed CORS origin", status_code=403)
            )
            await response(scope, receive, send)
            return

        if not allowed:
            # Let the request run — `authenticate_widget` will reject it on its own terms —
            # but emit no CORS headers, so a browser cannot read the reply.
            await self.app(scope, receive, send)
            return

        await self.app(scope, receive, _cors_sender(send, origin))


def _cors_sender(send: Send, origin: str) -> Send:
    async def send_with_cors(message: Message) -> None:
        if message["type"] == "http.response.start":
            _apply_cors_headers(MutableHeaders(scope=message), origin)
        await send(message)

    return send_with_cors
