from openai import AsyncOpenAI
from app.graph.state import GraphState
from app.utils.config import config
from app.utils.prompt_templates import build_response_formatter_prompt
from app.utils.logger import get_logger

logger = get_logger(__name__)

_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)


async def response_formatter_node(state: GraphState) -> GraphState:
    """
    Formats query results into a natural language response.

    For empty results: explains clearly with context
    For large results: summarizes instead of listing all rows
    For aggregates: highlights key numbers
    """
    question     = state["question"]
    sql          = state.get("generated_sql", "")
    results      = state.get("query_result", [])
    row_count    = state.get("row_count", 0)
    token_data   = state["token_data"]
    error        = state.get("error_message")

    logger.info(
        "Node 5 — Response Formatter | rows=%d | user=%s",
        row_count, token_data.username
    )

    if error:
        return {
            **state,
            "final_response": f"Sorry, I encountered an error: {error}"
        }

    if state.get("execution_error"):
        return {
            **state,
            "final_response": (
                "Sorry, the query could not be executed. "
                "Please try rephrasing your question."
            )
        }

    try:
        prompt = build_response_formatter_prompt(
            question=question,
            sql=sql,
            results=results,
            row_count=row_count,
            role=token_data.role.value
        )

        response = await _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  
            max_tokens=400,
        )

        formatted = response.choices[0].message.content.strip()

        logger.info(
            "Node 5 complete | response_length=%d", len(formatted)
        )

        return {**state, "final_response": formatted}

    except Exception as e:
        logger.error("Node 5 failed | error=%s", str(e))
        fallback = f"Query returned {row_count} rows. Results: {results[:5]}"
        return {**state, "final_response": fallback}