"""Widget authentication — the public widget endpoint has NO JWT. Auth is an active
`WidgetKey` looked up by the `X-Widget-Key` header, and the request `Origin` must be in the
key's domain allowlist. Fails closed: missing/inactive key -> 401, disallowed origin ->
403. business_id is derived from the key, never from the client body (tenancy boundary)."""

from urllib.parse import urlparse

from fastapi import Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.businesses.models import WidgetKey
from src.core.exceptions import NotAuthenticated, NotAuthorized


def _normalize_origin(origin: str) -> str:
    """Reduce an Origin/host to a bare hostname for allowlist comparison, so an allowlist
    of `example.com` matches an `Origin: https://example.com` header."""
    candidate = origin.strip().lower()
    if "://" in candidate:
        candidate = urlparse(candidate).netloc
    # Drop any port and userinfo.
    candidate = candidate.split("@")[-1].split(":")[0]
    return candidate


def _origin_allowed(origin: str | None, allowed_domains: list[str]) -> bool:
    # A configured-but-empty allowlist means "no domains permitted" — fail closed.
    if not allowed_domains:
        return False
    if origin is None:
        return False
    host = _normalize_origin(origin)
    return any(host == _normalize_origin(d) for d in allowed_domains)


async def authenticate_widget(
    db: AsyncSession,
    *,
    widget_key: str | None,
    origin: str | None,
) -> WidgetKey:
    """Resolve and authorise a widget request. Returns the active WidgetKey or raises."""
    if not widget_key:
        raise NotAuthenticated("Missing widget key.")
    result = await db.execute(
        select(WidgetKey).where(
            WidgetKey.public_key == widget_key, WidgetKey.is_active.is_(True)
        )
    )
    key = result.scalar_one_or_none()
    if key is None:
        raise NotAuthenticated("Invalid or inactive widget key.")
    if not _origin_allowed(origin, key.allowed_domains):
        raise NotAuthorized("Origin not permitted for this widget key.")
    return key


# FastAPI header declarations reused by the router so the OpenAPI docs show them.
def widget_key_header(x_widget_key: str | None = Header(default=None)) -> str | None:
    return x_widget_key


def origin_header(origin: str | None = Header(default=None)) -> str | None:
    return origin
