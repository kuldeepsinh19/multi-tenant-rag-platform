"""Origin allowlisting is the only thing standing between a tenant's widget key and any
site that scrapes it out of a public page — the key travels in client-side HTML, so it is
not a secret and the Origin check is the real boundary. These are pure-function tests over
`_normalize_origin` / `_origin_allowed`; the HTTP-level widget auth path is covered in
tests/chat/test_chat.py. Every fail-closed branch is asserted explicitly, because a
regression that turns a deny into an allow is silent."""

import pytest

from src.chat.dependencies import _normalize_origin, _origin_allowed


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.com", "example.com"),
        ("https://example.com", "example.com"),
        ("http://example.com", "example.com"),
        ("https://example.com:8443", "example.com"),
        ("https://user:pass@example.com", "example.com"),
        ("https://user:pass@example.com:8443", "example.com"),
        ("HTTPS://EXAMPLE.COM", "example.com"),
        ("  https://example.com  ", "example.com"),
        ("example.com:3000", "example.com"),
        ("https://shop.example.com", "shop.example.com"),
    ],
)
def test_normalize_origin_reduces_to_a_bare_hostname(raw: str, expected: str) -> None:
    assert _normalize_origin(raw) == expected


def test_normalize_origin_is_idempotent() -> None:
    once = _normalize_origin("https://Example.com:8443")
    assert _normalize_origin(once) == once


def test_origin_allowed_matches_a_configured_domain() -> None:
    assert _origin_allowed("https://example.com", ["example.com"]) is True


def test_origin_allowed_ignores_scheme_port_and_case() -> None:
    assert _origin_allowed("HTTPS://Example.com:8443", ["example.com"]) is True


def test_origin_allowed_matches_a_domain_stored_with_a_scheme() -> None:
    # Admins paste whole URLs into the allowlist field; both sides are normalized.
    assert _origin_allowed("https://example.com", ["https://example.com"]) is True


def test_origin_allowed_matches_any_entry_in_a_multi_domain_allowlist() -> None:
    allowed = ["first.test", "example.com", "third.test"]
    assert _origin_allowed("https://example.com", allowed) is True


def test_origin_allowed_rejects_a_domain_not_on_the_list() -> None:
    assert _origin_allowed("https://evil.test", ["example.com"]) is False


def test_origin_allowed_rejects_a_subdomain_of_an_allowed_domain() -> None:
    # Matching is exact, not suffix-based: allowing example.com must not hand
    # a tenant's chatbot to anyone who controls a subdomain of it.
    assert _origin_allowed("https://evil.example.com", ["example.com"]) is False


def test_origin_allowed_rejects_a_domain_that_merely_ends_with_an_allowed_one() -> None:
    # "notexample.com".endswith("example.com") is True — a suffix check here
    # would be exploitable by registering a lookalike domain.
    assert _origin_allowed("https://notexample.com", ["example.com"]) is False


def test_origin_allowed_fails_closed_on_an_empty_allowlist() -> None:
    # A key created without domains permits nothing, rather than everything.
    assert _origin_allowed("https://example.com", []) is False


def test_origin_allowed_fails_closed_on_a_missing_origin_header() -> None:
    # Non-browser clients (curl, server-side fetch) send no Origin at all.
    assert _origin_allowed(None, ["example.com"]) is False


def test_origin_allowed_fails_closed_when_both_inputs_are_absent() -> None:
    assert _origin_allowed(None, []) is False


@pytest.mark.parametrize(
    "hostile",
    [
        "https://example.com.evil.test",
        "https://example.com@evil.test",
        "https://evil.test/?next=https://example.com",
        "https://exampleXcom",
        "",
    ],
)
def test_origin_allowed_rejects_confusable_origins(hostile: str) -> None:
    assert _origin_allowed(hostile, ["example.com"]) is False
