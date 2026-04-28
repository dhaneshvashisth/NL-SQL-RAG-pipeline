import pytest
from datetime import timedelta
from jose import jwt

from app.auth.jwt_handler import create_access_token, decode_access_token
from app.auth.models import UserRole, TokenData, get_rbac_scope
from app.utils.config import config



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

    parts = token.split(".")
    import base64, json
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


@pytest.mark.asyncio
async def test_login_admin_success(client, db_pool):
    """Valid admin credentials must return JWT token."""
    response = await client.post(
        "/auth/login",
        data={"username": "admin_dv", "password": "Admin@1234"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "admin"
    assert data["username"] == "admin_dv"


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(client, db_pool):
    """Wrong password must return 401."""
    response = await client.post(
        "/auth/login",
        data={"username": "admin_dv", "password": "WrongPassword"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user_rejected(client, db_pool):
    """Non-existent username must return 401."""
    response = await client.post(
        "/auth/login",
        data={"username": "fake_user_xyz", "password": "anything"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint_returns_role(client, db_pool, admin_token):
    """Authenticated /auth/me must return correct role."""
    response = await client.get(
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
    response = await client.post(
        "/query/",
        json={"question": "show transactions"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_with_fake_token(client):
    """Request with fake token must return 401."""
    response = await client.post(
        "/query/",
        json={"question": "show transactions"},
        headers={"Authorization": "Bearer fake.token.here"}
    )
    assert response.status_code == 401