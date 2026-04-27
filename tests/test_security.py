"""
test_security.py — Security boundary tests

THESE ARE THE MOST IMPORTANT TESTS IN THE PROJECT.
They verify that malicious inputs cannot:
1. Execute dangerous SQL (DROP, DELETE, etc.)
2. Bypass role-based access control
3. Access other users' data through the cache
4. Inject SQL through natural language prompts

When asked in interviews: "How did you secure your AI system?"
These tests are your proof.
"""

import pytest
from app.graph.nodes.sql_validation import (
    _contains_forbidden_keywords,
    _inject_rbac_clause
)
from app.auth.models import TokenData, UserRole
from app.cache.redis_cache import SemanticCache


# ── SQL Injection via Forbidden Keywords ──────────────────────

class TestForbiddenKeywords:
    """Every dangerous SQL keyword must be caught."""

    def test_drop_table_caught(self):
        assert _contains_forbidden_keywords("DROP TABLE users") == "DROP"

    def test_delete_caught(self):
        assert _contains_forbidden_keywords(
            "DELETE FROM transactions WHERE id = 1"
        ) == "DELETE"

    def test_insert_caught(self):
        assert _contains_forbidden_keywords(
            "INSERT INTO users VALUES (1, 'hacker')"
        ) == "INSERT"

    def test_update_caught(self):
        assert _contains_forbidden_keywords(
            "UPDATE users SET role = 'admin' WHERE id = 5"
        ) == "UPDATE"

    def test_alter_caught(self):
        assert _contains_forbidden_keywords(
            "ALTER TABLE users ADD COLUMN secret TEXT"
        ) == "ALTER"

    def test_truncate_caught(self):
        assert _contains_forbidden_keywords(
            "TRUNCATE TABLE transactions"
        ) == "TRUNCATE"

    def test_sql_comment_injection_caught(self):
        """SQL comment -- is a common injection technique."""
        assert _contains_forbidden_keywords(
            "SELECT * FROM users -- DROP TABLE users"
        ) == "--"

    def test_semicolon_chaining_caught(self):
        """Semicolons enable query chaining attacks."""
        assert _contains_forbidden_keywords(
            "SELECT * FROM users; DROP TABLE users"
        ) == ";"

    def test_clean_select_passes(self):
        """Normal SELECT must not be flagged."""
        sql = """
        SELECT t.id, t.amount, t.status
        FROM transactions t
        JOIN users u ON t.agent_id = u.id
        WHERE t.status = 'pending'
        ORDER BY t.created_at DESC
        LIMIT 100
        """
        assert _contains_forbidden_keywords(sql) is None

    def test_created_at_not_flagged_as_create(self):
        """
        'created_at' column must NOT trigger CREATE keyword detection.
        This tests our word-boundary regex is correct.
        """
        sql = "SELECT id, created_at FROM transactions"
        assert _contains_forbidden_keywords(sql) is None

    def test_case_insensitive_detection(self):
        """Lowercase dangerous keywords must also be caught."""
        assert _contains_forbidden_keywords("drop table users") == "drop"
        assert _contains_forbidden_keywords("delete from users") == "delete"


# ── RBAC Injection Tests ──────────────────────────────────────

class TestRBACInjection:
    """Role-based WHERE clauses must always be appended correctly."""

    def test_agent_scope_appended_to_existing_where(self):
        """Agent's agent_id must be added after existing WHERE."""
        token = TokenData(4, "agent_dhoni", UserRole.AGENT, 2)
        sql = "SELECT * FROM transactions WHERE status = 'pending'"
        secured, injected = _inject_rbac_clause(sql, token)

        assert injected is True
        assert "agent_id = 4" in secured
        assert "status = 'pending'" in secured  # original condition preserved

    def test_agent_scope_added_when_no_where(self):
        """Agent scope must be added even when no WHERE exists."""
        token = TokenData(4, "agent_dhoni", UserRole.AGENT, 2)
        sql = "SELECT id, amount FROM transactions ORDER BY created_at DESC"
        secured, injected = _inject_rbac_clause(sql, token)

        assert injected is True
        assert "agent_id = 4" in secured

    def test_supervisor_scope_uses_subquery(self):
        """Supervisor must get subquery filtering to their agents."""
        token = TokenData(2, "supervisor_virat", UserRole.SUPERVISOR, 1)
        sql = "SELECT * FROM transactions WHERE status = 'completed'"
        secured, injected = _inject_rbac_clause(sql, token)

        assert injected is True
        assert "parent_id = 2" in secured
        assert "SELECT id FROM users" in secured

    def test_admin_gets_no_filter(self):
        """Admin SQL must be completely unchanged."""
        token = TokenData(1, "admin_dv", UserRole.ADMIN, None)
        sql = "SELECT * FROM transactions"
        secured, injected = _inject_rbac_clause(sql, token)

        assert injected is False
        assert secured == sql  # completely unchanged

    def test_different_agents_get_different_filters(self):
        """Two agents must get different agent_id values."""
        token_dhoni  = TokenData(4, "agent_dhoni",  UserRole.AGENT, 2)
        token_sachin = TokenData(12, "agent_sachin", UserRole.AGENT, 3)

        sql = "SELECT * FROM transactions"

        secured_dhoni,  _ = _inject_rbac_clause(sql, token_dhoni)
        secured_sachin, _ = _inject_rbac_clause(sql, token_sachin)

        assert "agent_id = 4"  in secured_dhoni
        assert "agent_id = 12" in secured_sachin
        # Critical: dhoni's filter must NOT appear in sachin's query
        assert "agent_id = 4"  not in secured_sachin
        assert "agent_id = 12" not in secured_dhoni


