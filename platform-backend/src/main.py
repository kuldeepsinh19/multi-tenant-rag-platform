import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from src.auth.router import router as auth_router
from src.businesses.router import router as businesses_router
from src.chat.cors import WidgetCORSMiddleware
from src.chat.router import router as chat_router
from src.core.config import get_settings
from src.core.exceptions import register_exception_handlers
from src.core.logging import configure_logging, get_logger, set_correlation_id
from src.core.security_headers import make_security_headers_middleware
from src.documents.router import router as documents_router
from src.observability.middleware import tracing_middleware
from src.ratelimit.middleware import RateLimitMiddleware
from src.usage.router import router as metrics_router

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

# Interactive docs and the OpenAPI schema are exposed in development only — in production
# they publish the entire (auth-gated) API surface to anonymous callers for no benefit.
app = FastAPI(
    title="Platform API",
    version="0.1.0",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

# NOTE ON ORDER: Starlette applies the most-recently-added middleware OUTERMOST, so the
# three registrations below run in reverse: WidgetCORS -> CORS -> RateLimit. That ordering
# is load-bearing.
#
# Rate-limit middleware (owner: ratelimit/): enforced BEFORE chat handlers so abuse costs a
# Redis INCR, not an LLM call, rejecting with a 429 before the request reaches the route.
# Scoped to chat paths only — health/auth/admin/metrics pass through untouched.
# Added FIRST so it sits INSIDE the CORS layers: its 429 JSONResponse short-circuits the
# stack, and if it sat outside CORS that response would carry no Access-Control-Allow-Origin
# and the browser would report an opaque network error instead of the 429.
app.add_middleware(RateLimitMiddleware)

# Dashboard CORS: a static allowlist. Does not (and cannot) cover the widget, whose
# permitted origins live per-key in the database — see WidgetCORSMiddleware below.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.dashboard_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Per-key CORS for /widget/*. Added AFTER CORSMiddleware so it wraps it: Starlette's
# CORSMiddleware answers every preflight it sees and rejects any origin outside its static
# allowlist with a 400, which would kill widget preflights before they could be resolved
# against the key's allowed_domains.
app.add_middleware(WidgetCORSMiddleware)

register_exception_handlers(app)

# Tracing middleware (owner: observability/): records per-request latency to Langfuse when
# configured. Fail-open no-op otherwise.
app.middleware("http")(tracing_middleware)


@app.middleware("http")
async def correlation_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    correlation_id = request.headers.get("x-correlation-id", str(uuid.uuid4()))
    set_correlation_id(correlation_id)
    response = await call_next(request)
    response.headers["x-correlation-id"] = correlation_id
    return response


# Registered LAST so it is the OUTERMOST layer: Starlette applies the most-recently-added
# HTTP middleware first, so this wraps everything (routes, rate-limit 429s, error responses)
# and stamps the security headers on every response that leaves the app.
app.middleware("http")(make_security_headers_middleware(enable_hsts=settings.is_production))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(businesses_router, prefix="/businesses", tags=["businesses"])
app.include_router(documents_router, prefix="/businesses", tags=["documents"])
app.include_router(chat_router, tags=["chat"])
app.include_router(metrics_router, prefix="/businesses", tags=["metrics"])
