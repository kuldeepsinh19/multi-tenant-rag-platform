"""Pure helpers inside the rate-limit middleware.

Two of these carry real risk. `_is_chat_path` decides whether a request is metered at all —
a prefix bug that stops matching `/chat` silently disables rate limiting on the only
expensive endpoint. `_mask_secret` is what keeps the widget public key out of the logs; it
is the sole bearer credential for `/widget/chat`, and logs have a wider audience than the
app. `_business_id_from_jwt` must fail *soft* (None) rather than raise, because the real 401
is the handler's auth dependency's job, not the limiter's.

No app or Redis is needed — the helpers only read a headers mapping and a client host.
tests/ratelimit/test_middleware.py covers the middleware end-to-end against real Redis."""

from typing import Any
from uuid import uuid4

import pytest

from src.auth.models import UserRole
from src.auth.security import create_access_token
from src.ratelimit.middleware import (
    _business_id_from_jwt,
    _client_ip,
    _is_chat_path,
    _mask_secret,
)


class _FakeClient:
    def __init__(self, host: str) -> None:
        self.host = host


class _FakeRequest:
    """Minimal stand-in — the helpers only touch `.headers` and `.client`."""

    def __init__(
        self, headers: dict[str, str] | None = None, client_host: str | None = None
    ) -> None:
        self.headers = headers or {}
        self.client = _FakeClient(client_host) if client_host is not None else None


def _request(**kwargs: Any) -> Any:
    return _FakeRequest(**kwargs)


@pytest.mark.parametrize("path", ["/chat", "/widget/chat", "/chat/", "/widget/chat/"])
def test_metered_paths_are_recognised(path: str) -> None:
    assert _is_chat_path(path) is True


@pytest.mark.parametrize(
    "path",
    ["/health", "/auth/login", "/businesses", "/businesses/abc/documents", "/", "/chatter"],
)
def test_unmetered_paths_are_not_rate_limited(path: str) -> None:
    # "/chatter" is the important one: a naive startswith("/chat") would meter it.
    assert _is_chat_path(path) is False


def test_client_ip_reads_the_connection_host() -> None:
    assert _client_ip(_request(client_host="203.0.113.7")) == "203.0.113.7"


def test_client_ip_falls_back_when_the_connection_has_no_client() -> None:
    # ASGI allows a null client (e.g. in-process transports); the limiter must
    # still produce a usable bucket key rather than crash the request.
    assert _client_ip(_request()) == "unknown"


def test_mask_secret_does_not_reveal_the_full_value() -> None:
    secret = "pk_live_abcdefghijklmnopqrstuvwxyz"

    masked = _mask_secret(secret)

    assert secret not in masked


def test_mask_secret_keeps_a_short_prefix_for_correlation() -> None:
    masked = _mask_secret("pk_live_abcdefghijklmnop")

    assert masked.startswith("pk_liv")


def test_mask_secret_reveals_no_more_than_six_characters() -> None:
    secret = "abcdefghijklmnopqrstuvwxyz"

    masked = _mask_secret(secret)

    assert "abcdefg" not in masked


def test_mask_secret_records_the_length_for_debugging() -> None:
    masked = _mask_secret("x" * 42)

    assert "42 chars" in masked


def test_mask_secret_handles_a_short_value_without_raising() -> None:
    assert "abc" not in _mask_secret("abc") or _mask_secret("abc").startswith("abc")


def test_business_id_from_jwt_extracts_the_tenant_claim() -> None:
    business_id = uuid4()
    token = create_access_token(uuid4(), UserRole.business_admin, business_id)

    extracted = _business_id_from_jwt(
        _request(headers={"authorization": f"Bearer {token}"})
    )

    assert extracted == business_id


def test_business_id_from_jwt_accepts_a_lowercase_scheme() -> None:
    business_id = uuid4()
    token = create_access_token(uuid4(), UserRole.business_admin, business_id)

    assert _business_id_from_jwt(_request(headers={"authorization": f"bearer {token}"})) == (
        business_id
    )


def test_business_id_from_jwt_is_none_for_a_super_admin() -> None:
    # Super-admins are unscoped, so they fall through to the next identity
    # source (client IP) rather than sharing one global bucket.
    token = create_access_token(uuid4(), UserRole.super_admin, None)

    assert _business_id_from_jwt(_request(headers={"authorization": f"Bearer {token}"})) is None


def test_business_id_from_jwt_is_none_when_the_header_is_absent() -> None:
    assert _business_id_from_jwt(_request()) is None


@pytest.mark.parametrize(
    "header",
    ["", "Bearer", "Bearer ", "Basic dXNlcjpwYXNz", "Bearer not-a-jwt", "Bearer a.b.c"],
)
def test_business_id_from_jwt_fails_soft_on_a_bad_header(header: str) -> None:
    # Must return None, never raise: the limiter runs before auth, and an
    # exception here would turn a 401 into a 500.
    assert _business_id_from_jwt(_request(headers={"authorization": header})) is None


def test_business_id_from_jwt_rejects_a_token_signed_with_another_secret() -> None:
    from jose import jwt as jose_jwt

    forged = jose_jwt.encode(
        {"sub": str(uuid4()), "role": "business_admin", "business_id": str(uuid4())},
        "not-the-real-secret-not-the-real-secret",
        algorithm="HS256",
    )

    assert _business_id_from_jwt(_request(headers={"authorization": f"Bearer {forged}"})) is None
