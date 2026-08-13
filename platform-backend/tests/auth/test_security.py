"""Token issuance and password hashing, tested directly rather than through HTTP.

The `business_id` claim carried here is the tenancy boundary for the whole platform:
`get_current_business_id` reads it and no request body is ever consulted. So the round-trip
must preserve it exactly, a tampered token must raise rather than degrade to an anonymous
request, and an expired token must not be accepted. tests/auth/test_login.py covers the
same ground at the HTTP layer; this file pins the primitives underneath it."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from jose import jwt

from src.auth.models import UserRole
from src.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from src.core.config import get_settings


def test_business_admin_token_round_trips_every_claim() -> None:
    user_id = uuid4()
    business_id = uuid4()

    payload = decode_access_token(
        create_access_token(user_id, UserRole.business_admin, business_id)
    )

    assert payload.sub == str(user_id)
    assert payload.role == UserRole.business_admin
    assert payload.business_id == business_id


def test_super_admin_token_carries_a_null_business_id() -> None:
    # A super_admin is not scoped to a tenant; the claim must be absent, not a
    # placeholder that some downstream check could mistake for a real tenant.
    payload = decode_access_token(create_access_token(uuid4(), UserRole.super_admin, None))

    assert payload.role == UserRole.super_admin
    assert payload.business_id is None


def test_tokens_for_different_users_are_distinct() -> None:
    first = create_access_token(uuid4(), UserRole.business_admin, uuid4())
    second = create_access_token(uuid4(), UserRole.business_admin, uuid4())

    assert first != second


def test_tampered_signature_is_rejected() -> None:
    token = create_access_token(uuid4(), UserRole.business_admin, uuid4())
    # Flip the final character of the signature segment.
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

    with pytest.raises(ValueError, match="invalid token"):
        decode_access_token(tampered)


def test_token_signed_with_a_different_secret_is_rejected() -> None:
    # The exact shape of a forged token: right claims, wrong key.
    settings = get_settings()
    forged = jwt.encode(
        {
            "sub": str(uuid4()),
            "role": UserRole.super_admin.value,
            "business_id": None,
            "exp": datetime.now(UTC) + timedelta(minutes=30),
        },
        "not-the-real-secret-not-the-real-secret",
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(ValueError, match="invalid token"):
        decode_access_token(forged)


def test_expired_token_is_rejected() -> None:
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": str(uuid4()),
            "role": UserRole.business_admin.value,
            "business_id": str(uuid4()),
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(ValueError, match="invalid token"):
        decode_access_token(expired)


@pytest.mark.parametrize("garbage", ["", "not-a-token", "a.b.c", "Bearer abc"])
def test_malformed_tokens_are_rejected(garbage: str) -> None:
    with pytest.raises(ValueError, match="invalid token"):
        decode_access_token(garbage)


def test_a_valid_token_does_not_leak_the_secret_in_its_payload() -> None:
    settings = get_settings()
    token = create_access_token(uuid4(), UserRole.business_admin, uuid4())

    assert settings.jwt_secret not in token


def test_password_hash_is_not_the_plaintext() -> None:
    hashed = hash_password("supersecret")

    assert hashed != "supersecret"
    assert "supersecret" not in hashed


def test_password_hashes_are_salted_so_the_same_password_hashes_differently() -> None:
    first = hash_password("supersecret")
    second = hash_password("supersecret")

    assert first != second
    # Both must still verify — the difference is salt, not content.
    assert verify_password("supersecret", first)
    assert verify_password("supersecret", second)


def test_verify_password_accepts_the_correct_password() -> None:
    assert verify_password("supersecret", hash_password("supersecret")) is True


def test_verify_password_rejects_the_wrong_password() -> None:
    assert verify_password("wrong-password", hash_password("supersecret")) is False


def test_verify_password_is_case_sensitive() -> None:
    assert verify_password("SUPERSECRET", hash_password("supersecret")) is False


def test_verify_password_rejects_an_empty_password_against_a_real_hash() -> None:
    assert verify_password("", hash_password("supersecret")) is False


def test_bcrypt_handles_a_long_password_without_raising() -> None:
    # bcrypt truncates at 72 bytes; the pinned bcrypt<4.1 + passlib pairing must
    # not raise on a longer input (it is a real user-supplied value).
    long_password = "x" * 200

    assert verify_password(long_password, hash_password(long_password)) is True
