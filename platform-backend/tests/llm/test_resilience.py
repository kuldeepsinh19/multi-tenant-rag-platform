import httpx

from src.llm.resilience import is_retryable


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "http://example.test")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


def test_timeouts_and_connection_errors_are_retryable() -> None:
    assert is_retryable(TimeoutError())
    assert is_retryable(ConnectionError())
    assert is_retryable(httpx.ConnectError("connect failed"))
    assert is_retryable(httpx.TimeoutException("timed out"))


def test_transient_http_status_codes_are_retryable() -> None:
    for status_code in (408, 429, 500, 502, 503, 504):
        assert is_retryable(_http_status_error(status_code))


def test_client_errors_are_not_retryable() -> None:
    assert not is_retryable(_http_status_error(401))
    assert not is_retryable(_http_status_error(404))
    assert not is_retryable(ValueError("bad request"))
