"""Shared test fixtures. Tests run against the real Postgres started by
docker-compose (see repo root docker-compose.yml) — there is no test-only DB, so every
fixture that creates rows must use randomly-suffixed values to avoid collisions with
other concurrent test runs or other agents' work against the same database."""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import async_session_factory, engine
from src.main import app


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_pool_per_test() -> AsyncGenerator[None, None]:
    """`engine` (src/core/db.py) is a module-level singleton whose asyncpg
    connections get bound to whatever event loop was running when they were first
    opened. pytest-asyncio gives each test function its own event loop, so a pooled
    connection surviving from a previous test crashes with "attached to a different
    loop". Disposing the pool after every test forces a fresh connection (and thus
    the current loop) next time it's used."""
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
