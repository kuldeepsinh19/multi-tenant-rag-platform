"""Classifies which provider-call failures are worth retrying. Per langgraph-agent-standards:
distinguish retryable errors (timeout, 429, transient 5xx) from non-retryable ones (bad
request, auth) — don't burn the retry budget on errors that will never recover."""

import httpx

_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


_RETRYABLE_EXCEPTION_TYPES = (
    TimeoutError,
    ConnectionError,
    httpx.TimeoutException,
    httpx.ConnectError,
)


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, _RETRYABLE_EXCEPTION_TYPES):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    return False