# ── Cache Security Tests ──────────────────────────────────────

class TestCacheSecurity:
    """
    Cache must never return one user's data to another user.
    This was the bug we caught and fixed in Phase 7.
    """

    def test_admin_cache_not_returned_to_agent(self):
        """
        Admin's cached result must not be returned to agent
        even for identical questions.
        """
        cache = SemanticCache()
        cache.clear()

        fake_vector = [0.5] * 1536
        question = "show all pending transactions"

        # Store admin's result
        cache.set(
            question=question,
            question_vector=fake_vector,
            generated_sql="SELECT * FROM transactions",
            result="Admin sees 47 transactions",
            row_count=47,
            user_id=1,
            role="admin"
        )

        # Agent tries to get same question
        hit = cache.get(
            question=question,
            question_vector=fake_vector,
            user_id=4,        # different user
            role="agent"      # different role
        )

        # Must be a cache MISS — not admin's data
        assert hit is None, (
            "SECURITY BUG: Admin cache result returned to agent!"
        )

    def test_same_role_different_users_isolated(self):
        """
        Two agents must not share cache entries.
        Agent dhoni's data must not be returned to agent sachin.
        """
        cache = SemanticCache()
        cache.clear()

        fake_vector = [0.3] * 1536
        question = "show my transactions"

        # Store dhoni's result
        cache.set(
            question=question,
            question_vector=fake_vector,
            generated_sql="SELECT * FROM transactions WHERE agent_id = 4",
            result="Dhoni has 55 transactions",
            row_count=55,
            user_id=4,
            role="agent"
        )

        # Sachin tries to get same question
        hit = cache.get(
            question=question,
            question_vector=fake_vector,
            user_id=12,       # sachin's id
            role="agent"      # same role, different user
        )

        assert hit is None, (
            "SECURITY BUG: Agent dhoni's cache returned to agent sachin!"
        )

    def test_same_user_same_role_gets_cache_hit(self):
        """
        Same user asking same question MUST get cache hit.
        """
        cache = SemanticCache()
        cache.clear()

        fake_vector = [0.7] * 1536

        cache.set(
            question="my transactions",
            question_vector=fake_vector,
            generated_sql="SELECT * FROM transactions WHERE agent_id = 4",
            result="55 transactions found",
            row_count=55,
            user_id=4,
            role="agent"
        )

        hit = cache.get(
            question="my transactions",
            question_vector=fake_vector,
            user_id=4,      # same user
            role="agent"    # same role
        )

        assert hit is not None
        assert hit["result"] == "55 transactions found"


# ── Input Validation Tests ────────────────────────────────────

class TestInputValidation:
    """API must reject invalid inputs gracefully."""

    @pytest.mark.asyncio
    async def test_empty_question_rejected(self, client, admin_token):
        """Empty question must return 400."""
        async with client as c:
            response = await c.post(
                "/query/",
                json={"question": ""},
                headers={"Authorization": f"Bearer {admin_token}"}
            )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_too_long_question_rejected(self, client, admin_token):
        """Questions over 500 chars must return 400."""
        async with client as c:
            response = await c.post(
                "/query/",
                json={"question": "x" * 501},
                headers={"Authorization": f"Bearer {admin_token}"}
            )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_health_endpoint_always_works(self, client):
        """Health endpoint must work without authentication."""
        async with client as c:
            response = await c.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"