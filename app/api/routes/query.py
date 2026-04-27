import time
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.models import TokenData
from app.auth.rbac import get_current_user
from app.cache.redis_cache import semantic_cache
from app.db.connection import get_pool
from app.graph.pipeline import run_pipeline
from app.vector_store.embedder import embed_text
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["Query"])


class QueryRequest(BaseModel):
    """
    What the client sends.
    Just the natural language question — everything else
    comes from the JWT token (who you are, your role).
    """
    question: str

    class Config:
        json_schema_extra = {
            "example": {
                "question": "show me all pending transactions this week"
            }
        }


class QueryResponse(BaseModel):
    """
    What we send back to the client.
    Includes the answer + metadata for transparency.
    """
    question:        str
    answer:          str
    generated_sql:   str | None
    row_count:       int
    was_cache_hit:   bool
    execution_time_ms: int
    role:            str
    username:        str


async def _log_query(
    pool:           asyncpg.Pool,
    user_id:        int,
    question:       str,
    generated_sql:  str | None,
    was_cache_hit:  bool,
    execution_time: int,
    row_count:      int,
    error_message:  str | None
) -> None:
    """
    Logs every query to the query_logs table.

    WHY LOG EVERY QUERY?
    1. Security audit — who asked what and when
    2. Performance monitoring — which queries are slow?
    3. Cache analytics — what % of queries hit cache?
    4. Business insight — what are users asking most?
    5. Debugging — what SQL was generated for a failed query?

    This runs AFTER the response is sent — never blocks the user.
    If logging fails, we catch it silently — never break the response.
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO query_logs (
                    user_id, natural_language_query, generated_sql,
                    was_cache_hit, execution_time_ms,
                    row_count, error_message
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                user_id,
                question,
                generated_sql,
                was_cache_hit,
                execution_time,
                row_count,
                error_message
            )
        logger.info(
            "Query logged | user_id=%d | cache_hit=%s | time=%dms",
            user_id, was_cache_hit, execution_time
        )
    except Exception as e:
        logger.error("Query logging failed (non-fatal) | %s", str(e))


@router.post("/", response_model=QueryResponse)
async def query(
    request:    QueryRequest,
    token_data: TokenData      = Depends(get_current_user),
    pool:       asyncpg.Pool   = Depends(get_pool)
):
    """
    The core endpoint — natural language → SQL → results.

    Flow:
    1. Validate question is not empty
    2. Embed question for cache lookup
    3. Check Redis semantic cache
    4. If miss: run full LangGraph pipeline
    5. Store result in cache
    6. Log to query_logs
    7. Return formatted response

    Protected by JWT — unauthenticated requests get 401.
    """
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty"
        )

    if len(question) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question too long — maximum 500 characters"
        )

    logger.info(
        "Query received | user=%s | role=%s | question='%s'",
        token_data.username, token_data.role.value, question[:60]
    )

    start_time = time.time()

    was_cache_hit  = False
    generated_sql  = None
    final_response = None
    row_count      = 0
    error_message  = None

    try:
        question_vector = await embed_text(question)

        cache_hit = semantic_cache.get(question, question_vector, user_id=token_data.user_id, role=token_data.role.value )

        if cache_hit:
            was_cache_hit  = True
            generated_sql  = cache_hit.get("generated_sql")
            final_response = cache_hit.get("result")
            row_count      = cache_hit.get("row_count", 0)

            logger.info(
                "Cache HIT | user=%s | similarity=%.4f | skipping pipeline",
                token_data.username,
                cache_hit.get("cache_similarity", 0)
            )

        else:
            logger.info("Cache MISS | user=%s | running pipeline", token_data.username)

            pipeline_result = await run_pipeline(
                question=question,
                token_data=token_data
            )

            generated_sql  = pipeline_result.get("generated_sql")
            final_response = pipeline_result.get("final_response")
            row_count      = pipeline_result.get("row_count", 0) or 0
            error_message  = pipeline_result.get("error_message")

            if final_response and not error_message:
                semantic_cache.set(
                    question=question,
                    question_vector=question_vector,
                    generated_sql=generated_sql or "",
                    result=final_response,
                    row_count=row_count,
                    user_id=token_data.user_id, 
                    role=token_data.role.value 
                )

    except Exception as e:
        error_message  = str(e)
        final_response = "An error occurred processing your query. Please try again."
        logger.error(
            "Query processing failed | user=%s | error=%s",
            token_data.username, error_message
        )

    execution_time_ms = int((time.time() - start_time) * 1000)

    await _log_query(
        pool=pool,
        user_id=token_data.user_id,
        question=question,
        generated_sql=generated_sql,
        was_cache_hit=was_cache_hit,
        execution_time=execution_time_ms,
        row_count=row_count,
        error_message=error_message
    )

    logger.info(
        "Query complete | user=%s | cache_hit=%s | rows=%d | time=%dms",
        token_data.username, was_cache_hit, row_count, execution_time_ms
    )

    return QueryResponse(
        question=question,
        answer=final_response or "No response generated.",
        generated_sql=generated_sql,
        row_count=row_count,
        was_cache_hit=was_cache_hit,
        execution_time_ms=execution_time_ms,
        role=token_data.role.value,
        username=token_data.username
    )


@router.get("/history")
async def query_history(token_data: TokenData = Depends(get_current_user), pool:asyncpg.Pool = Depends(get_pool),limit:int = 10):
    """Returns the user's recent query history.
    Admin sees ALL queries from all users.
    Supervisors and agents see only their own history.

    WHY THIS ENDPOINT?
    1. Users can see what they asked before
    2. Admins can audit who asked what
    3. Shows cache hit rate over time
    4. Great for the Streamlit dashboard (Phase 9)
    """
    async with pool.acquire() as conn:
        if token_data.role.value == "admin":
            # Admin sees everything
            rows = await conn.fetch(
                """
                SELECT
                    ql.id,
                    u.username,
                    u.role,
                    ql.natural_language_query,
                    ql.generated_sql,
                    ql.was_cache_hit,
                    ql.execution_time_ms,
                    ql.row_count,
                    ql.error_message,
                    ql.created_at
                FROM query_logs ql
                JOIN users u ON ql.user_id = u.id
                ORDER BY ql.created_at DESC
                LIMIT $1
                """,
                limit
            )
        else:
            # all others see only their own history
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    natural_language_query,
                    generated_sql,
                    was_cache_hit,
                    execution_time_ms,
                    row_count,
                    error_message,
                    created_at
                FROM query_logs
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                token_data.user_id,
                limit
            )

    return {
        "user":    token_data.username,
        "role":    token_data.role.value,
        "history": [dict(row) for row in rows]
    }