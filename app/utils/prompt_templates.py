def build_sql_generation_prompt(question: str, schemas:  list[dict], role:str, retry_count: int = 0, previous_sql: str | None = None, validation_error: str | None = None) -> str:
    """
    Builds the prompt for Node 2 (SQL Generation).

    On first attempt (retry_count=0): clean prompt
    On retry (retry_count>0): includes previous SQL + error for self-correction

    WHY INJECT ERROR ON RETRY?
    If we just say "try again", the LLM generates the same wrong SQL.
    If we say "this specific thing was wrong: <error>", the LLM
    can fix exactly that issue. This is called error-guided self-correction.
    """

    schema_context = "\n\n".join([
        f"--- {doc['doc_id']} ---\n{doc['content']}"
        for doc in schemas
    ])

    system_prompt = """You are an expert PostgreSQL query engineer.
            Your job is to convert natural language questions into precise, safe SQL queries.

            STRICT RULES — NEVER VIOLATE:
            1. Generate ONLY SELECT statements. Never INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE.
            2. Use ONLY the tables and columns described in the schema context below.
            3. Always use parameterized-style queries where possible.
            4. Never use SELECT * — always specify column names explicitly.
            5. Always add appropriate LIMIT clauses (default LIMIT 100) unless user asks for all.
            6. Return ONLY the SQL query — no explanation, no markdown, no backticks.
            7. Use PostgreSQL syntax (not MySQL, not SQLite).
            8. For date filtering, use: created_at >= NOW() - INTERVAL '7 days' style.
            9. Always use table aliases for clarity in JOINs.
            10. Column names with spaces must be quoted — but prefer snake_case columns (already in schema).

            SCHEMA CONTEXT (use ONLY these tables and columns):
            {schema_context}

            USER ROLE: {role}
            This affects what data the user should see. The validation system will
            enforce role-based WHERE clauses after you generate SQL, but try to
            generate appropriate SQL for the user's scope.

            FEW-SHOT EXAMPLES:

            Question: "show me all pending transactions"
            SQL: SELECT t.id, t.reference_code, t.amount, t.transaction_type, t.status, t.created_at, u.username as agent FROM transactions t JOIN users u ON t.agent_id = u.id WHERE t.status = 'pending' ORDER BY t.created_at DESC LIMIT 100

            Question: "how many transactions did each agent process this week"
            SQL: SELECT u.full_name as agent_name, COUNT(t.id) as transaction_count, SUM(t.amount) as total_amount FROM transactions t JOIN users u ON t.agent_id = u.id WHERE u.role = 'agent' AND t.created_at >= NOW() - INTERVAL '7 days' GROUP BY u.id, u.full_name ORDER BY transaction_count DESC LIMIT 100

            Question: "show total deposits by platform this month"
            SQL: SELECT p.name as platform_name, COUNT(t.id) as deposit_count, SUM(t.amount) as total_deposits FROM transactions t JOIN platforms p ON t.platform_id = p.id WHERE t.transaction_type = 'deposit' AND t.created_at >= DATE_TRUNC('month', NOW()) GROUP BY p.id, p.name ORDER BY total_deposits DESC LIMIT 100

            Question: "which agents are under supervisor virat"
            SQL: SELECT u.id, u.username, u.full_name, u.email, u.is_active FROM users u JOIN users sup ON u.parent_id = sup.id WHERE sup.username = 'supervisor_virat' AND u.role = 'agent' LIMIT 100
            """

    user_message = f"Question: {question}\n\nGenerate the SQL query:"

    if retry_count > 0 and previous_sql and validation_error:
        user_message = f"""Question: {question}

PREVIOUS ATTEMPT FAILED:
SQL you generated: {previous_sql}
Validation error: {validation_error}

Fix the SQL based on the error above and generate a corrected query:"""

    return system_prompt.format(
        schema_context=schema_context,
        role=role
    ) + "\n\n" + user_message


def build_response_formatter_prompt(question: str, sql:str, results: list[dict], row_count: int, role: str) -> str:
    """
    Builds the prompt for Node 5 (Response Formatting).

    Takes raw SQL results and converts to human-readable response.

    WHY USE LLM FOR FORMATTING?
    Raw SQL results look like: [{"amount": 1234.56, "status": "pending"}]
    Users want: "There are 47 pending transactions totaling $12,456.78"

    The LLM understands the original question's intent and formats
    the answer accordingly — summary for aggregate questions,
    table description for list questions.
    """
    results_preview = results[:20] if len(results) > 20 else results

    return f"""You are a helpful data analyst. 
                Convert these SQL query results into a clear, natural language response.

                Original question: {question}
                SQL executed: {sql}
                Total rows returned: {row_count}
                Results (first {len(results_preview)} rows): {results_preview}
                User role: {role}

                Rules:
                1. Be concise and direct — answer the question
                2. Include key numbers and totals where relevant
                3. If results are empty, say so clearly and suggest why
                4. Don't mention SQL or technical details
                5. Format currency with $ and 2 decimal places
                6. For large result sets (>10 rows), give a summary not a list

                Response:"""