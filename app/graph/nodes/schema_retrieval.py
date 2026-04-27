from app.graph.state import GraphState
from app.vector_store.indexer import retrieve_relevant_schemas
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def schema_retrieval_node(state: GraphState) -> GraphState:
    """
    Retrieves top-3 most relevant schema documents from Qdrant.

    Uses semantic similarity between the user's question
    and our pre-embedded schema descriptions.

    Returns updated state with retrieved_schemas populated.
    """
    question = state["question"]

    logger.info(
        "Node 1 — Schema Retrieval | question='%s'",
        question[:60]
    )

    try:
        schemas = await retrieve_relevant_schemas(
            query=question,
            top_k=3   
        )

        logger.info(
            "Node 1 complete | retrieved=%d schemas | top_doc=%s | score=%.4f",
            len(schemas),
            schemas[0]["doc_id"] if schemas else "none",
            schemas[0]["score"] if schemas else 0.0
        )

        return {**state, "retrieved_schemas": schemas}

    except Exception as e:
        logger.error("Node 1 failed | error=%s", str(e))
        return {
            **state,
            "retrieved_schemas": [],
            "error_message": f"Schema retrieval failed: {str(e)}"
        }