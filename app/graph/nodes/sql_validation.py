import re
from app.graph.state import GraphState
from app.auth.models import UserRole, get_rbac_scope
from app.utils.logger import get_logger

logger = get_logger(__name__)

FORBIDDEN_KEYWORDS = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE","TRUNCATE", "REPLACE", "MERGE", "GRANT", "REVOKE","EXEC", "EXECUTE", "CALL", "PRAGMA", "--", ";"]


def _contains_forbidden_keywords(sql: str) -> str | None:
    """
    Checks SQL for dangerous keywords.
    Returns the forbidden keyword found, or None if clean.

    WHY UPPERCASE CHECK?
    SQL is case-insensitive. "drop table" is as dangerous
    as "DROP TABLE". We uppercase both before checking.
    """
    sql_upper = sql.upper()
    for keyword in FORBIDDEN_KEYWORDS:       
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, sql_upper):
            return keyword
    return None


def _inject_rbac_clause(sql: str, token_data) -> tuple[str, bool]:
    """
    Appends role-based WHERE clause to the SQL.

    WHY APPEND NOT REWRITE?
    We trust the LLM-generated SQL structure.
    We just add one more constraint at the end.

    AGENT EXAMPLE:
    Input:  SELECT * FROM transactions WHERE status = 'pending'
    Output: SELECT * FROM transactions WHERE status = 'pending'
            AND agent_id = 5

    SUPERVISOR EXAMPLE:
    Input:  SELECT * FROM transactions WHERE status = 'pending'
    Output: SELECT * FROM transactions WHERE status = 'pending'
            AND agent_id IN (SELECT id FROM users WHERE parent_id = 2)

    ADMIN: No change — full access.

    RETURNS: (modified_sql, was_rbac_injected)
    """
    scope = get_rbac_scope(token_data)

    if scope.filter_column is None:
        logger.info("RBAC: Admin role — no filter applied")
        return sql, False

    sql = sql.rstrip(";").strip()

    if scope.filter_column == "supervisor":
        rbac_clause = (
            f" AND agent_id IN "
            f"(SELECT id FROM users WHERE parent_id = {scope.filter_value} "
            f"AND role = 'agent')"
        )
    else:
        rbac_clause = f" AND {scope.filter_column} = {scope.filter_value}"

    if "WHERE" in sql.upper():
        modified_sql = sql + rbac_clause
    else:
        order_match = re.search(r'\bORDER\s+BY\b', sql.upper())
        limit_match = re.search(r'\bLIMIT\b', sql.upper())

        insert_pos = None
        if order_match:
            insert_pos = order_match.start()
        elif limit_match:
            insert_pos = limit_match.start()

        if insert_pos:
            modified_sql = (
                sql[:insert_pos] +
                f"WHERE {scope.filter_column} = {scope.filter_value} " +
                sql[insert_pos:]
            )
        else:
            modified_sql = sql + f" WHERE {scope.filter_column} = {scope.filter_value}"

    logger.info(
        "RBAC injected | role=%s | clause='%s'",
        token_data.role.value, rbac_clause.strip()
    )
    return modified_sql, True


async def sql_validation_node(state: GraphState) -> GraphState:
    """
    Validates generated SQL for safety and injects RBAC clauses.

    Validation checks (in order):
    1. SQL must not be empty
    2. Must not contain forbidden keywords
    3. Must start with SELECT
    4. Inject RBAC WHERE clause based on user role

    If any check fails → is_valid=False, validation_error set
    → conditional edge routes back to Node 2
    """
    sql        = state.get("generated_sql", "")
    token_data = state["token_data"]

    logger.info(
        "Node 3 — SQL Validation | role=%s | sql='%s'",
        token_data.role.value, sql[:80]
    )

    if not sql or not sql.strip():
        logger.warning("Node 3: Empty SQL generated")
        return {
            **state,
            "is_valid":        False,
            "validation_error": "Generated SQL is empty. Generate a valid SELECT query."
        }

    forbidden = _contains_forbidden_keywords(sql)
    if forbidden:
        logger.warning("Node 3: Forbidden keyword '%s' found", forbidden)
        return {
            **state,
            "is_valid":        False,
            "validation_error": f"SQL contains forbidden keyword '{forbidden}'. "
                               f"Only SELECT statements are allowed."
        }

    sql_clean = sql.strip().upper()
    if not sql_clean.startswith("SELECT"):
        logger.warning("Node 3: SQL does not start with SELECT")
        return {
            **state,
            "is_valid":        False,
            "validation_error": "SQL must start with SELECT. "
                               "No other statement types are permitted."
        }

    try:
        secured_sql, was_injected = _inject_rbac_clause(sql, token_data)
    except Exception as e:
        logger.error("Node 3: RBAC injection failed | %s", str(e))
        return {
            **state,
            "is_valid":        False,
            "validation_error": f"RBAC enforcement failed: {str(e)}"
        }

    logger.info(
        "Node 3 complete | is_valid=True | rbac_injected=%s | final_sql='%s'",
        was_injected, secured_sql[:100]
    )

    return {
        **state,
        "generated_sql":   secured_sql,
        "is_valid":        True,
        "validation_error": None
    }