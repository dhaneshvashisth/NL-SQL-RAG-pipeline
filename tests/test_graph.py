
import asyncio
import pytest
from app.graph.pipeline import run_pipeline
from app.graph.nodes.sql_validation import (
    _contains_forbidden_keywords,
    _inject_rbac_clause
)
from app.auth.models import TokenData, UserRole


def test_forbidden_keywords_detected():
    """DROP TABLE must be caught before execution."""
    assert _contains_forbidden_keywords("DROP TABLE transactions") == "DROP"
    assert _contains_forbidden_keywords("SELECT * FROM users") is None
    assert _contains_forbidden_keywords("DELETE FROM transactions") == "DELETE"


def test_select_only_passes_keyword_check():
    """Clean SELECT should pass forbidden keyword check."""
    sql = "SELECT id, amount FROM transactions WHERE status = 'pending'"
    assert _contains_forbidden_keywords(sql) is None


def test_rbac_agent_scope_injected():
    """Agent SQL must have agent_id WHERE clause appended."""
    from app.auth.models import TokenData, UserRole
    token = TokenData(
        user_id=5, username="agent_dhoni",
        role=UserRole.AGENT, parent_id=2
    )
    sql = "SELECT id, amount FROM transactions WHERE status = 'pending'"
    secured, injected = _inject_rbac_clause(sql, token)
    assert injected is True
    assert "agent_id = 5" in secured


def test_rbac_admin_no_filter():
    """Admin SQL must NOT have any filter injected."""
    token = TokenData(
        user_id=1, username="admin_dv",
        role=UserRole.ADMIN, parent_id=None
    )
    sql = "SELECT id, amount FROM transactions"
    secured, injected = _inject_rbac_clause(sql, token)
    assert injected is False
    assert secured == sql