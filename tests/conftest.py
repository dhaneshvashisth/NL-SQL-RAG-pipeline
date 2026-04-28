"""
conftest.py — Shared pytest fixtures

KEY LESSONS FROM DEBUGGING:
1. httpx AsyncClient must be created fresh per test (not session-scoped)
   — session-scoped clients close after first use and can't reopen
2. asyncpg pool must be created per test's own event loop
   — pools are tied to the event loop that created them
3. scope="function" is safer for async resources than scope="session"
"""

import pytest
import asyncio
from app.auth.jwt_handler import create_access_token
from app.auth.models import TokenData, UserRole


# ── Token Fixtures (session-scoped is fine — pure Python, no async) ──

@pytest.fixture(scope="session")
def admin_token():
    return create_access_token(
        user_id=1, username="admin_dv",
        role="admin", parent_id=None
    )


@pytest.fixture(scope="session")
def supervisor_token():
    return create_access_token(
        user_id=2, username="supervisor_virat",
        role="supervisor", parent_id=1
    )


@pytest.fixture(scope="session")
def agent_token():
    return create_access_token(
        user_id=4, username="agent_dhoni",
        role="agent", parent_id=2
    )


# ── TokenData Fixtures (session-scoped — pure Python, no async) ──

@pytest.fixture(scope="session")
def admin_token_data():
    return TokenData(
        user_id=1, username="admin_dv",
        role=UserRole.ADMIN, parent_id=None
    )


@pytest.fixture(scope="session")
def supervisor_token_data():
    return TokenData(
        user_id=2, username="supervisor_virat",
        role=UserRole.SUPERVISOR, parent_id=1
    )


@pytest.fixture(scope="session")
def agent_token_data():
    return TokenData(
        user_id=4, username="agent_dhoni",
        role=UserRole.AGENT, parent_id=2
    )


# ── HTTP Client Fixture ──────────────────────────────────────────────
# MUST be function-scoped — session-scoped closes after first test
# and raises "Cannot reopen a client instance"

@pytest.fixture
async def client():
    """
    Fresh AsyncClient per test.
    WHY FUNCTION-SCOPED?
    httpx.AsyncClient is a context manager that closes connections
    after exiting. Session-scoped means it closes after test 1
    and raises RuntimeError on test 2+.
    Function-scoped = fresh client every test = no reopen error.
    
    WHY lifespan=False?
    Our lifespan calls create_pool() which needs its own event loop.
    We handle the pool separately in db_pool fixture below.
    """
    from httpx import AsyncClient, ASGITransport
    from app.api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


# ── DB Pool Fixture ──────────────────────────────────────────────────
# MUST be function-scoped — asyncpg pools are tied to event loop
# pytest-asyncio creates a new event loop per test function
# so a session-scoped pool from loop A fails in loop B

@pytest.fixture
async def db_pool():
    """
    Fresh DB pool per test.
    WHY FUNCTION-SCOPED?
    asyncpg pools are bound to the event loop that created them.
    pytest-asyncio (with asyncio_mode=auto) creates a NEW event loop
    for each test function. A pool from test 1's loop cannot be used
    in test 2's loop — raises 'attached to a different loop'.
    Solution: create pool fresh in each test's own loop.
    """
    from app.db.connection import create_pool, close_pool
    pool = await create_pool()
    yield pool
    await close_pool()


# ── Cache Fixture ────────────────────────────────────────────────────

@pytest.fixture
def clear_cache():
    """Clears Redis cache before and after test."""
    from app.cache.redis_cache import semantic_cache
    semantic_cache.clear()
    yield
    semantic_cache.clear()