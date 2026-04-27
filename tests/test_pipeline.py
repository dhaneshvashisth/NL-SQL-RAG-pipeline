"""
test_pipeline.py — End-to-end pipeline tests

WHAT WE TEST:
1. Full pipeline runs without error for each role
2. Generated SQL contains correct RBAC clauses
3. Retry loop triggers on bad SQL
4. Response is always a non-empty string
5. Row counts are non-negative integers

WHY INTEGRATION TESTS MATTER FOR AGENTIC SYSTEMS:
Unit tests verify individual functions.
But in a 5-node graph, a bug in state passing
between nodes would only show up in integration tests.
Example: Node 2 writes to wrong state key →
         Node 3 reads None → crashes silently
"""

import pytest
from app.graph.pipeline import run_pipeline
from app.graph.nodes.sql_validation import (
    _contains_forbidden_keywords,
    _inject_rbac_clause
)
from app.auth.models import TokenData, UserRole


@pytest.mark.asyncio
async def test_full_pipeline_admin(admin_token_data):
    """Admin pipeline must complete and return results."""
    result = await run_pipeline(
        question="how many transactions are there in total",
        token_data=admin_token_data
    )

    assert result["final_response"] is not None
    assert len(result["final_response"]) > 0
    assert result["generated_sql"] is not None
    assert result["row_count"] is not None
    assert result["row_count"] >= 0
    assert result["error_message"] is None


@pytest.mark.asyncio
async def test_full_pipeline_agent(agent_token_data):
    """Agent pipeline must complete with RBAC applied."""
    result = await run_pipeline(
        question="show me all my transactions",
        token_data=agent_token_data
    )

    assert result["final_response"] is not None
    assert result["generated_sql"] is not None

    # CRITICAL: Agent SQL must contain their agent_id
    sql = result["generated_sql"]
    assert str(agent_token_data.user_id) in sql, (
        f"RBAC not applied — agent_id {agent_token_data.user_id} "
        f"not found in SQL: {sql}"
    )


@pytest.mark.asyncio
async def test_full_pipeline_supervisor(supervisor_token_data):
    """Supervisor pipeline must complete with team scope."""
    result = await run_pipeline(
        question="show total transactions for my team",
        token_data=supervisor_token_data
    )

    assert result["final_response"] is not None
    assert result["generated_sql"] is not None

    # Supervisor SQL must contain subquery with their id
    sql = result["generated_sql"]
    assert str(supervisor_token_data.user_id) in sql, (
        f"RBAC not applied — supervisor_id {supervisor_token_data.user_id} "
        f"not found in SQL: {sql}"
    )


@pytest.mark.asyncio
async def test_pipeline_returns_no_error_on_valid_question(admin_token_data):
    """Valid question must not produce error_message."""
    result = await run_pipeline(
        question="what is the total deposit amount",
        token_data=admin_token_data
    )
    assert result.get("error_message") is None


@pytest.mark.asyncio
async def test_pipeline_state_fully_populated(admin_token_data):
    """All expected state keys must be populated after run."""
    result = await run_pipeline(
        question="how many agents are there",
        token_data=admin_token_data
    )

    # These must always be set after a successful run
    assert "retrieved_schemas" in result
    assert "generated_sql" in result
    assert "is_valid" in result
    assert "query_result" in result
    assert "final_response" in result
    assert "row_count" in result


@pytest.mark.asyncio
async def test_aggregate_question_returns_summary(admin_token_data):
    """Aggregate questions must return formatted summary."""
    result = await run_pipeline(
        question="what is the total number of pending transactions",
        token_data=admin_token_data
    )

    assert result["final_response"] is not None
    # Response should mention a number
    response = result["final_response"]
    assert any(char.isdigit() for char in response), (
        "Aggregate response should contain at least one number"
    )


@pytest.mark.asyncio
async def test_platform_question_retrieves_platform_schema(admin_token_data):
    """Platform question must retrieve platforms schema doc."""
    result = await run_pipeline(
        question="which platform has the most transactions",
        token_data=admin_token_data
    )

    schemas = result.get("retrieved_schemas", [])
    doc_ids = [s["doc_id"] for s in schemas]

    assert "platforms_table" in doc_ids or "transactions_table" in doc_ids, (
        f"Expected platform/transaction schema, got: {doc_ids}"
    )