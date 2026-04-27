from typing import TypedDict, Any
from app.auth.models import TokenData


class GraphState(TypedDict):
    """
    Complete state for the NL-to-SQL pipeline.
    Every field starts as None and gets populated
    as the graph progresses through nodes.
    """

    question: str
    token_data: TokenData
    retrieved_schemas: list[dict] | None
    generated_sql: str | None
    is_valid: bool | None
    validation_error: str | None
    retry_count: int
    query_result: list[dict] | None
    row_count: int | None
    execution_error: str | None
    final_response: str | None
    was_cache_hit: bool
    execution_time_ms: int | None
    error_message: str | None