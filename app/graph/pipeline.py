from langgraph.graph import StateGraph, END
from app.graph.state import GraphState
from app.graph.nodes.schema_retrieval   import schema_retrieval_node
from app.graph.nodes.sql_generation     import sql_generation_node
from app.graph.nodes.sql_validation     import sql_validation_node
from app.graph.nodes.sql_execution      import sql_execution_node
from app.graph.nodes.response_formatter import response_formatter_node
from app.utils.logger import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3


def should_retry_or_execute(state: GraphState) -> str:
    """
    Conditional edge function — called after Node 3 (validation).

    Decides which node to route to next based on state.

    Returns a string matching one of the edge destinations:
    - "execute"  → go to sql_execution_node
    - "retry"    → go back to sql_generation_node
    - "error"    → go to response_formatter_node (with error)

    WHY A FUNCTION NOT JUST IF/ELSE IN THE NODE?
    LangGraph requires edge routing to be separate from node logic.
    Nodes only read/write state. Edges decide where to go.
    This separation makes the graph easy to visualize and debug.
    """
    is_valid    = state.get("is_valid")
    error       = state.get("error_message")
    retry_count = state.get("retry_count", 0)

    if error:
        logger.info("Edge decision: ERROR → response_formatter")
        return "error"

    if is_valid:
        logger.info("Edge decision: VALID → sql_execution")
        return "execute"

    if retry_count >= MAX_RETRIES:
        logger.info(
            "Edge decision: MAX RETRIES (%d) reached → response_formatter",
            MAX_RETRIES
        )
        return "error"

    logger.info(
        "Edge decision: INVALID → retry sql_generation (attempt %d/%d)",
        retry_count, MAX_RETRIES
    )
    return "retry"


def build_pipeline() -> StateGraph:
    """
    Assembles and compiles the complete LangGraph pipeline.

    Called ONCE at application startup.
    The compiled graph is reused for every query.
    """
    logger.info("Building LangGraph pipeline...")

    graph = StateGraph(GraphState)

    graph.add_node("schema_retrieval",   schema_retrieval_node)
    graph.add_node("sql_generation",     sql_generation_node)
    graph.add_node("sql_validation",     sql_validation_node)
    graph.add_node("sql_execution",      sql_execution_node)
    graph.add_node("response_formatter", response_formatter_node)


    graph.set_entry_point("schema_retrieval")

    graph.add_edge("schema_retrieval", "sql_generation")

    graph.add_edge("sql_generation", "sql_validation")

    graph.add_conditional_edges(
        "sql_validation",           
        should_retry_or_execute,   
        {
            "execute": "sql_execution",     
            "retry":   "sql_generation",    
            "error":   "response_formatter"  #
        }
    )

    graph.add_edge("sql_execution", "response_formatter")

    graph.add_edge("response_formatter", END)

    compiled = graph.compile()
    logger.info("LangGraph pipeline compiled successfully.")

    return compiled

pipeline = build_pipeline()


async def run_pipeline(
    question:   str,
    token_data,
) -> GraphState:
    """
    Main entry point for running the pipeline.

    Initializes state with all None values,
    sets the question and token_data,
    invokes the graph,
    returns the final state.

    Called from:
    1. The FastAPI /query route (Phase 7)
    2. Direct testing (this phase)
    """
    logger.info(
        "Pipeline invoked | user=%s | role=%s | question='%s'",
        token_data.username, token_data.role.value, question[:60]
    )

    initial_state: GraphState = {
        "question":         question,
        "token_data":       token_data,
        "retrieved_schemas": None,
        "generated_sql":    None,
        "is_valid":         None,
        "validation_error": None,
        "retry_count":      0,
        "query_result":     None,
        "row_count":        None,
        "execution_error":  None,
        "final_response":   None,
        "was_cache_hit":    False,
        "execution_time_ms": None,
        "error_message":    None,
    }

    final_state = await pipeline.ainvoke(initial_state)

    logger.info(
        "Pipeline complete | user=%s | rows=%s | cache_hit=%s",
        token_data.username,
        final_state.get("row_count"),
        final_state.get("was_cache_hit")
    )

    return final_state