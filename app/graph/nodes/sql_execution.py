
from app.graph.state import GraphState
from app.db.connection import get_pool
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def sql_execution_node(state: GraphState) -> GraphState:
    """
    Executes the validated + RBAC-secured SQL query.

    Uses asyncpg pool → non-blocking → async-safe.
    Results converted from asyncpg Record objects to plain dicts
    so they can be JSON-serialized in Node 5.
    """
    sql        = state["generated_sql"]
    token_data = state["token_data"]

    logger.info(
        "Node 4 — SQL Execution | user=%s | sql='%s'",
        token_data.username, sql[:100]
    )

    try:
        pool = await get_pool()

        async with pool.acquire() as conn:
         
            rows = await conn.fetch(sql)

        results = [dict(row) for row in rows]
        row_count = len(results)

        logger.info(
            "Node 4 complete | rows=%d | user=%s",
            row_count, token_data.username
        )

        return {
            **state,
            "query_result":    results,
            "row_count":       row_count,
            "execution_error": None
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(
            "Node 4 failed | user=%s | error=%s",
            token_data.username, error_msg
        )
        return {
            **state,
            "query_result":    [],
            "row_count":       0,
            "execution_error": error_msg,
            "error_message":   f"Query execution failed: {error_msg}"
        }