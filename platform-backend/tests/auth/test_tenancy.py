"""`ensure_same_business` is the cross-tenant guard every router handler with a
business_id path parameter must call. It is a plain sync function rather than a FastAPI
dependency, which makes it cheap to test exhaustively — and worth doing, because a
regression here is a direct cross-tenant data leak. tests/businesses/test_businesses.py
and tests/usage/test_metrics.py cover it end-to-end over HTTP; this pins the logic itself.

No DB is touched: the guard only reads `user.role` and `user.business_id`, so an
unattached User instance is a faithful stand-in for a persisted one."""

from uuid import UUID, uuid4

import pytest

from src.auth.dependencies import ensure_same_business
from src.auth.models import User, UserRole
from src.core.exceptions import NotAuthorized


def _user(role: UserRole, business_id: UUID | None) -> User:
    """A transient User — never added to a session, so this stays a pure unit test."""
    return User(
        id=uuid4(),
        email=f"user-{uuid4().hex[:8]}@example.com",
        password_hash="not-a-real-hash",
        role=role,
        business_id=business_id,
    )


def test_business_admin_may_act_on_their_own_business() -> None:
    business_id = uuid4()
    user = _user(UserRole.business_admin, business_id)

    ensure_same_business(business_id, user)  # must not raise


def test_business_admin_is_denied_another_tenants_business() -> None:
    # The core multi-tenancy assertion: the path parameter is attacker-controlled,
    # the principal's own business_id is not.
    user = _user(UserRole.business_admin, uuid4())

    with pytest.raises(NotAuthorized):
        ensure_same_business(uuid4(), user)


def test_business_admin_with_no_business_is_denied() -> None:
    # Shouldn't be reachable (the column is populated for business admins), but
    # the guard must still fail closed rather than compare None to a real id.
    user = _user(UserRole.business_admin, None)

    with pytest.raises(NotAuthorized):
        ensure_same_business(uuid4(), user)


def test_super_admin_may_act_on_any_business() -> None:
    user = _user(UserRole.super_admin, None)

    ensure_same_business(uuid4(), user)  # must not raise


def test_super_admin_bypass_does_not_depend_on_their_own_business_id() -> None:
    # The role is what grants the bypass; a stray business_id must not narrow it.
    user = _user(UserRole.super_admin, uuid4())

    ensure_same_business(uuid4(), user)  # must not raise


def test_guard_is_denied_for_repeated_distinct_tenants() -> None:
    # Guards against a memoization/caching regression making the first check sticky.
    own = uuid4()
    user = _user(UserRole.business_admin, own)

    ensure_same_business(own, user)
    for _ in range(3):
        with pytest.raises(NotAuthorized):
            ensure_same_business(uuid4(), user)
