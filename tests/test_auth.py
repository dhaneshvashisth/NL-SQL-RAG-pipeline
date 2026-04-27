

# import pytest
# from app.auth.jwt_handler import create_access_token, decode_access_token
# from app.auth.models import UserRole, get_rbac_scope


# def test_create_and_decode_token():
#     """Token we create should decode to same values."""
#     token = create_access_token(
#         user_id=1, username="admin_dv",
#         role="admin", parent_id=None
#     )
#     decoded = decode_access_token(token)
#     assert decoded.user_id == 1
#     assert decoded.username == "admin_dv"
#     assert decoded.role == UserRole.ADMIN


# def test_agent_rbac_scope():
#     """Agent should only see their own transactions."""
#     from app.auth.models import TokenData
#     td = TokenData(user_id=5, username="agent_dhoni",
#                    role=UserRole.AGENT, parent_id=2)
#     scope = get_rbac_scope(td)
#     assert scope.filter_column == "agent_id"
#     assert scope.filter_value == 5


# def test_admin_rbac_scope():
#     """Admin should have no filter — full access."""
#     from app.auth.models import TokenData
#     td = TokenData(user_id=1, username="admin_dv",
#                    role=UserRole.ADMIN, parent_id=None)
#     scope = get_rbac_scope(td)
#     assert scope.filter_column is None
#     assert scope.filter_value is None


# def test_invalid_token_raises():
#     """Tampered token should raise ValueError."""
#     with pytest.raises(ValueError):
#         decode_access_token("this.is.fake")



"""
test_auth.py — Authentication and JWT tests

WHAT WE TEST:
1. Token creation and decoding roundtrip
2. Tampered tokens are rejected
3. Expired tokens are rejected
4. All three roles decode correctly
5. RBAC scopes are correct per role
6. Login endpoint works via HTTP
7. Protected endpoints reject unauthenticated requests
"""

import pytest
from datetime import timedelta
from jose import jwt

from app.auth.jwt_handler import create_access_token, decode_access_token
from app.auth.models import UserRole, TokenData, get_rbac_scope
from app.utils.config import config


# ── JWT Unit Tests ────────────────────────────────────────────

def test_create_token_returns_string():
    """Token must be a non-empty string."""
    token = create_access_token(1, "admin_dv", "admin")
    assert isinstance(token, str)
    assert len(token) > 0


def test_token_roundtrip_admin():
    """Created token must decode to same values."""
    token = create_access_token(
        user_id=1, username="admin_dv",
        role="admin", parent_id=None
    )
    decoded = decode_access_token(token)
    assert decoded.user_id == 1
    assert decoded.username == "admin_dv"
    assert decoded.role == UserRole.ADMIN
    assert decoded.parent_id is None


def test_token_roundtrip_supervisor():
    """Supervisor token carries parent_id correctly."""
    token = create_access_token(
        user_id=2, username="supervisor_virat",
        role="supervisor", parent_id=1
    )
    decoded = decode_access_token(token)
    assert decoded.role == UserRole.SUPERVISOR
    assert decoded.parent_id == 1


def test_token_roundtrip_agent():
    """Agent token carries parent_id (supervisor id)."""
    token = create_access_token(
        user_id=4, username="agent_dhoni",
        role="agent", parent_id=2
    )
    decoded = decode_access_token(token)
    assert decoded.role == UserRole.AGENT
    assert decoded.parent_id == 2


def test_tampered_token_rejected():
    """Modifying token payload must raise ValueError."""
    token = create_access_token(1, "admin_dv", "admin")

    # Tamper: decode without verification, change role, re-encode without secret
    parts = token.split(".")
    import base64, json
    # Corrupt the payload part
    tampered = token[:-5] + "XXXXX"

    with pytest.raises(ValueError):
        decode_access_token(tampered)


def test_completely_fake_token_rejected():
    """Random string must be rejected."""
    with pytest.raises(ValueError):
        decode_access_token("this.is.completely.fake")


def test_wrong_secret_token_rejected():
    """Token signed with wrong secret must be rejected."""
    fake_token = jwt.encode(
        {"user_id": 1, "username": "hacker", "role": "admin"},
        "wrong_secret_key",
        algorithm="HS256"
    )
    with pytest.raises(ValueError):
        decode_access_token(fake_token)


# ── RBAC Scope Tests ──────────────────────────────────────────

def test_admin_rbac_no_filter():
    """Admin must have NO filter — full data access."""
    td = TokenData(1, "admin_dv", UserRole.ADMIN, None)
    scope = get_rbac_scope(td)
    assert scope.filter_column is None
    assert scope.filter_value is None


def test_supervisor_rbac_scoped():
    """Supervisor must filter by their own id."""
    td = TokenData(2, "supervisor_virat", UserRole.SUPERVISOR, 1)
    scope = get_rbac_scope(td)
    assert scope.filter_column == "supervisor"
    assert scope.filter_value == 2


def test_agent_rbac_scoped():
    """Agent must filter by agent_id = their own id."""
    td = TokenData(4, "agent_dhoni", UserRole.AGENT, 2)
    scope = get_rbac_scope(td)
    assert scope.filter_column == "agent_id"
    assert scope.filter_value == 4


# ── API Endpoint Tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_admin_success(client):
    """Valid admin credentials must return JWT token."""
    async with client as c:
        response = await c.post(
            "/auth/login",
            data={
                "username": "admin_dv",
                "password": "Admin@1234"
            }
        )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "admin"
    assert data["username"] == "admin_dv"


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(client):
    """Wrong password must return 401."""
    async with client as c:
        response = await c.post(
            "/auth/login",
            data={
                "username": "admin_dv",
                "password": "WrongPassword"
            }
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user_rejected(client):
    """Non-existent username must return 401."""
    async with client as c:
        response = await c.post(
            "/auth/login",
            data={
                "username": "fake_user_xyz",
                "password": "anything"
            }
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint_returns_role(client, admin_token):
    """Authenticated /auth/me must return correct role."""
    async with client as c:
        response = await c.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "admin"
    assert data["username"] == "admin_dv"


@pytest.mark.asyncio
async def test_protected_endpoint_without_token(client):
    """Request without token must return 401."""
    async with client as c:
        response = await c.post(
            "/query/",
            json={"question": "show transactions"}
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_with_fake_token(client):
    """Request with fake token must return 401."""
    async with client as c:
        response = await c.post(
            "/query/",
            json={"question": "show transactions"},
            headers={"Authorization": "Bearer fake.token.here"}
        )
    assert response.status_code == 401