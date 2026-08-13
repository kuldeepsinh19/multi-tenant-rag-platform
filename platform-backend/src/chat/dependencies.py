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

# Loopback hosts are the one place a plaintext origin is accepted for a bare-domain
# allowlist entry, so local development against http://localhost keeps working.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]"})


def _split_origin(value: str) -> tuple[str | None, str]:
    """Split an Origin header or an allowlist entry into `(scheme, host)`.

    `scheme` is None when the value carries no explicit scheme (a bare-domain allowlist
    entry such as `example.com`). The host keeps IPv6 brackets but drops userinfo and port.
    """
    candidate = value.strip().lower()
    scheme: str | None = None
    if "://" in candidate:
        parsed = urlparse(candidate)
        scheme = parsed.scheme or None
        candidate = parsed.netloc
    candidate = candidate.split("@")[-1]
    if candidate.startswith("["):
        # IPv6 literal: keep the bracketed host, discard any `:port` that follows it.
        closing = candidate.find("]")
        host = candidate[: closing + 1] if closing != -1 else candidate
    else:
        host = candidate.split(":")[0]
    return scheme, host


def _entry_matches(origin_scheme: str, origin_host: str, entry: str) -> bool:
    entry_scheme, entry_host = _split_origin(entry)
    if not entry_host or entry_host != origin_host:
        return False
    if entry_scheme is not None:
        # An entry that names a scheme is honoured exactly — `https://x` never matches
        # `http://x`.
        return origin_scheme == entry_scheme
    # A bare-domain entry means "this host over TLS". Without this the allowlist would
    # silently accept the plaintext origin too, letting an injected/SSL-stripped page on
    # the customer's domain drive the widget key.
    return origin_scheme == "https" or origin_host in _LOCAL_HOSTS


def origin_allowed(origin: str | None, allowed_domains: list[str]) -> bool:
    # A configured-but-empty allowlist means "no domains permitted" — fail closed.
    if not allowed_domains:
        return False
    if origin is None:
        return False
    candidate = origin.strip().lower()
    # A real browser Origin is always `scheme://host`. `null` (sandboxed iframe, file://,
    # some redirects) and any scheme-less value are opaque — they identify no domain we
    # could have allowlisted, so they are rejected rather than normalised into a match.
    if candidate == "null" or "://" not in candidate:
        return False
    origin_scheme, origin_host = _split_origin(candidate)
    if origin_scheme is None or not origin_host:
        return False
    return any(_entry_matches(origin_scheme, origin_host, d) for d in allowed_domains)


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
    if not origin_allowed(origin, key.allowed_domains):
        raise NotAuthorized("Origin not permitted for this widget key.")
    return key


# FastAPI header declarations reused by the router so the OpenAPI docs show them.
def widget_key_header(x_widget_key: str | None = Header(default=None)) -> str | None:
    return x_widget_key


def origin_header(origin: str | None = Header(default=None)) -> str | None:
    return origin
