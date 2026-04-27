"""
conftest.py — Shared pytest fixtures

WHY FIXTURES?
Fixtures are reusable setup/teardown functions.
Without fixtures, every test file would repeat:
    token = create_access_token(...)
    pool = await create_pool()
    ...

With fixtures, you declare them once here and
inject them into any test just by naming the parameter.

FIXTURE SCOPES:
- scope="function" → runs fresh for each test (default)
- scope="module"   → runs once per test file
- scope="session"  → runs once for entire test run

We use "session" for expensive setup (DB pool, pipeline)
and "function" for things that change per test (cache state).
"""

import pytest
import asyncio
from app.auth.jwt_handler import create_access_token
from app.auth.models import TokenData, UserRole


# ── Token Fixtures ────────────────────────────────────────────
# These create real JWT tokens for each role
# Used by API tests to authenticate requests

@pytest.fixture(scope="session")
def admin_token():
    """Real JWT token for admin user."""
    return create_access_token(
        user_id=1,
        username="admin_dv",
        role="admin",
        parent_id=None
    )


@pytest.fixture(scope="session")
def supervisor_token():
    """Real JWT token for supervisor."""
    return create_access_token(
        user_id=2,
        username="supervisor_virat",
        role="supervisor",
        parent_id=1
    )


@pytest.fixture(scope="session")
def agent_token():
    """Real JWT token for agent."""
    return create_access_token(
        user_id=4,
        username="agent_dhoni",
        role="agent",
        parent_id=2
    )


# ── TokenData Fixtures ────────────────────────────────────────
# Decoded token objects — used directly by pipeline tests

@pytest.fixture(scope="session")
def admin_token_data():
    return TokenData(
        user_id=1,
        username="admin_dv",
        role=UserRole.ADMIN,
        parent_id=None
    )


@pytest.fixture(scope="session")
def supervisor_token_data():
    return TokenData(
        user_id=2,
        username="supervisor_virat",
        role=UserRole.SUPERVISOR,
        parent_id=1
    )


@pytest.fixture(scope="session")
def agent_token_data():
    return TokenData(
        user_id=4,
        username="agent_dhoni",
        role=UserRole.AGENT,
        parent_id=2
    )


# ── FastAPI Test Client ───────────────────────────────────────

@pytest.fixture(scope="session")
def client():
    """
    HTTPX async test client for FastAPI.

    WHY NOT USE requests?
    Our FastAPI app is async. The regular requests library
    is synchronous and can't properly test async endpoints.
    httpx.AsyncClient handles async FastAPI natively.

    WHY NOT START A REAL SERVER?
    TestClient/AsyncClient talks to the app directly in memory
    — no network, no port binding, faster tests.
    """
    from httpx import AsyncClient
    from app.api.main import app
    return AsyncClient(app=app, base_url="http://test")


# ── Cache Fixture ─────────────────────────────────────────────

@pytest.fixture(autouse=False)
def clear_cache():
    """
    Clears Redis cache before a test that needs a clean state.
    Use with: def test_something(clear_cache): ...
    """
    from app.cache.redis_cache import semantic_cache
    semantic_cache.clear()
    yield
    semantic_cache.clear()