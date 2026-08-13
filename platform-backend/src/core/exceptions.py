"""Typed domain exceptions and their central HTTP mapping.

Route handlers and services raise these instead of generic `Exception` or ad-hoc
`HTTPException`s, so every failure mode is named, documented, and handled in exactly one
place. Per project-conventions: fail closed, never leak internal detail to the client.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.core.logging import get_logger

logger = get_logger(__name__)


class DomainError(Exception):
    """Base for all typed domain exceptions. `status_code` and `client_message` are the
    only things that reach the HTTP layer — never the raw exception detail."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    client_message: str = "Something went wrong. Please try again."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.client_message
        super().__init__(self.detail)


class NotAuthenticated(DomainError):
    status_code = status.HTTP_401_UNAUTHORIZED
    client_message = "Authentication required."


class NotAuthorized(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    client_message = "You do not have access to this resource."


class BusinessSuspended(DomainError):
    """The target business is not active (suspended). Blocks tenant-facing actions that
    consume resources or LLM spend — chat and uploads — while still allowing a super_admin
    to manage the business. Fail-closed: any tenant action on a non-active business denies."""

    status_code = status.HTTP_403_FORBIDDEN
    client_message = "This business is currently suspended."


class ResourceNotFound(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    client_message = "The requested resource was not found."


class RateLimitExceeded(DomainError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    client_message = "Too many requests. Please slow down and try again shortly."


class BudgetExceeded(DomainError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    client_message = "This business has reached its usage budget for today."


class GuardrailBlocked(DomainError):
    """A guardrail (input or output) rejected the request/response. Fail-closed path —
    raised even when the *guardrail itself* errored, never silently passed through."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    client_message = "I can't safely process that request."


class RetrievalFailed(DomainError):
    status_code = status.HTTP_502_BAD_GATEWAY
    client_message = "I'm having trouble accessing the knowledge base right now."


class ProviderUnavailable(DomainError):
    """All configured LLM/embedding providers (primary + fallback) failed."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    client_message = "The assistant is temporarily unavailable. Please try again shortly."


class IngestionFailed(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    client_message = "This document could not be processed."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        logger.warning(
            "domain_error",
            path=request.url.path,
            error_type=type(exc).__name__,
            detail=exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": type(exc).__name__, "message": exc.client_message},
        )

    @app.exception_handler(Exception)
    async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Fail closed: never leak the stack trace or exception detail to the client.
        logger.error(
            "unhandled_error", path=request.url.path, error_type=type(exc).__name__, exc_info=exc
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalError",
                "message": "Something went wrong. Please try again.",
            },
        )
