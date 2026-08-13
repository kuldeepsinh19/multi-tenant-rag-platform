"""Origin allowlisting is the only thing standing between a tenant's widget key and any
site that scrapes it out of a public page — the key travels in client-side HTML, so it is
not a secret and the Origin check is the real boundary. These are pure-function tests over
`_split_origin` / `origin_allowed`; the HTTP-level widget auth path is covered in
tests/chat/test_chat.py. Every fail-closed branch is asserted explicitly, because a
regression that turns a deny into an allow is silent."""

import pytest

from src.chat.dependencies import _split_origin, origin_allowed


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.com", (None, "example.com")),
        ("https://example.com", ("https", "example.com")),
        ("http://example.com", ("http", "example.com")),
        ("https://example.com:8443", ("https", "example.com")),
        ("https://user:pass@example.com", ("https", "example.com")),
        ("https://user:pass@example.com:8443", ("https", "example.com")),
        ("HTTPS://EXAMPLE.COM", ("https", "example.com")),
        ("  https://example.com  ", ("https", "example.com")),
        ("example.com:3000", (None, "example.com")),
        ("https://shop.example.com", ("https", "shop.example.com")),
        # IPv6 literals keep their brackets so the host stays unambiguous.
        ("http://[::1]:5173", ("http", "[::1]")),
    ],
)
def test_split_origin_separates_scheme_from_host(
    raw: str, expected: tuple[str | None, str]
) -> None:
    assert _split_origin(raw) == expected


def test_split_origin_is_idempotent_on_its_own_host() -> None:
    _, host = _split_origin("https://Example.com:8443")
    assert _split_origin(host) == (None, host)


def test_origin_allowed_matches_a_configured_domain() -> None:
    assert origin_allowed("https://example.com", ["example.com"]) is True


def test_origin_allowed_ignores_port_and_case() -> None:
    assert origin_allowed("HTTPS://Example.com:8443", ["example.com"]) is True


def test_origin_allowed_matches_a_domain_stored_with_a_scheme() -> None:
    # Admins paste whole URLs into the allowlist field.
    assert origin_allowed("https://example.com", ["https://example.com"]) is True


def test_origin_allowed_matches_any_entry_in_a_multi_domain_allowlist() -> None:
    allowed = ["first.test", "example.com", "third.test"]
    assert origin_allowed("https://example.com", allowed) is True


def test_origin_allowed_rejects_a_domain_not_on_the_list() -> None:
    assert origin_allowed("https://evil.test", ["example.com"]) is False


def test_origin_allowed_rejects_a_subdomain_of_an_allowed_domain() -> None:
    # Matching is exact, not suffix-based: allowing example.com must not hand
    # a tenant's chatbot to anyone who controls a subdomain of it.
    assert origin_allowed("https://evil.example.com", ["example.com"]) is False


def test_origin_allowed_rejects_a_domain_that_merely_ends_with_an_allowed_one() -> None:
    # "notexample.com".endswith("example.com") is True — a suffix check here
    # would be exploitable by registering a lookalike domain.
    assert origin_allowed("https://notexample.com", ["example.com"]) is False


def test_origin_allowed_fails_closed_on_an_empty_allowlist() -> None:
    # A key created without domains permits nothing, rather than everything.
    assert origin_allowed("https://example.com", []) is False


def test_origin_allowed_fails_closed_on_a_missing_origin_header() -> None:
    # Non-browser clients (curl, server-side fetch) send no Origin at all.
    assert origin_allowed(None, ["example.com"]) is False


def test_origin_allowed_fails_closed_when_both_inputs_are_absent() -> None:
    assert origin_allowed(None, []) is False


# --- Scheme handling -------------------------------------------------------------------
# A bare-domain allowlist entry means "this host over TLS". Accepting the plaintext origin
# too would let an injected or SSL-stripped page on the customer's own domain drive the key.


def test_origin_allowed_rejects_http_downgrade_for_a_bare_domain_entry() -> None:
    assert origin_allowed("http://example.com", ["example.com"]) is False


def test_origin_allowed_rejects_http_downgrade_for_an_https_entry() -> None:
    assert origin_allowed("http://example.com", ["https://example.com"]) is False


def test_origin_allowed_honours_an_explicit_http_entry() -> None:
    # An operator who deliberately allowlists a plaintext origin still gets it.
    assert origin_allowed("http://example.com", ["http://example.com"]) is True


def test_origin_allowed_rejects_https_origin_against_an_http_only_entry() -> None:
    assert origin_allowed("https://example.com", ["http://example.com"]) is False


@pytest.mark.parametrize("loopback", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_origin_allowed_permits_plaintext_loopback_for_local_development(loopback: str) -> None:
    _, host = _split_origin(loopback)
    assert origin_allowed(loopback, [host]) is True


@pytest.mark.parametrize(
    "hostile",
    [
        "https://example.com.evil.test",
        "https://example.com@evil.test",
        "https://evil.test/?next=https://example.com",
        "https://exampleXcom",
        "",
        # Opaque origins identify no domain that could have been allowlisted.
        "null",
        "example.com",
    ],
)
def test_origin_allowed_rejects_confusable_or_opaque_origins(hostile: str) -> None:
    assert origin_allowed(hostile, ["example.com"]) is False
