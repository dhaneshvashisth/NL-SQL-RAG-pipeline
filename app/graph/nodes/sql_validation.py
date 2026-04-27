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


def _clean_placeholders(sql: str, token_data) -> str:
    """
    Replaces any template placeholders like {agent_id}, {user_id}
    that the LLM sometimes generates instead of real values.
    
    WHY THIS HAPPENS:
    LLMs sometimes generate parameterized-style placeholders
    when they're uncertain of the actual value. We replace them
    with real values from token_data before execution.
    """
    replacements = {
        "{agent_id}":      str(token_data.user_id),
        "{user_id}":       str(token_data.user_id),
        "{supervisor_id}": str(token_data.user_id),
        "{parent_id}":     str(token_data.parent_id or "NULL"),
    }
    for placeholder, value in replacements.items():
        sql = sql.replace(placeholder, value)
    return sql

def _inject_rbac_clause(sql: str, token_data) -> tuple[str, bool]:
    scope = get_rbac_scope(token_data)

    if scope.filter_column is None:
        logger.info("RBAC: Admin role — no filter applied")
        return sql, False

    sql = sql.rstrip(";").strip()

  
    if scope.filter_column == "supervisor":
        already_scoped = f"parent_id = {scope.filter_value}" in sql
    else:
        already_scoped = (
            f"{scope.filter_column} = {scope.filter_value}" in sql or
            f"agent_id = {scope.filter_value}" in sql
        )

    if already_scoped:
        logger.info(
            "RBAC: Scope already present in SQL — skipping injection | role=%s",
            token_data.role.value
        )
        return sql, False

    if scope.filter_column == "supervisor":
        rbac_condition = (
            f"agent_id IN "
            f"(SELECT id FROM users WHERE parent_id = {scope.filter_value} "
            f"AND role = 'agent')"
        )
    else:
        rbac_condition = f"{scope.filter_column} = {scope.filter_value}"

    sql_upper = sql.upper()
    order_pos = re.search(r'\bORDER\s+BY\b', sql_upper)
    limit_pos = re.search(r'\bLIMIT\b', sql_upper)

    insert_pos = None
    if order_pos:
        insert_pos = order_pos.start()
    if limit_pos:
        if insert_pos is None or limit_pos.start() < insert_pos:
            insert_pos = limit_pos.start()

    has_where = "WHERE" in sql_upper

    if insert_pos is not None:
        before = sql[:insert_pos].rstrip()
        after  = sql[insert_pos:]
        if has_where:
            modified_sql = f"{before} AND {rbac_condition} {after}"
        else:
            modified_sql = f"{before} WHERE {rbac_condition} {after}"
    else:
        if has_where:
            modified_sql = f"{sql} AND {rbac_condition}"
        else:
            modified_sql = f"{sql} WHERE {rbac_condition}"

    logger.info(
        "RBAC injected | role=%s | condition='%s'",
        token_data.role.value, rbac_condition
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
            "is_valid":   False,
            "validation_error": "Generated SQL is empty. Generate a valid SELECT query."
        }
    
    sql = _clean_placeholders(sql, token_data)
    logger.info("Placeholders cleaned | sql='%s'", sql[:80])

    forbidden = _contains_forbidden_keywords(sql)
    if forbidden:
        logger.warning("Node 3: Forbidden keyword '%s' found", forbidden)
        return {
            **state,
            "is_valid":  False,
            "validation_error": f"SQL contains forbidden keyword '{forbidden}'. Only SELECT statements are allowed."
        }

    sql_clean = sql.strip().upper()
    if not sql_clean.startswith("SELECT"):
        logger.warning("Node 3: SQL does not start with SELECT")
        return {
            **state,
            "is_valid":False,
            "validation_error": "SQL must start with SELECT. No other statement types are permitted."
        }

    try:
        secured_sql, was_injected = _inject_rbac_clause(sql, token_data)
    except Exception as e:
        logger.error("Node 3: RBAC injection failed | %s", str(e))
        return {
            **state,
            "is_valid": False,
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