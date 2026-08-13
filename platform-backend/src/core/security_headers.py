"""Security response headers applied to every response.

This is a JSON API consumed cross-origin by the SPA and by the embeddable widget, so the
headers here are the API-appropriate hardening baseline (OWASP Secure Headers): stop MIME
sniffing, forbid framing/clickjacking, minimise referrer leakage, lock down what a response
document is allowed to do, and — behind TLS in production — pin HTTPS with HSTS.

Interactive docs (`/docs`, `/redoc`, `/openapi.json`) are exempted from the restrictive
`Content-Security-Policy`: Swagger/ReDoc are HTML+inline-script pages that a `default-src
'none'` policy would break. Those routes are disabled entirely outside development anyway
(see `src/main.py`), so the exemption never applies in production.
"""

from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

# A locked-down CSP for API/JSON responses. `default-src 'none'` means a response rendered
# as a document can load nothing; `frame-ancestors 'none'` blocks framing even where
# X-Frame-Options is ignored; `base-uri`/`form-action 'none'` close off base-tag and form
# hijacking. Harmless on JSON, valuable on any HTML error page the stack might emit.
_API_CSP = (
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)

# Paths whose HTML needs a permissive CSP (dev-only; disabled in production).
_CSP_EXEMPT_PREFIXES = ("/docs", "/redoc", "/openapi.json")

_BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
}


def _is_csp_exempt(path: str) -> bool:
    return any(path == p or path.startswith(p) for p in _CSP_EXEMPT_PREFIXES)


def make_security_headers_middleware(
    *, enable_hsts: bool
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    """Build the security-headers HTTP middleware.

    `enable_hsts` should be True only in production (behind TLS): sending HSTS over plain
    HTTP is ignored by browsers, but pinning it in local dev can wedge a developer's browser
    onto https://localhost, so it is gated on the environment rather than always-on.
    """

    async def security_headers_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for header, value in _BASE_HEADERS.items():
            response.headers.setdefault(header, value)
        if not _is_csp_exempt(request.url.path):
            response.headers.setdefault("Content-Security-Policy", _API_CSP)
        if enable_hsts:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response

    return security_headers_middleware
