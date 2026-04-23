

import pytest
from app.auth.jwt_handler import create_access_token, decode_access_token
from app.auth.models import UserRole, get_rbac_scope


def test_create_and_decode_token():
    """Token we create should decode to same values."""
    token = create_access_token(
        user_id=1, username="admin_dv",
        role="admin", parent_id=None
    )
    decoded = decode_access_token(token)
    assert decoded.user_id == 1
    assert decoded.username == "admin_dv"
    assert decoded.role == UserRole.ADMIN


def test_agent_rbac_scope():
    """Agent should only see their own transactions."""
    from app.auth.models import TokenData
    td = TokenData(user_id=5, username="agent_dhoni",
                   role=UserRole.AGENT, parent_id=2)
    scope = get_rbac_scope(td)
    assert scope.filter_column == "agent_id"
    assert scope.filter_value == 5


def test_admin_rbac_scope():
    """Admin should have no filter — full access."""
    from app.auth.models import TokenData
    td = TokenData(user_id=1, username="admin_dv",
                   role=UserRole.ADMIN, parent_id=None)
    scope = get_rbac_scope(td)
    assert scope.filter_column is None
    assert scope.filter_value is None


def test_invalid_token_raises():
    """Tampered token should raise ValueError."""
    with pytest.raises(ValueError):
        decode_access_token("this.is.fake")