"""The security-headers middleware must stamp its hardening headers on every response,
including simple ones like /health. Guards against a future middleware reorder or removal
silently dropping the baseline."""

from httpx import AsyncClient


async def test_security_headers_present_on_every_response(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200

    headers = response.headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["cross-origin-opener-policy"] == "same-origin"
    assert "content-security-policy" in headers
    assert "default-src 'none'" in headers["content-security-policy"]
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert "permissions-policy" in headers


async def test_hsts_absent_in_development(client: AsyncClient) -> None:
    # The test/app process runs with a non-production ENV, so HSTS must NOT be sent
    # (it would wedge a local browser onto https). Production behaviour is covered by the
    # config/is_production unit tests.
    response = await client.get("/health")
    assert "strict-transport-security" not in response.headers
